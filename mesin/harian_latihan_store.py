"""Penyimpanan Latihan Harian: sesi 10 soal PG per tingkat, jawaban terkunci, batas gratis, dan ringkasan.

Aturan yang ditegakkan DI SINI (bukan di halaman), semuanya per `siswa_id` yang diberikan pemanggil dari sesi
server (tidak pernah dari URL/form):
- Kepemilikan: sesi yang bukan milik anak itu = `HarianTidakDitemukan` (pemanggil menjawab 404 identik), tanpa efek.
- Satu sesi berjalan per anak (indeks unik parsial). `mulai` menjalankan urutan: sesi berjalan dilanjutkan
  (tidak dihitung lagi) -> batas gratis (`akses_harian`; sesi dikerjakan hari kalender WIB `sekarang`, lihat `sesi_dikerjakan_hari_ini`) -> rakit -> simpan.
- Soal disimpan sebagai snapshot saat sesi dibuat. `muat_soal` membaca proyeksi AMAN (penyajian + empat opsi) lebih
  dulu; kunci dan pembahasan baru dibaca setelah soal itu terjawab (`UmpanBalik`). Soal hanya terbuka berurutan:
  nomor n bisa dibuka/dijawab bila n <= banyak jawaban + 1, jadi soal berikutnya tidak bocor.
- Jawab sekali: INSERT polos pada PRIMARY KEY (sesi_id, nomor); jawaban kedua = `diterima=False` tanpa efek.
  Jawaban ke-`jumlah_soal` menutup sesi (status `selesai`) dalam transaksi yang sama.
- Bukan bukti siklus belajar: modul ini tidak menyentuh tabel sesi/diagnosis/jawaban/soal guru dan tidak
  memanggil `learning_cycle`.
`mulai` dan `jawab` wajib dipanggil di dalam transaksi tulis pemanggil (`BEGIN IMMEDIATE`); tanpa commit di sini.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import secrets
import sqlite3
from typing import Optional, Sequence, Tuple

import akses_harian
import harian_rakit
import harian_tingkat
import harian_waktu
import visual_contract

HURUF_PILIHAN = ("A", "B", "C", "D")
STATUS_BERJALAN = "berjalan"
STATUS_SELESAI = "selesai"
HARI_RIWAYAT = 7


class HarianTidakDitemukan(LookupError):
    """Sesi/soal tidak ada, bukan milik anak ini, atau belum gilirannya; dijawab 404 identik tanpa efek."""


class TingkatTidakSah(ValueError):
    """Kode tingkat bukan salah satu `harian_tingkat.KODE_SAH`."""


class PilihanTidakSah(ValueError):
    """Pilihan jawaban bukan salah satu huruf A-D."""


class BatasGratisHabis(Exception):
    """Jatah sesi gratis hari ini (WIB) habis dan tidak ada sesi berjalan untuk dilanjutkan."""


@dataclass(frozen=True)
class SesiRingkas:
    id: int
    tingkat: str
    status: str
    jumlah_soal: int
    terjawab: int
    mulai_epoch: int
    selesai_epoch: Optional[int]

    @property
    def berjalan(self) -> bool:
        return self.status == STATUS_BERJALAN

    @property
    def nomor_berikut(self) -> int:
        """Nomor soal yang bisa dikerjakan berikutnya (soal terakhir bila semua terjawab)."""
        return min(self.terjawab + 1, self.jumlah_soal)


@dataclass(frozen=True)
class SoalAnak:
    """Proyeksi aman satu soal untuk halaman anak: TANPA kunci, pembahasan, atau penanda benar/salah."""

    nomor: int
    jumlah: int
    penyajian: visual_contract.PenyajianPertanyaan
    opsi: Tuple[str, ...]


@dataclass(frozen=True)
class UmpanBalik:
    """Dibaca HANYA setelah soal terjawab: pilihan anak, benar/salah, indeks kunci, dan pembahasan."""

    pilihan: int
    benar: bool
    kunci_indeks: int
    pembahasan: str
    beruntun: int = 1  # jawaban berturut-turut (termasuk soal ini) dengan hasil benar/salah yang sama


@dataclass(frozen=True)
class HasilJawab:
    diterima: bool  # False bila soal itu sudah dijawab (ditolak, tanpa efek)
    benar: Optional[bool]
    selesai: bool


@dataclass(frozen=True)
class Kuota:
    akses: akses_harian.Akses
    terpakai: int
    habis: bool


@dataclass(frozen=True)
class RingkasanSesi:
    tingkat: str
    jumlah_soal: int
    benar: int


@dataclass(frozen=True)
class RingkasanHarian:
    """Angka aktivitas 7 hari WIB terakhir untuk halaman orang tua."""

    tingkat_terakhir: Optional[str]
    hari: Tuple[Tuple[str, bool], ...]  # (tanggal WIB, ada latihan), terlama dulu
    soal_dikerjakan: int
    soal_benar: int

    @property
    def jumlah_hari(self) -> int:
        return sum(1 for _t, ada in self.hari if ada)

    @property
    def persen_benar(self) -> Optional[int]:
        if self.soal_dikerjakan == 0:
            return None
        return round(100 * self.soal_benar / self.soal_dikerjakan)


def _seed_baru() -> int:
    return secrets.randbelow(harian_rakit.SEED_MAKS) + 1


def _wajib_transaksi(kon: sqlite3.Connection) -> None:
    if not kon.in_transaction:
        raise RuntimeError("operasi tulis Latihan Harian wajib di dalam transaksi (BEGIN IMMEDIATE)")


_SELECT_SESI = (
    "SELECT s.id, s.tingkat, s.status, s.jumlah_soal, s.mulai_epoch, s.selesai_epoch, "
    "(SELECT COUNT(*) FROM harian_jawaban j WHERE j.sesi_id = s.id) AS terjawab FROM harian_sesi s ")


def _ke_ringkas(baris) -> SesiRingkas:
    return SesiRingkas(baris["id"], baris["tingkat"], baris["status"], baris["jumlah_soal"],
                       baris["terjawab"], baris["mulai_epoch"], baris["selesai_epoch"])


def sesi_berjalan(kon, siswa_id: int) -> Optional[SesiRingkas]:
    baris = kon.execute(_SELECT_SESI + "WHERE s.siswa_id = ? AND s.status = 'berjalan'", (siswa_id,)).fetchone()
    return None if baris is None else _ke_ringkas(baris)


def ambil_sesi(kon, siswa_id: int, sesi_id: int) -> SesiRingkas:
    """Sesi milik anak ini; selain itu `HarianTidakDitemukan` (identik untuk id asing dan id tak ada)."""
    baris = kon.execute(_SELECT_SESI + "WHERE s.id = ? AND s.siswa_id = ?", (sesi_id, siswa_id)).fetchone()
    if baris is None:
        raise HarianTidakDitemukan(sesi_id)
    return _ke_ringkas(baris)


def tingkat_terakhir(kon, siswa_id: int) -> Optional[str]:
    baris = kon.execute("SELECT tingkat FROM harian_sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT 1",
                        (siswa_id,)).fetchone()
    return None if baris is None else baris["tingkat"]


def sesi_dikerjakan_hari_ini(kon, siswa_id: int, sekarang: int) -> int:
    """Sesi anak ini yang DIKERJAKAN pada hari WIB `sekarang`: dimulai hari itu ATAU ada soal yang dijawab hari itu.

    Menyelesaikan sesi menggantung dari hari sebelumnya ikut memakai jatah hari baru, jadi akun gratis tidak
    bisa menyelesaikan sesi lama lalu memulai sesi baru di hari yang sama (±2 sesi/hari). Dipilih ketimbang
    menutup sesi menggantung saat hari berganti: status sesi dikunci CHECK skema (hanya berjalan/selesai) dan
    menandai selesai akan merusak ringkasan sesi. Melanjutkan tanpa menjawab belum dihitung.
    """
    awal, akhir = harian_waktu.batas_hari_wib(sekarang)
    return kon.execute(
        "SELECT COUNT(*) FROM harian_sesi s WHERE s.siswa_id = ? AND ((s.mulai_epoch >= ? AND s.mulai_epoch < ?) "
        "OR EXISTS (SELECT 1 FROM harian_jawaban j WHERE j.sesi_id = s.id AND j.dijawab_epoch >= ? "
        "AND j.dijawab_epoch < ?))", (siswa_id, awal, akhir, awal, akhir)).fetchone()[0]


def kuota(kon, siswa_id: int, sekarang: int) -> Kuota:
    """Akses (`akses_harian`) dan jatah hari ini; `habis` hanya bila TIDAK tanpa batas dan jatah gratis terpakai."""
    akses = akses_harian.akses(kon, siswa_id, harian_waktu.kini_baku(sekarang))
    terpakai = sesi_dikerjakan_hari_ini(kon, siswa_id, sekarang)
    return Kuota(akses, terpakai, (not akses.tanpa_batas) and terpakai >= akses_harian.BATAS_GRATIS_PER_HARI)


def _simpan_sesi(kon, siswa_id: int, kode: str, sekarang: int) -> int:
    seed = _seed_baru()
    rakitan = harian_rakit.rakit_sesi(kode, seed)
    sesi_id = kon.execute(
        "INSERT INTO harian_sesi (siswa_id, tingkat, seed, jumlah_soal, mulai_epoch, status) "
        "VALUES (?, ?, ?, ?, ?, 'berjalan')", (siswa_id, kode, seed, len(rakitan), sekarang)).lastrowid
    for r in rakitan:
        s = r.soal
        kon.execute(
            "INSERT INTO harian_soal (sesi_id, nomor, template_id, topik_id, level, sumber, ulangan, tanda_tangan, "
            "penyajian_json, opsi_json, kunci_indeks, pembahasan) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sesi_id, r.nomor, s.template_id, s.topik_id, s.level, r.sumber, int(r.ulangan), s.tanda_tangan,
             s.penyajian_json, json.dumps(list(s.opsi), ensure_ascii=False), s.kunci_indeks, s.pembahasan))
    return sesi_id


def mulai(kon, siswa_id: int, kode_tingkat, sekarang: int) -> Tuple[SesiRingkas, bool]:
    """Mulai sesi baru di tingkat `kode_tingkat`, atau lanjutkan yang berjalan: (sesi, baru).

    Urutan: tingkat sah -> sesi berjalan dilanjutkan (tanpa dihitung) -> batas gratis -> rakit dan simpan.
    `BatasGratisHabis` terjadi sebelum menulis apa pun.
    """
    _wajib_transaksi(kon)
    try:
        harian_tingkat.ambil_tingkat(kode_tingkat)
    except KeyError as galat:
        raise TingkatTidakSah(str(kode_tingkat)[:20]) from galat
    berjalan = sesi_berjalan(kon, siswa_id)
    if berjalan is not None:
        return berjalan, False
    if kuota(kon, siswa_id, sekarang).habis:
        raise BatasGratisHabis()
    return ambil_sesi(kon, siswa_id, _simpan_sesi(kon, siswa_id, kode_tingkat, sekarang)), True


def _cek_giliran(sesi: SesiRingkas, nomor: int) -> None:
    """Soal terbuka hanya bila 1 <= nomor <= jumlah dan nomor <= jawaban + 1 (tanpa melompat ke depan)."""
    if type(nomor) is not int or not 1 <= nomor <= sesi.jumlah_soal or nomor > sesi.terjawab + 1:
        raise HarianTidakDitemukan(nomor)


def muat_soal(kon, siswa_id: int, sesi_id: int, nomor: int) -> Tuple[SoalAnak, Optional[UmpanBalik]]:
    """(soal aman, umpan balik atau None). Kunci/pembahasan dibaca hanya bila soal ini sudah terjawab."""
    sesi = ambil_sesi(kon, siswa_id, sesi_id)
    _cek_giliran(sesi, nomor)
    aman = kon.execute("SELECT penyajian_json, opsi_json FROM harian_soal WHERE sesi_id = ? AND nomor = ?",
                       (sesi_id, nomor)).fetchone()
    if aman is None:
        raise HarianTidakDitemukan(nomor)
    soal = SoalAnak(nomor, sesi.jumlah_soal, visual_contract.deserialisasi_penyajian(aman["penyajian_json"]),
                    tuple(json.loads(aman["opsi_json"])))
    jawaban = kon.execute("SELECT pilihan, benar FROM harian_jawaban WHERE sesi_id = ? AND nomor = ?",
                          (sesi_id, nomor)).fetchone()
    if jawaban is None:
        return soal, None
    kunci = kon.execute("SELECT kunci_indeks, pembahasan FROM harian_soal WHERE sesi_id = ? AND nomor = ?",
                        (sesi_id, nomor)).fetchone()
    umpan = UmpanBalik(jawaban["pilihan"], bool(jawaban["benar"]), kunci["kunci_indeks"], kunci["pembahasan"])
    return soal, replace(umpan, beruntun=_hitung_beruntun(kon, sesi_id, nomor, umpan.benar))


def _hitung_beruntun(kon, sesi_id: int, nomor: int, benar: bool) -> int:
    """Berapa jawaban terakhir (sampai soal `nomor`, dalam sesi ini) yang hasilnya sama dengan `benar`."""
    baris = kon.execute("SELECT benar FROM harian_jawaban WHERE sesi_id = ? AND nomor <= ? ORDER BY nomor DESC",
                        (sesi_id, nomor)).fetchall()
    jumlah = 0
    for b in baris:
        if bool(b["benar"]) != benar:
            break
        jumlah += 1
    return jumlah


def jawab(kon, siswa_id: int, sesi_id: int, nomor: int, huruf, sekarang: int) -> HasilJawab:
    """Kunci jawaban soal `nomor`; jawaban kedua untuk soal yang sama ditolak (`diterima=False`) tanpa efek."""
    _wajib_transaksi(kon)
    if huruf not in HURUF_PILIHAN:
        raise PilihanTidakSah(str(huruf)[:10])
    sesi = ambil_sesi(kon, siswa_id, sesi_id)
    if type(nomor) is not int or not 1 <= nomor <= sesi.jumlah_soal:
        raise HarianTidakDitemukan(nomor)
    if nomor <= sesi.terjawab:
        return HasilJawab(False, None, False)
    _cek_giliran(sesi, nomor)
    pilihan = HURUF_PILIHAN.index(huruf)
    kunci = kon.execute("SELECT kunci_indeks FROM harian_soal WHERE sesi_id = ? AND nomor = ?",
                        (sesi_id, nomor)).fetchone()["kunci_indeks"]
    benar = pilihan == kunci
    try:
        kon.execute("INSERT INTO harian_jawaban (sesi_id, nomor, pilihan, benar, dijawab_epoch) VALUES (?, ?, ?, ?, ?)",
                    (sesi_id, nomor, pilihan, int(benar), sekarang))
    except sqlite3.IntegrityError:
        return HasilJawab(False, None, False)
    selesai = nomor == sesi.jumlah_soal
    if selesai:
        kon.execute("UPDATE harian_sesi SET status = 'selesai', selesai_epoch = ? WHERE id = ? AND status = 'berjalan'",
                    (sekarang, sesi_id))
    return HasilJawab(True, benar, selesai)


def ringkasan_sesi(kon, siswa_id: int, sesi_id: int) -> Optional[RingkasanSesi]:
    """Jumlah benar dari sesi yang SUDAH selesai; None bila sesi masih berjalan. Tanpa peringkat atau perbandingan."""
    sesi = ambil_sesi(kon, siswa_id, sesi_id)
    if sesi.berjalan:
        return None
    benar = kon.execute("SELECT COALESCE(SUM(benar), 0) FROM harian_jawaban WHERE sesi_id = ?", (sesi_id,)).fetchone()[0]
    return RingkasanSesi(sesi.tingkat, sesi.jumlah_soal, int(benar))


def _jawaban_antara(kon, siswa_id: int, dari: int, sampai: int):
    return kon.execute(
        "SELECT j.dijawab_epoch, j.benar FROM harian_jawaban j JOIN harian_sesi s ON s.id = j.sesi_id "
        "WHERE s.siswa_id = ? AND j.dijawab_epoch >= ? AND j.dijawab_epoch < ?", (siswa_id, dari, sampai)).fetchall()


def hari_latihan(kon, siswa_id: int, tanggal: Sequence[str], sekarang: int) -> Tuple[Tuple[str, bool], ...]:
    """Untuk tiap tanggal WIB di `tanggal`: apakah ada soal yang dijawab pada hari itu."""
    awal = harian_waktu.awal_hari_wib(sekarang) - 8 * harian_waktu.DETIK_PER_HARI
    akhir = harian_waktu.awal_hari_wib(sekarang) + 8 * harian_waktu.DETIK_PER_HARI
    ada = {harian_waktu.tanggal_wib(b["dijawab_epoch"]) for b in _jawaban_antara(kon, siswa_id, awal, akhir)}
    return tuple((t, t in ada) for t in tanggal)


def ringkasan_harian(kon, siswa_id: int, sekarang: int) -> RingkasanHarian:
    """Aktivitas 7 hari WIB terakhir (termasuk hari ini): hari latihan, soal dikerjakan, soal benar."""
    hari = harian_waktu.tujuh_hari_hingga(sekarang)
    awal = harian_waktu.awal_hari_wib(sekarang) - (HARI_RIWAYAT - 1) * harian_waktu.DETIK_PER_HARI
    akhir = harian_waktu.awal_hari_wib(sekarang) + harian_waktu.DETIK_PER_HARI
    baris = _jawaban_antara(kon, siswa_id, awal, akhir)
    ada = {harian_waktu.tanggal_wib(b["dijawab_epoch"]) for b in baris}
    return RingkasanHarian(tingkat_terakhir(kon, siswa_id), tuple((t, t in ada) for t in hari), len(baris),
                           sum(1 for b in baris if b["benar"]))

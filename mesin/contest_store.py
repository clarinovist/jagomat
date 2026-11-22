"""Penyimpanan sesi Latihan Lomba: timer yang dipegang server, jawaban, dan nilai.

Semua batas waktu memakai epoch detik dari jam server; `sekarang` selalu parameter (handler
memberi `int(time.time())`, tes memberi angka tetap). Jam klien tidak pernah dipercaya.
Sesi yang lewat batas ditutup secara malas (saat dibaca, disimpan, atau dikumpulkan) dengan satu
pernyataan UPDATE bersyarat, dan simpan jawaban satu pernyataan atomik yang menolak diri sendiri
bila sesi bukan milik anak itu, sudah tidak berjalan, atau sudah melewati batas.

Halaman anak hanya boleh memakai `soal_untuk_anak` (kolom aman); kunci dan pembahasan hanya dibaca
`hasil_ringkas` setelah sesi tidak lagi berjalan.

Dua mode (`lomba_sesi.mode`): Latihan (10 soal) dan Simulasi (35 soal). Batas waktu disalin ke `batas_epoch` saat
sesi dimulai, jadi mengubah durasi anak tidak memengaruhi sesi yang sedang berjalan. Satu sesi berjalan per anak,
apa pun modenya. Nomor soal sah di batas HTTP: 1..MAKS_NOMOR; nomor di luar jumlah soal sesi itu -> tidak ditemukan.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import AbstractSet, FrozenSet, Optional, Sequence, Tuple

import contest_core as C
import contest_session as S
import contest_templates

DURASI_DETIK = 15 * 60
DURASI_SIMULASI_DETIK = 60 * 60
DURASI_MAKS_DETIK = 180 * 60      # sama dengan CHECK durasi di lomba_penugasan
PAKET_ID = "corexis_l1_matematika"
BERJALAN, DIKUMPUL, WAKTU_HABIS = "berjalan", "dikumpul", "waktu_habis"
LATIHAN, SIMULASI = "latihan", "simulasi"
SEED_BIT = 63
NOMOR_PERTAMA, NOMOR_TERAKHIR = 1, S.JUMLAH_SOAL    # NOMOR_TERAKHIR = jumlah soal Latihan
MAKS_NOMOR = 35                                     # sama dengan CHECK nomor di lomba_soal
_DURASI_BAWAAN = {LATIHAN: DURASI_DETIK, SIMULASI: DURASI_SIMULASI_DETIK}
_POLA_ISIAN = re.compile(r"^[0-9]{1,6}$")
_SAVEPOINT = "lomba_mulai"
_KOLOM_SESI = ("id, siswa_id, status, mulai_epoch, batas_epoch, selesai_epoch, mode, "
               "(SELECT COUNT(*) FROM lomba_soal WHERE sesi_id = lomba_sesi.id) AS jumlah_soal")
_SYARAT_BERJALAN = ("EXISTS (SELECT 1 FROM lomba_sesi WHERE id = ? AND siswa_id = ? "
                    "AND status = 'berjalan' AND batas_epoch > ?)")


class SesiTidakDitemukan(LookupError):
    """Sesi atau nomor tidak ada, atau bukan milik anak itu (pemanggil menjawab 404 yang identik)."""


class SesiSelesai(RuntimeError):
    """Sesi sudah dikumpulkan atau waktunya habis; jawaban tidak diterima lagi."""


class SesiBerjalan(RuntimeError):
    """Hasil belum boleh dilihat selama sesi masih berjalan."""


class JawabanTidakSah(ValueError):
    """Bentuk jawaban tidak cocok dengan jenis soal."""


@dataclass(frozen=True)
class SesiRingkas:
    id: int
    siswa_id: int
    status: str
    mulai_epoch: int
    batas_epoch: int
    selesai_epoch: Optional[int]
    mode: str = LATIHAN
    jumlah_soal: int = NOMOR_TERAKHIR

    def sisa_detik(self, sekarang: int) -> int:
        return max(0, self.batas_epoch - sekarang) if self.status == BERJALAN else 0


@dataclass(frozen=True)
class SoalAnak:
    nomor: int
    jenis: str
    topik: str
    teks: str
    svg: str
    pilihan: Tuple[str, ...]
    gambar_pilihan: Tuple[str, ...]
    jawaban: Optional[str]


@dataclass(frozen=True)
class HasilRingkas:
    nilai: int
    jumlah_soal: int
    waktu_terpakai_detik: int
    status: str


def _ringkas(baris) -> SesiRingkas:
    return SesiRingkas(id=baris["id"], siswa_id=baris["siswa_id"], status=baris["status"],
                       mulai_epoch=baris["mulai_epoch"], batas_epoch=baris["batas_epoch"],
                       selesai_epoch=baris["selesai_epoch"], mode=baris["mode"], jumlah_soal=baris["jumlah_soal"])


def _finalkan_habis(kon, siswa_id: int, sekarang: int) -> None:
    """Tutup sesi berjalan milik anak yang batasnya sudah lewat; selesai = batas, bukan saat dibuka."""
    kon.execute(
        "UPDATE lomba_sesi SET status = 'waktu_habis', selesai_epoch = batas_epoch "
        "WHERE siswa_id = ? AND status = 'berjalan' AND ? >= batas_epoch", (siswa_id, sekarang))


def _berjalan(kon, siswa_id: int) -> Optional[SesiRingkas]:
    baris = kon.execute(f"SELECT {_KOLOM_SESI} FROM lomba_sesi WHERE siswa_id = ? AND status = 'berjalan'",
                        (siswa_id,)).fetchone()
    return _ringkas(baris) if baris else None


def tutup_yang_habis(kon, siswa_id: int, sekarang: int) -> None:
    """Tutup sesi berjalan milik anak yang batasnya sudah lewat (untuk pembaca riwayat)."""
    _finalkan_habis(kon, siswa_id, sekarang)


def sesi_berjalan(kon, siswa_id: int, sekarang: int) -> Optional[SesiRingkas]:
    _finalkan_habis(kon, siswa_id, sekarang)
    return _berjalan(kon, siswa_id)


def ambil_sesi(kon, siswa_id: int, sesi_id: int, sekarang: int) -> SesiRingkas:
    _finalkan_habis(kon, siswa_id, sekarang)
    baris = kon.execute(f"SELECT {_KOLOM_SESI} FROM lomba_sesi WHERE id = ? AND siswa_id = ?",
                        (sesi_id, siswa_id)).fetchone()
    if baris is None:
        raise SesiTidakDitemukan(sesi_id)
    return _ringkas(baris)


def _pastikan_milik(kon, siswa_id: int, sesi_id: int) -> None:
    ada = kon.execute("SELECT 1 FROM lomba_sesi WHERE id = ? AND siswa_id = ?", (sesi_id, siswa_id)).fetchone()
    if ada is None:
        raise SesiTidakDitemukan(sesi_id)


def _riwayat(kon, siswa_id: int) -> Tuple[Tuple[FrozenSet[str], ...], FrozenSet[str]]:
    """(tanda tangan soal per sesi untuk 5 sesi terakhir apa pun modenya, terbaru dulu;
    id template 2 sesi LATIHAN terakhir) milik anak ini.

    Rotasi jenis hanya membaca sesi Latihan: satu simulasi memakai hampir semua jenis, jadi bila ikut dihitung
    rotasi Latihan berikutnya hampir pasti gagal lalu dilepas juga, hanya lebih lambat.
    """
    ids = [baris[0] for baris in kon.execute(
        "SELECT id FROM lomba_sesi WHERE siswa_id = ? ORDER BY id DESC LIMIT ?", (siswa_id, S.RIWAYAT_SESI))]
    latihan = [baris[0] for baris in kon.execute(
        "SELECT id FROM lomba_sesi WHERE siswa_id = ? AND mode = 'latihan' ORDER BY id DESC LIMIT ?",
        (siswa_id, S.ROTASI_SESI))]

    def kolom(nama: str, sesi_id: int) -> FrozenSet[str]:
        return frozenset(baris[0] for baris in kon.execute(
            f"SELECT {nama} FROM lomba_soal WHERE sesi_id = ?", (sesi_id,)))

    dihindari = frozenset().union(*(kolom("template_id", i) for i in latihan))
    return tuple(kolom("tanda_tangan", i) for i in ids), dihindari


def _baris_soal(sesi_id: int, butir: S.ButirSesi) -> tuple:
    soal = butir.soal
    pengecoh = [{"nilai": p.nilai, "kesalahan": p.kesalahan, "svg": C.tanpa_atribut_data(p.svg)}
                for p in soal.pengecoh]
    return (sesi_id, butir.nomor, soal.template_id, soal.topik, soal.jenis, soal.tingkat,
            C.tanda_tangan(soal), soal.parameter, int(soal.inggris), soal.teks, C.tanpa_atribut_data(soal.svg),
            soal.kunci, json.dumps(list(butir.pilihan), ensure_ascii=False),
            json.dumps([C.tanpa_atribut_data(g) for g in butir.gambar_pilihan], ensure_ascii=False),
            butir.posisi_kunci,
            json.dumps(pengecoh, ensure_ascii=False), json.dumps(list(soal.pembahasan), ensure_ascii=False))


def _simpan_soal(kon, sesi_id: int, sesi: S.Sesi) -> None:
    kon.executemany(
        "INSERT INTO lomba_soal(sesi_id, nomor, template_id, topik, jenis, tingkat, tanda_tangan, parameter, "
        "inggris, teks, svg, kunci, pilihan_json, gambar_pilihan_json, posisi_kunci, pengecoh_json, "
        "pembahasan_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [_baris_soal(sesi_id, butir) for butir in sesi.butir])


def _simpan_sesi_baru(kon, siswa_id: int, sekarang: int, seed: int, sesi: S.Sesi, mode: str,
                      durasi_detik: int) -> SesiRingkas:
    """Sesi dan semua soalnya masuk atau batal bersama; yang kalah balapan melanjutkan pemenang."""
    kon.execute(f"SAVEPOINT {_SAVEPOINT}")
    try:
        kursor = kon.execute(
            "INSERT INTO lomba_sesi(siswa_id, paket_id, seed, mulai_epoch, batas_epoch, status, mode) "
            "VALUES (?, ?, ?, ?, ?, 'berjalan', ?)",
            (siswa_id, PAKET_ID, seed, sekarang, sekarang + durasi_detik, mode))
    except sqlite3.IntegrityError:
        kon.execute(f"ROLLBACK TO {_SAVEPOINT}")
        kon.execute(f"RELEASE {_SAVEPOINT}")
        pemenang = _berjalan(kon, siswa_id)
        if pemenang is None:
            raise
        return pemenang
    try:
        _simpan_soal(kon, kursor.lastrowid, sesi)
    except Exception:
        kon.execute(f"ROLLBACK TO {_SAVEPOINT}")
        kon.execute(f"RELEASE {_SAVEPOINT}")
        raise
    kon.execute(f"RELEASE {_SAVEPOINT}")
    return SesiRingkas(id=kursor.lastrowid, siswa_id=siswa_id, status=BERJALAN, mulai_epoch=sekarang,
                       batas_epoch=sekarang + durasi_detik, selesai_epoch=None, mode=mode,
                       jumlah_soal=len(sesi.butir))


def _periksa_mulai(mode: str, durasi_detik: int) -> None:
    if mode not in _DURASI_BAWAAN:
        raise ValueError(f"mode sesi tidak dikenal: {mode!r}")
    if (isinstance(durasi_detik, bool) or not isinstance(durasi_detik, int)
            or not 0 < durasi_detik <= DURASI_MAKS_DETIK):
        raise ValueError(f"durasi harus 1 sampai {DURASI_MAKS_DETIK} detik")


def mulai_atau_lanjut(kon, siswa_id: int, sekarang: int, *, seed: Optional[int] = None,
                      pool: Optional[Sequence[C.Template]] = None, mode: str = LATIHAN,
                      durasi_detik: Optional[int] = None) -> SesiRingkas:
    """Lanjutkan sesi yang masih berjalan (apa pun modenya), atau rakit sesi baru mode `mode`.

    `durasi_detik` None = durasi bawaan mode. Soal baru: tanpa ulang soal 5 sesi terakhir (dilonggarkan dari sesi
    tertua bila perlu, lihat `contest_session.rakit_dengan_pelonggaran`), rotasi jenis untuk Latihan.
    """
    durasi = _DURASI_BAWAAN.get(mode, 0) if durasi_detik is None else durasi_detik
    _periksa_mulai(mode, durasi)
    _finalkan_habis(kon, siswa_id, sekarang)
    ada = _berjalan(kon, siswa_id)
    if ada is not None:
        return ada
    seed = secrets.randbits(SEED_BIT) if seed is None else seed
    katalog = contest_templates.katalog() if pool is None else pool
    larangan, dihindari = _riwayat(kon, siswa_id)
    sesi = S.rakit_dengan_pelonggaran(seed, katalog, larangan, template_dihindari=dihindari, mode=mode)
    return _simpan_sesi_baru(kon, siswa_id, sekarang, seed, sesi, mode, durasi)


def soal_untuk_anak(kon, siswa_id: int, sesi_id: int, nomor: int) -> SoalAnak:
    """Soal yang boleh dilihat anak: hanya kolom aman (tanpa kunci, pembahasan, atau label pengecoh)."""
    baris = kon.execute(
        "SELECT s.nomor, s.jenis, s.topik, s.teks, s.svg, s.pilihan_json, s.gambar_pilihan_json, j.jawaban "
        "FROM lomba_soal s JOIN lomba_sesi x ON x.id = s.sesi_id "
        "LEFT JOIN lomba_jawaban j ON j.sesi_id = s.sesi_id AND j.nomor = s.nomor "
        "WHERE s.sesi_id = ? AND s.nomor = ? AND x.siswa_id = ?", (sesi_id, nomor, siswa_id)).fetchone()
    if baris is None:
        raise SesiTidakDitemukan((sesi_id, nomor))
    return SoalAnak(nomor=baris["nomor"], jenis=baris["jenis"], topik=baris["topik"], teks=baris["teks"],
                    svg=baris["svg"], pilihan=tuple(json.loads(baris["pilihan_json"])),
                    gambar_pilihan=tuple(json.loads(baris["gambar_pilihan_json"])),
                    jawaban=baris["jawaban"])


def nomor_terjawab(kon, siswa_id: int, sesi_id: int) -> FrozenSet[int]:
    _pastikan_milik(kon, siswa_id, sesi_id)
    return frozenset(baris[0] for baris in kon.execute(
        "SELECT nomor FROM lomba_jawaban WHERE sesi_id = ?", (sesi_id,)))


def _jenis_soal(kon, siswa_id: int, sesi_id: int, nomor: int) -> str:
    baris = kon.execute(
        "SELECT s.jenis FROM lomba_soal s JOIN lomba_sesi x ON x.id = s.sesi_id "
        "WHERE s.sesi_id = ? AND s.nomor = ? AND x.siswa_id = ?", (sesi_id, nomor, siswa_id)).fetchone()
    if baris is None:
        raise SesiTidakDitemukan((sesi_id, nomor))
    return baris["jenis"]


def _normalkan_jawaban(jenis: str, jawaban: str) -> Optional[str]:
    """Jawaban baku untuk disimpan; None berarti "hapus jawaban"."""
    if not isinstance(jawaban, str):
        raise JawabanTidakSah("jawaban wajib teks")
    bersih = jawaban.strip()
    if not bersih:
        return None
    if jenis == C.JENIS_PG:
        huruf = bersih.upper()
        if huruf in C.HURUF:
            return huruf
    elif _POLA_ISIAN.match(bersih):
        return str(int(bersih))
    raise JawabanTidakSah(f"jawaban tidak sah untuk soal {jenis}")


def simpan_jawaban(kon, siswa_id: int, sesi_id: int, nomor: int, jawaban: str, sekarang: int) -> None:
    """Simpan (atau hapus bila kosong) jawaban; satu pernyataan atomik yang menegakkan batas waktu."""
    jenis = _jenis_soal(kon, siswa_id, sesi_id, nomor)
    nilai = _normalkan_jawaban(jenis, jawaban)
    if nilai is None:
        kursor = kon.execute(
            f"DELETE FROM lomba_jawaban WHERE sesi_id = ? AND nomor = ? AND {_SYARAT_BERJALAN}",
            (sesi_id, nomor, sesi_id, siswa_id, sekarang))
    else:
        kursor = kon.execute(
            "INSERT INTO lomba_jawaban(sesi_id, nomor, jawaban, diubah_epoch) "
            f"SELECT ?, ?, ?, ? WHERE {_SYARAT_BERJALAN} "
            "ON CONFLICT(sesi_id, nomor) DO UPDATE SET jawaban = excluded.jawaban, "
            "diubah_epoch = excluded.diubah_epoch",
            (sesi_id, nomor, nilai, sekarang, sesi_id, siswa_id, sekarang))
    if kursor.rowcount == 0 and ambil_sesi(kon, siswa_id, sesi_id, sekarang).status != BERJALAN:
        raise SesiSelesai(sesi_id)


def kumpulkan(kon, siswa_id: int, sesi_id: int, sekarang: int) -> SesiRingkas:
    """Akhiri sesi lebih awal; idempoten. Kumpul setelah batas dicatat sebagai waktu habis pada batas."""
    _pastikan_milik(kon, siswa_id, sesi_id)
    kon.execute(
        "UPDATE lomba_sesi SET status = CASE WHEN ? >= batas_epoch THEN 'waktu_habis' ELSE 'dikumpul' END, "
        "selesai_epoch = MAX(mulai_epoch, MIN(?, batas_epoch)) "
        "WHERE id = ? AND siswa_id = ? AND status = 'berjalan'", (sekarang, sekarang, sesi_id, siswa_id))
    return ambil_sesi(kon, siswa_id, sesi_id, sekarang)


def benar(jenis: str, kunci: str, pilihan: Sequence[str], jawaban: Optional[str]) -> bool:
    if jawaban is None:
        return False
    if jenis == C.JENIS_ISIAN:
        return C.jawaban_benar(kunci, jawaban, C.JENIS_ISIAN)
    return jawaban in C.HURUF and C.jawaban_benar(kunci, pilihan[C.HURUF.index(jawaban)], C.JENIS_PG)


def hasil_ringkas(kon, siswa_id: int, sesi_id: int, sekarang: int) -> HasilRingkas:
    """Nilai total dan waktu terpakai; hanya setelah sesi tidak lagi berjalan (kunci dibaca di sini)."""
    sesi = ambil_sesi(kon, siswa_id, sesi_id, sekarang)
    if sesi.status == BERJALAN:
        raise SesiBerjalan(sesi_id)
    baris = kon.execute(
        "SELECT s.jenis, s.kunci, s.pilihan_json, j.jawaban FROM lomba_soal s "
        "LEFT JOIN lomba_jawaban j ON j.sesi_id = s.sesi_id AND j.nomor = s.nomor "
        "WHERE s.sesi_id = ? ORDER BY s.nomor", (sesi_id,)).fetchall()
    nilai = sum(1 for r in baris if benar(r["jenis"], r["kunci"], json.loads(r["pilihan_json"]), r["jawaban"]))
    return HasilRingkas(nilai=nilai, jumlah_soal=len(baris),
                        waktu_terpakai_detik=sesi.selesai_epoch - sesi.mulai_epoch, status=sesi.status)

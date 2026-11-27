"""Dasar jadwal private (orang tua mengajukan slot, admin menyetujui): berkas DB terpisah, skema, galat, dan aturan murni.

DB ini sengaja terpisah dari admin-control.db (pola guru_status_jurnal): berkas dibuat lazy 0600 saat tulis pertama,
baca tidak pernah membuat berkas (berkas belum ada = kosong), PRAGMA user_version = 1, tanpa WAL. Aturan
`alasan_basi` murni (tanpa DB) dipakai ulang oleh baca dan tulis supaya penentu basi hanya satu. Tabel tambahan
(`DDL_TAMBAHAN`, pola 2 hari) bersifat aditif: dipasang tiap tulis, tidak menaikkan user_version, dan dibaca lewat
`ada_tabel` supaya berkas v1 lama tetap sah.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional

import jadwal_dasar as jd
import kelas_dasar as kd
import paket_belajar_katalog as katalog
import schema_jadwal
from jadwal_private_bentuk import VERSI_SKEMA

ENV_BERKAS_DB = "JADWAL_PRIVATE_DB"
BERKAS_BAWAAN = "/data/jadwal-private.db"
PAKET = schema_jadwal.KODE_PAKET_PRIVATE
MENIT_SESI = katalog.ambil(PAKET).menit
JAM_PESAN_MINIMAL = 24
TIMEOUT_DETIK = 5.0
STATUS_DIAJUKAN = "diajukan"
STATUS_DISETUJUI = "disetujui"
STATUS_DITOLAK = "ditolak"
STATUS_DIBATALKAN = "dibatalkan"
PELAKU_ORANG_TUA = "orang_tua"
PELAKU_SISTEM = "sistem"
_PESAN_SKEMA = "Skema jadwal private tidak dikenali."
_DDL = (
    "CREATE TABLE private_slot (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    guru_id TEXT NOT NULL,\n"
    "    mulai TEXT NOT NULL,\n"
    "    menit INTEGER NOT NULL,\n"
    "    dibuat TEXT NOT NULL,\n"
    "    dibuat_oleh TEXT NOT NULL,\n"
    "    dibatalkan INTEGER NOT NULL DEFAULT 0 CHECK(dibatalkan IN (0,1)),\n"
    "    UNIQUE(guru_id, mulai)\n"
    ")",
    "CREATE TRIGGER private_slot_tolak_hapus BEFORE DELETE ON private_slot\n"
    "BEGIN SELECT RAISE(ABORT, 'slot private tidak boleh dihapus'); END",
    "CREATE TRIGGER private_slot_tolak_ubah BEFORE UPDATE ON private_slot\n"
    "WHEN NOT (OLD.dibatalkan = 0 AND NEW.dibatalkan = 1 AND NEW.id IS OLD.id AND NEW.guru_id IS OLD.guru_id\n"
    "          AND NEW.mulai IS OLD.mulai AND NEW.menit IS OLD.menit AND NEW.dibuat IS OLD.dibuat\n"
    "          AND NEW.dibuat_oleh IS OLD.dibuat_oleh)\n"
    "BEGIN SELECT RAISE(ABORT, 'slot private hanya boleh dibatalkan'); END",
    "CREATE TABLE private_pengajuan (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    order_id TEXT NOT NULL,\n"
    "    slot_id INTEGER NOT NULL REFERENCES private_slot(id),\n"
    "    status TEXT NOT NULL CHECK(status IN ('diajukan','disetujui','ditolak','dibatalkan')),\n"
    "    dibuat TEXT NOT NULL,\n"
    "    diputuskan TEXT,\n"
    "    diputuskan_oleh TEXT\n"
    ")",
    "CREATE UNIQUE INDEX private_pengajuan_aktif ON private_pengajuan(order_id) WHERE status = 'diajukan'",
    "CREATE INDEX private_pengajuan_order ON private_pengajuan(order_id, id)",
    "CREATE TRIGGER private_pengajuan_transisi BEFORE UPDATE ON private_pengajuan\n"
    "WHEN NOT (OLD.status = 'diajukan' AND NEW.status IN ('disetujui','ditolak','dibatalkan')\n"
    "          AND NEW.id IS OLD.id AND NEW.order_id IS OLD.order_id AND NEW.slot_id IS OLD.slot_id\n"
    "          AND NEW.dibuat IS OLD.dibuat)\n"
    "BEGIN SELECT RAISE(ABORT, 'status pengajuan hanya boleh berubah dari diajukan'); END",
)
ALASAN_LEWAT = "waktu mulai sudah lewat"
ALASAN_TERHALANG = "anak sudah punya jadwal di paket lain"
ALASAN_TERLALU_DEKAT = "waktu mulai kurang dari 24 jam lagi"
# Pola hibrida (2 hari + 1 jam, disetujui tim): hari 0=Senin..5=Sabtu (Minggu tidak dibuka); jam WIB dari daftar
# mockup Daftar Kelas (27 Nov 2026, layar 3A).
HARI_BOLEH = frozenset(range(0, 6))
JAM_BOLEH = ("15:00", "16:00", "17:00", "19:00")
_HARI_SQL = "BETWEEN %d AND %d" % (min(HARI_BOLEH), max(HARI_BOLEH))
_JAM_SQL = ", ".join("'%s'" % jam for jam in JAM_BOLEH)
_DDL_POLA = (
    "CREATE TABLE IF NOT EXISTS private_pola_pengajuan (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    order_id TEXT NOT NULL,\n"
    "    hari_a INTEGER NOT NULL CHECK(hari_a %s),\n"
    "    hari_b INTEGER NOT NULL CHECK(hari_b %s AND hari_b > hari_a),\n"
    "    jam TEXT NOT NULL CHECK(jam IN (%s)),\n"
    "    status TEXT NOT NULL CHECK(status IN ('diajukan','disetujui','ditolak','dibatalkan')),\n"
    "    dibuat TEXT NOT NULL,\n"
    "    diubah TEXT NOT NULL,\n"
    "    diputuskan_oleh TEXT\n"
    ")" % (_HARI_SQL, _HARI_SQL, _JAM_SQL),
    "CREATE UNIQUE INDEX IF NOT EXISTS private_pola_pengajuan_aktif ON private_pola_pengajuan(order_id)\n"
    "WHERE status = 'diajukan'",
    "CREATE INDEX IF NOT EXISTS private_pola_pengajuan_order ON private_pola_pengajuan(order_id, id)",
    "CREATE TRIGGER IF NOT EXISTS private_pola_pengajuan_transisi BEFORE UPDATE ON private_pola_pengajuan\n"
    "WHEN NOT (OLD.status = 'diajukan' AND NEW.status IN ('disetujui','ditolak','dibatalkan')\n"
    "          AND NEW.id IS OLD.id AND NEW.order_id IS OLD.order_id AND NEW.hari_a IS OLD.hari_a\n"
    "          AND NEW.hari_b IS OLD.hari_b AND NEW.jam IS OLD.jam AND NEW.dibuat IS OLD.dibuat)\n"
    "BEGIN SELECT RAISE(ABORT, 'status pola hanya boleh berubah dari diajukan'); END",
)
TUNGGU_STATUS_MENUNGGU = "menunggu"
TUNGGU_STATUS_DIBATALKAN = "dibatalkan"
TUNGGU_STATUS_DIHAPUS_ADMIN = "dihapus_admin"
# Daftar tunggu Mini (keputusan Pemilik K2): satu entri 'menunggu' per order; penempatan TIDAK disimpan di sini
# (dibaca dari admin-control saat tampil). Kelompok sengaja TEXT tanpa FK lintas DB.
_DDL_TUNGGU = (
    "CREATE TABLE IF NOT EXISTS tunggu_mini (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    order_id TEXT NOT NULL,\n"
    "    kelompok_id TEXT NOT NULL CHECK(length(kelompok_id)=36 AND substr(kelompok_id,1,4)='klp_'),\n"
    "    status TEXT NOT NULL CHECK(status IN ('menunggu','dibatalkan','dihapus_admin')),\n"
    "    dibuat TEXT NOT NULL,\n"
    "    diubah TEXT NOT NULL,\n"
    "    diputuskan_oleh TEXT\n"
    ")",
    "CREATE UNIQUE INDEX IF NOT EXISTS tunggu_mini_aktif ON tunggu_mini(order_id)\n"
    "WHERE status = 'menunggu'",
    "CREATE INDEX IF NOT EXISTS tunggu_mini_kelompok ON tunggu_mini(kelompok_id, status, dibuat, id)",
    "CREATE TRIGGER IF NOT EXISTS tunggu_mini_transisi BEFORE UPDATE ON tunggu_mini\n"
    "WHEN NOT (OLD.status = 'menunggu' AND NEW.status IN ('dibatalkan','dihapus_admin')\n"
    "          AND NEW.id IS OLD.id AND NEW.order_id IS OLD.order_id AND NEW.kelompok_id IS OLD.kelompok_id\n"
    "          AND NEW.dibuat IS OLD.dibuat)\n"
    "BEGIN SELECT RAISE(ABORT, 'status daftar tunggu hanya boleh berubah dari menunggu'); END",
)
# Daftar DDL tambahan: tiap fitur menambah grup baru di sini. Semua statement IF NOT EXISTS (aditif, idempoten) dan
# VERSI_SKEMA TIDAK dinaikkan: image lama menolak setiap versi selain 0/1 (503 / kartu hilang), sedangkan tabel
# ekstra tidak terbaca olehnya. Berkas tanpa tabel baru tetap terbaca lewat `ada_tabel`.
# APPEND-ONLY: grup yang sudah dirilis JANGAN diedit. IF NOT EXISTS berarti perubahan pada grup lama tidak pernah
# sampai ke berkas yang sudah ada; fitur baru menambah grup sendiri di akhir tuple ini.
DDL_TAMBAHAN = (_DDL_POLA, _DDL_TUNGGU)


class GalatJadwalPrivate(Exception):
    """Berkas jadwal private rusak, skemanya tak dikenali, atau tidak bisa dibaca / ditulis."""


@dataclass(frozen=True)
class BarisSlot:
    id: int
    guru_id: str
    mulai: str
    menit: int
    dibatalkan: bool

    @classmethod
    def dari(cls, baris) -> "BarisSlot":
        return cls(int(baris["id"]), baris["guru_id"], baris["mulai"], int(baris["menit"]),
                   bool(baris["dibatalkan"]))


@dataclass(frozen=True)
class FaktaOrder:
    """Keadaan order Private untuk aturan basi: aktif (lunas, paket private), batas akses, sudah berjadwal,
    dan terhalang penempatan lama anak yang sama (order lain belum berakhir aksesnya)."""

    aktif: bool
    batas: Optional[str]
    berjadwal: bool
    terhalang: bool


def path_db(path) -> Path:
    """Tujuan DB: parameter, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_BERKAS_DB, BERKAS_BAWAAN))


def periksa_id(nilai, nama: str) -> int:
    if type(nilai) is not int or nilai < 1:
        raise jd.JadwalTidakSah("%s tidak sah" % nama)
    return nilai


def periksa_himpunan_guru(guru_sah) -> FrozenSet[str]:
    if type(guru_sah) not in (set, frozenset):
        raise jd.JadwalTidakSah("daftar guru aktif tidak sah")
    return frozenset(guru_sah)


def periksa_guru_aktif(guru_id, guru_sah) -> str:
    guru = jd.periksa_guru_id(guru_id)
    if guru not in periksa_himpunan_guru(guru_sah):
        raise jd.JadwalTidakSah("guru tidak aktif")
    return guru


def batas_pesan(kini: str) -> str:
    """Waktu paling awal slot boleh diajukan: sekarang + JAM_PESAN_MINIMAL jam (baku UTC)."""
    return kd.tambah_jam(kini, JAM_PESAN_MINIMAL)


def alasan_basi(fakta: FaktaOrder, slot: BarisSlot, kini: str, guru_sah, terisi) -> Optional[str]:
    """Alasan pengajuan tidak bisa lagi dijalankan, atau None bila masih hidup. Urutan cek tetap (deterministik)."""
    if not fakta.aktif:
        return "paket tidak aktif"
    if fakta.batas is None or kini >= fakta.batas:
        return "masa akses paket sudah berakhir"
    if fakta.berjadwal:
        return "paket sudah punya jadwal"
    if fakta.terhalang:
        return ALASAN_TERHALANG
    if slot.dibatalkan:
        return "slot sudah dibatalkan"
    if slot.mulai < kini:
        return ALASAN_LEWAT
    if slot.guru_id not in guru_sah:
        return "guru tidak aktif"
    if jd.delapan_pertemuan(slot.mulai)[-1] > fakta.batas:
        return "pertemuan terakhir melewati masa akses"
    if (slot.guru_id, slot.mulai) in terisi:
        return "slot sudah terisi"
    return None


def ambil_slot(kon, slot_id: int) -> BarisSlot:
    baris = kon.execute("SELECT id,guru_id,mulai,menit,dibatalkan FROM private_slot WHERE id=?",
                        (slot_id,)).fetchone()
    if baris is None:
        raise jd.JadwalTidakDitemukan()
    return BarisSlot.dari(baris)


def siapkan_berkas(tujuan: Path) -> None:
    """Berkas baru dibuat 0600 sebelum SQLite membukanya; berkas yang sudah ada tidak diubah."""
    try:
        os.close(os.open(tujuan, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600))
    except FileExistsError:
        pass  # berkas sudah ada (atau dibuat proses lain): tidak diubah


def _hubung(tujuan: Path, ro: bool) -> sqlite3.Connection:
    """Koneksi autocommit (transaksi eksplisit di pemanggil), baris bernama, kunci asing aktif."""
    if ro:
        koneksi = sqlite3.connect(tujuan.resolve().as_uri() + "?mode=ro", uri=True,
                                  timeout=TIMEOUT_DETIK, isolation_level=None)
    else:
        koneksi = sqlite3.connect(str(tujuan), timeout=TIMEOUT_DETIK, isolation_level=None)
    koneksi.row_factory = sqlite3.Row
    koneksi.execute("PRAGMA foreign_keys = ON")
    return koneksi


def _periksa_versi(kon, buat: bool) -> None:
    """Versi 0 = berkas kosong: dibuatkan skema bila `buat`, selain itu belum ada apa-apa (tidak ditemukan)."""
    versi = kon.execute("PRAGMA user_version").fetchone()[0]
    if versi == VERSI_SKEMA:
        return
    if versi != 0:
        raise GalatJadwalPrivate(_PESAN_SKEMA)
    if not buat:
        raise jd.JadwalTidakDitemukan()
    for ddl in _DDL:
        kon.execute(ddl)
    kon.execute("PRAGMA user_version = %d" % VERSI_SKEMA)


def pasang_tambahan(kon) -> None:
    """Pasang `DDL_TAMBAHAN` (IF NOT EXISTS) di dalam transaksi tulis yang sudah berjalan. Dipanggil tiap tulis."""
    for kelompok in DDL_TAMBAHAN:
        for ddl in kelompok:
            kon.execute(ddl)


def ada_tabel(kon, nama: str) -> bool:
    """Tabel ada di berkas ini? Berkas v1 lama belum punya tabel tambahan sampai tulis pertama."""
    return kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nama,)).fetchone() is not None


@contextmanager
def dengan_tulis(path, *, buat: bool = False):
    """Satu transaksi `BEGIN IMMEDIATE` pada DB private. `buat` hanya untuk buat_slot, ajukan pola, dan masuk daftar
    tunggu Mini (setelah cek kepemilikan dan kelayakan); tulis lain tidak membuat berkas.

    Galat sqlite pada koneksi private dibungkus GalatJadwalPrivate; galat domain (JadwalKonflik, dll.) lolos utuh,
    termasuk dari penempatan admin-control yang ikut transaksi ini. Gagal = rollback.
    """
    tujuan = path_db(path)
    if not buat and not tujuan.exists():
        raise jd.JadwalTidakDitemukan()
    kon = _buka_tulis(tujuan, buat)
    try:
        kon.execute("BEGIN IMMEDIATE")
        _periksa_versi(kon, buat)
        pasang_tambahan(kon)
        yield kon
        kon.execute("COMMIT")
    except BaseException as galat:
        if kon.in_transaction:
            kon.rollback()
        if isinstance(galat, sqlite3.Error):
            raise GalatJadwalPrivate("Jadwal private tidak bisa ditulis.") from galat
        raise
    finally:
        kon.close()


def _buka_tulis(tujuan: Path, buat: bool) -> sqlite3.Connection:
    try:
        if buat:
            siapkan_berkas(tujuan)
        return _hubung(tujuan, ro=False)
    except (OSError, sqlite3.Error) as galat:
        raise GalatJadwalPrivate("Jadwal private tidak bisa ditulis.") from galat


def dengan_baca(path, fungsi, kosong):
    """Jalankan `fungsi(kon)` pada koneksi baca-saja. Berkas belum ada, atau belum berskema = `kosong`; tidak membuat berkas."""
    tujuan = path_db(path)
    if not tujuan.exists():
        return kosong
    try:
        with closing(_hubung(tujuan, ro=True)) as kon:
            versi = kon.execute("PRAGMA user_version").fetchone()[0]
            if versi == 0:
                return kosong
            if versi != VERSI_SKEMA:
                raise GalatJadwalPrivate(_PESAN_SKEMA)
            return fungsi(kon)
    except sqlite3.Error as galat:
        raise GalatJadwalPrivate("Jadwal private tidak bisa dibaca.") from galat

"""Penyimpanan tugas guru: DB SQLite terpisah (`guru-tugas.db`), append-only.

Hanya id sesi, id anak, id akun guru, topik tertutup, tenggat, dan waktu buat yang disimpan: tanpa nama, kontak,
atau teks bebas. catat() membuat berkas (privat 0600) dan skema pada tulis pertama. daftar_siswa() dan
daftar_guru() tidak pernah membuat berkas.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import auth
import guru_pertemuan_aturan as pertemuan
import guru_tugas_aturan as aturan
from guru_tugas_bentuk import NAMA_BERKAS, TABEL_SKEMA, VERSI_SKEMA

_log = logging.getLogger(__name__)

ENV_DB = "GURU_TUGAS_DB"
BERKAS_BAWAAN = "/data/" + NAMA_BERKAS
IZIN_BERKAS = 0o600
TIMEOUT_DETIK = 5.0
TIMEOUT_KUNCI_UJI_DETIK = 0.0
SESI_ID_MIN = 1
SISWA_ID_MIN = 1
PANJANG_TOPIK_MAKS = 64
PANJANG_AKUN_HEX = 32
PANJANG_GURU_AKUN = len("akun_") + PANJANG_AKUN_HEX
_PESAN_TOLAK_UBAH = "tugas guru hanya boleh ditambah"
_PESAN_TULIS = "Tugas guru tidak bisa ditulis."
_PESAN_BACA = "Tugas guru tidak bisa dibaca."
_PESAN_SKEMA = "Skema tugas guru tidak dikenali."

# Potongan SQL CHECK. Pola yang sama dengan guru_pertemuan_dasar (tidak di-import: modul ini mandiri).
_HEX = "NOT GLOB '*[^0-9a-f]*'"
_TANGGAL = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
_WAKTU = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
_CEK_GURU = (
    "length(guru_akun)={panjang_guru} AND substr(guru_akun,1,5)='akun_' AND substr(guru_akun,6) " + _HEX
)

_DDL_TUGAS = (
    "CREATE TABLE tugas_guru (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  sesi_id INTEGER NOT NULL UNIQUE CHECK(sesi_id>=1),\n"
    "  siswa_id INTEGER NOT NULL CHECK(siswa_id>=1),\n"
    "  guru_akun TEXT NOT NULL CHECK({guru}),\n"
    "  topik TEXT NOT NULL CHECK(length(topik) BETWEEN 1 AND {topik_maks}),\n"
    "  tenggat TEXT NULL CHECK(tenggat IS NULL OR tenggat GLOB {tanggal}),\n"
    "  dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})\n"
    ")"
).format(
    guru=_CEK_GURU.format(panjang_guru=PANJANG_GURU_AKUN),
    topik_maks=PANJANG_TOPIK_MAKS,
    tanggal=_TANGGAL,
    waktu=_WAKTU,
)

_DDL_INDEKS = (
    "CREATE INDEX idx_tugas_guru_siswa ON tugas_guru(siswa_id, id)",
    "CREATE INDEX idx_tugas_guru_guru ON tugas_guru(guru_akun, id)",
)


def _ddl_tolak(tabel: str, kata: str, aksi: str) -> str:
    return (
        f"CREATE TRIGGER {tabel}_tolak_{kata} BEFORE {aksi} ON {tabel} "
        f"BEGIN SELECT RAISE(ABORT, '{_PESAN_TOLAK_UBAH}'); END"
    )


_DDL_TRIGGER = tuple(
    _ddl_tolak(tabel, kata, aksi)
    for tabel in TABEL_SKEMA
    for kata, aksi in (("ubah", "UPDATE"), ("hapus", "DELETE"))
)
DDL_SKEMA = (_DDL_TUGAS,) + _DDL_INDEKS + _DDL_TRIGGER

_KOLOM_BACA = "id, sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat"
_NAMA_KOLOM_BACA = ("id", "sesi_id", "siswa_id", "guru_akun", "topik", "tenggat", "dibuat")
_SQL_PER_SISWA = "SELECT " + _KOLOM_BACA + " FROM tugas_guru WHERE siswa_id = ? ORDER BY id DESC"
_SQL_PER_GURU = "SELECT " + _KOLOM_BACA + " FROM tugas_guru WHERE guru_akun = ? ORDER BY id DESC"


class GalatTugas(Exception):
    """Tugas guru tidak bisa dibaca atau ditulis; pesan tanpa data privat dan tanpa path berkas."""


@dataclass(frozen=True)
class _Tugas:
    """Satu tugas yang sudah tervalidasi."""

    sesi_id: int
    siswa_id: int
    guru_akun: str
    topik: str
    tenggat: Optional[str]
    dibuat: str


# --- validasi ---------------------------------------------------------------------------

def _path_db(path) -> Path:
    """Tujuan DB: argumen, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_DB, BERKAS_BAWAAN))


def _periksa_id(nilai, minimum: int, pesan: str) -> None:
    """Bilangan bulat murni (bool ditolak) dan tidak di bawah batas."""
    if type(nilai) is not int or nilai < minimum:
        raise ValueError(pesan)


def _periksa_tugas(sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat) -> None:
    _periksa_id(sesi_id, SESI_ID_MIN, "ID sesi tidak sah.")
    _periksa_id(siswa_id, SISWA_ID_MIN, "ID siswa tidak sah.")
    if not auth.id_akun_sah(guru_akun):
        raise ValueError("ID akun guru tidak sah.")
    if not aturan.topik_tugas_sah(topik):
        raise ValueError("Topik tugas tidak sah.")
    if not aturan.tenggat_bentuk_sah(tenggat):
        raise ValueError("Tenggat tugas tidak sah.")
    if not pertemuan.waktu_sah(dibuat):
        raise ValueError("Waktu pembuatan tugas tidak sah.")


def _bentuk_tugas(sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat) -> _Tugas:
    _periksa_tugas(sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat)
    return _Tugas(sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat)


# --- skema dan berkas -------------------------------------------------------------------

def _versi(kon) -> int:
    return kon.execute("PRAGMA user_version").fetchone()[0]


def _pastikan_skema(kon) -> None:
    """Buat tabel, indeks, dan trigger bila DB masih versi 0; versi lain selain VERSI_SKEMA ditolak."""
    versi = _versi(kon)
    if versi == VERSI_SKEMA:
        return
    if versi != 0:
        raise GalatTugas(_PESAN_SKEMA)
    for ddl in DDL_SKEMA:
        kon.execute(ddl)
    kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _siapkan_berkas(tujuan: Path) -> bool:
    """Berkas baru dibuat 0600 sebelum SQLite membukanya. True bila dibuat di sini; yang sudah ada tidak diubah."""
    try:
        os.close(os.open(tujuan, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), IZIN_BERKAS))
    except FileExistsError:
        return False
    return True


def _bisa_dibuang(tujuan: Path) -> bool:
    """True bila berkas masih 0 byte dan tak ada penulis lain yang memegangnya. Tidak pernah membuat berkas.

    Probe `BEGIN EXCLUSIVE` tanpa menunggu. Ukuran dicek di bawah kunci itu. Galat apa pun dianggap "jangan buang",
    supaya galat tulis asli yang dilaporkan.
    """
    try:
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=rw", uri=True,
                                     timeout=TIMEOUT_KUNCI_UJI_DETIK)) as kon:
            kon.execute("BEGIN EXCLUSIVE")
            kosong = tujuan.stat().st_size == 0
            kon.execute("ROLLBACK")
    except (OSError, sqlite3.Error):
        _log.warning("berkas tugas kosong tidak diperiksa; dibiarkan")
        return False
    return kosong


def _hapus_bila_kosong(tujuan: Path, dibuat_di_sini: bool) -> None:
    """Bersihkan berkas 0 byte yang baru dibuat `catat` bila penulisan pertama gagal.

    Berkas 0 byte tidak punya header SQLite, sehingga backup operasional akan menolaknya. Berkas yang sudah ada
    sebelumnya atau sudah berisi tidak pernah disentuh, dan berkas yang dipegang penulis lain dibiarkan.
    """
    if not dibuat_di_sini or not _bisa_dibuang(tujuan):
        return
    try:
        tujuan.unlink()
    except OSError:
        _log.warning("berkas tugas kosong tidak bisa dibersihkan")


# --- tulis ------------------------------------------------------------------------------

def _sisipkan_tugas(kon, tugas: _Tugas) -> int:
    kursor = kon.execute(
        "INSERT INTO tugas_guru (sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat) VALUES (?, ?, ?, ?, ?, ?)",
        (tugas.sesi_id, tugas.siswa_id, tugas.guru_akun, tugas.topik, tugas.tenggat, tugas.dibuat),
    )
    return kursor.lastrowid


def catat(sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat, *, path=None) -> int:
    """Tambah satu tugas dan kembalikan id barunya. Semua argumen divalidasi sebelum berkas disentuh."""
    tugas = _bentuk_tugas(sesi_id, siswa_id, guru_akun, topik, tenggat, dibuat)
    tujuan = _path_db(path)
    dibuat_di_sini = False
    try:
        dibuat_di_sini = _siapkan_berkas(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=TIMEOUT_DETIK)) as kon, kon:
            kon.execute("BEGIN IMMEDIATE")
            _pastikan_skema(kon)
            return _sisipkan_tugas(kon, tugas)
    except (OSError, sqlite3.Error) as err:
        raise GalatTugas(_PESAN_TULIS) from err
    finally:
        _hapus_bila_kosong(tujuan, dibuat_di_sini)


# --- baca (tanpa membuat berkas) --------------------------------------------------------

def _ke_baris(baris) -> Dict[str, object]:
    return dict(zip(_NAMA_KOLOM_BACA, baris))


def _baca_berkas(tujuan: Path, baca: Callable[[object], List[Dict[str, object]]]) -> List[Dict[str, object]]:
    """Baca mode=ro dan query_only. Berkas tak ada atau versi 0 = daftar kosong; versi asing ditolak."""
    if not tujuan.exists():
        return []
    try:
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=TIMEOUT_DETIK)) as kon:
            kon.execute("PRAGMA query_only = ON")
            versi = _versi(kon)
            if versi == 0:
                return []
            if versi != VERSI_SKEMA:
                raise GalatTugas(_PESAN_SKEMA)
            return baca(kon)
    except sqlite3.Error as err:
        raise GalatTugas(_PESAN_BACA) from err


def _ambil(kon, sql: str, nilai) -> List[Dict[str, object]]:
    return [_ke_baris(baris) for baris in kon.execute(sql, (nilai,)).fetchall()]


def daftar_siswa(siswa_id: int, *, path=None) -> List[Dict[str, object]]:
    """Tugas milik seorang anak, terbaru dulu. Tidak membuat berkas."""
    _periksa_id(siswa_id, SISWA_ID_MIN, "ID siswa tidak sah.")
    return _baca_berkas(_path_db(path), lambda kon: _ambil(kon, _SQL_PER_SISWA, siswa_id))


def daftar_guru(guru_akun: str, *, path=None) -> List[Dict[str, object]]:
    """Tugas yang dibuat seorang guru, terbaru dulu. Tidak membuat berkas."""
    if not auth.id_akun_sah(guru_akun):
        raise ValueError("ID akun guru tidak sah.")
    return _baca_berkas(_path_db(path), lambda kon: _ambil(kon, _SQL_PER_GURU, guru_akun))

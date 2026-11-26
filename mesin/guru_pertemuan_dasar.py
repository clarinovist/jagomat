"""Penyimpanan catatan kehadiran dan jurnal pertemuan guru: DB SQLite terpisah, append-only.

Hanya id (kunci pertemuan, order_id, id akun) serta topik dan status tertutup yang disimpan: tanpa nama,
kontak, atau teks bebas. Setiap baris menyimpan `mulai` pertemuan saat dicatat, sehingga pertemuan yang
digeser atau dibatalkan tidak mewarisi catatan lama. catat() membuat berkas (privat 0600) dan skema pada
tulis pertama; terkini() dan punya_jurnal() tidak pernah membuat berkas.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import auth
import guru_pertemuan_aturan as aturan
from guru_pertemuan_bentuk import NAMA_BERKAS, TABEL_SKEMA, VERSI_SKEMA  # noqa: F401  (diekspor ulang untuk pemakai lama)

_log = logging.getLogger(__name__)

ENV_DB = "GURU_PERTEMUAN_DB"
BERKAS_BAWAAN = "/data/" + NAMA_BERKAS
PERAN_SAH = ("guru", "admin")
PERTEMUAN_ID_MIN = 1
PANJANG_POTONGAN_PASANGAN = 400
IZIN_BERKAS = 0o600
TIMEOUT_DETIK = 5.0
TIMEOUT_KUNCI_UJI_DETIK = 0.0
_PESAN_TOLAK_UBAH = "catatan pertemuan hanya boleh ditambah"
_PESAN_TULIS = "Catatan pertemuan tidak bisa ditulis."
_PESAN_BACA = "Catatan pertemuan tidak bisa dibaca."
_PESAN_SKEMA = "Skema catatan pertemuan tidak dikenali."

# Potongan SQL CHECK. Pola ini sama dengan schema_pesanan._HEX / _WAKTU (tidak di-import: modul ini mandiri).
_HEX = "NOT GLOB '*[^0-9a-f]*'"
_WAKTU = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
_CEK_KUNCI = (
    "length(kunci)=38 AND substr(kunci,1,4) IN ('klp_','kor_') AND substr(kunci,5,32) " + _HEX
    + " AND substr(kunci,37,1)=':' AND substr(kunci,38) GLOB '[1-8]'"
)
_CEK_OLEH = "length(oleh)=37 AND substr(oleh,1,5)='akun_' AND substr(oleh,6) " + _HEX

_DDL_JURNAL = (
    "CREATE TABLE pertemuan_jurnal (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  kunci TEXT NOT NULL CHECK({kunci}),\n"
    "  pertemuan_id INTEGER NOT NULL CHECK(pertemuan_id>=1),\n"
    "  mulai TEXT NOT NULL CHECK(mulai GLOB {waktu}),\n"
    "  topik TEXT NOT NULL CHECK(length(topik) BETWEEN 1 AND 64),\n"
    "  oleh TEXT NOT NULL CHECK({oleh}),\n"
    "  peran TEXT NOT NULL CHECK(peran IN ('guru','admin')),\n"
    "  pada TEXT NOT NULL CHECK(pada GLOB {waktu})\n"
    ")"
).format(kunci=_CEK_KUNCI, waktu=_WAKTU, oleh=_CEK_OLEH)

_DDL_HADIR = (
    "CREATE TABLE pertemuan_hadir (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  kunci TEXT NOT NULL CHECK({kunci}),\n"
    "  pertemuan_id INTEGER NOT NULL CHECK(pertemuan_id>=1),\n"
    "  mulai TEXT NOT NULL CHECK(mulai GLOB {waktu}),\n"
    "  order_id TEXT NOT NULL CHECK(length(order_id)=36 AND substr(order_id,1,4)='kor_' "
    "AND substr(order_id,5) {hex}),\n"
    "  status TEXT NOT NULL CHECK(status IN ('hadir','izin','tidak_hadir')),\n"
    "  oleh TEXT NOT NULL CHECK({oleh}),\n"
    "  peran TEXT NOT NULL CHECK(peran IN ('guru','admin')),\n"
    "  pada TEXT NOT NULL CHECK(pada GLOB {waktu})\n"
    ")"
).format(kunci=_CEK_KUNCI, waktu=_WAKTU, oleh=_CEK_OLEH, hex=_HEX)

_DDL_INDEKS = (
    "CREATE INDEX idx_pertemuan_jurnal_kunci ON pertemuan_jurnal(kunci, mulai, id)",
    "CREATE INDEX idx_pertemuan_hadir_kunci ON pertemuan_hadir(kunci, mulai, order_id, id)",
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
DDL_SKEMA = (_DDL_JURNAL, _DDL_HADIR) + _DDL_INDEKS + _DDL_TRIGGER


class GalatCatatan(RuntimeError):
    """Catatan pertemuan tidak bisa dibaca atau ditulis; pesan tanpa data privat."""


@dataclass(frozen=True)
class _Catatan:
    """Satu catatan yang sudah tervalidasi. `hadir` berisi pasangan (order_id, status) yang sudah terurut."""

    kunci: str
    pertemuan_id: int
    mulai: str
    topik: str
    hadir: Tuple[Tuple[str, str], ...]
    oleh: str
    peran: str
    pada: str


# --- validasi ---------------------------------------------------------------------------

def _path_db(path) -> Path:
    """Tujuan DB: argumen, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_DB, BERKAS_BAWAAN))


def _periksa_kunci_waktu(kunci, mulai) -> None:
    if not aturan.kunci_sah(kunci):
        raise ValueError("Kunci pertemuan tidak sah.")
    if not aturan.waktu_sah(mulai):
        raise ValueError("Waktu mulai pertemuan tidak sah.")


def _periksa_metadata(pertemuan_id, topik, oleh, peran, pada) -> None:
    if type(pertemuan_id) is not int or pertemuan_id < PERTEMUAN_ID_MIN:
        raise ValueError("ID pertemuan tidak sah.")
    if not aturan.topik_sah(topik):
        raise ValueError("Topik jurnal tidak sah.")
    if not auth.id_akun_sah(oleh):
        raise ValueError("ID pencatat tidak sah.")
    if type(peran) is not str or peran not in PERAN_SAH:
        raise ValueError("Peran pencatat tidak sah.")
    if not aturan.waktu_sah(pada):
        raise ValueError("Waktu pencatatan tidak sah.")


def _salin_hadir(hadir) -> Tuple[Tuple[str, str], ...]:
    """Salinan kehadiran yang sudah divalidasi dan terurut; mengembalikan tuple baru, argumen tidak diubah."""
    if not isinstance(hadir, Mapping):
        raise ValueError("Kehadiran harus pemetaan ID pesanan ke status.")
    salinan = dict(hadir)
    for order_id, status in salinan.items():
        if not aturan.order_id_sah(order_id):
            raise ValueError("ID pesanan kehadiran tidak sah.")
        if not aturan.status_sah(status):
            raise ValueError("Status kehadiran tidak sah.")
    return tuple(sorted(salinan.items()))


def _bentuk_catatan(kunci, pertemuan_id, mulai, topik, hadir, oleh, peran, pada) -> _Catatan:
    _periksa_kunci_waktu(kunci, mulai)
    _periksa_metadata(pertemuan_id, topik, oleh, peran, pada)
    return _Catatan(kunci, pertemuan_id, mulai, topik, _salin_hadir(hadir), oleh, peran, pada)


# --- skema dan berkas -------------------------------------------------------------------

def _versi(kon) -> int:
    return kon.execute("PRAGMA user_version").fetchone()[0]


def _pastikan_skema(kon) -> None:
    """Buat tabel, indeks, dan trigger bila DB masih versi 0; versi lain selain VERSI_SKEMA ditolak."""
    versi = _versi(kon)
    if versi == VERSI_SKEMA:
        return
    if versi != 0:
        raise GalatCatatan(_PESAN_SKEMA)
    for ddl in DDL_SKEMA:
        kon.execute(ddl)
    kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _siapkan_berkas(tujuan: Path) -> bool:
    """Berkas baru dibuat 0600 sebelum SQLite membukanya. True bila berkas dibuat di sini; yang sudah ada tidak diubah."""
    try:
        os.close(os.open(tujuan, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), IZIN_BERKAS))
    except FileExistsError:
        return False
    return True


def _bisa_dibuang(tujuan: Path) -> bool:
    """True bila berkas masih 0 byte dan tak ada penulis lain yang memegangnya. Tidak pernah membuat berkas.

    Probe `BEGIN EXCLUSIVE` tanpa menunggu (mode=rw, timeout nol). Ukuran dicek DI BAWAH kunci itu, lalu rollback
    sebelum berkas dibuang. Galat apa pun dianggap "jangan buang", supaya galat tulis asli yang dilaporkan.
    """
    try:
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=rw", uri=True,
                                     timeout=TIMEOUT_KUNCI_UJI_DETIK)) as kon:
            kon.execute("BEGIN EXCLUSIVE")
            kosong = tujuan.stat().st_size == 0
            kon.execute("ROLLBACK")
    except (OSError, sqlite3.Error):
        _log.warning("berkas catatan kosong tidak diperiksa; dibiarkan")
        return False
    return kosong


def _hapus_bila_kosong(tujuan: Path, dibuat_di_sini: bool) -> None:
    """Bersihkan berkas 0 byte yang baru dibuat `catat` bila penulisan pertama gagal.

    Berkas 0 byte tidak punya header SQLite: `sqlite_copy` backup operasional menolaknya sehingga seluruh backup
    gagal. Berkas yang sudah ada sebelumnya atau sudah berisi tidak pernah disentuh. Berkas yang sedang dipegang
    penulis lain (transaksi terbuka) dibiarkan: menghapusnya membuang data penulis itu.
    """
    if not dibuat_di_sini or not _bisa_dibuang(tujuan):
        return
    try:
        tujuan.unlink()
    except OSError:
        _log.warning("berkas catatan kosong tidak bisa dibersihkan")


# --- keadaan terkini --------------------------------------------------------------------

def _keadaan_kosong() -> Dict[str, object]:
    return {"topik": None, "hadir": {}}


def _baca_keadaan(kon, kunci: str, mulai: str) -> Dict[str, object]:
    """Topik terbaru dan status per order_id untuk (kunci, mulai). Baris id terbesar yang menang."""
    baris_topik = kon.execute(
        "SELECT topik FROM pertemuan_jurnal WHERE kunci = ? AND mulai = ? ORDER BY id DESC LIMIT 1",
        (kunci, mulai),
    ).fetchone()
    baris_hadir = kon.execute(
        "SELECT order_id, status FROM pertemuan_hadir WHERE kunci = ? AND mulai = ? ORDER BY id ASC",
        (kunci, mulai),
    ).fetchall()
    return {
        "topik": baris_topik[0] if baris_topik else None,
        "hadir": {order_id: status for order_id, status in baris_hadir},
    }


# --- tulis ------------------------------------------------------------------------------

def _sisipkan_jurnal(kon, catatan: _Catatan) -> None:
    kon.execute(
        "INSERT INTO pertemuan_jurnal (kunci, pertemuan_id, mulai, topik, oleh, peran, pada) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (catatan.kunci, catatan.pertemuan_id, catatan.mulai, catatan.topik,
         catatan.oleh, catatan.peran, catatan.pada),
    )


def _sisipkan_hadir(kon, catatan: _Catatan, order_id: str, status: str) -> None:
    kon.execute(
        "INSERT INTO pertemuan_hadir (kunci, pertemuan_id, mulai, order_id, status, oleh, peran, pada) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (catatan.kunci, catatan.pertemuan_id, catatan.mulai, order_id, status,
         catatan.oleh, catatan.peran, catatan.pada),
    )


def _tulis_selisih(kon, catatan: _Catatan) -> int:
    """Tulis hanya baris yang berbeda dari keadaan terkini: jurnal bila topik beda, hadir bila status beda."""
    keadaan = _baca_keadaan(kon, catatan.kunci, catatan.mulai)
    jurnal_baru = 0
    if catatan.topik != keadaan["topik"]:
        _sisipkan_jurnal(kon, catatan)
        jurnal_baru = 1
    hadir_baru = [
        (order_id, status)
        for order_id, status in catatan.hadir
        if keadaan["hadir"].get(order_id) != status
    ]
    for order_id, status in hadir_baru:
        _sisipkan_hadir(kon, catatan, order_id, status)
    return jurnal_baru + len(hadir_baru)


def catat(*, kunci, pertemuan_id, mulai, topik, hadir: Mapping[str, str], oleh, peran, pada, path=None) -> int:
    """Tambah baris yang berbeda dari keadaan terkini dalam satu transaksi. Kirim ulang identik = 0 baris."""
    catatan = _bentuk_catatan(kunci, pertemuan_id, mulai, topik, hadir, oleh, peran, pada)
    tujuan = _path_db(path)
    dibuat_di_sini = False
    try:
        dibuat_di_sini = _siapkan_berkas(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=TIMEOUT_DETIK)) as kon, kon:
            kon.execute("BEGIN IMMEDIATE")
            _pastikan_skema(kon)
            return _tulis_selisih(kon, catatan)
    except (OSError, sqlite3.Error) as err:
        raise GalatCatatan(_PESAN_TULIS) from err
    finally:
        # Sukses: berkas berisi skema, tidak disentuh. Gagal pada pembuatan pertama: transaksi dibatalkan, berkas 0 byte dibuang.
        _hapus_bila_kosong(tujuan, dibuat_di_sini)


# --- baca (tanpa membuat berkas) --------------------------------------------------------

def _baca_berkas(tujuan: Path, kosong, baca):
    """Baca mode=ro dan query_only. Berkas tak ada atau versi 0 = `kosong`; versi asing ditolak."""
    if not tujuan.exists():
        return kosong
    try:
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=ro", uri=True, timeout=TIMEOUT_DETIK)) as kon:
            kon.execute("PRAGMA query_only = ON")
            versi = _versi(kon)
            if versi == 0:
                return kosong
            if versi != VERSI_SKEMA:
                raise GalatCatatan(_PESAN_SKEMA)
            return baca(kon)
    except sqlite3.Error as err:
        raise GalatCatatan(_PESAN_BACA) from err


def terkini(kunci: str, mulai: str, *, path=None) -> Dict[str, object]:
    """Keadaan terkini untuk (kunci, mulai): {"topik": ..., "hadir": {order_id: status}}. Tidak membuat berkas."""
    _periksa_kunci_waktu(kunci, mulai)
    return _baca_berkas(_path_db(path), _keadaan_kosong(), lambda kon: _baca_keadaan(kon, kunci, mulai))


def _salin_pasangan(pasangan: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    hasil = []
    for item in pasangan:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError("Pasangan pertemuan harus (kunci, mulai).")
        kunci, mulai = item
        _periksa_kunci_waktu(kunci, mulai)
        hasil.append((kunci, mulai))
    return hasil


def _potong(daftar: List, ukuran: int) -> List[List]:
    return [daftar[i:i + ukuran] for i in range(0, len(daftar), ukuran)]


def _cari_bagian(kon, bagian: List[Tuple[str, str]]) -> Set[Tuple[str, str]]:
    """Pasangan (kunci, mulai) dalam `bagian` yang punya >=1 baris jurnal. Join pada kedua kolom, bukan IN silang."""
    nilai = ", ".join(["(?, ?)"] * len(bagian))
    parameter = [isi for pasangan in bagian for isi in pasangan]
    sql = (
        f"WITH p(k, m) AS (VALUES {nilai}) "
        "SELECT DISTINCT j.kunci, j.mulai FROM pertemuan_jurnal AS j "
        "JOIN p ON j.kunci = p.k AND j.mulai = p.m"
    )
    return {(kunci, mulai) for kunci, mulai in kon.execute(sql, parameter).fetchall()}


def _pasangan_berjurnal(kon, daftar: List[Tuple[str, str]]) -> Set[Tuple[str, str]]:
    bagian_hasil = [_cari_bagian(kon, bagian) for bagian in _potong(daftar, PANJANG_POTONGAN_PASANGAN)]
    return set().union(*bagian_hasil)


def punya_jurnal(pasangan: Iterable[Tuple[str, str]], *, path=None) -> Set[Tuple[str, str]]:
    """Himpunan (kunci, mulai) yang punya minimal satu baris jurnal. Tidak membuat berkas."""
    daftar = _salin_pasangan(pasangan)
    if not daftar:
        return set()
    return _baca_berkas(_path_db(path), set(), lambda kon: _pasangan_berjurnal(kon, daftar))

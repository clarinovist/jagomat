"""Penyimpanan tautan kode anak guru: DB SQLite terpisah, append-only, sebagai ledger persetujuan orang tua.

Kode anak tidak pernah disimpan, hanya hash-nya. Status permintaan diturunkan dari peristiwa (putusan, kode dicabut,
waktu), bukan dari kolom yang bisa diubah. Semua tulis berjalan dalam satu transaksi BEGIN IMMEDIATE, dan semua
pemeriksaan aturan dilakukan di koneksi tulis itu sendiri. Berkas dibuat privat 0600 pada tulis pertama; baca
(mode=ro) tidak pernah membuat berkas.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import auth
import guru_tautan_aturan as aturan
from guru_tautan_bentuk import NAMA_BERKAS, TABEL_SKEMA, VERSI_SKEMA  # noqa: F401  (diekspor ulang untuk pemakai lain)

_log = logging.getLogger(__name__)

ENV_DB = "GURU_TAUTAN_DB"
BERKAS_BAWAAN = "/data/" + NAMA_BERKAS
ID_MIN = 1
IZIN_BERKAS = 0o600
TIMEOUT_DETIK = 5.0
TIMEOUT_KUNCI_UJI_DETIK = 0.0
ALASAN_MENUNGGU_ADA = "menunggu_ada"
ALASAN_JEDA_TOLAK = "jeda_tolak"
ALASAN_KODE_PENUH = "kode_penuh"
_PESAN_TULIS = "Tautan kode anak tidak bisa ditulis."
_PESAN_BACA = "Tautan kode anak tidak bisa dibaca."
_PESAN_SKEMA = "Skema tautan kode anak tidak dikenali."
_PESAN_TOLAK_UBAH = "catatan tautan hanya boleh ditambah"
_PESAN_SUDAH_ADA = "Anak ini sudah punya kode aktif."
_PESAN_BASI = "Kode sudah berubah. Muat ulang halaman lalu coba lagi."
_PESAN_TAK_AKTIF = "Kode tidak bisa dipakai."
_PESAN_TAK_BISA = "Permintaan ini tidak bisa diputuskan lagi."
_POLA_HASH = re.compile(r"[0-9a-f]{64}")
_POLA_KELOMPOK = re.compile(r"klp_[0-9a-f]{32}")


class GalatTautan(RuntimeError):
    """Tautan kode anak tidak bisa dibaca atau ditulis; pesan tanpa data privat."""


class KodeSudahAda(GalatTautan):
    """Anak sudah punya kode aktif; buat baru hanya setelah kode lama dicabut."""


class KodeBasi(GalatTautan):
    """kode_id yang dikirim bukan kode aktif anak itu (sudah diganti, dicabut, atau milik anak lain)."""


class KodeTakAktif(GalatTautan):
    """Kode yang dipakai guru tidak aktif."""


class PutusanTakBisa(GalatTautan):
    """Permintaan tidak lagi menunggu: sudah diputuskan, kedaluwarsa, atau batal."""


class PermintaanDitolakAturan(GalatTautan):
    """Pengajuan ditolak aturan; `alasan` berisi salah satu ALASAN_* (konstanta, tanpa data privat)."""

    def __init__(self, alasan: str) -> None:
        super().__init__("Permintaan ditolak aturan: " + alasan)
        self.alasan = alasan


# --- validasi (sebelum berkas disentuh) -------------------------------------------------

def _path_db(path) -> Path:
    """Tujuan DB: argumen, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_DB, BERKAS_BAWAAN))


def _periksa_akun(nilai: Any, nama: str) -> None:
    if not auth.id_akun_sah(nilai):
        raise ValueError(nama + " tidak sah.")


def _periksa_id(nilai: Any, nama: str) -> None:
    if type(nilai) is not int or nilai < ID_MIN:
        raise ValueError(nama + " tidak sah.")


def _periksa_anak(akun_id: Any, siswa_id: Any) -> None:
    _periksa_akun(akun_id, "ID akun anak")
    _periksa_id(siswa_id, "ID siswa")


def _periksa_waktu(pada: Any) -> None:
    if not aturan.waktu_sah(pada):
        raise ValueError("Waktu tidak sah.")


def _periksa_pencatat(oleh: Any, peran: Any, pada: Any) -> None:
    _periksa_akun(oleh, "ID pencatat")
    if type(peran) is not str or peran not in aturan.PERAN_SAH:
        raise ValueError("Peran pencatat tidak sah.")
    _periksa_waktu(pada)


def _hash_sah(kode_hash: Any) -> bool:
    return type(kode_hash) is str and _POLA_HASH.fullmatch(kode_hash) is not None


def _periksa_hash(kode_hash: Any) -> None:
    if not _hash_sah(kode_hash):
        raise ValueError("Hash kode tidak sah.")


def _periksa_kelompok(kelompok_id: Any) -> None:
    if type(kelompok_id) is not str or _POLA_KELOMPOK.fullmatch(kelompok_id) is None:
        raise ValueError("ID kelompok tidak sah.")


def _periksa_hasil(hasil: Any) -> None:
    if type(hasil) is not str or hasil not in aturan.HASIL_SAH:
        raise ValueError("Hasil putusan tidak sah.")


# --- skema ------------------------------------------------------------------------------

_HEX = "NOT GLOB '*[^0-9a-f]*'"
_WAKTU = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
_PERAN_SQL = "'orang_tua','admin'"
_HASIL_SQL = "'setuju','tolak'"
_CEK_HASH = "length(kode_hash)=64 AND kode_hash " + _HEX
_CEK_KELOMPOK = "length(kelompok_id)=36 AND substr(kelompok_id,1,4)='klp_' AND substr(kelompok_id,5) " + _HEX


def _cek_akun(kolom: str) -> str:
    return ("length(" + kolom + ")=37 AND substr(" + kolom + ",1,5)='akun_' AND substr("
            + kolom + ",6) " + _HEX)


_DDL_KODE_ANAK = (
    "CREATE TABLE kode_anak (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  akun_id TEXT NOT NULL CHECK(" + _cek_akun("akun_id") + "),\n"
    "  siswa_id INTEGER NOT NULL CHECK(siswa_id>=1),\n"
    "  kode_hash TEXT NOT NULL UNIQUE CHECK(" + _CEK_HASH + "),\n"
    "  dibuat TEXT NOT NULL CHECK(dibuat GLOB " + _WAKTU + "),\n"
    "  oleh TEXT NOT NULL CHECK(" + _cek_akun("oleh") + "),\n"
    "  peran TEXT NOT NULL CHECK(peran IN (" + _PERAN_SQL + "))\n"
    ")"
)
_DDL_KODE_CABUT = (
    "CREATE TABLE kode_cabut (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  kode_id INTEGER NOT NULL UNIQUE REFERENCES kode_anak(id),\n"
    "  pada TEXT NOT NULL CHECK(pada GLOB " + _WAKTU + "),\n"
    "  oleh TEXT NOT NULL CHECK(" + _cek_akun("oleh") + "),\n"
    "  peran TEXT NOT NULL CHECK(peran IN (" + _PERAN_SQL + "))\n"
    ")"
)
_DDL_PERMINTAAN = (
    "CREATE TABLE permintaan (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  guru_id TEXT NOT NULL CHECK(" + _cek_akun("guru_id") + "),\n"
    "  kelompok_id TEXT NOT NULL CHECK(" + _CEK_KELOMPOK + "),\n"
    "  kode_id INTEGER NOT NULL REFERENCES kode_anak(id),\n"
    "  dibuat TEXT NOT NULL CHECK(dibuat GLOB " + _WAKTU + "),\n"
    "  kedaluwarsa TEXT NOT NULL CHECK(kedaluwarsa GLOB " + _WAKTU + ")\n"
    ")"
)
_DDL_PUTUSAN = (
    "CREATE TABLE putusan (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  permintaan_id INTEGER NOT NULL UNIQUE REFERENCES permintaan(id),\n"
    "  hasil TEXT NOT NULL CHECK(hasil IN (" + _HASIL_SQL + ")),\n"
    "  pada TEXT NOT NULL CHECK(pada GLOB " + _WAKTU + "),\n"
    "  oleh TEXT NOT NULL CHECK(" + _cek_akun("oleh") + ")\n"
    ")"
)
_DDL_PERCOBAAN_GAGAL = (
    "CREATE TABLE percobaan_gagal (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  guru_id TEXT NOT NULL CHECK(" + _cek_akun("guru_id") + "),\n"
    "  pada TEXT NOT NULL CHECK(pada GLOB " + _WAKTU + ")\n"
    ")"
)
_DDL_INDEKS = (
    "CREATE INDEX idx_kode_anak_anak ON kode_anak(akun_id, siswa_id, id)",
    "CREATE INDEX idx_permintaan_guru_kode ON permintaan(guru_id, kode_id)",
    "CREATE INDEX idx_permintaan_kode_dibuat ON permintaan(kode_id, dibuat)",
    "CREATE INDEX idx_percobaan_gagal_guru ON percobaan_gagal(guru_id, pada)",
)


def _ddl_tolak(tabel: str, kata: str, aksi: str) -> str:
    return ("CREATE TRIGGER " + tabel + "_tolak_" + kata + " BEFORE " + aksi + " ON " + tabel
            + " BEGIN SELECT RAISE(ABORT, '" + _PESAN_TOLAK_UBAH + "'); END")


_DDL_TRIGGER = tuple(
    _ddl_tolak(tabel, kata, aksi)
    for tabel in TABEL_SKEMA
    for kata, aksi in (("ubah", "UPDATE"), ("hapus", "DELETE"))
)
DDL_SKEMA = (
    (_DDL_KODE_ANAK, _DDL_KODE_CABUT, _DDL_PERMINTAAN, _DDL_PUTUSAN, _DDL_PERCOBAAN_GAGAL)
    + _DDL_INDEKS + _DDL_TRIGGER
)


# --- berkas dan transaksi ---------------------------------------------------------------

def _siapkan_berkas(tujuan: Path) -> bool:
    """Buat berkas 0600 sebelum SQLite membukanya. True bila dibuat di sini; berkas yang sudah ada tidak diubah."""
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
        _log.warning("berkas tautan kosong tidak diperiksa; dibiarkan")
        return False
    return kosong


def _hapus_bila_kosong(tujuan: Path, dibuat_di_sini: bool) -> None:
    """Buang berkas 0 byte yang baru dibuat tulis ini bila gagal. Berkas lain tidak pernah disentuh.

    Berkas yang sedang dipegang penulis lain (transaksi terbuka) dibiarkan: menghapusnya membuang data penulis itu.
    """
    if not dibuat_di_sini or not _bisa_dibuang(tujuan):
        return
    try:
        tujuan.unlink()
    except OSError:
        _log.warning("berkas tautan kosong tidak bisa dibersihkan")


def _versi(kon: sqlite3.Connection) -> int:
    return kon.execute("PRAGMA user_version").fetchone()[0]


def _pastikan_skema(kon: sqlite3.Connection) -> None:
    """Buat tabel, indeks, dan trigger bila DB masih versi 0; versi lain selain VERSI_SKEMA ditolak."""
    versi = _versi(kon)
    if versi == VERSI_SKEMA:
        return
    if versi != 0:
        raise GalatTautan(_PESAN_SKEMA)
    for ddl in DDL_SKEMA:
        kon.execute(ddl)
    kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _tulis(tujuan: Path, aksi: Callable[[sqlite3.Connection], Any]) -> Any:
    """Jalankan `aksi` dalam satu transaksi IMMEDIATE. Galat domain dilempar apa adanya setelah rollback."""
    dibuat_di_sini = False
    try:
        dibuat_di_sini = _siapkan_berkas(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=TIMEOUT_DETIK)) as kon, kon:
            kon.execute("PRAGMA foreign_keys = ON")
            kon.execute("BEGIN IMMEDIATE")
            _pastikan_skema(kon)
            return aksi(kon)
    except (OSError, sqlite3.Error) as err:
        raise GalatTautan(_PESAN_TULIS) from err
    finally:
        _hapus_bila_kosong(tujuan, dibuat_di_sini)


def _baca_berkas(tujuan: Path, kosong: Any, baca: Callable[[sqlite3.Connection], Any]) -> Any:
    """Baca mode=ro dan query_only. Berkas tak ada atau versi 0 = `kosong`; versi asing ditolak."""
    if not tujuan.exists():
        return kosong
    try:
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=TIMEOUT_DETIK)) as kon:
            kon.execute("PRAGMA query_only = ON")
            versi = _versi(kon)
            if versi == 0:
                return kosong
            if versi != VERSI_SKEMA:
                raise GalatTautan(_PESAN_SKEMA)
            return baca(kon)
    except sqlite3.Error as err:
        raise GalatTautan(_PESAN_BACA) from err


# --- kueri bersama (dipakai pembaca dan pemeriksaan di dalam transaksi) -----------------

def _kode_aktif_kon(kon: sqlite3.Connection, akun_id: str, siswa_id: int) -> Optional[Dict[str, object]]:
    """Kode aktif anak: baris kode_anak TERBARU yang belum punya baris kode_cabut. Tanpa kode_hash."""
    baris = kon.execute(
        "SELECT k.id, k.dibuat, k.oleh, k.peran, "
        "EXISTS(SELECT 1 FROM kode_cabut AS c WHERE c.kode_id = k.id) "
        "FROM kode_anak AS k WHERE k.akun_id = ? AND k.siswa_id = ? ORDER BY k.id DESC LIMIT 1",
        (akun_id, siswa_id),
    ).fetchone()
    if baris is None or baris[4]:
        return None
    return {"id": baris[0], "dibuat": baris[1], "oleh": baris[2], "peran": baris[3]}


def _cari_aktif_kon(kon: sqlite3.Connection, kode_hash: str) -> Optional[Dict[str, object]]:
    baris = kon.execute("SELECT id, akun_id, siswa_id FROM kode_anak WHERE kode_hash = ?", (kode_hash,)).fetchone()
    if baris is None:
        return None
    kode_id, akun_id, siswa_id = baris
    aktif = _kode_aktif_kon(kon, akun_id, siswa_id)
    if aktif is None or aktif["id"] != kode_id:
        return None
    return {"id": kode_id, "akun_id": akun_id, "siswa_id": siswa_id}


_KOLOM_PERMINTAAN = (
    "r.id, r.guru_id, r.kelompok_id, k.akun_id, k.siswa_id, r.dibuat, r.kedaluwarsa, p.hasil, p.pada, "
    "EXISTS(SELECT 1 FROM kode_cabut AS c WHERE c.kode_id = r.kode_id)"
)
_DARI_PERMINTAAN = (
    " FROM permintaan AS r JOIN kode_anak AS k ON k.id = r.kode_id "
    "LEFT JOIN putusan AS p ON p.permintaan_id = r.id WHERE "
)


def _query_permintaan(kon: sqlite3.Connection, where: str, parameter: tuple) -> List[tuple]:
    sql = "SELECT " + _KOLOM_PERMINTAAN + _DARI_PERMINTAAN + where + " ORDER BY r.id DESC"
    return kon.execute(sql, parameter).fetchall()


def _bentuk_permintaan(baris: tuple, kini: str) -> Dict[str, object]:
    """Baris permintaan ke dict dengan status turunan pada `kini`. Kolom kode_hash tidak pernah diambil."""
    permintaan_id, guru_id, kelompok_id, akun_id, siswa_id, dibuat, kedaluwarsa, hasil, pada_putusan, dicabut = baris
    status = aturan.status_permintaan(
        kedaluwarsa=kedaluwarsa, hasil_putusan=hasil, kode_dicabut=bool(dicabut), kini=kini,
    )
    return {
        "id": permintaan_id,
        "guru_id": guru_id,
        "kelompok_id": kelompok_id,
        "akun_id": akun_id,
        "siswa_id": siswa_id,
        "dibuat": dibuat,
        "kedaluwarsa": kedaluwarsa,
        "status": status,
        "pada_putusan": pada_putusan,
    }


def _satu_permintaan(kon: sqlite3.Connection, permintaan_id: int) -> Optional[tuple]:
    baris = _query_permintaan(kon, "r.id = ?", (permintaan_id,))
    return baris[0] if baris else None


def _tolak_terakhir(kon: sqlite3.Connection, guru_id: str, akun_id: str, siswa_id: int) -> Optional[str]:
    """Waktu putusan tolak terakhir untuk (guru, anak). Kunci per anak: ganti kode tidak mereset jeda."""
    baris = kon.execute(
        "SELECT p.pada FROM putusan AS p JOIN permintaan AS r ON r.id = p.permintaan_id "
        "JOIN kode_anak AS k ON k.id = r.kode_id "
        "WHERE r.guru_id = ? AND k.akun_id = ? AND k.siswa_id = ? AND p.hasil = ? "
        "ORDER BY p.pada DESC, p.id DESC LIMIT 1",
        (guru_id, akun_id, siswa_id, aturan.HASIL_TOLAK),
    ).fetchone()
    return baris[0] if baris else None


# --- sisip (satu baris per panggilan; dipanggil dari aksi di dalam transaksi) ----------

def _sisipkan_kode(kon: sqlite3.Connection, akun_id: str, siswa_id: int, kode_hash: str,
                   oleh: str, peran: str, pada: str) -> int:
    kursor = kon.execute(
        "INSERT INTO kode_anak (akun_id, siswa_id, kode_hash, dibuat, oleh, peran) VALUES (?, ?, ?, ?, ?, ?)",
        (akun_id, siswa_id, kode_hash, pada, oleh, peran),
    )
    return int(kursor.lastrowid)


def _sisipkan_cabut(kon: sqlite3.Connection, kode_id: int, oleh: str, peran: str, pada: str) -> None:
    kon.execute(
        "INSERT INTO kode_cabut (kode_id, pada, oleh, peran) VALUES (?, ?, ?, ?)",
        (kode_id, pada, oleh, peran),
    )


def _sisipkan_permintaan(kon: sqlite3.Connection, guru_id: str, kelompok_id: str, kode_id: int, pada: str) -> int:
    kursor = kon.execute(
        "INSERT INTO permintaan (guru_id, kelompok_id, kode_id, dibuat, kedaluwarsa) VALUES (?, ?, ?, ?, ?)",
        (guru_id, kelompok_id, kode_id, pada, aturan.hitung_kedaluwarsa(pada)),
    )
    return int(kursor.lastrowid)


def _sisipkan_putusan(kon: sqlite3.Connection, permintaan_id: int, hasil: str, oleh: str, pada: str) -> None:
    kon.execute(
        "INSERT INTO putusan (permintaan_id, hasil, pada, oleh) VALUES (?, ?, ?, ?)",
        (permintaan_id, hasil, pada, oleh),
    )


def _sisipkan_gagal(kon: sqlite3.Connection, guru_id: str, pada: str) -> None:
    kon.execute("INSERT INTO percobaan_gagal (guru_id, pada) VALUES (?, ?)", (guru_id, pada))


# --- pemeriksaan dan aksi di dalam transaksi tulis --------------------------------------

def _pastikan_kode_aktif(kon: sqlite3.Connection, akun_id: str, siswa_id: int, kode_id_aktif: int) -> None:
    aktif = _kode_aktif_kon(kon, akun_id, siswa_id)
    if aktif is None or aktif["id"] != kode_id_aktif:
        raise KodeBasi(_PESAN_BASI)


def _anak_dari_kode_aktif(kon: sqlite3.Connection, kode_id: int) -> Tuple[str, int]:
    baris = kon.execute("SELECT akun_id, siswa_id FROM kode_anak WHERE id = ?", (kode_id,)).fetchone()
    if baris is None:
        raise KodeTakAktif(_PESAN_TAK_AKTIF)
    akun_id, siswa_id = baris
    aktif = _kode_aktif_kon(kon, akun_id, siswa_id)
    if aktif is None or aktif["id"] != kode_id:
        raise KodeTakAktif(_PESAN_TAK_AKTIF)
    return akun_id, siswa_id


def _pastikan_belum_menunggu(kon: sqlite3.Connection, guru_id: str, akun_id: str, siswa_id: int, pada: str) -> None:
    """Satu permintaan menunggu per (guru, anak), bukan per kode: ganti kode tidak membuka celah."""
    for baris in _query_permintaan(kon, "r.guru_id = ? AND k.akun_id = ? AND k.siswa_id = ?",
                                   (guru_id, akun_id, siswa_id)):
        if _bentuk_permintaan(baris, pada)["status"] == aturan.STATUS_MENUNGGU:
            raise PermintaanDitolakAturan(ALASAN_MENUNGGU_ADA)


def _pastikan_tidak_jeda(kon: sqlite3.Connection, guru_id: str, akun_id: str, siswa_id: int, pada: str) -> None:
    pada_tolak = _tolak_terakhir(kon, guru_id, akun_id, siswa_id)
    if pada_tolak is not None and aturan.dalam_jeda_tolak(pada_tolak, pada):
        raise PermintaanDitolakAturan(ALASAN_JEDA_TOLAK)


def _pastikan_kuota_kode(kon: sqlite3.Connection, kode_id: int, pada: str) -> None:
    batas = aturan.waktu_mundur(pada, aturan.JENDELA_KODE)
    jumlah = kon.execute(
        "SELECT COUNT(*) FROM permintaan WHERE kode_id = ? AND dibuat > ?", (kode_id, batas),
    ).fetchone()[0]
    if aturan.kode_penuh(jumlah):
        raise PermintaanDitolakAturan(ALASAN_KODE_PENUH)


def _aksi_buat(kon: sqlite3.Connection, akun_id: str, siswa_id: int, kode_hash: str,
               oleh: str, peran: str, pada: str) -> int:
    if _kode_aktif_kon(kon, akun_id, siswa_id) is not None:
        raise KodeSudahAda(_PESAN_SUDAH_ADA)
    return _sisipkan_kode(kon, akun_id, siswa_id, kode_hash, oleh, peran, pada)


def _aksi_ganti(kon: sqlite3.Connection, akun_id: str, siswa_id: int, kode_id_aktif: int,
                kode_hash_baru: str, oleh: str, peran: str, pada: str) -> int:
    _pastikan_kode_aktif(kon, akun_id, siswa_id, kode_id_aktif)
    _sisipkan_cabut(kon, kode_id_aktif, oleh, peran, pada)
    return _sisipkan_kode(kon, akun_id, siswa_id, kode_hash_baru, oleh, peran, pada)


def _aksi_cabut(kon: sqlite3.Connection, akun_id: str, siswa_id: int, kode_id_aktif: int,
                oleh: str, peran: str, pada: str) -> None:
    _pastikan_kode_aktif(kon, akun_id, siswa_id, kode_id_aktif)
    _sisipkan_cabut(kon, kode_id_aktif, oleh, peran, pada)


def _aksi_cabut_semua(kon: sqlite3.Connection, akun_id: str, siswa_id: int,
                      oleh: str, peran: str, pada: str) -> int:
    aktif = _kode_aktif_kon(kon, akun_id, siswa_id)
    if aktif is None:
        return 0
    _sisipkan_cabut(kon, aktif["id"], oleh, peran, pada)
    return 1


def _aksi_ajukan(kon: sqlite3.Connection, guru_id: str, kelompok_id: str, kode_id: int, pada: str) -> int:
    akun_id, siswa_id = _anak_dari_kode_aktif(kon, kode_id)
    _pastikan_belum_menunggu(kon, guru_id, akun_id, siswa_id, pada)
    _pastikan_tidak_jeda(kon, guru_id, akun_id, siswa_id, pada)
    _pastikan_kuota_kode(kon, kode_id, pada)
    return _sisipkan_permintaan(kon, guru_id, kelompok_id, kode_id, pada)


def _menunggu_milik_anak(bentuk: Dict[str, object], akun_id: str, siswa_id: int) -> bool:
    milik = (bentuk["akun_id"], bentuk["siswa_id"]) == (akun_id, siswa_id)
    return milik and bentuk["status"] == aturan.STATUS_MENUNGGU


def _pastikan_menunggu_milik(kon: sqlite3.Connection, permintaan_id: int, akun_id: str, siswa_id: int,
                             pada: str) -> None:
    """Hanya permintaan MILIK anak itu yang masih menunggu. Selain itu PutusanTakBisa tanpa tulis."""
    baris = _satu_permintaan(kon, permintaan_id)
    if baris is None or not _menunggu_milik_anak(_bentuk_permintaan(baris, pada), akun_id, siswa_id):
        raise PutusanTakBisa(_PESAN_TAK_BISA)


def _aksi_putusan(kon: sqlite3.Connection, permintaan_id: int, akun_id: str, siswa_id: int,
                  hasil: str, oleh: str, pada: str) -> None:
    _pastikan_menunggu_milik(kon, permintaan_id, akun_id, siswa_id, pada)
    _sisipkan_putusan(kon, permintaan_id, hasil, oleh, pada)


class _GalatPenempatan(Exception):
    """Galat sqlite/OS dari `tempatkan()` dibawa keluar dari `_tulis` apa adanya, lalu dibuka lagi tanpa dibungkus."""

    def __init__(self, asli: BaseException) -> None:
        super().__init__("penempatan gagal")
        self.asli = asli


def _aksi_setuju_dengan_tempat(kon: sqlite3.Connection, permintaan_id: int, akun_id: str, siswa_id: int,
                               oleh: str, pada: str, tempatkan: Callable[[], Any]) -> None:
    _pastikan_menunggu_milik(kon, permintaan_id, akun_id, siswa_id, pada)
    try:
        tempatkan()
    except (OSError, sqlite3.Error) as galat:
        raise _GalatPenempatan(galat) from galat
    _sisipkan_putusan(kon, permintaan_id, aturan.HASIL_SETUJU, oleh, pada)


def _aksi_gagal(kon: sqlite3.Connection, guru_id: str, pada: str) -> None:
    _sisipkan_gagal(kon, guru_id, pada)


# --- tulis (API publik) -----------------------------------------------------------------

def buat_kode(*, akun_id: str, siswa_id: int, kode_hash: str, oleh: str, peran: str, pada: str,
              path=None) -> int:
    """Kode baru untuk anak. Ditolak (`KodeSudahAda`) bila anak masih punya kode aktif. Mengembalikan id kode."""
    _periksa_anak(akun_id, siswa_id)
    _periksa_hash(kode_hash)
    _periksa_pencatat(oleh, peran, pada)
    return _tulis(_path_db(path), lambda kon: _aksi_buat(kon, akun_id, siswa_id, kode_hash, oleh, peran, pada))


def ganti_kode(*, akun_id: str, siswa_id: int, kode_id_aktif: int, kode_hash_baru: str,
               oleh: str, peran: str, pada: str, path=None) -> int:
    """Cabut kode aktif (harus `kode_id_aktif`) dan buat kode baru dalam satu transaksi. Mengembalikan id kode baru."""
    _periksa_anak(akun_id, siswa_id)
    _periksa_id(kode_id_aktif, "ID kode")
    _periksa_hash(kode_hash_baru)
    _periksa_pencatat(oleh, peran, pada)
    return _tulis(_path_db(path), lambda kon: _aksi_ganti(
        kon, akun_id, siswa_id, kode_id_aktif, kode_hash_baru, oleh, peran, pada))


def cabut_kode(*, akun_id: str, siswa_id: int, kode_id_aktif: int, oleh: str, peran: str, pada: str,
               path=None) -> None:
    """Cabut kode aktif anak. `kode_id_aktif` yang basi ditolak (`KodeBasi`) tanpa tulis."""
    _periksa_anak(akun_id, siswa_id)
    _periksa_id(kode_id_aktif, "ID kode")
    _periksa_pencatat(oleh, peran, pada)
    _tulis(_path_db(path), lambda kon: _aksi_cabut(kon, akun_id, siswa_id, kode_id_aktif, oleh, peran, pada))


def cabut_semua(*, akun_id: str, siswa_id: int, oleh: str, peran: str, pada: str, path=None) -> int:
    """Cabut kode aktif anak bila ada. Idempoten: mengembalikan 1 bila ada yang dicabut, 0 bila tidak.

    Bila berkas belum ada tidak ada yang bisa dicabut, sehingga berkas tidak dibuat.
    """
    _periksa_anak(akun_id, siswa_id)
    _periksa_pencatat(oleh, peran, pada)
    tujuan = _path_db(path)
    if not tujuan.exists():
        return 0
    return _tulis(tujuan, lambda kon: _aksi_cabut_semua(kon, akun_id, siswa_id, oleh, peran, pada))


def ajukan(*, guru_id: str, kelompok_id: str, kode_id: int, pada: str, path=None) -> int:
    """Permintaan guru untuk memasukkan anak pemilik `kode_id` ke kelompoknya. Mengembalikan id permintaan.

    Ditolak `KodeTakAktif` bila kode tidak aktif, dan `PermintaanDitolakAturan` bila melanggar aturan
    (menunggu_ada, jeda_tolak, kode_penuh).

    TIDAK memeriksa bahwa guru pemilik `kelompok_id` dan bahwa anak masih ada (`anak_masih_ada`). Kedua pemeriksaan
    itu lapisan 3b-2 yang WAJIB ada sebelum fungsi ini dipanggil dari HTTP.
    """
    _periksa_akun(guru_id, "ID guru")
    _periksa_kelompok(kelompok_id)
    _periksa_id(kode_id, "ID kode")
    _periksa_waktu(pada)
    return _tulis(_path_db(path), lambda kon: _aksi_ajukan(kon, guru_id, kelompok_id, kode_id, pada))


def putusan(*, permintaan_id: int, akun_id: str, siswa_id: int, hasil: str, oleh: str, pada: str,
            path=None) -> None:
    """Putusan atas permintaan yang MILIK anak (`akun_id`, `siswa_id`) dan masih menunggu.

    Selain itu (anak lain, id tak ada, sudah diputus/kedaluwarsa/batal) `PutusanTakBisa` tanpa tulis.
    """
    _periksa_id(permintaan_id, "ID permintaan")
    _periksa_anak(akun_id, siswa_id)
    _periksa_hasil(hasil)
    _periksa_akun(oleh, "ID pencatat")
    _periksa_waktu(pada)
    _tulis(_path_db(path), lambda kon: _aksi_putusan(
        kon, permintaan_id, akun_id, siswa_id, hasil, oleh, pada))


def putusan_dengan_tempat(*, permintaan_id: int, akun_id: str, siswa_id: int, oleh: str, pada: str,
                          tempatkan: Callable[[], Any], path=None) -> None:
    """Setujui permintaan MILIK anak sambil menempatkannya, dalam SATU transaksi tautan (BEGIN IMMEDIATE).

    Urutan: verifikasi milik dan menunggu -> `tempatkan()` (tanpa argumen; transaksinya sendiri di luar tautan) ->
    sisip putusan `setuju` -> commit. Galat dari `tempatkan()` membatalkan tautan dan TANPA putusan. Galat domain
    dilempar apa adanya; galat sqlite/OS dari `tempatkan()` juga dilempar apa adanya (tidak dibungkus GalatTautan),
    supaya galat berkas admin tidak berlabel galat tautan. Galat sqlite saat menyisip putusan tetap GalatTautan.
    Permintaan yang tidak menunggu atau bukan milik anak itu = PutusanTakBisa tanpa memanggil `tempatkan()`.
    """
    _periksa_id(permintaan_id, "ID permintaan")
    _periksa_anak(akun_id, siswa_id)
    _periksa_akun(oleh, "ID pencatat")
    _periksa_waktu(pada)
    if not callable(tempatkan):
        raise ValueError("Penempatan tidak sah.")
    try:
        _tulis(_path_db(path), lambda kon: _aksi_setuju_dengan_tempat(
            kon, permintaan_id, akun_id, siswa_id, oleh, pada, tempatkan))
    except _GalatPenempatan as bawa:
        raise bawa.asli from None


def catat_gagal(*, guru_id: str, pada: str, path=None) -> None:
    """Catat satu percobaan kode yang gagal milik guru (untuk batas laju per guru)."""
    _periksa_akun(guru_id, "ID guru")
    _periksa_waktu(pada)
    _tulis(_path_db(path), lambda kon: _aksi_gagal(kon, guru_id, pada))


# --- baca (tanpa membuat berkas; tanpa kode_hash) ---------------------------------------

def kode_aktif(akun_id: str, siswa_id: int, *, path=None) -> Optional[Dict[str, object]]:
    """Kode aktif anak: {"id", "dibuat", "oleh", "peran"}, atau None. Tanpa kode_hash."""
    _periksa_anak(akun_id, siswa_id)
    return _baca_berkas(_path_db(path), None, lambda kon: _kode_aktif_kon(kon, akun_id, siswa_id))


def cari_kode_aktif(kode_hash: Any, *, path=None) -> Optional[Dict[str, object]]:
    """{"id", "akun_id", "siswa_id"} bila hash itu kode yang masih aktif, selain itu None.

    Hash yang bukan 64 heks kecil (termasuk None) dijawab None tanpa menyentuh berkas dan tanpa raise: gagal tertutup.
    """
    if not _hash_sah(kode_hash):
        return None
    return _baca_berkas(_path_db(path), None, lambda kon: _cari_aktif_kon(kon, kode_hash))


def permintaan_dengan_status(permintaan_id: int, kini: str, *, path=None) -> Optional[Dict[str, object]]:
    """Satu permintaan dengan status turunan pada `kini`, atau None bila tidak ada."""
    _periksa_id(permintaan_id, "ID permintaan")
    _periksa_waktu(kini)
    return _baca_berkas(_path_db(path), None, lambda kon: _satu_bentuk(kon, permintaan_id, kini))


def _satu_bentuk(kon: sqlite3.Connection, permintaan_id: int, kini: str) -> Optional[Dict[str, object]]:
    baris = _satu_permintaan(kon, permintaan_id)
    return None if baris is None else _bentuk_permintaan(baris, kini)


def _daftar(kon: sqlite3.Connection, where: str, parameter: tuple, kini: str) -> List[Dict[str, object]]:
    return [_bentuk_permintaan(baris, kini) for baris in _query_permintaan(kon, where, parameter)]


def _untuk_guru(bentuk: Dict[str, object]) -> Dict[str, object]:
    """Identitas anak (akun_id, siswa_id) terbuka untuk guru hanya bila status `setuju` (anak sudah anggota)."""
    if bentuk["status"] == aturan.STATUS_SETUJU:
        return bentuk
    return {**bentuk, "akun_id": None, "siswa_id": None}


def daftar_untuk_guru(guru_id: str, kini: str, *, path=None) -> List[Dict[str, object]]:
    """Permintaan milik guru itu saja, terbaru dulu. Identitas anak disamarkan kecuali status `setuju`."""
    _periksa_akun(guru_id, "ID guru")
    _periksa_waktu(kini)
    return _baca_berkas(_path_db(path), [], lambda kon: [
        _untuk_guru(bentuk) for bentuk in _daftar(kon, "r.guru_id = ?", (guru_id,), kini)
    ])


def daftar_untuk_anak(akun_id: str, siswa_id: int, kini: str, *, path=None) -> List[Dict[str, object]]:
    """Permintaan terhadap kode-kode anak itu, termasuk yang sudah dicabut, terbaru dulu."""
    _periksa_anak(akun_id, siswa_id)
    _periksa_waktu(kini)
    return _baca_berkas(_path_db(path), [], lambda kon: _daftar(
        kon, "k.akun_id = ? AND k.siswa_id = ?", (akun_id, siswa_id), kini))


def jumlah_gagal_guru(guru_id: str, kini: str, *, path=None) -> int:
    """Jumlah percobaan gagal guru dalam JENDELA_GURU terakhir. Tepat di batas awal jendela tidak dihitung."""
    _periksa_akun(guru_id, "ID guru")
    _periksa_waktu(kini)
    batas = aturan.waktu_mundur(kini, aturan.JENDELA_GURU)
    return _baca_berkas(_path_db(path), 0, lambda kon: _hitung_gagal(kon, guru_id, batas))


def _hitung_gagal(kon: sqlite3.Connection, guru_id: str, batas: str) -> int:
    return kon.execute(
        "SELECT COUNT(*) FROM percobaan_gagal WHERE guru_id = ? AND pada > ?", (guru_id, batas),
    ).fetchone()[0]

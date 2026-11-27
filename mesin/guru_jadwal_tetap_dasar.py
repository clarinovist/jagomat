"""Penyimpanan jadwal tetap guru: DB SQLite terpisah (`guru-jadwal-tetap.db`), append-only.

Guru mengusulkan blok jam mingguan; admin menyetujui, menolak, atau menetapkan langsung. Baris tidak pernah diubah
atau dihapus: aktif, menunggu, dan ditolak terakhir dihitung dari tabel usulan dan putusan. Keputusan yang
bergantung pada keadaan terkini (usul, tetapkan_admin, putus) memeriksanya di dalam `BEGIN IMMEDIATE` yang sama
dengan INSERT-nya. Berkas dibuat privat 0600 pada tulis pertama; baca tidak pernah membuat berkas.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

import auth
import guru_pertemuan_aturan as pertemuan
from guru_jadwal_tetap_bentuk import NAMA_BERKAS, TABEL_SKEMA, VERSI_SKEMA

_log = logging.getLogger(__name__)

ENV_DB = "GURU_JADWAL_TETAP_DB"
BERKAS_BAWAAN = "/data/" + NAMA_BERKAS
IZIN_BERKAS = 0o600
TIMEOUT_DETIK = 5.0
TIMEOUT_KUNCI_UJI_DETIK = 0.0
BATAS_USULAN_PER_HARI = 10
JENDELA_BATAS = timedelta(hours=24)
AWAL_JENDELA_TAHUN_SATU = "0000-00-00T00:00:00"
PANJANG_BLOK_MAKS = 200
KARAKTER_BLOK = frozenset("0123456789@-;")
BATAS_RIWAYAT_BAWAAN = 20
ID_MINIMUM = 1
ASAL_GURU = "guru"
ASAL_ADMIN = "admin"
PUTUSAN_SETUJU = "setuju"
PUTUSAN_TOLAK = "tolak"
PUTUSAN_SAH = (PUTUSAN_SETUJU, PUTUSAN_TOLAK)
KIND_UMUM = "umum"
KIND_KONFLIK = "konflik"
KIND_BATAS = "batas"
_PESAN_TOLAK_UBAH = "jadwal tetap guru hanya boleh ditambah"
_PESAN_TULIS = "Jadwal tetap guru tidak bisa ditulis."
_PESAN_BACA = "Jadwal tetap guru tidak bisa dibaca."
_PESAN_SKEMA = "Skema jadwal tetap guru tidak dikenali."
_PESAN_KONFLIK = "Usulan ini tidak lagi menunggu keputusan."
_PESAN_BATAS = "Batas usulan jadwal tetap dalam 24 jam sudah tercapai."

# Potongan SQL CHECK. Pola yang sama dengan guru_tugas_dasar (tidak di-import: modul ini mandiri).
_HEX = "NOT GLOB '*[^0-9a-f]*'"
_WAKTU = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
_PANJANG_AKUN = len("akun_") + 32


def _cek_akun(kolom: str) -> str:
    return f"length({kolom})={_PANJANG_AKUN} AND substr({kolom},1,5)='akun_' AND substr({kolom},6) {_HEX}"


_DDL_USULAN = (
    "CREATE TABLE tetap_usulan (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    f"  guru_akun TEXT NOT NULL CHECK({_cek_akun('guru_akun')}),\n"
    f"  blok TEXT NOT NULL CHECK(length(blok)<={PANJANG_BLOK_MAKS}),\n"
    "  asal TEXT NOT NULL CHECK(asal IN ('guru','admin')),\n"
    f"  oleh TEXT NOT NULL CHECK({_cek_akun('oleh')}),\n"
    f"  dibuat TEXT NOT NULL CHECK(dibuat GLOB {_WAKTU}),\n"
    "  CHECK(asal<>'guru' OR oleh=guru_akun)\n"
    ")"
)
_DDL_PUTUSAN = (
    "CREATE TABLE tetap_putusan (\n"
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "  usulan_id INTEGER NOT NULL UNIQUE REFERENCES tetap_usulan(id),\n"
    "  putusan TEXT NOT NULL CHECK(putusan IN ('setuju','tolak')),\n"
    f"  oleh TEXT NOT NULL CHECK({_cek_akun('oleh')}),\n"
    f"  dibuat TEXT NOT NULL CHECK(dibuat GLOB {_WAKTU})\n"
    ")"
)
_DDL_INDEKS = ("CREATE INDEX idx_tetap_usulan_guru ON tetap_usulan(guru_akun, id)",)


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
DDL_SKEMA = (_DDL_USULAN, _DDL_PUTUSAN) + _DDL_INDEKS + _DDL_TRIGGER

# Menunggu = usulan guru TERAKHIR, belum berputusan, dan lebih baru dari aktif. Usulan guru yang lebih lama dari
# usulan terakhir itu sudah tergantikan dan tidak pernah muncul lagi, walau penggantinya ditolak.
_SQL_MENUNGGU = (
    "SELECT id, blok, dibuat FROM ("
    "SELECT u.id, u.blok, u.dibuat, "
    "EXISTS (SELECT 1 FROM tetap_putusan AS p WHERE p.usulan_id = u.id) AS berputusan "
    "FROM tetap_usulan AS u WHERE u.guru_akun = ? AND u.asal = 'guru' "
    "ORDER BY u.id DESC LIMIT 1"
    ") WHERE berputusan = 0 AND id > ?"
)
_SQL_AKTIF = (
    "SELECT u.id, u.blok, u.asal, u.oleh, u.dibuat, p.dibuat "
    "FROM tetap_putusan AS p JOIN tetap_usulan AS u ON u.id = p.usulan_id "
    "WHERE u.guru_akun = ? AND p.putusan = 'setuju' ORDER BY p.id DESC LIMIT 1"
)
_SQL_TOLAK_TERAKHIR = (
    "SELECT u.id, u.blok, p.dibuat FROM tetap_usulan AS u "
    "JOIN tetap_putusan AS p ON p.usulan_id = u.id "
    "WHERE u.guru_akun = ? AND u.asal = 'guru' AND p.putusan = 'tolak' ORDER BY u.id DESC LIMIT 1"
)
_SQL_JUMLAH_USULAN = (
    "SELECT COUNT(*) FROM tetap_usulan WHERE guru_akun = ? AND asal = 'guru' AND dibuat > ?"
)
_SQL_RIWAYAT = (
    "SELECT u.id, u.blok, u.asal, u.oleh, u.dibuat, p.putusan, p.oleh, p.dibuat "
    "FROM tetap_usulan AS u LEFT JOIN tetap_putusan AS p ON p.usulan_id = u.id "
    "WHERE u.guru_akun = ? ORDER BY u.id DESC LIMIT ?"
)
_SQL_DAFTAR_GURU = "SELECT DISTINCT guru_akun FROM tetap_usulan ORDER BY guru_akun"
_KOLOM_AKTIF = ("usulan_id", "blok", "asal", "oleh", "dibuat", "diputus")
_KOLOM_MENUNGGU = ("usulan_id", "blok", "dibuat")
_KOLOM_RIWAYAT = ("usulan_id", "blok", "asal", "oleh", "dibuat", "putusan", "diputus_oleh", "diputus")


class GalatTetap(Exception):
    """Jadwal tetap guru tidak bisa dibaca atau ditulis, atau usulan melanggar aturan.

    `kind`: "umum" (galat baca, tulis, atau skema), "konflik" (usulan tidak lagi menunggu), "batas" (laju usulan).
    Pesan tidak memuat path berkas maupun data privat.
    """

    def __init__(self, kind: str, pesan: str) -> None:
        super().__init__(pesan)
        self.kind = kind


def _konflik() -> GalatTetap:
    return GalatTetap(KIND_KONFLIK, _PESAN_KONFLIK)


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


def _periksa_guru(guru_akun) -> None:
    if not auth.id_akun_sah(guru_akun):
        raise ValueError("ID akun guru tidak sah.")


def _periksa_admin(admin_akun) -> None:
    if not auth.id_akun_sah(admin_akun):
        raise ValueError("ID akun admin tidak sah.")


def _periksa_waktu(waktu) -> None:
    if not pertemuan.waktu_sah(waktu):
        raise ValueError("Waktu jadwal tetap tidak sah.")


def _periksa_blok(blok) -> None:
    """Teks kanonik `<hari>@<mulai>-<selesai>` dipisah `;`, atau kosong. Bentuk lengkapnya dicek lapisan atas."""
    if type(blok) is not str or len(blok) > PANJANG_BLOK_MAKS or not set(blok) <= KARAKTER_BLOK:
        raise ValueError("Blok jadwal tetap tidak sah.")


def _periksa_usul(guru_akun, blok, dibuat) -> None:
    _periksa_guru(guru_akun)
    _periksa_blok(blok)
    _periksa_waktu(dibuat)


def _periksa_putus(usulan_id, putusan, admin_akun, dibuat) -> None:
    _periksa_id(usulan_id, ID_MINIMUM, "ID usulan tidak sah.")
    if putusan not in PUTUSAN_SAH:
        raise ValueError("Putusan tidak sah.")
    _periksa_admin(admin_akun)
    _periksa_waktu(dibuat)


def _periksa_bukan_symlink(tujuan: Path, pesan: str) -> None:
    """Tolak symlink di komponen terakhir: SQLite akan mengikutinya ke sasaran di luar DB ini.

    Hanya komponen terakhir yang diperiksa. Ada celah kecil antara cek ini dan open SQLite (TOCTOU).
    """
    try:
        mode = os.lstat(tujuan).st_mode
    except FileNotFoundError:
        return
    except OSError as err:
        raise GalatTetap(KIND_UMUM, pesan) from err
    if stat.S_ISLNK(mode):
        raise GalatTetap(KIND_UMUM, pesan)


# --- skema dan berkas -------------------------------------------------------------------

def _versi(kon) -> int:
    return kon.execute("PRAGMA user_version").fetchone()[0]


def _pastikan_skema(kon) -> None:
    """Buat tabel, indeks, dan trigger bila DB masih versi 0; versi lain selain VERSI_SKEMA ditolak."""
    versi = _versi(kon)
    if versi == VERSI_SKEMA:
        return
    if versi != 0:
        raise GalatTetap(KIND_UMUM, _PESAN_SKEMA)
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
        _log.warning("berkas jadwal tetap kosong tidak diperiksa; dibiarkan")
        return False
    return kosong


def _hapus_bila_kosong(tujuan: Path, dibuat_di_sini: bool) -> None:
    """Bersihkan berkas 0 byte yang baru dibuat bila penulisan pertama gagal.

    Berkas 0 byte tidak punya header SQLite, sehingga backup operasional akan menolaknya. Berkas yang sudah ada
    sebelumnya atau sudah berisi tidak pernah disentuh, dan berkas yang dipegang penulis lain dibiarkan.
    """
    if not dibuat_di_sini or not _bisa_dibuang(tujuan):
        return
    try:
        tujuan.unlink()
    except OSError:
        _log.warning("berkas jadwal tetap kosong tidak bisa dibersihkan")


# --- tulis ------------------------------------------------------------------------------

def _tulis(tujuan: Path, kerja: Callable[[sqlite3.Connection], object]):
    """Satu BEGIN IMMEDIATE: skema (bila berkas baru), `kerja`, lalu commit. Galat SQLite/OS dibungkus `umum`."""
    _periksa_bukan_symlink(tujuan, _PESAN_TULIS)
    dibuat_di_sini = False
    try:
        dibuat_di_sini = _siapkan_berkas(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=TIMEOUT_DETIK)) as kon, kon:
            kon.execute("BEGIN IMMEDIATE")
            _pastikan_skema(kon)
            return kerja(kon)
    except (OSError, sqlite3.Error) as err:
        raise GalatTetap(KIND_UMUM, _PESAN_TULIS) from err
    finally:
        _hapus_bila_kosong(tujuan, dibuat_di_sini)


def _sisipkan_usulan(kon, guru_akun: str, blok: str, asal: str, oleh: str, dibuat: str) -> int:
    kursor = kon.execute(
        "INSERT INTO tetap_usulan (guru_akun, blok, asal, oleh, dibuat) VALUES (?, ?, ?, ?, ?)",
        (guru_akun, blok, asal, oleh, dibuat),
    )
    return kursor.lastrowid


def _sisipkan_putusan(kon, usulan_id: int, putusan: str, oleh: str, dibuat: str) -> None:
    kon.execute(
        "INSERT INTO tetap_putusan (usulan_id, putusan, oleh, dibuat) VALUES (?, ?, ?, ?)",
        (usulan_id, putusan, oleh, dibuat),
    )


def _batas_bawah_jendela(dibuat: str) -> str:
    """Batas bawah jendela 24 jam sebagai teks baku. Sebelum tahun 1, semua baris berada di dalam jendela."""
    try:
        waktu = datetime.strptime(dibuat, pertemuan.FORMAT_WAKTU) - JENDELA_BATAS
    except OverflowError:
        return AWAL_JENDELA_TAHUN_SATU
    return waktu.isoformat(timespec="seconds")


def _periksa_batas(kon, guru_akun: str, dibuat: str) -> None:
    """Galat `batas` bila guru sudah punya BATAS_USULAN_PER_HARI usulan dalam 24 jam sampai `dibuat`."""
    (jumlah,) = kon.execute(_SQL_JUMLAH_USULAN, (guru_akun, _batas_bawah_jendela(dibuat))).fetchone()
    if jumlah >= BATAS_USULAN_PER_HARI:
        raise GalatTetap(KIND_BATAS, _PESAN_BATAS)


def _usul_kon(kon, guru_akun: str, blok: str, dibuat: str) -> bool:
    _periksa_batas(kon, guru_akun, dibuat)
    aktif = _aktif_kon(kon, guru_akun)
    menunggu = _menunggu_kon(kon, guru_akun, aktif)
    acuan = menunggu if menunggu is not None else aktif
    if acuan is not None and acuan["blok"] == blok:
        return False
    _sisipkan_usulan(kon, guru_akun, blok, ASAL_GURU, guru_akun, dibuat)
    return True


def _tetapkan_kon(kon, guru_akun: str, blok: str, admin_akun: str, dibuat: str) -> bool:
    aktif = _aktif_kon(kon, guru_akun)
    menunggu = _menunggu_kon(kon, guru_akun, aktif)
    if menunggu is None and aktif is not None and aktif["blok"] == blok:
        return False
    usulan_id = _sisipkan_usulan(kon, guru_akun, blok, ASAL_ADMIN, admin_akun, dibuat)
    _sisipkan_putusan(kon, usulan_id, PUTUSAN_SETUJU, admin_akun, dibuat)
    return True


def _guru_usulan(kon, usulan_id: int) -> Optional[str]:
    """Guru pemilik usulan asal guru; None bila usulan tidak ada atau berasal dari admin."""
    baris = kon.execute("SELECT guru_akun FROM tetap_usulan WHERE id = ? AND asal = 'guru'", (usulan_id,)).fetchone()
    return None if baris is None else baris[0]


def _putus_kon(kon, usulan_id: int, putusan: str, admin_akun: str, dibuat: str) -> None:
    guru_akun = _guru_usulan(kon, usulan_id)
    if guru_akun is None:
        raise _konflik()
    aktif = _aktif_kon(kon, guru_akun)
    menunggu = _menunggu_kon(kon, guru_akun, aktif)
    if menunggu is None or menunggu["usulan_id"] != usulan_id:
        raise _konflik()
    _sisipkan_putusan(kon, usulan_id, putusan, admin_akun, dibuat)


# --- keadaan turunan (dipakai di dalam transaksi maupun baca) --------------------------

def _id_aktif(aktif: Optional[dict]) -> int:
    return aktif["usulan_id"] if aktif is not None else 0


def _aktif_kon(kon, guru_akun: str) -> Optional[dict]:
    baris = kon.execute(_SQL_AKTIF, (guru_akun,)).fetchone()
    return None if baris is None else dict(zip(_KOLOM_AKTIF, baris))


def _menunggu_kon(kon, guru_akun: str, aktif: Optional[dict]) -> Optional[dict]:
    baris = kon.execute(_SQL_MENUNGGU, (guru_akun, _id_aktif(aktif))).fetchone()
    return None if baris is None else dict(zip(_KOLOM_MENUNGGU, baris))


def _menunggu_terkini(kon, guru_akun: str) -> Optional[dict]:
    return _menunggu_kon(kon, guru_akun, _aktif_kon(kon, guru_akun))


def _ditolak_terakhir_kon(kon, guru_akun: str) -> Optional[dict]:
    baris = kon.execute(_SQL_TOLAK_TERAKHIR, (guru_akun,)).fetchone()
    if baris is None:
        return None
    usulan_id, blok, diputus = baris
    aktif = _aktif_kon(kon, guru_akun)
    menunggu = _menunggu_kon(kon, guru_akun, aktif)
    if usulan_id <= _id_aktif(aktif):
        return None
    if menunggu is not None and usulan_id <= menunggu["usulan_id"]:
        return None
    return {"usulan_id": usulan_id, "blok": blok, "diputus": diputus}


def _riwayat_kon(kon, guru_akun: str, batas: int) -> List[dict]:
    return [dict(zip(_KOLOM_RIWAYAT, baris)) for baris in kon.execute(_SQL_RIWAYAT, (guru_akun, batas)).fetchall()]


def _peta_per_guru(kon, pilih: Callable[[object, str], Optional[dict]]) -> Dict[str, dict]:
    """Peta guru_akun -> isi `pilih` untuk setiap guru yang pernah mengusulkan atau ditetapkan. Yang None dilewati."""
    hasil = {}
    for (guru_akun,) in kon.execute(_SQL_DAFTAR_GURU).fetchall():
        isi = pilih(kon, guru_akun)
        if isi is not None:
            hasil[guru_akun] = isi
    return hasil


# --- API tulis --------------------------------------------------------------------------

def usul(*, guru_akun: str, blok: str, dibuat: str, path=None) -> bool:
    """Usulan jadwal dari guru. True bila baris baru ditulis; no-op (False) bila identik dengan acuannya.

    Acuannya menunggu bila ada, selain itu aktif.
    """
    _periksa_usul(guru_akun, blok, dibuat)
    return _tulis(_path_db(path), lambda kon: _usul_kon(kon, guru_akun, blok, dibuat))


def tetapkan_admin(*, guru_akun: str, blok: str, admin_akun: str, dibuat: str, path=None) -> bool:
    """Ketetapan langsung admin: aktif sekaligus, menggantikan usulan menunggu.

    False (no-op) bila identik dengan aktif dan tidak ada usulan menunggu.
    """
    _periksa_guru(guru_akun)
    _periksa_blok(blok)
    _periksa_admin(admin_akun)
    _periksa_waktu(dibuat)
    return _tulis(_path_db(path), lambda kon: _tetapkan_kon(kon, guru_akun, blok, admin_akun, dibuat))


def putus(*, usulan_id: int, putusan: str, admin_akun: str, dibuat: str, path=None) -> None:
    """Setuju atau tolak usulan guru yang sedang menunggu. Selain itu konflik, tanpa tulis apa pun."""
    _periksa_putus(usulan_id, putusan, admin_akun, dibuat)
    tujuan = _path_db(path)
    _periksa_bukan_symlink(tujuan, _PESAN_TULIS)
    if not tujuan.exists():
        raise _konflik()
    _tulis(tujuan, lambda kon: _putus_kon(kon, usulan_id, putusan, admin_akun, dibuat))


# --- API baca (tidak pernah membuat berkas) ---------------------------------------------

def _baca_berkas(tujuan: Path, kosong, baca: Callable[[sqlite3.Connection], object]):
    """Baca mode=ro dan query_only. Berkas tak ada atau versi 0 = `kosong`; versi asing ditolak."""
    _periksa_bukan_symlink(tujuan, _PESAN_BACA)
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
                raise GalatTetap(KIND_UMUM, _PESAN_SKEMA)
            return baca(kon)
    except sqlite3.Error as err:
        raise GalatTetap(KIND_UMUM, _PESAN_BACA) from err


def aktif(guru_akun: str, *, path=None) -> Optional[dict]:
    """Jadwal yang berlaku: usulan dengan putusan 'setuju' yang id putusannya terbesar; None bila belum ada."""
    _periksa_guru(guru_akun)
    return _baca_berkas(_path_db(path), None, lambda kon: _aktif_kon(kon, guru_akun))


def menunggu(guru_akun: str, *, path=None) -> Optional[dict]:
    """Usulan guru yang menunggu keputusan admin; None bila tidak ada."""
    _periksa_guru(guru_akun)
    return _baca_berkas(_path_db(path), None, lambda kon: _menunggu_terkini(kon, guru_akun))


def ditolak_terakhir(guru_akun: str, *, path=None) -> Optional[dict]:
    """Usulan guru terakhir yang ditolak, bila masih lebih baru dari aktif dan dari menunggu; None bila tidak ada."""
    _periksa_guru(guru_akun)
    return _baca_berkas(_path_db(path), None, lambda kon: _ditolak_terakhir_kon(kon, guru_akun))


def aktif_semua(*, path=None) -> Dict[str, dict]:
    """Peta guru_akun -> isi `aktif` untuk guru yang punya jadwal aktif."""
    return _baca_berkas(_path_db(path), {}, lambda kon: _peta_per_guru(kon, _aktif_kon))


def menunggu_semua(*, path=None) -> Dict[str, dict]:
    """Peta guru_akun -> isi `menunggu` untuk guru yang punya usulan menunggu."""
    return _baca_berkas(_path_db(path), {}, lambda kon: _peta_per_guru(kon, _menunggu_terkini))


def riwayat(guru_akun: str, *, batas: int = BATAS_RIWAYAT_BAWAAN, path=None) -> List[dict]:
    """Usulan guru terbaru dahulu (id turun), maksimal `batas`, dengan putusannya bila sudah ada."""
    _periksa_guru(guru_akun)
    _periksa_id(batas, ID_MINIMUM, "Batas riwayat tidak sah.")
    return _baca_berkas(_path_db(path), [], lambda kon: _riwayat_kon(kon, guru_akun, batas))

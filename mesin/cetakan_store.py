"""Store cetakan soal berpola: DB SQLite terpisah (`cetakan.db`, skema v1).

Meniru `kurikulum_override`: membaca (mode=ro) tidak pernah membuat berkas; tulis dalam satu
transaksi `BEGIN IMMEDIATE` (cek skema, cek revisi, ubah, audit); revisi naik monoton; berkas 0o600.
Hanya `buat_draf` yang boleh membuat berkas. Transisi pada berkas yang belum ada ditolak
`ValueError` tanpa membuat apa pun.

Siklus status: draf -> aktif (`setujui`) -> nonaktif (`nonaktifkan`) -> aktif (`aktifkan_kembali`).
`ubah_draf` hanya untuk status draf. Tidak ada hapus: riwayat tetap ada (plan §3).
`setujui` dan `aktifkan_kembali` membaca ulang isi dan status DI DALAM transaksi lalu menjalankan
`cetakan_pola.uji_kelayakan` atas isi tersimpan itu; gagal = ValueError tanpa efek.

BEDA dari tulis: kegagalan BACA (berkas tak ada, bukan sqlite, user_version asing, tabel hilang)
jatuh ke hasil KOSONG dan dicatat lewat `logging` tanpa isi (plan §6: "Buat soal" tetap jalan
dengan cetakan kode saja). Baris rusak (JSON/validasi gagal, status/sumber asing, kelas/bab
kolom tak cocok dengan isi) dilewati satu per satu. TULIS ke DB berskema asing ditolak
(`GalatCetakan`) agar tidak menimpa berkas lain.

Hanya mengimpor stdlib + `cetakan_pola` (yang mengimpor `kurikulum_kelas`); tidak boleh diimpor
modul inti soal (`generator` dan penutupan impornya): cetakan tidak masuk sesi anak (C1).
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Optional, Tuple

import cetakan_pola

BERKAS_BAWAAN = "/data/cetakan.db"
ENV_BERKAS_DB = "CETAKAN_BERKAS_DB"
VERSI_SKEMA = 1
TTL_DETIK = 5
MAKS_PELAKU = 100
BATAS_RIWAYAT_BAWAAN = 10
BATAS_RIWAYAT_MAKS = 50

STATUS_DRAF = "draf"
STATUS_AKTIF = "aktif"
STATUS_NONAKTIF = "nonaktif"
STATUS_SAH = (STATUS_DRAF, STATUS_AKTIF, STATUS_NONAKTIF)
SUMBER_SAH = ("manual", "ai")
AKSI_SAH = ("buat", "ubah", "setujui", "nonaktifkan", "aktifkan")
TABEL_SKEMA = ("cetakan", "audit_cetakan")

_DDL_CETAKAN = (
    "CREATE TABLE IF NOT EXISTS cetakan (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    kelas INTEGER NOT NULL CHECK (kelas BETWEEN 1 AND 6),\n"
    "    bab INTEGER NOT NULL CHECK (bab >= 1),\n"
    "    status TEXT NOT NULL CHECK (status IN ('draf', 'aktif', 'nonaktif')),\n"
    "    sumber TEXT NOT NULL CHECK (sumber IN ('manual', 'ai')),\n"
    "    isi_json TEXT NOT NULL,\n"
    "    revisi INTEGER NOT NULL CHECK (revisi >= 1),\n"
    "    dibuat TEXT NOT NULL,\n"
    "    diperbarui TEXT NOT NULL\n"
    ")"
)
_DDL_AUDIT = (
    "CREATE TABLE IF NOT EXISTS audit_cetakan (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    cetakan_id INTEGER NOT NULL REFERENCES cetakan(id),\n"
    "    aksi TEXT NOT NULL CHECK (aksi IN ('buat', 'ubah', 'setujui', 'nonaktifkan', 'aktifkan')),\n"
    "    lama TEXT,\n"
    "    baru TEXT,\n"
    "    revisi INTEGER NOT NULL,\n"
    "    actor_id TEXT NOT NULL,\n"
    "    dibuat TEXT NOT NULL\n"
    ")"
)
_DDL_INDEKS = "CREATE INDEX IF NOT EXISTS idx_audit_cetakan ON audit_cetakan(cetakan_id, id)"

_log = logging.getLogger(__name__)
# Jam disuntik lewat variabel modul agar tes bisa memalsukan TTL cache.
_jam = time.monotonic
_kunci_cache = threading.Lock()
_cache = {}


class KonflikRevisi(Exception):
    """revisi_diharapkan tidak cocok dengan revisi baris sekarang."""


class GalatCetakan(Exception):
    """DB cetakan tak dapat ditulis atau skemanya tak dikenali; jangan ditelan admin."""


@dataclass(frozen=True)
class ItemCetakan:
    """Satu cetakan tersimpan: isi tervalidasi, status, sumber, dan revisi barisnya."""

    id: int
    kelas: int
    bab: int
    status: str
    sumber: str
    cetakan: cetakan_pola.Cetakan
    revisi: int
    dibuat: str
    diperbarui: str


@dataclass(frozen=True)
class RiwayatCetakan:
    """Satu entri audit: untuk buat/ubah, lama/baru = isi JSON; selain itu status lama/baru."""

    revisi: int
    aksi: str
    dibuat: str
    actor_id: str
    lama: Optional[str]
    baru: Optional[str]


def bersihkan_cache() -> None:
    """Kosongkan cache hasil baca; dipanggil setelah tulis berhasil."""
    with _kunci_cache:
        _cache.clear()


def _path_db(path) -> Path:
    """Tujuan DB: parameter, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_BERKAS_DB, BERKAS_BAWAAN))


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- validasi masukan --------------------------------------------------------

def _periksa_pelaku(actor_id) -> None:
    if (not isinstance(actor_id, str) or not actor_id.strip()
            or len(actor_id) > MAKS_PELAKU):
        raise ValueError("Identitas pelaku ubah cetakan tidak sah.")


def _periksa_revisi(revisi_diharapkan) -> None:
    if (type(revisi_diharapkan) is not int or revisi_diharapkan < 1):
        raise ValueError("Revisi yang diharapkan harus bilangan bulat positif.")


def _periksa_id(id_cetakan) -> None:
    if type(id_cetakan) is not int or id_cetakan < 1:
        raise ValueError("Id cetakan harus bilangan bulat positif.")


def _periksa_sumber(sumber) -> None:
    if sumber not in SUMBER_SAH:
        raise ValueError(f"Sumber cetakan harus salah satu dari {', '.join(SUMBER_SAH)}.")


def _periksa_batas_riwayat(batas) -> None:
    if type(batas) is not int or not 1 <= batas <= BATAS_RIWAYAT_MAKS:
        raise ValueError(f"Batas riwayat harus 1-{BATAS_RIWAYAT_MAKS}.")


# --- baris DB menjadi ItemCetakan --------------------------------------------

def _item_dari_baris(baris) -> Optional[ItemCetakan]:
    """Satu baris DB menjadi ItemCetakan; None (dengan log tanpa isi) bila baris rusak."""
    id_cetakan = baris["id"]
    try:
        if (type(id_cetakan) is not int or baris["status"] not in STATUS_SAH
                or baris["sumber"] not in SUMBER_SAH
                or type(baris["revisi"]) is not int or baris["revisi"] < 1
                or not isinstance(baris["dibuat"], str) or not isinstance(baris["diperbarui"], str)):
            raise ValueError("kolom baris tak sah")
        cetakan = cetakan_pola.dari_json(baris["isi_json"])
        if baris["kelas"] != cetakan.kelas or baris["bab"] != cetakan.bab:
            raise ValueError("kelas/bab kolom tak cocok dengan isi")
    except ValueError:
        _log.warning("Baris cetakan id=%r rusak, dilewati.", id_cetakan)
        return None
    return ItemCetakan(id_cetakan, cetakan.kelas, cetakan.bab, baris["status"], baris["sumber"],
                       cetakan, baris["revisi"], baris["dibuat"], baris["diperbarui"])


_SQL_PILIH = "SELECT id, kelas, bab, status, sumber, isi_json, revisi, dibuat, diperbarui FROM cetakan"


def _baca_db(tujuan: Path) -> Tuple[ItemCetakan, ...]:
    with closing(sqlite3.connect(f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
        kon.row_factory = sqlite3.Row
        if kon.execute("PRAGMA user_version").fetchone()[0] != VERSI_SKEMA:
            raise GalatCetakan("Skema DB cetakan tidak dikenali.")
        baris = kon.execute(_SQL_PILIH + " ORDER BY id").fetchall()
    return tuple(item for item in map(_item_dari_baris, baris) if item is not None)


def _muat(path) -> Tuple[ItemCetakan, ...]:
    """Semua cetakan sah (urut id); kegagalan apa pun jatuh ke tuple kosong (lihat docstring modul)."""
    tujuan = _path_db(path)
    kunci = os.path.abspath(str(tujuan))
    with _kunci_cache:
        entri = _cache.get(kunci)
    if entri is not None and _jam() - entri[1] < TTL_DETIK:
        return entri[0]
    try:
        semua = _baca_db(tujuan) if tujuan.exists() else ()
    except (sqlite3.Error, GalatCetakan, OSError) as err:
        _log.warning("DB cetakan tak terbaca (%s), dianggap kosong.", type(err).__name__)
        semua = ()
    with _kunci_cache:
        _cache[kunci] = (semua, _jam())
    return semua


# --- baca --------------------------------------------------------------------

def daftar(*, kelas=None, bab=None, status=None, path=None) -> Tuple[ItemCetakan, ...]:
    """Cetakan sah urut id, disaring bila kelas/bab/status diberikan."""
    return tuple(
        item for item in _muat(path)
        if (kelas is None or item.kelas == kelas) and (bab is None or item.bab == bab)
        and (status is None or item.status == status))


def ambil(id_cetakan, *, path=None) -> Optional[ItemCetakan]:
    """Satu cetakan menurut id, atau None bila tidak ada/rusak."""
    _periksa_id(id_cetakan)
    return next((item for item in _muat(path) if item.id == id_cetakan), None)


def aktif_untuk_bab(kelas: int, bab: int, *, path=None) -> Tuple[ItemCetakan, ...]:
    """Cetakan berstatus aktif untuk satu bab (urut id)."""
    return daftar(kelas=kelas, bab=bab, status=STATUS_AKTIF, path=path)


def _entri_riwayat(baris) -> Optional[RiwayatCetakan]:
    revisi, aksi = baris["revisi"], baris["aksi"]
    if (type(revisi) is not int or revisi < 1 or aksi not in AKSI_SAH
            or not isinstance(baris["dibuat"], str) or not isinstance(baris["actor_id"], str)
            or any(x is not None and not isinstance(x, str) for x in (baris["lama"], baris["baru"]))):
        _log.warning("Entri audit cetakan rusak dilewati.")
        return None
    return RiwayatCetakan(revisi, aksi, baris["dibuat"], baris["actor_id"], baris["lama"], baris["baru"])


def riwayat(id_cetakan, batas=BATAS_RIWAYAT_BAWAAN, *, path=None) -> Tuple[RiwayatCetakan, ...]:
    """Entri audit terbaru satu cetakan (terbaru dulu), baca-saja dan segar (tanpa cache).

    Berkas hilang, rusak, atau berskema asing = tuple kosong; tidak pernah membuat berkas.
    """
    _periksa_id(id_cetakan)
    _periksa_batas_riwayat(batas)
    tujuan = _path_db(path)
    try:
        if not tujuan.exists():
            return ()
        with closing(sqlite3.connect(f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
            kon.row_factory = sqlite3.Row
            if kon.execute("PRAGMA user_version").fetchone()[0] != VERSI_SKEMA:
                raise GalatCetakan("Skema DB cetakan tidak dikenali.")
            baris = kon.execute(
                "SELECT revisi, aksi, dibuat, actor_id, lama, baru FROM audit_cetakan"
                " WHERE cetakan_id = ? ORDER BY id DESC LIMIT ?", (id_cetakan, batas)).fetchall()
    except (sqlite3.Error, GalatCetakan, OSError) as err:
        _log.warning("Riwayat cetakan tak terbaca (%s).", type(err).__name__)
        return ()
    return tuple(e for e in map(_entri_riwayat, baris) if e is not None)


# --- tulis: infrastruktur ----------------------------------------------------

def _buat_skema(kon) -> None:
    for ddl in (_DDL_CETAKAN, _DDL_AUDIT, _DDL_INDEKS):
        kon.execute(ddl)


def _periksa_skema_tulis(kon) -> None:
    """Dalam transaksi: terima DB kosong (v0 tanpa tabel) atau v1; selain itu tolak."""
    versi = kon.execute("PRAGMA user_version").fetchone()[0]
    if versi not in (0, VERSI_SKEMA):
        raise GalatCetakan("Skema DB cetakan tidak dikenali.")
    if versi == 0:
        if kon.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None:
            raise GalatCetakan("DB cetakan bukan milik aplikasi ini.")
    _buat_skema(kon)
    if versi == 0:
        kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _buat_berkas_privat(tujuan: Path) -> None:
    descriptor = os.open(str(tujuan), os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)


def _jalankan_tulis(path, aksi, *, boleh_membuat: bool):
    """Satu transaksi BEGIN IMMEDIATE: cek skema, jalankan aksi(kon), commit, bersihkan cache."""
    tujuan = _path_db(path)
    try:
        if not tujuan.exists():
            if not boleh_membuat:
                raise ValueError("Cetakan tidak ditemukan.")
            _buat_berkas_privat(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=5.0)) as kon, kon:
            kon.row_factory = sqlite3.Row
            kon.execute("BEGIN IMMEDIATE")
            _periksa_skema_tulis(kon)
            hasil = aksi(kon)
    except (sqlite3.Error, OSError) as err:
        raise GalatCetakan("DB cetakan tidak dapat diubah.") from err
    bersihkan_cache()
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass
    return hasil


def _baris_dalam_transaksi(kon, id_cetakan: int, revisi_diharapkan: int):
    """Baris cetakan dari transaksi berjalan; ValueError bila tak ada, KonflikRevisi bila revisi beda."""
    baris = kon.execute(_SQL_PILIH + " WHERE id = ?", (id_cetakan,)).fetchone()
    if baris is None:
        raise ValueError("Cetakan tidak ditemukan.")
    revisi_kini = baris["revisi"]
    if type(revisi_kini) is not int or revisi_kini < 1:
        raise GalatCetakan("Baris cetakan rusak: revisi tidak terbaca.")
    if revisi_kini != revisi_diharapkan:
        raise KonflikRevisi(
            f"Revisi cetakan {id_cetakan} berubah: diharapkan {revisi_diharapkan}, sekarang {revisi_kini}.")
    return baris


def _item_wajib(baris) -> ItemCetakan:
    """ItemCetakan dari baris transaksi; baris rusak = GalatCetakan (jangan diubah diam-diam)."""
    item = _item_dari_baris(baris)
    if item is None:
        raise GalatCetakan("Baris cetakan rusak dan tidak dapat diubah.")
    return item


def _catat_audit(kon, id_cetakan, aksi, lama, baru, revisi, actor_id, dibuat) -> None:
    kon.execute(
        "INSERT INTO audit_cetakan(cetakan_id, aksi, lama, baru, revisi, actor_id, dibuat)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (id_cetakan, aksi, lama, baru, revisi, actor_id, dibuat))


def _ambil_segar(kon, id_cetakan: int) -> ItemCetakan:
    return _item_wajib(kon.execute(_SQL_PILIH + " WHERE id = ?", (id_cetakan,)).fetchone())


# --- tulis: API --------------------------------------------------------------

def buat_draf(isi, *, sumber, actor_id, path=None) -> ItemCetakan:
    """Simpan cetakan baru berstatus draf (revisi 1). ValueError untuk isi/sumber/pelaku tak sah."""
    cetakan = cetakan_pola.validasi(isi)
    _periksa_sumber(sumber)
    _periksa_pelaku(actor_id)
    isi_json = cetakan_pola.ke_json(cetakan)

    def aksi(kon):
        kini = _utc_iso()
        kursor = kon.execute(
            "INSERT INTO cetakan(kelas, bab, status, sumber, isi_json, revisi, dibuat, diperbarui)"
            " VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (cetakan.kelas, cetakan.bab, STATUS_DRAF, sumber, isi_json, kini, kini))
        _catat_audit(kon, kursor.lastrowid, "buat", None, isi_json, 1, actor_id, kini)
        return _ambil_segar(kon, kursor.lastrowid)

    return _jalankan_tulis(path, aksi, boleh_membuat=True)


def ubah_draf(id_cetakan, isi, *, actor_id, revisi_diharapkan, path=None) -> ItemCetakan:
    """Ganti isi cetakan berstatus draf; aktif/nonaktif ditolak (ValueError). Revisi naik, audit tercatat."""
    _periksa_id(id_cetakan)
    cetakan = cetakan_pola.validasi(isi)
    _periksa_pelaku(actor_id)
    _periksa_revisi(revisi_diharapkan)
    isi_json = cetakan_pola.ke_json(cetakan)

    def aksi(kon):
        baris = _baris_dalam_transaksi(kon, id_cetakan, revisi_diharapkan)
        if baris["status"] != STATUS_DRAF:
            raise ValueError("Hanya cetakan berstatus draf yang boleh diubah.")
        revisi_baru, kini = revisi_diharapkan + 1, _utc_iso()
        kon.execute(
            "UPDATE cetakan SET kelas = ?, bab = ?, isi_json = ?, revisi = ?, diperbarui = ? WHERE id = ?",
            (cetakan.kelas, cetakan.bab, isi_json, revisi_baru, kini, id_cetakan))
        _catat_audit(kon, id_cetakan, "ubah", baris["isi_json"], isi_json, revisi_baru, actor_id, kini)
        return _ambil_segar(kon, id_cetakan)

    return _jalankan_tulis(path, aksi, boleh_membuat=False)


_AKSI_AUDIT = {"disetujui": "setujui", "dinonaktifkan": "nonaktifkan", "diaktifkan kembali": "aktifkan"}


def _pindah_status(id_cetakan, dari, ke, nama_aksi, *, actor_id, revisi_diharapkan, path,
                   wajib_layak: bool) -> ItemCetakan:
    """Transisi status dalam satu transaksi; `wajib_layak` menjalankan uji kelayakan atas isi tersimpan."""
    _periksa_id(id_cetakan)
    _periksa_pelaku(actor_id)
    _periksa_revisi(revisi_diharapkan)

    def aksi(kon):
        baris = _baris_dalam_transaksi(kon, id_cetakan, revisi_diharapkan)
        if baris["status"] != dari:
            raise ValueError(f"Hanya cetakan berstatus {dari} yang boleh {nama_aksi}.")
        item = _item_wajib(baris)
        if wajib_layak:
            hasil = cetakan_pola.uji_kelayakan(item.cetakan)
            if not hasil.lolos:
                raise ValueError("Uji kelayakan gagal: " + "; ".join(hasil.alasan) + ".")
        revisi_baru, kini = revisi_diharapkan + 1, _utc_iso()
        kon.execute("UPDATE cetakan SET status = ?, revisi = ?, diperbarui = ? WHERE id = ?",
                    (ke, revisi_baru, kini, id_cetakan))
        _catat_audit(kon, id_cetakan, _AKSI_AUDIT[nama_aksi], dari, ke, revisi_baru, actor_id, kini)
        return _ambil_segar(kon, id_cetakan)

    return _jalankan_tulis(path, aksi, boleh_membuat=False)


def setujui(id_cetakan, *, actor_id, revisi_diharapkan, path=None) -> ItemCetakan:
    """draf -> aktif. WAJIB lolos `uji_kelayakan` atas isi tersimpan, di dalam transaksi yang sama."""
    return _pindah_status(id_cetakan, STATUS_DRAF, STATUS_AKTIF, "disetujui", actor_id=actor_id,
                          revisi_diharapkan=revisi_diharapkan, path=path, wajib_layak=True)


def nonaktifkan(id_cetakan, *, actor_id, revisi_diharapkan, path=None) -> ItemCetakan:
    """aktif -> nonaktif (cetakan hilang dari pemakaian; riwayat tetap)."""
    return _pindah_status(id_cetakan, STATUS_AKTIF, STATUS_NONAKTIF, "dinonaktifkan", actor_id=actor_id,
                          revisi_diharapkan=revisi_diharapkan, path=path, wajib_layak=False)


def aktifkan_kembali(id_cetakan, *, actor_id, revisi_diharapkan, path=None) -> ItemCetakan:
    """nonaktif -> aktif, dengan uji kelayakan lagi."""
    return _pindah_status(id_cetakan, STATUS_NONAKTIF, STATUS_AKTIF, "diaktifkan kembali", actor_id=actor_id,
                          revisi_diharapkan=revisi_diharapkan, path=path, wajib_layak=True)

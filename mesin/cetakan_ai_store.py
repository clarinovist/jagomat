"""Kuota harian + audit permintaan draf AI cetakan (C3): DB SQLite terpisah (`cetakan_ai.db`, skema v1).

Terpisah dari `cetakan.db` (isi cetakan) dan dari ledger /admin/ai (`ai_store`): kuota ini hanya milik draf
cetakan dan tetap berlaku walau fitur AI lama dihentikan. Meniru `cetakan_store`: baca `mode=ro` tanpa
membuat berkas, tulis dalam satu transaksi `BEGIN IMMEDIATE` setelah cek skema baca-saja dan `jurnal_wal.aktifkan`,
DB berskema asing ditolak, berkas 0o600.

Kuota = `BATAS_HARIAN` permintaan per hari WIB, global (semua admin). `reservasi` menghitung baris hari ini dan
menyisipkan baris 'berjalan' dalam SATU transaksi, jadi dua permintaan serentak tak bisa sama-sama lolos di
batas. Slot tetap terpakai walau AI gagal (biaya sudah mungkin terjadi). `hasil_json` hanya memuat id draf yang
dibuat dan alasan penolakan yang dipotong; tak pernah isi mentah balasan AI.

FAIL-CLOSED: DB tak terbaca/rusak/berskema asing -> `reservasi` melempar `GalatKuota` (permintaan ditolak tanpa
memanggil AI) dan `sisa_hari_ini` mengembalikan None (tombol disembunyikan). Hanya stdlib + `jurnal_wal`.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Optional, Sequence, Tuple

import jurnal_wal

BERKAS_BAWAAN = "/data/cetakan_ai.db"
ENV_BERKAS_DB = "CETAKAN_AI_BERKAS_DB"
VERSI_SKEMA = 1
BATAS_HARIAN = 20
MAKS_PELAKU = 100
MAKS_ALASAN = 3
MAKS_PANJANG_ALASAN = 200
MAKS_DRAF = 3
WIB = timezone(timedelta(hours=7))

STATUS_BERJALAN = "berjalan"
STATUS_SELESAI = "selesai"
STATUS_GAGAL = "gagal"
STATUS_AKHIR = (STATUS_SELESAI, STATUS_GAGAL)
STATUS_SAH = (STATUS_BERJALAN,) + STATUS_AKHIR
TABEL_SKEMA = ("permintaan",)

_DDL_PERMINTAAN = (
    "CREATE TABLE IF NOT EXISTS permintaan (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    kelas INTEGER NOT NULL CHECK (kelas BETWEEN 1 AND 6),\n"
    "    bab INTEGER NOT NULL CHECK (bab >= 1),\n"
    "    actor_id TEXT NOT NULL,\n"
    "    dibuat TEXT NOT NULL,\n"
    "    hari_wib TEXT NOT NULL,\n"
    "    status TEXT NOT NULL CHECK (status IN ('berjalan', 'selesai', 'gagal')),\n"
    "    jumlah_draf INTEGER NOT NULL DEFAULT 0 CHECK (jumlah_draf >= 0),\n"
    "    hasil_json TEXT NOT NULL DEFAULT '{}'\n"
    ")"
)
_DDL_INDEKS = "CREATE INDEX IF NOT EXISTS idx_permintaan_hari ON permintaan(hari_wib)"

_log = logging.getLogger(__name__)


class KuotaHabis(Exception):
    """Kuota harian sudah terpakai semua."""


class GalatKuota(Exception):
    """DB kuota tak dapat dibaca/ditulis atau skemanya asing; pemanggil menolak permintaan (fail-closed)."""


@dataclass(frozen=True)
class Permintaan:
    """Satu permintaan draf AI tersimpan; `draf` = id cetakan yang dibuat, `ditolak` = alasan (sudah dipotong)."""

    id: int
    kelas: int
    bab: int
    actor_id: str
    dibuat: str
    hari_wib: str
    status: str
    jumlah_draf: int
    draf: Tuple[int, ...]
    ditolak: Tuple[str, ...]


# --- bantu -------------------------------------------------------------------

def _path_db(path) -> Path:
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_BERKAS_DB, BERKAS_BAWAAN))


def _waktu(sekarang: Optional[datetime]) -> datetime:
    kini = sekarang if sekarang is not None else datetime.now(timezone.utc)
    if kini.tzinfo is None:
        raise ValueError("Waktu harus berzona.")
    return kini


def hari_wib(sekarang: Optional[datetime] = None) -> str:
    """Tanggal WIB (YYYY-MM-DD) dari waktu berzona; 23.30 UTC sudah hari berikutnya di WIB."""
    return _waktu(sekarang).astimezone(WIB).date().isoformat()


def _periksa_pelaku(actor_id) -> None:
    if (not isinstance(actor_id, str) or not actor_id.strip()
            or len(actor_id) > MAKS_PELAKU):
        raise ValueError("Identitas pelaku permintaan tidak sah.")


def _ringkas_hasil(draf: Sequence[int], ditolak: Sequence[str]) -> Tuple[Tuple[int, ...], Tuple[str, ...]]:
    """Id draf (int positif, maks MAKS_DRAF) dan alasan (str dipotong, maks MAKS_ALASAN)."""
    if any(type(i) is not int or i < 1 for i in draf):
        raise ValueError("Id draf harus bilangan bulat positif.")
    alasan = tuple(str(a)[:MAKS_PANJANG_ALASAN] for a in ditolak)
    return tuple(draf)[:MAKS_DRAF], alasan[:MAKS_ALASAN]


def _periksa_skema_baca(tujuan: Path) -> None:
    """Tolak DB asing/versi tak dikenal SEBELUM WAL menyentuh header berkas."""
    with closing(sqlite3.connect(f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
        if versi not in (0, VERSI_SKEMA):
            raise GalatKuota("Skema DB kuota tidak dikenali.")
        if versi == 0 and kon.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None:
            raise GalatKuota("DB kuota bukan milik aplikasi ini.")


def _periksa_skema_tulis(kon) -> None:
    versi = kon.execute("PRAGMA user_version").fetchone()[0]
    if versi not in (0, VERSI_SKEMA):
        raise GalatKuota("Skema DB kuota tidak dikenali.")
    if versi == 0 and kon.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None:
        raise GalatKuota("DB kuota bukan milik aplikasi ini.")
    kon.execute(_DDL_PERMINTAAN)
    kon.execute(_DDL_INDEKS)
    if versi == 0:
        kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _buat_berkas_privat(tujuan: Path) -> None:
    os.close(os.open(str(tujuan), os.O_CREAT | os.O_RDWR, 0o600))


def _jalankan_tulis(path, aksi, *, boleh_membuat: bool):
    """Satu transaksi BEGIN IMMEDIATE: cek skema, jalankan aksi(kon), commit. Galat DB = GalatKuota."""
    tujuan = _path_db(path)
    try:
        if not tujuan.exists():
            if not boleh_membuat:
                raise GalatKuota("DB kuota belum ada.")
            _buat_berkas_privat(tujuan)
        _periksa_skema_baca(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=5.0)) as kon, kon:
            kon.row_factory = sqlite3.Row
            jurnal_wal.aktifkan(kon)
            kon.execute("BEGIN IMMEDIATE")
            _periksa_skema_tulis(kon)
            hasil = aksi(kon)
    except (sqlite3.Error, OSError) as err:
        _log.warning("DB kuota draf AI tak dapat diubah (%s).", type(err).__name__)
        raise GalatKuota("DB kuota tidak dapat diubah.") from err
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass
    return hasil


def _terpakai(kon, hari: str) -> int:
    return kon.execute("SELECT COUNT(*) FROM permintaan WHERE hari_wib = ?", (hari,)).fetchone()[0]


# --- API ---------------------------------------------------------------------

def reservasi(kelas: int, bab: int, actor_id: str, *, sekarang: Optional[datetime] = None, path=None) -> int:
    """Pakai satu slot kuota hari ini dan kembalikan id permintaan ('berjalan').

    Hitung + sisip dalam satu transaksi. Penuh = `KuotaHabis`; DB bermasalah = `GalatKuota`.
    """
    _periksa_pelaku(actor_id)
    kini = _waktu(sekarang)
    hari = hari_wib(kini)

    def aksi(kon):
        if _terpakai(kon, hari) >= BATAS_HARIAN:
            raise KuotaHabis("Kuota draf AI hari ini habis.")
        return kon.execute(
            "INSERT INTO permintaan(kelas, bab, actor_id, dibuat, hari_wib, status) VALUES (?, ?, ?, ?, ?, ?)",
            (kelas, bab, actor_id, kini.astimezone(timezone.utc).isoformat(), hari, STATUS_BERJALAN)).lastrowid

    return _jalankan_tulis(path, aksi, boleh_membuat=True)


def selesaikan(id_permintaan: int, status: str, jumlah_draf: int, *, draf: Sequence[int] = (),
               ditolak: Sequence[str] = (), path=None) -> None:
    """Tutup permintaan 'berjalan' sebagai selesai/gagal dan catat hasil ringkas. Salah status/id = ValueError."""
    if status not in STATUS_AKHIR:
        raise ValueError("Status akhir harus selesai atau gagal.")
    if type(jumlah_draf) is not int or jumlah_draf < 0:
        raise ValueError("Jumlah draf tidak sah.")
    ringkas_draf, alasan = _ringkas_hasil(draf, ditolak)
    hasil_json = json.dumps({"draf": list(ringkas_draf), "ditolak": list(alasan)}, ensure_ascii=False)

    def aksi(kon):
        diubah = kon.execute(
            "UPDATE permintaan SET status = ?, jumlah_draf = ?, hasil_json = ? WHERE id = ? AND status = ?",
            (status, jumlah_draf, hasil_json, id_permintaan, STATUS_BERJALAN)).rowcount
        if diubah != 1:
            raise ValueError("Permintaan tidak ditemukan atau sudah ditutup.")

    _jalankan_tulis(path, aksi, boleh_membuat=False)


def _hasil_dari_json(teks) -> Tuple[Tuple[int, ...], Tuple[str, ...]]:
    """(id draf, alasan) dari `hasil_json`; bentuk rusak = kosong (ditampilkan sebagai tanpa rincian)."""
    try:
        data = json.loads(teks)
        draf, ditolak = data["draf"], data["ditolak"]
        if not isinstance(draf, list) or not isinstance(ditolak, list):
            raise ValueError("bentuk hasil tak sah")
        return _ringkas_hasil(draf, ditolak)
    except (ValueError, KeyError, TypeError):
        return (), ()


def _permintaan_dari_baris(baris) -> Optional[Permintaan]:
    if (type(baris["id"]) is not int or baris["status"] not in STATUS_SAH or type(baris["jumlah_draf"]) is not int
            or any(not isinstance(baris[k], str) for k in ("actor_id", "dibuat", "hari_wib"))):
        _log.warning("Baris permintaan draf AI rusak, dilewati.")
        return None
    draf, ditolak = _hasil_dari_json(baris["hasil_json"])
    return Permintaan(baris["id"], baris["kelas"], baris["bab"], baris["actor_id"], baris["dibuat"],
                      baris["hari_wib"], baris["status"], baris["jumlah_draf"], draf, ditolak)


def _baca(path, fungsi):
    """Jalankan `fungsi(kon)` di koneksi baca-saja; berkas hilang/kosong -> None; DB bermasalah = GalatKuota."""
    tujuan = _path_db(path)
    try:
        if not tujuan.exists():
            return None
        with closing(sqlite3.connect(f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
            kon.row_factory = sqlite3.Row
            versi = kon.execute("PRAGMA user_version").fetchone()[0]
            if versi == 0 and kon.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is None:
                return None  # berkas kosong (dibuat tetapi belum diberi skema) = belum ada pemakaian
            if versi != VERSI_SKEMA:
                raise GalatKuota("Skema DB kuota tidak dikenali.")
            return fungsi(kon)
    except (sqlite3.Error, OSError) as err:
        _log.warning("DB kuota draf AI tak terbaca (%s).", type(err).__name__)
        raise GalatKuota("DB kuota tidak terbaca.") from err


def sisa_hari_ini(*, sekarang: Optional[datetime] = None, path=None) -> Optional[int]:
    """Sisa kuota hari ini (0..BATAS_HARIAN), atau None bila DB tak terbaca/rusak (fail-closed: sembunyikan tombol).

    Berkas belum ada = belum ada pemakaian = BATAS_HARIAN. Tidak pernah membuat berkas."""
    hari = hari_wib(sekarang)
    try:
        terpakai = _baca(path, lambda kon: _terpakai(kon, hari))
    except GalatKuota:
        return None
    return BATAS_HARIAN - min(terpakai or 0, BATAS_HARIAN)


def ambil(id_permintaan, *, path=None) -> Optional[Permintaan]:
    """Satu permintaan menurut id, atau None bila tidak ada/rusak/DB tak terbaca."""
    if type(id_permintaan) is not int or id_permintaan < 1:
        return None
    try:
        baris = _baca(path, lambda kon: kon.execute(
            "SELECT id, kelas, bab, actor_id, dibuat, hari_wib, status, jumlah_draf, hasil_json "
            "FROM permintaan WHERE id = ?", (id_permintaan,)).fetchone())
    except GalatKuota:
        return None
    return None if baris is None else _permintaan_dari_baris(baris)

"""Sakelar fitur terpusat: DB SQLite terpisah, env hanya fallback.

Sakelar (NAMA_SAKELAR) disimpan di DB terpisah (skema v1) yang hanya
dibuat saat ubah(): membaca tidak pernah membuat berkas. Nama di luar
daftar adalah kesalahan programmer (ValueError), bukan konfigurasi. Baca
mengikuti urutan fail-closed: berkas DB tidak ada atau baris belum di-seed
-> env_fallback() lama (dievaluasi segar, tanpa cache); DB rusak, skema/
user_version salah, atau nilai baris hantu -> False tanpa menyentuh env.
Hasil DB dicache pendek (TTL_DETIK detik) per (path absolut, nama) dan
dikosongkan bersihkan_cache() setelah tiap ubah() berhasil.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Callable

import jurnal_wal

NAMA_SAKELAR = (
    "FUNNEL_AKTIF",
    "PESANAN_TRANSFER_AKTIF",
    "OSN_CETAK_RINGKAS",
    "OSN_BANK_KALIMAT",
    "OSN_LOMBA",
    "DAFTAR_AKUN_ANAK",
)

BERKAS_BAWAAN = "/data/sakelar.db"
ENV_BERKAS_DB = "SAKELAR_BERKAS_DB"
VERSI_SKEMA = 1
TTL_DETIK = 5

_DAFTAR_NAMA_SQL = ",".join("'" + nama + "'" for nama in NAMA_SAKELAR)


def _ddl_sakelar(nama_tabel: str, *, jika_belum_ada: bool) -> str:
    """DDL tabel sakelar dengan daftar nama sekarang (CHECK); dipakai membuat dan memperlebar tabel."""
    awalan = "CREATE TABLE IF NOT EXISTS" if jika_belum_ada else "CREATE TABLE"
    return (
        f"{awalan} {nama_tabel} (\n"
        f"    nama TEXT PRIMARY KEY CHECK (nama IN ({_DAFTAR_NAMA_SQL})),\n"
        "    aktif INTEGER NOT NULL CHECK (aktif IN (0, 1)),\n"
        "    revisi INTEGER NOT NULL CHECK (revisi >= 1),\n"
        "    diperbarui TEXT NOT NULL\n"
        ")"
    )


_DDL_SAKELAR = _ddl_sakelar("sakelar", jika_belum_ada=True)
_DDL_AUDIT = (
    "CREATE TABLE IF NOT EXISTS audit_sakelar (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    nama TEXT NOT NULL,\n"
    "    lama INTEGER,\n"
    "    baru INTEGER NOT NULL,\n"
    "    revisi INTEGER NOT NULL,\n"
    "    actor_id TEXT NOT NULL,\n"
    "    dibuat TEXT NOT NULL\n"
    ")"
)

# Jam disuntik lewat variabel modul agar tes bisa memalsukan TTL cache.
_jam = time.monotonic
_kunci_cache = threading.Lock()
_cache = {}
_BARIS_HILANG = object()  # sentinel: DB sehat tapi baris nama belum di-seed


class KonflikRevisi(Exception):
    """revisi_diharapkan tidak cocok dengan revisi baris sekarang."""


class GalatSakelar(Exception):
    """DB sakelar rusak atau skemanya tak dikenali; jangan ditelan admin."""


@dataclass(frozen=True)
class Sakelar:
    """Kondisi satu sakelar; sumber "db" (baris DB) atau "env" (fallback)."""

    nama: str
    aktif: bool
    revisi: int
    sumber: str


def bersihkan_cache() -> None:
    """Kosongkan cache hasil baca; dipanggil ubah() setelah commit."""
    with _kunci_cache:
        _cache.clear()


def _path_db(path):
    """Tujuan DB: parameter, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_BERKAS_DB, BERKAS_BAWAAN))


def _validasi_seed(seed):
    """Pastikan seed memetakan tepat semua nama sakelar ke bool."""
    if not isinstance(seed, Mapping):
        raise ValueError("Seed sakelar harus berupa pemetaan nama ke bool.")
    nilai = dict(seed)
    if set(nilai) != set(NAMA_SAKELAR):
        raise ValueError(
            "Seed sakelar harus memuat tepat semua nama: "
            + ", ".join(NAMA_SAKELAR)
        )
    for nama in NAMA_SAKELAR:
        if not isinstance(nilai[nama], bool):
            raise ValueError(f"Nilai seed sakelar {nama} harus bool.")
    return nilai


def _utc_iso() -> str:
    """Stempel waktu UTC ISO untuk kolom TEXT diperbarui/dibuat."""
    return datetime.now(timezone.utc).isoformat()


def _buat_skema(kon):
    """Buat kedua tabel bila belum ada; bagian dari transaksi ubah()."""
    kon.execute(_DDL_SAKELAR)
    kon.execute(_DDL_AUDIT)


def _perlu_perluasan(kon) -> bool:
    """True bila tabel sakelar punya CHECK nama yang belum memuat semua NAMA_SAKELAR (DB lama).

    Tabel tanpa CHECK nama (buatan tangan) tidak disentuh: tidak ada yang perlu diperlebar.
    """
    baris = kon.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'sakelar'").fetchone()
    if baris is None or "nama IN (" not in baris[0]:
        return False
    return any(f"'{nama}'" not in baris[0] for nama in NAMA_SAKELAR)


def _perluas_nama(kon):
    """Bangun ulang tabel sakelar dengan CHECK nama terbaru, menyalin semua baris apa adanya.

    SQLite tidak bisa mengubah CHECK di tempat. Versi skema TIDAK dinaikkan: daftar nama hanya
    diperlebar (nama lama tetap sah), sehingga kode lama masih membaca dan menulis DB ini.
    Dipanggil di dalam transaksi ubah(): gagal di mana pun, semuanya digulung balik.
    """
    kon.execute(_ddl_sakelar("sakelar_baru", jika_belum_ada=False))
    # Salin apa adanya, termasuk baris rusak yang sengaja dipulihkan lewat ubah(); penegakan CHECK
    # dikembalikan segera setelah menyalin.
    kon.execute("PRAGMA ignore_check_constraints = ON")
    try:
        kon.execute(
            "INSERT INTO sakelar_baru(nama, aktif, revisi, diperbarui) "
            "SELECT nama, aktif, revisi, diperbarui FROM sakelar")
    finally:
        kon.execute("PRAGMA ignore_check_constraints = OFF")
    kon.execute("DROP TABLE sakelar")
    kon.execute("ALTER TABLE sakelar_baru RENAME TO sakelar")


def _baca_baris(tujuan, nama):
    """Baca satu baris read-only. _BARIS_HILANG bila baris tak ada.

    Kegagalan apa pun (berkas rusak, bukan sqlite, user_version salah,
    tabel hilang) mengembalikan False agar fitur mati, bukan ke env lama.
    """
    try:
        with closing(sqlite3.connect(
                f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
            kon.row_factory = sqlite3.Row
            if kon.execute("PRAGMA user_version").fetchone()[0] != VERSI_SKEMA:
                return False
            baris = kon.execute(
                "SELECT aktif FROM sakelar WHERE nama = ?", (nama,)
            ).fetchone()
    except sqlite3.Error:
        return False
    if baris is None:
        return _BARIS_HILANG
    nilai = baris["aktif"]
    return bool(nilai) if nilai in (0, 1) else False


def aktif(nama: str, env_fallback: Callable[[], bool], *, path=None) -> bool:
    """Status satu sakelar: baris DB menang, env hanya fallback.

    Urutan: nama tak dikenal -> ValueError; berkas DB tidak ada atau baris
    belum di-seed -> env_fallback() segar; DB rusak/skema salah -> False
    tanpa menyentuh env; baris ada -> bool(aktif). Hasil DB dicache pendek,
    jalur env tidak pernah dicache.
    """
    if nama not in NAMA_SAKELAR:
        raise ValueError(f"Nama sakelar tidak dikenal: {nama!r}")
    tujuan = _path_db(path)
    kunci = (os.path.abspath(str(tujuan)), nama)
    with _kunci_cache:
        entri = _cache.get(kunci)
    if entri is not None and _jam() - entri[1] < TTL_DETIK:
        return entri[0]
    if not tujuan.exists():
        return env_fallback()
    hasil = _baca_baris(tujuan, nama)
    if hasil is _BARIS_HILANG:
        return env_fallback()
    with _kunci_cache:
        _cache[kunci] = (hasil, _jam())
    return hasil


def daftar(*, seed, path=None) -> "tuple[Sakelar, ...]":
    """Semua sakelar urut NAMA_SAKELAR untuk halaman admin.

    DB/baris belum ada -> nilai seed, revisi 0, sumber "env"; baris ada ->
    dari DB, sumber "db". Kegagalan baca tidak ditelan: GalatSakelar agar
    admin melihat galat jujur, bukan daftar palsu.
    """
    nilai_seed = _validasi_seed(seed)
    tujuan = _path_db(path)
    if not tujuan.exists():
        return tuple(
            Sakelar(nama, nilai_seed[nama], 0, "env") for nama in NAMA_SAKELAR
        )
    try:
        with closing(sqlite3.connect(
                f"file:{tujuan}?mode=ro", uri=True, timeout=2.0)) as kon:
            kon.row_factory = sqlite3.Row
            if kon.execute("PRAGMA user_version").fetchone()[0] != VERSI_SKEMA:
                raise GalatSakelar("Skema DB sakelar tidak dikenali.")
            baris = {
                b["nama"]: b
                for b in kon.execute("SELECT nama, aktif, revisi FROM sakelar")
            }
    except sqlite3.Error as err:
        raise GalatSakelar("DB sakelar tidak dapat dibaca.") from err
    hasil = []
    for nama in NAMA_SAKELAR:
        baris_nama = baris.get(nama)
        if baris_nama is None:
            hasil.append(Sakelar(nama, nilai_seed[nama], 0, "env"))
        else:
            nilai = baris_nama["aktif"]
            # Nilai hantu hasil tangan tampil mati, konsisten dengan aktif().
            kondisi = bool(nilai) if nilai in (0, 1) else False
            hasil.append(Sakelar(nama, kondisi, int(baris_nama["revisi"]), "db"))
    return tuple(hasil)


def ubah(nama: str, aktif: bool, *, actor_id: str, revisi_diharapkan: int,
         seed, path=None) -> Sakelar:
    """Ubah satu sakelar dalam satu transaksi: seed, cek revisi, audit.

    Konflik revisi digulung balik penuh termasuk seed baru. Nilai sama ->
    no-op tanpa revisi/audit baru. Setelah commit cache dibersihkan dan
    izin berkas dipatok 0o600.
    """
    if nama not in NAMA_SAKELAR:
        raise ValueError(f"Nama sakelar tidak dikenal: {nama!r}")
    if not isinstance(aktif, bool):
        raise ValueError("Nilai aktif sakelar harus bool.")
    if (not isinstance(actor_id, str) or not actor_id.strip()
            or len(actor_id) > 100):
        raise ValueError("Identitas pelaku ubah sakelar tidak sah.")
    nilai_seed = _validasi_seed(seed)
    tujuan = _path_db(path)
    try:
        with closing(sqlite3.connect(str(tujuan), timeout=5.0)) as kon, kon:
            kon.row_factory = sqlite3.Row
            jurnal_wal.aktifkan(kon)
            kon.execute("BEGIN IMMEDIATE")
            versi = kon.execute("PRAGMA user_version").fetchone()[0]
            if versi not in (0, VERSI_SKEMA):
                raise GalatSakelar("Skema DB sakelar tidak dikenali.")
            _buat_skema(kon)
            if _perlu_perluasan(kon):
                _perluas_nama(kon)
            if versi == 0:
                kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")
            for nama_seed in NAMA_SAKELAR:
                if kon.execute(
                    "SELECT 1 FROM sakelar WHERE nama = ?", (nama_seed,)
                ).fetchone() is None:
                    kon.execute(
                        "INSERT INTO sakelar(nama, aktif, revisi, diperbarui)"
                        " VALUES (?, ?, 1, ?)",
                        (nama_seed, int(nilai_seed[nama_seed]), _utc_iso()),
                    )
            baris = kon.execute(
                "SELECT aktif, revisi FROM sakelar WHERE nama = ?", (nama,)
            ).fetchone()
            try:
                revisi_kini = int(baris["revisi"])
            except (TypeError, ValueError) as err:
                raise GalatSakelar(
                    "Baris sakelar rusak: revisi tidak terbaca.") from err
            try:
                nilai_kini = int(baris["aktif"])
            except (TypeError, ValueError):
                nilai_kini = None  # baris hantu: paksakan cabang ubah agar pulih
            if revisi_kini != revisi_diharapkan:
                raise KonflikRevisi(
                    f"Revisi sakelar {nama} berubah: diharapkan"
                    f" {revisi_diharapkan}, sekarang {revisi_kini}."
                )
            if nilai_kini == int(aktif):
                hasil = Sakelar(nama, aktif, revisi_kini, "db")
            else:
                revisi_baru = revisi_kini + 1
                kini = _utc_iso()
                kon.execute(
                    "UPDATE sakelar SET aktif = ?, revisi = ?, diperbarui = ?"
                    " WHERE nama = ?",
                    (int(aktif), revisi_baru, kini, nama),
                )
                kon.execute(
                    "INSERT INTO audit_sakelar(nama, lama, baru, revisi,"
                    " actor_id, dibuat) VALUES (?, ?, ?, ?, ?, ?)",
                    (nama, nilai_kini, int(aktif), revisi_baru, actor_id, kini),
                )
                hasil = Sakelar(nama, aktif, revisi_baru, "db")
    except sqlite3.Error as err:
        raise GalatSakelar("DB sakelar tidak dapat diubah.") from err
    bersihkan_cache()
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass
    return hasil

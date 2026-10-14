"""Bundle backup privat untuk database riset konsumen.

Database riset sengaja tidak ikut bundle kampanye: ia punya retensi sendiri
(90 hari, lihat ``research_store.RETENSI_HARI``), berisi ucapan responden, dan
lokasi serta masa simpannya harus dapat dijalankan tanpa memaksa backup produk
belajar diperpanjang. Helper ini hanya bekerja pada salinan yang sudah dibuat
oleh caller di bawah write-hold; ia tidak menyentuh database live.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
from typing import Mapping, Optional

NAMA_DB = "riset-konsumen.db"
NAMA_MANIFEST = "manifest.json"
VERSI_MANIFEST = 1
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class BackupRisetTidakSah(RuntimeError):
    """Bundle riset hilang, rusak, atau tidak memenuhi kontrak privat."""


def _privat(path: Path, *, direktori: bool = False) -> None:
    try:
        info = path.lstat()
    except OSError as galat:
        raise BackupRisetTidakSah("artefak backup riset tidak tersedia") from galat
    sah = stat.S_ISDIR(info.st_mode) if direktori else stat.S_ISREG(info.st_mode)
    batas = 0o700 if direktori else 0o600
    if not sah or stat.S_IMODE(info.st_mode) & ~batas:
        raise BackupRisetTidakSah("izin artefak backup riset terlalu longgar")


def _sha256(path: Path) -> str:
    sidik = hashlib.sha256()
    with path.open("rb") as sumber:
        for blok in iter(lambda: sumber.read(1024 * 1024), b""):
            sidik.update(blok)
    return sidik.hexdigest()


def salin(sumber, tujuan) -> Path:
    """Salin DB riset memakai SQLite backup API; membaca sumber read-only."""
    sumber = Path(sumber)
    tujuan = Path(tujuan)
    sasaran = tujuan / NAMA_DB
    if sasaran.exists():
        raise BackupRisetTidakSah("tujuan backup riset harus kosong")
    asal = sqlite3.connect(sumber.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    keluaran = sqlite3.connect(str(sasaran))
    try:
        asal.backup(keluaran)
        keluaran.commit()
    except sqlite3.Error as galat:
        sasaran.unlink(missing_ok=True)
        raise BackupRisetTidakSah("salinan backup riset gagal") from galat
    finally:
        keluaran.close()
        asal.close()
    for akhiran in ("-wal", "-shm"):
        (sasaran.with_name(sasaran.name + akhiran)).unlink(missing_ok=True)
    sasaran.chmod(0o600)
    return sasaran


def buat_manifest(bundle, *, bundle_id: str, cutoff: int) -> Path:
    if type(bundle_id) is not str or _ID.fullmatch(bundle_id) is None:
        raise BackupRisetTidakSah("bundle ID riset tidak sah")
    if type(cutoff) is not int or cutoff < 0:
        raise BackupRisetTidakSah("cutoff riset tidak sah")
    akar = Path(bundle)
    _privat(akar, direktori=True)
    if {path.name for path in akar.iterdir()} != {NAMA_DB}:
        raise BackupRisetTidakSah("inventaris backup riset tidak tepat")
    db = akar / NAMA_DB
    _privat(db)
    manifest = {
        "versi": VERSI_MANIFEST, "bundle_id": bundle_id, "cutoff": cutoff,
        "berkas": {"nama": NAMA_DB, "sha256": _sha256(db), "ukuran": db.stat().st_size},
    }
    sementara = akar / (".%s.%s.tmp" % (NAMA_MANIFEST, secrets.token_hex(8)))
    try:
        fd = os.open(str(sementara), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as tujuan:
            json.dump(manifest, tujuan, sort_keys=True, separators=(",", ":"))
            tujuan.write("\n")
            tujuan.flush()
            os.fsync(tujuan.fileno())
        os.replace(str(sementara), str(akar / NAMA_MANIFEST))
        (akar / NAMA_MANIFEST).chmod(0o600)
    finally:
        sementara.unlink(missing_ok=True)
    return akar / NAMA_MANIFEST


def validasi(bundle, *, bundle_id: Optional[str] = None) -> Mapping:
    """Validasi hash, ukuran, schema, integrity, dan FK tanpa memperbaiki."""
    akar = Path(bundle)
    _privat(akar, direktori=True)
    if {path.name for path in akar.iterdir()} != {NAMA_DB, NAMA_MANIFEST}:
        raise BackupRisetTidakSah("inventaris backup riset tidak tepat")
    manifest_path = akar / NAMA_MANIFEST
    db = akar / NAMA_DB
    _privat(manifest_path)
    _privat(db)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raise BackupRisetTidakSah("manifest backup riset tidak sah") from None
    if (not isinstance(manifest, dict)
            or set(manifest) != {"versi", "bundle_id", "cutoff", "berkas"}
            or manifest["versi"] != VERSI_MANIFEST
            or type(manifest["bundle_id"]) is not str
            or _ID.fullmatch(manifest["bundle_id"]) is None
            or (bundle_id is not None and manifest["bundle_id"] != bundle_id)
            or type(manifest["cutoff"]) is not int or manifest["cutoff"] < 0
            or not isinstance(manifest["berkas"], dict)
            or set(manifest["berkas"]) != {"nama", "sha256", "ukuran"}):
        raise BackupRisetTidakSah("manifest backup riset tidak sah")
    info = manifest["berkas"]
    if (info["nama"] != NAMA_DB or type(info["ukuran"]) is not int or info["ukuran"] <= 0
            or not isinstance(info["sha256"], str) or _HASH.fullmatch(info["sha256"]) is None):
        raise BackupRisetTidakSah("metadata berkas backup riset tidak sah")
    if db.stat().st_size != info["ukuran"] or _sha256(db) != info["sha256"]:
        raise BackupRisetTidakSah("hash/ukuran backup riset tidak cocok")
    import research_store
    try:
        with research_store.buka_baca(db) as kon:
            if kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupRisetTidakSah("integritas backup riset gagal")
            if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise BackupRisetTidakSah("foreign key backup riset gagal")
            wawancara = int(kon.execute("SELECT COUNT(*) FROM wawancara_riset").fetchone()[0])
    except (RuntimeError, ValueError, sqlite3.Error):
        raise BackupRisetTidakSah("schema backup riset tidak lengkap") from None
    return {
        "bundle_id": manifest["bundle_id"], "cutoff": manifest["cutoff"],
        "wawancara": wawancara,
    }

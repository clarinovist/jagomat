#!/usr/bin/env python3
"""Backup harian online Jagomat, tanpa menghentikan aplikasi.

Menyalin setiap DB SQLite memakai backup API (konsisten per berkas), lalu
menormalkan salinan ke `journal_mode=DELETE` dan membuang sidecar `-wal/-shm`.
Salinan tidak koheren lintas DB, jadi manifest menandai `needs_reconciliation`.

Lampiran/foto dan bukti transfer sengaja tidak disalin:
- lampiran ikut bundle rilis (operational_backup);
- bukti transfer keputusan Pemilik: sementara 30 hari, tidak di-backup.

Dijalankan di host VPS oleh cron; tidak butuh impor kode aplikasi.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import sys

VERSI = 1
WAJIB = ("latihan.db", "admin-control.db", "ai-control.db", "pendamping.db", "riset-konsumen.db")
OPSIONAL = ("sakelar.db", "kurikulum.db", "cetakan.db", "cetakan_ai.db")
SANDI = "sandi.json"
RETENSI = 14
DIKECUALIKAN = (
    "lampiran/ (ikut bundle rilis)",
    "bukti-transfer/ (keputusan Pemilik: bukti sementara 30 hari)",
)
_POLA_ID = re.compile(r"^\d{8}-\d{6}$")


def _sha256(path: Path) -> str:
    sidik = hashlib.sha256()
    with path.open("rb") as sumber:
        for blok in iter(lambda: sumber.read(1024 * 1024), b""):
            sidik.update(blok)
    return sidik.hexdigest()


def _fsync(path: Path, *, direktori: bool = False) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _salin_db(sumber: Path, tujuan: Path) -> dict:
    asal = sqlite3.connect(sumber.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    keluaran = sqlite3.connect(str(tujuan))
    try:
        asal.backup(keluaran)
        mode = str(keluaran.execute("PRAGMA journal_mode = DELETE").fetchone()[0]).lower()
        if mode != "delete":
            raise RuntimeError(f"{sumber.name}: jurnal salinan bukan DELETE ({mode})")
        if keluaran.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"{sumber.name}: integrity_check gagal")
        versi = int(keluaran.execute("PRAGMA user_version").fetchone()[0])
        keluaran.commit()
    finally:
        keluaran.close()
        asal.close()
    for akhiran in ("-wal", "-shm"):
        tujuan.with_name(tujuan.name + akhiran).unlink(missing_ok=True)
    tujuan.chmod(0o600)
    _fsync(tujuan)
    return {"nama": tujuan.name, "sha256": _sha256(tujuan),
            "ukuran": tujuan.stat().st_size, "user_version": versi}


def _stempel(sekarang: int | None) -> str:
    epoch = dt.datetime.now(dt.timezone.utc).timestamp() if sekarang is None else sekarang
    wib = dt.datetime.fromtimestamp(epoch, dt.timezone(dt.timedelta(hours=7)))
    return wib.strftime("%Y%m%d-%H%M%S")


def _di_dalam(anak: Path, induk: Path) -> bool:
    try:
        anak.resolve().relative_to(induk.resolve())
        return True
    except ValueError:
        return False


def cadangkan(
    data_dir,
    output_dir,
    *,
    wajib=WAJIB,
    opsional=OPSIONAL,
    retensi=RETENSI,
    sekarang: int | None = None,
    host: str | None = None,
) -> Path:
    data = Path(data_dir)
    out = Path(output_dir)
    if not data.is_dir():
        raise FileNotFoundError(f"direktori data tidak ada: {data}")
    if _di_dalam(out, data) or _di_dalam(data, out):
        raise ValueError("direktori backup tidak boleh berada di dalam (atau memuat) data")
    if retensi < 1:
        raise ValueError("retensi minimal 1")

    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    kunci = (out / ".lock").open("a+")
    try:
        try:
            fcntl.flock(kunci.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as galat:
            raise RuntimeError("backup lain masih berjalan") from galat

        for nama in wajib:
            if not (data / nama).is_file():
                raise FileNotFoundError(f"state wajib tidak ada: {nama}")
        if not (data / SANDI).is_file():
            raise FileNotFoundError(f"state wajib tidak ada: {SANDI}")

        ident = _stempel(sekarang)
        akhir = out / ident
        if akhir.exists():
            raise FileExistsError(f"backup {ident} sudah ada")
        sementara = out / f".partial-{ident}-{os.getpid()}"
        sementara.mkdir(mode=0o700)

        berkas = []
        try:
            for nama in (*wajib, *opsional):
                sumber = data / nama
                if sumber.is_file():
                    berkas.append(_salin_db(sumber, sementara / nama))
            sandi = (data / SANDI).read_bytes()
            (sementara / SANDI).write_bytes(sandi)
            (sementara / SANDI).chmod(0o600)
            _fsync(sementara / SANDI)
            berkas.append({"nama": SANDI, "sha256": hashlib.sha256(sandi).hexdigest(),
                           "ukuran": len(sandi), "user_version": None})

            manifest = {
                "versi": VERSI,
                "id": ident,
                "dibuat": dt.datetime.now(dt.timezone.utc).isoformat(),
                "host": host or socket.gethostname(),
                "needs_reconciliation": True,
                "berkas": sorted(berkas, key=lambda item: item["nama"]),
                "dikecualikan": list(DIKECUALIKAN),
            }
            (sementara / "manifest.json").write_text(
                json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            (sementara / "manifest.json").chmod(0o600)
            _fsync(sementara / "manifest.json")
            _fsync(sementara, direktori=True)
            os.replace(sementara, akhir)
        except BaseException:
            shutil.rmtree(sementara, ignore_errors=True)
            raise

        salinan = sorted(
            (p for p in out.iterdir() if p.is_dir() and _POLA_ID.fullmatch(p.name)),
            key=lambda p: p.name, reverse=True)
        for lama in salinan[retensi:]:
            shutil.rmtree(lama, ignore_errors=True)
        return akhir
    finally:
        kunci.close()


def validasi(path) -> dict:
    akar = Path(path)
    manifest_path = akar / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (data.get("versi") != VERSI or _POLA_ID.fullmatch(str(data.get("id", ""))) is None
            or data.get("needs_reconciliation") is not True
            or not isinstance(data.get("berkas"), list)):
        raise ValueError("manifest backup harian tidak sah")
    for item in data["berkas"]:
        if set(item) != {"nama", "sha256", "ukuran", "user_version"}:
            raise ValueError("entri manifest tidak sah")
        berkas = akar / item["nama"]
        if not berkas.is_file() or berkas.stat().st_size != item["ukuran"]:
            raise ValueError(f"berkas backup tidak cocok: {item['nama']}")
        if _sha256(berkas) != item["sha256"]:
            raise ValueError(f"hash backup tidak cocok: {item['nama']}")
        if item["nama"].endswith(".db"):
            with sqlite3.connect(berkas) as kon:
                if kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError(f"integritas gagal: {item['nama']}")
    return data


def _ringkasan(akhir: Path, manifest: dict) -> dict:
    """Satu baris untuk log cron: tanpa nama berkas, isi, atau data anak."""
    berkas = manifest["berkas"]
    return {
        "id": manifest["id"],
        "status": "ok",
        "db": sum(1 for item in berkas if item["nama"].endswith(".db")),
        "berkas": len(berkas),
        "ukuran_total": sum(item["ukuran"] for item in berkas),
        "salinan_tersisa": sum(
            1 for p in akhir.parent.iterdir() if p.is_dir() and _POLA_ID.fullmatch(p.name)),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default="/opt/osn/data")
    p.add_argument("--output-dir", default="/opt/osn/backup-harian")
    p.add_argument("--retensi", type=int, default=RETENSI)
    p.add_argument("--validasi")
    a = p.parse_args(argv)
    if a.validasi:
        print(json.dumps(validasi(a.validasi), sort_keys=True))
        return 0
    hasil = cadangkan(a.data_dir, a.output_dir, retensi=a.retensi)
    manifest = validasi(hasil)
    print(json.dumps(_ringkasan(hasil, manifest), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

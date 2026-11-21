"""Pembantu bersama tes backup off-site: kunci RSA tmp, bundle sintetis, berkas env."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.append(str(SCRIPTS))

import backup_harian  # noqa: E402

PENANDA = "RAHASIA-ANAK-SINTETIS-7f3a9c41"
ENV_ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
ENV_AKSES = "AKIAUNIKSINTETIS99887766"
ENV_RAHASIA = "rahasiaUnikSintetis/Zy9+Xw8vUt7sRq6pOn5mLk4j"
UMUR_JAM = 3600


def buat_pasangan_kunci(direktori: Path, bit: int = 2048):
    """Kunci RSA sementara via openssl; kembalikan (privat, publik)."""
    privat, publik = direktori / "privat.pem", direktori / "publik.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                    f"rsa_keygen_bits:{bit}", "-out", str(privat)],
                   check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(privat), "-pubout", "-out", str(publik)],
                   check=True, capture_output=True)
    privat.chmod(0o600)
    return privat, publik


def buat_bundle(akar: Path, *, umur_jam: float = 1, penanda: str = PENANDA) -> Path:
    """Bundle valid hasil `backup_harian.cadangkan`, berumur `umur_jam` jam."""
    data = akar / "data"
    data.mkdir(mode=0o700, parents=True, exist_ok=True)
    kon = sqlite3.connect(data / "latihan.db")
    kon.execute("CREATE TABLE IF NOT EXISTS t(x TEXT)")
    kon.executemany("INSERT INTO t VALUES (?)", [(f"{penanda}-{i}",) for i in range(300)])
    kon.commit()
    kon.close()
    (data / "sandi.json").write_text('{"akun": ["%s"]}' % penanda, encoding="utf-8")
    epoch = int(time.time() - umur_jam * UMUR_JAM)
    return backup_harian.cadangkan(data, akar / "backup-harian", wajib=("latihan.db",),
                                   opsional=(), sekarang=epoch)


def hash_pohon(akar: Path) -> dict:
    return {str(p.relative_to(akar)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(akar.rglob("*")) if p.is_file()}


def tulis_env(path: Path, *, mode: int = 0o600, isi: dict | None = None) -> Path:
    nilai = {"R2_ACCOUNT_ID": ENV_ID, "R2_ACCESS_KEY_ID": ENV_AKSES,
             "R2_SECRET_ACCESS_KEY": ENV_RAHASIA, "R2_BUCKET": "bucket-uji"}
    nilai.update(isi or {})
    path.write_text("# kredensial uji\n" + "".join(f"{k}={v}\n" for k, v in nilai.items()),
                    encoding="utf-8")
    os.chmod(path, mode)
    return path

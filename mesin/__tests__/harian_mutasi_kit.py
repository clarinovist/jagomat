"""Harness mutation Latihan Harian: jalankan tes terarah pada salinan source terisolasi (hijau -> mutasi merah -> pulih hijau).

Dipakai `test_harian_mutation.py` dan `test_harian_gerbang_mutation.py`. Workspace asli tidak disentuh; merah karena
ImportError/SyntaxError/NameError tidak sah.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

AKAR = Path(__file__).resolve().parents[2]
BATAS_DETIK = 150


def _salin_sumber(tmp_path: Path, berkas_tes) -> Path:
    sumber = tmp_path / "mesin"
    sumber.mkdir()
    for f in (AKAR / "mesin").glob("*.py"):
        shutil.copy2(f, sumber / f.name)
    for nama_tes in berkas_tes:
        shutil.copy2(Path(__file__).with_name(nama_tes), tmp_path / nama_tes)
    if (AKAR / "mesin" / "aset").exists():
        os.symlink(AKAR / "mesin" / "aset", sumber / "aset")
    return sumber


def uji_mutasi(tmp_path: Path, berkas: str, ganti, berkas_tes: str, tes: str, salin_tes) -> None:
    """Pastikan hijau awal, merah setelah `ganti` ([(lama, baru)]) diterapkan, dan hijau lagi setelah dipulihkan."""
    sumber = _salin_sumber(tmp_path, salin_tes)
    target = sumber / berkas
    asli = target.read_text()
    for lama, _baru in ganti:
        assert asli.count(lama) == 1, "anchor mutasi tidak ditemukan tepat satu kali: " + lama
    cmd = [sys.executable, "-B", "-m", "pytest", berkas_tes, "-k", tes, "-q", "-W", "error", "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(sumber), "OSN_PBKDF2_ITERASI": "1000",
           "PYTHONDONTWRITEBYTECODE": "1"}

    def jalankan():
        return subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=BATAS_DETIK)

    hijau_awal = jalankan()
    assert hijau_awal.returncode == 0, hijau_awal.stdout + hijau_awal.stderr
    mutan = asli
    for lama, baru in ganti:
        mutan = mutan.replace(lama, baru)
    target.write_text(mutan)
    merah = jalankan()
    assert merah.returncode == 1 and " failed" in merah.stdout and " error" not in merah.stdout, (
        merah.stdout + merah.stderr)
    assert "ImportError" not in merah.stdout and "SyntaxError" not in merah.stdout and "NameError" not in merah.stdout
    target.write_text(asli)
    hijau = jalankan()
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

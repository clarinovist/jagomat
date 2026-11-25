"""Mutasi guard tunggakan paket kelas pada SALINAN repo terisolasi (bukan workspace, bukan DB nyata).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan `test_kelas_tunggakan.py`: hasil harus MERAH karena
asersi (bukan import/fixture rusak). Kontrol tanpa mutasi harus HIJAU di salinan yang sama. Pola sama dengan
`test_kelas_mutation.py`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AKAR = Path(__file__).resolve().parents[2]
SASARAN = ["mesin/__tests__/test_kelas_tunggakan.py"]
TUNGGAKAN = "mesin/kelas_tunggakan.py"

KASUS = (
    ("batas-hari-min-geser-ke-31",
     ((TUNGGAKAN, "HARI_TUNGGAKAN_MIN = 30\n", "HARI_TUNGGAKAN_MIN = 31\n"),)),
    ("order-terbuka-tidak-menahan-tunggakan",
     ((TUNGGAKAN, '    if _ada_order_terbuka(kon, baris["siswa_id"], baris["paket"], kini):\n',
       "    if False:\n"),)),
    ("akses-terlama-bukan-terakhir",
     ((TUNGGAKAN, "MAX(a.berakhir) AS berakhir", "MIN(a.berakhir) AS berakhir"),)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("tunggakan-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *SASARAN, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=240)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    hasil = _jalankan(salinan)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan", KASUS, ids=[k[0] for k in KASUS])
def test_guard_tunggakan_menangkap_mutasi(salinan, nama, suntingan):
    asli = {}
    try:
        for rel, lama, baru in suntingan:
            berkas = salinan / rel
            sumber = asli.setdefault(rel, berkas.read_text(encoding="utf-8"))
            terkini = berkas.read_text(encoding="utf-8")
            assert terkini.count(lama) == 1, "%s: pola mutasi harus unik di %s" % (nama, rel)
            berkas.write_text(terkini.replace(lama, baru), encoding="utf-8")
            assert sumber != berkas.read_text(encoding="utf-8")
        hasil = _jalankan(salinan)
    finally:
        for rel, sumber in asli.items():
            (salinan / rel).write_text(sumber, encoding="utf-8")
    keluaran = hasil.stdout + hasil.stderr
    assert hasil.returncode == 1, keluaran
    assert re.search(r"\b\d+ failed", keluaran), keluaran
    assert not re.search(r"\b\d+ error", keluaran), keluaran

"""Mutation guard penerbitan otomatis laporan Peta (`peta_otomatis`) pada SALINAN repo terisolasi.

Meniru `test_peta_laporan_guru_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasilnya harus MERAH karena asersi (bukan import atau fixture rusak). Kontrol: tanpa mutasi, tes yang sama
harus HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya (count == 1). Salinan tidak memuat `.venv`,
cadangan, `*.db`, atau `*.json` (tanpa data atau sandi nyata). Tiap kasus = satu param, jadi bisa dijalankan dengan `-k`.
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
T = "mesin/__tests__/test_peta_otomatis.py::"
MODUL = "mesin/peta_otomatis.py"
GUARD_MURNI = T + "test_izin_bila_sah_menolak_bila_satu_guard_gagal"
KASUS = (
    ("1-status-sudah-dibayar-dilepas",
     ((MODUL, '    if order["status"] != d.STATUS_SUDAH_DIBAYAR:\n        return None\n', ""),),
     (GUARD_MURNI,)),
    ("2-direfund-dilepas",
     ((MODUL, ' and purna_ringkas["direfund"] is False', ""),),
     (GUARD_MURNI,)),
    ("3-ditahan-dilepas",
     ((MODUL, ' and purna_ringkas["ditahan"] is False', ""),),
     (GUARD_MURNI,)),
    ("4-akun-tidak-diperiksa",
     ((MODUL, '    if id_akun is not None and order["akun_id"] != id_akun:\n        return None\n', ""),),
     (GUARD_MURNI,)),
    ("5-cek-diambil-dari-siswa",
     ((MODUL, '"cek_id": order["cek_id"],', '"cek_id": order["siswa_id"],'),),
     (T + "test_terbit_sah_menulis_laporan_sistem_dalam_satu_baris",
      T + "test_terbit_memakai_cek_dari_order_bukan_id_anak")),
    ("6-pra-cek-draf-dilepas",
     ((MODUL, '        if toko.ambil(kon, izin["siswa_id"]) is not None:\n            return SUDAH_ADA\n', ""),),
     (T + "test_draf_guru_dengan_bahan_dihapus_tetap_sudah_ada_tanpa_buat_draf",)),
    ("7-transaksi-atomik-dilepas",
     ((MODUL, "        with d.tulis(kon):\n", "        with contextlib.nullcontext():\n"),
      (MODUL, "        kon.rollback()  # transaksi ini milik kita", "        pass  # transaksi ini milik kita"),),
     (T + "test_galat_di_tengah_transaksi_batal_seluruhnya_tanpa_draf_yatim",
      T + "test_commit_gagal_setelah_tulis_tetap_batal_tanpa_draf_yatim")),
    ("7b-rollback-cadangan-dilepas",
     ((MODUL, "        kon.rollback()  # transaksi ini milik kita", "        pass  # transaksi ini milik kita"),),
     (T + "test_commit_gagal_setelah_tulis_tetap_batal_tanpa_draf_yatim",)),
    ("8-purna-tak-terpasang-lolos",
     ((MODUL, '(purna_ringkas["terpasang"] is True and purna_ringkas["lunas"] is True',
       '(purna_ringkas["lunas"] is True'),),
     (GUARD_MURNI,)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("peta-otomatis-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path, sasaran):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *sasaran, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=240)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    sasaran = sorted({t for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_penerbitan_otomatis_menangkap_mutasi(salinan, nama, suntingan, sasaran):
    asli = {}
    try:
        for rel, lama, baru in suntingan:
            berkas = salinan / rel
            sumber = asli.setdefault(rel, berkas.read_text(encoding="utf-8"))
            terkini = berkas.read_text(encoding="utf-8")
            assert terkini.count(lama) == 1, "%s: pola mutasi harus unik di %s" % (nama, rel)
            berkas.write_text(terkini.replace(lama, baru), encoding="utf-8")
            assert sumber != berkas.read_text(encoding="utf-8")
        hasil = _jalankan(salinan, sasaran)
    finally:
        for rel, sumber in asli.items():
            (salinan / rel).write_text(sumber, encoding="utf-8")
    keluaran = hasil.stdout + hasil.stderr
    assert hasil.returncode == 1, keluaran
    assert re.search(r"\b\d+ failed", keluaran), keluaran
    assert not re.search(r"\b\d+ error", keluaran), keluaran

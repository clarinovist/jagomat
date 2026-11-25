"""Mutation guard rilis harga (probe skema, rehearsal, deteksi backup) pada SALINAN repo terisolasi.

Menonaktifkan satu guard lalu menjalankan tes yang menjaganya: hasil harus MERAH karena asersi. Kontrol: tanpa mutasi, tes yang sama
hijau di salinan yang sama. Guard rehearsal "tidak boleh turun" berlapis dua (cek awal + cek state akhir) dan dimutasi bersama.
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
P = "mesin/__tests__/test_harga_probe.py::"
B = "mesin/__tests__/test_harga_backup.py::"
DEPLOY = "scripts/deploy.py"
BACKUP = "mesin/admin_backup.py"
BACKUP_PESANAN = "mesin/admin_backup_pesanan.py"

KASUS = (
    ("probe-skema-parsial-ditolak",
     ((DEPLOY, "        import schema_harga\n        assert schema_harga.validasi(kon), 'schema_harga_parsial'\n", "        pass\n"),),
     (P + "test_trigger_hilang_menggagalkan_probe", P + "test_kolom_berubah_menggagalkan_probe")),
    ("probe-skema-abaikan-tabel-ada",
     ((DEPLOY, "WHERE tbl_name GLOB 'harga_*'\").fetchone()[0]", "WHERE tbl_name GLOB 'harga_x*'\").fetchone()[0]"),),
     (P + "test_trigger_hilang_menggagalkan_probe", P + "test_tabel_harga_hilang_sebagian_menggagalkan_probe")),
    ("probe-image-tanpa-migrasi",
     ((DEPLOY, "        schema_harga.migrasikan(Path('/data/admin-control.db'))\n", "        pass\n"),),
     (P + "test_probe_image_memasang_harga_dua_kali_sebelum_rekening",)),
    ("probe-image-tanpa-foreign-key-check",
     ((DEPLOY, "        assert schema_harga.validasi(kon)\n        assert not kon.execute('PRAGMA foreign_key_check').fetchone()\n",
       "        assert schema_harga.validasi(kon)\n"),),
     (P + "test_probe_image_memasang_harga_dua_kali_sebelum_rekening",)),
    ("rehearsal-harga-tidak-boleh-turun",
     ((BACKUP, "    if type(target_harga) is not bool or (sebelum.skema_harga and not target_harga):\n",
       "    if type(target_harga) is not bool:\n"),
      (BACKUP, "            if admin_backup_pesanan.deteksi_harga(kon) != target_harga:\n                raise BackupTidakSah('state harga berubah selama rehearsal')\n",
       "")),
     (B + "test_rehearsal_harga_tidak_boleh_turun_dan_target_salah",)),
    ("deteksi-harga-parsial-diabaikan",
     ((BACKUP_PESANAN, "    return schema_harga.validasi(kon)\n", "    return False\n"),),
     (B + "test_bundle_harga_parsial_ditolak_validasi_dan_rehearsal",
      B + "test_bundle_dengan_harga_lolos_dan_rehearsal_mempertahankan")),
    ("validasi-bundle-tanpa-deteksi-harga",
     ((BACKUP, "                skema_harga = admin_backup_pesanan.deteksi_harga(kon)\n", ""),),
     (B + "test_bundle_harga_parsial_ditolak_validasi_dan_rehearsal",
      B + "test_bundle_dengan_harga_lolos_dan_rehearsal_mempertahankan")),
    ("rehearsal-harga-tidak-dimigrasi",
     ((BACKUP, "            if target_harga:\n                admin_backup_pesanan.migrasikan_harga(turunan / BERKAS_WAJIB['admin'])\n", ""),),
     (B + "test_rehearsal_target_harga_hanya_turunan_tanpa_menyeret_ledger_lain",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("harga-rilis-mutasi") / "repo"
    ignore = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json")
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=ignore)
    shutil.copytree(AKAR / "scripts", akar / "scripts", ignore=ignore)
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
def test_guard_rilis_harga_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

"""Mutation guard rilis tagihan (probe skema, rehearsal, deteksi backup, CLI migrasi) pada SALINAN repo terisolasi.

Menonaktifkan satu guard lalu menjalankan tes yang menjaganya: hasil harus MERAH karena asersi. Kontrol: tanpa mutasi, tes
yang sama hijau di salinan yang sama. Guard rehearsal "tidak boleh turun" berlapis dua (cek awal + cek state akhir) dan
dimutasi bersama supaya tidak tertutup lapis lain. Prasyarat kelas dimutasi di CLI (pesan galat khusus) dan di rehearsal.
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
P = "mesin/__tests__/test_tagihan_probe.py::"
B = "mesin/__tests__/test_tagihan_backup.py::"
M = "mesin/__tests__/test_tagihan_migrasi.py::"
DEPLOY = "scripts/deploy.py"
BACKUP = "mesin/admin_backup.py"
BACKUP_PESANAN = "mesin/admin_backup_pesanan.py"
MIGRASI = "mesin/tagihan_migrasi.py"

KASUS = (
    ("probe-skema-parsial-ditolak",
     ((DEPLOY, "        import schema_tagihan_catatan\n        assert schema_tagihan_catatan.validasi(kon), 'schema_tagihan_parsial'\n",
       "        pass\n"),),
     (P + "test_trigger_hilang_menggagalkan_probe", P + "test_kolom_berubah_menggagalkan_probe",
      P + "test_indeks_hilang_menggagalkan_probe")),
    ("probe-skema-abaikan-tabel-ada",
     ((DEPLOY, "WHERE tbl_name GLOB 'tagihan_*'\").fetchone()[0]", "WHERE tbl_name GLOB 'tagihan_x*'\").fetchone()[0]"),),
     (P + "test_trigger_hilang_menggagalkan_probe", P + "test_indeks_hilang_menggagalkan_probe")),
    ("probe-blok-tanpa-query-only",
     ((DEPLOY, "    kon.execute('PRAGMA query_only=ON')\n    ada = kon.execute(\"SELECT count(*) FROM sqlite_master WHERE tbl_name GLOB 'tagihan_*'\")",
       "    ada = kon.execute(\"SELECT count(*) FROM sqlite_master WHERE tbl_name GLOB 'tagihan_*'\")"),),
     (P + "test_blok_probe_tagihan_hanya_baca_mode_ro_dan_query_only",)),
    ("probe-image-tanpa-migrasi",
     ((DEPLOY, "        schema_tagihan_catatan.migrasikan(Path('/data/admin-control.db'))\n", "        pass\n"),),
     (P + "test_probe_image_memasang_tagihan_dua_kali_setelah_kelas_dan_harga",)),
    ("probe-image-tanpa-foreign-key-check",
     ((DEPLOY, "        assert schema_tagihan_catatan.validasi(kon)\n        assert not kon.execute('PRAGMA foreign_key_check').fetchone()\n",
       "        assert schema_tagihan_catatan.validasi(kon)\n"),),
     (P + "test_probe_image_memasang_tagihan_dua_kali_setelah_kelas_dan_harga",)),
    ("rehearsal-tagihan-tidak-boleh-turun",
     ((BACKUP, "    if type(target_tagihan) is not bool or (sebelum.skema_tagihan and not target_tagihan):\n",
       "    if type(target_tagihan) is not bool:\n"),
      (BACKUP, "            if admin_backup_pesanan.deteksi_tagihan(kon) != target_tagihan:\n                raise BackupTidakSah('state tagihan berubah selama rehearsal')\n",
       "")),
     (B + "test_rehearsal_tagihan_tidak_boleh_turun_dan_target_salah",)),
    ("rehearsal-tagihan-wajib-kelas",
     ((BACKUP, "    if target_tagihan and not target_kelas:\n        raise BackupTidakSah('target rehearsal tagihan memerlukan kelas')\n", ""),
      (BACKUP, "    if target_tagihan is True and target_kelas is None:\n        target_kelas = True\n", "")),
     (B + "test_rehearsal_tagihan_tanpa_kelas_eksplisit_ditolak",
      B + "test_rehearsal_target_tagihan_hanya_turunan_dan_menyeret_kelas_dan_pesanan")),
    ("deteksi-tagihan-parsial-diabaikan",
     ((BACKUP_PESANAN, "    return schema_tagihan_catatan.validasi(kon)\n", "    return False\n"),),
     (B + "test_bundle_tagihan_parsial_ditolak_validasi_dan_rehearsal",
      B + "test_bundle_dengan_tagihan_lolos_dan_rehearsal_mempertahankan")),
    ("validasi-bundle-tanpa-deteksi-tagihan",
     ((BACKUP, "                skema_tagihan = admin_backup_pesanan.deteksi_tagihan(kon)\n", ""),),
     (B + "test_bundle_tagihan_parsial_ditolak_validasi_dan_rehearsal",
      B + "test_bundle_dengan_tagihan_lolos_dan_rehearsal_mempertahankan")),
    ("rehearsal-tagihan-tidak-dimigrasi",
     ((BACKUP, "            if target_tagihan:\n                admin_backup_pesanan.migrasikan_tagihan(turunan / BERKAS_WAJIB['admin'])\n", ""),),
     (B + "test_rehearsal_target_tagihan_hanya_turunan_dan_menyeret_kelas_dan_pesanan",)),
    ("cli-migrasi-tanpa-prasyarat-kelas",
     ((MIGRASI, "    periksa_prasyarat(path)\n    schema_tagihan_catatan.migrasikan(path)\n",
       "    schema_tagihan_catatan.migrasikan(path)\n"),),
     (M + "test_tanpa_kelas_ditolak_tanpa_mengubah",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("tagihan-rilis-mutasi") / "repo"
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
def test_guard_rilis_tagihan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

"""Mutation guard harga pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil harus MERAH karena
asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus HIJAU di salinan yang sama.
Pola mutasi harus unik di berkasnya. Salinan tidak memuat .venv, cadangan, *.db, atau *.json.
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
HV = "mesin/__tests__/test_harga_validasi.py::"
H = "mesin/__tests__/test_harga.py::"
S = "mesin/__tests__/test_schema_harga.py::"
VALIDASI, ATURAN, INTI = "mesin/harga_validasi.py", "mesin/harga_aturan.py", "mesin/harga.py"
SKEMA = "mesin/schema_harga.py"
TRIGGER_UPDATE = ("CREATE TRIGGER harga_riwayat_tolak_update BEFORE UPDATE ON harga_riwayat\n"
                  "BEGIN SELECT RAISE(ABORT, '{tolak}'); END;\n")
TRIGGER_DELETE = ("CREATE TRIGGER harga_riwayat_tolak_delete BEFORE DELETE ON harga_riwayat\n"
                  "BEGIN SELECT RAISE(ABORT, '{tolak}'); END;\n")
TRIGGER_REPLACE = ("CREATE TRIGGER harga_riwayat_tolak_replace BEFORE INSERT ON harga_riwayat\n"
                   "WHEN NEW.id IS NOT NULL AND EXISTS(SELECT 1 FROM harga_riwayat WHERE id=NEW.id)\n"
                   "BEGIN SELECT RAISE(ABORT, 'riwayat harga duplikat'); END;\n")

KASUS = (
    ("A-rentang-maks-dilepas",
     ((VALIDASI, "    if not HARGA_MIN <= rupiah <= HARGA_MAKS:", "    if not HARGA_MIN <= rupiah:"),),
     (HV + "test_rentang_maksimum_ditolak_lewat_validator", HV + "test_rentang_batas_bawah_dan_atas_pada_aturan_murni")),
    ("B-tipe-bool-diterima",
     ((VALIDASI, "    if type(rupiah) is not int:", "    if False:"),),
     (HV + "test_harga_harus_bilangan_bulat_asli",)),
    ("C-kelipatan-dilepas",
     ((VALIDASI, "    if rupiah % KELIPATAN != 0:", "    if False:"),),
     (HV + "test_kelipatan_ditolak_lewat_validator_tanpa_konflik_pita", HV + "test_kelipatan_aturan_murni")),
    ("D-peta-bisa-diubah",
     ((VALIDASI, "    if kode not in ALLOW_UBAH:", "    if False:"),),
     (HV + "test_peta_hanya_baca_berapa_pun_nilainya", H + "test_peta_tidak_bisa_diubah_dan_tidak_menulis")),
    ("E1-nominal-positif-mini-dilepas",
     ((VALIDASI, "    if minimum_mini - RUPIAH_DEPOSIT <= 0:", "    if False:"),),
     (HV + "test_nominal_positif_ditolak_lewat_validator_mini_kecil", HV + "test_nominal_positif_setelah_deposit_aturan_murni")),
    ("E2-nominal-positif-private-dilepas",
     ((VALIDASI, '    if harga["private"] - RUPIAH_DEPOSIT <= 0:', "    if False:"),),
     (HV + "test_nominal_positif_setelah_deposit_aturan_murni",
      HV + "test_nominal_positif_private_ditolak_lewat_validator_tanpa_bentrok_pita")),
    ("A2-rentang-batas-bawah-dilepas",
     ((VALIDASI, "    if not HARGA_MIN <= rupiah <= HARGA_MAKS:", "    if not rupiah <= HARGA_MAKS:"),),
     (HV + "test_rentang_batas_bawah_dan_atas_pada_aturan_murni",)),
    ("F1-pita-dilepas",
     ((VALIDASI, "        if selisih <= KODE_MAKS:", "        if False:"),),
     (HV + "test_pita_selisih_998_dan_999_ditolak_selisih_1000_lolos_aturan_murni",
      HV + "test_pita_beririsan_selisih_875_ditolak_dan_menyebut_modul",
      HV + "test_deposit_private_sama_dengan_harian_tahunan_ditolak")),
    ("F2-pita-geser-satu-rupiah",
     ((VALIDASI, "        if selisih <= KODE_MAKS:", "        if selisih < KODE_MAKS:"),),
     (HV + "test_pita_selisih_998_dan_999_ditolak_selisih_1000_lolos_aturan_murni",)),
    ("F3-kandidat-diganti-harga-basi",
     ((VALIDASI, "    return {p: rupiah if p == kode else harga_lain[p] for p in KODE_PRODUK}",
       "    return {p: harga_lain[p] if p in harga_lain else rupiah for p in KODE_PRODUK}"),),
     (HV + "test_pita_memakai_kandidat_bukan_harga_basi_di_harga_lain",)),
    ("G-batas-atas-dilepas",
     ((VALIDASI, "    if tertinggi + KODE_MAKS > BATAS_RUPIAH:", "    if False:"),),
     (HV + "test_batas_atas_aturan_murni_dengan_kode_unik",)),
    ("P-proporsional-tanpa-setengah-naik",
     ((ATURAN, "    return (harga_bulanan * sisa + PERTEMUAN_PER_BULAN // 2) // PERTEMUAN_PER_BULAN",
       "    return (harga_bulanan * sisa) // PERTEMUAN_PER_BULAN"),),
     (H + "test_proporsional_pembulatan_setengah_naik",)),
    ("K-konflik-revisi-dilepas",
     ((INTI, "    if lama_aktif != diharapkan:", "    if False:"),),
     (H + "test_konflik_revisi_tidak_menulis",)),
    ("Q1-check-db-tanpa-kelipatan",
     ((SKEMA, '"{k} BETWEEN {min} AND {maks} AND {k} % {kelipatan} = 0".format(',
       '"{k} BETWEEN {min} AND {maks}".format('),),
     (S + "test_check_rupiah_menolak_di_luar_rentang_dan_bukan_kelipatan",)),
    ("Q2-check-db-tanpa-rentang",
     ((SKEMA, '"{k} BETWEEN {min} AND {maks} AND {k} % {kelipatan} = 0".format(',
       '"{k} % {kelipatan} = 0".format('),),
     (S + "test_check_rupiah_menolak_di_luar_rentang_dan_bukan_kelipatan",)),
    ("U-riwayat-update-diizinkan",
     ((SKEMA, TRIGGER_UPDATE, ""),),
     (S + "test_riwayat_menolak_update_append_only",)),
    ("V-riwayat-delete-diizinkan",
     ((SKEMA, TRIGGER_DELETE, ""),),
     (S + "test_riwayat_menolak_delete_append_only",)),
    ("R-replace-guard-dilepas",
     ((SKEMA, TRIGGER_REPLACE, ""),),
     (S + "test_riwayat_menolak_insert_or_replace_pada_id_sama",)),
)
KONTROL = tuple(sorted({t for _, _, ts in KASUS for t in ts}))


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("harga-mutasi") / "repo"
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
    hasil = _jalankan(salinan, KONTROL)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_harga_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

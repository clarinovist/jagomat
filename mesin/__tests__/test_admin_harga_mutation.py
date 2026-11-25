"""Mutation guard Harga admin pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes penjaga: hasil harus MERAH karena asersi
(bukan import atau fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus HIJAU di salinan yang sama.
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
UJI = [
    "mesin/__tests__/test_admin_harga.py",
    "mesin/__tests__/test_admin_harga_pages.py",
    "mesin/__tests__/test_admin_harga_baca.py",
]
HTTP = "mesin/admin_harga_http.py"
PAGES = "mesin/admin_harga_pages.py"
HTTP_ADMIN = "mesin/admin_http.py"
INTI = "mesin/harga.py"

KASUS = (
    ("A1-guard-admin-dilepas",
     ((HTTP, "    principal = h._principal_admin(penangan)", "    principal = penangan._principal()"),)),
    ("B1-csrf-dilepas",
     ((HTTP_ADMIN, '    _cek_csrf(akun, token_sesi, data.pop("csrf", None))\n    token = data.pop("tinjauan", None)',
       '    data.pop("csrf", None)\n    token = data.pop("tinjauan", None)'),)),
    ("B2-tinjauan-dilepas",
     ((HTTP_ADMIN, "    tinjauan = admin_security.periksa_tinjauan(akun, token_sesi, token)",
       '    tinjauan = {"aksi": aksi, "data": {"target_id": "private", "target_revisi": 640000}}'),)),
    ("B3-sandi-ulang-dilepas",
     ((HTTP_ADMIN, '    if not _reauth(principal, data.pop("reauth", "")):',
       '    if not _reauth(principal, data.pop("reauth", "")) and False:'),)),
    ("C1-kode-dari-form",
     ((HTTP, '    kode, lama = meta.get("target_id"), meta.get("target_revisi")',
       '    kode, lama = data.get(ui.FIELD_KODE), meta.get("target_revisi")'),)),
    ("D1-allow-ubah-dilepas",
     ((HTTP, '    if kode not in a.ALLOW_UBAH or type(lama) is not int:', '    if type(lama) is not int:'),)),
    ("E1-konflik-harga-lama-dilepas",
     ((INTI, "    if lama_aktif != diharapkan:", "    if False:"),)),
    ("F1-validasi-pra-dilewati",
     ((HTTP, "    _validasi_pra(kode, rupiah, lama, aktif)", "    pass"),)),
    ("H1-guard-selisih-besar-dilepas",
     ((HTTP, "    if besar and konfirmasi is None:", "    if False:"),)),
    ("H2-konfirmasi-nilai-sembarang-diterima",
     ((HTTP, "    if konfirmasi is not None and konfirmasi != ui.NILAI_KONFIRMASI:", "    if False:"),)),
    ("H3-batas-rasio-diubah-ke-10",
     ((HTTP, "BATAS_RASIO = 2 ", "BATAS_RASIO = 10 "),)),
    ("I1-harga-sama-diterima",
     ((HTTP, "    if rupiah == lama == aktif[kode]:", "    if False:"),)),
    ("J1-riwayat-lama-kosong-lagi",
     ((INTI, "(kode, lama_aktif, rupiah_baru, oleh, waktu))", "(kode, None, rupiah_baru, oleh, waktu))"),)),
    ("G1-escape-galat-dilepas",
     ((PAGES, "            % (e(judul), e(pesan)))", "            % (e(judul), pesan))"),)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("harga-admin-mutasi") / "repo"
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
    hasil = _jalankan(salinan, UJI)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan", KASUS, ids=[k[0] for k in KASUS])
def test_guard_harga_admin_menangkap_mutasi(salinan, nama, suntingan):
    asli = {}
    try:
        for rel, lama, baru in suntingan:
            berkas = salinan / rel
            asli.setdefault(rel, berkas.read_text(encoding="utf-8"))
            terkini = berkas.read_text(encoding="utf-8")
            assert terkini.count(lama) == 1, "%s: pola mutasi harus unik di %s" % (nama, rel)
            berkas.write_text(terkini.replace(lama, baru), encoding="utf-8")
        hasil = _jalankan(salinan, UJI)
    finally:
        for rel, sumber in asli.items():
            (salinan / rel).write_text(sumber, encoding="utf-8")
    keluaran = hasil.stdout + hasil.stderr
    assert hasil.returncode == 1, keluaran
    assert re.search(r"\b\d+ failed", keluaran), keluaran
    assert not re.search(r"\b\d+ error", keluaran), keluaran

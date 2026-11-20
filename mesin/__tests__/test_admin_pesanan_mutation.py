"""Mutation guard panel admin pesanan (Fase 3c-4) pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil harus
MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus HIJAU
di salinan yang sama. Pola mutasi harus unik di berkasnya. Salinan tidak memuat `.venv`, cadangan,
`*.db`, atau `*.json` (tanpa data/sandi nyata).
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
G = "mesin/__tests__/test_admin_pesanan.py::"
D = "mesin/__tests__/test_admin_pesanan_detail.py::"
HTTP, ADMIN = "mesin/admin_pesanan_http.py", "mesin/admin_http.py"
AKSI = "mesin/admin_pesanan_aksi.py"
REAUTH = (ADMIN, '    if not _reauth(principal, data.pop("reauth", "")):\n        raise PermissionError("Autentikasi ulang gagal.")\n',
          '    data.pop("reauth", "")\n')

KASUS = (
    ("A-peran-admin-dilepas",
     ((HTTP, "def _admin(penangan):\n    return h._principal_admin(penangan)\n",
       "def _admin(penangan):\n    return penangan._principal()\n"),),
     (G + "test_nonadmin_404_byte_identik_rute_tak_dikenal_tanpa_efek",)),
    ("B-csrf-dilepas",
     ((ADMIN, '    _cek_csrf(akun, token_sesi, data.pop("csrf", None))\n    token = data.pop("tinjauan", None)\n',
       '    data.pop("csrf", None)\n    token = data.pop("tinjauan", None)\n'),),
     (G + "test_csrf_salah_403_tanpa_efek",)),
    ("C-validasi-catatan-kode-dilepas",
     ((HTTP, '    if catatan not in CATATAN_REFUND:\n        raise ValueError("catatan_kode tidak sah")\n', ""),),
     (G + "test_refund_isian_tak_sah_400_tanpa_efek",)),
    ("D-akun-id-dari-form-bukan-ledger",
     ((HTTP, '    if data:\n        raise ValueError("isian asing")\n    runtime = _runtime_periksa(penangan)\n',
       '    if set(data) - {"akun_id"}:\n        raise ValueError("isian asing")\n    runtime = _runtime_periksa(penangan)\n'),
      (HTTP, "    akun_id = _akun_ledger(order_id)\n",
       '    akun_id = data.get("akun_id") or _akun_ledger(order_id)\n')),
     (G + "test_periksa_akun_id_dari_ledger_form_dengan_akun_id_ditolak",)),
    ("E-gerbang-tertutup-dilewati-pada-periksa",
     ((HTTP, "    return pesanan_http._runtime_bila_terbuka(penangan)\n", "    return pesanan_http._runtime(penangan)\n"),),
     (G + "test_periksa_gerbang_tertutup_jujur_tanpa_panggilan_provider_dan_tanpa_efek",)),
    ("F-sandi-ulang-dilepas",
     ((ADMIN, '    if not _reauth(principal, data.pop("reauth", "")):\n        raise PermissionError("Autentikasi ulang gagal.")\n',
       '    data.pop("reauth", "")\n'),),
     (G + "test_sandi_ulang_salah_403_tanpa_efek",)),
    ("G-tinjauan-lintas-aksi-diterima",
     ((ADMIN, '    if tinjauan["aksi"] != aksi:\n        raise PermissionError("Tinjauan tidak cocok.")\n', ""),),
     (G + "test_tinjauan_aksi_lain_tidak_berlaku_lintas_rute",)),
    ("H-operasi-refund-acak-tidak-idempoten",
     ((HTTP, '    return "rfd_" + hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:_PANJANG_OPERASI]\n',
       '    return "rfd_" + __import__("secrets").token_hex(16)\n'),),
     (G + "test_refund_idempoten_replay_form_sama", G + "test_refund_ulang_dari_form_baru_dengan_catatan_sama_idempoten")),
    # Fase C: aksi uang dari halaman Detail order. Reauth dimatikan (sama seperti F) harus merahkan tes negatif
    # refund dan periksa yang memakai form persis seperti dirender halaman Detail.
    ("I-reauth-dilepas-pada-refund-dari-detail", (REAUTH,),
     (D + "test_refund_dari_detail_tanpa_syarat_guard_403_tanpa_catatan",)),
    ("J-reauth-dilepas-pada-periksa-dari-detail", (REAUTH,),
     (D + "test_periksa_dari_detail_tanpa_syarat_guard_403_tanpa_efek",)),
    ("K-csrf-dilepas-pada-refund-dari-detail",
     ((ADMIN, '    _cek_csrf(akun, token_sesi, data.pop("csrf", None))\n    token = data.pop("tinjauan", None)\n',
       '    data.pop("csrf", None)\n    token = data.pop("tinjauan", None)\n'),),
     (D + "test_refund_dari_detail_tanpa_syarat_guard_403_tanpa_catatan",)),
    ("L-peran-admin-dilepas-pada-detail",
     ((HTTP, "def _admin(penangan):\n    return h._principal_admin(penangan)\n",
       "def _admin(penangan):\n    return penangan._principal()\n"),),
     (D + "test_detail_nonadmin_404_byte_identik_dan_ledger_tak_dibaca",)),
    ("M-id-detail-tak-divalidasi",
     ((AKSI, '    if type(order_id) is not str or _POLA_ORDER.fullmatch(order_id) is None:\n        raise ValueError("order tidak sah")\n    return order_id\n',
       "    return order_id\n"),),
     (D + "test_detail_query_tak_sah_404_identik_rute_tak_dikenal",)),
    ("N-allowlist-saringan-daftar-dilepas",
     ((HTTP, '    if saring is not None and saring not in ui.KODE_SARING:\n        raise ValueError("query tidak sah")\n', ""),),
     (D + "test_daftar_saringan_asing_404_identik",)),
    ("O-form-detail-untuk-sesi-non-kuki",
     ((HTTP, '    if principal.metode != "cookie":\n        return {}\n    tersedia = ui.aksi_tersedia(detail, gerbang_terbuka)\n',
       "    tersedia = ui.aksi_tersedia(detail, gerbang_terbuka)\n"),),
     (D + "test_detail_sesi_basic_baca_saja_tanpa_form_dan_tanpa_sandi",
      D + "test_detail_sesi_basic_lunas_baca_saja_tanpa_form_refund")),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("admin-pesanan-mutasi") / "repo"
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
    sasaran = sorted({t.split("::")[0] for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_admin_pesanan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

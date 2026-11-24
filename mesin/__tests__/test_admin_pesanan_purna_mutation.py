"""Mutation guard aksi admin purna (V3: voucher dipakai, laporan terbit) pada SALINAN repo terisolasi (bukan workspace).

Meniru `test_admin_pesanan_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus
HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya (count == 1). Salinan tidak memuat `.venv`, cadangan,
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
P = "mesin/__tests__/test_admin_pesanan_purna.py::"
G = "mesin/__tests__/test_admin_pesanan_purna_pages.py::"
W = "mesin/__tests__/test_pesanan_admin_order_purna.py::"
HTTP, ADMIN, HALAMAN = "mesin/admin_pesanan_http.py", "mesin/admin_http.py", "mesin/admin_pesanan_pages.py"
ORDER, ATURAN_REFUND = "mesin/pesanan_admin_order.py", "mesin/pesanan_refund_aturan.py"
CSRF = (ADMIN, '    _cek_csrf(akun, token_sesi, data.pop("csrf", None))\n    token = data.pop("tinjauan", None)\n',
        '    data.pop("csrf", None)\n    token = data.pop("tinjauan", None)\n')
REAUTH = (ADMIN, '    if not _reauth(principal, data.pop("reauth", "")):\n        raise PermissionError("Autentikasi ulang gagal.")\n',
          '    data.pop("reauth", "")\n')

KASUS = (
    ("a-validasi-field-voucher-dilepas",
     ((HTTP, '    if set(data) != {"catatan_kode"}:\n        raise ValueError("isian voucher tidak sah")\n', ""),),
     (P + "test_voucher_isian_tak_sah_400_tanpa_efek", P + "test_voucher_dan_terbit_order_id_hanya_dari_tinjauan_bukan_form")),
    ("b-validasi-enum-catatan-kode-dilepas",
     ((HTTP, '    if catatan not in CATATAN_PAKAI:\n        raise ValueError("catatan_kode voucher tidak sah")\n', ""),),
     (P + "test_voucher_isian_tak_sah_400_tanpa_efek",)),
    ("c-validasi-data-kosong-terbit-dilepas",
     ((HTTP, '    if data:\n        raise ValueError("isian terbit asing")\n', ""),),
     (P + "test_terbit_field_asing_400_tanpa_efek",)),
    ("d1-aksi-rute-terbit-salah-petakan",
     ((HTTP, "             RUTE_TERBIT: AKSI_TERBIT}\n", "             RUTE_TERBIT: AKSI_VOUCHER}\n"),),
     (P + "test_terbit_dari_detail_mencatat_jam_server_oleh_admin_sesi_lalu_form_hilang",
      P + "test_tinjauan_aksi_lain_ditolak_lintas_rute_purna")),
    ("d2-aksi-token-form-terbit-salah-petakan",
     ((HTTP, "            ui.AKSI_TERBIT: AKSI_TERBIT}\n", "            ui.AKSI_TERBIT: AKSI_VOUCHER}\n"),),
     (P + "test_terbit_dari_detail_mencatat_jam_server_oleh_admin_sesi_lalu_form_hilang",)),
    ("d3-aksi-tinjauan-tidak-dicocokkan",
     ((ADMIN, '    if tinjauan["aksi"] != aksi:\n        raise PermissionError("Tinjauan tidak cocok.")\n', ""),),
     (P + "test_tinjauan_aksi_lain_ditolak_lintas_rute_purna", P + "test_tinjauan_purna_ditolak_di_rute_refund_dan_periksa")),
    ("e-form-refund-tetap-tampil-bila-voucher-dipakai",
     ((HALAMAN, '    if status in STATUS_REFUND and not pur.get("dipakai"):\n', "    if status in STATUS_REFUND:\n"),),
     (P + "test_form_refund_tersembunyi_sesudah_voucher_dipakai_dengan_catatan_pengganti",
      G + "test_form_refund_tidak_dirender_bila_voucher_dipakai_walau_token_refund_ada")),
    ("f1-syarat-tampil-form-voucher-dilepas",
     ((HALAMAN, '    if terpasang and pur.get("voucher") == purna.VOUCHER_AKTIF:\n', "    if terpasang:\n"),),
     (P + "test_form_purna_tersembunyi_untuk_order_belum_lunas", P + "test_voucher_kedaluwarsa_409_tanpa_efek_dan_form_hilang",
      G + "test_aksi_tersedia_order_lunas_menurut_keadaan_purna")),
    ("f2-syarat-tampil-form-terbit-dilepas",
     ((HALAMAN, '    if terpasang and pur.get("lunas") and pur.get("terbit") is None and not pur.get("direfund"):\n',
       "    if terpasang:\n"),),
     (P + "test_form_terbit_tersembunyi_sesudah_terbit_dan_sesudah_refund", P + "test_form_purna_tersembunyi_untuk_order_belum_lunas",
      G + "test_aksi_tersedia_order_lunas_menurut_keadaan_purna")),
    ("g-peran-admin-dilepas-pada-rute-purna",
     ((HTTP, "def _admin(penangan):\n    return h._principal_admin(penangan)\n",
       "def _admin(penangan):\n    return penangan._principal()\n"),),
     (P + "test_nonadmin_404_byte_identik_rute_tak_dikenal_tanpa_efek",)),
    ("h-whitelist-detail-order-bocor",
     ((ORDER, '            "direfund": k.direfund}\n',
       '            "direfund": k.direfund, "waktu_lunas": k.waktu_lunas, "bisa_pilih": k.bisa_pilih}\n'),),
     (W + "test_whitelist_purna_daftar_kunci_persis_pada_detail_order", W + "test_nilai_purna_order_lunas_baru")),
    ("i-operasi-voucher-acak-tidak-idempoten",
     ((HTTP, '    return "vch_" + hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:_PANJANG_OPERASI]\n',
       '    return "vch_" + __import__("secrets").token_hex(16)\n'),),
     (P + "test_voucher_replay_token_sama_idempoten_satu_baris", P + "test_voucher_kedua_kali_dari_token_baru_catatan_sama_sudah_ada")),
    ("j-sandi-ulang-dilepas-pada-rute-purna", (REAUTH,), (P + "test_guard_form_ditolak_403_tanpa_efek",)),
    ("k-csrf-dilepas-pada-rute-purna", (CSRF,), (P + "test_guard_form_ditolak_403_tanpa_efek",)),
    ("l-domain-refund-tidak-menolak-voucher-dipakai",
     ((ATURAN_REFUND, '    if purna.voucher_dipakai(kon, order_id):\n        raise d.PesananKonflik("voucher sudah dipakai")\n', ""),),
     (P + "test_refund_post_sesudah_voucher_dipakai_409_dan_tidak_ada_baris_refund_di_kedua_tabel",
      P + "test_refund_post_dengan_form_lama_sesudah_voucher_dipakai_tetap_409")),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("admin-pesanan-purna-mutasi") / "repo"
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
def test_guard_purna_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

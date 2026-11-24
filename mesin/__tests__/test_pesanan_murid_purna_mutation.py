"""Mutation guard kartu deposit pembeli dan rute pilihan yang sudah dihapus, pada SALINAN repo terisolasi.

Meniru `test_pesanan_murid_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di
salinan yang sama. Pola mutasi harus unik di berkasnya. Salinan tanpa `.venv`, cadangan, `*.db`, `*.json`.

Catatan: `pesanan_status.ambil_order` di `keadaan_order` adalah lapis kedua (order sudah diturunkan dari akun sesi
lewat `order_id_akun`); karena itu kasus kepemilikan juga mengganti SUMBER order ke order mana pun di DB.
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
P = "mesin/__tests__/test_pesanan_murid_purna.py::"
U = "mesin/__tests__/test_pesanan_voucher_pages.py::"
K = "mesin/__tests__/test_orang_tua_pesanan_kartu.py::"
BACA, HALAMAN, HTTP, MURID = (
    "mesin/pesanan_voucher_baca.py", "mesin/pesanan_voucher_pages.py", "mesin/pesanan_http.py",
    "mesin/pesanan_murid_http.py")
ORTU = "mesin/orang_tua_pages.py"
KARTU_AKHIR = "        + _blok_laporan(k)\n    )"
PILIH_BARU = '"/murid/pesanan/pilih"'

KASUS = (
    ("V1a-rute-pilih-dihidupkan-lagi-untuk-murid",
     ((MURID, "_RUTE.bukti, _RUTE.ulang_transfer})", "_RUTE.bukti, _RUTE.ulang_transfer, %s})" % PILIH_BARU),),
     (P + "test_murid_post_rute_pilih_404_identik_dengan_rute_tak_dikenal_tanpa_efek",)),
    ("V2-kartu-memuat-tombol",
     ((HALAMAN, KARTU_AKHIR, "        + _blok_laporan(k)\n        + '<button type=\"submit\">Pilih</button>'\n    )"),),
     (P + "test_kartu_tampil_untuk_order_lunas_dengan_deposit_tenggat_dan_janji_tanpa_tombol",
      P + "test_kartu_terlambat_tanpa_tombol_dengan_kalimat_maaf_lalu_terbit_menurut_keadaan",
      U + "test_kartu_tanpa_tombol_form_atau_pilihan_apa_pun")),
    ("V3-kartu-menampilkan-kode-voucher",
     ((HALAMAN, KARTU_AKHIR, "        + _blok_laporan(k)\n        + '<code>%s</code>' % k.kode\n    )"),),
     (P + "test_kode_voucher_internal_tidak_tampil_ke_pembeli_tetapi_ada_di_domain",
      U + "test_kode_voucher_internal_tidak_ditampilkan_ke_pembeli")),
    ("V4-kartu-merender-kontak",
     ((HALAMAN, KARTU_AKHIR, "        + _blok_laporan(k)\n        + '<a href=\"https://wa.me/6281234567890\">Hubungi</a>'\n    )"),),
     (P + "test_halaman_murid_tanpa_kata_terlarang_kontak_atau_id_internal", U + "test_kartu_tanpa_kontak_dan_id_internal")),
    ("V5-kartu-tanpa-syarat-purna-terpasang",
     ((BACA, "            if not purna.terpasang(kon):\n                return None\n", ""),),
     (P + "test_kartu_tidak_tampil_bila_skema_purna_belum_dipasang",
      P + "test_halaman_orang_tua_tanpa_baris_janji_bila_purna_belum_dipasang")),
    ("V6-kartu-tanpa-syarat-status-sudah-dibayar-ditahan-dan-direfund-tampil",
     ((BACA, "    if status != dasar.STATUS_SUDAH_DIBAYAR:\n        return None\n", ""),),
     (P + "test_kartu_tidak_tampil_untuk_order_direfund",
      P + "test_kartu_tidak_tampil_untuk_order_perlu_diperiksa_ditahan")),
    ("V7-kartu-juga-untuk-permukaan-guru",
     ((HTTP, "    if principal.peran != permukaan.PERAN_MURID:\n        return None\n", ""),),
     (P + "test_guru_lama_rute_pilih_identik_rute_tak_dikenal_tanpa_kartu",)),
    ("V8-kepemilikan-kartu-order-bukan-dari-akun-sesi",
     ((BACA, "    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)\n    if order_id is None:\n        return None\n",
       "    with pesanan_transfer.buka(admin_store.BAWAAN) as kon0:\n"
       "        baris0 = kon0.execute('SELECT order_id FROM pesanan_order ORDER BY rowid LIMIT 1').fetchone()\n"
       "    order_id = None if baris0 is None else baris0[0]\n    if order_id is None:\n        return None\n"),
      (BACA, "            order = pesanan_status.ambil_order(kon, order_id, akun_id)\n",
       "            order = {\"order_id\": order_id}\n")),
     (P + "test_kartu_murid_b_memakai_order_miliknya_bukan_order_milik_lain",)),
    ("V9-baris-janji-orang-tua-tidak-tampil",
     ((ORTU, "        if sudah and purna is not None:", "        if sudah and purna is None:"),),
     (K + "test_sudah_dibayar_dengan_purna_menambah_satu_baris_janji_tanpa_tombol",
      P + "test_halaman_orang_tua_memuat_satu_baris_janji_tanpa_tombol_dan_beranda_tetap_satu_tautan")),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("pesanan-murid-purna-mutasi") / "repo"
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
def test_guard_pilih_dan_kartu_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

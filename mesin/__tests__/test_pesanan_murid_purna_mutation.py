"""Mutation guard pilihan terlambat dan kartu voucher pembeli (V4a) pada SALINAN repo terisolasi (bukan workspace).

Meniru `test_pesanan_murid_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di
salinan yang sama. Pola mutasi harus unik di berkasnya. Salinan tanpa `.venv`, cadangan, `*.db`, `*.json`.

Catatan: `pesanan_status.ambil_order` di rute pilih adalah lapis kedua (order sudah diturunkan dari akun sesi lewat
`order_id_akun`); karena itu kasus kepemilikan juga mengganti SUMBER order ke order mana pun di DB.
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
PILIH, BACA, HALAMAN, HTTP = (
    "mesin/pesanan_pilih_http.py", "mesin/pesanan_voucher_baca.py", "mesin/pesanan_voucher_pages.py",
    "mesin/pesanan_http.py")
KONDISI_TOMBOL = "    return rute.pilih is not None and k.bisa_pilih and k.pilihan != purna.PILIHAN_UANG_KEMBALI\n"
SYARAT_TOMBOL = (P + "test_dua_tombol_dalam_satu_form_hanya_saat_terlambat_dan_bisa_pilih",
                 P + "test_memilih_uang_kembali_dicatat_tanpa_tombol_dan_voucher_batal",
                 P + "test_guru_lama_tanpa_kartu_dan_tanpa_tombol_dan_tanpa_rute_pilih",
                 U + "test_tanpa_tombol_bila_tidak_bisa_pilih", U + "test_tanpa_tombol_bila_uang_kembali_walau_bisa_pilih_masih_true",
                 U + "test_tanpa_tombol_untuk_permukaan_guru_tanpa_rute_pilih")

KASUS = (
    ("V1-kepemilikan-order-bukan-dari-akun-sesi",
     ((PILIH, "    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)\n    if order_id is None:\n        raise pesanan.PesananTidakDitemukan()\n",
       "    with pesanan.buka(admin_store.BAWAAN) as kon0:\n"
       "        baris = kon0.execute('SELECT order_id FROM pesanan_order ORDER BY rowid LIMIT 1').fetchone()\n"
       "    order_id = None if baris is None else baris[0]\n    if order_id is None:\n        raise pesanan.PesananTidakDitemukan()\n"),
      (PILIH, "        order = pesanan_status.ambil_order(kon, order_id, principal.id_akun)\n        purna.catat_pilihan(kon, order[\"order_id\"], pilihan, alur.waktu_sekarang())",
       "        purna.catat_pilihan(kon, order_id, pilihan, alur.waktu_sekarang())")),
     (P + "test_murid_lain_dan_order_tak_ada_404_identik_dengan_rute_tak_dikenal_tanpa_efek",)),
    ("V2-whitelist-pilihan-dilepas",
     ((PILIH, "    if data[\"pilihan\"] not in schema_purna.PILIHAN_TERLAMBAT:\n        penangan._tolak_isian()\n        return None\n", ""),),
     (P + "test_pilihan_asing_dan_form_asing_400_tanpa_efek",)),
    ("V3-form-persis-dilonggarkan",
     ((PILIH, "    if data is None or set(data) != KUNCI_FORM:", "    if data is None or not KUNCI_FORM <= set(data):"),),
     (P + "test_pilihan_asing_dan_form_asing_400_tanpa_efek",)),
    ("V4a-token-tidak-divalidasi",
     ((PILIH, "    if not dasar.token_sah(principal, penangan._ambil_token(), AKSI_PILIH, data[\"token\"]):", "    if False:"),),
     (P + "test_token_tidak_sah_403_tanpa_efek",)),
    ("V4b-token-tidak-terikat-aksi-pilih",
     ((PILIH, "AKSI_PILIH, data[\"token\"]", "dasar.alur.AKSI_PERIKSA, data[\"token\"]"),),
     (P + "test_token_tidak_sah_403_tanpa_efek",)),
    ("V5-pembatas-laju-dilepas",
     ((PILIH, "    if not dasar._izinkan(penangan, principal, ketat=True):", "    if False:"),),
     (P + "test_pembatas_laju_429_tanpa_efek_tambahan",)),
    ("V6a-tombol-tanpa-syarat-bisa-pilih",
     ((HALAMAN, KONDISI_TOMBOL, "    return rute.pilih is not None and k.pilihan != purna.PILIHAN_UANG_KEMBALI\n"),), SYARAT_TOMBOL),
    ("V6b-tombol-tanpa-syarat-bukan-uang-kembali",
     ((HALAMAN, KONDISI_TOMBOL, "    return rute.pilih is not None and k.bisa_pilih\n"),), SYARAT_TOMBOL),
    ("V6c-tombol-tanpa-syarat-rute-pilih",
     ((HALAMAN, KONDISI_TOMBOL, "    return k.bisa_pilih and k.pilihan != purna.PILIHAN_UANG_KEMBALI\n"),), SYARAT_TOMBOL),
    ("V7-kartu-merender-kontak",
     ((HALAMAN, "        + _blok_pilihan(k, rute, token_pilih)\n    )",
       "        + _blok_pilihan(k, rute, token_pilih)\n        + '<a href=\"https://wa.me/6281234567890\">Hubungi</a>'\n    )"),),
     (P + "test_halaman_murid_tanpa_kata_terlarang_kontak_atau_id_internal", U + "test_kartu_tanpa_kontak_dan_id_internal")),
    ("V8-kartu-tanpa-syarat-purna-terpasang",
     ((BACA, "            if not purna.terpasang(kon):\n                return None\n", ""),),
     (P + "test_kartu_tidak_tampil_bila_skema_purna_belum_dipasang",
      P + "test_halaman_orang_tua_tanpa_baris_janji_bila_purna_belum_dipasang")),
    ("V9-kartu-tanpa-syarat-status-lunas",
     ((BACA, "    if status != dasar.STATUS_SUDAH_DIBAYAR:\n        return None\n", ""),),
     (P + "test_kartu_tidak_tampil_untuk_order_direfund",)),
    ("V10-kartu-juga-untuk-permukaan-guru",
     ((HTTP, "    if principal.peran != permukaan.PERAN_MURID:\n        return None, None\n    keadaan =", "    keadaan ="),),
     (P + "test_guru_lama_tanpa_kartu_dan_tanpa_tombol_dan_tanpa_rute_pilih",)),
    ("V11-baris-janji-orang-tua-tidak-tampil",
     ((("mesin/orang_tua_pages.py"), "        if sudah and purna is not None:", "        if sudah and purna is None:"),),
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

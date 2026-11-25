"""Mutation guard domain paket kelas pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard (uang, deposit, kepemilikan, integritas) di salinan lalu menjalankan tes yang
menjaganya: hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus
HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya. Salinan tidak memuat `.venv`, cadangan, `*.db`,
atau `*.json`. Pola sama dengan `test_purna_mutation.py`; guard DDL (CHECK/trigger) dimutasi di `test_schema_kelas.py`.

Catatan lapis ganda: pemakaian deposit dijaga beberapa lapis (cek status `purna`, `_pakai_sudah_ada`, kunci unik
`purna_voucher_pakai`, dan cek kepemilikan kelas). Kasus "deposit-sekali-pakai-semua-lapis-domain" melucuti dua lapis
domain sekaligus supaya tidak tertutup lapis lain; kasus per lapis hanya diklaim bila ia satu-satunya penghalang.
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
T = "mesin/__tests__/"
P = T + "test_kelas_putusan.py::"
S = T + "test_kelas_store.py::"
KATALOG = T + "test_paket_belajar_katalog.py::"
D = T + "test_purna_dalam_transaksi.py::"
PUTUSAN, STORE, STATUS, RINCIAN, PURNA = ("mesin/kelas_putusan.py", "mesin/kelas_store.py", "mesin/kelas_status.py",
                                         "mesin/kelas_rincian.py", "mesin/purna.py")
KATALOG_HARGA = "mesin/paket_belajar_katalog.py"

KASUS = (
    # --- deposit: tepat sekali, hanya akun yang sama, dicek ulang saat lunas ---
    ("deposit-tidak-dipakai-saat-lunas",
     ((PUTUSAN, '        if tagihan["potongan_deposit"] > 0:\n', "        if False:\n"),),
     (P + "test_setujui_dengan_deposit_mencatat_pemakaian_di_transaksi_yang_sama",
      P + "test_deposit_kedaluwarsa_di_antara_tagihan_dan_lunas_ditolak_tanpa_tulisan_apa_pun",
      P + "test_deposit_dipakai_manual_atau_direfund_di_antara_tagihan_dan_lunas_ditolak",
      P + "test_deposit_hanya_sekali_pakai_tagihan_kedua_yang_memegangnya_ditolak")),
    ("deposit-cek-ulang-status-tidak-ada",
     ((PURNA, "        if voucher != VOUCHER_AKTIF:\n", "        if False:\n"),),
     (P + "test_deposit_kedaluwarsa_di_antara_tagihan_dan_lunas_ditolak_tanpa_tulisan_apa_pun",
      P + "test_deposit_dipakai_manual_atau_direfund_di_antara_tagihan_dan_lunas_ditolak")),
    ("deposit-sekali-pakai-semua-lapis-domain",
     ((PURNA, "        if voucher != VOUCHER_AKTIF:\n", "        if False:\n"),
      (PURNA, "    if any(b[0] != operasi_id or b[1:] != isi for b in ada):\n", "    if False:\n")),
     (P + "test_deposit_hanya_sekali_pakai_tagihan_kedua_yang_memegangnya_ditolak",
      P + "test_deposit_dipakai_manual_atau_direfund_di_antara_tagihan_dan_lunas_ditolak")),
    ("deposit-milik-akun-dan-anak-tidak-dicek-saat-lunas",
     ((PUTUSAN, '    if peta is None or peta["akun_id"] != order["akun_id"] or peta["siswa_id"] != order["siswa_id"]:\n',
       "    if peta is None:\n"),),
     (P + "test_deposit_milik_akun_lain_ditolak_domain_walau_lapis_db_hilang",
      P + "test_deposit_anak_lain_ditolak_domain_walau_lapis_db_hilang")),
    ("deposit-pembaca-tanpa-filter-akun",
     ((RINCIAN, '"SELECT order_id FROM pesanan_order WHERE siswa_id=? AND akun_id=?"',
       '"SELECT order_id FROM pesanan_order WHERE siswa_id=? AND ? IS NOT NULL"'),),
     (S + "test_deposit_hanya_dari_order_peta_milik_akun_yang_sama",)),
    ("deposit-tidak-dicek-aktif-saat-tagihan",
     ((RINCIAN, "return order_id if purna.keadaan(kon, order_id, kini).voucher == purna.VOUCHER_AKTIF else None",
       "return order_id"),),
     (S + "test_deposit_kedaluwarsa_tidak_dipotongkan",
      S + "test_deposit_direfund_atau_sudah_dipakai_tidak_dipotongkan",
      S + "test_deposit_peta_belum_lunas_tidak_dipotongkan")),
    ("deposit-dua-tagihan-terbuka-memegang-sama",
     ((RINCIAN, '        if ks.baris_tagihan(kon, order["id"])["deposit_order_id"] == deposit_order:\n',
       "        if False:\n"),),
     (S + "test_deposit_tidak_dipegang_dua_tagihan_terbuka_sekaligus",
      S + "test_kartu_memuat_semua_paket_katalog_dengan_rincian_dan_penanda_tagihan")),
    ("harga-mini-turun-ke-250rb",
     ((KATALOG_HARGA, "HARGA_MINI = 300_000\n", "HARGA_MINI = 250_000\n"),),
     (KATALOG + "test_mini_300rb_offline_60_menit_kuota_5",
      S + "test_tagihan_tanpa_deposit_memakai_harga_katalog")),
    # --- uang: total = nominal + kode, kode unik, hitungan ---
    ("total-tidak-sama-nominal-tambah-kode-saat-setujui",
     ((PUTUSAN, '    if nominal <= 0 or tagihan["nominal"] != nominal or tagihan["total_transfer"] != nominal + '
                'tagihan["kode_unik"]:\n', "    if False:\n"),),
     (P + "test_hitungan_tagihan_tidak_konsisten_ditolak_saat_setujui",)),
    ("total-tagihan-tidak-sama-nominal-tambah-kode",
     ((STORE, "rincian.nominal + kode, kini))", "rincian.nominal + kode + 1, kini))"),),
     (S + "test_tagihan_tanpa_deposit_memakai_harga_katalog",
      S + "test_kode_unik_acak_server_dalam_rentang_dan_nominal_tidak_pernah_dari_pemanggil")),
    ("kode-unik-tidak-melihat-nominal-dipegang",
     ((STORE, "if nominal + kode not in dipegang]", "if True]"),),
     (S + "test_paket_lain_dan_anak_lain_mendapat_tagihan_sendiri_dengan_kode_berbeda_di_nominal_sama",
      S + "test_kode_unik_habis_menolak_tanpa_menulis")),
    # --- kepemilikan: 404-identik, tanpa efek ---
    ("tagihan-dari-tanpa-filter-akun",
     ((STORE, "    order = ks.baris_order_akun(kon, akun_id, order_id)\n", "    order = ks.baris_order(kon, order_id)\n"),),
     (S + "test_tagihan_dari_order_orang_lain_tak_ada_dan_id_salah_tak_terbedakan_dan_tanpa_efek",)),
    ("bukti-order-tanpa-filter-akun",
     ((STATUS, '"SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? "',
       '"SELECT %s FROM kelas_order WHERE ? IS NOT NULL AND siswa_id=? "'),),
     (S + "test_bukti_tanpa_tagihan_terbuka_atau_milik_akun_lain_konflik_identik_tanpa_efek",
      S + "test_tagihan_dari_dan_terbuka_mengembalikan_tagihan_yang_sama")),
    ("anak-milik-akun-lain-tidak-ditolak",
     ((STORE, "    if ks.akun_lain_punya_order(kon, akun_id, siswa_id):\n", "    if False:\n"),),
     (S + "test_kartu_dan_tagihan_anak_milik_akun_lain_berperilaku_tidak_ada",)),
    # --- bukti dan keputusan ---
    ("keputusan-bukan-atas-bukti-yang-dilihat-admin",
     ((PUTUSAN, "    if bukti_dilihat != fakta.bukti_terakhir_id:\n", "    if False:\n"),),
     (P + "test_setujui_atas_bukti_yang_sudah_usang_ditolak_tanpa_tulis",)),
    ("setujui-ulang-tidak-idempoten",
     ((PUTUSAN, "        if ulang is not None:\n", "        if False:\n"),),
     (P + "test_setujui_dua_kali_tidak_menggandakan_akses_maupun_deposit",)),
    ("berkas-bukti-boleh-dipakai-ulang",
     ((STORE, "        if _sha_sudah_dipakai(kon, sha256):\n", "        if False:\n"),),
     (S + "test_berkas_bukti_tidak_dipakai_ulang_di_order_lain_maupun_di_bukti_peta",)),
    ("batas-bukti-domain",
     ((STORE, "        if fakta.jumlah_bukti >= k.MAKS_BUKTI:\n", "        if False:\n"),),
     (S + "test_bukti_maksimal_lima_per_order",)),
    # --- transaksi dan masa aktif ---
    ("pemakaian-deposit-tanpa-syarat-dalam-transaksi",
     ((PURNA, '    if not kon.in_transaction:\n        raise d.PesananDataTidakSah("koneksi tidak dalam transaksi")\n',
       "    pass\n"),),
     (D + "test_ditolak_bila_koneksi_tidak_dalam_transaksi_tanpa_tulis",)),
    ("rantai-akses-tidak-memutus-yang-sudah-berakhir",
     ((PUTUSAN, '    if not baris or baris[0]["berakhir"] < kini:\n', "    if not baris:\n"),),
     (P + "test_akses_yang_sudah_berakhir_memulai_rantai_baru",)),
    ("rantai-akses-lintas-paket",
     ((PUTUSAN, 'WHERE a.siswa_id=? AND o.paket=? ORDER BY a.id DESC"', 'WHERE a.siswa_id=? AND ? IS NOT NULL ORDER BY a.id DESC"'),),
     (P + "test_rantai_per_paket_mini_tidak_menunggu_akhir_private",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("kelas-mutasi") / "repo"
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
def test_guard_kelas_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

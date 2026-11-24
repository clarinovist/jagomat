"""Mutation guard domain purna + guard refund pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard (integritas/pembayaran) di salinan lalu menjalankan tes yang menjaganya:
hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus
HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya. Salinan tidak memuat `.venv`, cadangan,
`*.db`, atau `*.json`. Pola sama dengan `test_pesanan_transfer_mutation.py`. Guard refund diuji per jalur
(satu kasus per pintu masuk) supaya satu jalur yang lolos tidak tertutup oleh jalur lain.
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
B = T + "test_purna.py::"
W = T + "test_purna_tulis.py::"
F = T + "test_purna_refund.py::"
PURNA, ATURAN, TRANSFER = "mesin/purna.py", "mesin/pesanan_refund_aturan.py", "mesin/pesanan_transfer.py"

KASUS = (
    # --- pemakaian voucher ---
    ("U1-pakai-tanpa-syarat-aktif",
     ((PURNA, "        if voucher != VOUCHER_AKTIF:\n", "        if False:\n"),),
     (W + "test_pakai_ditolak_bila_belum_lunas", W + "test_pakai_ditolak_bila_order_sudah_direfund_di_kedua_ledger",
      W + "test_pakai_ditolak_bila_sudah_memilih_uang_kembali",
      W + "test_pakai_kedaluwarsa_tepat_di_batas_ditolak_satu_detik_sebelumnya_boleh")),
    ("U2-pakai-lebih-dari-satu-kali",
     ((PURNA, "    if any(b[0] != operasi_id or b[1:] != isi for b in ada):\n", "    if False:\n"),),
     (W + "test_pakai_operasi_sama_isi_beda_konflik_tanpa_tulis",
      W + "test_pakai_order_sudah_punya_pemakaian_dengan_operasi_lain_konflik",
      W + "test_pakai_operasi_sama_untuk_order_lain_konflik_dan_order_lain_tidak_tertulis")),
    ("U3-replay-pakai-tidak-dilayani",
     ((PURNA, '        if _pakai_sudah_ada(kon, operasi_id, isi):\n            return {"baru": False}\n',
       '        if False:\n            return {"baru": False}\n'),),
     (W + "test_pakai_replay_identik_tidak_menulis_lagi_walau_waktu_berbeda",
      W + "test_pakai_replay_tetap_dilayani_setelah_kedaluwarsa")),
    ("U4-pemakaian-tidak-membuat-status-dipakai",
     ((PURNA, "    if dipakai:\n        return VOUCHER_DIPAKAI\n", "    if False:\n        return VOUCHER_DIPAKAI\n"),),
     (B + "test_dipakai_didahulukan_dari_kedaluwarsa", W + "test_pakai_voucher_aktif_menulis_satu_baris_untuk_qris_dan_transfer")),
    # --- batal / kedaluwarsa ---
    ("K1-refund-tidak-membatalkan-voucher",
     ((PURNA, "    if direfund or pilihan == PILIHAN_UANG_KEMBALI:\n", "    if pilihan == PILIHAN_UANG_KEMBALI:\n"),),
     (B + "test_keadaan_direfund_voucher_batal_di_kedua_ledger", B + "test_batal_didahulukan_dari_dipakai_dan_kedaluwarsa")),
    ("K2-uang-kembali-tidak-membatalkan-voucher",
     ((PURNA, "    if direfund or pilihan == PILIHAN_UANG_KEMBALI:\n", "    if direfund:\n"),),
     (B + "test_pilihan_efektif_dan_voucher_batal_bila_uang_kembali",
      W + "test_pakai_ditolak_bila_sudah_memilih_uang_kembali")),
    ("K3-kedaluwarsa-baru-sesudah-batas",
     ((PURNA, "kini >= berlaku_hingga", "kini > berlaku_hingga"),),
     (B + "test_kedaluwarsa_tepat_di_batas_hari_voucher",
      W + "test_pakai_kedaluwarsa_tepat_di_batas_ditolak_satu_detik_sebelumnya_boleh")),
    ("K4-hitungan-hari-voucher-salah",
     ((PURNA, "d.tambah_jam(waktu_lunas, HARI_VOUCHER * JAM_PER_HARI)", "d.tambah_jam(waktu_lunas, HARI_VOUCHER * 23)"),),
     (B + "test_berlaku_hingga_tepat_hari_voucher_kali_dua_puluh_empat_jam_dari_waktu_lunas",
      B + "test_keadaan_qris_aktif_memuat_semua_turunan")),
    ("K5-direfund-tidak-dibaca-dari-ledger",
     ((PURNA, "    direfund = st.status_dari_db(kon, st.dict_order(baris), kini) == d.STATUS_DIREFUND\n",
       "    direfund = False\n"),),
     (B + "test_keadaan_direfund_voucher_batal_di_kedua_ledger", W + "test_pilihan_ditolak_bila_order_sudah_direfund")),
    ("K6-transfer-lunas-tidak-dibaca",
     ((PURNA, '    if not tb.fakta(kon, order_id)["lunas"]:\n', "    if True:\n"),),
     (B + "test_waktu_lunas_transfer_dari_transfer_lunas", B + "test_keadaan_transfer_aktif",
      W + "test_pakai_voucher_aktif_menulis_satu_baris_untuk_qris_dan_transfer")),
    # --- batas terlambat dan SLA ---
    ("L1-batas-terlambat-termasuk-sama-dengan",
     ((PURNA, "terlambat = lunas and terbit is None and kini > batas", "terlambat = lunas and terbit is None and kini >= batas"),),
     (B + "test_terlambat_tepat_di_batas_pilihan_bukan_terlambat_plus_satu_detik_terlambat",
      W + "test_pilihan_ditolak_bila_belum_terlambat_tepat_di_batas_boleh_satu_detik_sesudahnya")),
    ("L2-toleransi-terlambat-dibuang",
     ((PURNA, "d.tambah_jam(janji, JAM_TOLERANSI_TERLAMBAT))", "d.tambah_jam(janji, 0))"),),
     (B + "test_batas_pilihan_tepat_janji_ditambah_toleransi", B + "test_keadaan_qris_aktif_memuat_semua_turunan")),
    ("L3-terbit-tidak-menghentikan-terlambat",
     ((PURNA, "terlambat = lunas and terbit is None and", "terlambat = lunas and"),),
     (B + "test_terbit_membuat_tidak_terlambat_dan_tidak_bisa_pilih",)),
    ("L4-sla-tidak-beku-selalu-entri-terakhir",
     ((PURNA, "        if berlaku_dari <= waktu_lunas:\n            jam = jam_entri\n", "        jam = jam_entri\n"),),
     (B + "test_entri_sla_baru_tidak_menggeser_janji_order_lama", B + "test_sla_jam_memilih_entri_terakhir_yang_berlaku_dari_lebih_awal_atau_sama")),
    ("L5-sla-selalu-entri-pertama",
     ((PURNA, "        if berlaku_dari <= waktu_lunas:\n", "        if jam is None:\n"),),
     (B + "test_entri_sla_baru_berlaku_untuk_order_yang_lunas_sesudahnya",
      B + "test_sla_jam_memilih_entri_terakhir_yang_berlaku_dari_lebih_awal_atau_sama")),
    # --- pilihan terlambat ---
    ("P1-pilihan-tanpa-syarat-terlambat",
     ((PURNA, "            and terlambat\n", ""),),
     (W + "test_pilihan_ditolak_bila_belum_terlambat_tepat_di_batas_boleh_satu_detik_sesudahnya",
      B + "test_bisa_pilih_mati_bila_salah_satu_syarat_gagal")),
    ("P2-pilihan-setelah-voucher-dipakai",
     ((PURNA, "            and not dipakai\n", ""),),
     (W + "test_pilihan_ditolak_bila_voucher_sudah_dipakai", W + "test_pilihan_ditolak_bila_dipakai_walau_voucher_batal_menutupi_status",
      B + "test_bisa_pilih_mati_bila_salah_satu_syarat_gagal")),
    # Dua lapis (`terlambat` sudah memuat "terbit None"): keduanya dilucuti agar guard terlihat.
    ("P3-pilihan-setelah-laporan-terbit",
     ((PURNA, "            and terbit is None)", "            and True)"),
      (PURNA, "terlambat = lunas and terbit is None and", "terlambat = lunas and")),
     (W + "test_pilihan_ditolak_bila_laporan_sudah_terbit",)),
    ("P4-pilihan-setelah-refund",
     ((PURNA, "            and not direfund\n", ""),),
     (W + "test_pilihan_ditolak_bila_order_sudah_direfund", B + "test_bisa_pilih_mati_bila_salah_satu_syarat_gagal")),
    ("P5-pilihan-tidak-monoton",
     ((PURNA, "        if pilihan == PILIHAN_MENUNGGU and k.pilihan == PILIHAN_UANG_KEMBALI:\n", "        if False:\n"),),
     (W + "test_pilihan_menunggu_setelah_uang_kembali_konflik_walau_baris_menunggu_ada",)),
    ("P6-replay-pilihan-tidak-dilayani",
     ((PURNA, '        if _pilihan_sudah_ada(kon, order_id, pilihan):\n            return {"baru": False}\n',
       '        if False:\n            return {"baru": False}\n'),),
     (W + "test_pilihan_replay_identik_tanpa_tulis", W + "test_pilihan_uang_kembali_replay_tetap_dilayani_setelah_refund_dan_terbit")),
    # --- laporan terbit ---
    ("T1-terbit-tanpa-syarat-lunas",
     ((PURNA, '        if not k.lunas:\n            raise d.PesananKonflik("order belum lunas")\n', "        if False:\n            pass\n"),),
     (W + "test_terbit_ditolak_bila_belum_lunas",)),
    ("T2-terbit-setelah-refund",
     ((PURNA, '        if k.direfund:\n            raise d.PesananKonflik("order sudah direfund")\n', "        if False:\n            pass\n"),),
     (W + "test_terbit_ditolak_bila_sudah_direfund",)),
    ("T3-terbit-lebih-awal-dari-waktu-lunas",
     ((PURNA, "        if kini < k.waktu_lunas:\n", "        if False:\n"),),
     (W + "test_terbit_lebih_awal_dari_waktu_lunas_ditolak_tepat_waktu_lunas_boleh",)),
    ("T4-replay-terbit-tidak-dilayani",
     ((PURNA, '        if _waktu_terbit(kon, order_id) is not None:\n            return {"baru": False}\n',
       "        if False:\n            return {\"baru\": False}\n"),),
     (W + "test_terbit_replay_tanpa_tulis_walau_pelaku_dan_waktu_beda",)),
    # --- purna belum terpasang ---
    ("N1-tulis-tanpa-purna-tidak-ditolak",
     ((PURNA, '    if not terpasang(kon):\n        raise d.PesananKonflik("voucher purna belum dipasang")\n',
       "    if False:\n        pass\n"),),
     (W + "test_pakai_tanpa_purna_terpasang_ditolak_jelas_tanpa_tulis", W + "test_terbit_tanpa_purna_terpasang_ditolak_jelas",
      W + "test_pilihan_tanpa_purna_terpasang_ditolak_jelas")),
    ("N2-voucher-dipakai-tanpa-cek-tabel",
     ((PURNA, '    if not _ada_tabel(kon, "purna_voucher_pakai"):\n        return False\n', ""),),
     (B + "test_voucher_dipakai_false_bila_purna_belum_terpasang",
      F + "test_refund_tanpa_namespace_purna_tetap_bekerja_di_db_transfer")),
    ("N3-pilihan-efektif-tanpa-cek-tabel",
     ((PURNA, '    if not _ada_tabel(kon, "purna_pilihan_terlambat"):\n        return None\n', ""),),
     (B + "test_keadaan_netral_bila_purna_belum_terpasang",)),
    # --- guard refund-setelah-pakai: satu kasus per pintu masuk ---
    ("R1-guard-refund-dibuang-di-aturan-qris",
     ((ATURAN, "    if purna.voucher_dipakai(kon, order_id):\n", "    if False:\n"),),
     (F + "test_refund_qris_ditolak_setelah_voucher_dipakai_tanpa_tulis",)),
    ("R2-guard-refund-dibuang-di-aturan-transfer-admin",
     ((ATURAN, "    if purna.voucher_dipakai(kon, order_id):\n", "    if False:\n"),),
     (F + "test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu[admin]",)),
    ("R3-guard-refund-dibuang-di-aturan-transfer-langsung",
     ((ATURAN, "    if purna.voucher_dipakai(kon, order_id):\n", "    if False:\n"),),
     (F + "test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu[langsung]",)),
    ("R4-voucher-dipakai-selalu-false",
     ((PURNA, '    return kon.execute("SELECT 1 FROM purna_voucher_pakai WHERE order_id=?", (order_id,)).fetchone() is not None\n',
       "    return False\n"),),
     (F + "test_refund_qris_ditolak_setelah_voucher_dipakai_tanpa_tulis",
      F + "test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu[admin]",
      F + "test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu[langsung]",
      B + "test_voucher_dipakai_true_hanya_bila_ada_catatan_pemakaian")),
    ("R5-jalur-qris-melewati-pemeriksaan-layak",
     ((ATURAN, "    periksa_layak_refund(kon, isi[0], kini)\n    return False\n", "    return False\n"),),
     (F + "test_refund_qris_ditolak_setelah_voucher_dipakai_tanpa_tulis",)),
    ("R6-jalur-transfer-melewati-pemeriksaan-layak",
     ((TRANSFER, "    ra.periksa_layak_refund(kon, order_id, kini)\n    kon.execute(\"INSERT INTO transfer_refund",
       "    kon.execute(\"INSERT INTO transfer_refund"),),
     (F + "test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu[langsung]",
      F + "test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu[admin]")),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("purna-mutasi") / "repo"
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

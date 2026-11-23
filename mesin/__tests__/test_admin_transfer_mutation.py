"""Mutation guard admin transfer, jendela ulang, dan retensi pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil harus MERAH karena
asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di salinan yang sama. Pola
mutasi harus unik di berkasnya. Salinan tidak memuat `.venv`, cadangan, `*.db`, atau `*.json`.
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
V = "mesin/__tests__/test_admin_transfer_verifikasi.py::"
R = "mesin/__tests__/test_admin_transfer_rekening.py::"
A = "mesin/__tests__/test_admin_transfer_akses.py::"
D = "mesin/__tests__/test_pesanan_admin_transfer.py::"
U = "mesin/__tests__/test_pesanan_transfer_ulang.py::"
UH = "mesin/__tests__/test_pesanan_transfer_ulang_http.py::"
T = "mesin/__tests__/test_pesanan_retensi.py::"
VH, RH = "mesin/admin_verifikasi_http.py", "mesin/admin_rekening_http.py"
RP, DOM = "mesin/admin_rekening_pages.py", "mesin/pesanan_transfer.py"
UL, TH = "mesin/pesanan_transfer_ulang.py", "mesin/pesanan_transfer_http.py"
RT = "mesin/pesanan_retensi.py"
ST, AO = "mesin/pesanan_status.py", "mesin/pesanan_admin_order.py"
PA, PT = "mesin/pesanan_admin.py", "mesin/pesanan_admin_transfer.py"
TR = "mesin/__tests__/test_pesanan_transfer.py::"
TI = "mesin/__tests__/test_pesanan_transfer_integrasi.py::"
AOT = "mesin/__tests__/test_pesanan_admin_order.py::"

KASUS = (
    ("A-peran-admin-dilepas-pada-rute-verifikasi",
     ((VH, "    principal = h._principal_admin(penangan)\n    if principal is None:\n        h._tidak_ada(penangan)\n"
           "        return True\n    (_get_detail if", "    principal = penangan._principal()\n    if principal is None:\n"
           "        h._tidak_ada(penangan)\n        return True\n    (_get_detail if"),),
     (A + "test_nonadmin_404_identik_rute_tak_dikenal_tanpa_membaca_ledger_atau_berkas",)),
    ("B-admin-id-dari-form-bukan-sesi",
     ((VH, '    aksi.wajib_field(data, frozenset() if setuju else frozenset({"alasan"}))\n', ""),
      (VH, "pesanan_transfer.setujui(kon, order_id, principal.id_akun,",
       'pesanan_transfer.setujui(kon, order_id, data.get("admin_id", principal.id_akun),')),
     (V + "test_setujui_admin_id_dari_sesi_bukan_dari_form",)),
    ("C-alasan-kosong-diterima",
     ((VH, 'principal.id_akun, data["alasan"], alur.waktu_sekarang(),', 'principal.id_akun, data["alasan"] or "-", alur.waktu_sekarang(),'),),
     (V + "test_tolak_alasan_tak_sah_400_tanpa_efek",)),
    ("D-bukti-dilihat-tidak-diteruskan-pada-setujui",
     ((VH, "alur.waktu_sekarang(),\n                                     bukti_terakhir_id=dilihat)",
       "alur.waktu_sekarang())"),),
     (V + "test_setujui_bukti_baru_masuk_setelah_dilihat_ditolak_409_tanpa_efek",)),
    ("E-bukti-dilihat-tidak-diteruskan-pada-tolak",
     ((VH, "alur.waktu_sekarang(),\n                                   bukti_terakhir_id=dilihat)", "alur.waktu_sekarang())"),),
     (V + "test_tolak_bukti_baru_masuk_setelah_dilihat_409",)),
    ("F-domain-tidak-memeriksa-bukti-terakhir",
     ((DOM, "    if bukti_terakhir_id is not None and bukti_terakhir_id != hingga:\n", "    if False:\n"),),
     (D + "test_setujui_bukti_baru_masuk_sesudah_dilihat_ditolak_tanpa_tulis",
      D + "test_tolak_bukti_baru_masuk_sesudah_dilihat_ditolak_tanpa_tulis")),
    ("G-pratinjau-tanpa-nosniff-eksplisit-maupun-bawaan-server",
     ((VH, '"X-Content-Type-Options": "nosniff", ', ""),
      ("mesin/web.py", '            self.send_header("X-Content-Type-Options", "nosniff")\n', "            pass\n")),
     (V + "test_pratinjau_header_aman_nama_generik_dan_isi_persis",)),
    ("H-pratinjau-tanpa-csp-sandbox",
     ((VH, "CSP_BUKTI = \"default-src 'none'; sandbox\"", "CSP_BUKTI = \"default-src 'none'\""),),
     (V + "test_pratinjau_header_aman_nama_generik_dan_isi_persis",)),
    ("I-id-pratinjau-unicode-diterima",
     ((VH, "if not nilai.isascii() or not nilai.isdigit()", "if not nilai.isdigit()"),),
     (V + "test_pratinjau_id_tak_sah_404_identik_tanpa_membuka_berkas",)),
    ("J-bukti-dihapus-tetap-dibuka",
     ((VH, 'if meta is None or meta["dihapus"]:', "if meta is None:"),),
     (V + "test_pratinjau_bukti_ditandai_dihapus_404_ramah_tanpa_membuka_berkas",)),
    ("K-tipe-berkas-tidak-dicocokkan-dengan-isi",
     ((VH, ' or bukti_berkas.mime_dari_isi(isi) != meta["mime"]', ""),),
     (V + "test_pratinjau_isi_tidak_cocok_dengan_tipe_tersimpan_tidak_disajikan",)),
    ("L-isian-rekening-asing-diterima",
     ((RH, "    aksi.wajib_field(data, _FIELD)\n", ""),),
     (R + "test_field_kurang_atau_asing_400_tanpa_efek",)),
    ("M-nomor-rekening-tidak-ter-mask",
     ((RP, "    return KARAKTER_TOPENG * max(0, len(nomor) - DIGIT_TERAKHIR) + nomor[-DIGIT_TERAKHIR:]\n",
       "    return nomor\n"),),
     (R + "test_halaman_terisi_menampilkan_nomor_ter_mask_dan_form_dengan_token",)),
    ("N-snapshot-rekening-dari-kondisi-terkini-bukan-yang-dilihat",
     ((RH, 'operasi=tinjauan["op"], revisi=revisi,\n        sidik_awal=sidik,',
       'operasi=tinjauan["op"],\n        revisi=pesanan_rekening.baca(h._path_admin()).revisi,\n'
       '        sidik_awal=pesanan_rekening.sidik_konfigurasi(pesanan_rekening.baca(h._path_admin())),'),),
     (R + "test_konflik_revisi_form_lama_ditolak_409_ramah_tanpa_menimpa",
      R + "test_revisi_dan_sidik_hanya_dari_tinjauan_bertanda_tangan")),
    ("O-ulang-transfer-saat-midtrans-terbuka",
     ((TH, "    if dasar._runtime_bila_terbuka(penangan) is not None:\n        return False\n    if not _terima_form(penangan, principal, teks.AKSI_ULANG)",
       "    if not _terima_form(penangan, principal, teks.AKSI_ULANG)"),),
     (UH + "test_midtrans_terbuka_rute_tidak_ditangani_404_tanpa_efek",)),
    ("P-token-ulang-memakai-aksi-tagihan",
     ((TH, "_terima_form(penangan, principal, teks.AKSI_ULANG)", "_terima_form(penangan, principal, teks.AKSI_TAGIHAN)"),),
     (UH + "test_token_aksi_lain_ditolak_403_tanpa_efek",)),
    ("Q-ulang-transfer-tanpa-syarat-kedaluwarsa",
     ((UL, "        _wajib_kedaluwarsa(kon, order_id, akun_id, sekarang)\n    return", "        pass\n    return"),),
     (U + "test_hanya_kedaluwarsa_provider_mati_di_jendela_terbuka_tidak_membuka_jalur_transfer",)),
    ("R-retensi-menandai-sebelum-menghapus",
     ((RT, '    try:\n        terhapus = bukti_berkas.hapus_berkas(bukti["berkas"], folder)\n',
       '    pesanan_transfer.tandai_dihapus(kon, bukti["bukti_id"], sekarang)\n    try:\n'
       '        terhapus = bukti_berkas.hapus_berkas(bukti["berkas"], folder)\n'),),
     (T + "test_urutan_aman_berkas_dihapus_sebelum_bukti_ditandai",)),
    ("S-retensi-sementara-tanpa-ambang-umur",
     ((RT, "    if not entri.name.startswith(bukti_berkas.AWALAN_SEMENTARA):\n        return False\n    info = os.lstat(entri.path)\n"
           "    return stat.S_ISREG(info.st_mode) and info.st_mtime <= batas",
           "    if not entri.name.startswith(bukti_berkas.AWALAN_SEMENTARA):\n        return False\n    info = os.lstat(entri.path)\n"
           "    return stat.S_ISREG(info.st_mode)"),),
     (T + "test_sisa_sementara_lama_dibuang_yang_baru_dan_bukan_sementara_tidak",)),
    ("T-retensi-sementara-mengikuti-tautan",
     ((RT, "    if not entri.name.startswith(bukti_berkas.AWALAN_SEMENTARA):\n        return False\n    info = os.lstat(entri.path)\n"
           "    return stat.S_ISREG(info.st_mode) and info.st_mtime <= batas",
           "    if not entri.name.startswith(bukti_berkas.AWALAN_SEMENTARA):\n        return False\n    info = os.lstat(entri.path)\n"
           "    return info.st_mtime <= batas"),),
     (T + "test_sisa_sementara_bukan_berkas_biasa_tidak_disentuh",)),
    ("U-retensi-mengabaikan-ambang-30-hari",
     ((RT, "kedaluwarsa = pesanan_transfer.bukti_kedaluwarsa(kon, sekarang, hari)",
       'kedaluwarsa = pesanan_transfer.bukti_kedaluwarsa(kon, "2999-01-01T00:00:00", 1)'),),
     (T + "test_sapu_sebelum_30_hari_tidak_menyentuh_apa_pun",)),
    ("X-retensi-menghapus-bukti-belum-diputuskan",
     ((DOM, "             AND EXISTS(SELECT 1 FROM transfer_verifikasi v WHERE v.order_id=b.order_id\n"
            "                        AND v.bukti_hingga_id>=b.id AND v.dibuat<=?)%s ORDER BY b.id",
       "             AND ? IS NOT NULL%s ORDER BY b.id"),),
     (T + "test_sapu_tidak_pernah_menghapus_bukti_yang_belum_diputuskan",)),
    ("V-retensi-folder-salah-tetap-menandai",
     ((RT, "    if not folder.is_dir():\n        # Folder salah", "    if False:\n        # Folder salah"),),
     (T + "test_folder_tidak_ada_dengan_bukti_kedaluwarsa_tidak_menandai_apa_pun",)),
    ("W-retensi-hari-tidak-diteruskan-ke-penandaan",
     ((RT, 'bukti["bukti_id"], sekarang, hari)', 'bukti["bukti_id"], sekarang)'),),
     (T + "test_hari_lebih_pendek_diteruskan_ke_penandaan",)),
    ("YA-yatim-menghapus-berkas-yang-dirujuk-ledger",
     ((RT, " or entri.name in dirujuk:", ":"),),
     (T + "test_berkas_yang_dirujuk_ledger_tidak_dibuang_walau_lebih_tua_dari_24_jam",)),
    ("YB-yatim-tanpa-ambang-umur-24-jam",
     ((RT, "    if bukti_berkas.POLA_NAMA.fullmatch(entri.name) is None or entri.name in dirujuk:\n        return False\n    info = os.lstat(entri.path)\n    return stat.S_ISREG(info.st_mode) and info.st_mtime <= batas",
           "    if bukti_berkas.POLA_NAMA.fullmatch(entri.name) is None or entri.name in dirujuk:\n        return False\n    info = os.lstat(entri.path)\n    return stat.S_ISREG(info.st_mode)"),),
     (T + "test_yatim_ambang_tepat_24_jam_dibuang_kurang_sedetik_tidak",)),
    ("YC-yatim-mengikuti-tautan",
     ((RT, "    if bukti_berkas.POLA_NAMA.fullmatch(entri.name) is None or entri.name in dirujuk:\n        return False\n    info = os.lstat(entri.path)\n    return stat.S_ISREG(info.st_mode) and info.st_mtime <= batas",
           "    if bukti_berkas.POLA_NAMA.fullmatch(entri.name) is None or entri.name in dirujuk:\n        return False\n    info = os.lstat(entri.path)\n    return info.st_mtime <= batas"),),
     (T + "test_sapu_yatim_tidak_menyentuh_tautan_direktori_dan_nama_bukan_pola_bukti",)),
    ("YD-yatim-hanya-merujuk-baris-yang-belum-bertanda-hapus",
     ((RT, '"SELECT berkas FROM transfer_bukti"',
           '"SELECT berkas FROM transfer_bukti WHERE id NOT IN (SELECT bukti_id FROM transfer_bukti_hapus)"'),),
     (T + "test_berkas_dirujuk_baris_bertanda_hapus_tetap_tidak_dibuang_sebagai_yatim",)),
    ("YE-yatim-mengabaikan-pola-nama-bukti",
     ((RT, "    if bukti_berkas.POLA_NAMA.fullmatch(entri.name) is None or entri.name in dirujuk:\n",
           "    if entri.name in dirujuk:\n"),),
     (T + "test_sapu_yatim_tidak_menyentuh_tautan_direktori_dan_nama_bukan_pola_bukti",)),
    ("KA-kode-order-lunas-langsung-dipakai-ulang",
     ((DOM, "    return {b[0] for b in baris} | _nominal_lunas_ditahan(kon, kini)", "    return {b[0] for b in baris}"),),
     (TR + "test_kode_order_lunas_transfer_ditahan_29_hari",)),
    ("KB-kode-order-lunas-ditahan-tanpa-batas-waktu",
     ((DOM, '           WHERE tl.dibuat>?""", (batas,))', '           WHERE ? IS NOT NULL""", (batas,))'),),
     (TR + "test_kode_order_lunas_transfer_dilepas_sesudah_30_hari",)),
    ("KC-kode-semua-tagihan-order-lunas-ditahan",
     ((DOM, "JOIN transfer_tagihan t ON t.order_id=tl.order_id AND t.urutan=v.urutan",
            "JOIN transfer_tagihan t ON t.order_id=tl.order_id"),),
     (TR + "test_hanya_tagihan_yang_dibayar_ditahan_bukan_tagihan_jendela_lain",)),
    ("MA-tagihan-order-kedua-saat-akun-punya-order-menunggu",
     ((DOM, "        _wajib_tanpa_menunggu_lain(kon, order, kini)\n        kode =", "        kode ="),),
     (TR + "test_tagihan_ditolak_bila_akun_punya_order_lain_menunggu_verifikasi",)),
    ("MB-bukti-order-kedua-saat-akun-punya-order-menunggu",
     ((DOM, "        if status != d.STATUS_MENUNGGU_VERIFIKASI:\n            _wajib_tanpa_menunggu_lain(kon, order, kini)\n", ""),),
     (TR + "test_bukti_ditolak_bila_akun_punya_order_lain_menunggu_verifikasi",)),
    ("MC-guard-menunggu-memblokir-semua-status-bukan-hanya-menunggu",
     ((DOM, "        if st.status_dari_db(kon, st.dict_order(baris), kini) == d.STATUS_MENUNGGU_VERIFIKASI:\n            raise PesananMenungguLain()",
            "        raise PesananMenungguLain()"),),
     (TR + "test_order_lain_perlu_diperiksa_tidak_memblokir_akun",)),
    ("MD-guard-menunggu-melintasi-akun",
     ((DOM, "WHERE o.akun_id=? AND o.order_id<>? AND %s", "WHERE ? IS NOT NULL AND o.order_id<>? AND %s"),),
     (TR + "test_akun_lain_tidak_terpengaruh_order_menunggu_akun_pertama",)),
    ("RA-tagihan-ulang-saat-receipt-penyedia-sudah-ada",
     ((DOM, "        _wajib_tanpa_receipt_provider(kon, order_id)\n        ada =", "        ada ="),),
     (TR + "test_tagihan_ulang_ditolak_bila_receipt_penyedia_masuk_sesudah_tagihan_dibuat",)),
    ("JA-receipt-lunas-dan-bukti-menunggu-tetap-sudah-dibayar",
     ((ST, "    if dua_jalur(receipt_hasil, transfer_lunas, transfer_bukti):\n        return d.STATUS_PERLU_DIPERIKSA\n", ""),),
     (TR + "test_receipt_lunas_dengan_bukti_menunggu_berstatus_perlu_diperiksa",
      TI + "test_turunkan_status_dengan_fakta_transfer_sebelum_kedaluwarsa")),
    ("JB-dua-jalur-menghitung-bukti-ditolak",
     ((ST, "transfer_bukti == tb.BUKTI_MENUNGGU)", "transfer_bukti is not None)"),),
     (TR + "test_receipt_lunas_dengan_bukti_ditolak_tetap_sudah_dibayar",)),
    ("JC-penanda-dua-jalur-detail-dimatikan",
     ((AO, '"dua_jalur": _dua_jalur(kon, order_id),', '"dua_jalur": False,'),),
     (AOT + "test_detail_dua_jalur_bila_receipt_lunas_dan_bukti_menunggu",)),
    ("JD-penanda-dua-jalur-daftar-dimatikan",
     ((PA, '"dua_jalur": st.dua_jalur(baris["receipt_hasil"], bool(baris["transfer_lunas"]), baris["transfer_bukti"]),',
           '"dua_jalur": False,'),),
     (AOT + "test_detail_dua_jalur_bila_receipt_lunas_dan_bukti_menunggu",)),
    ("PA-penanda-menunggu-72-jam-dimatikan",
     ((PA, "    return diunggah <= d.tambah_jam(kini, -JAM_PENANDA_MENUNGGU)", "    return False"),),
     (AOT + "test_menunggu_lama_ditandai_mulai_72_jam_sejak_bukti_terakhir",)),
    ("PB-penanda-menunggu-batas-72-jam-eksklusif",
     ((PA, "    return diunggah <= d.tambah_jam(", "    return diunggah < d.tambah_jam("),),
     (AOT + "test_menunggu_lama_ditandai_mulai_72_jam_sejak_bukti_terakhir",)),
    ("PC-menunggu-lama-tidak-diurutkan-ke-atas",
     ((PA, 'key=lambda i: not i["menunggu_lama"]', "key=lambda i: 0"),),
     (AOT + "test_menunggu_lama_diurutkan_paling_atas_di_tab_menunggu",
      AOT + "test_menunggu_lama_diurutkan_juga_di_daftar_hanya_menunggu")),
    ("PD-bukti-dipakai-ulang-menghitung-order-sendiri",
     ((PT, "AND b2.order_id<>b1.order_id", "AND b2.order_id=b1.order_id"),),
     (AOT + "test_detail_menghitung_order_lain_dengan_sha256_bukti_sama",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("admin-transfer-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path, sasaran):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *sasaran, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=300)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    sasaran = sorted({t for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_admin_transfer_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

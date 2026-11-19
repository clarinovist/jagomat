"""Mutation guard jalur transfer rekening (tahap 2) pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard keamanan di salinan lalu menjalankan tes yang menjaganya:
hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang
sama harus HIJAU di salinan yang sama. Pola mutasi unik di berkasnya. Salinan tidak memuat
`.venv`, cadangan, `*.db`, atau `*.json` (tanpa data/sandi nyata). Pola sama dengan
`test_pesanan_http_mutation.py`.
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
GER = T + "test_pesanan_transfer_gerbang.py::"
H = T + "test_pesanan_transfer_http.py::"
B = T + "test_pesanan_transfer_bukti_http.py::"
BB = T + "test_bukti_berkas.py::"
BM = T + "test_bukti_multipart.py::"
PG = T + "test_pesanan_transfer_pages.py::"
GERBANG, THTTP, BERKAS = "mesin/pesanan_transfer_gerbang.py", "mesin/pesanan_transfer_http.py", "mesin/bukti_berkas.py"
MULTI, PHTTP, TPAGES = "mesin/bukti_multipart.py", "mesin/pesanan_http.py", "mesin/pesanan_transfer_pages.py"

KASUS = (
    ("T1-sakelar-longgar",
     ((GERBANG, '    return os.environ.get(NAMA_SAKELAR) == _NILAI_AKTIF',
       '    return os.environ.get(NAMA_SAKELAR, "").strip() in ("1", "true")'),),
     (GER + "test_hanya_tepat_satu_membuka_sakelar", H + "test_satu_syarat_hilang_semua_tertutup_fail_closed")),
    ("T2-funnel-dilewati",
     ((GERBANG, "not transfer_aktif() or not funnel_flag.funnel_aktif() or runtime is None",
       "not transfer_aktif() or runtime is None"),),
     (GER + "test_funnel_mati_menutup_gerbang", H + "test_satu_syarat_hilang_semua_tertutup_fail_closed")),
    ("T3-runtime-produksi-dilewati",
     ((GERBANG, "not transfer_aktif() or not funnel_flag.funnel_aktif() or runtime is None",
       "not transfer_aktif() or not funnel_flag.funnel_aktif()"),),
     (GER + "test_runtime_tidak_ada_menutup_gerbang", H + "test_satu_syarat_hilang_semua_tertutup_fail_closed")),
    ("T4-galat-rekening-tidak-fail-closed",
     ((GERBANG, "    except Exception:\n        return None\n", "    except ZeroDivisionError:\n        return None\n"),),
     (GER + "test_galat_apa_pun_menutup_gerbang", H + "test_satu_syarat_hilang_semua_tertutup_fail_closed")),
    ("T5-gerbang-post-dilewati",
     ((THTTP, "    if dasar.rekening_transfer(penangan) is None:\n        return False\n", ""),),
     (H + "test_satu_syarat_hilang_semua_tertutup_fail_closed",)),
    ("T6-tipe-bukan-dari-magic-bytes",
     ((BERKAS, "    for awalan, mime in _TIPE_MAGIC:\n        if isi.startswith(awalan):\n            return mime\n    return None\n",
       '    return "image/jpeg" if isi else None\n'),),
     (BB + "test_mime_ditolak_bila_magic_tidak_lengkap_atau_tipe_lain",
      B + "test_isi_teks_dinamai_jpg_dengan_content_type_jpeg_ditolak_415")),
    ("T7-magic-png-tidak-lengkap",
     ((BERKAS, '_PNG = b"\\x89PNG\\r\\n\\x1a\\n"', '_PNG = b"\\x89PNG"'),),
     (BB + "test_mime_ditolak_bila_magic_tidak_lengkap_atau_tipe_lain",
      B + "test_magic_bytes_tidak_lengkap_atau_tipe_lain_ditolak")),
    ("T8-nama-berkas-tidak-divalidasi",
     ((BERKAS, "    if type(nama) is not str or POLA_NAMA.fullmatch(nama) is None:\n        raise NamaBerkasTidakSah()",
       "    if type(nama) is not str:\n        raise NamaBerkasTidakSah()"),),
     (BB + "test_buka_dan_hapus_menolak_nama_tidak_valid",
      BB + "test_hapus_idempoten_dan_tidak_menyentuh_di_luar_folder")),
    ("T9-izin-berkas-longgar",
     ((BERKAS, "MODE_BERKAS = 0o600", "MODE_BERKAS = 0o644"),),
     (BB + "test_izin_folder_0700_dan_berkas_0600", B + "test_unggah_sah_menyimpan_berkas_dan_metadata_lalu_menunggu_verifikasi")),
    ("T10-folder-longgar-tidak-diperketat",
     ((BERKAS, "    os.chmod(folder, MODE_FOLDER)\n", ""),),
     (BB + "test_folder_longgar_yang_sudah_ada_diperketat",)),
    ("T11-rollback-berkas-dibuang",
     ((THTTP, "    except BaseException:\n        bukti_berkas.hapus_berkas(nama)\n        raise\n",
       "    except BaseException:\n        raise\n"),),
     (B + "test_catat_bukti_gagal_menghapus_berkas_dan_jawaban_tidak_bocor",
      B + "test_galat_tak_terduga_saat_catat_juga_menghapus_berkas")),
    ("T12-berkas-duplikat-tidak-dihapus",
     ((THTTP, '    if not hasil["baru"]:\n        bukti_berkas.hapus_berkas(nama)\n',
       '    if False:\n        bukti_berkas.hapus_berkas(nama)\n'),),
     (B + "test_berkas_sama_diunggah_dua_kali_tidak_menggandakan_baris_maupun_berkas",)),
    ("T13-token-bukti-tidak-divalidasi",
     ((THTTP, "    if not dasar.token_sah(principal, penangan._ambil_token(), teks.AKSI_BUKTI, form.token):",
       "    if False:"),),
     (B + "test_csrf_salah_403_dan_token_aksi_lain_tidak_berlaku",)),
    ("T14-token-tagihan-tidak-divalidasi",
     ((THTTP, '    if not dasar.token_sah(principal, penangan._ambil_token(), aksi, data["token"]):', "    if False:"),),
     (H + "test_tagihan_csrf_salah_403_tanpa_efek", H + "test_tagihan_token_aksi_lain_tidak_berlaku")),
    ("T15-peran-lain-lolos",
     ((THTTP, "from kontak_http import _alihkan, _baca_form, _principal_guru\n",
       "from kontak_http import _alihkan, _baca_form\n\n\n"
       "def _principal_guru(penangan):\n    return penangan._principal()\n\n\n"),),
     (H + "test_tagihan_admin_404_identik_dan_murid_ditahan_palang", B + "test_admin_404_identik_tanpa_efek")),
    ("T16-batas-ukuran-dilewati",
     ((THTTP, "    if len(isi) > BATAS_UKURAN_BUKTI:\n", "    if False:\n"),),
     (B + "test_berkas_satu_byte_lebih_dari_batas_ditolak_413_lewat_cek_ukuran",)),
    ("T17-batas-body-dibuang",
     ((THTTP, "penangan._baca_tubuh(BATAS_BODY_UNGGAH)", "penangan._baca_tubuh(10 ** 12)"),),
     (B + "test_content_length_raksasa_ditolak_sebelum_body_dibaca",)),
    ("T18-laju-ketat-unggah-dibuang",
     ((THTTP, "dasar._izinkan(penangan, principal, ketat=True, ember=EMBER_BUKTI)",
       "dasar._izinkan(penangan, principal, ketat=False, ember=EMBER_BUKTI)"),),
     (B + "test_batas_laju_unggah_429_tanpa_efek_tambahan",)),
    ("T19-transfer-saja-menghubungi-provider",
     ((THTTP, "alur.pesan(admin_store.BAWAAN, principal, None, runtime.config.merchant)",
       "alur.pesan(admin_store.BAWAAN, principal, dasar.pesanan_midtrans.dari_runtime(runtime), runtime.config.merchant)"),),
     (H + "test_pesan_transfer_saja_membuat_satu_order_tanpa_panggilan_provider",)),
    ("T20-transfer-membuka-qr-midtrans",
     ((PHTTP, "    if jalur == RUTE_QR and runtime is None:  # QRIS hanya bila gerbang Midtrans terbuka\n",
       "    if False:\n"),),
     (H + "test_transfer_terbuka_tidak_membuka_midtrans_qr_404_provider_tak_dipanggil",)),
    ("T21-transfer-saja-tombol-midtrans-tampil",
     ((PHTTP, "    if runtime is None:\n        return None\n    return (alur.AKSI_ULANG", "    return (alur.AKSI_ULANG"),),
     (H + "test_transfer_saja_halaman_hanya_transfer_tanpa_qris",)),
    ("T22-alasan-tolak-tidak-di-escape",
     ((TPAGES, "<strong>{_e(tampilan.alasan_tolak)}</strong>", "<strong>{tampilan.alasan_tolak}</strong>"),),
     (PG + "test_ditolak_menampilkan_alasan_ter_escape_dan_unggah_ulang",
      B + "test_ditolak_menampilkan_alasan_dan_unggah_ulang_kembali_menunggu")),
    ("T23-nominal-bukan-dari-tagihan",
     ((TPAGES, "    nominal = rupiah(tampilan.nominal)\n", "    nominal = rupiah(49000)\n"),),
     (PG + "test_tagihan_menampilkan_rekening_nominal_persis_batas_waktu_dan_form_unggah",
      H + "test_tagihan_dibuat_nominal_persis_rekening_dan_batas_waktu_tampil")),
    ("T24-multipart-bagian-ganda-diterima",
     ((MULTI, "        if nama is None or nama in diambil:\n", "        if nama is None:\n"),),
     (BM + "test_bentuk_tidak_sah_ditolak",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("pesanan-transfer-mutasi") / "repo"
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
def test_guard_transfer_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

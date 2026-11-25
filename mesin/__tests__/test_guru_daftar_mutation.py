"""Mutation guard BARU pendaftaran guru mandiri (butir QA #5): gerbang, form ketat, laju per IP, parser query, persetujuan.

Tiap kasus menonaktifkan satu guard di salinan source terisolasi dan memastikan tes terkait MERAH karena perilaku, lalu hijau
setelah dipulihkan (harness bersama: `harian_mutasi_kit`). Workspace asli tidak disentuh.

Tidak dimutasi (setara): cek "pendaftaran ditutup" di handler, karena `admin_registration.daftar_publik` mengecek konfigurasi yang
sama di dalam kunci registrasi.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES = "test_guru_daftar_http.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES)

HTTP = "guru_daftar_http.py"
GERBANG = "guru_daftar_gate.py"

# (nama, berkas, [(lama, baru), ...], ekspresi -k)
KASUS = (
    ("post_tanpa_gerbang_env", HTTP, [
        ("    if not gerbang.aktif():\n        _kirim_belum_dibuka(penangan, 403)\n        return\n",
         "    if False:\n        _kirim_belum_dibuka(penangan, 403)\n        return\n"),
    ], "test_gerbang_mati_get_tidak_menampilkan_form_guru_dan_post_tidak_membuat_akun"),
    ("get_tanpa_gerbang_env", HTTP, [
        ("    if not gerbang.aktif():\n        _kirim_belum_dibuka(penangan)\n        return\n",
         "    if False:\n        _kirim_belum_dibuka(penangan)\n        return\n"),
    ], "test_gerbang_mati_get_tidak_menampilkan_form_guru_dan_post_tidak_membuat_akun"),
    ("gerbang_menyala_bukan_nilai_1", GERBANG, [
        ('    return os.environ.get(NAMA_ENV, "0") == "1"', '    return os.environ.get(NAMA_ENV, "0") != "0"'),
    ], "test_hanya_nilai_persis_1_membuka_gerbang"),
    ("form_longgar_menerima_field_asing", HTTP, [
        ("    if set(data) != KUNCI_FORM:", "    if not KUNCI_FORM <= set(data):"),
    ], "test_field_asing_ditolak_tanpa_akun"),
    ("laju_per_ip_dimatikan", HTTP, [
        ("        if laju_masuk.sedang_diblokir(KUNCI_LAJU, kunci_ip):", "        if False:"),
    ], "test_laju_per_ip_menutup_keran_setelah_lima_akun"),
    ("laju_tidak_menghitung_akun_baru", HTTP, [
        ("        if akun_baru.baru:\n            laju_masuk.catat_gagal(KUNCI_LAJU, kunci_ip)",
         "        if False:\n            laju_masuk.catat_gagal(KUNCI_LAJU, kunci_ip)"),
    ], "test_laju_per_ip_menutup_keran_setelah_lima_akun"),
    ("query_peran_ganda_dianggap_guru", HTTP, [
        ("    return nilai == [NILAI]", "    return NILAI in nilai"),
    ], "test_daftar_biasa_dan_peran_lain_tidak_berubah"),
    ("persetujuan_tidak_diperiksa", HTTP, [
        ('    if data["setuju"] != "1":\n        return PESAN_SETUJU\n', ""),
    ], "test_isian_tidak_sah_ditolak_tanpa_akun"),
    ("sandi_pendek_diterima", HTTP, [
        ('    if len(data["sandi"]) < 8:\n        return PESAN_SANDI\n', ""),
    ], "test_isian_tidak_sah_ditolak_tanpa_akun"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_daftar_guru_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, tes):
    uji_mutasi(tmp_path, berkas, ganti, TES, tes, SALIN_TES)

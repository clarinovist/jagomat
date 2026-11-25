"""Mutation guard BARU tab Akun guru admin: penyaring orang tua lama, filter, aksi tinjauan, hapus untuk anggota lembaga.

Tiap kasus menonaktifkan satu guard di salinan source terisolasi; tes terkait harus MERAH karena perilaku, lalu hijau lagi.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_DOMAIN = "test_admin_guru_akun.py"
TES_HTTP = "test_admin_guru_akun_http.py"
KIT = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py")))
SALIN_TES = KIT + ("conftest.py", TES_DOMAIN, TES_HTTP, "test_admin_http_c.py")
D = "admin_guru_akun.py"
H = "admin_guru_akun_http.py"
P = "admin_guru_akun_pages.py"

KASUS = (
    ("orang_tua_lama_ikut_daftar", D, [
        ("or akun.id_akun in lama:", "or False:"),
    ], TES_DOMAIN, "test_hanya_guru_aktif_bukan_orang_tua_lama or test_satu_guru_hanya_untuk_guru_yang_tampil"),
    ("receipt_tanpa_profil_dianggap_orang_tua_lama", D, [
        ("and op in profil", "and op not in profil"),
    ], TES_DOMAIN, "test_hanya_guru_aktif_bukan_orang_tua_lama"),
    ("nonaktif_ikut_daftar", D, [
        ('akun_mentah = [a for a in akun_mentah if not a.get("dinonaktifkan") or guru_status.nonaktif_admin(a)]', "akun_mentah = list(akun_mentah)"),
    ], TES_DOMAIN, "test_hanya_guru_aktif_bukan_orang_tua_lama"),
    ("filter_asing_diterima", D, [
        ('    if saring not in SARING:\n        raise Q.InputQueryTidakSah("filter guru tidak sah")\n', ""),
    ], TES_DOMAIN, "test_filter_tak_dikenal_ditolak"),
    ("filter_belum_lembaga_terbalik", D, [
        ('        return g.lembaga is None\n    if saring == "di_lembaga"', '        return g.lembaga is not None\n    if saring == "di_lembaga"'),
    ], TES_DOMAIN, "test_filter"),
    ("satu_guru_ikut_dipotong", D, [
        ("    return next((g for g in _semua_guru(kon, akun_mentah, mentah) if g.id_akun == id_akun), None)",
         "    return next((g for g in daftar_guru(kon, akun_mentah, mentah) if g.id_akun == id_akun), None)"),
    ], TES_DOMAIN, "test_guru_di_luar_batas_tabel_tetap_bisa_dikelola"),
    ("tinjauan_menerima_aksi_lain", H, [
        ("    if aksi not in AKSI_TINJAU:\n        return h._tidak_ada(penangan)\n", ""),
    ], TES_HTTP, "test_tinjauan_dari_guru_menolak_target_salah_aksi_salah_dan_hapus_untuk_pemilik_lembaga"),
    ("token_hapus_untuk_anggota_lembaga_tetap_dibuat", H, [
        ("    if aksi == AKSI_HAPUS_LOGIN and guru.lembaga:", "    if False:"),
    ], TES_HTTP, "test_tinjauan_dari_guru_menolak_target_salah_aksi_salah_dan_hapus_untuk_pemilik_lembaga"),
    ("tautan_hapus_untuk_anggota_lembaga_tampil", P, [
        ("        if g.lembaga else\n        '<a class=\"admin-tautan admin-bahaya\"", "        if False else\n        '<a class=\"admin-tautan admin-bahaya\""),
    ], TES_HTTP, "test_kelola_menautkan_aksi_dan_menyembunyikan_hapus_untuk_guru_di_lembaga"),
    ("kelola_menerima_target_bukan_guru", H, [
        ("            if guru is None:\n                return h._tidak_ada(penangan)", "            if False:\n                return h._tidak_ada(penangan)"),
    ], TES_HTTP, "test_kelola_target_bukan_guru_atau_tak_ada_404"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_akun_guru_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)

"""Mutation guard BARU nonaktifkan guru (auth/sesi): revisi naik, sinyal lama, peran, tombstone, koordinator, target dari tinjauan.

Tiap kasus menonaktifkan satu guard di salinan source terisolasi; tes terkait harus MERAH karena perilaku, lalu hijau lagi.
"""
from pathlib import Path

import pytest

from harian_mutasi_kit import uji_mutasi

TES_UNIT = "test_guru_status.py"
TES_HTTP = "test_admin_guru_status_http.py"
KIT = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py")))
SALIN_TES = KIT + ("conftest.py", TES_UNIT, TES_HTTP, "test_admin_http_c.py", "test_admin_guru_akun_http.py")
S = "guru_status.py"
H = "admin_guru_status_http.py"
D = "admin_guru_akun.py"

KASUS = (
    ("revisi_tidak_naik_cookie_lama_hidup", S, [
        ('        target["revisi_auth"] = revisi_diharap + 1', '        target["revisi_auth"] = revisi_diharap'),
    ], TES_HTTP, "test_nonaktifkan_mengunci_cookie_lama_basic_dan_login_baru"),
    ("revisi_tidak_naik_unit", S, [
        ('        target["revisi_auth"] = revisi_diharap + 1', '        target["revisi_auth"] = revisi_diharap'),
    ], TES_UNIT, "test_nonaktifkan_mengunci_login_dan_menaikkan_revisi"),
    ("flag_dinonaktifkan_tidak_ditulis", S, [
        ('        target["dinonaktifkan"] = True\n        target[KUNCI_MARKA]', '        target[KUNCI_MARKA]'),
    ], TES_UNIT, "test_nonaktifkan_mengunci_login_dan_menaikkan_revisi"),
    ("peran_admin_murid_boleh_dinonaktifkan", S, [
        ('target.get("peran", PERAN_GURU) != PERAN_GURU:\n        raise StatusDitolak("akun bukan guru")', 'False:\n        raise StatusDitolak("akun bukan guru")'),
    ], TES_UNIT, "test_admin_dan_murid_ditolak_tanpa_efek"),
    ("revisi_basi_diterima", S, [
        ("        if auth.revisi_auth(target) != revisi_diharap:\n            raise StatusBerubah()\n", ""),
    ], TES_UNIT, "test_revisi_basi_menjadi_konflik_tanpa_efek"),
    ("nonaktif_dua_kali_diterima", S, [
        ('        if target.get("dinonaktifkan") is True:\n            raise StatusDitolak("guru sudah nonaktif")\n', ""),
    ], TES_UNIT, "test_nonaktifkan_dua_kali_ditolak"),
    ("tombstone_dianggap_nonaktif_admin", S, [
        ("            and isinstance(marka, dict) and type(marka.get(\"oleh\")) is str and type(marka.get(\"pada\")) is int)", "            and True)"),
    ], TES_UNIT, "test_marka_tidak_sah_tidak_dihitung_nonaktif_admin or test_tombstone"),
    ("tombstone_tampil_di_daftar_guru", D, [
        ('or guru_status.nonaktif_admin(a)]', 'or True]'),
    ], TES_HTTP, "test_tombstone_tidak_bisa_diaktifkan_lewat_rute"),
    ("nonaktif_tampil_di_chip_semua", D, [
        ("    if g.nonaktif:\n        return False\n", ""),
    ], TES_HTTP, "test_daftar_dan_detail_menampilkan_status_nonaktif_dan_chip"),
    ("koordinator_boleh_dinonaktifkan", H, [
        ("    if nonaktifkan and guru.peran_lembaga == G.PERAN_KOORDINATOR:\n        raise _Tolak(ui.COPY_TAHAN_KOORDINATOR % guru.lembaga)\n    return guru", "    return guru"),
    ], TES_HTTP, "test_koordinator_lembaga_tidak_bisa_dinonaktifkan"),
    ("id_form_tidak_dicocokkan_dengan_tinjauan", H, [
        ("data[ui.FIELD_ID] != id_akun or ", ""),
    ], TES_HTTP, "test_koordinator_lembaga_tidak_bisa_dinonaktifkan"),
    ("keadaan_tidak_cocok_diterima", H, [
        ("    if nonaktifkan and guru.nonaktif or not nonaktifkan and not guru.nonaktif:\n        raise _Tolak(ui.COPY_TIDAK_BISA)\n", ""),
    ], TES_HTTP, "test_token_basi_setelah_nonaktif_tidak_menulis_lagi or test_aktifkan_guru_aktif_ditolak"),
)


@pytest.mark.parametrize("nama,berkas,ganti,berkas_tes,tes", KASUS, ids=[k[0] for k in KASUS])
def test_guard_nonaktifkan_guru_merah_saat_dimatikan(tmp_path, nama, berkas, ganti, berkas_tes, tes):
    uji_mutasi(tmp_path, berkas, ganti, berkas_tes, tes, SALIN_TES)

"""Mutasi terisolasi proyeksi penghapusan/consent dan pemilihan hash CSP akun."""
from test_policy_mutation import test_guard_policy_merah_hijau as jalankan_mutasi
import pytest


@pytest.mark.parametrize('file,old,new,test,name', [
    ('account_pages.py', '    if alasan_hapus:', '    if False:',
     'test_account_audit.py', 'test_tombol_hapus_tidak_aktif_bila_ada_alasan'),
    ('sensor_http.py', '            elif izin is None:', '            elif True:',
     'test_account_audit.py', 'test_status_pilihan_dan_izin_efektif'),
    ('account_http.py', 'header_privat(skrip_sandi=SKRIP_AKUN)', 'header_privat(skrip_sandi="")',
     'test_account_audit_http.py', 'test_get_post_akun_memakai_header_privat'),
])
def test_guard_ui_dan_header_merah_hijau(tmp_path, file, old, new, test, name):
    jalankan_mutasi(tmp_path, file, old, new, test, name)

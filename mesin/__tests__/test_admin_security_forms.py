"""Token/form admin dengan kunci, cookie dan request sintetis."""
import io
from pathlib import Path
import sys
from email.message import Message
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import admin_security as s


def _akun():
    return {'peran': 'admin', 'id_akun': 'akun_sintetis', 'revisi_auth': 1, 'kunci': 'ab' * 32}


def test_tinjauan_terikat_aksi_metadata_actor_cookie_dan_waktu():
    akun = _akun()
    token = s.buat_tinjauan(akun, 'cookie-sintetis', 'reset', {'target_id': 'target'}, sekarang=100)
    data = s.periksa_tinjauan(akun, 'cookie-sintetis', token, sekarang=101)
    assert data['data'] == {'target_id': 'target'} and data['aksi'] == 'reset'
    for alternatif, cookie, nilai, waktu in (
        (akun, 'cookie-lain', token, 101),
        ({**akun, 'id_akun': 'akun_lain'}, 'cookie-sintetis', token, 101),
        ({**akun, 'revisi_auth': 2}, 'cookie-sintetis', token, 101),
        ({**akun, 'kunci': 'ac' * 32}, 'cookie-sintetis', token, 101),
        (akun, 'cookie-sintetis', token + 'x', 101),
        (akun, 'cookie-sintetis', token, 1000),
        (akun, 'cookie-sintetis', token, 99),
    ):
        with pytest.raises(PermissionError):
            s.periksa_tinjauan(alternatif, cookie, nilai, sekarang=waktu)


def test_basic_tetap_punya_tinjauan_terikat_generasi_dan_revisi():
    akun = _akun()
    token = s.buat_tinjauan(akun, None, 'cari', sekarang=100)
    assert s.periksa_tinjauan(akun, None, token, sekarang=101)['aksi'] == 'cari'
    with pytest.raises(PermissionError):
        s.periksa_tinjauan(akun, 'cookie-sintetis', token, sekarang=101)
    with pytest.raises(ValueError):
        s.buat_tinjauan(akun, None, 'reset', {'sandi': 'jangan-disimpan'})


def _request(raw=b'aksi=cari', **tambahan):
    header = Message()
    header['Host'] = 'localhost:1234'
    header['Content-Type'] = 'application/x-www-form-urlencoded'
    header['Content-Length'] = str(len(raw))
    for key, value in tambahan.items():
        header[key.replace('_', '-')] = value
    return SimpleNamespace(headers=header, rfile=io.BytesIO(raw))


@pytest.mark.parametrize('raw', [b'a=1&a=2', b'a=%ZZ', b'a=%ff', b'field', b'a=1&', b'\xff=1'])
def test_parser_invalid_ditolak(raw):
    with pytest.raises(ValueError):
        s.baca_form(_request(raw))


@pytest.mark.parametrize('header', [
    {'Origin': 'https://asing.invalid'}, {'Origin': 'null'},
    {'Origin': 'http://localhost:2345'}, {'Sec_Fetch_Site': 'cross-site'},
])
def test_parser_cross_site_ditolak(header):
    with pytest.raises(PermissionError):
        s.baca_form(_request(**header))


def test_origin_null_hanya_native_same_origin_dengan_token_tetap_wajib():
    assert s.baca_form(_request(Origin='null', Sec_Fetch_Site='same-origin')) == {'aksi': 'cari'}
    for situs in ('', 'same-site', 'cross-site', 'none'):
        with pytest.raises(PermissionError):
            s.baca_form(_request(Origin='null', Sec_Fetch_Site=situs))


def test_parser_boundary_content_type_length_dan_transfer():
    assert s.baca_form(_request(Origin='http://localhost:1234')) == {'aksi': 'cari'}
    for req in (_request(Transfer_Encoding='chunked'), _request(Content_Length='20'), _request(b'a=' + b'x' * 9000)):
        with pytest.raises(ValueError):
            s.baca_form(req)
    req = _request()
    req.headers.replace_header('Content-Type', 'text/plain')
    with pytest.raises(ValueError):
        s.baca_form(req)


@pytest.mark.parametrize('nama', ['Origin', 'Host', 'Sec-Fetch-Site', 'Content-Type'])
def test_header_transport_ganda_ditolak_sebelum_baca_body(nama):
    req = _request()
    if nama not in req.headers:
        req.headers[nama] = 'http://localhost:1234' if nama == 'Origin' else 'same-origin'
    req.headers[nama] = req.headers[nama]
    with pytest.raises((ValueError, PermissionError)):
        s.baca_form(req)
    assert req.rfile.tell() == 0


def test_header_privat_skrip_terbatas_dan_tidak_mengizinkan_inline_bebas():
    headers = s.header_privat(skrip_sandi='skrip-sintetis')
    assert headers['Cache-Control'] == 'no-store'
    assert headers['Referrer-Policy'] == 'no-referrer'
    assert 'script-src \'sha256-' in headers['Content-Security-Policy']
    assert "script-src 'unsafe-inline'" not in headers['Content-Security-Policy']
    assert "script-src 'none'" in s.header_privat()['Content-Security-Policy']

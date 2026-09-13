"""Unggahan admin strict melalui socket, tidak menulis body ke berkas."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import auth
import admin_store
from test_admin_http_c import server, _login, _minta, _hidden, SANDI_ADMIN


def _multipart(data):
    batas = 'jagomat-ujimultipart'
    hasil = b''
    for nama, isi, file in data:
        hasil += ('--%s\r\nContent-Disposition: form-data; name="%s"%s\r\n\r\n' % (
            batas, nama, '; filename="../../kontak-rahasia.csv"' if file else '')).encode()
        hasil += isi + b'\r\n'
    return hasil + ('--%s--\r\n' % batas).encode(), batas


def test_ukuran_body_multipart_dibatasi_sebelum_parse_csv_valid(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, halaman, _ = _minta(server, '/admin?section=keluarga', cookie=token)
    parts = [('csrf', _hidden(halaman, 'csrf').encode(), False),
             ('tinjauan', _hidden(halaman, 'tinjauan').encode(), False),
             ('reauth', SANDI_ADMIN.encode(), False), ('aksi', b'bulk_teacher_create', False),
             ('csv', b'pengguna\nBody-Valid\n', True)]
    raw, batas = _multipart(parts)
    raw = raw.replace(b'../../kontak-rahasia.csv', b'x' * 66000)
    before = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _minta(server, '/admin/bulk/impor', cookie=token, raw=raw,
        headers={'Content-Type': 'multipart/form-data; boundary=' + batas})
    assert kode == 400 and auth.BERKAS_SANDI.read_bytes() == before


@pytest.mark.parametrize('kasus', ['dua_file', 'dua_csrf', 'field_asing', 'file_reauth', 'tanpa_file', 'boundary_rusak', 'epilogue', 'encoding'])
def test_multipart_ambigu_ditolak_tanpa_mutasi(server, kasus):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, halaman, _ = _minta(server, '/admin?section=keluarga', cookie=token)
    parts = [('csrf', _hidden(halaman, 'csrf').encode(), False),
             ('tinjauan', _hidden(halaman, 'tinjauan').encode(), False),
             ('reauth', SANDI_ADMIN.encode(), False),
             ('aksi', b'bulk_teacher_create', False), ('csv', b'pengguna\nMultipart-Safe\n', True)]
    if kasus == 'dua_file': parts.append(parts[-1])
    elif kasus == 'dua_csrf': parts.append(parts[0])
    elif kasus == 'field_asing': parts.append(('sandi', b'rahasia-sintetis', False))
    elif kasus == 'file_reauth': parts[2] = ('reauth', SANDI_ADMIN.encode(), True)
    elif kasus == 'tanpa_file': parts.pop()
    elif kasus == 'encoding': parts[2] = ('reauth', b'\xff', False)
    raw, batas = _multipart(parts)
    if kasus == 'boundary_rusak': raw = raw[:-10]
    elif kasus == 'epilogue': raw += b'rahasia-sintetis'
    before = auth.BERKAS_SANDI.read_bytes(), admin_store.BAWAAN.read_bytes()
    kode, isi, headers = _minta(server, '/admin/bulk/impor', cookie=token, raw=raw,
        headers={'Content-Type': 'multipart/form-data; boundary=' + batas})
    assert kode == 400
    assert before == (auth.BERKAS_SANDI.read_bytes(), admin_store.BAWAAN.read_bytes())
    assert 'kontak-rahasia' not in isi and 'rahasia-sintetis' not in isi
    assert headers['Cache-Control'] == 'no-store'

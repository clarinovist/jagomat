"""Respons akun nyata: hash CSP exact, GET/POST, dan consent tanpa efek samping."""
import base64
import hashlib
import re

import pytest
import auth
import admin_store
import policy_schema
import policy_store
import sensor_http
from http_test_kit import ServerUji, SANDI_GURU
from test_subscription_http import FormParser


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    try:
        yield s
    finally:
        s.berhenti()


def cek_header(body, headers):
    scripts = re.findall(r'<script>(.*?)</script>', body, re.S)
    assert len(scripts) == 1
    digest = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    csp = headers['Content-Security-Policy']
    assert "script-src 'sha256-" + digest + "'" in csp
    assert "default-src 'none'" in csp and 'https:' not in csp
    assert headers['Cache-Control'] == 'no-store'
    assert headers['Referrer-Policy'] == 'no-referrer'
    assert 'fonts.googleapis.com' not in body


def test_get_post_akun_memakai_header_privat(server):
    for section in ('akun', 'siswa', 'langganan'):
        code, body, headers = server.minta('/akun?section=' + section, auth=('guru', SANDI_GURU))
        assert code == 200
        cek_header(body, headers)
    code, body, headers = server.minta('/akun', auth=('guru', SANDI_GURU),
        data=dict(aksi='sandi', lama='salah', baru='kata-sandi-baru-123', ulang='kata-sandi-baru-123'))
    assert code == 200 and 'Sandi lama salah' in body
    cek_header(body, headers)
    assert auth.periksa('guru', SANDI_GURU)


def test_cabut_tanpa_konfirmasi_ditolak_dan_status_berubah(server, monkeypatch):
    policy_schema.migrasikan(admin_store.BAWAAN)
    monkeypatch.setattr(sensor_http, 'SIAP', True)
    # Sesi terikat principal; semua endpoint berikut melalui socket nyata.
    import sessions
    principal = auth.autentikasi('guru', SANDI_GURU)
    token = sessions.buat_dari_principal(principal)
    form = FormParser(server.minta('/persetujuan', cookie=token)[1]).forms['/persetujuan']
    server.minta('/persetujuan', cookie=token, data={**form, 'policy_aksi':'semua'})
    row = policy_store.baca(admin_store.BAWAAN, principal.id_akun)
    assert row['alur'] == 1
    _, body, headers = server.minta('/akun?section=akun', cookie=token)
    cek_header(body, headers)
    assert 'Penggunaan tambahan aktif' in body
    cabut = FormParser(body).forms['/analitik/sensor-cabut']
    cabut.pop('konfirmasi', None)
    assert server.minta('/analitik/sensor-cabut', cookie=token, data=cabut)[0] == 400
    assert policy_store.baca(admin_store.BAWAAN, principal.id_akun) == row
    server.minta('/analitik/sensor-cabut', cookie=token, data={**cabut, 'konfirmasi':'1'})
    assert policy_store.baca(admin_store.BAWAAN, principal.id_akun)['alur'] == 0
    assert 'Penggunaan tambahan tidak diizinkan' in server.minta('/akun?section=akun', cookie=token)[1]

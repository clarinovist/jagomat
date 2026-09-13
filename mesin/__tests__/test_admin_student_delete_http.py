"""Saga hapus siswa melalui signed review HTTP, hanya data sintetis."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import admin_security
import admin_service
import admin_store
import auth
import database
import sessions
from test_admin_http_c import server, _minta, _login, _hidden, SANDI_ADMIN


def _review(server, token):
    kode, body, _ = _minta(server, '/admin/tinjau?aksi=student_delete&id=%d' % server.siswa_c, cookie=token)
    assert kode == 200
    return {'aksi': 'student_delete', 'csrf': _hidden(body, 'csrf'),
            'tinjauan': _hidden(body, 'tinjauan'), 'reauth': SANDI_ADMIN, 'konfirmasi': '1'}


def test_student_delete_login_receipt_replay_dan_snapshot_tanpa_nama(server):
    auth.tambah_akun('Login-Saga', 'sandi-login-sintetis', 'murid', siswa_id=server.siswa_c)
    murid = _login(server, 'Login-Saga', 'sandi-login-sintetis')
    admin = _login(server, 'Admin-C', SANDI_ADMIN)
    before = server.db.read_bytes()
    data = _review(server, admin)
    assert server.db.read_bytes() == before
    snapshot = admin_security.periksa_tinjauan(auth.cari_akun('Admin-C'), admin, data['tinjauan'])
    assert set(snapshot['data']) == {'siswa_id', 'tingkat', 'login_id', 'login_revisi'}
    assert 'Anak C' not in repr(snapshot) and 'Login-Saga' not in repr(snapshot)
    assert _minta(server, '/admin/siswa', cookie=admin, data=data)[0] == 303
    with server.buka() as kon:
        assert kon.execute('SELECT 1 FROM siswa WHERE id=?', (server.siswa_c,)).fetchone() is None
    assert auth.cari_akun('Login-Saga') is None and sessions.ambil_principal(murid) is None
    before = auth.BERKAS_SANDI.read_bytes()
    assert _minta(server, '/admin/siswa', cookie=admin, data=data)[0] == 303
    assert auth.BERKAS_SANDI.read_bytes() == before
    audit = admin_store.daftar_riwayat()
    assert sum(x.aksi == 'student_delete' and x.status == 'succeeded' for x in audit.item) == 1


def test_student_delete_confirmation_csrf_reauth_tanpa_efek(server):
    admin = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _review(server, admin)
    before = auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes(), admin_store.BAWAAN.read_bytes()
    for delta, expected in (({'konfirmasi': ''}, 400), ({'csrf': 'palsu'}, 403), ({'reauth': 'salah'}, 403)):
        assert _minta(server, '/admin/siswa', cookie=admin, data={**data, **delta})[0] == expected
        assert before == (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes(), admin_store.BAWAAN.read_bytes())


def test_student_delete_referensi_baru_setelah_review_ditolak_no_orphan(server):
    auth.tambah_akun('Login-Saga', 'sandi-login-sintetis', 'murid', siswa_id=server.siswa_c)
    admin = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _review(server, admin)
    with server.buka() as kon:
        database.ganti_level(kon, server.siswa_c, 'P4')
    before = auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes()
    assert _minta(server, '/admin/siswa', cookie=admin, data=data)[0] == 409
    assert before == (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes())
    assert auth.cari_akun('Login-Saga') is not None
    kode, isi, _ = _minta(server, '/admin?section=siswa&id=%d' % server.siswa_c, cookie=admin)
    assert kode == 200 and 'Tinjau hapus siswa kosong' not in isi


def test_student_delete_nama_sama_beda_keluarga_tidak_salah_hapus(server):
    with server.buka() as kon:
        lain = database.tambah_siswa(kon, 'Anak C', 'P3', pemilik='guru')
    auth.tambah_akun('Login-Saga-C', 'sandi-login-sintetis', 'murid', siswa_id=server.siswa_c)
    auth.tambah_akun('Login-Saga-Lain', 'sandi-login-sintetis', 'murid', siswa_id=lain)
    before = auth.cari_akun('Login-Saga-Lain')
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _review(server, token)
    assert _minta(server, '/admin/siswa', cookie=token, data=data)[0] == 303
    assert auth.cari_akun('Login-Saga-C') is None and auth.cari_akun('Login-Saga-Lain') == before
    with server.buka() as kon:
        assert kon.execute('SELECT nama FROM siswa WHERE id=?', (lain,)).fetchone()[0] == 'Anak C'


def test_student_delete_crash_sesudah_login_tidak_menyebut_sukses_replay_reconcile(server, monkeypatch):
    auth.tambah_akun('Login-Saga', 'sandi-login-sintetis', 'murid', siswa_id=server.siswa_c)
    admin = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _review(server, admin)
    asli = admin_service.hapus_siswa
    monkeypatch.setattr(admin_service, 'hapus_siswa', lambda *a, **k: asli(*a, failpoint='setelah_login_delete', **k))
    kode, isi, _ = _minta(server, '/admin/siswa', cookie=admin, data=data)
    assert kode in (409, 503) and 'storage sintetik' not in isi
    assert auth.cari_akun('Login-Saga') is None
    with server.buka() as kon:
        assert kon.execute('SELECT 1 FROM siswa WHERE id=?', (server.siswa_c,)).fetchone()
    kode, ringkas, _ = _minta(server, '/admin', cookie=admin)
    assert kode == 200 and 'Operasi perlu diperiksa' in ringkas and '1 belum pasti' in ringkas
    monkeypatch.setattr(admin_service, 'hapus_siswa', asli)
    assert _minta(server, '/admin/siswa', cookie=admin, data=data)[0] == 303

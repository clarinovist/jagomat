"""Form publik akun+profil memakai HTTP sintetis tanpa membocorkan payload."""
import html
import json
import re

import pytest
import admin_registration as reg
import admin_store
import auth
import database
from http_test_kit import ServerUji


@pytest.fixture
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    auth.tambah_akun('admin-sintetis','sandi-admin-sintetis','admin')
    reg.migrasikan_profil_registrasi(database.BAWAAN)
    yield s
    s.berhenti()


def form(server):
    kode,isi,_=server.minta('/daftar')
    assert kode==200
    token=re.search(r'name="token_form" value="([^"]+)"',isi).group(1)
    return dict(nama='ortu-form',sandi='sandi-form-sintetis',setuju='1',token_form=token,
                nama_anak='Profil Sintetis',kelas_sekolah='4',profil_parameter='P4')


def test_form_akun_profil_kelas_opsional_dan_get_tanpa_write(server):
    a=auth.BERKAS_SANDI.read_bytes();d=database.BAWAAN.read_bytes()
    kode,isi,_=server.minta('/daftar')
    assert kode==200 and auth.BERKAS_SANDI.read_bytes()==a and database.BAWAAN.read_bytes()==d
    assert 'name="nama_anak" required maxlength="40"' in isi
    assert '<label for="kelas-anak-daftar">Kelas sekolah (opsional)</label>' in isi
    assert 'name="profil_parameter"' not in isi and 'Pilih variasi soal' not in isi
    assert 'type="email"' not in isi and 'type="tel"' not in isi


def test_http_schema_missing_gagal_tertutup_get_tidak_membuat(server):
    with database.buka() as c:c.execute('DROP TABLE registrasi_profil_anak')
    data=form(server);awal=auth.BERKAS_SANDI.read_bytes()
    code,_,header=server.minta('/daftar',data=data)
    assert code==503 and 'Set-Cookie' not in header and auth.BERKAS_SANDI.read_bytes()==awal
    with database.buka() as c:
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='registrasi_profil_anak'").fetchone()
        assert not c.execute('SELECT 1 FROM siswa').fetchone()


def test_http_pasangan_dibuat_tanpa_enrollment_dan_replay(server):
    data=form(server);server.minta('/daftar',data=data)
    awal=auth.BERKAS_SANDI.read_bytes()
    assert auth.cari_akun(data['nama'])
    server.minta('/daftar',data=data)
    assert auth.BERKAS_SANDI.read_bytes()==awal
    with database.buka() as c:
        r=c.execute('SELECT * FROM siswa WHERE pemilik=?',(data['nama'],)).fetchall()
        assert len(r)==1 and r[0]['nama']==data['nama_anak']
    with admin_store.buka_baca(admin_store.BAWAAN) as c:assert not c.execute('SELECT 1 FROM langganan_enrollment').fetchone()


def test_http_nama_anak_hilang_ditolak_tanpa_akun(server):
    data=form(server);del data['nama_anak'];awal=auth.BERKAS_SANDI.read_bytes()
    code,_,header=server.minta('/daftar',data=data)
    assert code in (200,400) and 'Set-Cookie' not in header
    assert auth.BERKAS_SANDI.read_bytes()==awal
    with database.buka() as c:assert not c.execute('SELECT 1 FROM siswa').fetchone()


def test_http_crash_after_db_token_dipertahankan_retry(server,monkeypatch):
    data=form(server);asli=reg.daftar_dengan_profil
    def crash(*a,**kw):return asli(*a,**kw,failpoint='setelah_db')
    monkeypatch.setattr(reg,'daftar_dengan_profil',crash)
    code,isi,header=server.minta('/daftar',data=data)
    assert code==503 and 'Set-Cookie' not in header
    assert html.escape(data['token_form'],quote=True) in isi
    assert 'value="Profil Sintetis"' in isi
    assert auth.cari_akun(data['nama']) is None
    monkeypatch.setattr(reg,'daftar_dengan_profil',asli)
    server.minta('/daftar',data=data)
    assert auth.cari_akun(data['nama'])
    with database.buka() as c:assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==1


def test_error_nama_anak_escape_tidak_ke_url(server):
    data=form(server);data.update(nama_anak='<img src=x onerror=alert(1)>',profil_parameter='')
    _,isi,header=server.minta('/daftar',data=data)
    assert '&lt;img src=x onerror=alert(1)&gt;' in isi
    assert '<img src=x' not in isi and 'Location' not in header

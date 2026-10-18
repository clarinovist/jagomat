"""Satu klik awal, decline sah, stale dan replay tidak mengaktifkan ulang."""
import time
import auth
import admin_store
import database
import policy_store as s
import policy_schema
import sensor_http
import sensor_store
from test_admin_http_c import server,_minta,_login,SANDI_ADMIN
from test_subscription_http import FormParser
from http_test_kit import SANDI_GURU


def setup(monkeypatch):
    policy_schema.migrasikan(admin_store.BAWAAN)
    monkeypatch.setattr(sensor_http,'SIAP',True)


def test_existing_gate_decline_tidak_ditanya_lagi(server,monkeypatch):
    setup(monkeypatch)
    token=_login(server,'guru',SANDI_GURU)
    code,body,_=_minta(server,'/guru',cookie=token)
    assert code==200 and 'Satu persetujuan' in body
    form=FormParser(body).forms['/persetujuan']
    assert _minta(server,'/persetujuan',cookie=token,data={**form,'policy_aksi':'pilihan'})[0]==303
    assert 'Satu persetujuan' not in _minta(server,'/guru',cookie=token)[1]
    assert s.baca(admin_store.BAWAAN,auth.autentikasi('guru',SANDI_GURU).id_akun)['alur']==0
    assert _minta(server,'/syarat-penggunaan')[0]==200
    assert _minta(server,'/kebijakan-privasi')[0]==200


def test_stale_epoch_dan_cabut_form_ditolak(server,monkeypatch):
    setup(monkeypatch)
    token=_login(server,'guru',SANDI_GURU)
    form=FormParser(_minta(server,'/persetujuan',cookie=token)[1]).forms['/persetujuan']
    assert _minta(server,'/persetujuan',cookie=token,data={**form,'policy_aksi':'semua'})[0]==303
    p=auth.autentikasi('guru',SANDI_GURU)
    sensor_store.cabut(admin_store.BAWAAN,auth.BERKAS_SANDI,p)
    assert _minta(server,'/persetujuan',cookie=token,data={**form,'policy_aksi':'semua'})[0]==409
    assert sensor_store.izin(admin_store.BAWAAN,p.id_akun,sekarang=int(time.time())) is None
    fresh=FormParser(_minta(server,'/persetujuan',cookie=token)[1]).forms['/persetujuan']
    monkeypatch.setattr(s,'EPOCH','e'*32)
    assert _minta(server,'/persetujuan',cookie=token,data={**fresh,'policy_aksi':'semua'})[0]==403


def test_register_satu_form_dan_replay_tidak_menimpa(server,monkeypatch):
    import admin_registration
    setup(monkeypatch)
    admin_registration.migrasikan_profil_registrasi(database.BAWAAN)
    body=_minta(server,'/daftar')[1]
    assert '/syarat-penggunaan' in body and 'Setuju &amp; aktifkan semua' in body
    form=FormParser(body).forms['/daftar']
    form.update(nama='Policy-baru',sandi='policy-sandi-123',nama_anak='Sintetis',kelas_sekolah='',setuju='1',policy_aksi='semua')
    assert _minta(server,'/daftar',data=form)[0]==303
    p=auth.autentikasi('Policy-baru','policy-sandi-123')
    assert s.berlaku(s.baca(admin_store.BAWAAN,p.id_akun))
    sensor_store.cabut(admin_store.BAWAAN,auth.BERKAS_SANDI,p)
    _minta(server,'/daftar',data=form)
    assert s.baca(admin_store.BAWAAN,p.id_akun)['alur']==0


def test_cabut_sebelum_receipt_menolak_form_lama(server,monkeypatch):
    setup(monkeypatch)
    token=_login(server,'guru',SANDI_GURU)
    form=FormParser(_minta(server,'/persetujuan',cookie=token)[1]).forms['/persetujuan']
    account=FormParser(_minta(server,'/akun?section=akun',cookie=token)[1]).forms['/analitik/sensor-cabut']
    assert _minta(server,'/analitik/sensor-cabut',cookie=token,data={**account,'konfirmasi':'1'})[0]==303
    assert _minta(server,'/persetujuan',cookie=token,data={**form,'policy_aksi':'semua'})[0]==409
    row=s.baca(admin_store.BAWAAN,auth.autentikasi('guru',SANDI_GURU).id_akun)
    assert row['alur']==0 and not s.berlaku(row)


def test_policy_absent_tidak_memblokir_guru(server,monkeypatch):
    import sensor_schema
    sensor_schema.migrasikan(admin_store.BAWAAN)
    monkeypatch.setattr(sensor_http,'SIAP',True)
    token=_login(server,'guru',SANDI_GURU)
    assert 'Satu persetujuan' not in _minta(server,'/guru',cookie=token)[1]
    with admin_store.buka_baca() as c:
        assert not policy_schema.validasi(c)


def test_admin_tidak_digated_dan_post_anonim_ditolak(server,monkeypatch):
    setup(monkeypatch)
    token=_login(server,'Admin-C',SANDI_ADMIN)
    assert 'Satu persetujuan' not in _minta(server,'/admin',cookie=token)[1]
    assert _minta(server,'/persetujuan',data={})[0]==404

"""Milestone sesungguhnya lewat HTTP, tidak mengarang event dari histori."""
import time

import auth
import admin_store
import database
import sensor_http as h
import sensor_store as s
import sensor_schema
from test_launch_onboarding_journey import server, _jalan


def test_onboarding_hooks_berizin_dan_replay(server,monkeypatch):
    sensor_schema.migrasikan(admin_store.BAWAAN)
    # Test hook domain existing; journey persetujuan baru diuji test_policy_http.
    import policy_http
    monkeypatch.setattr(policy_http,'perlu',lambda p:False)
    monkeypatch.setattr(h,'SIAP',True)
    monkeypatch.setattr(s,'GAGAL',False)
    asli=auth.autentikasi
    terdaftar=set()
    def login(nama,sandi,*args,**kwargs):
        principal=asli(nama,sandi,*args,**kwargs)
        if principal and principal.peran=='guru' and nama.startswith('akses-') and principal.id_akun not in terdaftar:
            terdaftar.add(principal.id_akun)
            # Fixture consent sebelum perjalanan dimulai; bukan hook produksi.
            s.setuju(admin_store.BAWAAN,auth.BERKAS_SANDI,principal,hasil=True,chat=False,sekarang=int(time.time())-2)
        return principal
    monkeypatch.setattr(auth,'autentikasi',login)
    _jalan(server,'mobile',1)
    with s.buka(admin_store.BAWAAN) as c:
        codes={row[0] for row in c.execute('SELECT kode FROM sensor_event')}
        assert {'disiapkan','pekerjaan_disimpan','dikirim','dikonfirmasi','lembar_disajikan'} <= codes
        assert c.execute('SELECT COUNT(*) FROM sensor_hasil').fetchone()[0]==1
    assert not s.GAGAL

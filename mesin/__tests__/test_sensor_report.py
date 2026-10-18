"""Supresi keluarga dan status jujur sensor."""
import sensor_report as r
import sensor_store as s
import sensor_schema
import sensor_domain as d
from test_subscription_service import keluarga
from test_subscription_store import T0


def test_sampel_kecil_tidak_terlihat_dari_total(keluarga,monkeypatch):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    monkeypatch.setattr(s,'GAGAL',False)
    s.setuju(k.admin,k.auth,k.principal,hasil=True,chat=True,sekarang=T0)
    izin=s.izin(k.admin,k.principal.id_akun,sekarang=T0)
    for sesi in range(20):
        s.catat_sesi(k.admin,izin,sesi,kode='disiapkan',dibuat=T0+1,jalur='terpandu',sekarang=T0+2)
    out=r.laporan(k.admin,siap=True,sekarang=T0+3)
    assert out['status']=='sampel_kecil'
    assert out['tahap']==() and out['hasil'] is None
    assert r.laporan(k.admin,siap=False,sekarang=T0+3)['status']=='nonaktif'


def test_chat_berizin_tanpa_funnel_tetap_independen(keluarga,monkeypatch):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    monkeypatch.setattr(s,'GAGAL',False)
    with s.buka(k.admin,tulis=True) as c:
        for i in range(5):
            gen=format(i,'032x')
            c.execute('INSERT INTO sensor_peserta VALUES(?,?,?,?,?,?,?,?,?)',
                      ('akun_'+gen,gen,'f'*64,s.BOOT,T0,T0+d.RETENSI_CONSENT,d.CONSENT,0,1))
            c.execute('INSERT INTO sensor_chat VALUES(?,?,?,?)',(gen,'e'*64,'penjelasan',(T0+2)//3600))
    out=r.laporan(k.admin,siap=True,sekarang=T0+3)
    assert out['tahap']==()
    assert dict(out['chat'])['penjelasan']==5


def test_lima_keluarga_bukan_lima_episode(keluarga,monkeypatch):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    monkeypatch.setattr(s,'GAGAL',False)
    with s.buka(k.admin,tulis=True) as c:
        for i in range(5):
            gen=format(i,'032x')
            c.execute('INSERT INTO sensor_peserta VALUES(?,?,?,?,?,?,?,?,?)',
                      ('akun_'+gen,gen,'f'*64,s.BOOT,T0,T0+d.RETENSI_CONSENT,d.CONSENT,0,0))
    for i in range(5):
        izin=s.izin(k.admin,'akun_'+format(i,'032x'),sekarang=T0)
        s.catat_sesi(k.admin,izin,1,kode='disiapkan',dibuat=T0+1,jalur='terpandu',sekarang=T0+2)
        if i==0:
            s.catat_sesi(k.admin,izin,1,kode='dikirim',dibuat=T0+1,jalur='terpandu',sekarang=T0+2)
    out=r.laporan(k.admin,siap=True,sekarang=T0+3)
    assert dict(out['tahap'])['Latihan disiapkan']==5
    assert dict(out['tahap'])['Latihan dikirim'] is None
    with s.buka(k.admin,tulis=True) as c:
        c.execute("UPDATE sensor_episode SET jalur='manual'")
    assert r.laporan(k.admin,siap=True,sekarang=T0+3)['status']=='sampel_kecil'
    with s.buka(k.admin,tulis=True) as c:
        c.execute("UPDATE sensor_episode SET jalur='terpandu'")
        c.execute("INSERT INTO sensor_event SELECT peserta,token,'lembar_disajikan',? FROM sensor_episode",(T0//3600,))
    assert r.laporan(k.admin,siap=True,sekarang=T0+3)['tahap']==()
    s.gangguan()
    assert r.laporan(k.admin,siap=True,sekarang=T0+3)['tahap']==()

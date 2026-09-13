"""Revalidasi actor AI dengan provider palsu dan akun/temp sintetis."""
import threading
import pytest
import auth
import ai_store
import ai_service
import ai_admin_operations


@pytest.fixture
def siap(tmp_path,monkeypatch):
    akun=tmp_path/'akun.json'; ai=tmp_path/'ai.db'
    monkeypatch.setattr(auth,'BERKAS_SANDI',akun)
    monkeypatch.setenv('AI_BERKAS_DB',str(ai))
    monkeypatch.setenv('DEEPSEEK_API_KEY','sintetis-bukan-kunci')
    monkeypatch.setattr(ai_service.ai_policy,'deployment_mengizinkan',lambda _:True)
    auth.tambah_akun('pengelola','sandi-sintetis-123','admin',akun)
    ai_store.siapkan(ai)
    a=auth.cari_akun('pengelola',akun)
    return ai,akun,a


def _nilai(path):
    with ai_store.buka(path) as kon:
        utama,batas=ai_store.konfigurasi(kon)
        data={n:utama[n] for n in ('dihentikan','request_akun_harian','uji_harian','uji_cooldown_detik')}
        for fitur,b in batas.items():
            if fitur!='global':data['aktif_'+fitur]=b['aktif']
            data['harian_'+fitur]=b['batas_harian'];data['bulanan_'+fitur]=b['batas_bulanan']
    return data


def test_stale_actor_tidak_menulis_config_atau_reservasi(siap):
    ai,akun,a=siap
    auth.simpan_sandi('sandi-lain-sintetis','pengelola',akun)
    with pytest.raises(PermissionError):
        ai_service.ubah_pengaturan_admin(_nilai(ai),actor_id=a['id_akun'],actor_revisi=a['revisi_auth'],operasi_id='op_'+'a'*32,revisi=1)
    panggilan=[]
    with pytest.raises(PermissionError):
        ai_service.panggil_uji_admin(lambda:panggilan.append(1),actor_id=a['id_akun'],actor_revisi=a['revisi_auth'],operasi_id='op_'+'b'*32)
    with ai_store.buka(ai) as kon:
        assert kon.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]==0
        assert kon.execute('SELECT COUNT(*) FROM operasi_pengaturan_admin').fetchone()[0]==0
    assert panggilan==[]


def test_settings_replay_metadata_saja_dan_group_audit_satu_operasi(siap):
    ai,_,a=siap;nilai=_nilai(ai);nilai['uji_harian']=3;nilai['request_akun_harian']=4
    kwargs=dict(actor_id=a['id_akun'],actor_revisi=a['revisi_auth'],operasi_id='op_'+'c'*32,revisi=1)
    assert ai_service.ubah_pengaturan_admin(nilai,**kwargs)==2
    assert ai_service.ubah_pengaturan_admin(nilai,**kwargs)==2
    with pytest.raises(ai_store.Ditolak):
        ai_service.ubah_pengaturan_admin({**nilai,'uji_harian':5},**kwargs)
    hasil=ai_service.riwayat_admin()
    assert hasil.total==1 and hasil.item[0].operasi_id==kwargs['operasi_id']


def test_network_tidak_menahan_auth_lock_dan_reset_membuang_hasil(siap):
    ai,akun,a=siap;selesai=threading.Event()
    def ubah():
        auth.simpan_sandi('sandi-lain-sintetis','pengelola',akun);selesai.set()
    def provider():
        thread=threading.Thread(target=ubah);thread.start();thread.join(3)
        assert selesai.is_set(),'auth lock masih dipegang saat network'
        return {'status':'ok'}
    with pytest.raises(PermissionError):
        ai_service.panggil_uji_admin(provider,actor_id=a['id_akun'],actor_revisi=a['revisi_auth'],operasi_id='op_'+'d'*32)
    with ai_store.buka(ai) as kon:
        assert kon.execute('SELECT status FROM ledger').fetchone()[0]=='selesai'


def test_uji_replay_tidak_memanggil_provider_dua_kali(siap):
    _,_,a=siap;panggilan=[]
    def provider():panggilan.append(1);return {'status':'ok'}
    kwargs=dict(actor_id=a['id_akun'],actor_revisi=a['revisi_auth'],operasi_id='op_'+'e'*32)
    assert ai_service.panggil_uji_admin(provider,**kwargs)=={'status':'ok'}
    with pytest.raises(ai_service.AIUnavailable):ai_service.panggil_uji_admin(provider,**kwargs)
    assert panggilan==[1]

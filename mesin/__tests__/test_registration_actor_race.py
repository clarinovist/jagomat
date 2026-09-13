"""Pengaturan pendaftaran tidak boleh ditulis actor stale setelah reauth."""
import threading
import pytest
import auth
import admin_registration as r
import admin_store
from json_storage import transaksi_json
from test_admin_domain_c import storage, ACTOR, TOKEN  # noqa: F401


def _ubah(admin, akun):
    return r.ubah(admin,path_auth=akun,actor_revisi=2,operasi_id='op_'+'f'*32,
                  actor_id=ACTOR,revisi=1,dibuka=False,pesan_kode='closed_standard',token_tinjauan=TOKEN)


@pytest.mark.parametrize('rusak',['reset','hapus','peran','generasi'])
def test_actor_berubah_nol_config_journal_audit(storage,rusak):
    admin,akun,_,_=storage
    with transaksi_json(akun):
        mentah,daftar,_=auth._baca_akun_untuk_tulis(akun)
        if rusak=='reset':daftar[0]['revisi_auth']=3
        elif rusak=='hapus':daftar=daftar[1:]
        elif rusak=='peran':daftar[0]['peran']='guru'
        else:daftar[0]['id_akun']='akun_'+'c'*32
        auth._tulis_akun_atomik(auth._bungkus_akun(mentah,daftar),akun)
    sebelum=admin.read_bytes()
    with pytest.raises(PermissionError):_ubah(admin,akun)
    assert admin.read_bytes()==sebelum


def test_actor_sah_config_replay_tidak_ulang(storage):
    admin,akun,_,_=storage
    hasil=_ubah(admin,akun)
    assert hasil.status=='succeeded'
    before=admin.read_bytes()
    assert _ubah(admin,akun)==hasil
    assert admin.read_bytes()==before


def test_lock_auth_dipegang_sampai_config_commit(storage,monkeypatch):
    admin,akun,_,_=storage;mulai=threading.Event();selesai=threading.Event();threads=[]
    asli=admin_store.ubah_konfigurasi
    def reset():
        mulai.set();auth.naikkan_revisi_auth(ACTOR,akun);selesai.set()
    def commit(*a,**kw):
        thread=threading.Thread(target=reset);threads.append(thread);thread.start()
        assert mulai.wait(1)
        assert not selesai.wait(.1),'reset menyusup sebelum config commit'
        return asli(*a,**kw)
    monkeypatch.setattr(admin_store,'ubah_konfigurasi',commit)
    try:assert _ubah(admin,akun).status=='succeeded'
    finally:
        for thread in threads:thread.join(2)
    assert selesai.is_set()

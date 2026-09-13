"""Aksi metadata tetap tersedia setelah draft dibersihkan, tanpa credential."""
from pathlib import Path
import os
import pytest
import admin_store
import auth
from test_admin_http_c import server, _login, _minta, SANDI_ADMIN
from test_admin_http_d import _impor_preview, _batch_form


@pytest.mark.parametrize('mode',['serahkan','hentikan'])
def test_purge_sebelum_aksi_metadata_durable_tetap_berfungsi(server,mode):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    aliases=['Fallback-After-%02d'%i for i in range(11 if mode=='hentikan' else 1)]
    data=_batch_form(_impor_preview(server,token,aliases))
    code,body,_=_minta(server,'/admin/bulk/proses',cookie=token,data=data)
    assert code==200
    transient=Path(os.environ['ADMIN_TRANSIENT_DB']);transient.unlink()
    code,body,_=_minta(server,'/admin/bulk/hasil?id='+data['batch_id'],cookie=token)
    assert code==200
    form=_batch_form(body,mode)
    assert _minta(server,'/admin/bulk/'+mode,cookie=token,data=form)[0]==303
    assert _minta(server,'/admin/bulk/'+mode,cookie=token,data=form)[0]==303
    state=admin_store.baca_batch_durable(admin_store.BAWAAN,data['batch_id'])
    if mode=='serahkan':assert state.item[0].credential_status=='confirmed'
    else:
        assert state.batch.status=='stopped'
        assert auth.cari_akun(aliases[-1]) is None
    assert not transient.exists()

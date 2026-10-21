"""Mutasi in-memory pada guard yang benar-benar dipanggil tes kendali data."""
import inspect
import pytest

import assistant_manage as manage
import assistant_service as service
from test_assistant_manage import server
from test_assistant_manage import (
    test_revoke_rollback_dan_versi as cek_revoke,
    test_csrf_konfirmasi_dan_stale_tidak_menghapus as cek_form,
    test_owner_asing_dan_tidak_ada_404_identik as cek_owner,
    test_race_tidak_kirim_setelah_admission_dan_tidak_commit_late as cek_race,
)


def pasang(monkeypatch, module, nama, lama, baru):
    source = inspect.getsource(getattr(module,nama))
    assert source.count(lama)==1
    ruang = dict(module.__dict__)
    exec(compile(source.replace(lama,baru),'<mutasi-terisolasi>','exec'),ruang)
    monkeypatch.setattr(module,nama,ruang[nama])


def test_mutasi_versi_revoke_terdeteksi(server,monkeypatch):
    pasang(monkeypatch,manage,'cabut_semua',
           'if assistant_store.versi_persetujuan(kon, account_id) != versi:', 'if False:')
    with pytest.raises(pytest.fail.Exception,match='DID NOT RAISE'):
        cek_revoke(server,monkeypatch)


def test_mutasi_owner_resource_terdeteksi(server,monkeypatch):
    pasang(monkeypatch,manage,'_chat_milik',
           'return chat if sumber is not None else None', 'return chat')
    with pytest.raises(AssertionError):
        cek_owner(server)


def test_mutasi_csrf_terdeteksi(server,monkeypatch):
    from assistant_http_common import _baca_form
    source=inspect.getsource(_baca_form)
    import assistant_http_common as common
    ruang=dict(common.__dict__)
    old='if (not asal and situs != "same-origin") or silang or situs == "cross-site":'
    assert old in source
    exec(compile(source.replace(old,'if False:'),'<mutasi-csrf>','exec'),ruang)
    monkeypatch.setattr(manage,'_baca_form',ruang['_baca_form'])
    with pytest.raises(AssertionError):
        cek_form(server)


def test_mutasi_versi_hapus_terdeteksi(server,monkeypatch):
    from test_assistant_manage import store
    source=inspect.getsource(store.hapus_chat)
    lama='AND dihapus IS NULL AND versi = ?'
    assert source.count(lama)==1
    ruang=dict(store.__dict__)
    exec(compile(source.replace(lama,'AND dihapus IS NULL AND ? >= 0'),'<mutasi-hapus-versi>','exec'),ruang)
    monkeypatch.setattr(store,'hapus_chat',ruang['hapus_chat'])
    with pytest.raises(AssertionError):
        cek_form(server)


@pytest.mark.parametrize('aksi',['cabut','hapus'])
def test_mutasi_fence_sebelum_client_terdeteksi(tmp_path,monkeypatch,aksi):
    pasang(monkeypatch,service,'panggil_provider_default',
           'if pagar is not None:', 'if False:')
    # Post-network guard masih menolak simpan, tetapi test juga mengharuskan client nol.
    with pytest.raises(AssertionError):
        cek_race(tmp_path,monkeypatch,aksi,'admission')

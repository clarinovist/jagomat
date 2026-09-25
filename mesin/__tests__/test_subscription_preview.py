"""Launcher preview hanya membuat state sintetis baru pada loopback."""

import json
import os

import pytest
import midtrans_contract as m
import subscription_preview as p

CFG = m.Konfigurasi('sandbox', 'kunci-sintetis-bukan-credential', 'M_SINTETIS')


def lindungi_global(monkeypatch):
    for modul, nama in ((p.admin_store, 'BAWAAN'), (p.auth, 'BERKAS_SANDI'),
                        (p.database, 'BAWAAN'), (p.sessions, 'BERKAS_SESI')):
        monkeypatch.setattr(modul, nama, getattr(modul, nama))
    for nama in ('AI_BERKAS_DB', 'ADMIN_TRANSIENT_DB'):
        lama = os.environ.get(nama)
        if lama is None:
            monkeypatch.delenv(nama, raising=False)
        else:
            monkeypatch.setenv(nama, lama)


def test_preview_baru_loopback_dan_bukan_default_user(tmp_path, monkeypatch):
    lindungi_global(monkeypatch)
    akar = tmp_path / 'preview-baru'
    server, hasil = p.siapkan(CFG, akar=akar)
    try:
        assert hasil == akar and server.server_address[0] == '127.0.0.1'
        assert server.langganan_sandbox.akar == akar.resolve()
        login = json.loads((akar / 'login-sintetis.json').read_text())
        assert login['pengguna'] == 'ortu-sandbox' and len(login['sandi']) >= 18
        assert (akar / 'sandi.json').is_file() and (akar / 'belajar.db').is_file()
        assert (akar / 'admin-control.db').is_file() and not (akar / 'midtrans.rtf').exists()
    finally:
        server.server_close()


def test_preview_menolak_produksi_dan_direktori_berisi(tmp_path, monkeypatch):
    lindungi_global(monkeypatch)
    with pytest.raises(ValueError):
        p.siapkan(m.Konfigurasi('production','kunci-sintetis','M_SINTETIS'), akar=tmp_path/'prod')
    berisi=tmp_path/'berisi'; berisi.mkdir(); (berisi/'sandi.json').write_text('{}')
    with pytest.raises(ValueError):
        p.siapkan(CFG, akar=berisi)

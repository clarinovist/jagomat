"""Lifecycle janitor server: bounded helper, retry aman, thread ditutup."""
import sys
from types import SimpleNamespace

import pytest
import serve


class SinyalUji:
    def __init__(self, langkah):
        self.langkah = iter(langkah)
        self.interval = []
        self.disetel = False

    def wait(self, interval):
        self.interval.append(interval)
        return next(self.langkah)

    def set(self):
        self.disetel = True


def test_janitor_startup_periodik_dan_shutdown_tanpa_tidur(monkeypatch, tmp_path):
    panggilan = []
    monkeypatch.setitem(sys.modules, 'admin_maintenance', SimpleNamespace(
        jalankan=lambda *args: panggilan.append(args)))
    service = serve.PemeliharaanAdmin(tmp_path/'admin.db', tmp_path/'transient.db')
    service.berhenti = SinyalUji([False, False, True])
    service.mulai()
    service.tutup()
    assert len(panggilan) == 3
    assert all(x == (tmp_path/'admin.db', tmp_path/'transient.db') for x in panggilan)
    assert service.berhenti.interval == [60, 60, 60]
    assert not service.ulir.is_alive() and service.berhenti.disetel
    with pytest.raises(RuntimeError):
        service.mulai()


def test_galat_purge_retry_tetap_aman_tidak_membocorkan_detail(monkeypatch, tmp_path, capsys):
    panggilan = []
    def jalankan(*args):
        panggilan.append(args)
        if len(panggilan) == 1:
            raise OSError('rahasia-path-anak-sintetis')
    monkeypatch.setitem(sys.modules, 'admin_maintenance', SimpleNamespace(jalankan=jalankan))
    service = serve.PemeliharaanAdmin(tmp_path/'admin.db', tmp_path/'transient.db')
    service.berhenti = SinyalUji([False, True])
    service.mulai()
    service.tutup()
    assert len(panggilan) == 2 and not service.ulir.is_alive()
    pesan = capsys.readouterr().err
    assert 'Pemeliharaan admin tertunda' in pesan and 'rahasia' not in pesan


def test_periodik_sebelum900_lalu961_memakai_waktu_helper_bukan_cache_startup(monkeypatch, tmp_path):
    waktu = [1]
    terlihat = []
    monkeypatch.setitem(sys.modules, 'admin_maintenance', SimpleNamespace(jalankan=lambda *_: terlihat.append(waktu[0])))
    class JamEvent:
        def __init__(self): self.n = 0
        def wait(self, interval):
            assert interval == 60
            self.n += 1
            waktu[0] = 901 if self.n == 1 else 961
            return self.n > 2
        def set(self): pass
    service = serve.PemeliharaanAdmin(tmp_path/'admin.db', tmp_path/'transient.db')
    service.berhenti = JamEvent()
    service.mulai()
    service.tutup()
    assert terlihat == [1, 901, 961]


@pytest.mark.parametrize('terminasi', ['keyboard', 'sigterm', 'runtime_error'])
def test_main_memulai_janitor_setelah_bootstrap_dan_menutup_pada_keyboardinterrupt(monkeypatch, tmp_path, terminasi):
    import admin_store
    import database
    import auth
    import sessions
    urutan = []
    sinyal = []
    def pasang(_nomor, handler):
        sinyal.append(handler)
        return 'handler_lama'
    monkeypatch.setattr(serve.signal, 'signal', pasang)
    path_db = tmp_path/'belajar.db'
    database.siapkan(path_db)
    buka_asli = database.buka
    monkeypatch.setattr(database, 'BAWAAN', path_db)
    monkeypatch.setattr(database, 'buka', lambda path=None: buka_asli(path_db if path is None else path))
    monkeypatch.setattr(database, 'siapkan', lambda: urutan.append('belajar'))
    monkeypatch.setattr(serve.ai_store, 'siapkan', lambda: urutan.append('ai'))
    monkeypatch.setattr(serve.ai_store, 'purge', lambda: None)
    monkeypatch.setattr(admin_store, 'BAWAAN', tmp_path/'admin.db')
    monkeypatch.setattr(admin_store, 'siapkan', lambda: urutan.append('admin'))
    monkeypatch.setattr(serve.admin_students, 'siapkan', lambda _p: urutan.append('siswa'))
    monkeypatch.setattr(serve.admin_bulk, 'siapkan_transient', lambda _p: urutan.append('transient'))
    monkeypatch.setattr(sessions, 'bersihkan', lambda: None)
    monkeypatch.setattr(serve, 'siapkan_admin_dan_pemilik', lambda: None)
    monkeypatch.setattr(auth, 'wajib_sandi', lambda: False)
    monkeypatch.setattr(sys, 'argv', ['serve.py'])
    class Janitor:
        def __init__(self, path_admin, path_transient):
            assert path_admin == tmp_path/'admin.db'
        def mulai(self): urutan.append('janitor_mulai')
        def tutup(self): urutan.append('janitor_tutup')
    class Server:
        def __init__(self, *_args): urutan.append('server_buat')
        def serve_forever(self):
            urutan.append('layani')
            if terminasi == 'sigterm':
                sinyal[0](serve.signal.SIGTERM, None)
            if terminasi == 'runtime_error':
                raise RuntimeError('gagal pelayan sintetis')
            raise KeyboardInterrupt()
        def server_close(self): urutan.append('server_tutup')
    monkeypatch.setattr(serve, 'PemeliharaanAdmin', Janitor)
    monkeypatch.setattr(serve, 'ThreadingHTTPServer', Server)
    if terminasi == 'runtime_error':
        with pytest.raises(RuntimeError, match='gagal pelayan sintetis'):
            serve.main()
    else:
        assert serve.main() == 0
    assert sinyal[-1] == 'handler_lama'
    assert urutan == ['belajar', 'ai', 'admin', 'siswa', 'transient', 'server_buat',
                      'janitor_mulai', 'layani', 'janitor_tutup', 'server_tutup']


def test_shutdown_membangunkan_wait_bukan_menunggu60detik(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'admin_maintenance', SimpleNamespace(jalankan=lambda *_: None))
    service = serve.PemeliharaanAdmin(tmp_path/'admin.db', tmp_path/'transient.db')
    service.mulai()
    service.tutup()
    assert not service.ulir.is_alive()

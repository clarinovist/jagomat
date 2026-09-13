"""Regresi HTTP review R1–R4 dengan sesi aktual dan storage sintetis."""
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import admin_bulk
import admin_service
import admin_store
import auth
import sessions
from test_admin_http_c import server, _login, _minta, SANDI_ADMIN
from test_admin_http_d import _impor_preview, _batch_form


def _cabut(token, mode):
    if mode == 'logout':
        assert sessions.hapus(token)
    elif mode == 'expired':
        from json_storage import transaksi_json
        with transaksi_json(sessions.BERKAS_SESI):
            data = json.loads(sessions.BERKAS_SESI.read_text())
            data[token]['kedaluarsa'] = 1
            sessions.BERKAS_SESI.write_text(json.dumps(data))
    elif mode == 'deleted':
        from json_storage import transaksi_json
        with transaksi_json(auth.BERKAS_SANDI):
            data = json.loads(auth.BERKAS_SANDI.read_text())
            data['akun'] = [akun for akun in data['akun'] if akun['pengguna'] != 'Admin-C']
            auth.BERKAS_SANDI.write_text(json.dumps(data))
    elif mode == 'demotion':
        from json_storage import transaksi_json
        with transaksi_json(auth.BERKAS_SANDI):
            data = json.loads(auth.BERKAS_SANDI.read_text())
            for akun in data['akun']:
                if akun['pengguna'] == 'Admin-C':
                    akun['peran'] = 'guru'
                    akun['revisi_auth'] += 1
            auth.BERKAS_SANDI.write_text(json.dumps(data))
    else:
        assert auth.naikkan_revisi_auth(auth.cari_akun('Admin-C')['id_akun']) is not None


@pytest.mark.parametrize('mode', ['logout', 'expired', 'reset', 'demotion', 'deleted'])
def test_cookie_dicabut_sesudah_item1_hentikan_item2_dan_buang_credential(server, monkeypatch, mode):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    nama = ['R-Sesi-Satu', 'R-Sesi-Dua']
    preview = _impor_preview(server, token, nama)
    data = _batch_form(preview)
    asli = admin_service.buat_akun
    jumlah = []
    def mutasi(*args, **kwargs):
        hasil = asli(*args, **kwargs)
        jumlah.append(hasil)
        if len(jumlah) == 1:
            _cabut(token, mode)
        return hasil
    monkeypatch.setattr(admin_service, 'buat_akun', mutasi)
    kode, body, headers = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert len(jumlah) == 1
    assert auth.cari_akun(nama[0]) is not None and auth.cari_akun(nama[1]) is None
    assert kode == 403 and 'aria-label="Sandi baru"' not in body
    assert jumlah[0].credential_sekali not in body
    assert headers['Cache-Control'] == 'no-store'


def test_cookie_expired_saat_menunggu_lock_tidak_memulai_item(server, monkeypatch):
    import os
    from contextlib import contextmanager
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Wait-Alias']))
    lock_asli = admin_bulk.kunci_batch
    tiba = Event()
    @contextmanager
    def tunggu_lock(*args, **kwargs):
        tiba.set()
        with lock_asli(*args, **kwargs):
            yield
    monkeypatch.setattr(admin_bulk, 'kunci_batch', tunggu_lock)
    before = auth.BERKAS_SANDI.read_bytes()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with lock_asli(Path(os.environ['ADMIN_TRANSIENT_DB']), data['batch_id']):
            future = pool.submit(_minta, server, '/admin/bulk/proses', cookie=token, data=data)
            assert tiba.wait(3)
            _cabut(token, 'expired')
        kode, body, _ = future.result(timeout=5)
    assert kode == 403 and auth.BERKAS_SANDI.read_bytes() == before
    assert 'aria-label="Sandi baru"' not in body


def test_durable_hasil_tetap_confirmed_sesudah_draft_hilang_tanpa_alias_atau_sandi(server):
    import os
    import re
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Fallback-Alias']))
    kode, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200
    sandi = re.search(r'aria-label="Sandi baru"', body)
    assert sandi
    assert _minta(server, '/admin/bulk/serahkan', cookie=token, data=_batch_form(body, 'serahkan'))[0] == 303
    transient = Path(os.environ['ADMIN_TRANSIENT_DB'])
    transient.unlink()
    before = admin_store.BAWAAN.read_bytes()
    kode, hasil, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'Penyerahan telah dikonfirmasi' in hasil
    assert 'R-Fallback-Alias' not in hasil and 'aria-label="Sandi baru"' not in hasil
    assert 'action="/admin/bulk/proses"' not in hasil
    assert not transient.exists() and admin_store.BAWAAN.read_bytes() == before


def test_janitor_actual_expiry_draft_durable_tetap_dan_get_tidak_purge(server, monkeypatch):
    import os
    import time
    import admin_maintenance
    import serve
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Janitor-Alias']))
    transient = Path(os.environ['ADMIN_TRANSIENT_DB'])
    now = int(time.time())
    real = admin_maintenance.jalankan
    panggilan = []
    def putaran(path_admin, path_transient):
        panggilan.append(1)
        return real(path_admin, path_transient, sekarang=now + 961)
    monkeypatch.setattr(admin_maintenance, 'jalankan', putaran)
    class Stop:
        def wait(self, interval):
            assert interval == 60
            return True
        def set(self): pass
    service = serve.PemeliharaanAdmin(admin_store.BAWAAN, transient)
    service.berhenti = Stop()
    service.mulai()
    service.tutup()
    assert panggilan == [1]
    import sqlite3
    with sqlite3.connect(transient) as kon:
        assert kon.execute('SELECT COUNT(*) FROM draft_bulk').fetchone()[0] == 0
    before = admin_store.BAWAAN.read_bytes(), transient.read_bytes()
    kode, hasil, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'Draft alias sudah tidak tersedia' in hasil
    assert panggilan == [1] and before == (admin_store.BAWAAN.read_bytes(), transient.read_bytes())


def test_partial_purge_tidak_mengulang_sukses_atau_memulai_pending(server):
    import os
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    nama = ['R-Partial-%02d' % i for i in range(11)]
    data = _batch_form(_impor_preview(server, token, nama))
    kode, hasil, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200 and hasil.count('aria-label="Sandi baru"') == 10
    berikutnya = _batch_form(hasil)
    transient = Path(os.environ['ADMIN_TRANSIENT_DB'])
    transient.unlink()
    before = auth.BERKAS_SANDI.read_bytes()
    kode, body, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'Perlu pemeriksaan' in body and '10 berhasil' in body
    assert 'action="/admin/bulk/proses"' not in body and 'aria-label="Sandi baru"' not in body
    assert _minta(server, '/admin/bulk/proses', cookie=token, data=berikutnya)[0] in (400, 409)
    kode, replay, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode in (200, 400, 409) and 'aria-label="Sandi baru"' not in replay
    assert auth.BERKAS_SANDI.read_bytes() == before
    assert auth.cari_akun(nama[-1]) is None


def test_batchid_actor_token_path_dari_form_tidak_diterima(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Field-Alias']))
    before = auth.BERKAS_SANDI.read_bytes(), admin_store.BAWAAN.read_bytes()
    for nama in ('token_sesi', 'path_sesi', 'path_auth', 'actor_id', 'actor_revisi', 'session_binding'):
        kode, _, _ = _minta(server, '/admin/bulk/proses', cookie=token, data={**data, nama:'asing'})
        assert kode == 400
        assert before == (auth.BERKAS_SANDI.read_bytes(), admin_store.BAWAAN.read_bytes())


def test_pending_create_tanpa_draft_tidak_boleh_diproses_ulang(server):
    import os
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Lost-Alias']))
    transient = Path(os.environ['ADMIN_TRANSIENT_DB'])
    transient.unlink()
    kode, hasil, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'Perlu pemeriksaan' in hasil
    assert 'action="/admin/bulk/proses"' not in hasil
    assert 'R-Lost-Alias' not in hasil and not transient.exists()
    before = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode in (400, 409) and auth.BERKAS_SANDI.read_bytes() == before


def test_durable_fallback_sesi_lain_tetap404_dan_akun_tidak_dibuka(server):
    import os
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Private-Fallback']))
    Path(os.environ['ADMIN_TRANSIENT_DB']).unlink()
    lain = _login(server, 'Admin-C', SANDI_ADMIN)
    hasil = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=lain)
    tidak_ada = _minta(server, '/admin/bulk/hasil?id=batch_' + 'f'*32, cookie=lain)
    assert hasil[:2] == tidak_ada[:2] and hasil[0] == 404
    assert 'R-Private-Fallback' not in hasil[1]
    assert auth.cari_akun('R-Private-Fallback') is None


def test_handover_replay_operation_stabil_payload_changed_ditolak(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Handover-Satu']))
    _, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    handover = _batch_form(body, 'serahkan')
    assert _minta(server, '/admin/bulk/serahkan', cookie=token, data=handover)[0] == 303
    before = admin_store.BAWAAN.read_bytes()
    assert _minta(server, '/admin/bulk/serahkan', cookie=token, data=handover)[0] == 303
    assert admin_store.BAWAAN.read_bytes() == before
    assert _minta(server, '/admin/bulk/serahkan', cookie=token,
        data={**handover, 'item_ids': 'item_' + 'f'*32})[0] == 400
    assert admin_store.BAWAAN.read_bytes() == before


def test_hasil_get_tidak_memanggil_pemeliharaan(server, monkeypatch):
    import admin_maintenance
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-No-Get-Purge']))
    def dilarang(*_a, **_k):
        pytest.fail('GET tidak boleh menjalankan janitor')
    monkeypatch.setattr(admin_maintenance, 'jalankan', dilarang)
    assert _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)[0] == 200
    assert _minta(server, '/admin?section=riwayat&sumber=batch', cookie=token)[0] == 200


def test_audit_batch_durable_admin_sesi_baru_tanpa_mewarisi_draft(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Audit-Privat']))
    kode, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200
    assert _minta(server, '/admin/bulk/serahkan', cookie=token, data=_batch_form(body, 'serahkan'))[0] == 303
    sessions.hapus(token)
    baru = _login(server, 'Admin-C', SANDI_ADMIN)
    assert _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=baru)[0] == 404
    kode, audit, _ = _minta(server, '/admin?section=riwayat&sumber=batch', cookie=baru)
    assert kode == 200 and data['batch_id'] in audit
    kode, detail, _ = _minta(server, '/admin?section=riwayat&sumber=batch&id=' + data['batch_id'], cookie=baru)
    assert kode == 200 and 'confirmed' in detail
    assert 'R-Audit-Privat' not in detail and 'aria-label="Sandi baru"' not in detail
    assert 'action="/admin/bulk/' not in detail
    assert _minta(server, '/admin?section=riwayat&sumber=batch')[0] == 404


def test_janitor_hapus_draft_selesai_sebelum_render_fresh_tidak_menghilangkan_pasangan_akses(server, monkeypatch):
    import os
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Janitor-Fresh']))
    asli = admin_bulk.proses_kelompok
    def proses_lalu_purge(*args, **kwargs):
        hasil = asli(*args, **kwargs)
        Path(os.environ['ADMIN_TRANSIENT_DB']).unlink()
        return hasil
    monkeypatch.setattr(admin_bulk, 'proses_kelompok', proses_lalu_purge)
    kode, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200 and 'R-Janitor-Fresh' in body and body.count('aria-label="Sandi baru"') == 1
    kode, replay, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'R-Janitor-Fresh' not in replay and 'aria-label="Sandi baru"' not in replay


def test_cookie_dicabut_saat_render_hasil_credential_dibuang(server, monkeypatch):
    import admin_pages
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _batch_form(_impor_preview(server, token, ['R-Render-Satu']))
    asli = admin_pages.render_bulk_batch
    def render(*args, **kwargs):
        body = asli(*args, **kwargs)
        sessions.hapus(token)
        return body
    monkeypatch.setattr(admin_pages, 'render_bulk_batch', render)
    kode, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 403 and 'aria-label="Sandi baru"' not in body
    assert auth.cari_akun('R-Render-Satu') is not None


@pytest.mark.parametrize('jalur,helper', [('hentikan', 'hentikan'), ('serahkan', 'konfirmasi_penyerahan')])
@pytest.mark.parametrize('mode', ['logout', 'reset', 'demotion', 'deleted'])
def test_stop_handover_setelah_reauth_sesi_dicabut_nol_metadata(server, monkeypatch, jalur, helper, mode):
    import os
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    preview = _impor_preview(server, token, ['R-Meta-Satu', 'R-Meta-Dua'])
    if jalur == 'serahkan':
        kode, preview, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=_batch_form(preview))
        assert kode == 200
    data = _batch_form(preview, jalur)
    before = admin_store.BAWAAN.read_bytes(), Path(os.environ['ADMIN_TRANSIENT_DB']).read_bytes()
    asli = getattr(admin_bulk, helper)
    def cabut_lalu_write(*args, **kwargs):
        _cabut(token, mode)
        return asli(*args, **kwargs)
    monkeypatch.setattr(admin_bulk, helper, cabut_lalu_write)
    kode, body, _ = _minta(server, '/admin/bulk/' + jalur, cookie=token, data=data)
    assert kode == 403 and 'aria-label="Sandi baru"' not in body
    assert before == (admin_store.BAWAAN.read_bytes(), Path(os.environ['ADMIN_TRANSIENT_DB']).read_bytes())

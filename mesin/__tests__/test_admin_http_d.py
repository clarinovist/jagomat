"""Regresi HTTP C+D: bypass lama, AI reauth dan batch native."""
import os
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ai_service
import ai_store
import assistant_client
import auth
import admin_store
from test_admin_http_c import server, _minta, _login, _hidden, _unggah, SANDI_ADMIN


def test_akun_admin_forged_post_tidak_mengubah_siswa_login_atau_audit(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    sebelum = (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes(), admin_store.BAWAAN.read_bytes())
    for aksi in ("tingkat", "siswa_hapus", "akun_murid_tambah", "akun_murid_hapus", "akun_murid_sandi", "anak_baru"):
        kode, _, header = _minta(server, "/akun", cookie=token, data={
            "aksi": aksi, "siswa_id": str(server.siswa_c), "tingkat": "P6",
            "nama": "Anak C", "nama_akun": "Bypass-D", "sandi": "sandi-bypass-d",
            "baru": "sandi-bypass-d", "section": "siswa",
        })
        assert kode == 303 and header["Location"] == "/admin"
        assert (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes(), admin_store.BAWAAN.read_bytes()) == sebelum


def _form_ai(server, token, aksi):
    kode, isi, _ = _minta(server, "/admin/ai", cookie=token)
    assert kode == 200
    form = re.search(r'<form method="post" action="/admin/ai/%s">(.*?)</form>' % aksi, isi, re.S).group(1)
    return {"csrf": _hidden(form, "csrf"), "tinjauan": _hidden(form, "tinjauan"), "reauth": SANDI_ADMIN}


def test_ai_reauth_csrf_origin_dan_duplicate_tidak_admission(server, monkeypatch):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    data = dict(_form_ai(server, token, "uji"), konfirmasi="1")
    path = ai_service.path_store()
    awal = path.read_bytes()
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sintetis-bukan-key-asli')
    monkeypatch.setattr(__import__('ai_policy'), 'deployment_mengizinkan', lambda _f: True)
    panggilan = []
    monkeypatch.setattr(assistant_client, 'kirim', lambda *_a, **_k: panggilan.append(1) or {'status': 'ok'})
    for ubah, headers, kode_harap in (
        ({"reauth": "salah"}, {}, 403), ({"csrf": "basic:known-id"}, {}, 403),
        ({}, {"Origin": "https://asing.invalid"}, 403),
        ({"konfirmasi": ""}, {}, 400), ({"actor_id": "asing"}, {}, 400),
    ):
        kode, isi, tajuk = _minta(server, "/admin/ai/uji", cookie=token, data={**data, **ubah}, headers=headers)
        assert panggilan == []
        assert path.read_bytes() == awal
        assert kode == kode_harap
        assert tajuk["Cache-Control"] == "no-store" and tajuk["Referrer-Policy"] == "no-referrer"
        assert path.read_bytes() == awal
        assert "basic:known-id" not in isi
    assert _minta(server, '/admin/ai/uji', cookie=token, data=data)[0] == 303
    assert panggilan == [1]


def test_ai_tes_sintetis_replay_satu_provider_dan_sukses_terlihat(server, monkeypatch):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sintetis-bukan-key-asli")
    monkeypatch.setattr(__import__("ai_policy"), "deployment_mengizinkan", lambda _f: True)
    panggilan = []
    monkeypatch.setattr(assistant_client, "kirim", lambda *_a, **_k: panggilan.append(1) or {"status": "ok"})
    data = dict(_form_ai(server, token, "uji"), konfirmasi="1")
    kode, _, header = _minta(server, "/admin/ai/uji", cookie=token, data=data)
    assert kode == 303
    assert "Koneksi sintetis berhasil." in _minta(server, header["Location"], cookie=token)[1]
    kode, _, _ = _minta(server, "/admin/ai/uji", cookie=token, data=data)
    assert kode == 409 and panggilan == [1]
    with ai_store.buka(ai_service.path_store()) as kon:
        assert kon.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 1
        row = kon.execute("SELECT actor_id,status FROM audit_uji_admin").fetchone()
        assert row['actor_id'] == auth.cari_akun('Admin-C')['id_akun']
        assert row['status'] == 'selesai'
    kode, audit, _ = _minta(server, '/admin?section=riwayat&sumber=ai', cookie=token)
    assert kode == 200 and 'Tes sintetis AI' in audit
    assert 'sintetis-bukan-key-asli' not in audit and 'Balas JSON' not in audit


def _pilihan_data(isi, **extra):
    return {"csrf": _hidden(isi, "csrf"), "pilihan": _hidden(isi, "pilihan"), **extra}


def test_selection_lintas_halaman_filter_tetap_dan_hapus_native(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    for i in range(30):
        auth.tambah_akun('Pilih-%02d' % i, 'sandi-pilih-sintetis', 'guru')
    kode, isi, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
    assert kode == 200
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='cari', cari='Pilih-', halaman='1'))
    assert kode == 200
    pertama = auth.cari_akun('Pilih-00')['id_akun']
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='tambah', halaman_token=_hidden(isi, 'halaman_token'), target=pertama, cari='Pilih-'))
    assert kode == 200 and 'Pilihan: 1 akun' in isi
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='cari', cari='Pilih-', halaman='2'))
    assert kode == 200 and 'Pilihan: 1 akun' in isi
    kedua = auth.cari_akun('Pilih-29')['id_akun']
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='tambah', halaman_token=_hidden(isi, 'halaman_token'), target=kedua))
    assert kode == 200 and 'Pilihan: 2 akun' in isi
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='cari', cari='tidak-cocok'))
    assert kode == 200 and 'Pilihan: 2 akun' in isi and 'Tidak ada hasil.' in isi
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='hapus', hapus=pertama))
    assert kode == 200 and 'Pilihan: 1 akun' in isi
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='kosongkan'))
    assert kode == 200 and 'Pilihan: 0 akun' in isi


def test_selection_forged_admin_target_asing_duplicate_dan_session_tanpa_write(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, isi, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
    dasar = _pilihan_data(isi, mode='tambah', halaman_token=_hidden(isi, 'halaman_token'))
    before = auth.BERKAS_SANDI.read_bytes()
    for target in (auth.cari_akun('Admin-C')['id_akun'], 'akun_' + 'f'*32):
        kode, _, _ = _minta(server, '/admin/bulk/pilih', cookie=token, data={**dasar, 'target': target})
        assert kode == 400 and auth.BERKAS_SANDI.read_bytes() == before
    lain = _login(server, 'Admin-C', SANDI_ADMIN)
    assert _minta(server, '/admin/bulk/pilih', cookie=lain, data=dasar)[0] == 403
    import urllib.parse
    raw = urllib.parse.urlencode({**dasar, 'target': auth.cari_akun('Ortu-C')['id_akun']}).encode()
    raw += b'&target=' + auth.cari_akun('Ortu-C')['id_akun'].encode()
    assert _minta(server, '/admin/bulk/pilih', cookie=token, raw=raw)[0] == 400
    assert auth.BERKAS_SANDI.read_bytes() == before


def test_selection_batas100_tidak_memilih101_atau_aksi_kosong(server):
    import admin_security
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    for i in range(101):
        auth.tambah_akun('Batas-%03d' % i, 'sandi-batas-sintetis', 'guru')
    _, isi, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
    _, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='cari', cari='Batas-', halaman='1'))
    for halaman in range(1, 5):
        if halaman > 1:
            kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
                data=_pilihan_data(isi, mode='cari', cari='Batas-', halaman=str(halaman)))
            assert kode == 200
        kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
            data=_pilihan_data(isi, mode='halaman', cari='Batas-', halaman=str(halaman),
                              halaman_token=_hidden(isi, 'halaman_token')))
        assert kode == 200 and ('Pilihan: %d akun' % (halaman * 25)) in isi
    _, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='cari', cari='Batas-', halaman='5'))
    snapshot = admin_security.periksa_tinjauan(auth.cari_akun('Admin-C'), token, _hidden(isi, 'pilihan'))
    assert len(snapshot['data']['pilihan']) == 100
    before = auth.BERKAS_SANDI.read_bytes()
    assert _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(isi, mode='halaman', halaman_token=_hidden(isi, 'halaman_token')))[0] == 400
    assert auth.BERKAS_SANDI.read_bytes() == before
    _, kosong, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
    assert _minta(server, '/admin/bulk/pilih', cookie=token,
        data=_pilihan_data(kosong, mode='tinjau', aksi='account_password_reset', reauth=SANDI_ADMIN))[0] == 400


def test_selection_field_lintas_mode_ditolak_tanpa_write(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, isi, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
    before = auth.BERKAS_SANDI.read_bytes()
    for extra in ({'target': 'asing'}, {'hapus': 'asing'}, {'reauth': SANDI_ADMIN}, {'aksi': 'account_password_reset'}):
        assert _minta(server, '/admin/bulk/pilih', cookie=token,
            data=_pilihan_data(isi, mode='cari', **extra))[0] == 400
    assert auth.BERKAS_SANDI.read_bytes() == before


def test_upload_multipart_invalid_semua_ditolak_tanpa_draft_atau_echo(server):
    import sqlite3
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, isi, _ = _minta(server, '/admin?section=keluarga', cookie=token)
    data = {'csrf': _hidden(isi, 'csrf'), 'tinjauan': _hidden(isi, 'tinjauan'), 'reauth': SANDI_ADMIN, 'aksi': 'bulk_teacher_create'}
    before = auth.BERKAS_SANDI.read_bytes()
    for csv in (b'pengguna,sandi\nX,rahasia-sintetis\n', b'pengguna\n=SUM(A1)\n', b'pengguna\n\xff\n',
                b'pengguna\nabc\x00\n', b'pengguna\nOrtu-C\n', b'pengguna\n' + b'X'*65536,
                b'pengguna\n"kutip-rusak\n', b'pengguna\nX@example.test\n', b'pengguna\n'):
        kode, body, _ = _unggah(server, token, data, csv)
        assert kode == 400
        assert 'rahasia-sintetis' not in body and 'X@example.test' not in body
        assert auth.BERKAS_SANDI.read_bytes() == before
    with sqlite3.connect(os.environ['ADMIN_TRANSIENT_DB']) as kon:
        assert kon.execute('SELECT COUNT(*) FROM draft_bulk').fetchone()[0] == 0


def test_native_origin_null_same_origin_tetap_wajib_token_dan_search_pager(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    for i in range(27):
        auth.tambah_akun('Pager-%02d' % i, 'sandi-pager-sintetis', 'guru')
    _, body, _ = _minta(server, '/admin?section=keluarga', cookie=token)
    data = {'mode': 'cari', 'section': 'keluarga', 'csrf': _hidden(body, 'csrf'), 'cari': 'Pager-'}
    headers = {'Origin': 'null', 'Sec-Fetch-Site': 'same-origin'}
    assert _minta(server, '/admin', cookie=token, headers=headers, data={**data, 'csrf': 'palsu'})[0] == 403
    kode, body, _ = _minta(server, '/admin', cookie=token, headers=headers, data=data)
    assert kode == 200
    forms = re.findall(r'<form method="post" action="/admin">(.*?)</form>', body, re.S)
    assert forms
    pager = forms[-1]
    data = {name: _hidden(pager, name) for name in ('mode', 'section', 'csrf', 'cari', 'halaman')}
    kode, body, _ = _minta(server, '/admin', cookie=token, headers=headers, data=data)
    assert kode == 200 and 'Pager-26' in body and 'Pager-00' not in body
    assert not re.search(r'href="[^"]*Pager-', body)


def test_semua_rute_admin_nonadmin_privat_dan_tanpa_efek(server):
    from http_test_kit import SANDI_GURU, SANDI_MURID
    sebelum = (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes(), admin_store.BAWAAN.read_bytes())
    routes = ['/admin/bulk/pilih', '/admin/bulk/hasil?id=batch_asing', '/admin/bulk/templat',
              '/admin/asing', '/admin/akun', '/admin/siswa', '/admin/pendaftaran',
              '/admin/bulk/impor', '/admin/bulk/proses', '/admin/bulk/hentikan', '/admin/bulk/serahkan']
    for route in routes:
        for post in (False, True):
            results = []
            for principal in (None, ('guru', SANDI_GURU), ('feby', SANDI_MURID)):
                kode, body, headers = _minta(server, route, auth_basic=principal, data={'asing': 'x'} if post else None)
                assert kode == 404
                for k, v in (('Cache-Control', 'no-store'), ('Referrer-Policy', 'no-referrer'), ('X-Frame-Options', 'DENY')):
                    assert headers[k] == v
                results.append(body)
            assert results[0] == results[1] == results[2]
    assert (auth.BERKAS_SANDI.read_bytes(), server.db.read_bytes(), admin_store.BAWAAN.read_bytes()) == sebelum


def _impor_preview(server, token, nama):
    _, isi, _ = _minta(server, '/admin?section=keluarga', cookie=token)
    kode, preview, _ = _unggah(server, token, {
        'csrf': _hidden(isi, 'csrf'), 'tinjauan': _hidden(isi, 'tinjauan'),
        'reauth': SANDI_ADMIN, 'aksi': 'bulk_teacher_create',
    }, 'pengguna\n' + '\n'.join(nama) + '\n')
    assert kode == 200
    return preview


def _batch_form(isi, jalur='proses'):
    form = re.search(r'<form method="post" action="/admin/bulk/%s">(.*?)</form>' % jalur, isi, re.S).group(1)
    data = {'csrf': _hidden(form, 'csrf'), 'tinjauan': _hidden(form, 'tinjauan'),
            'batch_id': _hidden(form, 'batch_id'), 'reauth': SANDI_ADMIN, 'konfirmasi': '1'}
    if jalur == 'serahkan':
        data['item_ids'] = _hidden(form, 'item_ids')
    return data


def test_bulk_11_replay_tidak_maju_stop_results_privacy(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    names = ['Batch-D-%02d' % i for i in range(11)]
    preview = _impor_preview(server, token, names)
    assert all(n in preview for n in names)
    data = _batch_form(preview)
    kode, hasil, header = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200 and hasil.count('aria-label="Sandi baru"') == 10
    assert sum(auth.cari_akun(n) is not None for n in names) == 10
    sandi = re.findall(r'type="password" readonly value="([^"]+)"', hasil)
    assert len(set(sandi)) == 10 and all(len(x) >= 24 for x in sandi)
    assert header['Cache-Control'] == 'no-store'
    for path in (admin_store.BAWAAN, Path(os.environ['ADMIN_TRANSIENT_DB']), auth.BERKAS_SANDI):
        assert all(s.encode() not in path.read_bytes() for s in sandi)
    kode, replay, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200 and 'aria-label="Sandi baru"' not in replay
    assert sum(auth.cari_akun(n) is not None for n in names) == 10
    stop = _batch_form(hasil, 'hentikan')
    assert _minta(server, '/admin/bulk/hentikan', cookie=token, data=stop)[0] == 303
    kode, status, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'Dibatalkan' in status and all(s not in status for s in sandi)
    assert 'action="/admin/bulk/proses"' not in status
    assert sum(auth.cari_akun(n) is not None for n in names) == 10
    serahkan = _batch_form(status, 'serahkan')
    assert _minta(server, '/admin/bulk/serahkan', cookie=token, data=serahkan)[0] == 303
    status = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)[1]
    assert 'Penyerahan telah dikonfirmasi' in status and 'aria-label="Sandi baru"' not in status


@pytest.mark.parametrize('aksi', ['account_password_reset', 'account_session_revoke'])
def test_bulk_reset_revoke_target_pilihan_saja_cookie_lama_dicabut(server, aksi):
    from test_admin_http_c import SANDI_ORANG_TUA
    import sessions
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    cookie_target = _login(server, 'Ortu-C', SANDI_ORANG_TUA)
    before_other = auth.cari_akun('guru')
    before = auth.cari_akun('Ortu-C')
    _, isi, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
    kode, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token, data=_pilihan_data(isi,
        mode='tambah', target=before['id_akun'], halaman_token=_hidden(isi, 'halaman_token')))
    assert kode == 200
    kode, preview, _ = _minta(server, '/admin/bulk/pilih', cookie=token, data=_pilihan_data(isi,
        mode='tinjau', aksi=aksi, reauth=SANDI_ADMIN))
    assert kode == 200
    data = _batch_form(preview)
    kode, hasil, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200
    assert auth.cari_akun('Ortu-C')['revisi_auth'] == before['revisi_auth'] + 1
    assert auth.cari_akun('guru') == before_other
    assert sessions.ambil_principal(cookie_target) is None
    assert hasil.count('aria-label="Sandi baru"') == (1 if aksi == 'account_password_reset' else 0)
    assert _minta(server, '/admin/bulk/proses', cookie=token, data=data)[0] == 200
    assert auth.cari_akun('Ortu-C')['revisi_auth'] == before['revisi_auth'] + 1


def test_bulk_seluruh_batch_preflight_item11_invalid_nol_akun(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    names = ['Preflight-D-%02d' % i for i in range(11)]
    preview = _impor_preview(server, token, names)
    auth.tambah_akun(names[-1], 'sandi-target-berubah', 'guru')
    before = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=_batch_form(preview))
    assert kode in (400, 409)
    assert auth.BERKAS_SANDI.read_bytes() == before
    assert all(auth.cari_akun(n) is None for n in names[:-1])


def test_bulk_partial_uncertain_menghentikan_kelompok_tidak_replay_sukses(server, monkeypatch):
    import admin_service
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    names = ['Partial-D-%02d' % i for i in range(3)]
    preview = _impor_preview(server, token, names)
    data = _batch_form(preview)
    asli = admin_service.buat_akun
    calls = []
    def gagal_kedua(*args, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise admin_service.OperasiTidakDapatDilanjutkan('uncertain sintetik')
        return asli(*args, **kw)
    monkeypatch.setattr(admin_service, 'buat_akun', gagal_kedua)
    kode, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200 and 'Tak pasti' in body
    assert body.count('aria-label="Sandi baru"') == 1
    assert 'action="/admin/bulk/proses"' not in body
    assert sum(auth.cari_akun(n) is not None for n in names) == 1 and len(calls) == 2
    kode, replay, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
    assert kode == 200 and 'aria-label="Sandi baru"' not in replay and len(calls) == 2
    kode, status, _ = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=token)
    assert kode == 200 and 'Tak pasti' in status and 'Belum diproses' in status


def test_bulk_100_create_10_kelompok_unik_dan_replay_aman(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    names = ['Ratus-D-%03d' % i for i in range(100)]
    body = _impor_preview(server, token, names)
    for kelompok in range(10):
        data = _batch_form(body)
        kode, body, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=data)
        assert kode == 200 and body.count('aria-label="Sandi baru"') == 10
        assert sum(auth.cari_akun(n) is not None for n in names) == (kelompok + 1) * 10
    assert 'action="/admin/bulk/proses"' not in body
    before = auth.BERKAS_SANDI.read_bytes()
    assert _minta(server, '/admin/bulk/proses', cookie=token, data=data)[0] == 200
    assert auth.BERKAS_SANDI.read_bytes() == before


def test_bulk_murid_reset_role_tetap_siswa_tidak_berubah(server):
    auth.tambah_akun('Bulk-Murid-D', 'sandi-anak-bulk-d', 'murid', siswa_id=server.siswa_c)
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    target = auth.cari_akun('Bulk-Murid-D')
    _, isi, _ = _minta(server, '/admin/bulk/pilih?peran=murid', cookie=token)
    _, isi, _ = _minta(server, '/admin/bulk/pilih', cookie=token, data=_pilihan_data(isi,
        mode='tambah', target=target['id_akun'], halaman_token=_hidden(isi, 'halaman_token')))
    kode, preview, _ = _minta(server, '/admin/bulk/pilih', cookie=token, data=_pilihan_data(isi,
        mode='tinjau', aksi='account_password_reset', reauth=SANDI_ADMIN))
    assert kode == 200
    before = server.db.read_bytes()
    kode, hasil, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=_batch_form(preview))
    assert kode == 200 and hasil.count('aria-label="Sandi baru"') == 1
    baru = auth.cari_akun('Bulk-Murid-D')
    assert baru['id_akun'] == target['id_akun'] and baru['peran'] == 'murid'
    assert baru['revisi_auth'] == target['revisi_auth'] + 1 and server.db.read_bytes() == before


def test_bulk_handover_tidak_boleh_mengubah_item_di_luar_tinjauan(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    preview = _impor_preview(server, token, ['Handover-D'])
    _, hasil, _ = _minta(server, '/admin/bulk/proses', cookie=token, data=_batch_form(preview))
    data = _batch_form(hasil, 'serahkan')
    before = Path(os.environ['ADMIN_TRANSIENT_DB']).read_bytes()
    assert _minta(server, '/admin/bulk/serahkan', cookie=token, data={**data, 'item_ids': 'item_' + 'f'*32})[0] == 400
    assert Path(os.environ['ADMIN_TRANSIENT_DB']).read_bytes() == before


def test_bulk_upload101_ditolak_sebelum_draft(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, isi, _ = _minta(server, '/admin?section=keluarga', cookie=token)
    before = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _unggah(server, token, {
        'csrf': _hidden(isi, 'csrf'), 'tinjauan': _hidden(isi, 'tinjauan'),
        'reauth': SANDI_ADMIN, 'aksi': 'bulk_teacher_create',
    }, 'pengguna\n' + '\n'.join('Lebih-D-%03d' % i for i in range(101)) + '\n')
    assert kode == 400 and auth.BERKAS_SANDI.read_bytes() == before


def test_bulk_owner_session_stale_csrf_konfirmasi_tanpa_write(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    preview = _impor_preview(server, token, ['Owner-Batch-D'])
    data = _batch_form(preview)
    before = auth.BERKAS_SANDI.read_bytes()
    for delta, status in (({'reauth': 'salah'}, 403), ({'csrf': 'palsu'}, 403), ({'konfirmasi': ''}, 400)):
        assert _minta(server, '/admin/bulk/proses', cookie=token, data={**data, **delta})[0] == status
    lain = _login(server, 'Admin-C', SANDI_ADMIN)
    asing = _minta(server, '/admin/bulk/hasil?id=' + data['batch_id'], cookie=lain)
    hilang = _minta(server, '/admin/bulk/hasil?id=batch_' + 'f'*32, cookie=lain)
    assert asing[:2] == hilang[:2] and asing[0] == 404
    assert auth.BERKAS_SANDI.read_bytes() == before


def test_ai_csrf_signature_tamper_dan_duplicate_tanpa_write(server, monkeypatch):
    import urllib.parse
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = dict(_form_ai(server, token, 'uji'), konfirmasi='1')
    awal = ai_service.path_store().read_bytes()
    badan, signature = data['csrf'].split('.')
    data_palsu = dict(data, csrf=badan + '.' + ('A' if signature[0] != 'A' else 'B') + signature[1:])
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sintetis-bukan-key-asli')
    monkeypatch.setattr(__import__('ai_policy'), 'deployment_mengizinkan', lambda _f: True)
    panggilan = []
    monkeypatch.setattr(assistant_client, 'kirim', lambda *_a, **_k: panggilan.append(1) or {'status': 'ok'})
    kode = _minta(server, '/admin/ai/uji', cookie=token, data=data_palsu)[0]
    assert panggilan == [] and ai_service.path_store().read_bytes() == awal
    assert kode == 403
    raw = urllib.parse.urlencode(data).encode() + b'&reauth=ganda'
    assert _minta(server, '/admin/ai/uji', cookie=token, raw=raw)[0] == 400
    assert ai_service.path_store().read_bytes() == awal
    assert _minta(server, '/admin/ai/uji', cookie=token, data=data)[0] == 303
    assert panggilan == [1]


@pytest.mark.parametrize('jenis', ['uji', 'pengaturan'])
def test_ai_actor_reset_setelah_reauth_sebelum_admission_nol_efek(server, monkeypatch, jenis):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _form_ai(server, token, jenis)
    if jenis == 'uji':
        data['konfirmasi'] = '1'
        nama_helper = 'panggil_uji_admin'
    else:
        nama_helper = 'ubah_pengaturan_admin'
        data.update(revisi='1', request_akun_harian='20', uji_harian='3', uji_cooldown_menit='15')
        for fitur in ('global', *__import__('ai_policy').FITUR):
            data['harian_' + fitur] = '0.25'
            data['bulanan_' + fitur] = '2.50'
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'key-sintetis')
    monkeypatch.setattr(__import__('ai_policy'), 'deployment_mengizinkan', lambda _f: True)
    provider = []
    monkeypatch.setattr(assistant_client, 'kirim', lambda *_a, **_k: provider.append(1) or {'status': 'ok'})
    asli = getattr(ai_service, nama_helper)
    def reset_lalu_admission(*args, **kwargs):
        auth.naikkan_revisi_auth(auth.cari_akun('Admin-C')['id_akun'])
        return asli(*args, **kwargs)
    monkeypatch.setattr(ai_service, nama_helper, reset_lalu_admission)
    before = ai_service.path_store().read_bytes()
    kode, _, _ = _minta(server, '/admin/ai/' + jenis, cookie=token, data=data)
    assert kode == 403 and provider == []
    assert ai_service.path_store().read_bytes() == before


def test_ai_reset_saat_network_tidak_terblokir_dan_hasil_dibuang(server, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = dict(_form_ai(server, token, 'uji'), konfirmasi='1')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'key-sintetis')
    monkeypatch.setattr(__import__('ai_policy'), 'deployment_mengizinkan', lambda _f: True)
    def provider(*_args, **_kw):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(auth.naikkan_revisi_auth, auth.cari_akun('Admin-C')['id_akun']).result(timeout=3)
        return {'status': 'ok'}
    monkeypatch.setattr(assistant_client, 'kirim', provider)
    kode, body, header = _minta(server, '/admin/ai/uji', cookie=token, data=data)
    assert kode == 403 and 'Koneksi sintetis berhasil.' not in body
    assert header['Cache-Control'] == 'no-store'
    with ai_store.buka(ai_service.path_store()) as kon:
        assert kon.execute('SELECT status FROM ledger').fetchone()[0] == 'selesai'
        assert kon.execute('SELECT COUNT(*) FROM audit_uji_admin').fetchone()[0] == 1


def test_ai_pengaturan_replay_konflik_dan_audit_grouped(server):
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    data = _form_ai(server, token, 'pengaturan')
    data.update(revisi='1', request_akun_harian='23', uji_harian='3', uji_cooldown_menit='15')
    for fitur in ('global', *__import__('ai_policy').FITUR):
        data['harian_' + fitur] = '0.25'
        data['bulanan_' + fitur] = '2.50'
    stale = dict(data, **_form_ai(server, token, 'pengaturan'))
    assert _minta(server, '/admin/ai/pengaturan', cookie=token, data=data)[0] == 303
    with ai_store.buka(ai_service.path_store()) as kon:
        revisi = ai_store.konfigurasi(kon)[0]['revisi']
    assert _minta(server, '/admin/ai/pengaturan', cookie=token, data=data)[0] == 303
    assert _minta(server, '/admin/ai/pengaturan', cookie=token, data={**data, 'request_akun_harian': '24'})[0] == 409
    assert _minta(server, '/admin/ai/pengaturan', cookie=token, data=stale)[0] == 409
    with ai_store.buka(ai_service.path_store()) as kon:
        assert ai_store.konfigurasi(kon)[0]['revisi'] == revisi
    riwayat = ai_service.riwayat_admin()
    assert riwayat.total == 1 and riwayat.item[0].actor_id == auth.cari_akun('Admin-C')['id_akun']
    kode, isi, _ = _minta(server, '/admin?section=riwayat&sumber=ai', cookie=token)
    assert kode == 200 and 'Ubah pengaturan AI' in isi and 'dikelompokkan per operasi' in isi
    assert SANDI_ADMIN not in isi


def test_pendaftaran_actor_reset_setelah_reauth_sebelum_commit_nol_efek(server, monkeypatch):
    import admin_registration
    token = _login(server, 'Admin-C', SANDI_ADMIN)
    _, body, _ = _minta(server, '/admin?section=pendaftaran', cookie=token)
    data = {'aksi': 'registration_config_update', 'csrf': _hidden(body, 'csrf'),
            'tinjauan': _hidden(body, 'tinjauan'), 'reauth': SANDI_ADMIN, 'pesan_kode': 'closed_standard'}
    asli = admin_registration.ubah
    def reset_lalu_commit(*args, **kw):
        auth.naikkan_revisi_auth(auth.cari_akun('Admin-C')['id_akun'])
        return asli(*args, **kw)
    monkeypatch.setattr(admin_registration, 'ubah', reset_lalu_commit)
    before = admin_store.BAWAAN.read_bytes()
    kode, _, _ = _minta(server, '/admin/pendaftaran', cookie=token, data=data)
    assert admin_store.BAWAAN.read_bytes() == before
    assert kode == 403


def test_ai_query_tidak_memantulkan_pesan_bebas(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, _ = _minta(server, "/admin/ai?pesan=rahasia-sintetis", cookie=token)
    assert kode == 200 and "rahasia-sintetis" not in isi

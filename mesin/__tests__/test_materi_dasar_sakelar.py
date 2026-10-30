"""Sakelar penawaran/pembuatan, bukan sakelar pembaca histori (DB sintetis)."""
import json

import pytest

import assistant_actions
import assistant_catalog
import assistant_inline
import assistant_inline_http
import auth
import database
import question_context
import question_variants_ui
import topics
from http_test_kit import SANDI_GURU, ServerUji
from test_variasi_dasar_latihan import catat, keadaan, halaman, panel, post, terbaru
from test_assistant_actions import server as server_pendamping, _buat_usulan_http, _field_tinjau, _origin


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.delenv('OSN_MATERI_DASAR', raising=False)
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, 'Anak Sintetis T3', 'P3', pemilik='guru')
    try:
        yield srv
    finally:
        srv.berhenti()


@pytest.mark.parametrize('nilai,aktif', [(None, False), ('0', False), ('1', True), (' 1 ', True)])
def test_env(nilai, aktif, monkeypatch):
    if nilai is None:
        monkeypatch.delenv('OSN_MATERI_DASAR', raising=False)
    else:
        monkeypatch.setenv('OSN_MATERI_DASAR', nilai)
    assert question_context.materi_dasar_aktif() is aktif


@pytest.mark.parametrize('nilai', ['', 'true', '2', '-1', 'on'])
def test_env_tidak_sah(nilai, monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', nilai)
    with pytest.raises(ValueError, match='OSN_MATERI_DASAR'):
        question_context.materi_dasar_aktif()


def jumlah_baris(server):
    with server.buka() as kon:
        return {t: kon.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                for t in ('sesi', 'soal', 'sesi_soal', 'konteks_butir')}


def test_mati_markup_latihan(server):
    isi = panel(halaman(server), 'manual')
    assert 'value="bilangan-dasar"' not in isi
    assert 'Bilangan Dasar' not in isi
    assert 'name="variasi_dasar"' not in isi
    assert 'Variasi materi dasar' not in isi
    assert 'value="pola-bilangan"' in isi
    assert 'bilangan-dasar' in topics.daftar_topik()
    assert topics.ambil('bilangan-dasar').komposisi['P1']


@pytest.mark.parametrize('tambahan', [{}, {'variasi_dasar': 'P1'}, {'profil_parameter': 'P2'}])
def test_mati_post_tanpa_efek(server, tambahan, monkeypatch):
    import web
    asli = web.buat_sesi_seed_baru
    panggilan = []

    def pantau(*args, **kwargs):
        panggilan.append(True)
        return asli(*args, **kwargs)

    monkeypatch.setattr(web, 'buat_sesi_seed_baru', pantau)
    awal, jumlah = keadaan(server), jumlah_baris(server)
    kode, isi, _ = post(server, dict(topik='bilangan-dasar', **tambahan))
    assert kode == 400
    assert 'Materi ini belum dibuka.' in isi
    assert jumlah_baris(server) == jumlah
    assert keadaan(server) == awal
    assert panggilan == []  # Palang HTTP sendiri, bukan diselamatkan guard store.


def sumber_dasar(server, monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    assert post(server, {'topik': 'bilangan-dasar', 'variasi_dasar': 'P1'})[0] == 200
    with server.buka() as kon:
        sumber = catat(kon, server.siswa, 'P1')
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    return sumber


@pytest.mark.parametrize('sumber_eksplisit', [False, True])
def test_mati_remedial_tanpa_efek(server, monkeypatch, sumber_eksplisit):
    sumber = sumber_dasar(server, monkeypatch)
    awal, jumlah = keadaan(server), jumlah_baris(server)
    data = {'template_id': 'tambah_dasar', 'jumlah_soal': '5'}
    if sumber_eksplisit:
        data['sumber_sesi_id'] = str(sumber)
    kode, isi, _ = post(server, data, route='sesi-remedial')
    assert kode == 400
    assert 'Materi ini belum dibuka.' in isi
    assert jumlah_baris(server) == jumlah
    assert keadaan(server) == awal
    with server.buka() as kon:
        with pytest.raises(ValueError, match='Materi ini belum dibuka'):
            database.buat_sesi_remedial(kon, server.siswa, template_ids=['tambah_dasar'])
    assert keadaan(server) == awal


def test_mati_penawaran_remedial_dan_topik_terakhir(server, monkeypatch):
    sumber = sumber_dasar(server, monkeypatch)
    assert 'value="tambah_dasar"' not in panel(halaman(server, 'remedial'), 'remedial')
    assert 'value="bilangan-dasar"' not in panel(halaman(server), 'manual')
    kode, isi, _ = server.minta('/sesi/%d' % sumber, auth=('guru', SANDI_GURU))
    assert kode == 200
    assert 'value="tambah_dasar"' not in isi


def test_mati_gabungan_tanpa_efek(server):
    awal = keadaan(server)
    kode, isi, _ = post(server, [('topik', 'bilangan-dasar'), ('topik', 'pola-bilangan')], route='sesi-gabungan')
    assert kode == 400
    assert 'Materi ini belum dibuka.' in isi
    assert keadaan(server) == awal


def test_mati_pendamping_katalog_dan_validasi(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    katalog = assistant_catalog.buat_katalog()
    assert 'bilangan-dasar' not in {t.id for t in katalog.topik}
    assert 'tambah_dasar' not in {t.id for t in katalog.template}
    muatan = json.loads(assistant_catalog.serialisasi_ringkas(katalog))
    assert all(t['id'] != 'bilangan-dasar' for t in muatan['topik'])
    with pytest.raises(assistant_actions.GalatTindakan):
        assistant_actions.validasi_usulan({'topik_id': 'bilangan-dasar', 'level': 'P1',
                                          'template_ids': ['tambah_dasar'], 'jumlah_soal': 10})


@pytest.mark.parametrize('jenis', ['manual', 'gabungan'])
def test_mati_topik_sah_draf(jenis, monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    nama = 'parse_draf_latihan' if jenis == 'manual' else 'parse_draf_gabungan'
    asli = getattr(assistant_inline, nama)
    terlihat = []

    def periksa(data, topik_sah, **kwargs):
        terlihat.extend(topik_sah)
        return asli(data, topik_sah, **kwargs)

    monkeypatch.setattr(assistant_inline, nama, periksa)
    data = {'inline_form': [jenis], 'topik': ['bilangan-dasar'], 'jumlah_soal': ['10'],
            'mode': ['drill'], 'durasi_menit': ['15'], 'timer_auto': ['0']}
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline_http._pisahkan_draf_inline(data, assistant_inline.tujuan_anak(7, 'latihan'))
    assert terlihat and 'bilangan-dasar' not in terlihat


def test_mati_pemilih_legacy_tidak_menawarkan_dasar(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    assert question_variants_ui.pemilih_dasar('bilangan-dasar', 'P1') == ''
    with pytest.raises(ValueError, match='Materi ini belum dibuka'):
        question_variants_ui.pemilih_isi(['bilangan-dasar'], 'uji')
    isi = question_variants_ui.kontrol_variasi('uji')
    assert 'value="P1"' not in isi and 'value="P2"' not in isi
    assert 'value="P3"' in isi


def test_mati_muatan_provider_tanpa_topik_dasar(monkeypatch):
    import assistant_service
    import assistant_store
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    monkeypatch.setattr(assistant_store, 'memori_untuk_chat', lambda *a: [])
    monkeypatch.setattr(assistant_store, 'daftar_pesan', lambda *a: [])
    pesan = assistant_service._pesan_provider(None, 'sintetis', 'sintetis', 'Bantu latihan')
    isi = json.loads(pesan[-1]['content'])
    assert 'bilangan-dasar' not in {t['id'] for t in isi['katalog']['topik']}
    assert 'tambah_dasar' not in {t['id'] for t in isi['katalog']['template']}


def test_mati_admin_juga_ditolak(server):
    auth.tambah_akun('pengelola', SANDI_GURU, 'admin', path=auth.BERKAS_SANDI)
    awal = keadaan(server)
    kode, isi, _ = post(server, {'topik': 'bilangan-dasar'}, pengguna='pengelola')
    assert kode == 400
    assert 'Materi ini belum dibuka.' in isi
    assert keadaan(server) == awal


def test_mati_latihan_serupa_tetap_ditolak_tanpa_efek(server, monkeypatch):
    sumber = sumber_dasar(server, monkeypatch)
    with server.buka() as kon:
        item = database.isi_sesi(kon, sumber)[0]
        kon.execute("UPDATE diagnosis SET kode_final='T' WHERE jawaban_id IN "
                    "(SELECT id FROM jawaban WHERE sesi_soal_id=?)", (item['sesi_soal_id'],))
    awal = keadaan(server)
    kode, _, _ = server.minta('/sesi/%d/latihan-serupa' % sumber, auth=('guru', SANDI_GURU),
                              data={'sesi_soal_id': str(item['sesi_soal_id'])})
    assert kode == 409  # P1 bukan tingkat siswa: guard selevel lama tetap berlaku.
    assert keadaan(server) == awal


def test_panduan_tidak_cache_sakelar_hidup_ke_mati(monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    assert 'Bilangan Dasar' in question_variants_ui.panduan_variasi()
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    assert 'Bilangan Dasar' not in question_variants_ui.panduan_variasi()


@pytest.mark.parametrize('jalur', ['/sesi/{sesi}', '/sesi/{sesi}/tinjauan', '/laporan/{anak}',
                                  '/anak/{anak}?section=riwayat', '/sesi/{sesi}/cetak',
                                  '/lembar/{sesi}', '/lembar/{sesi}/penilaian'])
def test_mati_pembaca_tetap_200(server, monkeypatch, jalur):
    sumber = sumber_dasar(server, monkeypatch)
    kode, _, _ = server.minta(jalur.format(sesi=sumber, anak=server.siswa), auth=('guru', SANDI_GURU))
    assert kode == 200


@pytest.mark.parametrize('jalur', ['/sesi/{id}', '/sesi/{id}/tinjauan', '/laporan/{id}',
                                  '/anak/{id}?section=riwayat', '/sesi/{id}/cetak', '/lembar/{id}'])
def test_mati_pembaca_guru_lain_404_identik(server, monkeypatch, jalur):
    sumber = sumber_dasar(server, monkeypatch)
    auth.tambah_akun('guru-lain', SANDI_GURU, 'guru', path=auth.BERKAS_SANDI)
    ident = server.siswa if jalur.startswith(('/anak/', '/laporan/')) else sumber
    awal = keadaan(server)
    asing = server.minta(jalur.format(id=ident), auth=('guru-lain', SANDI_GURU))
    hilang = server.minta(jalur.format(id=999999), auth=('guru-lain', SANDI_GURU))
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert keadaan(server) == awal


@pytest.mark.parametrize('route,data', [('sesi-baru', {'topik': 'bilangan-dasar'}),
                                       ('sesi-remedial', {'template_id': 'tambah_dasar'}),
                                       ('sesi-gabungan', [('topik', 'bilangan-dasar'), ('topik', 'pola-bilangan')])])
def test_mati_pembuat_guru_lain_404_identik(server, route, data):
    auth.tambah_akun('guru-lain', SANDI_GURU, 'guru', path=auth.BERKAS_SANDI)
    awal = keadaan(server)
    asing = post(server, data, route=route, pengguna='guru-lain')
    hilang = post(server, data, route=route, pengguna='guru-lain', siswa=999999)
    assert asing[0] == hilang[0] == 404
    assert asing[1] == hilang[1]
    assert keadaan(server) == awal


@pytest.mark.parametrize('pembuat', ['biasa', 'urutan', 'gabungan'])
def test_mati_writer_langsung_tanpa_efek(server, pembuat):
    awal = keadaan(server)
    with server.buka() as kon:
        with pytest.raises(ValueError, match='Materi ini belum dibuka'):
            if pembuat == 'biasa':
                database.buat_sesi(kon, server.siswa, 5, topik='bilangan-dasar', level='P1')
            elif pembuat == 'urutan':
                database.buat_sesi_dari_urutan(kon, server.siswa, 5, ('tambah_dasar',),
                                              topik=topics.paket_untuk_template(['tambah_dasar']), level='P1')
            else:
                database.buat_sesi_gabungan(kon, server.siswa, 5, ['bilangan-dasar', 'pola-bilangan'])
    assert keadaan(server) == awal


def test_mati_draf_remedial(server, monkeypatch):
    sumber = sumber_dasar(server, monkeypatch)
    awal = keadaan(server)
    data = {'inline_form': ['remedial'], 'template_id': ['tambah_dasar'],
            'jumlah_soal': ['10'], 'sumber_sesi_id': [str(sumber)]}
    with pytest.raises(assistant_inline.GalatInline):
        assistant_inline_http._pisahkan_draf_inline(data, assistant_inline.tujuan_anak(server.siswa, 'latihan'))
    assert keadaan(server) == awal


@pytest.mark.parametrize('dibuat', [False, True])
def test_mati_histori_usulan_pendamping_tetap_terbaca(server_pendamping, monkeypatch, dibuat):
    srv = server_pendamping
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    srv.provider.respons['usulan_latihan'] = {'topik_id': 'bilangan-dasar', 'level': 'P1',
                                             'template_ids': ['tambah_dasar'], 'jumlah_soal': 10}
    token, chat, usulan = _buat_usulan_http(srv)
    kode, isi, _ = srv.minta('/pendamping/usulan/' + usulan, cookie=token)
    assert kode == 200
    field = _field_tinjau(isi)
    data = {'versi': field['versi_usulan'], 'hash': field['hash_usulan'], 'request_id': field['request_id']}
    route = '/pendamping/usulan/' + usulan + '/konfirmasi'
    if dibuat:
        assert srv.minta(route, cookie=token, data=data, headers=_origin(srv))[0] == 200
    monkeypatch.setenv('OSN_MATERI_DASAR', '0')
    awal = keadaan(srv)
    kode, isi, _ = srv.minta('/pendamping/chat/' + chat, cookie=token)
    assert kode == 200
    if not dibuat:
        assert 'Materi ini belum dibuka.' in isi
        assert 'Tinjau usulan' not in isi
    else:
        assert srv.minta('/pendamping/usulan/' + usulan, cookie=token)[0] == 200
    kode, _, _ = srv.minta(route, cookie=token, data=data, headers=_origin(srv))
    assert kode == (200 if dibuat else 409)
    assert keadaan(srv) == awal


def test_hidup_kartu_dan_p1(server, monkeypatch):
    monkeypatch.setenv('OSN_MATERI_DASAR', '1')
    isi = panel(halaman(server), 'manual')
    assert 'value="bilangan-dasar"' in isi
    assert 'name="variasi_dasar"' in isi
    assert post(server, {'topik': 'bilangan-dasar', 'variasi_dasar': 'P1'})[0] == 200
    sesi, soal = terbaru(server)
    assert sesi['level'] == 'P1'
    assert all(int(s['kunci']) <= 10 for s in soal)

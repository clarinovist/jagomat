"""Pilihan profil manual eksplisit dan terpisah dari kelas sekolah."""
import pytest

import database
import learning_profile
from http_test_kit import ServerUji, SANDI_GURU


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        learning_profile.simpan_kelas(kon, srv.siswa, 1, revisi=0, pemilik='guru')
    yield srv
    srv.berhenti()


def test_kelas_http_memakai_metadata_dan_menolak_tab_lama(server):
    with server.buka() as kon:
        putaran = database.buat_putaran_fokus(kon, server.siswa, 'P3')
        sebelum = tuple(tuple(b) for b in kon.execute('SELECT * FROM kejadian_belajar'))
    data = {'aksi': 'kelas_sekolah', 'siswa_id': str(server.siswa),
            'kelas_sekolah': '6', 'revisi_profil': '1'}
    kode, isi, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data=data)
    assert kode == 200 and 'Kelas sekolah disimpan' in isi
    kode, isi, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data=dict(data, kelas_sekolah='2'))
    assert kode == 200 and 'Muat ulang' in isi
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.siswa, pemilik='guru').kelas_sekolah == 6
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'
        assert tuple(tuple(b) for b in kon.execute('SELECT * FROM kejadian_belajar')) == sebelum
        assert kon.execute('SELECT id FROM putaran_fokus').fetchone()[0] == putaran


def test_kelas_http_asing_hilang_404_identik(server):
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, 'Sintetis lain', 'P6', pemilik='lain')
        sebelum = tuple(kon.iterdump())
    hasil = []
    for sid in (asing, 99999):
        kode, isi, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data={
            'aksi': 'kelas_sekolah', 'siswa_id': str(sid), 'kelas_sekolah': '2', 'revisi_profil': '0'})
        assert kode == 404
        hasil.append(isi)
    assert hasil[0] == hasil[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_onboarding_tidak_menafsir_payload_lama_atau_default(server):
    for tambahan in ({}, {'tingkat': 'P3'}, {'level': 'P6'}, {'profil_parameter': ''}):
        kode, _, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data={
            'aksi': 'anak_baru', 'nama': 'Baru Sintetis', 'sandi_anak': 'sintetis-panjang-123', **tambahan})
        assert kode == 400
    with server.buka() as kon:
        assert kon.execute('SELECT count(*) FROM siswa').fetchone()[0] == 1


def test_http_form_level_lama_tidak_mengubah_kelas_dan_bukti(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data={
        'aksi': 'tingkat', 'siswa_id': str(server.siswa), 'tingkat': 'P6'})
    assert kode == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_http_kelas_field_asing_dan_ganda_tidak_menulis(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    data = {'aksi': 'kelas_sekolah', 'siswa_id': str(server.siswa),
            'kelas_sekolah': '4', 'revisi_profil': '1'}
    for kirim in (dict(data, tingkat='P6'), list(data.items()) + [('kelas_sekolah', '5')]):
        kode, _, _ = server.minta('/akun', auth=('guru', SANDI_GURU), data=kirim)
        assert kode == 400
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_manual_memilih_profil_bukan_kelas_atau_tingkat(server):
    kode, _, _ = server.minta('/sesi-baru/%d' % server.siswa,
                              auth=('guru', SANDI_GURU),
                              data={'topik': 'aritmatika-lanjut', 'profil_parameter': 'P6', 'jumlah_soal': '4'})
    assert kode == 200
    with server.buka() as kon:
        sesi = kon.execute('SELECT * FROM sesi').fetchone()
        assert sesi is not None and sesi['level'] == 'P6' and sesi['tujuan'] == 'bebas'
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'
        assert learning_profile.baca(kon, server.siswa, pemilik='guru').kelas_sekolah == 1
        assert kon.execute('SELECT count(*) FROM kejadian_belajar').fetchone()[0] == 0


@pytest.mark.parametrize('profil', ['', 'asing'])
def test_profil_manual_tidak_fallback(server, profil):
    kode, _, _ = server.minta('/sesi-baru/%d' % server.siswa,
                              auth=('guru', SANDI_GURU),
                              data={'topik': 'pola-bilangan', 'profil_parameter': profil})
    assert kode == 400
    with server.buka() as kon:
        assert kon.execute('SELECT count(*) FROM sesi').fetchone()[0] == 0


def test_form_semua_materi_dan_profil_tanpa_pagar_kelas(server):
    kode, isi, _ = server.minta('/anak/%d' % server.siswa, auth=('guru', SANDI_GURU))
    assert kode == 200
    assert 'name="profil_parameter"' in isi
    assert 'value="aritmatika-lanjut"' in isi
    assert '<option value="pola-bilangan" selected>' in isi
    assert 'Variasi A' in isi and 'Variasi D' in isi


def test_profil_hilang_dan_ganda_ditolak_tanpa_default(server):
    for data in ({'topik': 'pola-bilangan'},
                 [('topik', 'pola-bilangan'), ('profil_parameter', 'P3'), ('profil_parameter', 'P6')]):
        kode, _, _ = server.minta('/sesi-baru/%d' % server.siswa,
                                  auth=('guru', SANDI_GURU), data=data)
        assert kode == 400
    with server.buka() as kon:
        assert kon.execute('SELECT count(*) FROM sesi').fetchone()[0] == 0


def test_gabungan_tidak_mengabaikan_topik_tanpa_profil(server):
    data = [('topik', 'pola-bilangan'), ('topik', 'aritmatika-lanjut'), ('profil_parameter', 'P3')]
    kode, _, _ = server.minta('/sesi-gabungan/%d' % server.siswa, auth=('guru', SANDI_GURU), data=data)
    assert kode == 400
    with server.buka() as kon:
        assert kon.execute('SELECT count(*) FROM sesi').fetchone()[0] == 0


def test_manual_lintas_profil_resource_asing_404_identik_tanpa_efek(server):
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, 'Sintetis lain', 'P6', pemilik='lain')
        sebelum = tuple(kon.iterdump())
    hasil = []
    for sid in (asing, 99999):
        kode, isi, _ = server.minta('/sesi-baru/%d' % sid, auth=('guru', SANDI_GURU),
                                    data={'topik': 'pola-bilangan', 'profil_parameter': 'P6'})
        assert kode == 404
        hasil.append(isi)
    assert hasil[0] == hasil[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_laporan_konteks_dari_reducer_tanpa_persen_atau_efek_get(server):
    from datetime import date, timedelta
    from test_mastery_context import _sesi
    with server.buka() as kon:
        for i, hari in enumerate((date.today() - timedelta(days=7), date.today() - timedelta(days=3))):
            _sesi(kon, server.siswa, 'P4', 61 + i, hari)
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta('/laporan/%d?section=penguasaan&tampilan=konteks' % server.siswa,
                               auth=('guru', SANDI_GURU))
    assert kode == 200
    panel = isi.split('id="bukti-per-konteks"', 1)[1].split('</section>', 1)[0]
    assert 'Variasi B' in panel and 'Menunjukkan pemahaman' in panel
    assert '196' not in panel and '%' not in panel
    assert 'Variasi A</b>' not in panel
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum

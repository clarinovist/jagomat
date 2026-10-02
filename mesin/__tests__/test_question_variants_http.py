"""Alur baru tidak meminta pilihan variasi; payload lama tetap dipagari."""
import pytest

import database
from http_test_kit import ServerUji, SANDI_GURU
from test_school_profile_ui import Formulir


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        srv.siswa = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
    yield srv
    srv.berhenti()


def test_get_form_otomatis_tidak_menulis_atau_meminta_variasi(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta(
        '/anak/%d?section=latihan' % server.siswa, auth=('guru', SANDI_GURU)
    )
    assert kode == 200
    Formulir(isi)
    manual = isi.split('id="form-latihan-manual-', 1)[1].split('</form>', 1)[0]
    gabungan = isi.split('id="form-latihan-gabungan-', 1)[1].split('</form>', 1)[0]
    for panel in (manual, gabungan):
        assert 'name="profil_parameter"' not in panel
        assert 'Bandingkan isi' not in panel
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_manual_otomatis_memakai_profil_internal_tanpa_mengubahnya(server):
    kode, _, _ = server.minta(
        '/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU),
        data={'topik': 'pola-bilangan', 'jumlah_soal': '4'},
    )
    assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT level FROM sesi').fetchone()[0] == 'P3'
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'
        assert not kon.execute('SELECT 1 FROM kejadian_belajar').fetchone()


def test_payload_profil_lama_sah_tetap_kompatibel_tanpa_mutasi_profil(server):
    kode, _, _ = server.minta(
        '/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU),
        data={'topik': 'pola-bilangan', 'profil_parameter': 'P6', 'jumlah_soal': '4'},
    )
    assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT level FROM sesi').fetchone()[0] == 'P6'
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'


def test_payload_profil_lama_ganda_ditolak_tanpa_write(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, _, _ = server.minta(
        '/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU),
        data=[('topik', 'pola-bilangan'), ('profil_parameter', 'P3'),
              ('profil_parameter', 'P6')],
    )
    assert kode == 400
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_metadata_perbandingan_lama_ditolak_tanpa_write(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, isi, _ = server.minta(
        '/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU),
        data={'topik': 'statistika', 'profil_parameter': 'P3',
              'versi_pilihan_isi': '1', 'topik_dibandingkan': 'statistika'},
    )
    assert kode == 409 and 'sudah otomatis' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_gabungan_otomatis_memakai_irisan_terdekat(server):
    kode, _, _ = server.minta(
        '/sesi-gabungan/%d' % server.siswa, auth=('guru', SANDI_GURU),
        data=[('topik', 'pola-bilangan'), ('topik', 'aritmatika-lanjut'),
              ('jumlah_soal', '10'), ('mode', 'drill'), ('format_jawaban', 'isian')],
    )
    assert kode == 200
    with server.buka() as kon:
        sesi = kon.execute('SELECT level,topik FROM sesi').fetchone()
        assert sesi['level'] == 'P5'
        assert sesi['topik'] == 'gabungan:pola-bilangan,aritmatika-lanjut'
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'


def test_resource_asing_dan_hilang_404_identik_tanpa_efek(server):
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, 'Asing', 'P3', pemilik='keluarga-lain')
        sebelum = tuple(kon.iterdump())
    respons = []
    for sid in (asing, 999999):
        kode, isi, _ = server.minta(
            '/sesi-baru/%d' % sid, auth=('guru', SANDI_GURU),
            data={'topik': 'pola-bilangan'},
        )
        assert kode == 404
        respons.append(isi)
    assert respons[0] == respons[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum

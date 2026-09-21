"""Pilihan variasi native tetap memakai kontrak HTTP dan histori yang sama."""
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


def test_get_panduan_tidak_membuat_sesi_atau_bukti(server):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    for url in ('/anak/%d' % server.siswa, '/akun?section=siswa'):
        kode, isi, _ = server.minta(url, auth=('guru', SANDI_GURU))
        assert kode == 200
        assert isi.count('id="panduan-variasi"') == 1
        assert '<option value="P3"' in isi and '>Variasi A</option>' in isi
        assert 'data-contoh="pola-bilangan:P6"' in isi
        Formulir(isi)  # termasuk guard form tidak bersarang
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('profil', ['P3', 'P4', 'P5', 'P6'])
def test_pilihan_variasi_menyimpan_kode_asli_tanpa_mengubah_profil(server, profil):
    kode, isi, _ = server.minta('/anak/%d' % server.siswa, auth=('guru', SANDI_GURU))
    assert kode == 200
    nama = dict(zip(('P3','P4','P5','P6'), ('Variasi A','Variasi B','Variasi C','Variasi D')))[profil]
    assert nama in isi
    kode, _, _ = server.minta('/sesi-baru/%d' % server.siswa, auth=('guru', SANDI_GURU), data={
        'topik': 'pola-bilangan', 'profil_parameter': profil, 'jumlah_soal': '4'})
    assert kode == 200
    with server.buka() as kon:
        assert kon.execute('SELECT level FROM sesi').fetchone()[0] == profil
        assert kon.execute('SELECT tingkat FROM siswa').fetchone()[0] == 'P3'
        assert kon.execute('SELECT count(*) FROM kejadian_belajar').fetchone()[0] == 0

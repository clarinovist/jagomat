"""Slot guru dan palang HTTP; fixture positif bukan pengesahan konten ajar."""
import sqlite3

import pytest

import database
import teaching_playbook as pb
import teacher_session_pages
import profile_home
import share_links
import student_pages
from learning_cycle import BuktiSiklus, RencanaBelajar, PutaranFokus, StatusFokus
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
from test_teaching_playbook import entri_sintetis, simpan, FOKUS, PENDEKATAN


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'playbook-ui.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


@pytest.fixture
def db_terjaga(db, monkeypatch):
    asli = sqlite3.Row
    class RowTerjaga(asli):
        def __getitem__(self, k):
            if k in {'kunci', 'malrule_id', 'kode_usulan', 'kode_final', 'alasan'}:
                raise AssertionError('Murid membaca kolom terlarang')
            return super().__getitem__(k)
    monkeypatch.setattr(sqlite3, 'Row', RowTerjaga)
    return db


@pytest.fixture
def konten(tmp_path, monkeypatch):
    p = tmp_path / 'fixture-ulasan-sintetis.json'
    simpan(p, [entri_sintetis()])
    monkeypatch.setattr(pb, 'BERKAS', p)
    return p


def sesi_sintetis(kon, nama='Anak Sintetis', pemilik='guru', selesai=True):
    anak = database.tambah_siswa(kon, nama, 'P3', pemilik=pemilik)
    sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=1)
    b = database.isi_sesi(kon, sesi)[0]
    assert b['template_id'] == FOKUS[0]
    if selesai:
        malrule = next(m for m in database.malrule_soal(kon, b['soal_id']) if m['malrule_id'] == FOKUS[2])
        jid = database.simpan_jawaban(kon, b['sesi_soal_id'], malrule['jawaban'], 'Cara sintetis')
        database.simpan_diagnosis(kon, jid, False, 'K', 'K', FOKUS[2])
        database.tandai_selesai(kon, sesi)
    return anak, sesi


def test_slot_tinjauan_tambahan_draf_tanpa_write(db, konten):
    with database.buka(db) as kon:
        _, sesi = sesi_sintetis(kon)
        sebelum = tuple(kon.iterdump())
        simpan(konten, [])
        kosong = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        e = entri_sintetis()
        simpan(konten, [e])
        isi = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert isi.count('data-playbook-guru') == 1
        assert 'PENANDA SINTETIS' in isi
        assert isi.index('data-playbook-guru') > isi.index('pembahasan-soal-')
        e.update(status='draf', reviewer=None, tanggal_review=None, versi_review=None, sha256_review=None)
        simpan(konten, [e])
        isi_draf = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert 'data-playbook-draf' in isi_draf and 'PENANDA SINTETIS' in isi_draf
        assert 'belum direview manusia; jangan dianggap panduan ajar final' in isi_draf
        assert 'data-playbook-guru' not in kosong
        assert isi_draf.count('<form') == kosong.count('<form')
        assert tuple(kon.iterdump()) == sebelum


def test_kode_draf_berbeda_tidak_memakai_malrule_lama(db, konten):
    with database.buka(db) as kon:
        _, sesi = sesi_sintetis(kon)
        b = database.isi_sesi(kon, sesi)[0]
        # Kode H tidak boleh diwarisi ID malrule K pada jawaban lama.
        database.simpan_diagnosis(kon, b['jawaban_id'], False, 'K', 'H', FOKUS[2], manual=True)
        isi = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert 'data-playbook-guru' not in isi


def test_slot_profil_mengikuti_pendekatan_dan_cta_tetap(konten):
    p = PutaranFokus(7, 'P3', (StatusFokus(FOKUS, 'perlu_dipelajari', pendekatan_berikutnya=PENDEKATAN),))
    r = RencanaBelajar('intervensi', 'uji', putaran=p)
    b = BuktiSiklus(9, 'P3')
    anak = {'id': 9, 'nama': 'Sintetis'}
    isi = profile_home.kartu(r, b, anak, peran='guru')
    assert isi.count('data-playbook-guru') == 1
    assert 'Contoh sintetis A.' in isi and 'Contoh sintetis B.' not in isi
    assert isi.count('class="rencana-cta-utama-st"') == 1
    for peran in ('murid', 'admin', None):
        assert 'data-playbook-guru' not in profile_home.kartu(r, b, anak, peran=peran)
    simpan(konten, [])
    kosong = profile_home.kartu(r, b, anak, peran='guru')
    e = entri_sintetis()
    e.update(status='draf', reviewer=None, tanggal_review=None, versi_review=None, sha256_review=None)
    simpan(konten, [e])
    isi_draf = profile_home.kartu(r, b, anak, peran='guru')
    assert 'data-playbook-draf' in isi_draf
    assert 'belum direview manusia; jangan dianggap panduan ajar final' in isi_draf
    assert isi_draf.count('class="rencana-cta-utama-st"') == kosong.count('class="rencana-cta-utama-st"')


def test_profil_http_meneruskan_peran_dan_fokus(tmp_path, monkeypatch, konten):
    import learning_cycle_ui as ui
    p = PutaranFokus(7, 'P3', (StatusFokus(FOKUS, 'perlu_dipelajari', pendekatan_berikutnya=PENDEKATAN),))
    r = RencanaBelajar('intervensi', 'uji', putaran=p)
    monkeypatch.setattr(ui, 'rencana_berikutnya', lambda *a, **kw: r)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            anak, _ = sesi_sintetis(kon)
        kode, isi, _ = server.minta('/anak/' + str(anak), auth=('guru', SANDI_GURU))
        assert kode == 200 and 'PENANDA SINTETIS' in isi
        assert isi.count('data-playbook-guru') == 1
    finally:
        server.berhenti()


def test_draf_tersedia_juga_untuk_guru_kedua(tmp_path, monkeypatch, konten):
    import auth
    e = entri_sintetis()
    e.update(status='draf', reviewer=None, tanggal_review=None, versi_review=None, sha256_review=None)
    simpan(konten, [e])
    server = ServerUji(tmp_path, monkeypatch)
    try:
        auth.tambah_akun('guru-kedua', 'sandi-sintetis-kedua', 'guru')
        with server.buka() as kon:
            _, sesi = sesi_sintetis(kon, pemilik='guru-kedua')
        kode, isi, _ = server.minta('/sesi/' + str(sesi), auth=('guru-kedua', 'sandi-sintetis-kedua'))
        assert kode == 200 and 'data-playbook-draf' in isi
        assert 'belum direview manusia; jangan dianggap panduan ajar final' in isi
        kode, _, _ = server.minta('/sesi/' + str(sesi), auth=('guru', SANDI_GURU))
        assert kode == 404
    finally:
        server.berhenti()


def test_murid_row_dan_loader_terjaga(db_terjaga, monkeypatch):
    def dilarang():
        pytest.fail('Loader dipanggil sisi murid')
    monkeypatch.setattr(pb, '_baca', dilarang)
    with database.buka(db_terjaga) as kon:
        anak = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=1)
        assert 'data-playbook-guru' not in student_pages.halaman_kerja_baru(kon, anak, sesi).decode()


def test_http_murid_share_asing_tidak_membaca_playbook(tmp_path, monkeypatch, konten):
    e = entri_sintetis()
    e.update(status='draf', reviewer=None, tanggal_review=None, versi_review=None, sha256_review=None)
    simpan(konten, [e])
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            anak, sesi = sesi_sintetis(kon, nama='feby')
            asing, sesi_asing = sesi_sintetis(kon, nama='Asing Sintetis', pemilik='lain')
            aktif = database.buat_sesi(kon, anak, 78, jumlah_soal=1)
            token = share_links.buat(kon, aktif)
        kode, isi, _ = server.minta('/sesi/' + str(sesi), auth=('guru', SANDI_GURU))
        assert kode == 200 and 'PENANDA SINTETIS' in isi
        baca = []
        def dilarang():
            baca.append(True)
            raise AssertionError('Loader playbook terlarang')
        monkeypatch.setattr(pb, '_baca', dilarang)
        for jalur in ('/murid/', '/murid/kerjakan/' + str(aktif), '/murid/hasil/' + str(sesi)):
            kode, isi, _ = server.minta(jalur, auth=('feby', SANDI_MURID))
            assert kode == 200, (jalur, kode)
            assert 'data-playbook-guru' not in isi and 'PENANDA SINTETIS' not in isi
        kode, isi, _ = server.minta('/mulai/' + token)
        assert kode == 200 and 'PENANDA SINTETIS' not in isi
        for jalur in ('/sesi/' + str(sesi), '/anak/' + str(anak), '/konten/playbook_p3.json', '/aset/../konten/playbook_p3.json'):
            kode, isi, _ = server.minta(jalur, auth=('feby', SANDI_MURID))
            assert kode in (401, 404) and 'PENANDA SINTETIS' not in isi
        with server.buka() as kon:
            sebelum = tuple(kon.iterdump())
        for jenis, identitas in (('anak', asing), ('sesi', sesi_asing)):
            ka, a, _ = server.minta('/' + jenis + '/' + str(identitas), auth=('guru', SANDI_GURU))
            kb, b, _ = server.minta('/' + jenis + '/999999', auth=('guru', SANDI_GURU))
            assert ka == kb == 404 and a == b
        assert not baca
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
    finally:
        server.berhenti()

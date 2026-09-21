"""Kartu ringkas tidak melipat instruksi wajib atau menyembunyikan hasil cerita."""
from datetime import date
from html.parser import HTMLParser

import pytest

import database
import interventions
import learning_cycle_ui
import llm
import teacher_pages
from learning_cycle import BuktiSiklus, PutaranFokus, RencanaBelajar, StatusFokus


class LetakIsi(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.details = []
        self.kedalaman = 0
        self.teks = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            self.kedalaman += 1
            self.details.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag == 'details':
            self.kedalaman -= 1

    def handle_data(self, data):
        if data.strip():
            self.teks.append((data, self.kedalaman))


@pytest.mark.parametrize('tindakan', ['pemetaan', 'intervensi', 'tunggu_evaluasi', 'eskalasi'])
def test_progres_dilipat_tetapi_tindakan_dan_peringatan_tetap_terlihat(tindakan):
    fokus = ('deret_aritmetika', 'K', None)
    putaran = PutaranFokus(7, 'P3', (StatusFokus(fokus, 'perlu_dipelajari', jumlah_sesi=2),))
    rencana = RencanaBelajar(tindakan, 'Sintetis', putaran=putaran,
                            kandidat=(fokus,), tersedia_pada=date(2026, 10, 1) if tindakan.startswith('tunggu') else None)
    bukti = BuktiSiklus(9, 'P3')
    isi = learning_cycle_ui.render_rencana(rencana, bukti, 9)
    struktur = LetakIsi(isi)
    assert 'Langkah belajar berikutnya' in isi
    assert 'Detail progres dan alur belajar' in isi
    progres = learning_cycle_ui._progres(rencana, bukti)
    assert any(progres in t and d > 0 for t, d in struktur.teks)
    assert all('open' not in a for a in struktur.details)
    assert any('Peran orang tua/guru' in t and d == 0 for t, d in struktur.teks)
    if tindakan == 'intervensi':
        materi = interventions.untuk_fokus(fokus)
        assert any(materi.contoh_terbimbing in t and d == 0 for t, d in struktur.teks)
        assert any(materi.instruksi_orang_tua in t and d == 0 for t, d in struktur.teks)
    if tindakan.startswith('tunggu'):
        assert any('1 Oktober 2026' in t and d == 0 for t, d in struktur.teks)
    if tindakan == 'pemetaan':
        assert any('15 soal' in t and d == 0 for t, d in struktur.teks)
        assert any('tanggal berbeda' in t and d == 0 for t, d in struktur.teks)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'ui.db'
    database.siapkan(path)
    monkeypatch.setattr(llm, 'aktif', lambda: True)
    def dilarang(*args, **kwargs):
        raise AssertionError('GET tidak boleh memanggil AI')
    monkeypatch.setattr(llm, 'bungkus', dilarang)
    return path


@pytest.mark.parametrize('keadaan', ['aktif', 'mati', 'terkunci', 'visual'])
def test_cerita_disclosure_cetak_dan_pesan_tetap_di_luar(db, monkeypatch, keadaan):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        if keadaan == 'visual':
            monkeypatch.setenv('OSN_VISUAL_KELUARGA', 'statistika')
            sesi = database.buat_sesi_dari_urutan(kon, sid, 42, ('diagram_batang_garis',), topik='statistika', level='P3')
        else:
            sesi = database.buat_sesi(kon, sid, 42, jumlah_soal=1)
        if keadaan == 'mati':
            monkeypatch.setattr(llm, 'aktif', lambda: False)
        if keadaan == 'terkunci':
            kon.execute('UPDATE sesi SET penyajian_dibekukan=CURRENT_TIMESTAMP WHERE id=?', (sesi,))
        sebelum = tuple(kon.iterdump())
        isi = teacher_pages.halaman_sesi_cetak(kon, sesi, pesan='Cerita gagal <sintetis>.').decode()
        assert tuple(kon.iterdump()) == sebelum
        for nav in (teacher_pages._pil_sesi, teacher_pages._pil_sesi_stitch):
            assert 'Cerita' not in nav(kon, sesi, 'cetak')
    struktur = LetakIsi(isi)
    assert any('Cerita gagal <sintetis>.' in t and d == 0 for t, d in struktur.teks)
    assert 'CETAK &amp; CERITA' not in isi
    if keadaan == 'mati':
        assert 'cerita-tambahan-st' not in isi.split('</style>')[-1]
    else:
        assert any(a.get('class') == 'cerita-tambahan-st' and 'open' not in a for a in struktur.details)
        assert 'Opsi tambahan: ubah cerita soal' in isi
        assert 'Mengubah redaksi; angka dan jawaban tetap.' in isi
        assert (f'action="/cerita/{sesi}"' in isi) == (keadaan == 'aktif')

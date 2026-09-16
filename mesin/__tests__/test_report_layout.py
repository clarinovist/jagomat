"""Regresi navigasi laporan tanpa lipatan dan angka yang terbaca."""
from html.parser import HTMLParser
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import reports
import mastery_report
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID


class Struktur(HTMLParser):
    """Catat kedalaman disclosure dan konteks tautan tanpa membaca CSS."""

    def __init__(self, halaman):
        super().__init__()
        self.kedalaman = 0
        self.maksimum = 0
        self.tautan = []
        self.feed(halaman)

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        if tag == 'details':
            self.kedalaman += 1
            self.maksimum = max(self.maksimum, self.kedalaman)
        if tag == 'a':
            self.tautan.append((atribut, self.kedalaman))

    def handle_endtag(self, tag):
        if tag == 'details':
            self.kedalaman -= 1


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    monkeypatch.setattr(auth, 'BERKAS_SANDI', tmp_path / 'sandi.json')
    path = tmp_path / 'uji.db'
    database.siapkan(path)
    return path


def test_rencana_utama_tidak_tersembunyi_dalam_lipatan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Contoh', pemilik='guru')
        h = reports.halaman_laporan(kon, sid).decode()
    aksi = [(a, d) for a, d in Struktur(h).tautan if 'aksi-rencana-laporan' in a.get('class', '')]
    assert len(aksi) == 1
    assert aksi[0][1] == 0


def test_peta_target_tidak_memiliki_lipatan_di_dalam_lipatan(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Peta', 'P5', pemilik='guru')
        peta = mastery_report.peta_penguasaan(database.muat_bukti_siklus(kon, sid), sid)
    h = mastery_report.render_peta(peta, reports._tanggal_pendek)
    assert Struktur(h).maksimum == 0
    assert 'class="peta-bukti"' in h


def test_nama_topik_gabungan_bukan_id_internal():
    assert reports._nama_topik('gabungan:logika,pola-bilangan') == 'Gabungan 2 topik'


@pytest.mark.parametrize('bagian', ['ringkasan', 'penguasaan', 'riwayat', 'asing', '<script>x</script>'])
def test_section_hanya_merender_bagian_terpilih_tanpa_write(db, bagian):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Navigasi', pemilik='guru')
        awal = tuple(kon.iterdump())
        h = reports.halaman_laporan(kon, sid, section=bagian).decode()
        assert tuple(kon.iterdump()) == awal
    aktif = bagian if bagian in {'penguasaan', 'riwayat'} else 'ringkasan'
    struktur = Struktur(h)
    terpilih = [a for a, _ in struktur.tautan if a.get('aria-current') == 'page']
    assert len(terpilih) == 1 and terpilih[0]['href'] == f'/laporan/{sid}?section={aktif}'
    assert ('id="rencana-belajar-laporan"' in h) == (aktif == 'ringkasan')
    assert ('class="peta-pilihan"' in h) == (aktif == 'penguasaan')
    assert ('id="riwayat-hasil-sesi"' in h) == (aktif == 'riwayat')
    assert struktur.maksimum <= 1
    assert '<script>x</script>' not in h


def test_riwayat_ringkas_satu_tautan_per_sesi_dan_penyebut_tersedia(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Riwayat', pemilik='guru')
        sesi = database.buat_sesi_dari_urutan(kon, sid, 431, ('deret_aritmetika',) * 15)
        for b in database.isi_sesi(kon, sesi)[:7]:
            jawaban = database.simpan_jawaban(kon, b['sesi_soal_id'], b['kunci'], 'Langkah contoh')
            database.simpan_diagnosis(kon, jawaban, True, None, None)
        database.tandai_selesai(kon, sesi)
        kon.execute('UPDATE sesi SET topik=? WHERE id=?', ('gabungan:logika,pola-bilangan', sesi))
        h = reports.halaman_laporan(kon, sid, section='riwayat').decode()
    tabel = h.split('class="tabel-wrap tabel-tren"', 1)[1].split('</table>', 1)[0]
    assert tabel.count('<th scope="col"') == 4
    assert tabel.count(f'href="/sesi/{sesi}"') == 1
    assert 'class="rasio-laporan">7 / 15</span>' in tabel
    assert 'Gabungan 2 topik' in tabel and 'gabungan:' not in tabel
    assert 'soal tersedia' in h and 'termasuk yang belum dijawab' in h
    assert '<th scope="col">K</th>' not in tabel
    assert 'Arti kode penilaian' in h
    assert 'Cara membaca laporan' not in h


def test_histori_panjang_tetap_terbaca_tanpa_lipatan_bersarang():
    from datetime import date
    from learning_cycle import RencanaBelajar
    from learning_journey import BuktiFokusPerjalanan, FokusPerjalanan, HistoriPutaran, PerjalananBelajar
    from cycle_report import render_perjalanan

    kunci = ('deret_aritmetika', 'K', 'sintetis')
    bukti = tuple(BuktiFokusPerjalanan(date(2026, 8, n), n, 'penguatan') for n in range(1, 7))
    fokus = FokusPerjalanan(kunci, 'menunggu_evaluasi', bukti)
    histori = HistoriPutaran(1, 'P3', date(2026, 8, 1), date(2026, 8, 7),
                            'putaran_ditutup', (kunci,), perjalanan_fokus=(fokus,))
    perjalanan = PerjalananBelajar(RencanaBelajar('pemetaan', ''), histori=(histori,))
    h = render_perjalanan(perjalanan, reports._nama_tipe_soal, reports._tanggal_pendek)
    assert Struktur(h).maksimum == 0
    assert all(h.count(f'href="/sesi/{n}"') == 1 for n in range(1, 7))
    assert 'Riwayat putaran sebelumnya' in h and 'Bukti sebelumnya' in h


def test_css_angka_dan_header_tidak_dipenggal():
    from report_dashboard import GAYA_LAPORAN

    for selektor in ('.laporan-editorial-st .rasio-laporan', '.laporan-editorial-st .tabel-tren th'):
        aturan = GAYA_LAPORAN.split(selektor + ' {', 1)[1].split('}', 1)[0]
        assert 'white-space:nowrap' in aturan
    assert '.laporan-editorial-st .tabel-tren table {min-width:0;table-layout:auto;overflow-wrap:normal;}' in GAYA_LAPORAN


@pytest.mark.parametrize('bagian', ['ringkasan', 'penguasaan', 'riwayat', 'asing'])
def test_http_navigasi_laporan_tetap_di_balik_guard_existing(tmp_path, monkeypatch, bagian):
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            sid = database.tambah_siswa(kon, 'Contoh Milik Guru', pemilik='guru')
            asing = database.tambah_siswa(kon, 'Contoh Keluarga Lain', pemilik='lain')
            sebelum = tuple(kon.iterdump())
        query = f'?section={bagian}'
        kode, h, _ = server.minta(f'/laporan/{sid}{query}', auth=('guru', SANDI_GURU))
        assert kode == 200
        aktif = bagian if bagian != 'asing' else 'ringkasan'
        assert f'href="/laporan/{sid}?section={aktif}" aria-current="page"' in h
        ka, ha, _ = server.minta(f'/laporan/{asing}{query}', auth=('guru', SANDI_GURU))
        kh, hh, _ = server.minta(f'/laporan/999999{query}', auth=('guru', SANDI_GURU))
        assert ka == kh == 404 and ha == hh
        km, hm, _ = server.minta(f'/laporan/{sid}{query}', auth=('feby', SANDI_MURID))
        assert km in (401, 403) and 'id="judul-laporan"' not in hm
        with server.buka() as kon:
            assert tuple(kon.iterdump()) == sebelum
    finally:
        server.berhenti()

"""Variasi dibaca dari isi soal, tanpa menebak kelas atau mengubah bukti."""
import random
from html.parser import HTMLParser

import pytest

import database
import profile_workspace
import question_context
import teacher_pages
import topics
from templates import LEVEL


def test_nama_variasi_netral_kode_tetap_kanonis():
    assert [question_context.label_profil_parameter(p) for p in LEVEL] == [
        'Variasi A', 'Variasi B', 'Variasi C', 'Variasi D']
    assert question_context.label_profil_parameter('lama') == 'Konfigurasi lama: lama'
    assert question_context.konteks_warisan('keliling_luas_datar', 'P3').id == 'warisan-v1:keliling_luas_datar:P3'


def test_identitas_anak_bukan_konfigurasi_soal():
    isi = profile_workspace.bingkai(dict(id=1, nama='Sintetis', tingkat='P6', pemilik='guru'),
                                    'latihan', 0, '', kelas_sekolah=2)
    kepala = isi.split('<header', 1)[1].split('</header>', 1)[0]
    assert 'Kelas 2' in kepala and 'Ubah kelas' not in kepala
    assert 'P6' not in kepala and 'Konteks latihan' not in kepala


def test_pemilih_isi_memakai_huruf_sekunder_dan_contoh_kontekstual():
    from question_variants_ui import pemilih_isi
    isi = pemilih_isi(('pola-bilangan',), 'manual', 'P5')
    assert '<legend>Pilih isi latihan</legend>' in isi
    assert isi.count('name="profil_parameter"') == 4
    assert '<input type="radio" name="profil_parameter" value="P5"' in isi
    assert ' checked' in isi
    assert '<span class="variasi-penanda"><span class="variasi-sr">Pilihan </span>C</span>' in isi
    assert '<strong class="variasi-nama-isi">Pola pecahan</strong>' in isi
    assert 'pola lain' not in isi
    assert isi.index('variasi-penanda') < isi.index('variasi-nama-isi') < isi.index('variasi-meta')
    assert '<span class="variasi-meta">Mencakup 12 pola soal.</span>' in isi
    assert 'Pola soal:' not in isi
    assert 'Lihat contoh: ' in isi and 'Contoh salah satu soal:' not in isi
    assert 'data-contoh="pola-bilangan:P5"' in isi
    assert 'A–D hanya penanda' in isi and 'Variasi A–D hanya penanda' not in isi
    assert 'bukan urutan kemampuan' in isi
    assert '<select' not in isi and '<script' not in isi
    gaya = __import__('question_variants_ui').GAYA_VARIASI
    assert 'font-size:1rem' in gaya and '.variasi-penanda {' in gaya
    assert 'display:flex; flex-direction:column' in gaya and 'margin-top:auto' in gaya


def test_pemilih_isi_hanya_menawarkan_irisan_topik_dan_tidak_fallback():
    from question_variants_ui import pemilih_isi
    isi = pemilih_isi(('aritmatika-lanjut', 'pola-bilangan'), 'gabungan')
    assert isi.count('name="profil_parameter"') == 2
    assert 'value="P5"' in isi and 'value="P6"' in isi
    assert 'value="P3"' not in isi and 'value="P4"' not in isi
    assert '<span class="variasi-sr">Pilihan </span>C' in isi
    assert '<span class="variasi-sr">Pilihan </span>D' in isi
    assert '<span class="variasi-sr">Pilihan </span>A' not in isi
    assert isi.count('<span class="variasi-meta">Mencakup 2 materi dan ') == 2
    assert '<span class="variasi-meta"><span>' not in isi
    assert 'pola lain' not in isi


def test_pemilih_campuran_mengikuti_komposisi_campuran_bukan_irisan_semua_topik():
    from question_variants_ui import pemilih_isi
    isi = pemilih_isi(('campuran',), 'manual')
    assert isi.count('name="profil_parameter"') == 4
    assert 'value="P3"' in isi and 'value="P6"' in isi
    assert 'data-contoh="campuran:P3"' in isi
    assert 'Campuran Semua Topik' in isi
    assert 'pola lain' not in isi
    assert isi.count('<span class="variasi-meta">Mencakup ') == 4


@pytest.mark.parametrize('topik', [t for t in topics.daftar_topik() if t != 'campuran'])
def test_contoh_tepat_paket_profil_deterministik_dan_hanya_soal(topik):
    from generator import buat_lembar
    from question_variants_ui import contoh_variasi
    from render import _badan_soal
    from template_labels import nama_tipe_soal
    paket = topics.ambil(topik)
    for profil in LEVEL:
        if profil not in paket.komposisi:
            with pytest.raises(ValueError):
                contoh_variasi(topik, profil)
            continue
        keadaan = random.getstate()
        pola, badan = contoh_variasi(topik, profil)
        # Sumber independen dari helper presentasi: pasangan aktual, bukan fallback.
        tid = paket.komposisi[profil][0]
        soal = buat_lembar(42, urutan=(tid,), level=profil, topik=topik).soal[0]
        assert pola == nama_tipe_soal(tid)
        assert badan == _badan_soal(soal, paket, namespace='contoh-' + topik + '-' + profil)
        assert contoh_variasi(topik, profil) == (pola, badan)
        assert random.getstate() == keadaan
        assert 'data-kunci' not in badan and 'malrule' not in badan and 'diagnosis' not in badan


def test_panduan_mencakup_registry_tanpa_klaim_jenjang():
    from question_variants_ui import panduan_variasi
    from template_labels import nama_tipe_soal
    import html
    isi = panduan_variasi()
    assert 'id="panduan-variasi"' in isi and '<details' in isi
    assert 'bukan urutan kemampuan' in isi
    assert 'Contoh ini bukan soal sesi yang akan dibuat' in isi
    assert 'Campuran mengikuti materi yang tersedia' in isi
    assert '<script' not in isi and '<form' not in isi and '<input' not in isi
    for topik in topics.daftar_topik():
        if topik == 'campuran':
            continue
        paket = topics.ambil(topik)
        assert html.escape(paket.nama) in isi
        for profil, komposisi in paket.komposisi.items():
            assert 'data-contoh="%s:%s"' % (topik, profil) in isi
            for tid in set(komposisi):
                assert html.escape(nama_tipe_soal(tid)) in isi


def test_pilihan_pemetaan_menjelaskan_cakupan_tanpa_klaim_kemampuan():
    from question_variants_ui import pemilih_pemetaan
    isi = pemilih_pemetaan('rencana-awal')
    assert isi.count('name="profil_parameter"') == 4
    assert 'materi' in isi and 'pola soal' in isi
    assert 'Lihat contoh materi:' in isi
    assert len(isi) < 50_000  # cakupan pemetaan diringkas, bukan katalog seluruh pola.
    assert '<span class="variasi-sr">Pilihan </span>A' in isi
    assert '<span class="variasi-sr">Pilihan </span>D' in isi
    assert isi.count('<span class="variasi-meta">Mencakup ') == 4
    assert '<span class="variasi-meta"><span>' not in isi
    assert 'kelas anak' in isi and 'Mudah' not in isi and 'Sulit' not in isi
    assert '<script' not in isi


def test_panduan_ringkas_hanya_memindah_penjelasan_bukan_isi_contoh():
    import re
    from question_variants_ui import kontrol_variasi, panduan_variasi
    biasa = panduan_variasi()
    ringkas = panduan_variasi(ringkas=True)
    pola = r'<article class="variasi-contoh".*?</article>'
    assert re.findall(pola, biasa) == re.findall(pola, ringkas)
    assert 'Tentang variasi dan contoh' not in biasa
    assert 'href="#panduan-variasi"' not in kontrol_variasi('manual')
    assert biasa.count('<summary>Bandingkan isi dan contoh soal</summary>') == 1
    assert 'href="#panduan-variasi"' not in kontrol_variasi('anak', ringkas=True)
    assert 'bukan urutan kemampuan atau kelas anak' in kontrol_variasi('anak', ringkas=True)
    posisi_materi = ringkas.index('class="variasi-materi"')
    posisi_keterangan = ringkas.index('<summary>Tentang variasi dan contoh</summary>')
    assert posisi_materi < posisi_keterangan < ringkas.index('Contoh ini bukan soal sesi yang akan dibuat')
    assert 'Campuran mengikuti materi yang tersedia' in ringkas
    profil = panduan_variasi(judul='Lihat contoh soal')
    assert profil.replace('<summary>Lihat contoh soal</summary>',
                          '<summary>Bandingkan isi dan contoh soal</summary>', 1) == biasa
    assert '<summary>&lt;uji&gt;</summary>' in panduan_variasi(judul='<uji>')


class Rincian(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.kedalaman = 0
        self.luar = []
        self.dalam = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            assert 'open' not in dict(attrs)
            self.kedalaman += 1

    def handle_endtag(self, tag):
        if tag == 'details':
            self.kedalaman -= 1

    def handle_data(self, isi):
        (self.dalam if self.kedalaman else self.luar).append(isi)


def test_konteks_laporan_keterampilan_dahulu_bukti_tetap_terpisah(tmp_path):
    from datetime import date, timedelta
    from test_mastery_context import _sesi, _muat
    from context_report import render_konteks
    path = tmp_path / 'sintetis.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', 'P3', pemilik='guru')
        for profil in ('P3', 'P4'):
            for i, hari in enumerate((date.today() - timedelta(days=7), date.today() - timedelta(days=3))):
                _sesi(kon, sid, profil, 61 + i, hari)
        sebelum = tuple(kon.iterdump())
        isi = render_konteks(_muat(kon, sid), sid, lambda nilai: nilai)
        assert tuple(kon.iterdump()) == sebelum
    rincian = Rincian(isi)
    luar, dalam = ''.join(rincian.luar), ''.join(rincian.dalam)
    assert 'P3' not in luar and 'P4' not in luar and 'Profil' not in luar
    assert 'Menunjukkan pemahaman' in luar
    assert 'Variasi A' in luar and 'Variasi B' in luar
    assert 'P3' in dalam and 'P4' in dalam and 'Sumber:' in dalam

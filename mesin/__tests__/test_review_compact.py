"""Kontrak tinjauan datar: form utuh, keputusan terlihat, CSP terbatas."""
from html.parser import HTMLParser
import re

import pytest

import assistant_browser
import database
import teacher_pages
from test_review_layout import db, sesi_contoh
import style_stitch
import design_tokens as T
from test_teacher_corrections import FormKoreksi
from test_correction_disclosure import Struktur


class Detail(HTMLParser):
    """Hitung disclosure dari markup, bukan teks CSS/JS."""

    def __init__(self, html):
        super().__init__()
        self.depth = 0
        self.max_depth = 0
        self.count = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            self.count += 1
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)

    def handle_endtag(self, tag):
        if tag == 'details':
            self.depth -= 1


@pytest.mark.parametrize('mode', ['diagnostik', 'drill'])
def test_semua_soal_dua_detail_datar_dan_payload_native_utuh(db, mode):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        kon.execute('UPDATE sesi SET mode=? WHERE id=?', (mode, sesi))
        html = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        struktur = Struktur(html)
        data = FormKoreksi(html, sesi).data
        kartu = re.findall(r'<article\b[^>]*data-kartu-tinjauan.*?</article>', html, re.S)
        assert len(kartu) == len(ids)
        for sid, card in zip(ids, kartu):
            detail = Detail(card)
            assert (detail.count, detail.max_depth) == (2, 1)
            assert not re.search(r'<details[^>]*\bopen\b', card)
            assert '(opsional)' not in card
            assert 'Penilaian yang dipakai saat disimpan' in card
            assert 'Wajib untuk konfirmasi, kecuali dilewati' in card
            assert not struktur.tertutup(f'kode_{sid}')
            assert not struktur.tertutup(f'cek_pemahaman_{sid}')
            assert len(struktur.kontrol[f'cek_pemahaman_{sid}']) == 4
            assert all('disabled' not in a for a, _ in struktur.kontrol[f'kode_{sid}'])
            assert all('required' not in a for a, _ in struktur.kontrol[f'kode_{sid}'])
            assert data[f'kode_{sid}'] == data[f'cek_pemahaman_{sid}'] == ''
            expected = {'jwb', 'kode', 'cek_pemahaman', 'hadir_belum', 'hadir_dilewati',
                        'catatan_tinjauan', 'provenance', 'jawaban_bantuan', 'versi_tinjauan'}
            if mode != 'drill':
                expected.add('cara')
            assert {name for name in data if name.endswith(f'_{sid}')} == {f'{p}_{sid}' for p in expected}
        assert html.count('<summary>Panduan memilih penilaian</summary>') == 1
        assert Detail(html).max_depth == 1
        assert 'Jangan menimpa jawaban awal dengan hasil bantuan.' in html
        assert 'Centang hanya jika anak mengatakannya, bukan karena ia bingung.' in html


@pytest.mark.parametrize('mode,format_jawaban', [
    ('diagnostik', 'isian'), ('drill', 'isian'),
    ('diagnostik', 'pilihan_ganda'), ('drill', 'pilihan_ganda'),
])
def test_sepuluh_soal_termasuk_kosong_nomor_tujuh_tetap_datar(db, mode, format_jawaban):
    with database.buka(db) as kon:
        anak = database.tambah_siswa(kon, 'Anak Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=10,
                                 mode=mode, format_jawaban=format_jawaban)
        database.tandai_selesai(kon, sesi)
        isi = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        kartu = re.findall(r'<article\b[^>]*data-kartu-tinjauan.*?</article>', isi, re.S)
        assert len(kartu) == 10
        for card in kartu:
            assert (Detail(card).count, Detail(card).max_depth) == (2, 1)
            assert len(re.findall(r'type="radio"[^>]*name="cek_pemahaman_', card)) == 4
            assert 'Wajib untuk konfirmasi, kecuali dilewati' in card
            assert '(opsional)' not in card
        struktur = Struktur(isi)
        data = FormKoreksi(isi, sesi).data
        for b in database.isi_sesi(kon, sesi):
            sid = b['sesi_soal_id']
            assert not struktur.tertutup(f'kode_{sid}')
            assert not struktur.tertutup(f'cek_pemahaman_{sid}')
            assert data[f'hadir_belum_{sid}'] == data[f'hadir_dilewati_{sid}'] == '1'
            assert (f'cara_{sid}' in data) == (mode != 'drill' or format_jawaban == 'pilihan_ganda')
        assert isi.count('<summary>Panduan memilih penilaian</summary>') == 1


def test_css_antrean_satu_aturan_utuh_dan_kartu_tidak_menggandakan_jarak():
    css = style_stitch.CSS_SESI
    aturan = re.search(r'\.koreksi-editorial-st \.antrean-tinjauan-st ul\s*\{([^}]+)\}', css)
    assert aturan is not None
    for deklarasi in ('display: flex', 'flex-wrap: wrap', 'padding: 0', 'list-style: none'):
        assert deklarasi in aturan.group(1)
    assert '.kelompok-tinjauan-st > .koreksi-kartu-st { margin-bottom: 0; }' in css
    header = re.search(r'\.koreksi-editorial-st button\.koreksi-ringkas-st\s*\{([^}]+)\}', css).group(1)
    assert 'display: flex' in header and 'flex-wrap: wrap' in header
    assert 'min-height: ' + T.TARGET_SENTUH in header
    assert 'text-overflow: ellipsis' not in header


def test_hash_hanya_tinjauan_tanpa_izin_koneksi_dan_teks_palsu_tidak_memicu():
    from review_browser import SKRIP_TINJAUAN, HASH_TINJAUAN
    html = b'<body><form data-tinjauan-ringkas></form></body>'
    hasil, csp = assistant_browser.lengkapi_respons(html)
    assert hasil.count(b'<script>') == 1
    assert SKRIP_TINJAUAN.encode() in hasil
    assert csp == "script-src 'sha256-" + HASH_TINJAUAN + "'; "
    assert not assistant_browser.memiliki_tinjauan(b'&lt;form data-tinjauan-ringkas&gt;')
    assert not assistant_browser.memiliki_tinjauan(b'<style>form[data-tinjauan-ringkas]{}</style>')
    assert 'fetch(' not in SKRIP_TINJAUAN
    assert '.submit(' not in SKRIP_TINJAUAN and 'requestSubmit(' not in SKRIP_TINJAUAN


def test_sumber_t_otomatis_tetap_menampilkan_tindakan_dan_tidak_override(db):
    with database.buka(db) as kon:
        sesi, ids = sesi_contoh(kon)
        b = database.isi_sesi(kon, sesi)[0]
        database.simpan_diagnosis(kon, b['jawaban_id'], False, 'T', 'T')
        html = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        assert '>Pastikan kebutuhan pengenalan</p>' in html
        assert FormKoreksi(html, sesi).data[f'kode_{ids[0]}'] == ''
        assert re.search(r'<button[^>]*disabled[^>]*data-buka-kartu>', html)

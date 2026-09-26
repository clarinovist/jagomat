"""Regresi UI ringkas: detail native, isian utuh, dan makna wajib terlihat."""
from html.parser import HTMLParser
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import auth
import database
import reports
import student_pages
import teacher_pages
from style_stitch import GAYA_STITCH


class Markup(HTMLParser):
    """Catat ancestry disclosure tanpa mengimpor browser/dependensi tambahan."""
    def __init__(self, isi):
        super().__init__()
        self.details = []
        self.kontrol = []
        self.teks = []
        self.stack = []
        self.feed(isi.split('</style>')[-1])

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'details':
            self.stack.append(a)
            self.details.append(a)
        if tag in ('input', 'textarea', 'button', 'select'):
            self.kontrol.append((tag, a, tuple(self.stack)))

    def handle_endtag(self, tag):
        if tag == 'details':
            self.stack.pop()

    def handle_data(self, teks):
        self.teks.append((teks, tuple(self.stack)))

    def terlihat(self):
        return ' '.join(t for t, induk in self.teks if all('open' in a for a in induk))


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'ringkas.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    monkeypatch.setattr(auth, 'BERKAS_SANDI', tmp_path / 'sandi.json')
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, 'Anak Contoh', pemilik='guru')
        sesi = database.buat_sesi(kon, anak, seed=7, jumlah_soal=3)
        yield kon, anak, sesi


def test_petunjuk_ringkas_tanpa_menghilangkan_kontrak_anak(db):
    kon, anak, sesi = db
    dom = Markup(student_pages.halaman_kerja_baru(kon, anak, sesi).decode())
    assert any(a.get('class') == 'rincian-ui-st petunjuk-lengkap-st' for a in dom.details)
    assert 'Jangan menebak asal' in dom.terlihat()
    for teks in ('Simpan sementara', 'Selesai & kirim', 'belum pernah lihat soal seperti ini'):
        assert teks in dom.terlihat()
    assert len([a for _, a, _ in dom.kontrol if a.get('name', '').startswith('jwb_')]) == 3
    radio = [a for _, a, _ in dom.kontrol if a.get('name', '').startswith('pilih_')]
    assert len(radio) == 18
    assert len({a['value'] for a in radio}) == 6
    noms = [a.get('name', '') for _, a, _ in dom.kontrol]
    assert next(i for i, n in enumerate(noms) if n.startswith('jwb_')) < next(i for i, n in enumerate(noms) if n.startswith('pilih_'))
    aksi = [a['value'] for _, a, _ in dom.kontrol if a.get('name') == 'aksi']
    assert aksi == ['simpan', 'selesai']


def test_penjelasan_opsional_terbuka_bila_berisi_dan_tetap_dikirim(db):
    kon, anak, sesi = db
    butir = database.isi_sesi(kon, sesi)
    database.simpan_jawaban(kon, butir[0]['sesi_soal_id'], cara='[pilihan] hitung — Catatan <contoh>')
    dom = Markup(student_pages.halaman_kerja_baru(kon, anak, sesi).decode())
    cara = [(a, induk) for tag, a, induk in dom.kontrol if tag == 'textarea' and a.get('name', '').startswith('cara_')]
    assert len(cara) == 3
    for i, (a, induk) in enumerate(cara):
        assert len(induk) == 1 and induk[0].get('class') == 'rincian-ui-st cara-opsional-st'
        assert ('open' in induk[0]) == (i == 0)
        assert 'disabled' not in a and 'required' not in a
    assert 'Catatan <contoh>' in dom.terlihat()


def test_hasil_semua_pembahasan_tersedia_dan_yang_benar_dilipat(db):
    kon, anak, sesi = db
    for i, b in enumerate(database.isi_sesi(kon, sesi)):
        database.simpan_jawaban(kon, b['sesi_soal_id'], jawaban=b['kunci'] if i == 0 else '99999', cara='Saya menghitung')
    reports.diagnosa_murid(kon, sesi)
    database.tandai_selesai(kon, sesi)
    assert student_pages.halaman_hasil_murid(kon, anak, sesi) is None
    kon.execute("UPDATE sesi SET direview='2026-09-26' WHERE id=?", (sesi,))
    isi = student_pages.halaman_hasil_murid(kon, anak, sesi).decode()
    dom = Markup(isi)
    lipat = [a for a in dom.details if a.get('class') == 'rincian-ui-st hasil-cara-st']
    assert len(lipat) == 1 and 'open' not in lipat[0]
    assert isi.count('Caranya:') == 3
    assert any(a.get('class') == 'rumus-blok-st' and 'open' not in a for a in dom.details)
    assert all(a.get('name') != 'kode_final' for _, a, _ in dom.kontrol)


def test_form_latihan_satu_bantuan_dan_judul_visual(db):
    kon, anak, _ = db
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (anak,)).fetchone()
    isi = teacher_pages.halaman_anak(kon, siswa, pengguna='guru').decode()
    dom = Markup(isi)
    assert 'class="info-baris sub"' in isi
    assert 'class="st profil-sr-st"' in isi
    assert 'href="#panduan-variasi"' not in isi
    assert len([a for _, a, _ in dom.kontrol if a.get('id') == 'manual-topik']) == 1
    assert 'Pilihan ganda untuk latihan manual, belum menjadi bukti penguasaan.' in dom.terlihat()


@pytest.mark.parametrize('terisi', [False, True])
def test_penjelasan_pilihan_ganda_tetap_opsional_dan_berisi_terbuka(db, terisi):
    kon, anak, _ = db
    sesi = database.buat_sesi(kon, anak, seed=11, jumlah_soal=2, format_jawaban='pilihan_ganda')
    b = database.isi_sesi(kon, sesi)[0]
    if terisi:
        database.simpan_jawaban(kon, b['sesi_soal_id'], cara='Cara <contoh>')
    isi = student_pages.halaman_kerja_baru(kon, anak, sesi).decode()
    dom = Markup(isi)
    rincian = [a for a in dom.details if a.get('class') == 'rincian-ui-st cara-opsional-st']
    assert len(rincian) == 2
    assert ('open' in rincian[0]) == terisi and 'open' not in rincian[1]
    assert not any('petunjuk-lengkap-st' in a.get('class', '') for a in dom.details)
    assert 'Belum menjawab' in dom.terlihat()
    if terisi:
        assert 'Cara &lt;contoh&gt;' in isi


def test_bar_kirim_tidak_overlay_kontrol_anak():
    blok = GAYA_STITCH.split('.kerja-editorial-st .kerja-simpan-strip-st {', 1)[1].split('}', 1)[0]
    assert 'position: static' in blok
    assert 'z-index: auto' in blok


def test_info_tidak_meminjam_gaya_tombol_utama():
    assert '.info-baris .info:is(button)' in GAYA_STITCH
    blok = GAYA_STITCH.split('.info-baris .info:is(button)', 1)[1].split('}', 1)[0]
    assert 'background: transparent' in blok
    assert 'font: 700 .75rem/1' in blok
    assert '.info-baris .info-bubble' in GAYA_STITCH

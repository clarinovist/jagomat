"""Keterbacaan form mobile tanpa mengubah pilihan, aksi, atau data latihan."""
from html.parser import HTMLParser
import re

import pytest

import database
import profile_workspace
import teacher_pages


class FormLatihan(HTMLParser):
    """Kumpulkan label, opsi, dan atribut kontrol untuk regresi markup."""

    def __init__(self, isi):
        super().__init__()
        self.elemen = []
        self.dalam_form = 0
        self.maks_form = 0
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))
        if tag == 'form':
            self.dalam_form += 1
            self.maks_form = max(self.maks_form, self.dalam_form)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.dalam_form -= 1


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'mobile-sintetis.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'Anak Contoh', 'P3', pemilik='guru')
        siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
        yield kon, siswa


def test_label_pendek_helper_terhubung_dan_nilai_default_tidak_berubah(db):
    kon, siswa = db
    sebelum = tuple(kon.iterdump())
    isi = teacher_pages.halaman_anak(kon, siswa, pengguna='guru', privat=True).decode()
    assert '<label for="manual-jumlah">Jumlah soal</label>' in isi
    # Jangan menambahkan selected pada topik; default tetap urutan registry.
    assert '<option value="campuran" selected>' not in isi
    assert '<option value="campuran">Campuran semua topik</option>' in isi
    assert '<option value="" selected>Sesuai topik</option>' in isi
    dom = FormLatihan(isi)
    kontrol = next(a for t, a in dom.elemen if a.get('id') == 'manual-jumlah')
    assert kontrol['aria-describedby'] == 'manual-jumlah-petunjuk'
    assert 'id="manual-jumlah-petunjuk"' in isi
    assert 'Estimasi ±3 menit per soal.' in isi
    assert isi.count('action="/sesi-baru/%d"' % siswa['id']) == 1
    assert isi.count('formaction="/pendamping/inline/buka"') == 1
    assert tuple(kon.iterdump()) == sebelum


def _blok(css, selector):
    cocok = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', css)
    assert cocok, selector
    return cocok.group(1)


def test_grid_field_mobile_satu_kolom_dan_kontrol_teks_aman():
    css = profile_workspace.GAYA_PROFIL
    grid = _blok(css, '.profil-workspace-st .profil-champs-st')
    assert 'grid-template-columns:minmax(0,1fr)' in grid
    kontrol = _blok(css, '.profil-workspace-st .profil-champs-st select.st-input')
    assert 'font-size:16px' in kontrol
    assert 'min-height:44px' in kontrol


def test_tab_mobile_satu_kelompok_dan_tombol_utama_lebar_penuh():
    css = profile_workspace.GAYA_PROFIL
    mobile = css.split('@media(max-width:48rem)', 1)[1]
    tab = _blok(mobile, '.profil-workspace-st .profil-formulaire-st .tab-bar-st')
    assert 'grid-template-columns:minmax(0,1fr)' in tab
    cta = _blok(mobile, '.profil-workspace-st .profil-champs-st .st-tombol-coral')
    assert 'width:100%' in cta
    assert 'position:fixed' not in mobile and 'safe-area-inset' not in mobile


def test_draf_semua_field_tetap_sama_dan_tidak_nested(db):
    from assistant_inline import DrafLatihan, tujuan_anak
    from assistant_components import panel_persetujuan
    kon, siswa = db
    draf = DrafLatihan('campuran', '30', 'drill', True, '47', '1', 'pilihan_ganda')
    panel = panel_persetujuan(tujuan_anak(int(siswa['id']), 'latihan'), sumber={'label':'Latihan', 'level':'P3'}, dalam_form=True)
    isi = teacher_pages.halaman_anak(kon, siswa, pengguna='guru', draf_latihan=draf, bantuan_latihan=panel).decode()
    assert '<option value="campuran" selected>Campuran semua topik</option>' in isi
    assert '<option value="30" selected>' in isi
    assert 'value="pilihan_ganda" selected' in isi
    assert 'name="mode" value="drill" checked' in isi
    assert 'name="durasi_menit" value="47"' in isi
    assert 'name="timer_auto" value="1" checked' in isi
    assert isi.count('id="manual-jumlah-petunjuk"') == 1
    dom = FormLatihan(isi)
    assert dom.maks_form == 1 and dom.dalam_form == 0
    ids = [a['id'] for _, a in dom.elemen if 'id' in a]
    assert len(ids) == len(set(ids))

"""Regresi navigasi tanpa centang dan pengantar profil yang lebih ringkas."""
import re
from html.parser import HTMLParser

import pytest

import profile_workspace as P
import report_navigation as N
import design_tokens as T
from report_dashboard import GAYA_LAPORAN
from test_concise_ui import db
import teacher_pages


class Tautan(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.tautan = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.tautan.append(dict(attrs))


@pytest.mark.parametrize('aktif', ['materi', 'kriteria', 'perjalanan'])
def test_pilihan_tanpa_centang_dengan_url_aria_dan_label_utuh(aktif):
    opsi = [('materi', 'Materi'), ('kriteria', 'Kriteria & bukti'), ('perjalanan', 'Perjalanan')]
    h = N.pilihan('Tampilan <uji>', opsi, aktif, lambda k: N.url_laporan(7, 'penguasaan', tampilan=k))
    assert '✓' not in h and '✔' not in h and '<span' not in h
    assert 'Kriteria &amp; bukti' in h and 'Tampilan &lt;uji&gt;' in h
    tautan = Tautan(h).tautan
    assert len(tautan) == 3
    assert [a['href'] for a in tautan if a.get('aria-current') == 'true'] == [
        '/anak/7?section=perkembangan&bagian=penguasaan&tampilan=' + aktif]
    aktif_css = GAYA_LAPORAN.split('.laporan-pilihan a[aria-current="true"]', 1)[1].split('}', 1)[0]
    assert 'font-weight:700' in aktif_css and 'border:2px solid' in aktif_css


@pytest.mark.parametrize('peran', ['guru', 'admin'])
def test_kepala_anak_tanpa_tautan_ubah_kelas(peran):
    """Ubah kelas hanya lewat menu akun, bukan kepala profil anak."""
    h = P.bingkai(dict(id=7, nama='Contoh <uji>', tingkat='P3', pemilik='guru'), 'latihan', 0, '', peran=peran, kelas_sekolah=2)
    assert 'class="profil-identitas-st"' in h
    assert 'Ubah kelas' not in h
    assert not [a for a in Tautan(h).tautan if a.get('class') == 'profil-ubah-kelas-st']
    assert 'Kelas 2' in h and 'Contoh &lt;uji&gt;' in h


def test_kepala_anak_meringkas_kembali_ke_baris_identitas():
    """Kembali tidak lagi menjadi baris terpisah di atas identitas."""
    h = P.bingkai(dict(id=7, nama='Contoh', tingkat='P3', pemilik='guru'), 'latihan', 0, '', peran='guru', kelas_sekolah=2)
    assert 'class="jejak"' not in h
    kepala = h.split('<header class="kepala-anak-st editorial-kepala-st">', 1)[1].split('</header>', 1)[0]
    assert 'class="profil-kembali-st"' in kepala
    assert '&larr; Semua anak' in kepala
    a = [a for a in Tautan(h).tautan if a.get('class') == 'profil-kembali-st']
    assert len(a) == 1 and a[0]['href'] == '/guru'


def test_catatan_batas_manual_punya_jarak_dari_tombol():
    """Kotak catatan tidak lagi menempel pada tombol Buat latihan."""
    aturan = P.GAYA_PROFIL.split('.profil-workspace-st .profil-batas-manual-st', 1)[1].split('}', 1)[0]
    assert f'margin:{T.SP_5} 0 0' in aturan


def test_pilihan_latihan_menjelaskan_isi_di_dekat_topik_tanpa_instruksi_ganda(db):
    kon, sid, _ = db
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
    awal = tuple(kon.iterdump())
    h = teacher_pages.halaman_anak(
        kon, siswa, pengguna='guru', query='section=latihan'
    ).decode()
    assert tuple(kon.iterdump()) == awal
    assert 'Pilih materi dan bentuk latihan.' not in h
    assert '<summary>Lihat contoh soal</summary>' not in h
    panel = h.split('id="form-latihan-manual-', 1)[1].split('</form>', 1)[0]
    assert 'id="manual-topik"' in panel
    assert 'name="profil_parameter"' not in panel
    assert 'Jagomat memilih cakupan yang sesuai' in panel
    assert teacher_pages.INFO_LATIHAN_BEBAS in h
    assert h.count('name="jenis-latihan"') >= 2
    assert 'name="topik"' in h and 'type="checkbox"' in h
    assert 'A–D hanya penanda' not in panel
    assert 'tanpa pilihan A–D' in panel
    assert 'Pilihan ganda untuk latihan manual, belum menjadi bukti penguasaan.' in h

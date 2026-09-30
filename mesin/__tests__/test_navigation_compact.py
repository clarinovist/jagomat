"""Regresi navigasi tanpa centang dan pengantar profil yang lebih ringkas."""
import re
from html.parser import HTMLParser

import pytest

import profile_workspace as P
import report_navigation as N
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
        '/laporan/7?section=penguasaan&tampilan=' + aktif]
    aktif_css = GAYA_LAPORAN.split('.laporan-pilihan a[aria-current="true"]', 1)[1].split('}', 1)[0]
    assert 'font-weight:700' in aktif_css and 'border:2px solid' in aktif_css


@pytest.mark.parametrize('peran,tujuan', [('guru', '/akun?section=siswa'), ('admin', '/admin?section=siswa&id=7')])
def test_ubah_kelas_di_identitas_tujuan_tetap(peran, tujuan):
    h = P.bingkai(dict(id=7, nama='Contoh <uji>', tingkat='P3', pemilik='guru'), 'latihan', 0, '', peran=peran, kelas_sekolah=2)
    assert 'class="profil-identitas-st"' in h
    assert '>Ubah kelas</a>' in h and 'Kelola kelas sekolah' not in h
    a = [a for a in Tautan(h).tautan if a.get('class') == 'profil-ubah-kelas-st']
    assert len(a) == 1 and a[0]['href'] == tujuan
    assert 'Kelas 2' in h and 'Contoh &lt;uji&gt;' in h


def test_pilihan_latihan_menjelaskan_isi_di_dekat_topik_tanpa_instruksi_ganda(db):
    kon, sid, _ = db
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
    awal = tuple(kon.iterdump())
    h = teacher_pages.halaman_anak(kon, siswa, pengguna='guru').decode()
    assert tuple(kon.iterdump()) == awal
    assert 'Pilih materi dan bentuk latihan.' not in h
    assert '<summary>Lihat contoh soal</summary>' not in h
    panel = h.split('id="form-latihan-manual-', 1)[1].split('</form>', 1)[0]
    assert panel.index('id="manual-topik"') < panel.index('<legend>Pilih isi latihan</legend>')
    assert panel.count('name="profil_parameter"') == 4
    assert 'data-contoh="pola-bilangan:P3"' in panel
    assert teacher_pages.INFO_LATIHAN_BEBAS in h
    assert h.count('name="jenis-latihan"') >= 2
    assert 'name="topik"' in h and 'type="checkbox"' in h
    assert 'A–D hanya penanda' in panel
    assert 'bukan urutan kemampuan atau kelas anak' in panel
    assert 'Pilihan ganda untuk latihan manual, belum menjadi bukti penguasaan.' in h

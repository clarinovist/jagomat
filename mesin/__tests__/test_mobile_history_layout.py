"""Riwayat mobile: filter native, pagination ringkas, dan status tetap utuh."""
from html.parser import HTMLParser
import re

import pytest

import database
import profile_history
import profile_workspace
import teacher_pages
from http_test_kit import ServerUji, SANDI_GURU


class Markup(HTMLParser):
    def __init__(self, teks):
        super().__init__()
        self.elemen = []
        self.feed(teks)

    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'riwayat-mobile.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Anak <Contoh>', pemilik='guru')
        for seed in range(41):
            kon.execute("INSERT INTO sesi(siswa_id,seed,tanggal,topik) VALUES(?,?,'2026-09-18','campuran')", (siswa, seed))
        yield kon, siswa


def render(db, query='section=riwayat'):
    kon, sid = db
    siswa = kon.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
    return teacher_pages.halaman_anak(kon, siswa, pengguna='guru', privat=True, query=query).decode().split('</style>', 1)[1]


def test_filter_details_tertutup_dengan_ringkasan_dan_satu_reset(db):
    isi = render(db, 'section=riwayat&topik=campuran&jenis=bebas&tinjauan=belum_dikirim&mulai=2026-01-01&halaman=2')
    dom = Markup(isi)
    details = [a for tag,a in dom.elemen if tag=='details' and a.get('class')=='profil-saring-st']
    assert len(details)==1 and 'open' not in details[0]
    summary = re.search(r'<summary class="profil-saring-judul-st">(.*?)</summary>',isi,re.S).group(1)
    assert 'Saring riwayat' in summary and 'Campuran semua topik' in summary
    assert 'Latihan bebas' in summary and 'Belum dikirim' in summary and '2026-01-01' in summary
    assert isi.count('>Reset filter</a>')==1
    assert f'href="/anak/{db[1]}?section=riwayat"' in isi
    assert '<option value="campuran" selected>Campuran semua topik</option>' in isi
    assert 'name="halaman"' not in isi
    assert 'topik=campuran' in isi and 'halaman=3' in isi


def test_default_tanpa_reset_dan_empty_tanpa_paging_palsu(db):
    assert '>Reset filter</a>' not in render(db)
    isi = render(db, 'section=riwayat&mulai=2027-01-01')
    assert 'Tidak ada sesi yang cocok' in isi
    assert isi.count('Menampilkan 0–0 dari 0 sesi')==1
    assert 'class="profil-pager-st"' not in isi
    assert isi.count('>Reset filter</a>')==1
    assert 'class="profil-kosong-st"' in isi


@pytest.mark.parametrize('halaman,total,jumlah', [(1,41,3),(2,41,3),(3,41,3)])
def test_pager_satu_markup_status_dan_tujuan_sesuai_filter(halaman,total,jumlah):
    f = profile_history.parse_filter('section=riwayat&topik=campuran&halaman='+str(halaman))
    isi = profile_workspace._pager(7,f,total)
    assert isi.count('<nav')==1
    assert f'Halaman {halaman}/{jumlah}' in isi
    dom = Markup(isi)
    nav_links = [a for t,a in dom.elemen if t=='a' and a.get('class') in ('profil-prev-st','profil-next-st')]
    assert len(nav_links)==(2 if halaman==2 else 1)
    assert all('topik=campuran' in a['href'] for a in nav_links)
    if halaman==1: assert 'class="profil-prev-st" aria-disabled="true"' in isi
    if halaman==3: assert 'class="profil-next-st" aria-disabled="true"' in isi


@pytest.mark.parametrize('total',[0,1,20])
def test_pager_tidak_dibuat_untuk_satu_halaman(total):
    assert profile_workspace._pager(7,profile_history.FilterProfil(),total)==''


def test_metadata_dan_status_tidak_dibuang_demi_ringkas(db):
    isi=render(db)
    baris=re.search(r'<tr data-sesi-id=".*?</tr>',isi,re.S).group()
    assert 'class="riwayat-meta-st"' in baris
    assert 'Latihan bebas' in baris and 'Profil P3' in baris and 'Mode Diagnosa' in baris
    assert 'Sesi #' in baris and 'Belum Dikerjakan' in baris and 'Menunggu pengiriman' in baris
    assert baris.count('>Buka →</a>')==1
    assert 'Bagikan sesi ke anak' in baris


def test_css_mobile_filter_penuh_dan_status_tidak_dipotong():
    css=profile_workspace.GAYA_PROFIL
    mobile=css.split('@media(max-width:48rem)',1)[1]
    blok=re.search(r'\.profil-workspace-st \.profil-filter-st \{([^}]+)',mobile).group(1)
    assert 'grid-template-columns:minmax(0,1fr)' in blok
    assert '.profil-page-number-st' in mobile and 'display:none' in mobile
    assert 'text-overflow:ellipsis' not in mobile
    pager=re.search(r'\.profil-workspace-st \.profil-pager-st \{([^}]+)',mobile).group(1)
    assert 'flex-wrap:wrap' in pager
    assert 'min-width:min(100%,6em)' in mobile


@pytest.fixture()
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    with s.buka() as kon:
        sid=database.tambah_siswa(kon,'Anak Navigasi',pemilik='guru')
        for n in range(25):
            kon.execute("INSERT INTO sesi(siswa_id,seed,topik) VALUES(?,?,'statistika')",(sid,n))
    yield s,sid
    s.berhenti()


def test_http_reset_filter_kembali_ke_anak_sama_tanpa_write(server):
    s,sid=server
    with s.buka() as kon: sebelum=tuple(kon.iterdump())
    kode,isi,_=s.minta(f'/anak/{sid}?section=riwayat&mulai=2027-01-01',auth=('guru',SANDI_GURU))
    assert kode==200
    reset=re.search(r'<a class="profil-reset-st" href="([^"]+)">Reset filter</a>',isi).group(1)
    assert reset==f'/anak/{sid}?section=riwayat'
    kode,isi,_=s.minta(reset,auth=('guru',SANDI_GURU))
    assert kode==200 and 'Menampilkan 1–20 dari 25 sesi' in isi
    assert 'class="profil-reset-st"' not in isi.split('</style>',1)[1]
    with s.buka() as kon: assert tuple(kon.iterdump())==sebelum

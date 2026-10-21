"""Pencarian/filter GET beranda: identitas sendiri, HTML aman, tanpa JavaScript."""
import html
import re
from html.parser import HTMLParser
from urllib.parse import urlencode

import pytest

import auth
import database
import teacher_home_priority as P
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
from test_teacher_home_priority import _sesi_terpandu, _kirim


class Markup(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.tags = []
        self.feed(isi)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def nama_kartu(isi):
    return [html.unescape(n) for n in re.findall(r'<h3 class="guru-nama-st">(.*?)</h3>', isi)]


@pytest.fixture
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            menunggu = database.tambah_siswa(kon, 'Aaa Menunggu', 'P3', pemilik='guru')
            baru = database.tambah_siswa(kon, 'Bbb Baru', 'P3', pemilik='guru')
            tindakan = database.tambah_siswa(kon, 'Ccc Terkirim', 'P3', pemilik='guru')
            _sesi_terpandu(kon, menunggu, 301)
            _kirim(kon, _sesi_terpandu(kon, tindakan, 302))
            asing = database.tambah_siswa(kon, 'Rahasia Asing', 'P3', pemilik='guru-lain')
            sesi_asing = database.buat_sesi(kon, asing, 303, jumlah_soal=1)
        auth.tambah_akun('Login-Unik', 'sandi-sintetis-login', 'murid', siswa_id=baru)
        auth.tambah_akun('Login-Asing', 'sandi-sintetis-asing', 'murid', siswa_id=asing)
        uji.ids = (menunggu, baru, tindakan, asing, sesi_asing)
        yield uji
    finally:
        uji.berhenti()


def beranda(server, **query):
    kode, isi, tajuk = server.minta('/guru?' + urlencode(query), auth=('guru', SANDI_GURU))
    assert kode == 200
    assert tajuk.get('Cache-Control') == 'no-store'
    assert tajuk.get('Referrer-Policy') == 'no-referrer'
    return isi


@pytest.mark.parametrize('cari', ['bbb', ' BBB ', 'bBb BaRu', 'login-unik', ' LOGIN-UNIK '])
def test_cari_nama_siswa_atau_login_terhubung(server, cari):
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    isi = beranda(server, cari=cari)
    assert nama_kartu(isi) == ['Bbb Baru']
    assert '1 dari 3' in isi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('kelompok,nama', [
    ('perlu-tindakan', ['Ccc Terkirim']), ('siap', ['Bbb Baru']),
    ('menunggu', ['Aaa Menunggu']), ('semua', ['Ccc Terkirim', 'Bbb Baru', 'Aaa Menunggu']),
])
def test_filter_kelompok_menjaga_sumber_dan_urutan(server, kelompok, nama):
    isi = beranda(server, kelompok=kelompok)
    assert nama_kartu(isi) == nama
    tags = Markup(isi).tags
    assert any(t == 'option' and a.get('value') == kelompok and 'selected' in a for t, a in tags)


def test_kombinasi_kosong_bukan_belum_punya_siswa(server):
    isi = beranda(server, cari='Bbb', kelompok='menunggu')
    assert nama_kartu(isi) == []
    assert 'Tidak ada siswa yang cocok' in isi and '0 dari 3' in isi
    assert 'Tambahkan anak pertama' not in isi
    assert 'id="guru-hapus-filter" href="/guru"' in isi
    assert 'name="cari"' in isi and 'value="Bbb"' in isi


def test_filter_invalid_tidak_menghilangkan_semua_siswa(server):
    assert nama_kartu(beranda(server, kelompok='tidak-valid')) == ['Ccc Terkirim', 'Bbb Baru', 'Aaa Menunggu']


def test_form_get_native_tanpa_js_dan_nilai_escape(server):
    cari = '"><img src=x onerror=alert(1)>'
    isi = beranda(server, cari=cari, kelompok='<script>')
    tags = Markup(isi).tags
    forms = [a for t, a in tags if t == 'form' and a.get('id') == 'guru-filter']
    assert len(forms) == 1 and forms[0]['method'] == 'get' and forms[0]['action'] == '/guru'
    assert not any(t == 'script' or any(k.startswith('on') for k in a) for t, a in tags)
    assert any(t == 'input' and a.get('name') == 'cari' and a.get('value') == cari for t, a in tags)
    assert not any(t == 'img' and a.get('src') == 'x' for t, a in tags)
    assert html.escape(cari, quote=True) in isi
    assert any(t == 'label' and a.get('for') == 'guru-cari' for t, a in tags)
    assert any(t == 'label' and a.get('for') == 'guru-kelompok' for t, a in tags)


def test_nama_siswa_bermarkup_tetap_teks(server):
    nama = 'Sintetis <b>contoh</b> & "aman"'
    with server.buka() as kon:
        database.tambah_siswa(kon, nama, 'P3', pemilik='guru')
    isi = beranda(server, cari='<b>contoh</b>')
    assert nama_kartu(isi) == [nama]
    assert '<b>contoh</b>' not in isi


def test_akun_asing_tidak_dicari_atau_dihitung(server, monkeypatch):
    import students
    asli = students.akun_murid_dari_siswa
    dibaca = []
    def pantau(kon, sid):
        dibaca.append(sid)
        assert sid != server.ids[3], 'Akun asing disentuh pencarian'
        return asli(kon, sid)
    monkeypatch.setattr(students, 'akun_murid_dari_siswa', pantau)
    isi = beranda(server, cari='Login-Asing', pemilik='guru-lain', peran='admin')
    assert nama_kartu(isi) == [] and '0 dari 3' in isi
    assert 'Rahasia Asing' not in isi
    assert dibaca and set(dibaca) <= set(server.ids[:3])


def test_alias_mempertahankan_filter(server):
    kode, isi, _ = server.minta('/ortu?cari=Login-Unik&kelompok=siap', auth=('guru', SANDI_GURU))
    assert kode == 200 and nama_kartu(isi) == ['Bbb Baru']


def test_input_dibatasi_dan_spasi_dinormalkan(server):
    isi = beranda(server, cari=' Bbb   Baru ')
    assert nama_kartu(isi) == ['Bbb Baru']
    isi = beranda(server, cari='x' * 150)
    cari = next(a for t, a in Markup(isi).tags if t == 'input' and a.get('name') == 'cari')
    assert len(cari['value']) == 100 and cari['maxlength'] == '100'


def test_palang_murid_share_dan_404_asing_tetap(server, monkeypatch):
    import share_links
    # Filter nama akun/kelompok tidak boleh mengubah otorisasi resource.
    with server.buka() as kon:
        anak = database.tambah_siswa(kon, 'feby', 'P3', pemilik='guru')
        sesi = database.buat_sesi(kon, anak, 304, jumlah_soal=1)
        token = share_links.buat(kon, sesi)
    asli = P.langkah_anak
    dipanggil = []
    def pantau(*a):
        dipanggil.append(True)
        return asli(*a)
    monkeypatch.setattr(P, 'langkah_anak', pantau)
    for ident in (None, ('feby', SANDI_MURID)):
        kode, isi, _ = server.minta('/guru?cari=Login-Asing&kelompok=semua', auth=ident)
        assert kode == 401 and not nama_kartu(isi)
    kode, isi, _ = server.minta('/mulai/' + token + '?cari=Login-Asing&kelompok=semua')
    assert kode == 200 and 'id="guru-filter"' not in isi
    kode, isi, _ = server.minta('/murid/?cari=Login-Asing&kelompok=semua', auth=('feby', SANDI_MURID))
    assert kode == 200 and 'id="guru-filter"' not in isi
    assert not dipanggil
    for jenis, identitas in (('anak', server.ids[3]), ('sesi', server.ids[4])):
        # URL resource valid; query asing dapat ditolak parser lebih dulu dan
        # menyamarkan kegagalan ownership pada mutation.
        ka, a, _ = server.minta('/' + jenis + '/' + str(identitas), auth=('guru', SANDI_GURU))
        kb, b, _ = server.minta('/' + jenis + '/999999', auth=('guru', SANDI_GURU))
        assert ka == kb == 404 and a == b
    # Akses share/kerja punya timestamp existing; khusus penolakan harus tanpa write.
    with server.buka() as kon:
        sesudah = tuple(kon.iterdump())
    for jenis, identitas in (('anak', server.ids[3]), ('sesi', server.ids[4])):
        server.minta('/' + jenis + '/' + str(identitas), auth=('guru', SANDI_GURU))
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sesudah


def test_gaya_hp_terbatas_beranda_dan_target_sentuh():
    import design_tokens as T
    import teacher_pages
    gaya = teacher_pages.GAYA_FILTER_GURU
    assert '.guru-filter-st' in gaya and '@media (max-width:36rem)' in gaya
    assert 'grid-template-columns:minmax(0, 1fr)' in gaya
    assert 'overflow-wrap:anywhere' in gaya
    assert 'min-height:' + T.TARGET_SENTUH in gaya
    assert '.guru-filter-aksi-st a { color:' + T.AKSEN_TEAL_TUA in gaya


def test_tanpa_pencarian_tidak_memuat_akun(server, monkeypatch):
    import students
    def dilarang(*a):
        pytest.fail('Nama akun tidak diperlukan tanpa pencarian')
    monkeypatch.setattr(students, 'akun_murid_dari_siswa', dilarang)
    assert nama_kartu(beranda(server, kelompok='siap')) == ['Bbb Baru']


def test_filter_tetap_mendahulukan_yang_terlama(server):
    from test_teacher_home_priority import _terkirim_dengan_tanggal
    with server.buka() as kon:
        _terkirim_dengan_tanggal(kon, 'Zzz Terkirim Lama', 5, 401)
        _terkirim_dengan_tanggal(kon, 'Ddd Terkirim Baru', 2, 402)
    assert nama_kartu(beranda(server, cari='terkirim', kelompok='perlu-tindakan')) == [
        'Zzz Terkirim Lama', 'Ddd Terkirim Baru', 'Ccc Terkirim']


@pytest.mark.parametrize('cari', ['%', '_', "' OR 1=1 --"])
def test_pencarian_literal_bukan_wildcard_sql(server, cari):
    assert nama_kartu(beranda(server, cari=cari)) == []


def test_pencocokan_murni_tidak_mengubah_langkah():
    langkah = P.LangkahAnak(1, 'Bbb Baru', 'pemetaan', P.SIAP, 'Siapkan latihan awal')
    assert P.cocok_filter(langkah, 'bbb', 'siap')
    assert P.cocok_filter(langkah, 'login-unik', 'semua', 'Login-Unik')
    assert not P.cocok_filter(langkah, 'asing', 'semua', 'Login-Unik')
    assert not P.cocok_filter(langkah, 'bbb', 'menunggu')
    assert langkah.tindakan == 'pemetaan' and langkah.kelompok == P.SIAP

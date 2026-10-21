"""Kontrak UI akhir: dua laporan, antrian ringkas, form native dan CSP exact."""
from dataclasses import replace
import base64
import hashlib
from html.parser import HTMLParser

import pytest

import assistant_browser
import database
import practice_browser
import reports
import mastery_report
import profile_history
import teacher_pages
from http_test_kit import ServerUji, SANDI_GURU
from test_mastery_targets import _bukti, _baik, HARI


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags=[]
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag,dict(attrs)))


@pytest.fixture
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    with s.buka() as kon:
        s.anak=database.tambah_siswa(kon,'Anak Sintetis','P3',pemilik='guru')
    yield s
    s.berhenti()


def test_mode_native_satu_form_aktif_dan_hash_csp_tanpa_jaringan_baru(server):
    for mode,route in (('manual','sesi-baru'),('gabungan','sesi-gabungan'),('remedial','sesi-remedial')):
        kode,isi,headers=server.minta(f'/anak/{server.anak}?section=latihan&mode_latihan={mode}',auth=('guru',SANDI_GURU))
        assert kode==200
        tags=Markup(isi).tags
        forms=[a for t,a in tags if t=='form' and 'data-latihan-terpadu' in a]
        assert len(forms)==1 and forms[0]['action']==f'/{route}/{server.anak}'
        panels=[a for t,a in tags if t=='fieldset' and 'data-mode-latihan' in a]
        assert len(panels)==3
        assert [a['data-mode-latihan'] for a in panels if 'disabled' not in a]==[mode]
        assert '<noscript>' in isi and 'Tampilkan mode' in isi
        assert f"'sha256-{practice_browser.HASH_LATIHAN}'" in headers['Content-Security-Policy']
        assert '<script>'+practice_browser.SKRIP_LATIHAN+'</script>' in isi
    assert 'fetch(' not in practice_browser.SKRIP_LATIHAN
    assert 'localStorage' not in practice_browser.SKRIP_LATIHAN
    assert practice_browser.HASH_LATIHAN == base64.b64encode(hashlib.sha256(practice_browser.SKRIP_LATIHAN.encode()).digest()).decode()
    _,izin=assistant_browser.lengkapi_respons(b'<body><form data-latihan-terpadu></form></body>')
    assert 'connect-src' not in izin
    assert not practice_browser.memiliki_latihan(b'<body>&lt;form data-latihan-terpadu&gt;</body>')
    assert practice_browser.memiliki_latihan(b'<body><form data-latihan-terpadu></form></body>')
    assert 'input.matches(\':disabled\')' in assistant_browser.SKRIP_CHAT


def test_gabungan_satu_topik_ditolak_server_tanpa_buat_sesi(server):
    with server.buka() as kon:
        sebelum=tuple(kon.iterdump())
    kode,isi,_=server.minta(f'/sesi-gabungan/{server.anak}',auth=('guru',SANDI_GURU),data={'topik':'pola-bilangan','jumlah_soal':'10'})
    assert kode in (200,400)
    with server.buka() as kon:
        assert tuple(kon.iterdump())==sebelum


def test_laporan_dua_tampilan_satu_disclaimer_dan_periode_semua(server):
    with server.buka() as kon:
        awal=tuple(kon.iterdump())
        for bagian in ('ringkasan','penguasaan'):
            isi=reports.konten_laporan(kon,server.anak,query='bagian='+bagian)
            nav=isi.split('</nav>',1)[0]
            assert nav.count('<a ')==2 and '>Perjalanan</a>' not in nav
            assert isi.count('Belum dinilai bukan berarti tidak mampu.')==1
            assert 'perjalanan-titik-baris-st' not in isi
            if bagian=='ringkasan':
                assert 'Semua waktu' in isi and 'name="periode" value="custom"' in isi
                assert isi.count('class="stat"')==4
                assert 'ketepatan jawaban latihan' not in isi
                assert 'class="aktivitas-komposisi-st"' not in isi
            else:
                from mastery_catalog import katalog_target
                assert isi.count('class="peta-pilihan"')==len({t.topik_id for t in katalog_target('P3')})
                assert 'id="detail-materi"' in isi
        lama=reports.konten_laporan(kon,server.anak,query='section=perjalanan')
        assert '<details class="riwayat-putaran-detail" id="perjalanan" open>' in lama
        assert tuple(kon.iterdump())==awal


def test_judul_adaptif_tidak_mengubah_status_reducer():
    peta=mastery_report.peta_penguasaan(_bukti(_baik()),1,HARI)
    before=tuple(peta.status)
    isi=mastery_report.render_peta(peta,reports._tanggal_pendek,ringkas=True)
    assert '1 dari' in isi and 'target menunjukkan pemahaman</h2>' in isi
    kosong=replace(peta,status=tuple(replace(s,status='dipelajari') for s in peta.status))
    isi=mastery_report.render_peta(kosong,reports._tanggal_pendek,ringkas=True)
    assert 'target sedang dipelajari</h2>' in isi
    assert 'Belum ada yang tercatat menunjukkan pemahaman' in isi
    assert peta.status==before


def test_aksesibilitas_warna_dan_aksi_selesai_mobile():
    import design_tokens as T
    import profile_workspace
    from test_profile_terminology import _kontras
    for teks,latar in ((T.TEKS_REVIEW,T.LATAR_REVIEW),
                       (T.KODE_SALAH_KONSEP_TEKS,T.KODE_SALAH_KONSEP_BG),
                       (T.KODE_BENAR_TEKS,T.KODE_BENAR_BG),
                       (T.TEKS_SUBTLE,T.LATAR_NONAKTIF)):
        assert _kontras(teks,latar)>=4.5
    css=profile_workspace.GAYA_PROFIL
    selector='.profil-workspace-st .riwayat-ringkas-st .riwayat-aksi-st > .riwayat-buka-st'
    mobile=css.split('@media(max-width:48rem)',1)[1]
    assert 'background:transparent' in mobile.split(selector+' {',1)[1].split('}',1)[0]


def test_strip_dan_chip_antrian_sesuai_snapshot_aktif(server):
    with server.buka() as kon:
        a=database.buat_sesi(kon,server.anak,seed=11,jumlah_soal=1)
        b=database.buat_sesi(kon,server.anak,seed=12,jumlah_soal=1)
        database.tandai_selesai(kon,a)
        database.tandai_selesai(kon,b)
        database.konfirmasi_hasil(kon,b,guru='guru',dilewati={database.isi_sesi(kon,b)[0]['sesi_soal_id']})
        awal=tuple(kon.iterdump())
        siswa=kon.execute('SELECT * FROM siswa WHERE id=?',(server.anak,)).fetchone()
        isi=teacher_pages.halaman_anak(kon,siswa,query='section=riwayat').decode()
        assert '1 sesi menunggu tinjauan.' in isi
        assert f'href="/sesi/{a}">Tinjau sesi terlama</a>' in isi
        # Banner tidak menyiratkan urutan wajib yang bisa berbeda dari tombol utama Beranda.
        assert 'Mulai dari yang paling lama' not in isi
        hasil,total,_=profile_history.halaman_riwayat(kon,server.anak,profile_history.parse_filter('section=riwayat&tinjauan=perlu_tinjauan'))
        assert total==1 and hasil[0]['id']==a
        assert tuple(kon.iterdump())==awal

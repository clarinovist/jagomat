"""Antrean tinjauan hanya pintasan UI, bukan penilaian atau bukti baru."""
from html.parser import HTMLParser

import pytest

import database
import teacher_pages
from assistant_inline import DrafButir, DrafKoreksi
from test_teacher_corrections import FormKoreksi


class Navigasi(HTMLParser):
    """Ambil tautan antrean dan target kartu tanpa bergantung teks CSS."""
    def __init__(self, html):
        super().__init__()
        self.dalam = False
        self.tautan = []
        self.kartu = []
        self.ids = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'nav' and a.get('aria-labelledby') == 'judul-antrean-tinjauan':
            self.dalam = True
        if self.dalam and tag == 'a':
            self.tautan.append(a['href'])
        if 'koreksi-kartu-st' in a.get('class', '').split():
            self.kartu.append(a)

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.dalam = False


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'navigasi-sintetis.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


@pytest.fixture()
def server(tmp_path, monkeypatch):
    from http_test_kit import ServerUji
    s = ServerUji(tmp_path,monkeypatch)
    with s.buka() as kon:
        s.sesi,s.ids=_sesi(kon)
    yield s
    s.berhenti()


def _sesi(kon):
    siswa = database.tambah_siswa(kon, 'Peserta Navigasi', pemilik='guru')
    sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=3)
    database.tandai_selesai(kon, sesi)
    butir = database.isi_sesi(kon, sesi)
    # Satu dinilai benar, satu hanya cara sebagian, satu kosong total.
    jid = database.simpan_jawaban(kon, butir[0]['sesi_soal_id'], butir[0]['kunci'], 'Cara asli')
    database.simpan_diagnosis(kon, jid, True, None, None)
    database.simpan_jawaban(kon, butir[1]['sesi_soal_id'], '', 'Belum selesai menghitung')
    return sesi, [b['sesi_soal_id'] for b in butir]


def test_antrean_kosong_dan_pekerjaan_sebagian_tanpa_mengubah_form_atau_data(db):
    with database.buka(db) as kon:
        sesi, ids = _sesi(kon)
        sebelum = tuple(kon.iterdump())
        html = teacher_pages.halaman_sesi_stitch(kon, sesi).decode()
        nav = Navigasi(html)
        assert nav.tautan == [f'#tinjau-soal-{sid}' for sid in ids]
        assert '3 soal perlu ditinjau' in html
        assert len(nav.kartu) == 3
        assert len(nav.ids) == len(set(nav.ids))
        for sid in ids:
            kartu = next(k for k in nav.kartu if k.get('id') == f'tinjau-soal-{sid}')
            assert kartu['tabindex'] == '-1'
        form = FormKoreksi(html, sesi).data
        assert all(f'jwb_{sid}' in form for sid in ids)
        assert html.count('>Simpan draf</button>') == 1
        assert html.count('>Konfirmasi hasil sesi</button>') == 1
        assert tuple(kon.iterdump()) == sebelum


def test_draf_efektif_mengubah_antrean_tanpa_menilai_ulang_db(db):
    with database.buka(db) as kon:
        sesi, ids = _sesi(kon)
        draf = DrafKoreksi(tuple((sid, DrafButir('123', 'benar' if n else '',
                    'Cara', '', n == 2, False)) for n, sid in enumerate(ids)), False)
        html = teacher_pages.halaman_sesi_stitch(kon,sesi,draf_koreksi=draf).decode()
        assert Navigasi(html).tautan == [f'#tinjau-soal-{sid}' for sid in ids[:2]]
        assert 'Antrean mengikuti isian yang sedang ditampilkan' in html
        assert database.isi_sesi(kon,sesi)[0]['benar'] == 1


@pytest.mark.parametrize('kode,manual,provenance,antre', [
    (None, False, '', True), ('H', True, '', False), ('T', True, '', False),
    ('T', False, '', True), ('H', True, 'setelah_bantuan', True),
])
def test_keputusan_efektif_dan_provenance_tidak_disamakan_dengan_catatan(db, kode, manual, provenance, antre):
    with database.buka(db) as kon:
        sesi, ids = _sesi(kon)
        jid = database.isi_sesi(kon,sesi)[1]['jawaban_id']
        database.simpan_diagnosis(kon,jid,False,kode,kode,manual=manual)
        kon.execute('''INSERT INTO tinjauan_guru
            (sesi_soal_id,revisi,catatan,provenance,guru) VALUES (?,1,'Catatan tersimpan',?,'guru')''', (ids[1],provenance))
        html = teacher_pages.halaman_sesi_stitch(kon,sesi).decode()
        assert (f'#tinjau-soal-{ids[1]}' in Navigasi(html).tautan) == antre


@pytest.mark.parametrize('keadaan', ['belum_dikirim','dibatalkan','dikonfirmasi','semua_dilewati'])
def test_antrean_tidak_muncul_pada_keadaan_yang_tidak_memerlukan_nav(db, keadaan):
    with database.buka(db) as kon:
        sesi,ids=_sesi(kon)
        if keadaan == 'belum_dikirim':
            kon.execute('UPDATE sesi SET selesai=NULL WHERE id=?',(sesi,))
        elif keadaan == 'dibatalkan':
            kon.execute("UPDATE sesi SET dibatalkan='2026-09-15' WHERE id=?",(sesi,))
        elif keadaan == 'dikonfirmasi':
            database.konfirmasi_hasil(kon,sesi,'guru',dilewati=set(ids[1:]))
        else:
            for sid in ids:
                kon.execute('INSERT INTO tinjauan_guru(sesi_soal_id,revisi,dilewati,guru) VALUES (?,1,1,\'guru\')',(sid,))
        html=teacher_pages.halaman_sesi_stitch(kon,sesi).decode()
        assert not Navigasi(html).tautan
        assert len(Navigasi(html).kartu)==3


def test_navigasi_dihilangkan_seluruh_kartu_dan_form_tetap_utuh(db, monkeypatch):
    import review_navigation
    with database.buka(db) as kon:
        sesi, ids = _sesi(kon)
        sebelum = tuple(kon.iterdump())
        normal = teacher_pages.halaman_sesi_stitch(kon,sesi).decode()
        monkeypatch.setattr(review_navigation, 'render_antrean', lambda *a, **k: '')
        fallback = teacher_pages.halaman_sesi_stitch(kon,sesi).decode()
        assert not Navigasi(fallback).tautan
        assert len(Navigasi(normal).kartu) == len(Navigasi(fallback).kartu) == len(ids)
        assert FormKoreksi(normal,sesi).data == FormKoreksi(fallback,sesi).data
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('sid,nomor', [(0,1), (1,0), ('<script>',1), (1,'<script>')])
def test_navigasi_hanya_merender_identitas_kartu_internal(sid,nomor):
    from review_navigation import render_antrean
    with pytest.raises(ValueError):
        render_antrean([(sid,nomor)])


def test_simpan_tinjauan_redirect_get_menampilkan_status_tetap(server):
    from http_test_kit import SANDI_GURU
    s=server
    status,html,_=s.minta(f'/sesi/{s.sesi}',auth=('guru',SANDI_GURU))
    data=FormKoreksi(html,s.sesi).data
    data[f'catatan_tinjauan_{s.ids[1]}']='Catatan tinjauan sintetis'
    status,html,_=s.minta(f'/sesi/{s.sesi}/tinjauan',auth=('guru',SANDI_GURU),data=data)
    assert status==200
    assert 'Tinjauan tersimpan. Konfirmasi hasil tetap merupakan langkah terpisah.' in html
    assert html.count('>Simpan draf</button>')==1
    assert html.count('>Konfirmasi hasil sesi</button>')==1
    assert FormKoreksi(html,s.sesi).data[f'catatan_tinjauan_{s.ids[1]}']=='Catatan tinjauan sintetis'
    with s.buka() as kon:
        assert kon.execute('SELECT count(*) FROM snapshot_outcome').fetchone()[0]==0


@pytest.mark.parametrize('query', ['pesan=TEKS_ASING_%3Cscript%3E', 'pesan=Tinjauan%20tersimpan&pesan=lain'])
def test_query_pesan_bebas_atau_ganda_tidak_diecho(server,query):
    from http_test_kit import SANDI_GURU
    status,html,_=server.minta(f'/sesi/{server.sesi}?{query}',auth=('guru',SANDI_GURU))
    assert status==200
    assert 'TEKS_ASING' not in html
    assert 'Tinjauan tersimpan. Konfirmasi hasil tetap merupakan langkah terpisah.' not in html


def test_galat_memakai_daftar_masalah_existing_bukan_dua_antrean(db):
    with database.buka(db) as kon:
        sesi,ids=_sesi(kon)
        html=teacher_pages.halaman_sesi_stitch(kon,sesi,masalah_konfirmasi=((ids[2],3,'kosong'),)).decode()
        assert not Navigasi(html).tautan
        assert html.count(f'href="#tinjau-soal-{ids[2]}"')==1
        assert 'Ada 1 soal yang perlu ditinjau' in html

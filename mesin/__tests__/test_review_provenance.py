"""Provenance tinjauan, rollback, konflik tab, dan draft lokal Pendamping."""
import sqlite3

import pytest

import database
import learning_cycle_service as layanan
import review_store
import student_submissions
import teacher_pages
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
from test_teacher_corrections import FormKoreksi


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'review.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Peserta Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=1)
        student_submissions.arsipkan(kon, sesi, 'akun')
        database.tandai_selesai(kon, sesi)
    return path, sesi


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        siswa = database.tambah_siswa(kon, 'feby', pemilik='guru')
        s.sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=1)
        s.sid = database.isi_sesi(kon, s.sesi)[0]['sesi_soal_id']
    assert s.minta(f'/murid/kerjakan/{s.sesi}', auth=('feby', SANDI_MURID), data={'aksi':'selesai'})[0] == 200
    yield s
    s.berhenti()


def _form(s):
    status, html, _ = s.minta(f'/sesi/{s.sesi}', auth=('guru', SANDI_GURU))
    assert status == 200
    return FormKoreksi(html, s.sesi).data, html


def test_kosong_ui_pertanyaan_relevan_dan_roundtrip_tinjauan(server):
    s = server
    data, html = _form(s)
    assert 'apa yang membuatmu belum menjawab?' in html
    assert 'Kamu dapat jawaban ini dari mana?' not in html
    assert html.count('>Simpan draf</button>') == 1
    assert html.count('>Konfirmasi hasil sesi</button>') == 1
    assert 'Jawaban saat dikirim' in html
    data[f'catatan_tinjauan_{s.sid}'] = 'Belum sempat <script>contoh</script>'
    status, _, _ = s.minta(f'/sesi/{s.sesi}/tinjauan', auth=('guru', SANDI_GURU), data=data)
    assert status == 200
    pulih, html = _form(s)
    assert pulih[f'catatan_tinjauan_{s.sid}'] == data[f'catatan_tinjauan_{s.sid}']
    assert '<script>contoh</script>' not in html and '&lt;script&gt;contoh&lt;/script&gt;' in html
    with s.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0
        sebelum = tuple(kon.iterdump())
    assert s.minta(f'/sesi/{s.sesi}/konfirmasi', auth=('guru', SANDI_GURU), data=pulih)[0] == 400
    with s.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    pulih[f'dilewati_{s.sid}'] = '1'
    assert s.minta(f'/sesi/{s.sesi}/konfirmasi', auth=('guru', SANDI_GURU), data=pulih)[0] == 200
    with s.buka() as kon:
        assert kon.execute('SELECT dilewati FROM snapshot_outcome').fetchone()[0] == 1
        assert kon.execute('SELECT COUNT(*) FROM tinjauan_outcome').fetchone()[0] == 1


def test_tab_lama_ditolak_draf_tetap_terlihat(server):
    s = server
    data, _ = _form(s)
    terbaru = dict(data, **{f'catatan_tinjauan_{s.sid}': 'Catatan terbaru'})
    assert s.minta(f'/sesi/{s.sesi}/tinjauan', auth=('guru', SANDI_GURU), data=terbaru)[0] == 200
    lama = dict(data, **{f'catatan_tinjauan_{s.sid}': 'Catatan tab lama'})
    status, html, _ = s.minta(f'/sesi/{s.sesi}/tinjauan', auth=('guru', SANDI_GURU), data=lama)
    assert status == 400 and 'Catatan tab lama' in html
    assert 'Tinjauan berubah di halaman lain' in html
    with s.buka() as kon:
        assert review_store.muat(kon, s.sesi)[s.sid]['catatan'] == 'Catatan terbaru'
    # Retry payload yang sama tidak membuat revisi baru.
    assert s.minta(f'/sesi/{s.sesi}/tinjauan', auth=('guru', SANDI_GURU), data=terbaru)[0] == 200


def test_koreksi_transkripsi_berprovenance_dan_invalidasi(db):
    path, sesi = db
    with database.buka(path) as kon:
        b = database.isi_sesi(kon, sesi)[0]
        sid = b['sesi_soal_id']
        data = {f'jwb_{sid}': b['kunci'], f'cara_{sid}':'Pekerjaan pada kertas',
                f'kode_{sid}':'benar', f'provenance_{sid}':'koreksi_transkripsi',
                f'catatan_tinjauan_{sid}':'Dibaca dari lembar kertas asli', f'versi_tinjauan_{sid}':review_store.tanda(kon,sid)}
        kh = layanan.konfirmasi_dari_form(kon, sesi, 'guru', data)
        lama = tuple(kon.execute('SELECT * FROM tinjauan_outcome').fetchone())
        assert student_submissions.kosong(kon, sesi) == ()
        assert review_store.pengiriman(kon, sesi)[sid]['jawaban'] == ''
        assert layanan.konfirmasi_dari_form(kon, sesi, 'guru', data) == kh
        layanan.simpan_tinjauan_dari_form(kon, sesi, 'guru', {
            f'catatan_tinjauan_{sid}':'Sumber kertas dikonfirmasi ulang', f'versi_tinjauan_{sid}':review_store.tanda(kon,sid)})
        assert kon.execute('SELECT dikonfirmasi_guru FROM sesi').fetchone()[0] is None
        assert tuple(kon.execute('SELECT * FROM tinjauan_outcome').fetchone()) == lama
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("UPDATE tinjauan_outcome SET data_json='[]'")


def test_t_otomatis_warisan_tidak_lolos_noop(db):
    path, _ = db
    with database.buka(path) as kon:
        siswa = kon.execute('SELECT id FROM siswa').fetchone()[0]
        sesi = database.buat_sesi(kon, siswa, 8, jumlah_soal=1)
        database.tandai_selesai(kon, sesi)  # Warisan tanpa arsip pengiriman.
        sid = database.isi_sesi(kon, sesi)[0]['sesi_soal_id']
        jid = database.simpan_jawaban(kon, sid, '', '[pilihan] bingung')
        database.simpan_diagnosis(kon, jid, False, 'T', 'T', manual=False)
        with pytest.raises(ValueError):
            database.konfirmasi_hasil(kon, sesi, 'guru')
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0


def test_arsip_gagal_rollback_semua_butir(db):
    path, _ = db
    with database.buka(path) as kon:
        siswa = kon.execute('SELECT id FROM siswa').fetchone()[0]
        sesi = database.buat_sesi(kon, siswa, 42, jumlah_soal=2)
        kon.execute("CREATE TEMP TRIGGER gagal_arsip BEFORE INSERT ON pengiriman_butir WHEN NEW.nomor=2 BEGIN SELECT RAISE(ABORT,'gagal sintetis'); END")
        with pytest.raises(sqlite3.IntegrityError):
            student_submissions.arsipkan(kon, sesi, 'akun')
        assert kon.execute('SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?',(sesi,)).fetchone() is None
        assert kon.execute('SELECT selesai FROM sesi WHERE id=?',(sesi,)).fetchone()[0] is None


@pytest.mark.parametrize('kode', ['K', 'H', 'benar'])
def test_semua_hasil_bantuan_ditolak_sebagai_bukti_mandiri(db, kode):
    path, sesi = db
    with database.buka(path) as kon:
        b = database.isi_sesi(kon, sesi)[0]
        sid = b['sesi_soal_id']
        data = {f'jwb_{sid}':'', f'cara_{sid}':'', f'kode_{sid}':kode,
                f'catatan_tinjauan_{sid}':'Kesulitan setelah diberi contoh',
                f'provenance_{sid}':'setelah_bantuan', f'jawaban_bantuan_{sid}':'123',
                f'versi_tinjauan_{sid}':review_store.tanda(kon,sid)}
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError):
            layanan.konfirmasi_dari_form(kon,sesi,'guru',data)
        assert tuple(kon.iterdump()) == sebelum
        data[f'dilewati_{sid}'] = '1'
        layanan.konfirmasi_dari_form(kon,sesi,'guru',data)
        assert kon.execute('SELECT dilewati,kode_final FROM snapshot_outcome').fetchone()[:] == (1,None)


def test_post_legacy_kode_parsial_mempertahankan_jawaban_cara(server):
    s = server
    # Sesi uji kedua memiliki pengiriman jawaban asli, bukan mengedit arsip kosong.
    with s.buka() as kon:
        siswa = kon.execute('SELECT id FROM siswa').fetchone()[0]
        sesi = database.buat_sesi(kon,siswa,9,jumlah_soal=1)
        b = database.isi_sesi(kon,sesi)[0]
        sid = b['sesi_soal_id']
        jid = database.simpan_jawaban(kon,sid,b['kunci'],'Cara asli')
        database.simpan_diagnosis(kon,jid,True,None,None)
        student_submissions.arsipkan(kon,sesi,'akun')
        database.tandai_selesai(kon,sesi)
        versi = review_store.tanda(kon,sid)
    status,_,_ = s.minta(f'/sesi/{sesi}',auth=('guru',SANDI_GURU),data={f'kode_{sid}':'H',f'versi_tinjauan_{sid}':versi})
    assert status == 200
    with s.buka() as kon:
        baru = database.isi_sesi(kon,sesi)[0]
        assert baru['jawaban'] == b['kunci'] and baru['cara'] == 'Cara asli'
        assert baru['kode_final'] == 'H'


def test_arsip_yang_sudah_ada_tidak_bisa_dihapus_bersama_sesi_berbukti(db):
    path, sesi = db
    with database.buka(path) as kon:
        sid = database.isi_sesi(kon, sesi)[0]['sesi_soal_id']
        database.konfirmasi_hasil(kon, sesi, 'guru', dilewati={sid})
        with pytest.raises(sqlite3.IntegrityError):
            database.hapus_sesi(kon, sesi)
        assert kon.execute('SELECT count(*) FROM pengiriman_butir').fetchone()[0] == 1


def test_pengalaman_parsial_disimpan_tanpa_mengosongkan_jawaban(db):
    path, sesi = db
    with database.buka(path) as kon:
        sid = database.isi_sesi(kon, sesi)[0]['sesi_soal_id']
        layanan.simpan_tinjauan_dari_form(kon,sesi,'guru',{f'belum_{sid}':'1'})
        b = database.isi_sesi(kon,sesi)[0]
        assert b['belum_pernah'] == 1 and b['kode_final'] is None
        before = tuple(kon.iterdump())
        layanan.simpan_tinjauan_dari_form(kon,sesi,'guru',{})
        assert tuple(kon.iterdump()) == before


def test_lewati_parsial_disimpan_dan_konfirmasi_parsial_memakainya(db):
    path,sesi = db
    with database.buka(path) as kon:
        sid = database.isi_sesi(kon,sesi)[0]['sesi_soal_id']
        layanan.simpan_tinjauan_dari_form(kon,sesi,'guru',{f'dilewati_{sid}':'1'})
        assert review_store.muat(kon,sesi)[sid]['dilewati'] == 1
        layanan.konfirmasi_dari_form(kon,sesi,'guru',{})
        assert kon.execute('SELECT dilewati FROM snapshot_outcome').fetchone()[0] == 1


def test_tab_lama_pengalaman_parsial_ditolak(db):
    path,sesi = db
    with database.buka(path) as kon:
        sid = database.isi_sesi(kon,sesi)[0]['sesi_soal_id']
        versi = review_store.tanda(kon,sid)
        layanan.simpan_tinjauan_dari_form(kon,sesi,'guru',{f'catatan_tinjauan_{sid}':'Versi baru'})
        with pytest.raises(ValueError):
            layanan.simpan_tinjauan_dari_form(kon,sesi,'guru',{f'belum_{sid}':'1',f'versi_tinjauan_{sid}':versi})
        assert not database.isi_sesi(kon,sesi)[0]['belum_pernah']


def test_marker_parsial_clear_tidak_menghapus_checkbox_lain(server):
    s=server
    data,_=_form(s)
    data[f'belum_{s.sid}']='1'
    data[f'dilewati_{s.sid}']='1'
    assert s.minta(f'/sesi/{s.sesi}/tinjauan',auth=('guru',SANDI_GURU),data=data)[0] == 200
    with s.buka() as kon:
        versi=review_store.tanda(kon,s.sid)
    data={f'hadir_belum_{s.sid}':'1',f'versi_tinjauan_{s.sid}':versi}
    assert s.minta(f'/sesi/{s.sesi}/tinjauan',auth=('guru',SANDI_GURU),data=data)[0] == 200
    with s.buka() as kon:
        assert not database.isi_sesi(kon,s.sesi)[0]['belum_pernah']
        assert review_store.muat(kon,s.sesi)[s.sid]['dilewati'] == 1
        versi=review_store.tanda(kon,s.sid)
    data={f'hadir_dilewati_{s.sid}':'1',f'versi_tinjauan_{s.sid}':versi}
    assert s.minta(f'/sesi/{s.sesi}/tinjauan',auth=('guru',SANDI_GURU),data=data)[0] == 200
    with s.buka() as kon:
        assert not review_store.muat(kon,s.sesi)[s.sid]['dilewati']


def test_perubahan_tinjauan_gagal_atomik_dengan_form_asing(db):
    path, sesi = db
    with database.buka(path) as kon:
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError):
            layanan.simpan_tinjauan_dari_form(kon, sesi, 'guru', {'catatan_tinjauan_999999':'asing'})
        assert tuple(kon.iterdump()) == sebelum


@pytest.mark.parametrize('peran', ['guru', 'admin'])
def test_aktor_post_legacy_dan_snapshot_adalah_principal_server(server, peran):
    import auth
    import json
    s=server
    nama='pendidik-sintetis' if peran=='guru' else 'pengelola-sintetis'
    sandi='sandi-aktor-sintetis-12345'
    auth.tambah_akun(nama,sandi,peran,path=auth.BERKAS_SANDI)
    with s.buka() as kon:
        if peran=='guru':
            kon.execute('UPDATE siswa SET pemilik=?',(nama,))
        versi=review_store.tanda(kon,s.sid)
    data={f'catatan_tinjauan_{s.sid}':'Percakapan oleh aktor server',f'versi_tinjauan_{s.sid}':versi}
    assert s.minta(f'/sesi/{s.sesi}',auth=(nama,sandi),data=data)[0]==200
    with s.buka() as kon:
        assert review_store.muat(kon,s.sesi)[s.sid]['guru']==nama
    status,html,_=s.minta(f'/sesi/{s.sesi}',auth=(nama,sandi))
    data=FormKoreksi(html,s.sesi).data
    data[f'dilewati_{s.sid}']='1'
    assert s.minta(f'/sesi/{s.sesi}/konfirmasi',auth=(nama,sandi),data=data)[0]==200
    with s.buka() as kon:
        arsip=json.loads(kon.execute('SELECT data_json FROM tinjauan_outcome').fetchone()[0])
        assert arsip[0]['guru']==nama


def test_migrasi_additive_idempoten_tidak_backfill(db):
    path, sesi = db
    with database.buka(path) as kon:
        siswa = kon.execute('SELECT id FROM siswa').fetchone()[0]
        lama = database.buat_sesi(kon, siswa, 42, jumlah_soal=2)
        database.tandai_selesai(kon, lama)
    database.siapkan(path)
    with database.buka(path) as kon:
        sebelum = tuple(kon.iterdump())
    database.siapkan(path)
    with database.buka(path) as kon:
        assert tuple(kon.iterdump()) == sebelum
        assert kon.execute('SELECT 1 FROM pengiriman_sesi WHERE sesi_id=?',(lama,)).fetchone() is None
        assert kon.execute('PRAGMA foreign_key_check').fetchall() == []
        assert kon.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

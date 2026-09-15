"""Regresi pengiriman kosong dan arsip asli memakai data sintetis."""
import pytest
import database
import students
from diagnosis import diagnosa


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'submission.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


@pytest.mark.parametrize('jawaban,cara,belum', [('', '', False), ('', '[pilihan] bingung', False),
    ('360', '[pilihan] bingung', False), ('', '', True), ('360', 'Saya hitung', True)])
def test_catatan_ambigu_tidak_otomatis_mendiagnosis(jawaban, cara, belum):
    u = diagnosa('360', jawaban, cara, '', belum, [])
    assert u.kode is None and not u.yakin and not u.benar


def test_form_parsial_tidak_menghapus_jawaban_atau_cara(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Peserta Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=2)
        a, b = database.isi_sesi(kon, sesi)
        students.simpan_jawaban_murid(kon, siswa, sesi, {
            f'jwb_{a["sesi_soal_id"]}': '123', f'cara_{a["sesi_soal_id"]}': 'Cara asli',
            f'jwb_{b["sesi_soal_id"]}': '456', f'cara_{b["sesi_soal_id"]}': 'Cara kedua',
        })
        students.simpan_jawaban_murid(kon, siswa, sesi, {f'cara_{a["sesi_soal_id"]}': 'Cara diperjelas'})
        a, b = database.isi_sesi(kon, sesi)
        assert a['jawaban'] == '123' and a['cara'] == 'Cara diperjelas'
        assert b['jawaban'] == '456' and b['cara'] == 'Cara kedua'


def test_checkbox_anak_parsial_set_noop_dan_clear(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Peserta Checkbox', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=1)
        sid = database.isi_sesi(kon, sesi)[0]['sesi_soal_id']
        students.simpan_jawaban_murid(kon,siswa,sesi,{f'cara_{sid}':'Cara asli'})
        students.simpan_jawaban_murid(kon,siswa,sesi,{f'blm_{sid}':'on'})
        b = database.isi_sesi(kon,sesi)[0]
        assert b['belum_pernah']==1 and b['cara']=='Cara asli'
        sebelum=tuple(kon.iterdump())
        students.simpan_jawaban_murid(kon,siswa,sesi,{})
        assert tuple(kon.iterdump())==sebelum
        students.simpan_jawaban_murid(kon,siswa,sesi,{f'hadir_blm_{sid}':'1'})
        b=database.isi_sesi(kon,sesi)[0]
        assert b['belum_pernah']==0 and b['cara']=='Cara asli'


@pytest.fixture()
def server(tmp_path, monkeypatch):
    from http_test_kit import ServerUji
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        s.siswa = database.tambah_siswa(kon, 'feby', pemilik='guru')
        s.sesi = database.buat_sesi(kon, s.siswa, 7, jumlah_soal=2)
        s.ids = [b['sesi_soal_id'] for b in database.isi_sesi(kon, s.sesi)]
    yield s
    s.berhenti()


def _kirim(server, data, jalur=None):
    from http_test_kit import SANDI_MURID
    return server.minta(jalur or f'/murid/kerjakan/{server.sesi}',
                        auth=('feby', SANDI_MURID) if jalur is None else None, data=data)


@pytest.mark.parametrize('tautan', [False, True])
def test_kosong_semua_refleksi_opsional_dan_arsip_utuh(server, tautan):
    import share_links
    import student_submissions
    with server.buka() as kon:
        token = share_links.buat(kon, server.sesi) if tautan else None
    jalur = f'/mulai/{token}' if token else None
    status, isi, _ = _kirim(server, {'aksi': 'selesai', 'flow_kosong': '1', 'revisi_pekerjaan': '0'}, jalur)
    assert status == 200 and 'Latihan belum dikirim' in isi
    assert 'Boleh tanpa mengisi alasan' in isi
    assert ' required' not in isi and ' checked' not in isi
    with server.buka() as kon:
        assert kon.execute('SELECT selesai FROM sesi').fetchone()[0] is None
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_sesi').fetchone()[0] == 0
    status, isi, _ = _kirim(server, {'aksi': 'kirim_latihan', 'revisi_pekerjaan': '0'}, jalur)
    assert status == 200
    with server.buka() as kon:
        assert kon.execute('SELECT selesai FROM sesi').fetchone()[0]
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_butir').fetchone()[0] == 2
        assert all(b[0] == '' for b in kon.execute('SELECT jawaban FROM pengiriman_butir'))
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0
        before = tuple(kon.iterdump())
    assert _kirim(server, {'aksi': 'kirim_latihan'}, jalur)[0] in (404, 409)
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == before


def test_refleksi_parsial_kembali_dan_versi_tab_lama(server):
    import student_submissions as sub
    sid = server.ids[0]
    data = {'aksi': 'selesai', 'flow_kosong': '1', 'revisi_pekerjaan': '0', f'cara_{sid}': '[pilihan] bingung'}
    assert _kirim(server, data)[0] == 200
    with server.buka() as kon:
        versi = str(sub.revisi(kon, server.sesi))
    status, isi, _ = _kirim(server, {'aksi': 'kembali', 'revisi_pekerjaan': versi, f'alasan_kosong_{sid}': 'langkah_awal'})
    assert status == 200
    with server.buka() as kon:
        assert sub.refleksi(kon, server.sesi)[sid] == 'langkah_awal'
        b = database.isi_sesi(kon, server.sesi)[0]
        assert b['cara'] == '[pilihan] bingung' and b['jawaban'] == ''
        sebelum = tuple(kon.iterdump())
    assert _kirim(server, {'aksi': 'kirim_latihan', 'revisi_pekerjaan': versi})[0] == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
        versi_baru = str(sub.revisi(kon, server.sesi))
    assert _kirim(server, {'aksi':'kembali', 'revisi_pekerjaan':versi_baru, f'alasan_kosong_{sid}':''})[0] == 200
    with server.buka() as kon:
        assert sub.refleksi(kon, server.sesi)[sid] == ''
        assert database.isi_sesi(kon, server.sesi)[0]['cara'] == '[pilihan] bingung'


def test_arsip_immutable_dan_delete_lifecycle(db):
    import sqlite3
    import student_submissions as sub
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, 'Peserta Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=2)
        sub.arsipkan(kon, sesi, 'akun')
        database.tandai_selesai(kon, sesi)
        for sql in ('UPDATE pengiriman_butir SET jawaban=\'999\'', 'DELETE FROM pengiriman_butir', 'DELETE FROM pengiriman_sesi'):
            with pytest.raises(sqlite3.IntegrityError, match='immutable'):
                kon.execute(sql)
        assert database.hapus_sesi(kon, sesi)
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_butir').fetchone()[0] == 0
        assert kon.execute('PRAGMA foreign_key_check').fetchall() == []


def test_simpan_tinjauan_tanpa_bukti_dan_hasil_bantuan_ditolak(server):
    import review_store
    import learning_cycle_service as layanan
    import student_submissions as sub
    sid = server.ids[0]
    assert _kirim(server, {'aksi': 'selesai'})[0] == 200  # klien lama tetap bisa kirim
    with server.buka() as kon:
        data = {f'catatan_tinjauan_{sid}': 'Masih bingung, lanjut besok', f'versi_tinjauan_{sid}': review_store.tanda(kon, sid)}
        layanan.simpan_tinjauan_dari_form(kon, server.sesi, 'guru', data)
        assert review_store.muat(kon, server.sesi)[sid]['catatan'] == 'Masih bingung, lanjut besok'
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0
        assert kon.execute('SELECT COUNT(*) FROM kejadian_belajar').fetchone()[0] == 0
        # Bantuan dicatat terpisah; tidak boleh membuat jawaban kosong jadi benar.
        data = {f'catatan_tinjauan_{sid}': 'Diberi contoh', f'provenance_{sid}': 'setelah_bantuan',
                f'jawaban_bantuan_{sid}': '123', f'versi_tinjauan_{sid}': review_store.tanda(kon, sid)}
        layanan.simpan_tinjauan_dari_form(kon, server.sesi, 'guru', data)
        sebelum = tuple(kon.iterdump())
        with pytest.raises(ValueError):
            layanan.konfirmasi_dari_form(kon, server.sesi, 'guru', {f'jwb_{sid}': '123', f'kode_{sid}': 'benar', f'cara_{sid}': 'Contoh'})
        assert tuple(kon.iterdump()) == sebelum


def test_konfirmasi_langsung_tidak_mengakali_provenance(server):
    import student_submissions as sub
    assert _kirim(server, {'aksi': 'selesai'})[0] == 200
    with server.buka() as kon:
        for sid in server.ids:
            jid = database.simpan_jawaban(kon, sid, '123', 'setelah bantuan')
            database.simpan_diagnosis(kon, jid, True, None, None, manual=True)
        with pytest.raises(ValueError, match='transkripsi'):
            database.konfirmasi_hasil(kon, server.sesi, 'guru')
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0

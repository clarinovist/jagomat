"""Aksi kelas sekolah admin terpisah, dengan receipt dan pemulihan sintetis."""
from dataclasses import replace
import sqlite3

import pytest

import admin_contracts as C
import admin_service
import admin_store
import admin_students
import auth
import database
import learning_profile
from http_test_kit import ServerUji
from test_admin_http_c import _login, _minta, _hidden, SANDI_ADMIN


@pytest.fixture
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun('Admin-Profil', SANDI_ADMIN, 'admin')
    with s.buka() as kon:
        s.sid = database.tambah_siswa(kon, 'Sintetis Profil', 'P5', pemilik='guru')
        database.buat_sesi(kon, s.sid, 42, level='P4', jumlah_soal=1)
    yield s
    s.berhenti()


def _tinjau(server):
    token = _login(server, 'Admin-Profil', SANDI_ADMIN)
    kode, isi, _ = _minta(server, '/admin/tinjau?aksi=student_school_grade_update&id=%d' % server.sid, cookie=token)
    assert kode == 200
    return token, dict(aksi='student_school_grade_update', csrf=_hidden(isi, 'csrf'), tinjauan=_hidden(isi, 'tinjauan'), kelas_sekolah='2', revisi_profil='0', reauth=SANDI_ADMIN)


def test_admin_http_kelas_terpisah_retry_dan_stale(server):
    token, data = _tinjau(server)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    kode, _, _ = _minta(server, '/admin/siswa', cookie=token, data=data)
    assert kode == 303
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').kelas_sekolah == 2
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (server.sid,)).fetchone()[0] == 'P5'
        assert kon.execute('SELECT level FROM sesi WHERE siswa_id=?', (server.sid,)).fetchone()[0] == 'P4'
        tersimpan = tuple(kon.iterdump())
    assert tersimpan != sebelum
    assert _minta(server, '/admin/siswa', cookie=token, data=data)[0] == 303
    assert _minta(server, '/admin/siswa', cookie=token, data=dict(data, kelas_sekolah='3'))[0] == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == tersimpan
    kode, isi, _ = _minta(server, '/admin?section=siswa&id=%d' % server.sid, cookie=token)
    assert kode == 200 and 'Kelas 2' in isi and 'Profil P4' in isi and 'Profil P5' in isi
    assert 'student_level_update&amp;' not in isi


@pytest.mark.parametrize('mutasi', ['revisi', 'token', 'aksi', 'kelas', 'target'])
def test_admin_http_token_dan_payload_tidak_cocok(server, mutasi):
    token, data = _tinjau(server)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        admin_sebelum = tuple(kon.iterdump())
    if mutasi == 'revisi': data['revisi_profil'] = '8'
    if mutasi == 'token': data['tinjauan'] += 'x'
    if mutasi == 'aksi': data['aksi'] = 'student_level_update'
    if mutasi == 'kelas': data['kelas_sekolah'] = 'P4'
    if mutasi == 'target': data['siswa_id'] = str(server.sid + 1)
    assert _minta(server, '/admin/siswa', cookie=token, data=data)[0] in (400, 403)
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        assert tuple(kon.iterdump()) == admin_sebelum


def _perintah(server, operasi='op_school_profile_a', revisi=0, kelas=2):
    akun = auth.cari_akun('Admin-Profil')
    return C.PerintahProfilSiswa(operasi, akun['id_akun'], auth.revisi_auth(akun), C.AKSI_UBAH_KELAS_SEKOLAH, server.sid, revisi, kelas, 't' * 64)


def _jalankan(server, perintah, **kw):
    return admin_service.ubah_kelas_sekolah(admin_store.BAWAAN, auth.BERKAS_SANDI, server.db, perintah, **kw)


@pytest.mark.parametrize('failpoint', ['setelah_commit', 'sebelum_finalize'])
def test_recovery_receipt_tidak_menulis_ulang(server, failpoint):
    p = _perintah(server)
    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        _jalankan(server, p, failpoint=failpoint)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    hasil = _jalankan(server, p)
    assert hasil.hasil.status == 'succeeded' and not hasil.baru_dieksekusi
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_admin_perubahan_kelas_menjaga_histori_dan_rekomendasi(server, monkeypatch):
    from test_school_profile_ui import _histori
    from learning_cycle import rencana_berikutnya
    with server.buka() as kon:
        database.buat_putaran_fokus(kon, server.sid, 'P5')
        sesi = kon.execute('SELECT id FROM sesi WHERE siswa_id=?', (server.sid,)).fetchone()[0]
        butir = database.isi_sesi(kon, sesi)[0]
        jawaban = database.simpan_jawaban(kon, butir['sesi_soal_id'], butir['kunci'], 'Langkah sintetis')
        database.simpan_diagnosis(kon, jawaban, benar=True, kode_usulan=None, kode_final=None)
        database.tandai_selesai(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, 'guru')
        sebelum = _histori(kon)
        bukti = database.muat_bukti_siklus(kon, server.sid)
    def terlarang(*args, **kw):
        pytest.fail('kelas sekolah tidak boleh memanggil ganti_level')
    monkeypatch.setattr(database, 'ganti_level', terlarang)
    assert _jalankan(server, _perintah(server)).hasil.status == 'succeeded'
    with server.buka() as kon:
        assert _histori(kon) == sebelum
        sesudah = database.muat_bukti_siklus(kon, server.sid)
        assert sesudah == bukti
        assert rencana_berikutnya(sesudah, server.sid) == rencana_berikutnya(bukti, server.sid)


def test_dua_request_admin_identik_hanya_satu_mutasi(server):
    from concurrent.futures import ThreadPoolExecutor
    p = _perintah(server)
    with ThreadPoolExecutor(max_workers=2) as pool:
        hasil = list(pool.map(lambda _: _jalankan(server, p), range(2)))
    assert all(h.hasil.status == 'succeeded' for h in hasil)
    assert sum(h.baru_dieksekusi for h in hasil) == 1
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').revisi == 1
        assert kon.execute('SELECT COUNT(*) FROM operasi_admin_profil').fetchone()[0] == 1


def test_admin_domain_stale_dan_noop(server):
    p = _perintah(server)
    assert _jalankan(server, p).hasil.status == 'succeeded'
    assert _jalankan(server, replace(p, operasi_id='op_school_profile_b')).hasil.status == 'conflict'
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').revisi == 1
    assert _jalankan(server, replace(p, operasi_id='op_school_profile_c', revisi_profil=1)).hasil.status == 'succeeded'
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').revisi == 1


@pytest.mark.parametrize('sudah_commit', [False, True])
def test_actor_stale_ditolak_termasuk_replay(server, sudah_commit):
    p = _perintah(server)
    if sudah_commit:
        _jalankan(server, p)
    auth.simpan_sandi('sandi-baru-sintetis-admin', 'Admin-Profil')
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    with pytest.raises(admin_service.OperasiTidakDapatDilanjutkan):
        _jalankan(server, p)
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_failpoint_sebelum_commit_rollback(server):
    hasil = _jalankan(server, _perintah(server), failpoint='sebelum_commit')
    assert hasil.hasil.status == 'failed_before_commit'
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').revisi == 0
        assert kon.execute('SELECT COUNT(*) FROM operasi_admin_profil').fetchone()[0] == 0


def test_anchor_tanpa_receipt_tidak_membuka_replay(server):
    p = _perintah(server)
    admin_students.siapkan_anchor_admin(admin_store.BAWAAN, p)
    with pytest.raises(admin_service.OperasiTidakDapatDilanjutkan):
        _jalankan(server, p)
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').revisi == 0


def test_actor_dicabut_setelah_reservasi_sebelum_commit(server, monkeypatch):
    p = _perintah(server)
    asli = admin_students.siapkan_anchor_admin
    def cabut(*args, **kw):
        asli(*args, **kw)
        auth.simpan_sandi('sandi-baru-sintetis-admin', 'Admin-Profil')
    monkeypatch.setattr(admin_students, 'siapkan_anchor_admin', cabut)
    with pytest.raises(admin_service.OperasiTidakDapatDilanjutkan):
        _jalankan(server, p)
    with server.buka() as kon:
        assert learning_profile.baca(kon, server.sid, pemilik='guru').revisi == 0
        assert kon.execute('SELECT COUNT(*) FROM operasi_admin_profil').fetchone()[0] == 0


def test_reader_receipt_memeriksa_sidik(server):
    import learning_profile_admin
    p = _perintah(server)
    _jalankan(server, p)
    with server.buka() as kon:
        kon.execute('UPDATE operasi_admin_profil SET sidik_perintah=?', ('f'*64,))
    with pytest.raises(admin_students.KonflikSiswa):
        learning_profile_admin.baca_receipt(server.db, auth.BERKAS_SANDI, p)


def test_receipt_rusak_tidak_dianggap_sukses(server):
    p = _perintah(server)
    _jalankan(server, p)
    with server.buka() as kon:
        kon.execute("UPDATE operasi_admin_profil SET sidik_perintah=?", ('f'*64,))
    with pytest.raises(admin_service.OperasiTidakDapatDilanjutkan):
        _jalankan(server, p)


def test_migrasi_v4_ke_v5_menjaga_batch_receipt_dan_audit(tmp_path):
    # Bentuk v4 dipulihkan hanya dari DDL tanpa token registry baru; semua data sintetis.
    path = tmp_path / 'admin-v4.db'
    ddl = admin_store._DDL.replace(
        "'student_school_grade_update',", ''
    ).replace("'student_school_grade_updated',", '')
    with sqlite3.connect(path) as kon:
        admin_store._jalankan_ddl(kon, ddl)
        kon.execute("INSERT INTO konfigurasi_pendaftaran VALUES(1,1,1,'closed_standard',1)")
        kon.execute("INSERT INTO operasi_admin VALUES('op_preserved','actor_syn','student_level_update','student','student_1',NULL,0,?,'succeeded','student_level_updated',0,NULL,'not_applicable',1,1)", ('a'*64,))
        kon.execute("INSERT INTO receipt_admin VALUES('op_preserved','actor_syn','student_level_update','student','student_1',?,'student_level_updated',1)", ('a'*64,))
        kon.execute("INSERT INTO audit_admin VALUES(1,'op_preserved','actor_syn','student_level_update','student','student_1',NULL,'succeeded','student_level_updated',1)")
        kon.execute("INSERT INTO audit_admin_perubahan VALUES(1,'student_level','P3','P4')")
        kon.execute("INSERT INTO batch_admin VALUES('batch_syn','actor_syn',1,?,'account_teacher_create','guru',1,'succeeded',NULL,1,1)", ('b'*64,))
        kon.execute("INSERT INTO batch_admin_item VALUES('batch_syn','item_syn',1,'op_batch_syn','target_syn',0,'succeeded','result_syn','confirmed',1)")
        kon.execute("INSERT INTO kelompok_admin VALUES('group_syn','batch_syn','completed',1,1)")
        kon.execute("INSERT INTO kelompok_admin_item VALUES('group_syn','batch_syn','item_syn',1)")
        kon.execute("INSERT INTO penyerahan_admin VALUES('handover_syn','batch_syn','actor_syn',1,?,1,1)", ('c'*64,))
        kon.execute("INSERT INTO penyerahan_admin_item VALUES('handover_syn','batch_syn','item_syn')")
        kon.execute('PRAGMA user_version=4')
        tabel = [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        sebelum = {t: kon.execute('SELECT * FROM ' + t).fetchall() for t in tabel}
    admin_store.siapkan(path)
    admin_store.siapkan(path)
    with sqlite3.connect(path) as kon:
        assert {t: kon.execute('SELECT * FROM ' + t).fetchall() for t in tabel} == sebelum
        assert kon.execute('PRAGMA user_version').fetchone()[0] == 5
        assert kon.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not kon.execute('PRAGMA foreign_key_check').fetchall()
        assert 'student_school_grade_update' in kon.execute("SELECT sql FROM sqlite_master WHERE name='operasi_admin'").fetchone()[0]


def test_migrasi_v4_gagal_rollback(tmp_path, monkeypatch):
    path = tmp_path / 'admin-v4-gagal.db'
    with sqlite3.connect(path) as kon:
        admin_store._jalankan_ddl(kon, admin_store._DDL.replace("'student_school_grade_update',", '').replace("'student_school_grade_updated',", ''))
        kon.execute("INSERT INTO konfigurasi_pendaftaran VALUES(1,1,1,'closed_standard',1)")
        kon.execute('PRAGMA user_version=4')
        sebelum = tuple(kon.iterdump())
    asli = admin_store._jalankan_ddl
    def gagal(kon, skrip):
        asli(kon, skrip)
        if skrip == admin_store._DDL:
            raise RuntimeError('migrasi sintetis gagal')
    monkeypatch.setattr(admin_store, '_jalankan_ddl', gagal)
    with pytest.raises(RuntimeError, match='migrasi sintetis'):
        admin_store.siapkan(path)
    with sqlite3.connect(path) as kon:
        assert tuple(kon.iterdump()) == sebelum
        assert kon.execute('PRAGMA user_version').fetchone()[0] == 4


def test_guru_dan_murid_tidak_mengakses_aksi_admin(server):
    from http_test_kit import SANDI_GURU, SANDI_MURID
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    for nama, sandi in [('guru', SANDI_GURU), ('feby', SANDI_MURID)]:
        token = _login(server, nama, sandi)
        assert _minta(server, '/admin/tinjau?aksi=student_school_grade_update&id=%d' % server.sid, cookie=token)[0] != 200
        assert _minta(server, '/admin/siswa', cookie=token, data={'aksi':'student_school_grade_update','kelas_sekolah':'4'})[0] in (401,403,404)
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_token_aksi_lain_dengan_payload_sama_ditolak(server):
    import admin_security
    token, data = _tinjau(server)
    data['tinjauan'] = admin_security.buat_tinjauan(
        auth.cari_akun('Admin-Profil'), token, 'student_level_update',
        {'siswa_id': server.sid, 'revisi_profil': 0, 'section': 'siswa'},
    )
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    assert _minta(server, '/admin/siswa', cookie=token, data=data)[0] == 403
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_admin_http_stale_setelah_guru_mengubah(server):
    token, data = _tinjau(server)
    with server.buka() as kon:
        learning_profile.simpan_kelas(kon, server.sid, 6, revisi=0, pemilik='guru')
        sebelum = tuple(kon.iterdump())
    assert _minta(server, '/admin/siswa', cookie=token, data=data)[0] == 409
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_reservasi_journal_mengikat_kelas(server):
    p = _perintah(server)
    admin_store.reservasi(admin_store.BAWAAN, p)
    with pytest.raises(admin_store.KonflikOperasi):
        admin_store.reservasi(admin_store.BAWAAN, replace(p, kelas_sekolah=3))


def test_sidik_mengikat_kelas_dan_revisi(server):
    p = _perintah(server)
    assert len({C.sidik_perintah(p), C.sidik_perintah(replace(p, kelas_sekolah=3)), C.sidik_perintah(replace(p, revisi_profil=1)), C.sidik_perintah(replace(p, token_tinjauan='u'*64))}) == 4

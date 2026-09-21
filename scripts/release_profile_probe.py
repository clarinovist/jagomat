"""Probe mandiri admin5/profil/konteks dikirim via stdin, tanpa dependensi image host."""

# Definisi saja; dipanggil hanya di sandbox sintetis. Tidak dipasang pada readiness.
SUMBER_UJI_PROFIL = r'''
def uji_profil_konteks(akar):
    import sqlite3
    from pathlib import Path
    from dataclasses import replace
    import admin_store, admin_students, admin_service, admin_contracts, auth
    import database, learning_profile, learning_profile_admin
    assert admin_store.VERSI_SKEMA == 5
    akar = Path(akar)
    akar.mkdir(parents=True, exist_ok=True)
    admin = akar / 'admin.db'
    belajar = akar / 'belajar.db'
    sandi = akar / 'sandi.json'
    # Fixture v4 memiliki data nyata sintetis untuk membuktikan preservasi.
    ddl = admin_store._DDL.replace("'student_school_grade_update',", '').replace("'student_school_grade_updated',", '')
    with sqlite3.connect(str(admin)) as kon:
        admin_store._jalankan_ddl(kon, ddl)
        kon.execute("INSERT INTO konfigurasi_pendaftaran VALUES(1,7,0,'closed_standard',1)")
        kon.execute("INSERT INTO operasi_admin VALUES('op_lama','actor_syn','student_level_update','student','student_1',NULL,0,?,'succeeded','student_level_updated',0,NULL,'not_applicable',1,1)", ('a'*64,))
        kon.execute("INSERT INTO receipt_admin VALUES('op_lama','actor_syn','student_level_update','student','student_1',?,'student_level_updated',1)", ('a'*64,))
        kon.execute('PRAGMA user_version=4')
        lama = {t: kon.execute('SELECT * FROM '+t).fetchall() for t in ('operasi_admin','receipt_admin','konfigurasi_pendaftaran')}
    for _ in range(2):
        admin_store.siapkan(admin, sekarang=2)
        with admin_store.buka_baca(admin) as kon:
            assert kon.execute('PRAGMA user_version').fetchone()[0] == 5
            assert all([tuple(r) for r in kon.execute('SELECT * FROM '+t)] == rows for t,rows in lama.items())
            assert not kon.execute('PRAGMA foreign_key_check').fetchall()
            assert kon.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    database.siapkan(belajar)
    admin_students.siapkan(belajar)
    auth.tambah_akun('probe-profil-admin','sandi-sintetis-profil-123','admin',sandi)
    akun = auth.cari_akun('probe-profil-admin',path=sandi)
    with database.buka(belajar) as kon:
        sid = database.tambah_siswa(kon,'Anak Sintetis Profil','P4',pemilik='guru')
        sesi = database.buat_sesi(kon,sid,31,level='P4',jumlah_soal=2)
        butir = database.isi_sesi(kon,sesi)
        lewat = {b['sesi_soal_id'] for b in butir}
        database.tandai_selesai(kon,sesi)
        kh = database.konfirmasi_hasil(kon,sesi,'guru',dilewati=lewat)
        assert kon.execute('SELECT COUNT(*) FROM konteks_butir').fetchone()[0] == 2
        assert kon.execute('SELECT versi FROM konteks_sesi WHERE sesi_id=?',(sesi,)).fetchone()[0] == 1
        arsip = kon.execute('SELECT snapshot_json FROM konteks_konfirmasi WHERE konfirmasi_id=?',(kh,)).fetchone()[0]
        assert database.konfirmasi_hasil(kon,sesi,'guru',dilewati=lewat) == kh
        bukti = database.muat_bukti_siklus(kon,sid)
        tabel = ('siswa','sesi','soal','konfirmasi_hasil','snapshot_outcome','konteks_butir','konteks_konfirmasi','kejadian_belajar')
        sejarah = {t:[tuple(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tabel}
    p = admin_contracts.PerintahProfilSiswa('op_profil_probe',akun['id_akun'],auth.revisi_auth(akun),
        admin_contracts.AKSI_UBAH_KELAS_SEKOLAH,sid,0,5,'t'*64)
    # Commit domain berhasil, finalisasi journal gagal: replay wajib receipt asli.
    try:
        admin_service.ubah_kelas_sekolah(admin,sandi,belajar,p,sekarang=3,failpoint='setelah_commit')
    except admin_service.CrashSebelumFinalisasi:
        pass
    else:
        raise AssertionError('crash profil tidak tercapai')
    with database.buka(belajar) as kon:
        sebelum_replay = tuple(kon.iterdump())
    for _ in range(2):
        hasil = admin_service.ubah_kelas_sekolah(admin,sandi,belajar,p,sekarang=4)
        assert hasil.hasil.status == 'succeeded' and not hasil.baru_dieksekusi
    with database.buka(belajar) as kon:
        assert tuple(kon.iterdump()) == sebelum_replay
        assert learning_profile.baca(kon,sid,pemilik='guru').kelas_sekolah == 5
        assert learning_profile.baca(kon,sid,pemilik='guru').revisi == 1
        assert kon.execute('SELECT COUNT(*) FROM operasi_admin_profil').fetchone()[0] == 1
        assert database.muat_bukti_siklus(kon,sid) == bukti
        assert all([tuple(r) for r in kon.execute('SELECT * FROM '+t+' ORDER BY rowid')] == rows for t,rows in sejarah.items())
    stale = replace(p,operasi_id='op_profil_stale',kelas_sekolah=6)
    assert admin_service.ubah_kelas_sekolah(admin,sandi,belajar,stale,sekarang=5).hasil.status == 'conflict'
    with database.buka(belajar) as kon:
        assert tuple(kon.iterdump()) == sebelum_replay
        for sql in ("UPDATE konteks_konfirmasi SET snapshot_json='{}'", 'DELETE FROM konteks_konfirmasi',
                    'INSERT OR REPLACE INTO konteks_konfirmasi SELECT * FROM konteks_konfirmasi'):
            try:
                kon.execute(sql)
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError('arsip konteks dapat dimutasi')
        assert kon.execute('SELECT snapshot_json FROM konteks_konfirmasi').fetchone()[0] == arsip
        # Korupkan salinan sintetis: reader tidak boleh diam-diam melanjutkan.
        kon.execute('DROP TRIGGER konteks_konfirmasi_immutable_delete')
        kon.execute('DELETE FROM konteks_konfirmasi')
        sebelum = tuple(kon.iterdump())
        try:
            database.muat_bukti_siklus(kon,sid)
        except ValueError:
            pass
        else:
            raise AssertionError('arsip hilang tidak ditolak')
        assert tuple(kon.iterdump()) == sebelum
        kon.rollback()
    with database.buka(belajar) as kon:
        kon.execute("UPDATE operasi_admin_profil SET sidik_perintah=? WHERE operasi_id=?",('f'*64,p.operasi_id))
    try:
        learning_profile_admin.baca_receipt(belajar,sandi,p)
    except admin_students.KonflikSiswa:
        pass
    else:
        raise AssertionError('pembaca receipt profil rusak diterima')
    try:
        admin_service.ubah_kelas_sekolah(admin,sandi,belajar,p,sekarang=6)
    except admin_service.OperasiTidakDapatDilanjutkan:
        pass
    else:
        raise AssertionError('receipt profil rusak diterima')
    return 6
'''

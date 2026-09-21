"""Fondasi kelas sekolah terpisah; data sintetis dan histori tetap utuh."""
import sqlite3

import pytest

import database
from learning_cycle import rencana_berikutnya


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'profil.db'
    database.siapkan(path)
    return path


def _profil():
    import learning_profile
    return learning_profile


def _histori(kon):
    tabel = ('siswa', 'soal', 'sesi', 'sesi_soal', 'jawaban', 'diagnosis',
             'putaran_fokus', 'anggota_fokus', 'konfirmasi_hasil',
             'snapshot_outcome', 'penyajian_outcome', 'kejadian_belajar')
    return {nama: tuple(tuple(b) for b in kon.execute('SELECT * FROM ' + nama + ' ORDER BY rowid'))
            for nama in tabel}


def test_skema_profil_terpisah_tanpa_backfill_kelas(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', 'P5', pemilik='guru')
        tabel = {b['name'] for b in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert 'profil_belajar' in tabel
        assert kon.execute('SELECT * FROM profil_belajar WHERE siswa_id=?', (sid,)).fetchone() is None
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=?', (sid,)).fetchone()[0] == 'P5'


def test_kelas_sekolah_tidak_mengubah_bukti_soal_atau_rekomendasi(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', 'P5', pemilik='guru')
        sesi = database.buat_sesi(kon, sid, 42, level='P5', jumlah_soal=1)
        butir = database.isi_sesi(kon, sesi)[0]
        jawaban = database.simpan_jawaban(kon, butir['sesi_soal_id'], butir['kunci'], 'Langkah sintetis')
        database.simpan_diagnosis(kon, jawaban, benar=True, kode_usulan=None, kode_final=None)
        database.tandai_selesai(kon, sesi)
        database.konfirmasi_hasil(kon, sesi, 'guru')
        sebelum = _histori(kon)
        bukti = database.muat_bukti_siklus(kon, sid)
        awal = profil.baca(kon, sid, pemilik='guru')
        assert awal.kelas_sekolah is None and awal.revisi == 0
        tersimpan = profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')
        assert tersimpan.kelas_sekolah == 4 and tersimpan.revisi == 1
        assert profil.simpan_kelas(kon, sid, 5, revisi=1, pemilik='guru').revisi == 2
        assert _histori(kon) == sebelum
        sesudah = database.muat_bukti_siklus(kon, sid)
        assert sesudah == bukti
        assert rencana_berikutnya(sesudah, sid) == rencana_berikutnya(bukti, sid)


@pytest.mark.parametrize('kelas', [0, 7, True, 4.5, '4', 'P4', '', [], {}])
def test_kelas_tidak_sah_ditolak_tanpa_mutasi(db, kelas):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        before = kon.total_changes
        with pytest.raises(ValueError, match='kelas sekolah'):
            profil.simpan_kelas(kon, sid, kelas, revisi=0, pemilik='guru')
        assert kon.total_changes == before


@pytest.mark.parametrize('revisi', [-1, True, 0.0, '0', None])
def test_revisi_tidak_sah_ditolak(db, revisi):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        before = kon.total_changes
        with pytest.raises(ValueError, match='revisi'):
            profil.simpan_kelas(kon, sid, 4, revisi=revisi, pemilik='guru')
        assert kon.total_changes == before


def test_pemilik_asing_dan_id_hilang_identik_tanpa_efek_samping(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='keluarga-lain')
        pesan = []
        for identitas in (sid, 999999):
            for aksi in ('baca', 'simpan'):
                before = kon.total_changes
                with pytest.raises(profil.ProfilTidakDitemukan) as e:
                    if aksi == 'baca':
                        profil.baca(kon, identitas, pemilik='guru')
                    else:
                        profil.simpan_kelas(kon, identitas, 4, revisi=0, pemilik='guru')
                pesan.append(str(e.value))
                assert kon.total_changes == before
        assert len(set(pesan)) == 1
        assert kon.execute('SELECT COUNT(*) FROM profil_belajar').fetchone()[0] == 0


@pytest.mark.parametrize('pemilik', ['', None, 123])
def test_pemilik_kosong_bukan_jalur_admin(db, pemilik):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Warisan')
        with pytest.raises(profil.ProfilTidakDitemukan):
            profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik=pemilik)
        with pytest.raises(profil.ProfilTidakDitemukan):
            profil.baca(kon, sid, pemilik=pemilik)


def test_tab_stale_tidak_menimpa_kelas_baru(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')
        before = kon.total_changes
        with pytest.raises(profil.KonflikProfil):
            profil.simpan_kelas(kon, sid, 5, revisi=0, pemilik='guru')
        assert profil.baca(kon, sid, pemilik='guru').kelas_sekolah == 4
        assert kon.total_changes == before
        assert profil.simpan_kelas(kon, sid, None, revisi=1, pemilik='guru').kelas_sekolah is None


def test_stale_nilai_sama_tetap_ditolak(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')
        with pytest.raises(profil.KonflikProfil):
            profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')


def test_simpan_nilai_sama_tidak_menambah_revisi(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        assert profil.simpan_kelas(kon, sid, None, revisi=0, pemilik='guru').revisi == 0
        pertama = profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')
        before = kon.total_changes
        assert profil.simpan_kelas(kon, sid, 4, revisi=1, pemilik='guru') == pertama
        assert kon.total_changes == before


def test_simpan_tidak_commit_transaksi_pemanggil(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
    with pytest.raises(RuntimeError, match='batal sintetis'):
        with database.buka(db) as kon:
            profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')
            raise RuntimeError('batal sintetis')
    with database.buka(db) as kon:
        assert profil.baca(kon, sid, pemilik='guru').revisi == 0


def test_cas_dua_koneksi_hanya_satu_pemenang(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
    with database.buka(db) as a, database.buka(db) as b:
        ra = profil.baca(a, sid, pemilik='guru').revisi
        rb = profil.baca(b, sid, pemilik='guru').revisi
        profil.simpan_kelas(a, sid, 4, revisi=ra, pemilik='guru')
        a.commit()
        with pytest.raises(profil.KonflikProfil):
            profil.simpan_kelas(b, sid, 5, revisi=rb, pemilik='guru')
        assert profil.baca(b, sid, pemilik='guru').kelas_sekolah == 4


@pytest.mark.parametrize('siswa_id', [True, 0, -1, '1', None, []])
def test_identitas_tidak_sah_tidak_membuka_profil(db, siswa_id):
    profil = _profil()
    with database.buka(db) as kon:
        database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        with pytest.raises(profil.ProfilTidakDitemukan):
            profil.baca(kon, siswa_id, pemilik='guru')
        assert kon.execute('SELECT COUNT(*) FROM profil_belajar').fetchone()[0] == 0


@pytest.mark.parametrize('persaingan', ['revisi', 'pemilik'])
def test_palang_tulis_memeriksa_ulang_setelah_pembacaan(db, persaingan):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')

        class KoneksiBersaing:
            """Sisipkan perubahan sah tepat sebelum statement penulisan."""
            def execute(self, sql, argumen=()):
                if sql.lstrip().startswith('INSERT INTO profil_belajar'):
                    if persaingan == 'revisi':
                        kon.execute('UPDATE profil_belajar SET kelas_sekolah=6, revisi=2 WHERE siswa_id=?', (sid,))
                    else:
                        kon.execute("UPDATE siswa SET pemilik='keluarga-lain' WHERE id=?", (sid,))
                return kon.execute(sql, argumen)

        with pytest.raises(profil.KonflikProfil):
            profil.simpan_kelas(KoneksiBersaing(), sid, 5, revisi=1, pemilik='guru')
        baris = kon.execute('SELECT kelas_sekolah, revisi FROM profil_belajar WHERE siswa_id=?', (sid,)).fetchone()
        assert tuple(baris) == ((6, 2) if persaingan == 'revisi' else (4, 1))


def test_skema_menolak_data_di_luar_kontrak(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        for kelas, revisi in ((0, 1), (7, 1), (4.5, 1), (4, 0), (4, -1), (4, 1.5)):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute('INSERT INTO profil_belajar VALUES (?, ?, ?)', (sid, kelas, revisi))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute('INSERT INTO profil_belajar VALUES (?, 4, 1)', (999999,))


def test_profil_tidak_memblokir_penghapusan_anak_tanpa_bukti(db):
    profil = _profil()
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        profil.simpan_kelas(kon, sid, 4, revisi=0, pemilik='guru')
        kon.execute('DELETE FROM siswa WHERE id=?', (sid,))
        assert kon.execute('SELECT COUNT(*) FROM profil_belajar').fetchone()[0] == 0


def test_migrasi_aditif_idempoten_dan_tanpa_reka_kelas(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Warisan', 'P4', pemilik='guru')
        database.buat_sesi(kon, sid, 42, level='P4', jumlah_soal=1)
        sebelum = _histori(kon)
        kon.execute('DROP TABLE IF EXISTS profil_belajar')
    database.siapkan(db)
    database.siapkan(db)
    with database.buka(db) as kon:
        assert _histori(kon) == sebelum
        assert _profil().baca(kon, sid, pemilik='guru').kelas_sekolah is None
        assert kon.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not kon.execute('PRAGMA foreign_key_check').fetchall()
        _profil().simpan_kelas(kon, sid, 5, revisi=0, pemilik='guru')
    database.siapkan(db)
    with database.buka(db) as kon:
        assert _profil().baca(kon, sid, pemilik='guru').kelas_sekolah == 5
        assert _histori(kon) == sebelum


def test_migrasi_gagal_rollback_tabel_baru_dan_histori(db, monkeypatch):
    import migrate_params
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Warisan', pemilik='guru')
        sebelum = _histori(kon)
        kon.execute('DROP TABLE IF EXISTS profil_belajar')
    def gagal(kon):
        raise RuntimeError('migrasi sintetis gagal')
    monkeypatch.setattr(migrate_params, 'jalankan', gagal)
    with pytest.raises(RuntimeError, match='migrasi sintetis gagal'):
        database.siapkan(db)
    with database.buka(db) as kon:
        assert _histori(kon) == sebelum
        assert kon.execute("SELECT 1 FROM sqlite_master WHERE name='profil_belajar'").fetchone() is None


@pytest.mark.parametrize('sudah_ada_profil', [False, True])
def test_rebuild_siswa_era_unik_global_menjaga_metadata_aditif(tmp_path, sudah_ada_profil):
    path = tmp_path / 'warisan.db'
    with sqlite3.connect(str(path)) as kon:
        kon.execute("CREATE TABLE siswa (id INTEGER PRIMARY KEY, nama TEXT UNIQUE NOT NULL, tingkat TEXT NOT NULL DEFAULT 'P3', dibuat TEXT NOT NULL)")
        kon.execute("INSERT INTO siswa VALUES (1, 'Sintetis', 'P4', '2026-01-01')")
        if sudah_ada_profil:
            from learning_profile_schema import SKEMA_PROFIL_BELAJAR
            database._jalankan_skema(kon, SKEMA_PROFIL_BELAJAR)
            kon.execute('INSERT INTO profil_belajar VALUES (1, 5, 2)')
    database.siapkan(path)
    with database.buka(path) as kon:
        assert kon.execute('SELECT COUNT(*) FROM profil_belajar').fetchone()[0] == int(sudah_ada_profil)
        if sudah_ada_profil:
            assert tuple(kon.execute('SELECT * FROM profil_belajar').fetchone()) == (1, 5, 2)
        assert kon.execute('SELECT tingkat FROM siswa WHERE id=1').fetchone()[0] == 'P4'
        assert not kon.execute('PRAGMA foreign_key_check').fetchall()

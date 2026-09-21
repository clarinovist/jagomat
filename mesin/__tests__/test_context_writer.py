"""Penulis konteks melalui sesi/konfirmasi nyata dengan data sintetis."""
import json
import sqlite3

import pytest

import database
import learning_profile
from generator import buat_lembar


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'sintetis.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', tingkat='P4', pemilik='guru')
        yield kon, siswa


def _sesi(db, **opsi):
    kon, siswa = db
    return database.buat_sesi(kon, siswa, 71, level='P4', jumlah_soal=4, **opsi)


def _konfirmasi(kon, sesi):
    database.tandai_selesai(kon, sesi)
    butir = database.isi_sesi(kon, sesi)
    return database.konfirmasi_hasil(kon, sesi, 'guru',
                                    dilewati={b['sesi_soal_id'] for b in butir})


def test_penulis_membekukan_konteks_per_butir(db):
    kon, _ = db
    sesi = _sesi(db)
    tabel = {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'konteks_butir' in tabel, 'penulis belum menyimpan metadata konteks'
    baris = kon.execute('SELECT * FROM konteks_butir').fetchall()
    assert len(baris) == 4
    assert {b['profil_parameter'] for b in baris} == {'P4'}
    assert all(b['konteks_id'] == 'warisan-v1:' + b['template_id'] + ':P4' for b in baris)
    assert kon.execute('SELECT versi FROM konteks_sesi WHERE sesi_id=?', (sesi,)).fetchone()[0] == 1


def test_konfirmasi_mengarsipkan_konteks_dan_idempoten(db):
    kon, siswa = db
    sesi = _sesi(db)
    kh = _konfirmasi(kon, sesi)
    tabel = {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'konteks_konfirmasi' in tabel, 'snapshot belum mengikat konteks'
    serial = kon.execute('SELECT snapshot_json FROM konteks_konfirmasi WHERE konfirmasi_id=?', (kh,)).fetchone()[0]
    isi = json.loads(serial)
    assert isi['versi'] == 1 and len(isi['butir']) == 4
    assert all(b['target_fokus'] is None for b in isi['butir'])
    learning_profile.simpan_kelas(kon, siswa, 1, revisi=0, pemilik='guru')
    assert _konfirmasi(kon, sesi) == kh
    assert kon.execute('SELECT snapshot_json FROM konteks_konfirmasi').fetchone()[0] == serial


@pytest.mark.parametrize('kolom,nilai', [('level', 'P5'), ('template_id', 'asing')])
def test_konfirmasi_menolak_sumber_konteks_berubah(db, kolom, nilai):
    kon, _ = db
    sesi = _sesi(db)
    soal_id = kon.execute('SELECT soal_id FROM sesi_soal WHERE sesi_id=? LIMIT 1', (sesi,)).fetchone()[0]
    kon.execute('UPDATE soal SET ' + kolom + '=? WHERE id=?', (nilai, soal_id))
    with pytest.raises(ValueError, match='konteks'):
        _konfirmasi(kon, sesi)
    assert kon.execute('SELECT count(*) FROM konfirmasi_hasil').fetchone()[0] == 0


def test_konteks_campuran_ditolak_tanpa_sesi_sebagian(db, monkeypatch):
    kon, siswa = db
    import dataclasses
    lembar = buat_lembar(73, level='P4', jumlah_soal=4)
    rusak = dataclasses.replace(lembar, soal=(dataclasses.replace(lembar.soal[0], level='P5'),) + lembar.soal[1:])
    monkeypatch.setattr(database, 'buat_lembar', lambda *a, **k: rusak)
    with pytest.raises((ValueError, sqlite3.IntegrityError), match='konteks'):
        database.buat_sesi(kon, siswa, 73, level='P4')
    assert kon.execute('SELECT count(*) FROM sesi').fetchone()[0] == 0
    assert kon.execute('SELECT count(*) FROM soal').fetchone()[0] == 0


def test_metadata_immutable_dan_hapus_sesi_tanpa_bukti_tetap_sah(db):
    kon, _ = db
    sesi = _sesi(db)
    for sql in ("UPDATE konteks_butir SET profil_parameter='P5'",
                'DELETE FROM konteks_butir', 'DELETE FROM konteks_sesi',
                'INSERT OR REPLACE INTO konteks_sesi SELECT * FROM konteks_sesi'):
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            kon.execute(sql)
    assert database.hapus_sesi(kon, sesi)
    assert kon.execute('SELECT count(*) FROM konteks_butir').fetchone()[0] == 0
    assert kon.execute('SELECT count(*) FROM konteks_sesi').fetchone()[0] == 0


def test_arsip_konteks_tidak_dapat_diubah_atau_dihapus(db):
    kon, _ = db
    sesi = _sesi(db)
    _konfirmasi(kon, sesi)
    for sql in ("UPDATE konteks_konfirmasi SET snapshot_json='{}'",
                'DELETE FROM konteks_konfirmasi',
                'INSERT OR REPLACE INTO konteks_konfirmasi SELECT * FROM konteks_konfirmasi'):
        with pytest.raises(sqlite3.IntegrityError, match='immutable'):
            kon.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        database.hapus_sesi(kon, sesi)


def test_reader_menolak_arsip_hilang_tanpa_menulis(db):
    from mastery_evidence import lengkapi_bukti_materi
    kon, siswa = db
    sesi = _sesi(db)
    _konfirmasi(kon, sesi)
    kon.execute('DROP TRIGGER konteks_konfirmasi_immutable_delete')
    kon.execute('DELETE FROM konteks_konfirmasi')
    sebelum = tuple(kon.iterdump())
    with pytest.raises(ValueError, match='arsip konteks'):
        lengkapi_bukti_materi(kon, database.muat_bukti_siklus(kon, siswa))
    assert tuple(kon.iterdump()) == sebelum


def test_loader_menolak_outcome_beda_konteks(db):
    kon, siswa = db
    sesi = _sesi(db)
    _konfirmasi(kon, sesi)
    kon.execute('DROP TRIGGER snapshot_outcome_tolak_update')
    kon.execute("UPDATE snapshot_outcome SET level_efektif='P5'")
    sebelum = tuple(kon.iterdump())
    with pytest.raises(ValueError, match='konteks outcome'):
        database.muat_bukti_siklus(kon, siswa)
    assert tuple(kon.iterdump()) == sebelum


def test_fokus_dibekukan_pada_event_dan_arsip(db):
    from learning_cycle import RencanaBelajar
    kon, siswa = db
    fokus = ('keliling_luas_datar', 'K', 'sintetis')
    putaran = database.buat_putaran_fokus(kon, siswa, 'P4')
    rencana = RencanaBelajar('evaluasi', 'Uji sintetis', kandidat=(fokus,), jumlah_probe_minimum=4)
    sesi = database.buat_sesi_dari_rencana(kon, siswa, rencana, putaran_id=putaran, seed=74)
    event = json.loads(kon.execute("SELECT data FROM kejadian_belajar WHERE jenis='sesi_dibuat'").fetchone()[0])
    assert sum(b['target_fokus'] == list(fokus) for b in event['konteks_latihan']['butir']) == 4
    kh = _konfirmasi(kon, sesi)
    arsip = json.loads(kon.execute('SELECT snapshot_json FROM konteks_konfirmasi WHERE konfirmasi_id=?', (kh,)).fetchone()[0])
    assert arsip == event['konteks_latihan']


def test_konteks_fokus_asing_ditolak_tanpa_konfirmasi(db):
    kon, siswa = db
    sesi = _sesi(db)
    kon.execute("INSERT INTO kejadian_belajar(siswa_id,sesi_id,jenis,data) VALUES(?,?,'sesi_dibuat',?)",
                (siswa, sesi, json.dumps({'target_per_nomor': {'1': ['asing', 'K', None]}})))
    with pytest.raises(ValueError, match='konteks fokus'):
        _konfirmasi(kon, sesi)
    assert kon.execute('SELECT count(*) FROM konfirmasi_hasil').fetchone()[0] == 0


def test_sesi_warisan_tetap_format_lama_tanpa_backfill(db, monkeypatch):
    import context_store
    kon, _ = db
    monkeypatch.setattr(context_store, 'simpan_butir', lambda *a: None)
    sesi = _sesi(db)
    kh = _konfirmasi(kon, sesi)
    assert kon.execute('SELECT count(*) FROM konteks_sesi').fetchone()[0] == 0
    assert kon.execute('SELECT count(*) FROM konteks_konfirmasi').fetchone()[0] == 0
    sebelum = tuple(kon.execute('SELECT * FROM konfirmasi_hasil').fetchone())
    assert _konfirmasi(kon, sesi) == kh
    assert tuple(kon.execute('SELECT * FROM konfirmasi_hasil').fetchone()) == sebelum


def test_arsip_dan_fingerprint_historis_tetap_setelah_koreksi(db):
    import hashlib
    kon, _ = db
    sesi = _sesi(db)
    kh = _konfirmasi(kon, sesi)
    arsip = kon.execute('SELECT snapshot_json FROM konteks_konfirmasi').fetchone()[0]
    outcome = kon.execute('SELECT * FROM snapshot_outcome ORDER BY nomor').fetchall()
    kolom = ('nomor', 'template_id', 'jawaban', 'benar', 'kode_final', 'malrule_id',
             'dilewati', 'level_efektif', 'cek_pemahaman', 'target_template_id',
             'target_kode_intervensi', 'target_malrule_id')
    kanonis = [{k: b[k] for k in kolom} for b in outcome]
    sidik_lama = hashlib.sha256(json.dumps(kanonis, ensure_ascii=False, sort_keys=True,
                                          separators=(',', ':')).encode()).hexdigest()
    assert kon.execute('SELECT fingerprint FROM konfirmasi_hasil').fetchone()[0] == sidik_lama
    butir = database.isi_sesi(kon, sesi)[0]
    database.simpan_jawaban(kon, butir['sesi_soal_id'], '0', 'Cara sintetis')
    assert kon.execute('SELECT snapshot_json FROM konteks_konfirmasi WHERE konfirmasi_id=?', (kh,)).fetchone()[0] == arsip


def test_migrasi_konteks_aditif_idempoten(tmp_path):
    path = tmp_path / 'migrasi.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 75)
        kh = _konfirmasi(kon, sesi)
        sebelum = tuple(kon.iterdump())
    database.siapkan(path)
    database.siapkan(path)
    with database.buka(path) as kon:
        assert tuple(kon.iterdump()) == sebelum
        assert _konfirmasi(kon, sesi) == kh
        assert kon.execute('PRAGMA foreign_key_check').fetchall() == []
        assert kon.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_upgrade_historis_tidak_menulis_konteks_atau_snapshot(tmp_path, monkeypatch):
    import context_store
    import context_schema
    path = tmp_path / 'warisan.db'
    with monkeypatch.context() as m:
        m.setattr(database, 'SKEMA', database.SKEMA.replace(context_schema.SKEMA_KONTEKS, ''))
        database.siapkan(path)
        m.setattr(context_store, 'simpan_butir', lambda *a: None)
        m.setattr(context_store, 'proyeksi', lambda *a: None)
        with database.buka(path) as kon:
            siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
            sesi = database.buat_sesi(kon, siswa, 76)
            _konfirmasi(kon, sesi)
            snapshot = tuple(tuple(b) for b in kon.execute('SELECT * FROM snapshot_outcome'))
            fingerprint = kon.execute('SELECT fingerprint_konfirmasi FROM sesi').fetchone()[0]
    database.siapkan(path)
    database.siapkan(path)
    with database.buka(path) as kon:
        assert tuple(tuple(b) for b in kon.execute('SELECT * FROM snapshot_outcome')) == snapshot
        assert kon.execute('SELECT fingerprint_konfirmasi FROM sesi').fetchone()[0] == fingerprint
        assert kon.execute('SELECT count(*) FROM konteks_butir').fetchone()[0] == 0
        assert kon.execute('SELECT count(*) FROM konteks_sesi').fetchone()[0] == 0
        assert kon.execute('PRAGMA foreign_key_check').fetchall() == []
        _konfirmasi(kon, sesi)
        assert kon.execute('SELECT count(*) FROM konfirmasi_hasil').fetchone()[0] == 1


def test_migrasi_konteks_gagal_tidak_meninggalkan_tabel_parsial(tmp_path, monkeypatch):
    import context_schema
    path = tmp_path / 'gagal.db'
    with monkeypatch.context() as m:
        m.setattr(database, 'SKEMA', database.SKEMA.replace(context_schema.SKEMA_KONTEKS, ''))
        database.siapkan(path)
    with database.buka(path) as kon:
        sebelum = tuple(kon.iterdump())
    with monkeypatch.context() as m:
        m.setattr(database, 'SKEMA', database.SKEMA + '\nCREATE TABLE gagal(;\n')
        with pytest.raises(sqlite3.OperationalError):
            database.siapkan(path)
    with database.buka(path) as kon:
        assert tuple(kon.iterdump()) == sebelum
    database.siapkan(path)
    with database.buka(path) as kon:
        assert kon.execute('PRAGMA foreign_key_check').fetchall() == []


def test_metadata_butir_hilang_ditolak_bukan_dianggap_warisan(db):
    kon, _ = db
    sesi = _sesi(db)
    kon.execute('DROP TRIGGER konteks_butir_immutable_delete')
    kon.execute('DELETE FROM konteks_butir WHERE sesi_soal_id=(SELECT min(sesi_soal_id) FROM konteks_butir)')
    with pytest.raises(ValueError, match='konteks'):
        _konfirmasi(kon, sesi)
    assert kon.execute('SELECT count(*) FROM konfirmasi_hasil').fetchone()[0] == 0


def test_di_luar_inventaris_tidak_menjadi_konteks_kemampuan(db):
    kon, siswa = db
    sesi = database.buat_sesi_dari_urutan(kon, siswa, 77, ('persen_diskon',),
                                        topik='aritmatika-lanjut', level='P6')
    baris = kon.execute('SELECT * FROM konteks_butir').fetchone()
    assert baris['profil_parameter'] == 'P6' and baris['konteks_id'] is None
    _konfirmasi(kon, sesi)

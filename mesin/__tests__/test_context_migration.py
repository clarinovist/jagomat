"""Rebuild CHECK sintetis: histori identik, fail-closed, dan rollback nyata."""

from contextlib import closing
import hashlib
import importlib.util
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

import pytest

import context_migration as migrasi
import database
from context_schema import SKEMA_KONTEKS
from schema import SKEMA
from templates import LEVEL


_CHECK_BARU = "CHECK(profil_parameter IN ('P1','P2','P3','P4','P5','P6'))"
_CHECK_LAMA = "CHECK(profil_parameter IN ('P3','P4','P5','P6'))"
_KOLOM = "sesi_soal_id, template_id, profil_parameter, konteks_id"
_TRIGGER = {
    "konteks_butir_validasi_insert", "konteks_butir_immutable_update",
    "konteks_butir_immutable_replace", "konteks_butir_immutable_delete",
}


def _ddl(kon):
    return kon.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='konteks_butir'"
    ).fetchone()[0]


def _baris(kon):
    return tuple(kon.execute(f"SELECT {_KOLOM} FROM konteks_butir ORDER BY sesi_soal_id"))


def _trigger(kon):
    return {b[0] for b in kon.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='konteks_butir'"
    )}


def _sidik_uji(baris):
    # Oracle independen dari helper produksi; juga bandingkan tuple utuh.
    return len(baris), hashlib.sha256(repr(baris).encode("utf-8")).hexdigest()


def _snapshot(path):
    with closing(sqlite3.connect(path)) as kon:
        return tuple(kon.iterdump())


def _baris_tabel_lain(kon):
    return {
        nama: tuple(kon.execute('SELECT * FROM "' + nama + '" ORDER BY rowid'))
        for (nama,) in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if nama != 'konteks_butir'
    }


def _induk(kon, profil, nomor):
    """Parent minimum sah, tanpa generator/konten P1/P2 yang belum tersedia."""
    siswa = kon.execute(
        "INSERT INTO siswa(nama,pemilik) VALUES (?, 'guru-sintetis')",
        (f"Sintetis {nomor}",),
    ).lastrowid
    sesi = kon.execute(
        "INSERT INTO sesi(siswa_id,seed,level) VALUES (?, ?, ?)",
        (siswa, nomor, profil),
    ).lastrowid
    template = "template-sintetis-α\n" + str(nomor)
    soal = kon.execute(
        "INSERT INTO soal(tanda_tangan,template_id,parameter,kunci,level) "
        "VALUES (?, ?, '{}', '1', ?)", (f"sintetis-{nomor}", template, profil),
    ).lastrowid
    # ID tidak berurutan mengikuti urutan INSERT; pemindahan harus ORDER BY ID.
    butir = 100 - nomor
    kon.execute(
        "INSERT INTO sesi_soal(id,sesi_id,soal_id,nomor) VALUES (?, ?, ?, 1)",
        (butir, sesi, soal),
    )
    kon.execute("INSERT INTO konteks_sesi(sesi_id,versi) VALUES (?, 1)", (sesi,))
    return butir, template, sesi


def _buat_lama(path, check=_CHECK_LAMA):
    assert SKEMA.count(_CHECK_BARU) == 1
    skema = SKEMA.replace(_CHECK_BARU, check)
    with closing(sqlite3.connect(path)) as kon:
        kon.execute("PRAGMA foreign_keys=ON")
        kon.executescript(skema)
        for nomor, profil in enumerate(("P3", "P4", "P5", "P6"), 1):
            butir, template, sesi = _induk(kon, profil, nomor)
            konteks = None if nomor % 2 else f"warisan-v1:{template}:{profil}"
            # Semua trigger aktif saat INSERT; histori baru dikunci sesudahnya.
            kon.execute(
                f"INSERT INTO konteks_butir ({_KOLOM}) VALUES (?, ?, ?, ?)",
                (butir, template, profil, konteks),
            )
            kon.execute(
                "UPDATE sesi SET mulai='2026-01-01', selesai='2026-01-01' WHERE id=?",
                (sesi,),
            )
        kon.commit()
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.fixture
def lama(tmp_path):
    path = tmp_path / "latihan.db"
    _buat_lama(path)
    return path


def test_siapkan_migrasi_check_dan_histori_identik(lama):
    with closing(sqlite3.connect(lama)) as kon:
        sebelum = _baris(kon)
        tabel_lain = _baris_tabel_lain(kon)
        # Verifikasi ulang asumsi objek skema pada DB lama sintetis.
        objek = {(b[0], b[1]) for b in kon.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL"
        ) if 'konteks_butir' in b[2]}
        assert objek == {('table', 'konteks_butir')} | {('trigger', t) for t in _TRIGGER}
    database.siapkan(lama)
    with closing(sqlite3.connect(lama)) as kon:
        assert migrasi._profil_dari_ddl(_ddl(kon)) == set(LEVEL)
        # Oracle sederhana terpisah mengunci isi CHECK kanonis hasil rebuild.
        daftar = re.search(r"CHECK\(profil_parameter IN \(([^)]+)\)\)", _ddl(kon))[1]
        assert {p.strip().strip("'") for p in daftar.split(',')} == set(LEVEL)
        assert _baris(kon) == sebelum
        assert _sidik_uji(_baris(kon)) == _sidik_uji(sebelum)
        assert _baris_tabel_lain(kon) == tabel_lain
        assert _trigger(kon) == _TRIGGER
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
        assert kon.execute("SELECT name FROM sqlite_master WHERE name='konteks_butir_baru'").fetchall() == []


@pytest.mark.parametrize('aksi', [
    "UPDATE konteks_butir SET konteks_id=NULL WHERE sesi_soal_id=99",
    "DELETE FROM konteks_butir WHERE sesi_soal_id=99",
    "INSERT OR REPLACE INTO konteks_butir SELECT * FROM konteks_butir WHERE sesi_soal_id=99",
])
def test_immutable_histori_tetap_aktif(lama, aksi):
    database.siapkan(lama)
    sebelum = _snapshot(lama)
    with closing(sqlite3.connect(lama)) as kon:
        with pytest.raises(sqlite3.IntegrityError, match="metadata konteks immutable"):
            kon.execute(aksi)
        kon.rollback()
    assert _snapshot(lama) == sebelum


@pytest.mark.parametrize('profil', ['P1', 'P2', 'P9'])
def test_check_baru_menerima_profil_dasar_menolak_asing(lama, profil):
    database.siapkan(lama)
    with closing(sqlite3.connect(lama)) as kon:
        kon.execute('PRAGMA foreign_keys=ON')
        butir, template, _ = _induk(kon, profil, 10)
        perintah = f"INSERT INTO konteks_butir ({_KOLOM}) VALUES (?, ?, ?, NULL)"
        if profil == 'P9':
            # Parent/marker valid; penolakan harus CHECK, bukan trigger validasi.
            with pytest.raises(sqlite3.IntegrityError, match='CHECK constraint failed'):
                kon.execute(perintah, (butir, template, profil))
        else:
            kon.execute(perintah, (butir, template, profil))
            assert kon.execute('SELECT profil_parameter FROM konteks_butir WHERE sesi_soal_id=?',
                               (butir,)).fetchone() == (profil,)
        assert _trigger(kon) == _TRIGGER
        assert kon.execute('PRAGMA foreign_key_check').fetchall() == []
        kon.commit()


def test_validasi_insert_histori_masih_menolak(lama):
    database.siapkan(lama)
    with closing(sqlite3.connect(lama)) as kon:
        butir, template, sesi = _induk(kon, 'P1', 10)
        kon.execute("UPDATE sesi SET mulai='2026-01-01' WHERE id=?", (sesi,))
        with pytest.raises(sqlite3.IntegrityError, match='konteks butir tidak cocok sumber'):
            kon.execute(f"INSERT INTO konteks_butir ({_KOLOM}) VALUES (?, ?, 'P1', NULL)",
                        (butir, template))
        kon.rollback()


def test_siapkan_kedua_tidak_rebuild(lama, monkeypatch):
    asli = database.rebuild_konteks_butir
    hasil = []

    def catat(kon):
        nilai = asli(kon)
        hasil.append(nilai)
        return nilai

    monkeypatch.setattr(database, 'rebuild_konteks_butir', catat)
    database.siapkan(lama)
    sebelum = _snapshot(lama)
    with closing(sqlite3.connect(lama)) as kon:
        sidik = migrasi._sidik_baris(kon, 'konteks_butir')
    database.siapkan(lama)
    assert hasil == [True, False]
    assert _snapshot(lama) == sebelum
    with closing(sqlite3.connect(lama)) as kon:
        assert migrasi.rebuild_konteks_butir(kon) is False
        assert not kon.in_transaction
        assert migrasi._sidik_baris(kon, 'konteks_butir') == sidik


def test_db_baru_tanpa_rebuild(tmp_path, monkeypatch):
    hasil = []
    asli = database.rebuild_konteks_butir

    def catat(kon):
        nilai = asli(kon)
        hasil.append(nilai)
        return nilai

    monkeypatch.setattr(database, 'rebuild_konteks_butir', catat)
    path = tmp_path / 'baru.db'
    database.siapkan(path)
    assert hasil == [False]
    with closing(sqlite3.connect(path)) as kon:
        assert migrasi._profil_dari_ddl(_ddl(kon)) == set(LEVEL)
        assert _baris(kon) == ()
        assert _trigger(kon) == _TRIGGER


@pytest.mark.parametrize('rusak', ['hilang_baris', 'ubah_isi'])
def test_salinan_rusak_rollback_utuh(lama, monkeypatch, rusak):
    sebelum = _snapshot(lama)
    sidik_file = hashlib.sha256(lama.read_bytes()).hexdigest()
    asli = migrasi._sidik_baris
    diperiksa = []

    def sabotase(kon, tabel):
        if tabel == 'konteks_butir_baru':
            if rusak == 'hilang_baris':
                kon.execute('DELETE FROM konteks_butir_baru WHERE sesi_soal_id=99')
            else:
                kon.execute("UPDATE konteks_butir_baru SET template_id='berubah' WHERE sesi_soal_id=99")
            diperiksa.append(tabel)
        return asli(kon, tabel)

    monkeypatch.setattr(migrasi, '_sidik_baris', sabotase)
    with pytest.raises(sqlite3.IntegrityError, match='sidik baris'):
        database.siapkan(lama)
    assert diperiksa == ['konteks_butir_baru']
    assert _snapshot(lama) == sebelum
    assert hashlib.sha256(lama.read_bytes()).hexdigest() == sidik_file


def test_gagal_setelah_drop_rename_memulihkan_trigger_lama(lama, monkeypatch):
    sebelum = _snapshot(lama)
    monkeypatch.setattr(database, 'SKEMA', SKEMA + '\nSQL_SENGAJA_RUSAK;')
    with pytest.raises(sqlite3.OperationalError):
        database.siapkan(lama)
    assert _snapshot(lama) == sebelum


@pytest.mark.parametrize('check', [
    "CHECK(profil_parameter != '')",
    "CHECK(profil_parameter IN ('P3','P4','P5','P6','P9'))",
    "CHECK(profil_parameter IN ('P3','P4','P5','P6') OR 1)",
    "CHECK(profil_parameter IN ('P3','P4','P5','P6')) CHECK(profil_parameter != '')",
    "DEFAULT 'CHECK(profil_parameter IN (''P1'',''P2'',''P3'',''P4'',''P5'',''P6''))'",
    "/* CHECK(profil_parameter IN ('P1','P2','P3','P4','P5','P6')) */",
])
def test_ddl_tak_dikenal_atau_asing_ditolak_tanpa_perubahan(tmp_path, check):
    path = tmp_path / 'tak-dikenal.db'
    _buat_lama(path, check)
    sebelum = _snapshot(path)
    with pytest.raises(ValueError, match='CHECK'):
        database.siapkan(path)
    assert _snapshot(path) == sebelum
    with closing(sqlite3.connect(path)) as kon:
        with pytest.raises(ValueError, match='CHECK'):
            migrasi.rebuild_konteks_butir(kon)
        assert not kon.in_transaction
    assert _snapshot(path) == sebelum


@pytest.mark.parametrize('nama', ['profil_parameter', '"profil_parameter"', '`profil_parameter`', '[profil_parameter]'])
def test_parser_check_bukan_substring(nama):
    ddl = ("CREATE TABLE konteks_butir (profil_parameter TEXT, "
           "catatan TEXT DEFAULT 'CHECK(profil_parameter IN (''P9''))', "
           "/* CHECK(profil_parameter IN ('P9')) */ "
           f"cHeCk ( {nama} /* sah */ In ( 'P6',\n'P3','P4','P5', 'P3' ) ));")
    assert migrasi._profil_dari_ddl(ddl) == {'P3', 'P4', 'P5', 'P6'}


@pytest.mark.parametrize('ekspresi', [
    'profil_parameter IN (P3, P4)', "profil_parameter IN ('P3',)",
    "profil_parameter IN (upper('P3'))", "profil_parameter IN (SELECT 'P3')",
    "profil_parameter IN ('P3', 'P4') AND 1", "profil_parameter NOT IN ('P9')",
    "profil_parameter IN ('P3' 'P4')",
])
def test_parser_menolak_ekspresi_bukan_daftar_literal(ekspresi):
    with pytest.raises(ValueError, match='CHECK'):
        migrasi._profil_dari_ddl(f'CREATE TABLE konteks_butir(profil_parameter TEXT CHECK({ekspresi}))')


@pytest.mark.parametrize('profil', [[], ['P1'], ['P6', 'P1', 'P3']])
def test_subset_level_lain_juga_diperluas(tmp_path, profil):
    path = tmp_path / 'subset.db'
    daftar = ','.join(repr(p) for p in profil)
    with closing(sqlite3.connect(path)) as kon:
        kon.executescript(SKEMA.replace(_CHECK_BARU, f'CHECK(profil_parameter IN ({daftar}))'))
    database.siapkan(path)
    with closing(sqlite3.connect(path)) as kon:
        assert migrasi._profil_dari_ddl(_ddl(kon)) == set(LEVEL)


@pytest.mark.parametrize('fk', [0, 1])
def test_rebuild_mandiri_commit_dan_pulihkan_fk(lama, fk):
    with closing(sqlite3.connect(lama)) as kon:
        kon.execute(f'PRAGMA foreign_keys={fk}')
        sebelum = _baris(kon)
        assert migrasi.rebuild_konteks_butir(kon) is True
        assert not kon.in_transaction
        assert kon.execute('PRAGMA foreign_keys').fetchone()[0] == fk
        assert _baris(kon) == sebelum
        assert _trigger(kon) == set()  # Sengaja hanya siapkan/SKEMA memasang trigger.
        assert migrasi.rebuild_konteks_butir(kon) is False
        database._jalankan_skema(kon, SKEMA)
        assert _trigger(kon) == _TRIGGER
    with closing(sqlite3.connect(lama)) as kon:
        assert migrasi._profil_dari_ddl(_ddl(kon)) == set(LEVEL)


def test_transaksi_pemanggil_fk_aktif_ditolak(lama):
    sebelum = _snapshot(lama)
    with closing(sqlite3.connect(lama)) as kon:
        kon.execute('PRAGMA foreign_keys=ON')
        kon.execute('BEGIN IMMEDIATE')
        with pytest.raises(sqlite3.IntegrityError, match='FK nonaktif'):
            migrasi.rebuild_konteks_butir(kon)
        assert kon.in_transaction
        assert kon.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        kon.rollback()
    assert _snapshot(lama) == sebelum


def test_transaksi_pemanggil_tidak_dicommmit_helper(lama):
    sebelum = _snapshot(lama)
    with closing(sqlite3.connect(lama)) as kon:
        kon.execute('PRAGMA foreign_keys=OFF')
        kon.execute('BEGIN IMMEDIATE')
        assert migrasi.rebuild_konteks_butir(kon) is True
        assert kon.in_transaction
        kon.rollback()
    assert _snapshot(lama) == sebelum


def test_rebuild_mandiri_gagal_sidik_rollback_dan_fk(lama, monkeypatch):
    sebelum = _snapshot(lama)
    asli = migrasi._sidik_baris

    def salah(kon, tabel):
        jumlah, sidik = asli(kon, tabel)
        return jumlah, 'salah' if tabel == 'konteks_butir_baru' else sidik

    monkeypatch.setattr(migrasi, '_sidik_baris', salah)
    with closing(sqlite3.connect(lama)) as kon:
        kon.execute('PRAGMA foreign_keys=ON')
        with pytest.raises(sqlite3.IntegrityError, match='sidik baris'):
            migrasi.rebuild_konteks_butir(kon)
        assert not kon.in_transaction
        assert kon.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert _snapshot(lama) == sebelum


@pytest.mark.parametrize('mandiri', [False, True])
def test_fk_rusak_menggulung_rebuild(lama, mandiri):
    with closing(sqlite3.connect(lama)) as kon:
        kon.execute('INSERT INTO sesi(siswa_id,seed) VALUES (9999, 42)')
        kon.commit()
    sebelum = _snapshot(lama)
    with pytest.raises(sqlite3.IntegrityError, match='FK rusak'):
        if mandiri:
            with closing(sqlite3.connect(lama)) as kon:
                migrasi.rebuild_konteks_butir(kon)
        else:
            database.siapkan(lama)
    assert _snapshot(lama) == sebelum


def test_ddl_baru_identik_dengan_sumber_kanonis(tmp_path):
    with closing(sqlite3.connect(tmp_path / 'ddl.db')) as kon:
        # CREATE FK boleh dilakukan sebelum tabel induk tersedia; hanya DDL.
        kon.executescript(SKEMA_KONTEKS)
        kon.execute(migrasi._ddl_tabel_baru())
        baru = kon.execute("SELECT sql FROM sqlite_master WHERE name='konteks_butir_baru'").fetchone()[0]
        assert baru.replace('konteks_butir_baru', 'konteks_butir', 1) == _ddl(kon)
        assert list(kon.execute('PRAGMA table_info(konteks_butir_baru)')) == list(kon.execute('PRAGMA table_info(konteks_butir)'))
        assert list(kon.execute('PRAGMA foreign_key_list(konteks_butir_baru)')) == list(kon.execute('PRAGMA foreign_key_list(konteks_butir)'))


def test_probe_rilis_profil_skema_lulus_tanpa_menulis(lama, tmp_path):
    import admin_store
    import admin_students

    akar = Path(__file__).resolve().parents[2]
    spek = importlib.util.spec_from_file_location('deploy_uji_migrasi_konteks', akar / 'scripts' / 'deploy.py')
    deploy = importlib.util.module_from_spec(spek)
    spek.loader.exec_module(deploy)
    database.siapkan(lama)
    # Bootstrap receipt admin juga dilakukan oleh fixture probe rilis existing;
    # database.siapkan sendiri tidak memasang operasi_admin_profil.
    admin_students.siapkan(lama)
    admin = tmp_path / 'admin-control.db'
    admin_store.siapkan(admin, sekarang=1)
    sebelum = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (lama, admin)}
    skrip = 'import sqlite3\n' + deploy.PROBE_PROFIL_SKEMA.replace('/data/', str(tmp_path) + '/')
    # Sama dengan test_profile_release_probe: proses Python segar, -E -B,
    # source probe asli, koneksi mode=ro/query_only, bukan tiruan assertion.
    hasil = subprocess.run([sys.executable, '-E', '-B', '-'], input=skrip, cwd=tmp_path,
                           capture_output=True, text=True, timeout=45)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout == ''
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (lama, admin)} == sebelum

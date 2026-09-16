"""Fondasi snapshot PG diuji di DB sintetis; startup aplikasi belum diubah."""
from dataclasses import replace
import json
import sqlite3

import pytest

import database
from choice_contract import fingerprint, serialisasi
from choice_schema import SKEMA_PILIHAN
from choice_store import baca_pilihan, daftarkan_validasi, simpan_pilihan
from multiple_choice import buat_pilihan


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "sintetis.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        daftarkan_validasi(kon)
        kon.execute("BEGIN IMMEDIATE")
        database._jalankan_skema(kon, SKEMA_PILIHAN)
    with database.buka(path) as kon:
        daftarkan_validasi(kon)
        yield kon, path


@pytest.fixture
def db_terjaga(db):
    kon, path = db
    asli = kon.row_factory

    class BarisTerjaga:
        def __init__(self, cursor, data):
            self.baris = sqlite3.Row(cursor, data)

        def __getitem__(self, kolom):
            assert kolom not in {"kunci", "malrule_id", "kode_final", "kode_usulan", "alasan"}
            return self.baris[kolom]

    kon.row_factory = BarisTerjaga
    yield kon, path
    kon.row_factory = asli


def siapkan(kon, nama="Sintetis"):
    siswa = database.tambah_siswa(kon, nama, pemilik="guru")
    sesi = kon.execute("INSERT INTO sesi(siswa_id,seed,format_jawaban) VALUES (?,42,'pilihan_ganda')", (siswa,)).lastrowid
    from generator import buat_lembar
    for nomor, soal in enumerate(buat_lembar(42, jumlah_soal=2).soal, 1):
        database._simpan_butir_sesi(kon, sesi, nomor, soal)
    pilihan = tuple(buat_pilihan(
        sesi_soal_id=b["id"], fingerprint_pertanyaan=b["fingerprint_penyajian"],
        kebijakan="tiga-v1", jenis="angka", kunci="24", pengecoh=("12", "23"),
        seed=42, identitas=str(b["nomor"]),
    ) for b in kon.execute("SELECT id,nomor,fingerprint_penyajian FROM sesi_soal WHERE sesi_id=? ORDER BY nomor", (sesi,)))
    return siswa, sesi, pilihan


def jumlah(kon):
    return kon.execute("SELECT COUNT(*) FROM pilihan_butir").fetchone()[0]


def test_simpan_baca_replay_tanpa_kunci(db_terjaga):
    kon, _ = db_terjaga
    # Setup memakai writer guru, proyeksi baca tetap Row terjaga.
    siswa, sesi, pilihan = siapkan(kon)
    simpan_pilihan(kon, siswa, sesi, pilihan)
    for p in pilihan:
        assert baca_pilihan(kon, siswa, sesi, p.sesi_soal_id) == p
    assert jumlah(kon) == 2


def test_kepemilikan_identik_resource_tidak_ada_dan_tanpa_efek_samping(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    lain, sesi_lain, _ = siapkan(kon, "Lain")
    simpan_pilihan(kon, siswa, sesi, pilihan)
    awal = list(kon.execute("SELECT * FROM pilihan_butir"))
    assert baca_pilihan(kon, lain, sesi, pilihan[0].sesi_soal_id) is None
    assert baca_pilihan(kon, siswa, sesi_lain, pilihan[0].sesi_soal_id) is None
    assert baca_pilihan(kon, siswa, sesi, 99999) is None
    with pytest.raises(ValueError, match="milik siswa"):
        simpan_pilihan(kon, lain, sesi, pilihan)
    assert list(kon.execute("SELECT * FROM pilihan_butir")) == awal


def test_hilang_bukan_fallback_isian(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    with pytest.raises(ValueError, match="belum tersedia"):
        baca_pilihan(kon, siswa, sesi, pilihan[0].sesi_soal_id)


@pytest.mark.parametrize("jenis", ["parsial", "duplikat", "salah_sidik", "salah_butir"])
def test_batch_tidak_sah_tidak_menyisakan_baris(db, jenis):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    salah = {
        "parsial": pilihan[:1], "duplikat": (pilihan[0], pilihan[0]),
        "salah_sidik": (pilihan[0], replace(pilihan[1], fingerprint_pertanyaan="b" * 64)),
        "salah_butir": (pilihan[0], replace(pilihan[1], sesi_soal_id=9999)),
    }[jenis]
    with pytest.raises(ValueError):
        simpan_pilihan(kon, siswa, sesi, salah)
    assert jumlah(kon) == 0


@pytest.mark.parametrize("kolom,nilai", [
    ("mulai", "2026-09-16"), ("selesai", "2026-09-16"),
    ("penyajian_dibekukan", "2026-09-16"), ("dibatalkan", "2026-09-16"),
    ("dikonfirmasi_guru", "2026-09-16"), ("tujuan", "pemetaan"), ("jenis", "remedial"),
])
def test_lifecycle_terkunci_ditolak_di_trigger(db, kolom, nilai):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    if kolom in ('tujuan', 'jenis'):
        with pytest.raises(sqlite3.IntegrityError, match='manual'):
            kon.execute(f"UPDATE sesi SET {kolom}=? WHERE id=?", (nilai, sesi))
        kon.execute('DROP TRIGGER pilihan_sesi_manual_update')
    kon.execute(f"UPDATE sesi SET {kolom}=? WHERE id=?", (nilai, sesi))
    with pytest.raises(sqlite3.IntegrityError, match="terkunci"):
        simpan_pilihan(kon, siswa, sesi, pilihan)
    assert jumlah(kon) == 0


def test_kegagalan_butir_kedua_rollback_butir_pertama(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    kon.execute(f"""CREATE TRIGGER kegagalan_sintetis BEFORE INSERT ON pilihan_butir
        WHEN NEW.sesi_soal_id={pilihan[1].sesi_soal_id}
        BEGIN SELECT RAISE(ABORT, 'gagal butir kedua'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="gagal butir kedua"):
        simpan_pilihan(kon, siswa, sesi, pilihan)
    assert jumlah(kon) == 0
    kon.execute("DROP TRIGGER kegagalan_sintetis")
    simpan_pilihan(kon, siswa, sesi, pilihan)
    assert jumlah(kon) == 2


def test_pekerjaan_butir_lain_juga_mengunci_opsi(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    kon.execute('DROP TRIGGER pilihan_jawaban_insert')
    database.simpan_jawaban(kon, pilihan[1].sesi_soal_id, "17")
    p = pilihan[0]
    with pytest.raises(sqlite3.IntegrityError, match="terkunci"):
        kon.execute("INSERT INTO pilihan_butir VALUES (?,?,?)",
                    (p.sesi_soal_id, serialisasi(p), fingerprint(p)))
    assert jumlah(kon) == 0


def test_simpan_tidak_commit_transaksi_pemanggil(db):
    kon, path = db
    siswa, sesi, pilihan = siapkan(kon)
    kon.commit()
    simpan_pilihan(kon, siswa, sesi, pilihan)
    assert kon.in_transaction
    with database.buka(path) as pembaca:
        assert jumlah(pembaca) == 0
    kon.rollback()
    assert jumlah(kon) == 0


@pytest.mark.parametrize("operasi", ["update", "replace", "delete", "pertanyaan", "hapus_butir", "bagian"])
def test_immutable_termasuk_ikatan_pertanyaan(db, operasi):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    simpan_pilihan(kon, siswa, sesi, pilihan)
    p = pilihan[0]
    with pytest.raises(sqlite3.IntegrityError):
        if operasi == "update":
            kon.execute("UPDATE pilihan_butir SET snapshot_json='{}' WHERE sesi_soal_id=?", (p.sesi_soal_id,))
        elif operasi == "replace":
            kon.execute("INSERT OR REPLACE INTO pilihan_butir VALUES (?,?,?)", (p.sesi_soal_id, serialisasi(p), fingerprint(p)))
        elif operasi == "delete":
            kon.execute("DELETE FROM pilihan_butir WHERE sesi_soal_id=?", (p.sesi_soal_id,))
        elif operasi == "hapus_butir":
            kon.execute("DELETE FROM sesi_soal WHERE id=?", (p.sesi_soal_id,))
        elif operasi == "bagian":
            kon.execute("UPDATE sesi_soal SET bagian_soal='X' WHERE id=?", (p.sesi_soal_id,))
        else:
            kon.execute("UPDATE sesi_soal SET nomor=99 WHERE id=?", (p.sesi_soal_id,))
    assert baca_pilihan(kon, siswa, sesi, p.sesi_soal_id) == p
    assert jumlah(kon) == 2


def test_penghapusan_sesi_tanpa_bukti_masih_sah(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    simpan_pilihan(kon, siswa, sesi, pilihan)
    assert database.hapus_sesi(kon, sesi)
    assert jumlah(kon) == 0
    assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


def test_ddl_idempoten_dan_data_utuh(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    simpan_pilihan(kon, siswa, sesi, pilihan)
    database._jalankan_skema(kon, SKEMA_PILIHAN)
    database._jalankan_skema(kon, SKEMA_PILIHAN)
    assert baca_pilihan(kon, siswa, sesi, pilihan[0].sesi_soal_id) == pilihan[0]
    assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


def test_trigger_menolak_snapshot_rahasia_meski_sidik_dihitung_ulang(db):
    import hashlib
    kon, _ = db
    _, _, pilihan = siapkan(kon)
    p = pilihan[0]
    data = json.loads(serialisasi(p))
    data["kunci"] = "24"
    teks = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO pilihan_butir VALUES (?,?,?)", (p.sesi_soal_id, teks, hashlib.sha256(teks.encode()).hexdigest()))
    assert jumlah(kon) == 0


def test_koneksi_tanpa_validator_tidak_bisa_menulis(db):
    kon, path = db
    _, _, pilihan = siapkan(kon)
    kon.commit()
    p = pilihan[0]
    with database.buka(path) as asing:
        asing.create_function('pilihan_snapshot_sah', 4, None)
        with pytest.raises(sqlite3.OperationalError):
            asing.execute("INSERT INTO pilihan_butir VALUES (?,?,?)", (p.sesi_soal_id, serialisasi(p), fingerprint(p)))
        assert jumlah(asing) == 0


def test_reader_tolak_data_rusak_meski_trigger_telah_dinonaktifkan(db):
    kon, _ = db
    siswa, sesi, pilihan = siapkan(kon)
    simpan_pilihan(kon, siswa, sesi, pilihan)
    kon.execute("DROP TRIGGER pilihan_butir_tolak_update")
    kon.execute("UPDATE pilihan_butir SET snapshot_json='{}'")
    with pytest.raises(ValueError):
        baca_pilihan(kon, siswa, sesi, pilihan[0].sesi_soal_id)


def test_startup_memasang_tabel_tanpa_mengubah_default_isian(tmp_path):
    path = tmp_path / "tanpa-pg.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        assert kon.execute("SELECT 1 FROM sqlite_master WHERE name='pilihan_butir'").fetchone() is not None
        assert "format_jawaban" in {b['name'] for b in kon.execute('PRAGMA table_info(sesi)')}
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 1)
        assert kon.execute('SELECT format_jawaban FROM sesi WHERE id=?', (sesi,)).fetchone()[0] == 'isian'

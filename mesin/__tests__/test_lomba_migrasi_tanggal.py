"""Migrasi tanggal + nama lomba per anak (23 Nov 2026): baris lama mempertahankan 12 Des, anak baru tidak mewarisinya.

DB lama dibuat dari DDL beku (lomba_penugasan sebelum kolom tanggal/nama), bukan impor modul, supaya tes tetap
menggambarkan DB produksi lama walau skema kode berubah lagi. Data sintetis di tmp_path.
"""
import datetime
import sqlite3

import pytest

import contest_assignment_store as AS
import database

DDL_PENUGASAN_LAMA = """
DROP TABLE lomba_penugasan;
CREATE TABLE lomba_penugasan (
    siswa_id             INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    paket_id             TEXT    NOT NULL CHECK (length(paket_id) BETWEEN 1 AND 64),
    aktif                INTEGER NOT NULL CHECK (aktif IN (0, 1)),
    target_harian        INTEGER CHECK (target_harian IS NULL OR target_harian BETWEEN 0 AND 5),
    tampil_hitung_mundur INTEGER CHECK (tampil_hitung_mundur IS NULL OR tampil_hitung_mundur IN (0, 1)),
    diubah_epoch         INTEGER NOT NULL,
    diubah_oleh          TEXT    NOT NULL DEFAULT '' CHECK (length(diubah_oleh) <= 64),
    durasi_latihan_detik  INTEGER CHECK (durasi_latihan_detik IS NULL OR durasi_latihan_detik BETWEEN 300 AND 10800),
    durasi_simulasi_detik INTEGER CHECK (durasi_simulasi_detik IS NULL OR durasi_simulasi_detik BETWEEN 300 AND 10800)
);
"""
SEKARANG = 1_800_000_000
KOLOM_BARU = ("tanggal_lomba", "nama_lomba")


def _buat_db_lama(path):
    """DB versi sekarang, lalu lomba_penugasan diganti bentuk lama berisi satu baris untuk anak A."""
    database.siapkan(path)
    kon = sqlite3.connect(str(path))
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys = OFF")
    kon.executescript(DDL_PENUGASAN_LAMA)
    kon.execute("PRAGMA foreign_keys = ON")
    kon.execute("INSERT INTO siswa(nama, pemilik) VALUES ('Anak A', 'guru')")
    a = kon.execute("SELECT id FROM siswa WHERE nama = 'Anak A'").fetchone()[0]
    kon.execute("INSERT INTO lomba_penugasan(siswa_id, paket_id, aktif, target_harian, tampil_hitung_mundur, "
                "diubah_epoch, diubah_oleh, durasi_latihan_detik) VALUES (?, 'corexis_l1_matematika', 1, 3, 0, 1000, 'guru', 1200)",
                (a,))
    kon.commit()
    kon.close()
    return a


def _kolom(kon):
    return {r["name"] for r in kon.execute("PRAGMA table_info(lomba_penugasan)")}


def test_db_lama_tanpa_kolom_mendapat_dua_kolom_dan_baris_lama_berdefault_dua_belas_desember(tmp_path):
    path = tmp_path / "lama.db"
    a = _buat_db_lama(path)
    with database.buka(path) as kon:
        assert not set(KOLOM_BARU) & _kolom(kon)

    database.siapkan(path)

    with database.buka(path) as kon:
        assert set(KOLOM_BARU) <= _kolom(kon)
        lama = AS.ambil(kon, a)
        assert lama.tanggal_lomba == datetime.date(2026, 12, 12) and lama.nama_lomba == "Grand Final Corexis"
        assert (lama.target_harian, lama.tampil_hitung_mundur, lama.durasi_latihan_detik) == (3, False, 1200)


def test_migrasi_idempoten_dan_tidak_menimpa_nilai_yang_sudah_diubah_guru(tmp_path):
    path = tmp_path / "lama.db"
    a = _buat_db_lama(path)
    database.siapkan(path)
    with database.buka(path) as kon:
        lama = AS.ambil(kon, a)
        AS.atur(kon, a, aktif=lama.aktif, target_harian=lama.target_harian, tampil_hitung_mundur=lama.tampil_hitung_mundur,
                durasi_latihan_detik=lama.durasi_latihan_detik, durasi_simulasi_detik=None,
                tanggal_lomba=datetime.date(2027, 2, 1), nama_lomba=None, sekarang=SEKARANG, oleh="guru")

    database.siapkan(path)

    with database.buka(path) as kon:
        akhir = AS.ambil(kon, a)
        assert (akhir.tanggal_lomba, akhir.nama_lomba) == (datetime.date(2027, 2, 1), None)
        assert database.migrasi(kon) == [] and kon.execute("PRAGMA foreign_key_check").fetchall() == []


def test_anak_baru_pada_db_hasil_migrasi_tidak_mewarisi_default_dua_belas_desember(tmp_path):
    path = tmp_path / "lama.db"
    _buat_db_lama(path)
    database.siapkan(path)

    with database.buka(path) as kon:
        baru = database.tambah_siswa(kon, "Anak Baru Sintetis", pemilik="guru")
        hasil = AS.atur(kon, baru, aktif=True, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None,
                        durasi_simulasi_detik=None, tanggal_lomba=None, nama_lomba=None, sekarang=SEKARANG, oleh="guru")
        assert (hasil.tanggal_lomba, hasil.nama_lomba) == (None, None)
        assert tuple(kon.execute("SELECT tanggal_lomba, nama_lomba FROM lomba_penugasan WHERE siswa_id = ?",
                                 (baru,)).fetchone()) == (None, None)


def test_db_baru_punya_kedua_kolom_dan_tanggal_none_tersimpan_null(tmp_path):
    path = tmp_path / "baru.db"
    database.siapkan(path)

    with database.buka(path) as kon:
        assert set(KOLOM_BARU) <= _kolom(kon)
        anak = database.tambah_siswa(kon, "Anak Sintetis", pemilik="guru")
        hasil = AS.atur(kon, anak, aktif=True, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None,
                        durasi_simulasi_detik=None, tanggal_lomba=None, nama_lomba=None, sekarang=SEKARANG, oleh="guru")
        assert (hasil.tanggal_lomba, hasil.nama_lomba) == (None, None)


def test_check_migrasi_menolak_tanggal_dan_nama_liar_pada_db_hasil_migrasi(tmp_path):
    path = tmp_path / "lama.db"
    a = _buat_db_lama(path)
    database.siapkan(path)

    with database.buka(path) as kon:
        for kolom, nilai in (("tanggal_lomba", "2026-13-45"), ("tanggal_lomba", "besok"), ("nama_lomba", "x" * 61)):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(f"UPDATE lomba_penugasan SET {kolom} = ? WHERE siswa_id = ?", (nilai, a))

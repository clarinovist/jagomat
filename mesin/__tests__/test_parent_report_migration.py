"""Migrasi aditif tabel laporan orang tua + pembersihan saat data anak hilang.

Basis data "lama" di sini adalah skema pra-siklus dari
``test_legacy_migration`` (tanpa tabel laporan). Yang dibuktikan: tabel baru
lahir lewat ``database.siapkan`` tanpa mengubah baris lama, idempoten, bersih
menurut ``integrity_check``/``foreign_key_check``, dan tidak meninggalkan sisa
saat anak/keluarga dihapus.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import family_deletion  # noqa: E402
import parent_report_store  # noqa: E402
from test_legacy_migration import TABEL_HISTORI, _buat_database_pra_siklus  # noqa: E402


def _tabel(kon):
    return {
        baris[0] for baris in kon.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _jumlah(kon, nama):
    return kon.execute(f'SELECT COUNT(*) FROM "{nama}"').fetchone()[0]


def _bersih(kon):
    assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


def _laporan(kon, siswa_id, *, periode=("2026-11-01", "2026-11-30"),
             isi='{"topik":[],"tahap":null,"langkah":"","versi":1}'):
    return parent_report_store.buat_draf(
        kon, siswa_id, periode[0], periode[1], isi, catatan="Catatan", guru="guru",
    )


def test_db_pra_siklus_mendapat_tabel_baru_tanpa_mengubah_histori(tmp_path):
    path = tmp_path / "pra-siklus.db"
    _buat_database_pra_siklus(path)
    with database.buka(path) as kon:
        assert "laporan_ortu" not in _tabel(kon)
        jumlah_lama = {nama: _jumlah(kon, nama) for nama in TABEL_HISTORI}

    database.siapkan(path)
    with database.buka(path) as kon:
        tabel = _tabel(kon)
        assert {"laporan_ortu", "tautan_laporan"} <= tabel
        assert {nama: _jumlah(kon, nama) for nama in TABEL_HISTORI} == jumlah_lama
        _bersih(kon)
        dump_pertama = tuple(kon.iterdump())

    database.siapkan(path)
    with database.buka(path) as kon:
        assert tuple(kon.iterdump()) == dump_pertama
        _bersih(kon)


def test_siapkan_ulang_tidak_menghapus_laporan_anak(tmp_path):
    path = tmp_path / "data.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, "Bima", "P3", pemilik="guru")
        laporan = _laporan(kon, anak)
        token = parent_report_store.terbitkan(
            kon, laporan, anak, 0, "guru", sekarang=1_000,
        )
        sebelum = (dict(parent_report_store.ambil(kon, laporan)),
                   dict(kon.execute("SELECT * FROM tautan_laporan").fetchone()))
    database.siapkan(path)
    with database.buka(path) as kon:
        assert dict(parent_report_store.ambil(kon, laporan)) == sebelum[0]
        assert dict(kon.execute("SELECT * FROM tautan_laporan").fetchone()) == sebelum[1]
        assert parent_report_store.ambil_tautan(kon, token, sekarang=1_001)
        _bersih(kon)


def test_kendala_skema_menolak_nilai_tidak_sah(tmp_path):
    path = tmp_path / "kendala.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, "Bima", "P3", pemilik="guru")
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(
                """INSERT INTO laporan_ortu
                       (siswa_id, periode_mulai, periode_akhir, isi)
                   VALUES (?, '2026-11-30', '2026-11-01', '{"topik":[]}')""",
                (anak,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(
                """INSERT INTO laporan_ortu
                       (siswa_id, periode_mulai, periode_akhir, catatan, isi)
                   VALUES (?, '2026-11-01', '2026-11-30', ?, '{"topik":[]}')""",
                (anak, "x" * 2001),
            )
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(
                """INSERT INTO tautan_laporan
                       (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa)
                   VALUES (?, ?, 'pendek', 1, 2)""",
                (anak, _laporan(kon, anak)),
            )
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(
                """INSERT INTO laporan_ortu
                       (siswa_id, periode_mulai, periode_akhir, isi)
                   VALUES (?, '2026-11-01', '2026-11-30', '')""",
                (anak,),
            )


def test_hapus_anak_menghapus_laporan_dan_tautan_tanpa_sisa(tmp_path):
    path = tmp_path / "hapus.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, "Bima", "P3", pemilik="guru")
        lain = database.tambah_siswa(kon, "Rara", "P4", pemilik="guru")
        laporan = _laporan(kon, anak)
        parent_report_store.terbitkan(kon, laporan, anak, 0, "guru", sekarang=10)
        _laporan(kon, lain)
        kon.execute("DELETE FROM siswa WHERE id = ?", (anak,))
        assert _jumlah(kon, "laporan_ortu") == 1
        assert _jumlah(kon, "tautan_laporan") == 0
        assert kon.execute(
            "SELECT siswa_id FROM laporan_ortu").fetchone()[0] == lain
        _bersih(kon)
        kon.execute("DELETE FROM siswa WHERE id = ?", (lain,))
        assert _jumlah(kon, "laporan_ortu") == 0
        _bersih(kon)


def test_hapus_keluarga_membuang_laporan_dan_tautan(tmp_path):
    path = tmp_path / "keluarga.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        anak = database.tambah_siswa(kon, "Bima", "P3", pemilik="keluarga-target")
        lain = database.tambah_siswa(kon, "Rara", "P4", pemilik="keluarga-lain")
        laporan = _laporan(kon, anak)
        parent_report_store.terbitkan(kon, laporan, anak, 0, "guru", sekarang=10)
        laporan_lain = _laporan(kon, lain)
        parent_report_store.terbitkan(kon, laporan_lain, lain, 0, "guru", sekarang=10)

    family_deletion._ubah_belajar(
        path, "keluarga-target", "akun_" + "b" * 32, "keluarga_dihapus_uji",
    )
    with database.buka(path) as kon:
        assert _jumlah(kon, "laporan_ortu") == 1
        assert _jumlah(kon, "tautan_laporan") == 1
        assert kon.execute(
            "SELECT siswa_id FROM laporan_ortu").fetchone()[0] == lain
        # Nama anak target tetap dipseudonimkan seperti janji retensi.
        nama = kon.execute(
            "SELECT nama, pemilik FROM siswa WHERE id = ?", (anak,)
        ).fetchone()
        assert nama["pemilik"] == "keluarga_dihapus_uji"
        assert nama["nama"].startswith("Dihapus-")
        _bersih(kon)

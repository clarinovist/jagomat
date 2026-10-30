"""Kolom sesi.level harus mencatat level yang BENAR-BENAR dipakai (fase 5).

`buat_sesi` menyimpan level MENTAH yang diminta, sementara generator
menormalkan level tak dikenal ke level paket lewat `_level_efektif`. Anak
bertingkat 'kelas 4' mendapat sesi bertuliskan level 'kelas 4' padahal
soalnya P3 — dan kolom itulah yang ditampilkan ke anak di halaman murid
("level kelas 4") serta dipakai laporan guru.

Bug ini lebih tua dan lebih luas dari perbaikan remedial: ia menyentuh
jalur pembuatan sesi yang paling umum. Data produksi saat ini bersih
(semua level P3/P4/P6), jadi ini laten — diperbaiki sebelum ada yang
mengetik tingkat berformat bebas, bukan sesudah.

Kontrak: apa pun jalurnya, `sesi.level` == level soal-soalnya.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import teacher_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _level(kon, sesi_id):
    tersimpan = kon.execute(
        "SELECT level FROM sesi WHERE id = ?", (sesi_id,)
    ).fetchone()["level"]
    soal = {b["level"] for b in database.isi_sesi(kon, sesi_id)}
    return tersimpan, soal


def test_buat_sesi_menyimpan_level_efektif(db):
    """Jalur pembuatan sesi paling umum — inilah bug fase 5."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(
            kon, "AnakTeksBebas", pemilik="guru", tingkat="P3"
        )
        # Simulasikan data historis; writer baru menolak tingkat teks bebas.
        kon.execute("UPDATE siswa SET tingkat='kelas 4' WHERE id=?", (sid,))
        sesi_id = database.buat_sesi(
            kon, sid, seed=1, level="kelas 4", jumlah_soal=3
        )
        tersimpan, soal = _level(kon, sesi_id)
    assert tersimpan != "kelas 4", (
        "sesi menyimpan level mentah; anak melihat 'level kelas 4' "
        "padahal soalnya bukan level itu"
    )
    assert {tersimpan} == soal, f"sesi {tersimpan!r} vs soal {soal}"


def test_buat_sesi_seed_baru_menyimpan_level_efektif(db):
    """Jalur tombol 'Buat sesi baru' membaca tingkat anak apa adanya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(
            kon, "AnakTombol", pemilik="guru", tingkat="P3"
        )
        # Simulasikan data historis; writer baru menolak tingkat teks bebas.
        kon.execute("UPDATE siswa SET tingkat='kelas 4' WHERE id=?", (sid,))
        sesi_id = teacher_pages.buat_sesi_seed_baru(kon, sid, jumlah_soal=3)
        tersimpan, soal = _level(kon, sesi_id)
    assert tersimpan != "kelas 4"
    assert {tersimpan} == soal


def test_level_resmi_tidak_diubah(db):
    """Level yang sah harus tersimpan APA ADANYA.

    Penting: perbaikan ini tidak boleh diam-diam memindahkan level anak
    yang tingkatnya memang benar. Kalau P5 berubah jadi P3, seluruh
    riwayat dan laporan ikut salah.
    """
    for level in ("P3", "P4", "P5", "P6"):
        with database.buka(db) as kon:
            sid = database.tambah_siswa(
                kon, f"Anak{level}", pemilik="guru", tingkat=level
            )
            sesi_id = database.buat_sesi(
                kon, sid, seed=7, level=level, jumlah_soal=3
            )
            tersimpan, soal = _level(kon, sesi_id)
        assert tersimpan == level, f"level sah {level} diubah jadi {tersimpan}"
        assert {tersimpan} == soal


def test_semua_jalur_pembuatan_sesi_konsisten(db):
    """Sapu SEMUA jalur: tak satu pun boleh menyimpan level yang berbeda
    dari soalnya. Ditulis menyapu, bukan per-fungsi, supaya jalur baru
    yang lupa menormalkan langsung ketahuan."""
    hasil = {}
    with database.buka(db) as kon:
        sid = database.tambah_siswa(
            kon, "AnakSapu", pemilik="guru", tingkat="P3"
        )
        # Simulasikan data historis; writer baru menolak tingkat teks bebas.
        kon.execute("UPDATE siswa SET tingkat='kelas 4' WHERE id=?", (sid,))
        hasil["buat_sesi"] = database.buat_sesi(
            kon, sid, seed=11, level="kelas 4", jumlah_soal=3
        )
        hasil["seed_baru"] = teacher_pages.buat_sesi_seed_baru(
            kon, sid, jumlah_soal=3
        )
        hasil["dari_urutan"] = database.buat_sesi_dari_urutan(
            kon, sid, seed=12,
            urutan=("deret_aritmetika",) * 3, level="kelas 4",
        )
        hasil["gabungan"] = database.buat_sesi_gabungan(
            kon, sid, seed=13,
            topik_ids=["logika", "statistika"],
            level="kelas 4", jumlah_soal=3,
        )
        salah = {}
        for nama, sesi_id in hasil.items():
            tersimpan, soal = _level(kon, sesi_id)
            if {tersimpan} != soal:
                salah[nama] = (tersimpan, soal)
    assert not salah, f"jalur menyimpan level tidak konsisten: {salah}"

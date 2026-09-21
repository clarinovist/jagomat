"""Level anak vs level yang didukung paket — jalur POST tidak boleh dipercaya.

`siswa.tingkat` adalah kolom teks bebas, dan tidak semua topik punya semua
level (logika melompati P4, kombinatorik mulai P5). Form guru memang
memfilter pilihan per level, tapi POST bisa dikirim dengan kombinasi apa
pun — dan tingkat anak bisa diubah SESUDAH form dirender.

Sebelum perbaikan: anak P4 + dua topik yang sama-sama tanpa P4 membuat
generator melempar ValueError, handler mati, dan pengguna melihat 502.
Kontraknya di sini: jalur yang levelnya BUKAN pilihan pengguna
(tingkat anak) menormalkan diri; yang memang pilihan pengguna tetap
ditolak dengan jelas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def test_gabungan_level_anak_tidak_didukung_dua_topik(db):
    """Anak P4 + logika & kombinatorik (keduanya tanpa P4) harus tetap jadi.

    Level di sini BUKAN pilihan pengguna — ia dibaca dari tingkat anak.
    Menolaknya berarti mematikan fitur untuk anak yang tingkatnya kebetulan
    tidak dimiliki topik pilihannya.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakP4", pemilik="guru", tingkat="P4")
        sesi_id = database.buat_sesi_gabungan(
            kon, sid, seed=1,
            topik_ids=["logika", "kombinatorik"],
            level="P4", jumlah_soal=5,
        )
        isi = database.isi_sesi(kon, sesi_id)
    assert sesi_id is not None
    assert len(isi) == 5


def test_gabungan_level_tersimpan_adalah_level_efektif(db):
    """Yang tercatat di sesi harus level yang BENAR-BENAR dipakai.

    Kalau kolom level menyimpan 'P4' padahal soalnya P5, laporan dan
    perbandingan antar-sesi jadi berbohong. Diuji lewat level teks bebas
    ('kelas 4'), bukan 'P4': dengan normalisasi aktif, level P4 sudah
    disamakan sebelum insert sehingga menyimpan `level` atau
    `lembar.level` menghasilkan nilai identik — mutation test membuktikan
    versi itu LOLOS. Teks bebas tidak pernah sama dengan level efektif,
    jadi ia benar-benar membedakan keduanya.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(
            kon, "AnakP4b", pemilik="guru", tingkat="kelas 4"
        )
        sesi_id = database.buat_sesi_gabungan(
            kon, sid, seed=2,
            topik_ids=["logika", "kombinatorik"],
            level="kelas 4", jumlah_soal=4,
        )
        tersimpan = kon.execute(
            "SELECT level FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["level"]
        soal_level = {b["level"] for b in database.isi_sesi(kon, sesi_id)}
    assert tersimpan != "kelas 4", (
        "sesi menyimpan level mentah yang diminta, bukan level yang dipakai"
    )
    assert tersimpan in soal_level, (
        f"sesi tercatat level {tersimpan!r} tapi soalnya {soal_level}"
    )


def test_sesi_dari_urutan_menyimpan_level_efektif(db):
    """Kolom level harus mencatat level yang BENAR-BENAR dipakai.

    Diuji lewat `buat_sesi_dari_urutan` (jalur remedial) dengan tingkat
    teks bebas: di `buat_sesi_gabungan` normalisasi sudah menyamakan
    `level` dan `lembar.level` sebelum insert, jadi mutasi "simpan level
    yang diminta" tidak bisa dibedakan di sana — mutation test
    membuktikannya LOLOS. Di sini keduanya berbeda, jadi benar-benar
    menggigit.
    """
    with database.buka(db) as kon:
        sid = database.tambah_siswa(
            kon, "AnakUrutan", pemilik="guru", tingkat="kelas 4"
        )
        sesi_id = database.buat_sesi_dari_urutan(
            kon, sid, seed=4,
            urutan=("deret_aritmetika",) * 3,
            level="kelas 4",
        )
        tersimpan = kon.execute(
            "SELECT level FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()["level"]
        soal_level = {b["level"] for b in database.isi_sesi(kon, sesi_id)}
    assert tersimpan != "kelas 4", (
        "sesi menyimpan level mentah yang diminta, bukan level yang dipakai"
    )
    assert tersimpan in soal_level


def test_level_terdekat_bukan_level_pertama():
    """Level pengganti dipilih yang TERDEKAT, bukan yang paling awal.

    Anak P6 yang topiknya hanya punya P3 dan P5 harus dapat P5 — memberi
    P3 berarti menurunkan anak tiga tingkat diam-diam. Diuji langsung
    karena data nyata (P4 -> P3) kebetulan membuat "terdekat" dan
    "pertama" menghasilkan jawaban yang sama; mutation test membuktikan
    mutasi `urut[0]` LOLOS tanpa test ini.
    """
    assert database._level_terdekat("P6", ("P3", "P5")) == "P5"
    assert database._level_terdekat("P5", ("P3", "P6")) == "P6"  # 2 vs 1
    assert database._level_terdekat("P4", ("P3", "P5")) == "P3"  # seri -> bawah
    assert database._level_terdekat("P3", ("P5", "P6")) == "P5"
    assert database._level_terdekat("kelas 4", ("P5", "P6")) == "P5"


def test_gabungan_level_teks_bebas_tidak_meledak(db):
    """Tingkat lama berformat bebas ('kelas 4') sudah ada di data produksi."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(
            kon, "AnakLama", pemilik="guru", tingkat="kelas 4"
        )
        sesi_id = database.buat_sesi_gabungan(
            kon, sid, seed=3,
            topik_ids=["logika", "statistika"],
            level="kelas 4", jumlah_soal=4,
        )
    assert sesi_id is not None


def test_http_gabungan_level_tak_didukung_tidak_500(server):
    """POST tidak boleh dipercaya: kombinasi ini bisa dikirim langsung."""
    with server.buka() as kon:
        sid = database.tambah_siswa(
            kon, "AnakHttpP4", pemilik="guru", tingkat="P4"
        )
    kode, isi, _ = server.minta(
        f"/sesi-gabungan/{sid}", auth=("guru", SANDI_GURU),
        data=[("topik", "logika"), ("topik", "kombinatorik"),
              ("jumlah_soal", "10"), ("profil_parameter", "P4")],
    )
    assert kode == 400, f"kombinasi tidak tersedia harus ditolak (kode {kode})"
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert n == 0, "kombinasi tidak tersedia tidak boleh fallback diam-diam"

"""Poin 4 tahap 2 — sesi CUSTOM lintas beberapa topik pilihan guru.

Sudah ada "campuran" (semua topik sekaligus) dan topik tunggal. Yang
belum: guru memilih SEBAGIAN topik, misalnya "geometri datar + pengukuran
saja" untuk anak yang lemah di dua itu.

Kontrak yang dikunci:
  1. `topics.gabungan([...])` membuat paket sintetis di memori — TIDAK
     mendaftarkan apa pun ke registri global (paket ad-hoc per permintaan,
     bukan state yang bocor antar-request).
  2. Komposisinya interleave antar-topik terpilih, seperti campuran.
  3. Satu topik saja -> sama dengan topik itu sendiri (tidak bikin paket).
  4. Topik tak dikenal -> ditolak, bukan diam-diam dilewati.
  5. Sesi tersimpan membawa daftar topiknya sehingga bisa direplay.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import topics  # noqa: E402
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


# ── 1. topics.gabungan ────────────────────────────────────────────────


def test_gabungan_dua_topik_isinya_dari_keduanya():
    paket = topics.gabungan(["geometri-datar", "pengukuran"])
    a = set(topics.ambil("geometri-datar").templates)
    b = set(topics.ambil("pengukuran").templates)
    assert set(paket.templates) == a | b
    komp = set(paket.komposisi_untuk("P5"))
    assert komp & a, "template geometri tidak ikut"
    assert komp & b, "template pengukuran tidak ikut"


def test_gabungan_tidak_mengotori_registri_global():
    """Paket ad-hoc tidak boleh jadi state global.

    Kalau ia terdaftar, dropdown topik akan penuh paket sekali-pakai dan
    dua permintaan berbeda bisa saling menimpa.
    """
    sebelum = set(topics.daftar_topik())
    topics.gabungan(["logika", "teori-bilangan"])
    assert set(topics.daftar_topik()) == sebelum


def test_gabungan_satu_topik_sama_dengan_topik_itu():
    paket = topics.gabungan(["logika"])
    assert paket.id == "logika"


def test_gabungan_topik_asing_ditolak():
    with pytest.raises(KeyError):
        topics.gabungan(["geometri-datar", "topik-hantu"])


def test_gabungan_kosong_ditolak():
    with pytest.raises(ValueError):
        topics.gabungan([])


def test_gabungan_buang_duplikat():
    paket = topics.gabungan(["logika", "logika"])
    assert paket.id == "logika"


def test_gabungan_bisa_membangkitkan_lembar():
    """Bukti paket sintetis benar-benar hidup, bukan cuma struktur."""
    import generator

    lembar = generator.buat_lembar(
        seed=11, level="P5", topik=topics.gabungan(["geometri-datar", "logika"]),
        jumlah_soal=8,
    )
    assert len(lembar.soal) == 8
    assert all(s.pembahasan for s in lembar.soal)


# ── 2. Sesi gabungan di DB ────────────────────────────────────────────


def test_buat_sesi_gabungan_menyimpan_id_topik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakGab", pemilik="guru")
        ses = database.buat_sesi_gabungan(
            kon, sid, seed=31, topik_ids=["geometri-datar", "logika"],
            level="P5", jumlah_soal=8,
        )
        baris = kon.execute("SELECT topik FROM sesi WHERE id = ?", (ses,)).fetchone()
        isi = database.isi_sesi(kon, ses)
    assert baris["topik"] == "gabungan:geometri-datar,logika"
    assert len(isi) == 8


def test_sesi_gabungan_soalnya_dari_kedua_topik(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakGab2", pemilik="guru")
        ses = database.buat_sesi_gabungan(
            kon, sid, seed=77, topik_ids=["geometri-datar", "logika"],
            level="P5", jumlah_soal=12,
        )
        dipakai = {b["template_id"] for b in database.isi_sesi(kon, ses)}
    a = set(topics.ambil("geometri-datar").templates)
    b = set(topics.ambil("logika").templates)
    assert dipakai & a, "tidak ada soal geometri"
    assert dipakai & b, "tidak ada soal logika"


def test_sesi_gabungan_bisa_dibaca_ulang_dari_kolom_topik(db):
    """Replay: sesi lama harus tetap tahu paket gabungannya."""
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "AnakGab3", pemilik="guru")
        ses = database.buat_sesi_gabungan(
            kon, sid, seed=5, topik_ids=["logika", "pengukuran"],
            level="P5", jumlah_soal=6,
        )
        nilai = kon.execute(
            "SELECT topik FROM sesi WHERE id = ?", (ses,)
        ).fetchone()["topik"]
    paket = topics.dari_sesi(nilai)
    assert paket.id == "gabungan:logika,pengukuran"


def test_dari_sesi_gabungan_rusak_jatuh_ke_bawaan():
    """Topik hilang tidak boleh membuat halaman sesi lama gagal."""
    paket = topics.dari_sesi("gabungan:logika,topik-yang-sudah-dihapus")
    assert paket.id == topics.TOPIK_BAWAAN


# ── 3. UI + rute HTTP ─────────────────────────────────────────────────


def test_form_gabungan_muncul_di_halaman_anak(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakForm", pemilik="guru")
    kode, isi, _ = server.minta(f"/anak/{sid}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert f'action="/sesi-gabungan/{sid}"' in isi
    assert 'type="checkbox" name="topik"' in isi
    assert "Buat latihan gabungan" in isi


def test_http_buat_sesi_gabungan(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakHttpGab", pemilik="guru")
    kode, isi, _ = server.minta(
        f"/sesi-gabungan/{sid}",
        auth=("guru", SANDI_GURU),
        data=[("topik", "geometri-datar"), ("topik", "logika"),
              ("jumlah_soal", "10"), ("profil_parameter", "P3")],
    )
    assert kode == 200
    assert "Latihan gabungan untuk" in isi
    with server.buka() as kon:
        ses = kon.execute(
            "SELECT id, topik FROM sesi WHERE siswa_id = ? ORDER BY id DESC",
            (sid,),
        ).fetchone()
        isi_sesi = database.isi_sesi(kon, int(ses["id"]))
    assert ses["topik"] == "gabungan:geometri-datar,logika"
    assert len(isi_sesi) == 10


def test_http_gabungan_satu_topik_ditolak_dengan_pesan(server):
    """Satu topik bukan gabungan — arahkan ke form biasa, jangan bikin sesi."""
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakSatuTopik", pemilik="guru")
    kode, isi, _ = server.minta(
        f"/sesi-gabungan/{sid}",
        auth=("guru", SANDI_GURU),
        data=[("topik", "logika")],
    )
    assert kode == 200
    assert "minimal DUA topik" in isi
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert n == 0


def test_http_gabungan_topik_asing_400(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakAsing", pemilik="guru")
    kode, _, _ = server.minta(
        f"/sesi-gabungan/{sid}",
        auth=("guru", SANDI_GURU),
        data=[("topik", "logika"), ("topik", "topik-hantu")],
    )
    assert kode == 400
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert n == 0


def test_http_gabungan_anak_keluarga_lain_404(server):
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakLainGab", pemilik="guru2")
        sebelum = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    kode, _, _ = server.minta(
        f"/sesi-gabungan/{sid}",
        auth=("guru", SANDI_GURU),
        data=[("topik", "logika"), ("topik", "pengukuran")],
    )
    assert kode == 404
    with server.buka() as kon:
        sesudah = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (sid,)
        ).fetchone()["n"]
    assert sesudah == sebelum, "sesi terbuat padahal bukan anak keluarganya"

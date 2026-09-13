"""Isolasi antar keluarga: guru hanya melihat anak miliknya.

Skenario nyata: aplikasi dipakai BANYAK keluarga di satu deployment. Guru
keluarga A tidak boleh membuka — bahkan mengetahui keberadaan — data keluarga
B: sesi, laporan, lembar (berisi kunci), lampiran, hapus, dan membuat sesi
untuk anak orang lain. Tolakannya 404, bukan 403: keberadaan id orang lain
bukan informasi yang boleh bocor. Admin melihat semuanya.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import auth  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

SANDI_A = "sandi-ortu-a-1234567"
SANDI_B = "sandi-ortu-b-1234567"
SANDI_ADMIN = "sandi-pengelola-9999"


@pytest.fixture()
def dua_keluarga(tmp_path, monkeypatch):
    """Dua keluarga (ortu-a, ortu-b) + admin, masing-masing dengan anak & sesi.

    Akun murid "feby" (bawaan ServerUji) menjadi anak keluarga ortu-a lewat
    siswa bernama sama, supaya kasus lintas-keluarga di sisi murid bisa diuji.
    """
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        a = database.tambah_siswa(kon, "BimaA", "P3", pemilik="ortu-a")
        b = database.tambah_siswa(kon, "RaraB", "P4", pemilik="ortu-b")
        feby = database.tambah_siswa(kon, "feby", "P3", pemilik="ortu-a")
        sesi_a = database.buat_sesi(kon, a, seed=11)
        sesi_b = database.buat_sesi(kon, b, seed=22)
        sesi_feby = database.buat_sesi(kon, feby, seed=33)
        lamp_b = database.simpan_lampiran(kon, sesi_b, "foto-b.jpg")
    auth.tambah_akun("ortu-a", SANDI_A, "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("ortu-b", SANDI_B, "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("pengelola", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI)
    yield s, {
        "a": a,
        "b": b,
        "feby": feby,
        "sesi_a": sesi_a,
        "sesi_b": sesi_b,
        "sesi_feby": sesi_feby,
        "lamp_b": lamp_b,
    }
    s.berhenti()


def test_guru_lain_404_di_rute_sesi_dan_lembar(dua_keluarga):
    s, ids = dua_keluarga
    for jalur in (
        f"/sesi/{ids['sesi_b']}",
        f"/lembar/{ids['sesi_b']}",
        f"/lembar/{ids['sesi_b']}/penilaian",
        f"/lampiran/{ids['lamp_b']}",
        f"/lampiran/berkas/{ids['lamp_b']}",
    ):
        kode, _, _ = s.minta(jalur, auth=("ortu-a", SANDI_A))
        assert kode == 404, f"{jalur} terbaca keluarga lain"


def test_guru_lain_404_di_laporan_anak_orang(dua_keluarga):
    s, ids = dua_keluarga
    kode, _, _ = s.minta(f"/laporan/{ids['b']}", auth=("ortu-a", SANDI_A))
    assert kode == 404


def test_guru_lain_404_di_halaman_anak_orang(dua_keluarga):
    """Rute /anak/<id> (feedback no. 6) wajib pakai palang yang sama dengan
    /laporan/<id> — guru keluarga lain tidak boleh membaca history anak."""
    s, ids = dua_keluarga
    kode, _, _ = s.minta(f"/anak/{ids['b']}", auth=("ortu-a", SANDI_A))
    assert kode == 404


def test_guru_lain_tidak_bisa_hapus_sesi_orang(dua_keluarga):
    s, ids = dua_keluarga
    kode, _, _ = s.minta(
        f"/sesi/{ids['sesi_b']}/hapus", auth=("ortu-a", SANDI_A)
    )
    assert kode == 404
    kode, _, _ = s.minta(
        f"/sesi/{ids['sesi_b']}/hapus",
        auth=("ortu-a", SANDI_A),
        data={"konfirmasi": "1"},
    )
    assert kode == 404
    with s.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE id = ?", (ids["sesi_b"],)
        ).fetchone()["n"]
    assert n == 1, "sesi keluarga B ternyata terhapus"


def test_guru_lain_tidak_bisa_simpan_jawaban_sesi_orang(dua_keluarga):
    s, ids = dua_keluarga

    def jumlah_jawaban():
        with s.buka() as kon:
            return kon.execute(
                """SELECT COUNT(*) AS n FROM jawaban j
                   JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
                   WHERE ss.sesi_id = ?""",
                (ids["sesi_b"],),
            ).fetchone()["n"]

    sebelum = jumlah_jawaban()
    kode, _, _ = s.minta(
        f"/sesi/{ids['sesi_b']}",
        auth=("ortu-a", SANDI_A),
        data={"jawaban_1": "diusap orang lain"},
    )
    assert kode == 404
    assert jumlah_jawaban() == sebelum, "jawaban keluarga B ternyata tersentuh"


def test_guru_lain_tidak_bisa_buat_sesi_untuk_anak_orang(dua_keluarga):
    s, ids = dua_keluarga
    kode, _, _ = s.minta(
        f"/sesi-baru/{ids['b']}",
        auth=("ortu-a", SANDI_A),
        data={"topik": "pola-bilangan", "mode": "diagnostik"},
    )
    assert kode == 404
    with s.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) AS n FROM sesi WHERE siswa_id = ?", (ids["b"],)
        ).fetchone()["n"]
    assert n == 1


def test_guru_lain_tidak_bisa_upload_dan_terapkan_lampiran_orang(dua_keluarga):
    s, ids = dua_keluarga
    kode, _, _ = s.minta(
        f"/lampiran/{ids['sesi_b']}", auth=("ortu-a", SANDI_A), data={"x": "1"}
    )
    assert kode == 404
    kode, _, _ = s.minta(
        f"/lampiran/{ids['lamp_b']}/terapkan", auth=("ortu-a", SANDI_A), data={}
    )
    assert kode == 404


def test_guru_lain_tidak_bisa_variasi_cerita_sesi_orang(dua_keluarga):
    s, ids = dua_keluarga
    kode, _, _ = s.minta(
        f"/cerita/{ids['sesi_b']}", auth=("ortu-a", SANDI_A), data={}
    )
    assert kode == 404


def test_guru_tetap_bisa_akses_keluarganya_sendiri(dua_keluarga):
    s, ids = dua_keluarga
    for jalur in (
        f"/sesi/{ids['sesi_a']}",
        f"/lembar/{ids['sesi_a']}",
        f"/laporan/{ids['a']}",
    ):
        kode, _, _ = s.minta(jalur, auth=("ortu-a", SANDI_A))
        assert kode == 200, f"{jalur} jadi tertutup untuk pemiliknya"


def test_admin_melihat_semua_keluarga(dua_keluarga):
    s, ids = dua_keluarga
    for jalur in (
        f"/sesi/{ids['sesi_b']}",
        f"/laporan/{ids['b']}",
        f"/lembar/{ids['sesi_b']}",
        f"/lampiran/{ids['lamp_b']}",
    ):
        kode, _, _ = s.minta(jalur, auth=("pengelola", SANDI_ADMIN))
        assert kode == 200, f"{jalur} tertutup untuk admin"


def test_dashboard_guru_hanya_anaknya(dua_keluarga):
    s, ids = dua_keluarga
    kode, isi, _ = s.minta("/", auth=("ortu-a", SANDI_A))
    assert kode == 200
    assert "BimaA" in isi
    assert "RaraB" not in isi


def test_dashboard_guru_menampilkan_badge_orang_tua(dua_keluarga):
    s, ids = dua_keluarga
    _, isi, _ = s.minta("/", auth=("ortu-a", SANDI_A))
    assert "Orang Tua" in isi


def test_admin_diarahkan_ke_panel_semua_keluarga(dua_keluarga):
    # Admin full-write (4 Sep 2026): GET / tetap dialihkan ke /admin —
    # daftar semua keluarga tampil di sana, dan admin menulis lewat
    # rute guru yang sama (bukan lewat dashboard terpisah).
    s, ids = dua_keluarga
    kode, isi, _ = s.minta("/", auth=("pengelola", SANDI_ADMIN))
    assert kode == 200
    assert "BimaA" in isi
    assert "RaraB" in isi
    assert "Pengelola" in isi
    assert "Buat sesi baru" not in isi
    kode_siswa, daftar_siswa, _ = s.minta(
        "/admin?section=siswa", auth=("pengelola", SANDI_ADMIN)
    )
    assert kode_siswa == 200
    assert f'href="/admin?section=siswa&amp;id={ids["b"]}"' in daftar_siswa, "anak harus jadi tautan detail admin"


def test_murid_keluarga_a_tak_bisa_menjangkau_sesi_keluarga_b(dua_keluarga):
    s, ids = dua_keluarga
    kode, _, _ = s.minta(
        f"/murid/kerjakan/{ids['sesi_b']}", auth=("feby", SANDI_MURID)
    )
    assert kode == 404
    kode, _, _ = s.minta(
        f"/murid/kerjakan/{ids['sesi_b']}",
        auth=("feby", SANDI_MURID),
        data={},
    )
    assert kode == 404


def test_murid_keluarga_a_daftar_sesinya_sendiri(dua_keluarga):
    s, ids = dua_keluarga
    kode, isi, _ = s.minta("/murid", auth=("feby", SANDI_MURID))
    assert kode == 200
    assert f"/murid/kerjakan/{ids['sesi_feby']}" in isi
    assert f"/murid/kerjakan/{ids['sesi_b']}" not in isi

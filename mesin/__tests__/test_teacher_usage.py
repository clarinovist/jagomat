"""Pemakaian guru: perhitungan murni dan halaman admin `/admin/pemakaian`.

Semua data sintetis. Waktu di DB adalah WIB naif (`datetime('now', '+7 hours')`),
jadi batas minggu mengikuti jam dinding WIB.
"""
from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import teacher_usage as P  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _login, _minta, server,  # noqa: F401
)
from http_test_kit import SANDI_MURID  # noqa: E402

NAMA_ANAK = "Zorblat Sintetis"
SEKARANG = datetime(2026, 11, 6, 12, 0, 0)  # Jumat, minggu ISO 45


def _sesi(kon, siswa_id, dibuat, *, mulai=None, selesai=None, direview=None,
          konfirmasi=None, dibatalkan=None, sumber=None):
    kur = kon.execute(
        "INSERT INTO sesi (siswa_id, seed, dibuat, mulai, selesai, direview,"
        " dikonfirmasi_guru, dibatalkan) VALUES (?,?,?,?,?,?,?,?)",
        (siswa_id, 1, dibuat, mulai, selesai, direview, konfirmasi, dibatalkan),
    )
    if sumber:
        kon.execute(
            "INSERT INTO pengiriman_sesi (sesi_id, sumber) VALUES (?, ?)",
            (kur.lastrowid, sumber),
        )
    return kur.lastrowid


@pytest.fixture()
def data(server):
    auth.tambah_akun("Guru-B", SANDI_ORANG_TUA + "b", "guru")
    with server.buka() as kon:
        a = database.tambah_siswa(kon, NAMA_ANAK, "P3", pemilik="Ortu-C")
        b = database.tambah_siswa(kon, "Anak Lain B", "P3", pemilik="Guru-B")
        # minggu 45, lengkap; dikirim lewat tautan HP anak
        _sesi(kon, a, "2026-11-02 08:00:00", mulai="2026-11-02 08:05:00",
              selesai="2026-11-02 08:25:00", direview="2026-11-02 09:00:00",
              konfirmasi="2026-11-02 09:10:00", sumber="tautan")
        # Minggu 44: Minggu malam 23:30 WIB harus tetap minggu 44.
        _sesi(kon, a, "2026-11-01 23:30:00", mulai="2026-11-01 23:35:00",
              selesai="2026-11-01 23:55:00")
        # Dibatalkan: tidak dihitung, minggu 42 tidak aktif karena ini.
        _sesi(kon, a, "2026-10-14 08:00:00", dibatalkan="2026-10-14 08:30:00")
        # Waktu negatif: tetap dihitung sebagai sesi, durasinya diabaikan.
        _sesi(kon, a, "2026-10-15 08:00:00", mulai="2026-10-15 10:00:00",
              selesai="2026-10-15 09:00:00")
        # Absurd: kerja 26 jam dan tinjau > 24 jam diabaikan; jeda tetap masuk.
        _sesi(kon, a, "2026-10-20 08:00:00", mulai="2026-10-20 08:00:00",
              selesai="2026-10-21 10:00:00", direview="2026-10-20 08:00:00",
              konfirmasi="2026-10-22 08:00:00", sumber="foto")
        # Guru B: satu sesi minggu ini, satu di luar jendela 8 minggu.
        _sesi(kon, b, "2026-11-03 10:00:00", mulai="2026-11-03 10:00:00",
              selesai="2026-11-03 10:30:00", sumber="foto")
        _sesi(kon, b, "2026-08-01 10:00:00", mulai="2026-08-01 10:00:00",
              selesai="2026-08-01 10:30:00")
        kon.execute(
            "INSERT INTO laporan_ortu (siswa_id, periode_mulai, periode_akhir,"
            " isi, guru, diterbitkan) VALUES (?,?,?,?,?,?)",
            (a, "2026-10-01", "2026-10-31", "{}", "Ortu-C", "2026-11-03 09:00:00"),
        )
        kon.execute(
            "INSERT INTO laporan_ortu (siswa_id, periode_mulai, periode_akhir,"
            " isi, guru) VALUES (?,?,?,?,?)",
            (a, "2026-09-01", "2026-09-30", "{}", "Ortu-C"),
        )
    return server


def _hitung(server):
    with server.buka() as kon:
        return {g.pengguna: g for g in P.ambil_pemakaian(kon, sekarang=SEKARANG)}


def test_hitungan_sesi_minggu_aktif_dan_median(data):
    hasil = _hitung(data)
    a = hasil["Ortu-C"]
    assert (a.sesi_dibuat, a.sesi_selesai, a.sesi_dikonfirmasi) == (4, 4, 2)
    assert a.minggu_aktif == 4
    assert a.median_kerja_menit == 20
    assert a.median_jeda_konfirmasi_menit == 682.5
    assert a.median_tinjau_menit == 10
    assert a.laporan_terbit == 1
    assert dict(a.sumber) == {"tautan": 1, "foto": 1, "akun": 0, "tanpa": 2}


def test_batas_minggu_jakarta_minggu_malam_masuk_minggu_lama(data):
    a = _hitung(data)["Ortu-C"]
    per_minggu = {m.senin.isoformat(): m.sesi_dibuat for m in a.minggu}
    assert per_minggu["2026-10-26"] == 1  # Minggu 1 Nov 23:30 -> minggu 44
    assert per_minggu["2026-11-02"] == 1
    assert per_minggu["2026-10-12"] == 1  # yang dibatalkan tidak dihitung
    assert len(a.minggu) == 8
    assert a.minggu[-1].senin.isoformat() == "2026-11-02"


def test_zona_aware_utc_dikonversi_ke_wib():
    assert P.minggu_senin("2026-11-01T16:30:00+00:00").isoformat() == "2026-10-26"  # 23:30 WIB
    assert P.minggu_senin("2026-11-01 23:30:00").isoformat() == "2026-10-26"
    assert P.minggu_senin("2026-11-01T23:30:00Z").isoformat() == "2026-11-02"


@pytest.mark.parametrize("nilai", [None, "", "bukan tanggal", "2026-13-45 00:00:00"])
def test_waktu_rusak_diabaikan(nilai):
    assert P.minggu_senin(nilai) is None


def test_guru_lain_dan_jendela_delapan_minggu(data):
    b = _hitung(data)["Guru-B"]
    assert (b.sesi_dibuat, b.minggu_aktif, b.median_kerja_menit) == (1, 1, 30)
    assert b.median_tinjau_menit is None and b.laporan_terbit == 0
    assert dict(b.sumber)["foto"] == 1


def test_halaman_admin_menampilkan_guru_tanpa_nama_anak(data):
    token = _login(data, "Admin-C", SANDI_ADMIN)
    kode, isi, header = _minta(data, "/admin/pemakaian", cookie=token)
    assert kode == 200
    assert "Ortu-C" in isi and "Guru-B" in isi
    assert NAMA_ANAK not in isi and "Anak Lain B" not in isi
    assert "Waktu persiapan belum bisa diukur." in isi
    assert "perkiraan" in isi and "<script" not in isi
    assert header["Cache-Control"] == "no-store"
    assert 'href="/admin/pemakaian"' in _minta(data, "/admin", cookie=token)[1]


def test_halaman_tertutup_untuk_selain_admin_sama_dengan_404_admin_lain(data):
    acuan = _minta(data, "/admin/tidak-ada")[:2]
    assert acuan[0] == 404
    anonim = _minta(data, "/admin/pemakaian")[:2]
    guru = _minta(data, "/admin/pemakaian", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    murid = _minta(data, "/admin/pemakaian", auth_basic=("feby", SANDI_MURID))[:2]
    assert anonim == guru == murid == acuan
    assert _minta(data, "/admin/pemakaian?x=1", cookie=_login(data, "Admin-C", SANDI_ADMIN))[0] == 404


def test_get_tanpa_efek_samping(data):
    token = _login(data, "Admin-C", SANDI_ADMIN)
    with data.buka() as kon:
        sebelum = tuple(kon.iterdump())
    sandi = auth.BERKAS_SANDI.read_bytes()
    assert _minta(data, "/admin/pemakaian", cookie=token)[0] == 200
    with data.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert auth.BERKAS_SANDI.read_bytes() == sandi


@pytest.mark.parametrize("nilai,teks", [
    (None, "—"), (7.5, "7,5 mnt"), (30.0, "30 mnt"), (60.0, "1 j"), (682.5, "11 j 22 mnt"),
])
def test_format_durasi_mudah_dibaca(nilai, teks):
    import admin_usage_pages
    assert admin_usage_pages.menit(nilai) == teks

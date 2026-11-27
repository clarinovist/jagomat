"""Kartu "Tugas dari Guru" di beranda anak: isi, batas, gerbang, palang murid, dan galat baca (data sintetis).

Tugas ditulis lewat `guru_tugas_dasar.catat` ke berkas sementara (env `GURU_TUGAS_DB`), sesi lewat DB belajar
sementara. Gerbang dinyalakan dengan monkeypatch `guru_tugas_aturan.GURU_TUGAS_AKTIF`. Tanpa data anak nyata.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

import pytest

import database
import domain_clock
import guru_tugas_aturan as aturan
import guru_tugas_baca as baca
import guru_tugas_dasar as dasar
import guru_tugas_kartu as kartu_guru
import guru_pertemuan_aturan as pertemuan
import cek_murid
import student_pages
import students
from http_test_kit import SANDI_MURID, ServerUji

HARI_INI = date(2026, 12, 3)
GURU = "akun_" + "a" * 32
GURU_LAIN = "akun_" + "b" * 32
TOPIK = "pola-bilangan"
TOPIK_LAIN = "kombinatorik"
DIBUAT = "2026-12-01T09:00:00"
TENGGAT_LEWAT = "2026-12-02"
TENGGAT_HARI_INI = "2026-12-03"
TENGGAT_NANTI = "2026-12-10"
JUDUL = "Tugas dari Guru"
LEWAT = "Lewat tenggat"
BADGE_SELESAI = '<span class="st-badge selesai">Selesai</span>'
TERLARANG_DI_KARTU = ("benar", "total", "skor", "akun_", "kor_", "klp_", "pengajar", "malrule", "kunci", "diagnosis")
PESAN_BACA_RAHASIA = "pesan rahasia di /data/guru-tugas.db"


@pytest.fixture(autouse=True)
def env_ke_berkas_sintetis(tmp_path, monkeypatch):
    """Tidak ada tes yang boleh menyentuh berkas tugas asli di /data."""
    monkeypatch.setenv(dasar.ENV_DB, str(tmp_path / "guru-tugas-env.db"))


@pytest.fixture()
def berkas_tugas(tmp_path, monkeypatch):
    berkas = tmp_path / "guru-tugas.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    return berkas


@pytest.fixture()
def gerbang_menyala(monkeypatch):
    monkeypatch.setattr(aturan, "GURU_TUGAS_AKTIF", True)


@pytest.fixture()
def db_belajar(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    return jalur


def _siswa(kon, nama):
    return database.tambah_siswa(kon, nama, tingkat="P4", pemilik="guru")


def _sesi(kon, siswa_id, seed):
    return database.buat_sesi(kon, siswa_id, seed=seed, level="P4", jumlah_soal=4)


def _tugas(berkas, sesi_id, siswa_id, *, topik=TOPIK, tenggat=None, guru=GURU):
    return dasar.catat(sesi_id=sesi_id, siswa_id=siswa_id, guru_akun=guru, topik=topik,
                       tenggat=tenggat, dibuat=DIBUAT, path=berkas)


def _kerjakan(sesi_id) -> str:
    return f'href="/murid/kerjakan/{sesi_id}"'


def _sesi_belum(isi: str) -> list:
    """Id sesi yang punya tautan Kerjakan, urut tampil. Hanya tugas belum selesai yang punya tautan."""
    return [int(sid) for sid in re.findall(r'href="/murid/kerjakan/(\d+)"', isi)]


def _kartu_html(isi: str) -> str:
    cocok = re.search(r'<section[^>]*judul-tugas-guru.*?</section>', isi, re.S)
    return "" if cocok is None else cocok.group(0)


def _beranda(server, jalur="/murid"):
    status, isi, _ = server.minta(jalur, auth=("feby", SANDI_MURID))
    assert status == 200, status
    return isi


# --- gerbang dan keadaan kosong ----------------------------------------------------------------

def test_gerbang_mati_kosong_dan_tidak_membaca_tugas(db_belajar, berkas_tugas, monkeypatch):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa)

        def tidak_boleh_dibaca(*_args, **_kwargs):
            raise AssertionError("gerbang mati tidak boleh membaca tugas")

        monkeypatch.setattr(dasar, "daftar_siswa", tidak_boleh_dibaca)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert isi == ""


def test_tanpa_tugas_kosong_dan_tidak_membuat_berkas(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert isi == ""
    assert not berkas_tugas.exists()


# --- isi kartu -----------------------------------------------------------------------------

def test_belum_selesai_tampil_dengan_tautan_kerjakan(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert JUDUL in isi
    assert _kerjakan(sesi) in isi and "Kerjakan" in isi
    assert pertemuan.label_topik(TOPIK) in isi
    assert BADGE_SELESAI not in isi


def test_selesai_tampil_selesai_tanpa_tautan_kerjakan(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa)
        database.tandai_selesai(kon, sesi)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert BADGE_SELESAI in isi
    assert _kerjakan(sesi) not in isi


def test_tenggat_tampil_format_indonesia_dan_tanpa_tenggat_tanpa_baris_tenggat(
        db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        ada = _sesi(kon, siswa, seed=11)
        tanpa = _sesi(kon, siswa, seed=12)
        _tugas(berkas_tugas, ada, siswa, tenggat=TENGGAT_NANTI)
        _tugas(berkas_tugas, tanpa, siswa, topik=TOPIK_LAIN)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert "Tenggat 10 Des 2026" in isi
    assert isi.count("Tenggat ") == 1


def test_urutan_belum_selesai_terbaru_dulu(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = [_sesi(kon, siswa, seed=20 + i) for i in range(3)]
        for sid in sesi:
            _tugas(berkas_tugas, sid, siswa)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert _sesi_belum(isi) == list(reversed(sesi))


def test_paling_banyak_lima_belum_selesai_dan_tiga_selesai(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        belum = [_sesi(kon, siswa, seed=100 + i) for i in range(7)]
        sudah = [_sesi(kon, siswa, seed=200 + i) for i in range(4)]
        for sid in belum:
            _tugas(berkas_tugas, sid, siswa)
        for sid in sudah:
            _tugas(berkas_tugas, sid, siswa)
            database.tandai_selesai(kon, sid)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert _sesi_belum(isi) == list(reversed(belum[2:]))
    assert isi.count(BADGE_SELESAI) == 3


def test_tenggat_lewat_hanya_label_dan_tautan_tetap(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa, tenggat=TENGGAT_LEWAT)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert LEWAT in isi
    assert _kerjakan(sesi) in isi


def test_selesai_yang_tenggatnya_lewat_tidak_diberi_penanda_lewat(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa, tenggat=TENGGAT_LEWAT)
        database.tandai_selesai(kon, sesi)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert BADGE_SELESAI in isi
    assert LEWAT not in isi


def test_hari_tenggat_sama_dengan_hari_ini_belum_lewat(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa, tenggat=TENGGAT_HARI_INI)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert "Tenggat 3 Des 2026" in isi
    assert LEWAT not in isi


# --- yatim, dibatalkan, dan isolasi antaranak ----------------------------------------------------

def test_yatim_dan_dibatalkan_tidak_tampil_dan_tidak_memakan_jatah(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        nyata = _sesi(kon, siswa, seed=11)
        dibatalkan = _sesi(kon, siswa, seed=12)
        _tugas(berkas_tugas, nyata, siswa)
        for sid in range(990001, 990006):
            _tugas(berkas_tugas, sid, siswa)
        database.batalkan_sesi(kon, dibatalkan)
        _tugas(berkas_tugas, dibatalkan, siswa)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert _sesi_belum(isi) == [nyata]


def test_anak_a_tidak_melihat_tugas_anak_b(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        a = _siswa(kon, "Anak Alfa")
        b = _siswa(kon, "Anak Beta")
        sesi_a = _sesi(kon, a, seed=11)
        sesi_b = _sesi(kon, b, seed=12)
        _tugas(berkas_tugas, sesi_a, a)
        _tugas(berkas_tugas, sesi_b, b, guru=GURU_LAIN)
        isi_a = kartu_guru.kartu_beranda_untuk(kon, a, HARI_INI)
        isi_b = kartu_guru.kartu_beranda_untuk(kon, b, HARI_INI)
    assert _sesi_belum(isi_a) == [sesi_a]
    assert _sesi_belum(isi_b) == [sesi_b]
    assert _kerjakan(sesi_b) not in isi_a


def test_tugas_dengan_siswa_id_tidak_cocok_dengan_sesi_tidak_tampil(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        a = _siswa(kon, "Anak Alfa")
        b = _siswa(kon, "Anak Beta")
        sesi_b = _sesi(kon, b, seed=12)
        _tugas(berkas_tugas, sesi_b, a)
        isi_a = kartu_guru.kartu_beranda_untuk(kon, a, HARI_INI)
    assert isi_a == ""


# --- palang murid ---------------------------------------------------------------------------

def test_kartu_dengan_skor_nyata_tidak_memuat_skor_atau_identitas(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        selesai = _sesi(kon, siswa, seed=11)
        belum = _sesi(kon, siswa, seed=12)
        _tugas(berkas_tugas, selesai, siswa, tenggat=TENGGAT_NANTI)
        _tugas(berkas_tugas, belum, siswa, topik=TOPIK_LAIN)
        database.tandai_selesai(kon, selesai)
        isi = _kartu_html(kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI))
    assert isi and BADGE_SELESAI in isi
    minus = isi.lower()
    for terlarang in TERLARANG_DI_KARTU + (GURU, GURU_LAIN):
        assert terlarang.lower() not in minus, terlarang


def test_skor_yang_dibaca_tidak_dirender_walau_bernilai_janggal(db_belajar, berkas_tugas, gerbang_menyala,
                                                                  monkeypatch):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        selesai = _sesi(kon, siswa, seed=11)
        belum = _sesi(kon, siswa, seed=12)
        _tugas(berkas_tugas, selesai, siswa)
        _tugas(berkas_tugas, belum, siswa, topik=TOPIK_LAIN)
        sentinel = {
            selesai: {"selesai": True, "benar": 987654, "total": 123457},
            belum: {"selesai": False, "benar": None, "total": 246813},
        }
        monkeypatch.setattr(baca, "skor_ringkas", lambda _kon, _pasangan: sentinel)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    for angka in ("987654", "123457", "246813"):
        assert angka not in isi
    assert _kerjakan(belum) in isi and BADGE_SELESAI in isi


def test_topik_berisi_html_tampil_ter_escape(db_belajar, berkas_tugas, gerbang_menyala, monkeypatch):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        baris = [{"id": 1, "sesi_id": sesi, "siswa_id": siswa, "guru_akun": GURU, "topik": "<script>alert(1)</script>",
                  "tenggat": None, "dibuat": DIBUAT}]
        monkeypatch.setattr(dasar, "daftar_siswa", lambda _siswa_id, **_kw: baris)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert "<script>" not in isi
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in isi


# --- galat baca ----------------------------------------------------------------------------

@pytest.mark.parametrize("galat", [
    dasar.GalatTugas(PESAN_BACA_RAHASIA),
    sqlite3.Error(PESAN_BACA_RAHASIA),
    OSError(PESAN_BACA_RAHASIA),
    ValueError(PESAN_BACA_RAHASIA),
])
def test_galat_baca_kosong_dan_hanya_mencatat_nama_galat(db_belajar, berkas_tugas, gerbang_menyala, monkeypatch,
                                                         caplog, galat):
    def gagal(*_args, **_kwargs):
        raise galat

    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        monkeypatch.setattr(dasar, "daftar_siswa", gagal)
        isi = kartu_guru.kartu_beranda_untuk(kon, siswa, HARI_INI)
    assert isi == ""
    assert type(galat).__name__ in caplog.text
    assert PESAN_BACA_RAHASIA not in caplog.text


# --- sisi halaman dan beranda HTTP ---------------------------------------------------------------

def test_halaman_tanpa_kartu_tugas_identik_dengan_parameter_kosong(db_belajar):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        bawaan = student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak Alfa")
        kosong = student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak Alfa", kartu_tugas="")
    assert bawaan == kosong
    assert JUDUL.encode() not in bawaan


def test_kartu_tugas_disisipkan_di_kolom_utama(db_belajar):
    penanda = "<p>penanda-kartu-tugas-uji</p>"
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        isi = student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak Alfa", kartu_tugas=penanda).decode()
    assert penanda in isi


def test_beranda_murid_menampilkan_kartu_saat_gerbang_menyala(tmp_path, monkeypatch, berkas_tugas,
                                                                gerbang_menyala):
    monkeypatch.setattr(domain_clock, "hari_wib", lambda: HARI_INI)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = _siswa(kon, "feby")
            sesi = _sesi(kon, siswa, seed=11)
            _tugas(berkas_tugas, sesi, siswa, tenggat=TENGGAT_NANTI)
        isi = _beranda(server)
    finally:
        server.berhenti()
    assert JUDUL in isi
    assert _kerjakan(sesi) in _kartu_html(isi)


def test_beranda_murid_tanpa_kartu_saat_gerbang_mati_dan_tidak_membaca_tugas(tmp_path, monkeypatch, berkas_tugas):
    monkeypatch.setattr(domain_clock, "hari_wib", lambda: HARI_INI)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = _siswa(kon, "feby")
            sesi = _sesi(kon, siswa, seed=11)
            _tugas(berkas_tugas, sesi, siswa)

        def tidak_boleh_dibaca(*_args, **_kwargs):
            raise AssertionError("gerbang mati tidak boleh membaca tugas")

        monkeypatch.setattr(dasar, "daftar_siswa", tidak_boleh_dibaca)
        isi = _beranda(server)
    finally:
        server.berhenti()
    assert JUDUL not in isi
    assert _kartu_html(isi) == ""
    assert _kerjakan(sesi) in isi  # gerbang mati tidak menyembunyikan sesi apa pun


def test_beranda_murid_tetap_200_saat_galat_baca(tmp_path, monkeypatch, berkas_tugas, gerbang_menyala):
    monkeypatch.setattr(domain_clock, "hari_wib", lambda: HARI_INI)
    server = ServerUji(tmp_path, monkeypatch)

    def gagal(*_args, **_kwargs):
        raise dasar.GalatTugas(PESAN_BACA_RAHASIA)

    try:
        with server.buka() as kon:
            _siswa(kon, "feby")
        monkeypatch.setattr(dasar, "daftar_siswa", gagal)
        isi = _beranda(server)
    finally:
        server.berhenti()
    assert JUDUL not in isi
    assert PESAN_BACA_RAHASIA not in isi


# --- himpunan sembunyi dan satu pintu masuk per sesi (isu 1) -------------------------------------

def _halaman(kon, siswa_id, kartu="", sembunyi=frozenset()) -> str:
    return student_pages.halaman_daftar_sesi_baru(
        kon, siswa_id, "Anak Alfa", kartu_tugas=kartu, sembunyikan_sesi=sembunyi).decode()


def test_tugas_beranda_gerbang_mati_kosong_tanpa_sembunyi_dan_tanpa_baca(db_belajar, berkas_tugas, monkeypatch):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa)

        def tidak_boleh_dibaca(*_args, **_kwargs):
            raise AssertionError("gerbang mati tidak boleh membaca tugas")

        monkeypatch.setattr(dasar, "daftar_siswa", tidak_boleh_dibaca)
        hasil = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
    assert hasil == ("", frozenset())


def test_belum_selesai_yang_tampil_disembunyikan_dari_daftar_biasa(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
    assert _kerjakan(sesi) in kartu
    assert sembunyi == frozenset({sesi})


def test_selesai_yang_tampil_tidak_disembunyikan(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = _sesi(kon, siswa, seed=11)
        _tugas(berkas_tugas, sesi, siswa)
        database.tandai_selesai(kon, sesi)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
    assert BADGE_SELESAI in kartu
    assert sembunyi == frozenset()


def test_sesi_di_luar_batas_yatim_dan_dibatalkan_tidak_disembunyikan(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = [_sesi(kon, siswa, seed=300 + i) for i in range(7)]
        dibatalkan = _sesi(kon, siswa, seed=400)
        for sid in sesi:
            _tugas(berkas_tugas, sid, siswa)
        database.batalkan_sesi(kon, dibatalkan)
        _tugas(berkas_tugas, dibatalkan, siswa)
        _tugas(berkas_tugas, 990010, siswa)  # yatim, paling baru
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
    assert _sesi_belum(kartu) == list(reversed(sesi[2:]))
    assert sembunyi == frozenset(sesi[2:])


@pytest.mark.parametrize("galat", [
    dasar.GalatTugas(PESAN_BACA_RAHASIA),
    sqlite3.Error(PESAN_BACA_RAHASIA),
    OSError(PESAN_BACA_RAHASIA),
    ValueError(PESAN_BACA_RAHASIA),
])
def test_galat_baca_tidak_menyembunyikan_apa_pun(db_belajar, berkas_tugas, gerbang_menyala, monkeypatch, galat):
    def gagal(*_args, **_kwargs):
        raise galat

    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        monkeypatch.setattr(dasar, "daftar_siswa", gagal)
        hasil = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
    assert hasil == ("", frozenset())


def test_satu_tautan_per_sesi_tugas_di_seluruh_halaman(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        biasa = _sesi(kon, siswa, seed=21)
        tugas = _sesi(kon, siswa, seed=22)
        _tugas(berkas_tugas, tugas, siswa)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
        assert students.beranda_murid(kon, siswa)["utama_id"] == tugas  # prasyarat: tanpa sembunyi, tugas jadi utama
        isi = _halaman(kon, siswa, kartu, sembunyi)
    assert isi.count(_kerjakan(tugas)) == 1
    assert _kerjakan(tugas) in _kartu_html(isi)
    assert _kerjakan(biasa) in isi


def test_kartu_utama_tidak_memakai_sesi_tugas_yang_disembunyikan(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        biasa = _sesi(kon, siswa, seed=21)
        tugas = _sesi(kon, siswa, seed=22)
        _tugas(berkas_tugas, tugas, siswa)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
        assert students.beranda_murid(kon, siswa)["utama_id"] == tugas
        isi = _halaman(kon, siswa, kartu, sembunyi)
    assert f'data-utama="true" {_kerjakan(tugas)}' not in isi
    assert _kerjakan(biasa) in isi


def test_hanya_tugas_tersembunyi_tanpa_keadaan_kosong_di_sampingnya(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        tugas = _sesi(kon, siswa, seed=22)
        _tugas(berkas_tugas, tugas, siswa)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
        isi = _halaman(kon, siswa, kartu, sembunyi)
    assert _kerjakan(tugas) in _kartu_html(isi)
    assert isi.count(_kerjakan(tugas)) == 1
    assert "Siap untuk latihan pertama" not in isi


def test_tugas_selesai_tetap_di_menunggu_diperiksa_tanpa_tautan(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        tugas = _sesi(kon, siswa, seed=22)
        _tugas(berkas_tugas, tugas, siswa)
        database.tandai_selesai(kon, tugas)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
        isi = _halaman(kon, siswa, kartu, sembunyi)
    assert sembunyi == frozenset()
    assert "Menunggu diperiksa" in isi
    assert _kerjakan(tugas) not in isi
    assert BADGE_SELESAI in _kartu_html(isi)


def test_beranda_murid_satu_tautan_untuk_tugas_belum_selesai(tmp_path, monkeypatch, berkas_tugas, gerbang_menyala):
    monkeypatch.setattr(domain_clock, "hari_wib", lambda: HARI_INI)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = _siswa(kon, "feby")
            biasa = _sesi(kon, siswa, seed=21)
            tugas = _sesi(kon, siswa, seed=22)
            _tugas(berkas_tugas, tugas, siswa, tenggat=TENGGAT_NANTI)
        isi = _beranda(server)
    finally:
        server.berhenti()
    assert isi.count(_kerjakan(tugas)) == 1
    assert _kerjakan(tugas) in _kartu_html(isi)
    assert _kerjakan(biasa) in isi


def test_sembunyikan_dari_cek_tetap_bekerja_bersama_sembunyi_tugas(tmp_path, monkeypatch, berkas_tugas,
                                                                     gerbang_menyala):
    monkeypatch.setattr(domain_clock, "hari_wib", lambda: HARI_INI)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = _siswa(kon, "feby")
            cek = _sesi(kon, siswa, seed=21)
            tugas = _sesi(kon, siswa, seed=22)
            _tugas(berkas_tugas, tugas, siswa)
        monkeypatch.setattr(cek_murid, "untuk_beranda", lambda _kon, _akun, _siswa_id: ("", frozenset({cek})))
        isi = _beranda(server)
    finally:
        server.berhenti()
    assert _kerjakan(cek) not in isi
    assert isi.count(_kerjakan(tugas)) == 1


def test_galat_baca_di_beranda_tidak_menyembunyikan_sesi(tmp_path, monkeypatch, berkas_tugas, gerbang_menyala):
    monkeypatch.setattr(domain_clock, "hari_wib", lambda: HARI_INI)
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            siswa = _siswa(kon, "feby")
            biasa = _sesi(kon, siswa, seed=21)
            tugas = _sesi(kon, siswa, seed=22)
            _tugas(berkas_tugas, tugas, siswa)

        def gagal(*_args, **_kwargs):
            raise dasar.GalatTugas(PESAN_BACA_RAHASIA)

        monkeypatch.setattr(dasar, "daftar_siswa", gagal)
        isi = _beranda(server)
    finally:
        server.berhenti()
    assert isi.count(_kerjakan(tugas)) == 1
    assert _kerjakan(biasa) in isi


def test_sesi_di_luar_batas_tetap_tampil_di_daftar_biasa(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        sesi = [_sesi(kon, siswa, seed=300 + i) for i in range(7)]
        for sid in sesi:
            _tugas(berkas_tugas, sid, siswa)
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
        assert students.beranda_murid(kon, siswa)["utama_id"] == sesi[6]  # prasyarat: sesi terbaru jadi utama
        isi = _halaman(kon, siswa, kartu, sembunyi)
    for lewat in sesi[:2]:
        assert _kerjakan(lewat) in isi
        assert _kerjakan(lewat) not in _kartu_html(isi)
    assert isi.count(_kerjakan(sesi[6])) == 1


def test_tugas_selesai_dan_diperiksa_tetap_punya_tautan_hasil_di_riwayat(db_belajar, berkas_tugas, gerbang_menyala):
    with database.buka(db_belajar) as kon:
        siswa = _siswa(kon, "Anak Alfa")
        tugas = _sesi(kon, siswa, seed=22)
        _tugas(berkas_tugas, tugas, siswa)
        database.tandai_selesai(kon, tugas)
        kon.execute("UPDATE sesi SET direview='2026-12-02' WHERE id=?", (tugas,))
        kartu, sembunyi = kartu_guru.tugas_beranda_untuk(kon, siswa, HARI_INI)
        isi = _halaman(kon, siswa, kartu, sembunyi)
    assert sembunyi == frozenset()
    assert f'href="/murid/hasil/{tugas}"' in isi
    assert _kerjakan(tugas) not in isi

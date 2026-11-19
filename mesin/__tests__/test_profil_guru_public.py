"""Halaman publik funnel membaca profil guru dari store admin; data sepenuhnya fiktif."""
from __future__ import annotations

import sqlite3

import pytest

import admin_store
import auth
import funnel_contoh
import funnel_pages
import profil_guru_settings as pg
from http_test_kit import ServerUji

RUTE = ("/paket-coba", "/contoh-peta-kemampuan")
SANDI = "sandi-admin-publik-123"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


def _admin():
    if auth.cari_akun("Admin-Publik") is None:
        auth.tambah_akun("Admin-Publik", SANDI, "admin")
    return auth.autentikasi("Admin-Publik", SANDI)


def _isi_profil(**timpa):
    pg.migrasikan(admin_store.BAWAAN, sekarang=2)
    nilai = dict(operasi="op_" + "1" * 32, nama="Guru Contoh", latar="S1 Pendidikan Matematika (contoh)",
                 lama_mengajar="5 tahun (contoh)", urutan=1, tampil=True, sekarang=10)
    nilai.update(timpa)
    return pg.tambah(admin_store.BAWAAN, auth.BERKAS_SANDI, _admin(), **nilai)


def _tanpa_fitur(jalur):
    """Halaman yang dirender renderer lama (tanpa argumen profil) = perilaku sebelum fitur."""
    renderer = {"/paket-coba": funnel_pages.halaman_paket_coba,
                "/contoh-peta-kemampuan": funnel_contoh.halaman_contoh_peta}[jalur]
    return renderer(None).decode()


@pytest.mark.parametrize("jalur", RUTE)
def test_tabel_absen_halaman_identik_byte_per_byte_dengan_sebelum_fitur(server, jalur):
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    assert isi == _tanpa_fitur(jalur)
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU not in isi


@pytest.mark.parametrize("jalur", RUTE)
def test_tabel_ada_tapi_kosong_identik_dengan_sebelum_fitur(server, jalur):
    pg.migrasikan(admin_store.BAWAAN, sekarang=2)
    assert server.minta(jalur)[1] == _tanpa_fitur(jalur)


@pytest.mark.parametrize("jalur", RUTE)
def test_profil_tampil_dirender_dan_yang_tersembunyi_tidak(server, jalur):
    _isi_profil()
    _isi_profil(operasi="op_" + "2" * 32, nama="Guru Contoh Tersembunyi", urutan=2, tampil=False)
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU in isi
    assert "Guru Contoh" in isi and "S1 Pendidikan Matematika (contoh)" in isi and "5 tahun (contoh)" in isi
    assert "Tersembunyi" not in isi


@pytest.mark.parametrize("jalur", RUTE)
def test_nilai_dari_store_di_escape_pada_halaman(server, jalur):
    _isi_profil(nama='Guru "Contoh" & \'Rekan\'')
    isi = server.minta(jalur)[1]
    assert "Guru &quot;Contoh&quot; &amp; &#x27;Rekan&#x27;" in isi
    assert 'Guru "Contoh" & \'Rekan\'' not in isi


def test_escape_langsung_pada_sumber_data_renderer():
    kartu = funnel_pages.kartu_profil_guru((
        {"nama": "<script>alert(1)</script>", "latar": '"><img src=x>', "lama_mengajar": "a & b"},
    ))
    assert "<script>" not in kartu and "<img" not in kartu
    assert "&lt;script&gt;" in kartu and "a &amp; b" in kartu


def test_semantik_profil_none_konstanta_dan_kosong_tanpa_kartu(monkeypatch):
    monkeypatch.setattr(funnel_pages, "PROFIL_GURU", ({"nama": "Guru Konstanta", "latar": "x", "lama_mengajar": "y"},))
    assert "Guru Konstanta" in funnel_pages.kartu_profil_guru(None)
    assert funnel_pages.kartu_profil_guru(()) == ""
    assert "Guru Konstanta" not in funnel_pages.halaman_paket_coba(None, ()).decode()
    assert "Guru Konstanta" not in funnel_contoh.halaman_contoh_peta(None, ()).decode()
    assert "Guru Konstanta" in funnel_pages.halaman_paket_coba(None).decode()


@pytest.mark.parametrize("jalur", RUTE)
def test_sakelar_mati_tidak_membaca_database(server, monkeypatch, jalur):
    _isi_profil()
    monkeypatch.setenv("FUNNEL_AKTIF", "0")

    def terlarang(*a, **kw):
        pytest.fail("profil guru dibaca saat sakelar funnel mati")
    monkeypatch.setattr(pg, "baca_publik", terlarang)
    kode, isi, _ = server.minta(jalur)
    assert kode == 200 and "belum dibuka" in isi.lower()
    assert funnel_pages.COPY_JUDUL_PROFIL_GURU not in isi


@pytest.mark.parametrize("jalur", RUTE)
def test_galat_baca_berarti_tanpa_kartu_bukan_500(server, monkeypatch, jalur):
    _isi_profil()

    def rusak(*a, **kw):
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(pg, "baca_publik", rusak)
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    assert isi == _tanpa_fitur(jalur)


@pytest.mark.parametrize("jalur", RUTE)
def test_skema_parsial_berarti_tanpa_kartu(server, jalur):
    _isi_profil()
    with sqlite3.connect(admin_store.BAWAAN) as kon:
        kon.execute("DROP TABLE profil_guru_audit")
    assert server.minta(jalur)[1] == _tanpa_fitur(jalur)


def test_pembaca_publik_hanya_membaca_tidak_menulis(server):
    _isi_profil()
    awal = admin_store.BAWAAN.read_bytes()
    server.minta("/paket-coba")
    server.minta("/contoh-peta-kemampuan")
    assert admin_store.BAWAAN.read_bytes() == awal

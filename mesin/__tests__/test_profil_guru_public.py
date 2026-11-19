"""Halaman publik funnel membaca profil guru dari store admin; data sepenuhnya fiktif."""
from __future__ import annotations

import sqlite3

import pytest

import admin_store
import auth
import funnel_contoh
import funnel_http
import funnel_pages
import profil_guru_settings as pg
from http_test_kit import ServerUji

RUTE = ("/paket-coba", "/contoh-peta-kemampuan")
SANDI = "sandi-admin-publik-123"


@pytest.fixture(autouse=True)
def cache_bersih():
    funnel_http._reset_cache_profil()
    yield
    funnel_http._reset_cache_profil()


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


# --- cache TTL pembacaan profil ------------------------------------------------------

class _Jam:
    def __init__(self):
        self.kini = 1000.0

    def __call__(self):
        return self.kini


def _hitung_baca(monkeypatch):
    panggilan = []
    asli = pg.baca_publik

    def pembungkus(*a, **kw):
        panggilan.append(a)
        return asli(*a, **kw)
    monkeypatch.setattr(pg, "baca_publik", pembungkus)
    return panggilan


def test_ttl_ditetapkan_sebagai_konstanta_bernama():
    assert funnel_http.TTL_PROFIL_DETIK == 30


@pytest.mark.parametrize("jalur", RUTE)
def test_dua_get_dalam_ttl_hanya_membuka_store_sekali(server, monkeypatch, jalur):
    jam = _Jam()
    monkeypatch.setattr(funnel_http, "_sekarang", jam)
    _isi_profil()
    panggilan = _hitung_baca(monkeypatch)
    pertama = server.minta(jalur)[1]
    jam.kini += funnel_http.TTL_PROFIL_DETIK - 1
    kedua = server.minta(jalur)[1]
    assert len(panggilan) == 1
    assert pertama == kedua and funnel_pages.COPY_JUDUL_PROFIL_GURU in kedua


def test_setelah_ttl_habis_dibaca_ulang_dan_perubahan_tampil(server, monkeypatch):
    jam = _Jam()
    monkeypatch.setattr(funnel_http, "_sekarang", jam)
    _isi_profil(nama="Guru Contoh Lama")
    panggilan = _hitung_baca(monkeypatch)
    assert "Guru Contoh Lama" in server.minta("/paket-coba")[1]
    with sqlite3.connect(admin_store.BAWAAN) as kon:
        kon.execute("UPDATE profil_guru SET tampil=0")
    assert "Guru Contoh Lama" in server.minta("/paket-coba")[1]       # masih di dalam TTL
    jam.kini += funnel_http.TTL_PROFIL_DETIK
    assert "Guru Contoh Lama" not in server.minta("/paket-coba")[1]   # TTL habis: data baru
    assert len(panggilan) == 2


def test_hasil_galat_juga_di_cache_agar_kegagalan_tidak_membanjiri_db(server, monkeypatch):
    jam = _Jam()
    monkeypatch.setattr(funnel_http, "_sekarang", jam)
    panggilan = []

    def rusak(*a, **kw):
        panggilan.append(a)
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(pg, "baca_publik", rusak)
    for _ in range(3):
        assert server.minta("/paket-coba")[1] == _tanpa_fitur("/paket-coba")
    assert len(panggilan) == 1
    jam.kini += funnel_http.TTL_PROFIL_DETIK
    server.minta("/paket-coba")
    assert len(panggilan) == 2


def test_cache_per_path_database_dan_dapat_direset(server, monkeypatch, tmp_path):
    jam = _Jam()
    monkeypatch.setattr(funnel_http, "_sekarang", jam)
    _isi_profil()
    panggilan = _hitung_baca(monkeypatch)
    server.minta("/paket-coba")
    funnel_http._reset_cache_profil()
    server.minta("/paket-coba")
    assert len(panggilan) == 2
    monkeypatch.setattr(admin_store, "BAWAAN", tmp_path / "lain.db")
    server.minta("/paket-coba")
    assert len(panggilan) == 3


@pytest.mark.parametrize("jalur", RUTE)
def test_sakelar_mati_tidak_membaca_dan_tidak_mengisi_cache(server, monkeypatch, jalur):
    _isi_profil()
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    panggilan = _hitung_baca(monkeypatch)
    assert "belum dibuka" in server.minta(jalur)[1].lower()
    assert panggilan == [] and funnel_http._cache_profil == {}

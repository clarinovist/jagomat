"""Banner perpanjang paket belajar di halaman orang tua lewat HTTP nyata (`GET /murid/orang-tua`).

- Sakelar PAKET_BELAJAR mati: tanpa banner dan DB kelas TIDAK dibuka sama sekali.
- Sakelar hidup: banner untuk paket yang segera berakhir atau sudah habis, dibaca dari akun dan anak sesi.
- Galat DB kelas: halaman tetap 200 tanpa banner.
Waktu dikendalikan fixture `jam`; data sintetis; tanpa jaringan.
"""
from __future__ import annotations

import sqlite3

import pytest

import admin_store as _admin_store
import admin_store_core
import kelas_putusan
import kelas_store
from kelas_http_kit import (ADMIN, AWAL, bukti_terakhir, buat_dan_unggah, buat_murid, jam, kidup,  # noqa: F401
                            kmati, minta_mentah, server)

JALUR = "/murid/orang-tua"
ANAK = "Anak Sintetis"
PENANDA = 'id="ortu-paket-banner"'
# Akses Mini disetujui pada AWAL (2026-11-23T03:00:00): berakhir satu bulan kalender kemudian.
BERAKHIR = "2026-12-23T03:00:00"


@pytest.fixture()
def murid_berakses(kidup, monkeypatch):
    """Murid dengan satu akses Mini yang disetujui pada AWAL; sakelar pendaftaran anak menyala."""
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    murid = buat_murid(kidup, "murid-ortu", ANAK)
    oid = buat_dan_unggah(kidup, murid, "mini")
    with kelas_store.buka(_admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, oid, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(oid))
    return murid


def _halaman(server_uji, murid):
    kode, isi, _ = minta_mentah(server_uji, JALUR, murid.akun)
    return kode, isi


def test_sakelar_paket_mati_tanpa_banner_dan_db_kelas_tidak_dibuka(murid_berakses, server, jam, monkeypatch):
    jam.nilai = "2026-12-24T03:00:00"                  # sudah habis: banner akan muncul bila sakelar hidup
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    dibuka = []

    def buka_dicatat(*args, **kwargs):
        dibuka.append(args)
        raise sqlite3.OperationalError("uji: DB kelas tidak boleh dibuka saat sakelar mati")

    monkeypatch.setattr(kelas_store, "buka", buka_dicatat)
    kode, isi = _halaman(server, murid_berakses)
    assert kode == 200 and PENANDA not in isi and 'id="judul-ortu"' in isi
    assert dibuka == []


def test_sakelar_hidup_paket_sudah_habis_menampilkan_banner(murid_berakses, server, jam):
    jam.nilai = "2026-12-24T03:00:00"
    kode, isi = _halaman(server, murid_berakses)
    assert kode == 200 and PENANDA in isi
    assert f"Paket Mini Class {ANAK} sudah berakhir." in isi and "Sudah berakhir" in isi
    assert 'href="/murid/paket"' in isi


def test_sakelar_hidup_paket_segera_berakhir_menampilkan_sisa_hari(murid_berakses, server, jam):
    jam.nilai = "2026-12-21T03:00:00"                  # sisa tepat 2 hari sebelum BERAKHIR
    kode, isi = _halaman(server, murid_berakses)
    assert kode == 200 and PENANDA in isi
    assert f"Paket Mini Class {ANAK} berakhir 2 hari lagi." in isi and "Segera berakhir" in isi


def test_sakelar_hidup_paket_masih_jauh_dari_batas_tanpa_banner(murid_berakses, server, jam):
    jam.nilai = "2026-12-01T03:00:00"
    kode, isi = _halaman(server, murid_berakses)
    assert kode == 200 and PENANDA not in isi and 'id="judul-ortu"' in isi


@pytest.mark.parametrize("galat", [sqlite3.OperationalError("uji"), admin_store_core.StoreBelumSiap("uji")],
                         ids=["sqlite", "belum-siap"])
def test_galat_db_kelas_halaman_tetap_tampil_tanpa_banner(murid_berakses, server, jam, monkeypatch, galat):
    jam.nilai = "2026-12-24T03:00:00"

    def buka_gagal(*args, **kwargs):
        raise galat

    monkeypatch.setattr(kelas_store, "buka", buka_gagal)
    kode, isi = _halaman(server, murid_berakses)
    assert kode == 200 and PENANDA not in isi and 'id="judul-ortu"' in isi

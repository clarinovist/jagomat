"""Banner "tagihan belum dibayar" di halaman orang tua lewat HTTP nyata (butir QA #3, notifikasi gantung; data sintetis).

Hanya untuk tagihan paket belajar yang masih menunggu pembayaran (belum_bayar) atau perlu unggah ulang (ditolak) dan
jendela bayarnya terbuka. Tidak tampil bila bukti sudah menunggu verifikasi, tagihan habis, atau sakelar PAKET_BELAJAR mati.
"""
from __future__ import annotations

import sqlite3

import pytest

import kelas_masa
import kelas_store
from kelas_http_kit import (buat, buat_dan_unggah, buat_murid, jam, kidup, kmati, minta_mentah, server)  # noqa: F401

JALUR = "/murid/orang-tua"
ANAK = "Anak Sintetis"
PENANDA = 'id="ortu-tagihan-banner"'


@pytest.fixture()
def murid(kidup, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    return buat_murid(kidup, "murid-tagihan", ANAK)


def _halaman(server_uji, pembeli):
    kode, isi, _ = minta_mentah(server_uji, JALUR, pembeli.akun)
    return kode, isi


def test_tagihan_belum_dibayar_menampilkan_banner_dengan_tautan_ke_halaman_bayar(kidup, murid):
    buat(kidup, murid, "mini")
    kode, isi = _halaman(kidup, murid)
    assert kode == 200 and PENANDA in isi
    assert "Tagihan Mini Class" in isi and "belum dibayar" in isi and 'href="/murid/paket"' in isi
    assert "Lanjutkan pembayaran" in isi


def test_tanpa_tagihan_tanpa_banner(kidup, murid):
    assert PENANDA not in _halaman(kidup, murid)[1]


def test_bukti_sudah_menunggu_verifikasi_tanpa_banner(kidup, murid):
    buat_dan_unggah(kidup, murid, "mini")
    assert PENANDA not in _halaman(kidup, murid)[1]


def test_tagihan_kedaluwarsa_tanpa_banner(kidup, murid, jam):
    buat(kidup, murid, "mini")
    jam.maju_jam(25)
    assert PENANDA not in _halaman(kidup, murid)[1]


def test_sakelar_mati_tanpa_banner_dan_db_kelas_tidak_dibuka(kidup, murid, monkeypatch):
    buat(kidup, murid, "mini")
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    dibuka = []

    def buka_dicatat(*args, **kwargs):
        dibuka.append(args)
        raise sqlite3.OperationalError("uji: DB kelas tidak boleh dibuka saat sakelar mati")

    monkeypatch.setattr(kelas_store, "buka", buka_dicatat)
    assert PENANDA not in _halaman(kidup, murid)[1] and dibuka == []


def test_galat_db_kelas_halaman_tetap_200_tanpa_banner(kidup, murid, monkeypatch):
    buat(kidup, murid, "mini")

    def rusak(*args, **kwargs):
        raise sqlite3.OperationalError("uji: DB kelas rusak")

    monkeypatch.setattr(kelas_masa, "tagihan_belum_dibayar", rusak)
    kode, isi = _halaman(kidup, murid)
    assert kode == 200 and PENANDA not in isi

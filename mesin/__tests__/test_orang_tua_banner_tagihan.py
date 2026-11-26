"""Banner "tagihan belum dibayar" di halaman orang tua lewat HTTP nyata (butir QA #3, notifikasi gantung; data sintetis).

Hanya untuk tagihan paket belajar yang masih menunggu pembayaran (belum_bayar) atau perlu unggah ulang (ditolak) dan
jendela bayarnya terbuka. Tidak tampil bila bukti sudah menunggu verifikasi, tagihan habis, atau sakelar PAKET_BELAJAR mati.
"""
from __future__ import annotations

import sqlite3

import pytest

import kelas_masa
import kelas_store
from bukti_kit import JPEG
from kelas_http_kit import (buat, buat_dan_unggah, buat_murid, hapus_tagihan, jam, kidup, kmati, minta_mentah,  # noqa: F401
                            pasang_catatan, server, unggah)

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
    assert "Tagihan Mini Class" in isi and "belum dibayar" in isi and 'href="/murid/paket/tagihan?kode=mini"' in isi
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


def _banner(isi):
    awal = isi.index(PENANDA)
    return isi[awal:isi.index("</p>", awal)]


def test_dua_tagihan_belum_dibayar_dua_baris_masing_masing_menaut_kodenya(kidup, murid):
    assert buat(kidup, murid, "private")[0] == 303
    assert buat(kidup, murid, "mini")[0] == 303
    banner = _banner(_halaman(kidup, murid)[1])
    assert banner.count("<br>") == 1 and banner.count("Lanjutkan pembayaran") == 2
    assert 'href="/murid/paket/tagihan?kode=private"' in banner and 'href="/murid/paket/tagihan?kode=mini"' in banner


def test_tagihan_menunggu_verifikasi_tidak_diingatkan_tagihan_lain_tetap(kidup, murid):
    assert buat(kidup, murid, "private")[0] == 303
    assert buat(kidup, murid, "mini")[0] == 303
    assert unggah(kidup, murid, JPEG, kode="mini")[0] == 303
    banner = _banner(_halaman(kidup, murid)[1])
    assert "kode=private" in banner and "kode=mini" not in banner


def test_tagihan_dibatalkan_tidak_diingatkan(kidup, murid):
    pasang_catatan()
    assert buat(kidup, murid, "private")[0] == 303
    assert buat(kidup, murid, "mini")[0] == 303
    assert hapus_tagihan(kidup, murid, "mini")[0] == 303
    banner = _banner(_halaman(kidup, murid)[1])
    assert "kode=private" in banner and "kode=mini" not in banner

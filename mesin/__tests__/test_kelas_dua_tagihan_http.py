"""Dua tagihan Paket Belajar berdampingan lewat HTTP nyata (data sintetis): daftar selalu tampil, halaman tagihan per KODE
PAKET, dan unggah masuk ke tagihan paket yang dipilih. Id order tidak pernah dirender; kode paket dari allowlist.
"""
from __future__ import annotations

import re

import pytest

from bukti_kit import JPEG, PNG
from kelas_http_kit import (M, baca_admin, buat, buat_murid, halaman, hitung, jam, kidup, kmati, minta_mentah, semua_berkas,  # noqa: F401
                            server, tagihan_halaman, token, unggah)

TAUTAN_MINI = 'href="/murid/paket/tagihan?kode=mini"'
TAUTAN_PRIVATE = 'href="/murid/paket/tagihan?kode=private"'
KARTU_DI_ATAS = "Tagihan paket ini ada di atas."


def _teks(isi):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def _rupiah(nilai):
    return "Rp" + f"{nilai:,}".replace(",", ".")


def _total(paket):
    (baris,) = baca_admin("SELECT t.total_transfer FROM kelas_tagihan t JOIN kelas_order o ON o.id=t.order_id "
                          "WHERE o.paket=?", (paket,))
    return baris["total_transfer"]


def _paket_bukti():
    return [r["paket"] for r in baca_admin("SELECT o.paket FROM kelas_bukti b JOIN kelas_order o ON o.id=b.order_id "
                                           "ORDER BY b.id")]


@pytest.fixture()
def dua(kidup):
    """Anak dengan dua tagihan terbuka berdampingan; `mini` dibuat terakhir (paling baru)."""
    anak = buat_murid(kidup, "murid-a", "Anak Alfa")
    assert buat(kidup, anak, "private")[0] == 303
    assert buat(kidup, anak, "mini")[0] == 303
    return anak


# --- daftar selalu tampil ------------------------------------------------------------------------

def test_daftar_selalu_tampil_dengan_dua_kartu_tagihan_dan_tanpa_id_order(kidup, dua):
    isi = halaman(kidup, dua)
    assert TAUTAN_MINI in isi and TAUTAN_PRIVATE in isi
    assert _rupiah(_total("mini")) in _teks(isi) and _rupiah(_total("private")) in _teks(isi)
    assert isi.count(KARTU_DI_ATAS) == 2 and 'action="/murid/paket/buat"' not in isi
    assert "kor_" not in isi


def test_daftar_menampilkan_status_teks_per_tagihan(kidup, dua):
    t = _teks(halaman(kidup, dua))
    assert t.count("Menunggu pembayaran") == 2


def test_kembali_dari_halaman_tagihan_menuju_daftar_yang_selalu_tampil(kidup, dua):
    _kode, isi, _ = tagihan_halaman(kidup, dua, "mini")
    assert 'href="/murid/paket"' in isi and "Kembali ke pilih paket" in _teks(isi)
    kode, daftar, _ = minta_mentah(kidup, M, dua.akun)
    assert kode == 200 and "Pilih paket" in _teks(daftar)
    assert TAUTAN_MINI in daftar and TAUTAN_PRIVATE in daftar


# --- halaman tagihan per kode paket ----------------------------------------------------------------

def test_tagihan_per_kode_hanya_memuat_paket_itu_dan_formulir_terikat_kode(kidup, dua):
    kode, isi, _ = tagihan_halaman(kidup, dua, "private")
    assert kode == 200
    assert 'action="/murid/paket/bukti?kode=private"' in isi and 'action="/murid/paket/bukti?kode=mini"' not in isi
    t = _teks(isi)
    assert _rupiah(_total("private")) in t and _rupiah(_total("mini")) not in t
    assert "Bank Contoh" in t and "kor_" not in isi


def test_tagihan_tanpa_tagihan_terbuka_404_identik_dan_tanpa_id(kidup, dua):
    lain = buat_murid(kidup, "murid-b", "Anak Beta")
    assert buat(kidup, lain, "mini")[0] == 303          # tagihan milik anak lain: tidak boleh terlihat dari sini
    kosong = buat_murid(kidup, "murid-c", "Anak Gamma")
    hasil = [tagihan_halaman(kidup, kosong, kode) for kode in ("mini", "private", "gratis")]
    assert [h[0] for h in hasil] == [404, 404, 404]
    assert hasil[0][1] == hasil[1][1] == hasil[2][1]
    assert "kor_" not in hasil[0][1] and "Bank Contoh" not in hasil[0][1]


# --- unggah masuk ke tagihan paket yang dipilih ----------------------------------------------------

def test_unggah_masuk_ke_tagihan_paket_yang_dipilih_walau_mini_terbaru(kidup, dua):
    kode, _, tajuk = unggah(kidup, dua, JPEG, kode="private")
    assert (kode, tajuk["Location"]) == (303, M)
    assert _paket_bukti() == ["private"]
    assert unggah(kidup, dua, PNG, kode="mini")[0] == 303
    assert _paket_bukti() == ["private", "mini"]


def test_token_unggah_terikat_kode_paket(kidup, dua):
    kode, _, _ = unggah(kidup, dua, JPEG, kode="private", tok=token(dua.akun, "kelas_bukti:mini"))
    assert kode == 403
    assert hitung()["kelas_bukti"] == 0 and semua_berkas(kidup) == []


def test_unggah_kode_asing_404_sebelum_db_tanpa_berkas(kidup, dua):
    kode, isi, _ = unggah(kidup, dua, JPEG, kode="gratis")
    assert kode == 404 and "kor_" not in isi
    assert hitung()["kelas_bukti"] == 0 and semua_berkas(kidup) == []


def test_unggah_ke_paket_tanpa_tagihan_terbuka_409_tanpa_efek(kidup):
    anak = buat_murid(kidup, "murid-d", "Anak Delta")
    assert buat(kidup, anak, "mini")[0] == 303
    awal = hitung()
    assert unggah(kidup, anak, JPEG, kode="private")[0] == 409
    assert hitung() == awal and semua_berkas(kidup) == []

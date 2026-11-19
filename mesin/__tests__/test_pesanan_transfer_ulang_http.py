"""HTTP jendela bayar ulang jalur transfer (POST /pesanan/tagihan/ulang) dan tombolnya di /pesanan.

Server loopback + runtime/provider PALSU, data sintetis. Efek dibuktikan dari ledger, bukan kode status saja.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pesanan_dasar  # noqa: E402
import pesanan_pages  # noqa: E402
import pesanan_transfer_pages as teks  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    AKUN_A, AKUN_ADMIN, AKUN_B, STATUS, TAGIHAN, atur_tahap, bayar, dua_jalur, hitung,
    jam, keluarga, kirim, kirim_bukti, kirim_tagihan, ledger, minta_mentah, server, siap_order,
    siap_tagihan, teks_tampak, tertutup, token, transfer, JPEG,
)

ULANG = "/pesanan/tagihan/ulang"
JUDUL_TOMBOL = teks.COPY_TOMBOL_ULANG


def _kirim_ulang(server, akun=AKUN_A, **kw):
    return kirim(server, ULANG, akun, aksi=teks.AKSI_ULANG, **kw)


def _kedaluwarsakan(jam):
    jam.maju_jam(25)


def _jendela():
    with ledger() as kon:
        return [tuple(r) for r in kon.execute("SELECT urutan FROM pesanan_jendela ORDER BY urutan")]


def _tagihan_nominal():
    with ledger() as kon:
        return [r[0] for r in kon.execute("SELECT nominal_transfer FROM transfer_tagihan ORDER BY urutan")]


def _stempel():
    return _jendela(), hitung("transfer_tagihan"), hitung("transfer_bukti")


def _halaman(server, akun=AKUN_A):
    kode, isi, _t = minta_mentah(server, STATUS, akun)
    assert kode == 200
    return isi


# --- tombol ----------------------------------------------------------------------

def test_tombol_muncul_saat_jendela_habis_tanpa_bukti_dan_midtrans_tertutup(transfer, jam):
    siap_tagihan(transfer)
    assert ULANG not in _halaman(transfer)                    # jendela masih terbuka
    _kedaluwarsakan(jam)
    isi = _halaman(transfer)
    assert 'action="%s"' % ULANG in isi and JUDUL_TOMBOL in isi
    assert "Waktu pembayaran habis" in isi
    assert isi.count(ULANG) == 1                              # satu aksi satu tombol


def test_tombol_tidak_muncul_bila_midtrans_terbuka(dua_jalur, jam):
    siap_tagihan(dua_jalur)
    _kedaluwarsakan(jam)
    isi = _halaman(dua_jalur)
    assert ULANG not in isi and JUDUL_TOMBOL not in isi


def test_tombol_tidak_muncul_bila_ada_bukti_menunggu(transfer, jam):
    siap_tagihan(transfer)
    assert kirim_bukti(transfer, JPEG)[0] == 303
    _kedaluwarsakan(jam)
    assert ULANG not in _halaman(transfer)


# --- aksi ----------------------------------------------------------------------

def test_ulang_membuka_jendela_baru_lalu_tagihan_baru_dengan_nominal_baru(transfer, jam):
    siap_tagihan(transfer)
    lama = _tagihan_nominal()[0]
    _kedaluwarsakan(jam)
    kode, isi, tajuk = _kirim_ulang(transfer)
    assert (kode, isi, tajuk["Location"]) == (303, "", STATUS)
    assert _jendela() == [(1,), (2,)]
    halaman = _halaman(transfer)
    assert "Buat tagihan transfer" in halaman and ULANG not in halaman
    assert kirim_tagihan(transfer)[0] == 303
    baru = _tagihan_nominal()
    assert len(baru) == 2 and baru[0] == lama and 49001 <= baru[1] <= 49999
    tampak = teks_tampak(_halaman(transfer))
    assert "Rp49.%03d" % (baru[1] - 49000) in tampak


def test_ulang_sebelum_jendela_habis_ditolak_409_tanpa_efek(transfer):
    siap_tagihan(transfer)
    sebelum = _stempel()
    kode, isi, _t = _kirim_ulang(transfer)
    assert kode == 409 and "Traceback" not in isi
    assert _stempel() == sebelum


def test_ulang_dengan_bukti_menunggu_ditolak_409_tanpa_efek(transfer, jam):
    siap_tagihan(transfer)
    assert kirim_bukti(transfer, JPEG)[0] == 303
    _kedaluwarsakan(jam)
    sebelum = _stempel()
    assert _kirim_ulang(transfer)[0] == 409
    assert _stempel() == sebelum


def test_ulang_ganda_berurutan_hanya_satu_jendela_baru(transfer, jam):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    assert _kirim_ulang(transfer)[0] == 303
    assert _kirim_ulang(transfer)[0] == 409
    assert _jendela() == [(1,), (2,)]


def test_batas_lima_jendela_empat_kali_ulang_lalu_ditolak_dan_tombol_hilang(transfer, jam):
    siap_tagihan(transfer)
    for _ in range(4):
        _kedaluwarsakan(jam)
        assert _kirim_ulang(transfer)[0] == 303
    assert _jendela() == [(n,) for n in range(1, 6)]
    _kedaluwarsakan(jam)
    assert ULANG not in _halaman(transfer)
    kode, isi, _t = _kirim_ulang(transfer)
    assert kode == 409 and pesanan_pages.COPY_BATAS_ULANG in isi
    assert _jendela() == [(n,) for n in range(1, 6)]


def test_kuota_habis_tombol_hilang_dan_ulang_ditolak(transfer, jam, monkeypatch):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 0)
    assert ULANG not in _halaman(transfer)
    kode, isi, _t = _kirim_ulang(transfer)
    assert kode == 409 and pesanan_pages.COPY_KUOTA_HABIS in isi
    assert _jendela() == [(1,)]


# --- guard ---------------------------------------------------------------------

def test_midtrans_terbuka_rute_tidak_ditangani_404_tanpa_efek(dua_jalur, jam):
    siap_tagihan(dua_jalur)
    _kedaluwarsakan(jam)
    acuan = minta_mentah(dua_jalur, "/rute-tidak-ada", AKUN_A, {"x": "1"})
    kode, isi, _t = _kirim_ulang(dua_jalur)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert _jendela() == [(1,)]


@pytest.mark.parametrize("cara", ["env-hilang", "rekening"])
def test_gerbang_transfer_tertutup_404_tanpa_efek(transfer, jam, monkeypatch, cara):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    tok = token(AKUN_A, teks.AKSI_ULANG)
    if cara == "env-hilang":
        monkeypatch.delenv("PESANAN_TRANSFER_AKTIF")
    else:
        import pesanan_rekening
        monkeypatch.setattr(pesanan_rekening, "baca_publik", lambda path=None: None)
    acuan = minta_mentah(transfer, "/rute-tidak-ada", AKUN_A, {"x": "1"})
    kode, isi, _t = minta_mentah(transfer, ULANG, AKUN_A, {"token": tok})
    assert (kode, isi) == acuan[:2] and _jendela() == [(1,)]


def test_token_aksi_lain_ditolak_403_tanpa_efek(transfer, jam):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    for aksi in ("ulang", "tagihan", "bukti", "pesan"):
        assert _kirim_ulang(transfer, tok=token(AKUN_A, aksi))[0] == 403
    assert _kirim_ulang(transfer, tok="rusak")[0] == 403
    assert _jendela() == [(1,)]


@pytest.mark.parametrize("ekstra,hapus", [({"order_id": "x"}, ()), ({"nominal": "1"}, ()), (None, ("token",))])
def test_form_tidak_sah_400_tanpa_efek(transfer, jam, ekstra, hapus):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    assert _kirim_ulang(transfer, ekstra=ekstra, hapus=hapus)[0] == 400
    assert _jendela() == [(1,)]


def test_anonim_ditolak_palang_sandi_tanpa_efek(transfer, jam):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    assert minta_mentah(transfer, ULANG, None, {"token": "x"})[0] == 401
    assert _jendela() == [(1,)]


def test_admin_404_identik_rute_tak_dikenal_tanpa_efek(transfer, jam):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    acuan = minta_mentah(transfer, "/rute-tidak-ada", AKUN_ADMIN, {"x": "1"})
    kode, isi, _t = minta_mentah(transfer, ULANG, AKUN_ADMIN, {"token": token(AKUN_A, teks.AKSI_ULANG)})
    assert (kode, isi) == acuan[:2] and kode == 404
    assert _jendela() == [(1,)]


def test_akun_tanpa_order_404_identik_tanpa_efek(transfer, jam):
    siap_tagihan(transfer)
    _kedaluwarsakan(jam)
    acuan = minta_mentah(transfer, "/rute-tidak-ada", AKUN_B, {"x": "1"})
    kode, isi, _t = _kirim_ulang(transfer, AKUN_B)
    assert (kode, isi) == acuan[:2] and kode == 404
    assert _jendela() == [(1,)]

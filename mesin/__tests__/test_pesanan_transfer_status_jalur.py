"""Status baru transfer (`menunggu_verifikasi`, `ditolak`) di halaman /pesanan pada semua kombinasi gerbang.

Celah yang ditutup: status baru tidak boleh membuat KeyError/500 di jalur Midtrans (QRIS pilihan
kedua, tombol Midtrans) maupun saat gerbang transfer sudah tertutup padahal order sudah punya
bukti; dan berkas bukti tidak pernah tersaji lewat rute baca mana pun. Data sintetis saja.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import pesanan_transfer  # noqa: E402
from bukti_kit import JPEG  # noqa: E402
from pesanan_transfer_http_kit import (  # noqa: E402
    AKUN_A, STATUS, berkas_tersimpan, dua_jalur, jam, keluarga, kirim_bukti, minta_mentah, server,
    siap_tagihan, teks_tampak, tertutup, transfer,
)

ALASAN = "Nominal kurang sintetis"
WAKTU_KEPUTUSAN = "2026-11-18T10:30:00"


def _order_id():
    with pesanan_transfer.buka(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT order_id FROM pesanan_order").fetchone()[0]


def _tolak_bukti():
    with pesanan_transfer.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        pesanan_transfer.tolak(kon, _order_id(), "admin_sintetis_a", ALASAN, WAKTU_KEPUTUSAN)


def _siap_menunggu(server):
    siap_tagihan(server)
    assert kirim_bukti(server, JPEG)[0] == 303


def _tanpa_tombol_midtrans(halaman):
    for rute in ("/pesanan/periksa", "/pesanan/ulang", "/pesanan/buat"):
        assert rute not in halaman


def test_dua_jalur_menunggu_verifikasi_tanpa_qris_dan_tanpa_tombol_midtrans(dua_jalur):
    _siap_menunggu(dua_jalur)
    kode, halaman, _t = minta_mentah(dua_jalur, STATUS, AKUN_A)
    assert kode == 200 and "Bukti diterima, menunggu pemeriksaan" in halaman
    assert "/pesanan/qr" not in halaman and "<form" not in teks_tampak(halaman)
    _tanpa_tombol_midtrans(halaman)


def test_dua_jalur_ditolak_menampilkan_alasan_unggah_ulang_tanpa_qris(dua_jalur):
    _siap_menunggu(dua_jalur)
    _tolak_bukti()
    kode, halaman, _t = minta_mentah(dua_jalur, STATUS, AKUN_A)
    assert kode == 200 and "Bukti belum sesuai" in halaman and ALASAN in halaman
    assert "Unggah ulang bukti" in halaman and "/pesanan/qr" not in halaman
    _tanpa_tombol_midtrans(halaman)


@pytest.mark.parametrize("keputusan", ["menunggu", "ditolak"])
def test_gerbang_transfer_tertutup_order_bersejarah_bukti_tetap_terbaca(dua_jalur, monkeypatch, keputusan):
    _siap_menunggu(dua_jalur)
    if keputusan == "ditolak":
        _tolak_bukti()
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "0")
    kode, halaman, _t = minta_mentah(dua_jalur, STATUS, AKUN_A)
    assert kode == 200 and "Traceback" not in halaman
    assert "Bukti diterima, menunggu pemeriksaan" in halaman or "Bukti belum sesuai" in halaman
    assert "Bayar lewat transfer" not in halaman and "<form" not in teks_tampak(halaman)


@pytest.mark.parametrize("jalur", ["/bukti-transfer/%s", "/lampiran/%s", "/murid/bukti/%s", "/pesanan/bukti/%s"])
def test_berkas_bukti_tidak_pernah_tersaji_lewat_rute_baca(transfer, jalur):
    _siap_menunggu(transfer)
    nama = berkas_tersimpan(transfer)[0]
    kode, isi, _t = minta_mentah(transfer, jalur % nama, AKUN_A)
    assert kode in (303, 404) and "\xff" not in isi and "JFIF" not in isi

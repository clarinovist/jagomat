"""Renderer murni purna di admin: `aksi_tersedia` (gerbang tunggal UI + token), kolom Laporan, kartu Detail order."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_detail_pages as dp  # noqa: E402
import admin_pesanan_pages as ui  # noqa: E402

ORDER = "ord_" + "a" * 32
TOKEN = ("csrf-sintetis", "tinjauan-sintetis")
FORMS = {"voucher": TOKEN, "refund": TOKEN, "periksa": TOKEN}


def _purna(**ganti):
    dasar = {"terpasang": True, "lunas": True, "voucher": "aktif", "kode": "JGV-AAAAAAAAAAAA",
             "berlaku_hingga": "2027-02-16T10:00:00", "janji_terbit": "2026-11-20T10:00:00",
             "batas_pilihan": "2026-11-23T10:00:00", "terbit": None, "terlambat": False,
             "dipakai": False, "direfund": False, "ditahan": False}
    return {**dasar, **ganti}


def _detail(status="sudah_dibayar", **purna):
    return {"order_id": ORDER, "akun": "akun_a1a1a1a1", "status": status, "dibuat": "2026-11-18T10:00:00",
            "kedaluwarsa": "2026-11-19T10:00:00", "cara": "qris", "nominal": None, "jumlah_bukti": 0,
            "langkah": ({"kode": "dibuat", "waktu": "2026-11-18T10:00:00", "jumlah": 0},),
            "purna": _purna(**purna)}


# --- aksi_tersedia ----------------------------------------------------------------------

@pytest.mark.parametrize("ganti,harap", [
    ({}, ("refund", "voucher")),
    ({"dipakai": True, "voucher": "dipakai"}, ()),
    ({"terbit": "2026-11-18T12:00:00"}, ("refund", "voucher")),
    ({"voucher": "kedaluwarsa"}, ("refund",)),
    ({"voucher": "batal", "direfund": True}, ("refund",)),
    ({"terpasang": False}, ("refund",)),
])
def test_aksi_tersedia_order_lunas_menurut_keadaan_purna(ganti, harap):
    assert ui.aksi_tersedia(_detail(**ganti), False) == harap


def test_aksi_tersedia_order_ditahan_hanya_refund_tanpa_voucher():
    item = _detail("perlu_diperiksa", ditahan=True, voucher="ditahan")
    assert ui.aksi_tersedia(item, False) == ("refund",)


def test_tidak_ada_aksi_terbit_admin_di_aksi_tersedia_apa_pun_keadaannya():
    assert not hasattr(ui, "AKSI_TERBIT") and not hasattr(ui, "RUTE_TERBIT")
    for ganti in ({}, {"terlambat": True}, {"ditahan": True}, {"terbit": "2026-11-18T12:00:00"}):
        assert "terbit" not in ui.aksi_tersedia(_detail(**ganti), True)


def test_aksi_tersedia_order_direfund_tanpa_voucher():
    assert ui.aksi_tersedia(_detail("direfund", voucher="batal", direfund=True), True) == ()


def test_aksi_tersedia_order_belum_lunas_tanpa_voucher():
    assert ui.aksi_tersedia(_detail("belum_bayar", lunas=False, voucher="belum_lunas"), True) == ("periksa",)


def test_aksi_tersedia_item_tanpa_kunci_purna_dianggap_belum_terpasang():
    item = {"status": "sudah_dibayar"}
    assert ui.aksi_tersedia(item, False) == ("refund",)


# --- teks kolom Laporan ---------------------------------------------------------------------

@pytest.mark.parametrize("ganti,harap", [
    ({"terpasang": False}, "—"),
    ({"lunas": False, "voucher": "belum_lunas", "janji_terbit": None}, "—"),
    ({}, "Janji 20 Nov 2026, 17.00 WIB"),
    ({"terlambat": True}, "Terlambat"),
    ({"terbit": "2026-11-19T10:00:00"}, "Terbit"),
    ({"direfund": True, "terlambat": True}, "—"),
    ({"direfund": True, "terbit": "2026-11-19T10:00:00"}, "Terbit"),
    ({"ditahan": True}, "Perlu diperiksa"),
    ({"ditahan": True, "terlambat": True}, "Perlu diperiksa"),
])
def test_teks_laporan_urutan_keutamaan(ganti, harap):
    assert ui.teks_laporan(_purna(**ganti)) == harap


def test_teks_laporan_tanpa_data_adalah_strip():
    assert ui.teks_laporan(None) == "—" and ui.teks_laporan({}) == "—"


def test_kolom_laporan_dirender_per_order_dan_default_strip():
    daftar = {"items": ({"order_id": ORDER, "akun": "akun_a1a1a1a1", "dibuat": "2026-11-18T10:00:00",
                         "alasan_kode": None, "status": "sudah_dibayar"},), "total": 1, "halaman": 1, "per_halaman": 25}
    kosong = ui.halaman(daftar, halaman=1, gerbang_terbuka=False, hasil=None)
    ada = ui.halaman(daftar, halaman=1, gerbang_terbuka=False, hasil=None, laporan={ORDER: _purna(terbit="2026-11-19T10:00:00")})
    assert "<td>—</td>" in kosong and "<td>Terbit</td>" in ada and "<th scope=\"col\">Laporan</th>" in ada


# --- kartu Detail order ---------------------------------------------------------------------

def test_kartu_purna_tanpa_token_tidak_ada_form_meski_aksi_tersedia():
    isi = dp.halaman(_detail(), gerbang_terbuka=False, forms={})
    assert "Voucher dan laporan" in isi and "<form" not in isi


def test_kartu_purna_dengan_token_memuat_form_voucher_dan_refund_tanpa_form_terbit():
    isi = dp.halaman(_detail(), gerbang_terbuka=False, forms=FORMS)
    assert isi.count('action="/admin/pesanan/voucher"') == 1 and 'action="/admin/pesanan/terbit"' not in isi


def test_kartu_purna_belum_terpasang_satu_baris_tanpa_form_walau_token_ada():
    isi = dp.halaman(_detail(terpasang=False), gerbang_terbuka=False, forms=FORMS)
    assert dp.COPY_PURNA_BELUM in isi and 'action="/admin/pesanan/voucher"' not in isi


def test_kartu_purna_item_tanpa_kunci_purna_dianggap_belum_terpasang():
    detail = {k: v for k, v in _detail().items() if k != "purna"}
    assert dp.COPY_PURNA_BELUM in dp.halaman(detail, gerbang_terbuka=False, forms=FORMS)


def test_kartu_purna_nilai_dinamis_di_escape():
    isi = dp.halaman(_detail(kode="<b>x</b>"), gerbang_terbuka=False, forms={})
    assert "<b>x</b>" not in isi and "&lt;b&gt;x&lt;/b&gt;" in isi


def test_form_refund_tidak_dirender_bila_voucher_dipakai_walau_token_refund_ada():
    isi = dp.halaman(_detail(dipakai=True, voucher="dipakai"), gerbang_terbuka=False, forms=FORMS)
    assert 'action="/admin/pesanan/refund"' not in isi and dp.COPY_REFUND_VOUCHER_DIPAKAI in isi


def test_enum_pemakaian_voucher_di_form_sama_dengan_skema():
    import schema_purna
    assert sorted(dp.URUTAN_ALASAN_VOUCHER) == sorted(schema_purna.CATATAN_PAKAI)
    assert set(dp.COPY_ALASAN_VOUCHER) == set(schema_purna.CATATAN_PAKAI)


# --- ditahan (H-1) dan terbit sesudah uang kembali (L-1) pada kartu Detail order -------------------

def _tanpa_tag(isi):
    import re
    return re.sub(r"<[^>]+>", " ", isi)


def test_kartu_order_ditahan_menampilkan_status_dan_catatan_tanpa_form_voucher():
    isi = dp.halaman(_detail("perlu_diperiksa", ditahan=True, voucher="ditahan"), gerbang_terbuka=False, forms=FORMS)
    assert dp.COPY_VOUCHER["ditahan"] == "Ditahan (pembayaran perlu diperiksa)"
    assert dp.COPY_VOUCHER["ditahan"] in isi and dp.COPY_DITAHAN in isi
    assert 'action="/admin/pesanan/voucher"' not in isi and 'action="/admin/pesanan/terbit"' not in isi
    assert 'action="/admin/pesanan/refund"' in isi          # refund tetap tersedia pada order ditahan


def test_kartu_order_normal_tanpa_catatan_ditahan():
    assert dp.COPY_DITAHAN not in dp.halaman(_detail(), gerbang_terbuka=False, forms=FORMS)


def test_kartu_terlambat_menampilkan_status_dan_tetap_menawarkan_refund_tanpa_form_terbit_atau_pilihan_keluarga():
    isi = dp.halaman(_detail(terlambat=True), gerbang_terbuka=False, forms=FORMS)
    assert "Terlambat sejak" in isi and 'action="/admin/pesanan/refund"' in isi
    assert 'action="/admin/pesanan/terbit"' not in isi
    for lama in ("Keluarga meminta uang kembali", "Minta uang kembali", "Pilihan keluarga"):
        assert lama not in isi
    assert not hasattr(dp, "COPY_PILIHAN") and not hasattr(dp, "COPY_MINTA_UANG_KEMBALI")
    assert not hasattr(ui, "COPY_LAPORAN_MINTA_KEMBALI")


def test_kartu_menampilkan_status_terbit_baca_saja_tanpa_copy_catat_terbit():
    sudah = dp.halaman(_detail(terbit="2026-11-19T10:00:00"), gerbang_terbuka=False, forms=FORMS)
    assert dp.COPY_LAPORAN_SUDAH in sudah and "Waktu terbit" in sudah
    belum = dp.halaman(_detail(), gerbang_terbuka=False, forms=FORMS)
    assert dp.COPY_LAPORAN_BELUM in belum and "Catat laporan terbit" not in belum
    for nama in ("COPY_TOMBOL_TERBIT", "COPY_PETUNJUK_TERBIT", "COPY_KONFIRMASI_TERBIT", "_form_terbit"):
        assert not hasattr(dp, nama)

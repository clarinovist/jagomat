"""Renderer murni halaman admin pesanan: aksi yang tersedia, escape, tanpa hex, penanda DRAF."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_pages as pg  # noqa: E402

ORDER = "ord_" + "a" * 32


def _item(**ganti):
    dasar = {"order_id": ORDER, "akun": "akun_a1a1a1a1", "dibuat": "2026-11-18T10:00:00",
             "kedaluwarsa": "2026-11-19T10:00:00", "alasan_kode": None, "status": "belum_bayar"}
    return {**dasar, **ganti}


def _daftar(*items, total=None):
    return {"items": tuple(items), "total": len(items) if total is None else total,
            "halaman": 1, "per_halaman": 25}


@pytest.mark.parametrize("status,gerbang,harap", [
    ("belum_bayar", True, ("periksa",)),
    ("kedaluwarsa", True, ("periksa",)),
    ("belum_bayar", False, ()),
    ("kedaluwarsa", False, ()),
    ("sudah_dibayar", True, ("refund",)),
    ("sudah_dibayar", False, ("refund",)),
    ("perlu_diperiksa", False, ("refund",)),
    ("direfund", True, ()),
])
def test_aksi_tersedia_menurut_status_dan_gerbang(status, gerbang, harap):
    assert pg.aksi_tersedia(_item(status=status), gerbang) == harap


def test_halaman_escape_semua_nilai_dinamis():
    item = _item(order_id="ord_<script>alert(1)</script>", akun='akun_"><b>', alasan_kode="<img src=x>")
    isi = pg.halaman(_daftar(item), halaman=1, gerbang_terbuka=True, forms={}, hasil=None)
    assert "<script>alert" not in isi and "<img src=x>" not in isi and "<b>" not in isi
    assert "&lt;script&gt;" in isi


def test_halaman_tanpa_forms_tidak_menampilkan_form_aksi():
    isi = pg.halaman(_daftar(_item()), halaman=1, gerbang_terbuka=True, forms={}, hasil=None)
    assert "<form" not in isi


def test_halaman_umpan_balik_hanya_dari_kode_dikenal():
    isi = pg.halaman(_daftar(), halaman=1, gerbang_terbuka=False, forms={}, hasil="refund_dicatat")
    assert pg.COPY_HASIL["refund_dicatat"] in isi
    assert pg.halaman(_daftar(), halaman=1, gerbang_terbuka=False, forms={}, hasil=None).count("role=\"status\"") == 0


def test_tidak_ada_hex_warna_di_renderer():
    sumber = (Path(__file__).resolve().parent.parent / "admin_pesanan_pages.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber)


def test_tidak_ada_penanda_draf_di_sumber_renderer():
    sumber = (Path(__file__).resolve().parent.parent / "admin_pesanan_pages.py").read_text(encoding="utf-8")
    assert not re.search(r"\bDRAF\b|menunggu persetujuan Pemilik", sumber)


def test_halaman_terender_tanpa_penanda_draf():
    isi = pg.halaman(_daftar(_item()), halaman=1, gerbang_terbuka=True, forms={}, hasil="refund_dicatat")
    assert "draf" not in isi.lower() and "draf" not in pg.halaman_tidak_siap().lower()


def _item_transfer(**ganti):
    return _item(status="menunggu_verifikasi", **ganti)


RINGKAS = {ORDER: {"nominal": 49321, "jumlah_bukti": 2, "diunggah": "2026-11-18T12:30:00"}}


def test_baris_transfer_memuat_nominal_persis_jumlah_bukti_waktu_dan_tautan_periksa():
    isi = pg.halaman(_daftar(_item_transfer()), halaman=1, gerbang_terbuka=False, forms={}, hasil=None,
                     transfer=RINGKAS)
    assert "Rp49.321" in isi and "2 · 18 Nov 2026, 19.30 WIB" in isi
    assert "Menunggu verifikasi" in isi
    assert 'href="/admin/pesanan/verifikasi?order=%s"' % ORDER in isi and pg.COPY_PERIKSA_BUKTI in isi


def test_tautan_bukti_berlabel_lihat_untuk_status_lain_dan_hilang_tanpa_bukti():
    lunas = pg.halaman(_daftar(_item(status="sudah_dibayar")), halaman=1, gerbang_terbuka=False, forms={},
                       hasil=None, transfer=RINGKAS)
    assert pg.COPY_LIHAT_BUKTI in lunas and pg.COPY_PERIKSA_BUKTI not in lunas
    tanpa = pg.halaman(_daftar(_item_transfer()), halaman=1, gerbang_terbuka=False, forms={}, hasil=None,
                       transfer={ORDER: {"nominal": 49321, "jumlah_bukti": 0, "diunggah": None}})
    assert "/verifikasi?" not in tanpa and "Rp49.321" in tanpa


def test_tab_menandai_aktif_dan_pager_mempertahankan_filter():
    daftar = _daftar(_item_transfer(), total=60)
    isi = pg.halaman(daftar, halaman=2, gerbang_terbuka=False, forms={}, hasil=None, saring="menunggu")
    assert 'href="/admin/pesanan?status=menunggu" aria-current="page"' in isi
    pager = isi.split("admin-pager")[1]
    assert "status=menunggu&amp;halaman=1" in pager or "halaman=1&amp;status=menunggu" in pager
    semua = pg.halaman(daftar, halaman=2, gerbang_terbuka=False, forms={}, hasil=None)
    assert 'href="/admin/pesanan" aria-current="page"' in semua and "status=menunggu&amp;halaman" not in semua.split("admin-pager")[1]


def test_kosong_tab_menunggu_memakai_pesan_sendiri():
    isi = pg.halaman(_daftar(), halaman=1, gerbang_terbuka=False, forms={}, hasil=None, saring="menunggu")
    assert pg.COPY_KOSONG_MENUNGGU in isi and pg.COPY_KOSONG not in isi


def test_kode_hasil_verifikasi_dikenal_dan_label_status_baru_ada():
    assert {"verifikasi_setuju", "verifikasi_tolak"} <= pg.KODE_HASIL
    assert pg.COPY_STATUS["menunggu_verifikasi"] and pg.COPY_STATUS["ditolak"]

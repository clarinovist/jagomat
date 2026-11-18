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


def test_setiap_konstanta_copy_diawali_penanda_draf():
    baris = (Path(__file__).resolve().parent.parent / "admin_pesanan_pages.py").read_text(encoding="utf-8").splitlines()
    copy = [i for i, b in enumerate(baris) if re.match(r"COPY_[A-Z_]+ = ", b)]
    assert copy
    for i in copy:
        assert baris[i - 1].strip() == "# DRAF: teks final menunggu persetujuan Pemilik", baris[i]

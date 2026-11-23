"""Renderer murni Detail order admin: bagian tindakan, escape, tanpa hex/draf, enum refund utuh."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_detail_pages as dp  # noqa: E402
import admin_pesanan_pages as ui  # noqa: E402
from schema_pesanan import CATATAN_REFUND  # noqa: E402

ORDER = "ord_" + "a" * 32
TOKEN = ("csrf-sintetis", "tinjauan-sintetis")
FORMS = {"periksa": TOKEN, "refund": TOKEN}


def _detail(**ganti):
    dasar = {"order_id": ORDER, "akun": "akun_a1a1a1a1", "status": "belum_bayar", "dibuat": "2026-11-18T10:00:00",
             "kedaluwarsa": "2026-11-19T10:00:00", "cara": "qris", "nominal": None, "jumlah_bukti": 0,
             "langkah": ({"kode": "dibuat", "waktu": "2026-11-18T10:00:00", "jumlah": 0},)}
    return {**dasar, **ganti}


def _render(detail=None, **ganti):
    return dp.halaman(detail or _detail(), **{"gerbang_terbuka": True, "forms": FORMS, **ganti})


def test_urutan_alasan_refund_adalah_permutasi_enum_server_dan_kebijakan_pertama():
    assert sorted(dp.URUTAN_ALASAN_REFUND) == sorted(CATATAN_REFUND)
    assert dp.URUTAN_ALASAN_REFUND[0] == "kebijakan" and set(dp.COPY_ALASAN_REFUND) == set(CATATAN_REFUND)


def test_langkah_dan_cara_punya_label_untuk_semua_kode_domain():
    import pesanan_admin_order as po
    kode = {v for k, v in vars(po).items() if k.startswith("LANGKAH_")}
    assert kode <= set(dp.COPY_LANGKAH)
    assert {po.CARA_TRANSFER, po.CARA_QRIS} <= set(dp.COPY_CARA)


@pytest.mark.parametrize("status,periksa,refund", [
    ("belum_bayar", True, False), ("kedaluwarsa", True, False), ("sudah_dibayar", False, True),
    ("perlu_diperiksa", False, True), ("menunggu_verifikasi", False, False), ("ditolak", False, False),
    ("direfund", False, False),
])
def test_form_tampil_hanya_untuk_status_yang_diizinkan(status, periksa, refund):
    isi = _render(_detail(status=status))
    assert ('action="/admin/pesanan/periksa"' in isi) is periksa
    assert ('action="/admin/pesanan/refund"' in isi) is refund
    assert (dp.COPY_RINGKAS_REFUND in isi) is refund


def test_tanpa_token_tidak_ada_form_meski_aksi_tersedia():
    isi = _render(_detail(status="sudah_dibayar"), forms={})
    assert "<form" not in isi and dp.COPY_KEBIJAKAN_REFUND in isi
    assert "<form" not in _render(_detail(status="belum_bayar"), forms={})


def test_gerbang_tertutup_menyembunyikan_form_periksa_dengan_penjelasan():
    isi = _render(gerbang_terbuka=False)
    assert "<form" not in isi and dp.COPY_PERIKSA_GERBANG in isi


def test_hasil_diluar_allowlist_detail_tidak_ditampilkan():
    assert ui.COPY_HASIL["refund_dicatat"] in _render(hasil="refund_dicatat")
    assert 'role="status"' not in _render(hasil="verifikasi_setuju")
    assert 'role="status"' not in _render(hasil="sembarang")


def test_escape_nilai_dinamis():
    isi = _render(_detail(order_id="ord_<script>x</script>", akun='"><img src=x>'))
    assert "<script>x" not in isi and "<img src=x>" not in isi and "&lt;script&gt;" in isi


def test_nominal_tiga_digit_unik_disorot_dan_kosong_bertanda_strip():
    assert '<mark class="admin-digit-unik">321</mark>' in _render(_detail(nominal=49321))
    assert "<strong>—</strong>" in _render(_detail(nominal=None))


def test_langkah_banyak_bukti_menyebut_jumlah_berkas():
    langkah = ({"kode": "bukti", "waktu": "2026-11-18T12:00:00", "jumlah": 3},)
    assert "(3 berkas)" in _render(_detail(langkah=langkah, jumlah_bukti=3))
    langkah = ({"kode": "bukti", "waktu": "2026-11-18T12:00:00", "jumlah": 1},)
    assert "berkas)" not in _render(_detail(langkah=langkah, jumlah_bukti=1))


def test_tombol_refund_gaya_bahaya_garis_dan_konfirmasi_menyebut_tak_dapat_dibatalkan():
    isi = _render(_detail(status="sudah_dibayar"))
    assert re.search(r'<button class="admin-tombol admin-bahaya-garis" type="submit">Catat uang kembali</button>', isi)
    assert "tidak dapat dibatalkan" in isi


def test_penanda_dua_jalur_tampil_hanya_bila_dua_jalur():
    assert dp.COPY_DUA_JALUR in _render(_detail(status="perlu_diperiksa", dua_jalur=True))
    assert dp.COPY_DUA_JALUR not in _render(_detail(status="perlu_diperiksa", dua_jalur=False))
    assert dp.COPY_DUA_JALUR not in _render()                       # fixture lama tanpa kunci: tanpa penanda


def test_peringatan_bukti_dipakai_ulang_menyebut_jumlah_order_lain_saja():
    isi = _render(_detail(status="menunggu_verifikasi", bukti_dipakai_ulang=3))
    assert "muncul di 3 order lain" in isi and "mutasi bank" in isi
    assert "muncul di" not in _render(_detail(bukti_dipakai_ulang=0))
    assert "muncul di" not in _render()


def test_peringatan_tanpa_form_dan_tanpa_hex_atau_id_order_lain():
    isi = _render(_detail(status="perlu_diperiksa", dua_jalur=True, bukti_dipakai_ulang=2))
    assert 'role="note"' in isi and isi.count('role="note"') == 2
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", isi.replace("&#", ""))

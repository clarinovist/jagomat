"""Render murni halaman Harga admin (admin_harga_pages): escape, baca-saja, tanpa form saat skema belum, teks tegas.

Tanpa I/O dan tanpa DB. Data SINTETIS.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_harga_baca as baca  # noqa: E402
import admin_harga_pages as ui  # noqa: E402
import harga  # noqa: E402
import harga_aturan  # noqa: E402

TOKEN = ("csrf-sintetis", "tinjauan-sintetis")


def _produk(diubah=""):
    return (
        baca.BarisProduk("private", "Private", 640_000, True, diubah, 591_000),
        baca.BarisProduk("mini", "Mini Class", 300_000, True, "", 251_000),
        baca.BarisProduk("peta", "Peta Kemampuan", 49_000, False),
    )


def _tampilan(*, terpasang=True, produk=None, riwayat=()):
    return baca.Tampilan(
        terpasang=terpasang, produk=produk or _produk(), riwayat=riwayat,
        harian=(baca.BarisHarian("bulanan", "Bulanan", 39_000), baca.BarisHarian("tahunan", "Tahunan", 349_000)))


def _tokens():
    return {"private": TOKEN, "mini": TOKEN}


def test_halaman_memuat_produk_harian_dan_teks_tagihan_baru():
    isi = ui.halaman(_tampilan(), _tokens(), None)
    for teks in ("Private", "Mini Class", "Peta Kemampuan", "Bulanan", "Tahunan", "Belum bisa diatur", "Rp640.000",
                 "Rp591.000", "Rp251.000", "Rp49.000", "nilai awal", ui.COPY_TAGIHAN_BARU):
        assert teks in isi, teks


def test_form_hanya_untuk_produk_yang_boleh_diubah_dan_field_kode_terikat():
    isi = ui.halaman(_tampilan(), _tokens(), None)
    assert isi.count('name="harga_baru"') == 2
    assert 'name="kode" value="private"' in isi and 'name="kode" value="mini"' in isi
    assert 'value="peta"' not in isi and 'value="harian"' not in isi


def test_input_harga_teks_numerik_bukan_type_number_dengan_pola_dari_konstanta():
    isi = ui.halaman(_tampilan(), _tokens(), None)
    assert 'type="number"' not in isi and 'inputmode="numeric"' in isi
    assert 'pattern="%s"' % ui.pola_isian_harga() in isi


def test_pola_dan_rentang_tampil_dari_konstanta_harga_aturan(monkeypatch):
    monkeypatch.setattr(harga_aturan, "HARGA_MAKS", 12_345_678)
    monkeypatch.setattr(harga_aturan, "KELIPATAN", 500)
    assert ui.pola_isian_harga() == "[0-9]{1,8}"
    isi = ui.halaman(_tampilan(), _tokens(), None)
    assert "Rp12.345.678" in isi and "Rp500" in isi


def test_tanpa_tokens_tampil_baca_saja_tanpa_form():
    isi = ui.halaman(_tampilan(), None, None)
    assert ui.COPY_TANPA_SESI in isi and "<form" not in isi and 'name="harga_baru"' not in isi


def test_skema_belum_terpasang_tanpa_form_dan_catatan_belum_dipasang():
    isi = ui.halaman(_tampilan(terpasang=False), None, None)
    assert ui.COPY_BELUM_DIPASANG in isi and "<form" not in isi and 'name="harga_baru"' not in isi


def test_sumber_diubah_admin_menampilkan_waktu():
    produk = (baca.BarisProduk("private", "Private", 700_000, True, "2026-11-25T08:00:00", 651_000),) + _produk()[1:]
    isi = ui.halaman(_tampilan(produk=produk), _tokens(), None)
    assert "diubah admin" in isi and "2026-11-25T08:00:00" in isi


def test_riwayat_tampil_sesuai_urutan_masukan_dan_nilai_dinamis_di_escape():
    riwayat = (
        harga.RiwayatHarga(2, "mini", 300_000, 320_000, "<img src=x>", "2026-11-25T09:00:00"),
        harga.RiwayatHarga(1, "private", None, 700_000, "admin-sintetis", "2026-11-25T08:00:00"),
    )
    isi = ui.halaman(_tampilan(riwayat=riwayat), _tokens(), None)
    assert "&lt;img src=x&gt;" in isi and "<img src=x>" not in isi
    assert isi.index("2026-11-25T09:00:00") < isi.index("2026-11-25T08:00:00")


def test_hasil_hanya_dari_kode_dikenal():
    assert 'role="status"' in ui.halaman(_tampilan(), _tokens(), "tersimpan")
    assert 'role="status"' not in ui.halaman(_tampilan(), _tokens(), "sembarang")


def test_galat_isian_di_escape_sekali():
    isi = ui.galat_isian("<b>x</b>")
    assert "&lt;b&gt;x&lt;/b&gt;" in isi and "<b>x</b>" not in isi


def test_galat_belum_dipasang_dan_layanan_tanpa_detail_internal():
    assert ui.COPY_BELUM_DIPASANG in ui.galat_belum_dipasang()
    galat = ui.galat_layanan()
    assert "Tidak ada yang diubah" in galat
    assert "sqlite" not in galat.lower() and "harga_riwayat" not in galat


def test_tautan_pengaturan_menunjuk_rute_harga():
    assert 'href="%s"' % ui.RUTE in ui.tautan_pengaturan()

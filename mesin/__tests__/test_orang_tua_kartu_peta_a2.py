"""Kartu Peta di halaman orang tua (F1, Usulan A + A2): kartu gelap sebelum bayar dan blok setelah lunas.

Data sintetis; murni render (`_blok_pesanan`, `halaman_isi`) kecuali tes baca harga dan nominal yang memakai
monkeypatch atau SQLite memori. Tanpa jaringan dan tanpa DB admin nyata.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import replace

import admin_store_core
import funnel_pages
import harga
import orang_tua_data
import orang_tua_http
import orang_tua_pages as halaman
import pesanan_pages
import purna
from orang_tua_data import DataOrangTua
from pesanan_murid_kit import KEADAAN_TERLAMBAT
from pesanan_transfer_pages import rupiah

HARGA = {"private": 640000, "mini": 300000}
KEADAAN_AKTIF = replace(KEADAAN_TERLAMBAT, terbit=None, voucher=purna.VOUCHER_AKTIF)
KEADAAN_KEDALUWARSA = replace(KEADAAN_TERLAMBAT, terbit=None, voucher=purna.VOUCHER_KEDALUWARSA)
RUTE_BAYAR = "/murid/pesanan"
RUTE_PAKET = "/murid/paket"
RUTE_LANGGANAN = "/murid/langganan"
STATUS_BUTUH_BAYAR = (pesanan_pages.STATUS_BELUM_BAYAR, pesanan_pages.STATUS_KEDALUWARSA, pesanan_pages.STATUS_DITOLAK)
STATUS_TANPA_BAYAR_LAGI = (pesanan_pages.STATUS_MENUNGGU_VERIFIKASI, pesanan_pages.STATUS_PERLU_DIPERIKSA,
                           pesanan_pages.STATUS_DIREFUND)


def _sebelum_bayar(**kwargs) -> str:
    return halaman._blok_pesanan(None, True, **kwargs)


def _lunas(*, purna_=KEADAAN_AKTIF, terbit=True, **kwargs) -> str:
    return halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True, purna_, terbit, **kwargs)


# --- Sebelum bayar: kartu gelap ---------------------------------------------------------------

def test_sebelum_bayar_menampilkan_harga_dan_satu_tombol_utama_ke_pesanan():
    html = _sebelum_bayar()
    assert 'id="ortu-pesanan"' in html and "Peta Kemampuan" in html
    assert "Rp49.000" in html and "sekali bayar" in html
    assert "Bukan langganan. Tidak ada tagihan bulan depan." in html
    assert f'href="{RUTE_BAYAR}">Buka Peta Kemampuan · Rp49.000</a>' in html
    assert html.count('class="ceria-tombol"') == 1


def test_sebelum_bayar_tanpa_form_button_atau_input():
    html = _sebelum_bayar(tautan_paket=True, tautan_langganan=True, harga_kelas=HARGA)
    assert "<form" not in html and "<button" not in html and "<input" not in html


def test_sebelum_bayar_memuat_kalimat_resmi_tidak_dapat_dikembalikan_harfiah_dari_funnel():
    kalimat = "Laporan langsung terbit setelah pembayaran terverifikasi, jadi pembayaran tidak dapat dikembalikan."
    assert funnel_pages.COPY_PEMBATALAN_BUTIR[0][0].strip() == kalimat
    assert kalimat in _sebelum_bayar()


def test_sebelum_bayar_tanpa_tautan_sekunder_bila_paket_dan_langganan_mati():
    html = _sebelum_bayar(tautan_paket=False, tautan_langganan=False, harga_kelas=HARGA)
    assert "Lihat kelas" not in html and "Langganan" not in html and f'href="{RUTE_PAKET}"' not in html


def test_sebelum_bayar_menautkan_lihat_kelas_dan_langganan_bila_aktif():
    html = _sebelum_bayar(tautan_paket=True, tautan_langganan=True, harga_kelas=HARGA)
    assert f'href="{RUTE_PAKET}">Lihat kelas</a>' in html
    assert f'href="{RUTE_LANGGANAN}">Langganan</a>' in html


def test_status_butuh_bayar_memakai_kartu_gelap_dengan_lencana_status_tanpa_kalimat_qris():
    for status in STATUS_BUTUH_BAYAR:
        html = halaman._blok_pesanan(status, True)
        assert "Buka Peta Kemampuan · Rp49.000" in html, status
        assert pesanan_pages.COPY_STATUS[status][0] in html, status
        assert "QRIS" not in html, status


def test_status_tanpa_bayar_lagi_tetap_kartu_status_tanpa_tawaran_beli():
    for status in STATUS_TANPA_BAYAR_LAGI:
        html = halaman._blok_pesanan(status, True)
        assert "Buka Peta Kemampuan" not in html and "Rp49.000" not in html, status
        assert "Lihat status pembayaran" in html and html.count("<a ") == 1, status


# --- Setelah lunas: A2 ------------------------------------------------------------------------

def test_lunas_terbit_menampilkan_chip_dan_jangkar_ke_blok_peta():
    html = _lunas(terbit=True)
    assert "Lunas · laporan terbit" in html
    assert 'href="#ortu-peta">Buka laporan lengkap</a>' in html


def test_lunas_belum_terbit_tanpa_chip_dan_tanpa_jangkar_ke_peta():
    html = _lunas(purna_=KEADAAN_AKTIF, terbit=False)
    assert "Lunas · laporan terbit" not in html and "#ortu-peta" not in html
    assert "Pembayaran diterima. Laporan sedang disiapkan." in html


def test_lunas_dengan_nominal_menampilkan_potongan_sesuai_nominal_bukan_konstanta():
    html = _lunas(tautan_paket=True, harga_kelas=HARGA, nominal_bayar=55000)
    assert "Potongan deposit Peta Rp55.000 untuk tagihan bulan pertama" in html
    assert "Rp49.000" not in html


def test_lunas_nominal_tidak_terbaca_tanpa_kalimat_potongan_tetapi_pilihan_kelas_tetap():
    html = _lunas(tautan_paket=True, harga_kelas=HARGA, nominal_bayar=None)
    assert "Potongan deposit" not in html
    assert "Daftar kelas" in html


def test_lunas_voucher_tidak_aktif_atau_purna_belum_terbaca_tanpa_kalimat_potongan():
    kedaluwarsa = _lunas(purna_=KEADAAN_KEDALUWARSA, tautan_paket=True, harga_kelas=HARGA, nominal_bayar=49000)
    tanpa_purna = _lunas(purna_=None, tautan_paket=True, harga_kelas=HARGA, nominal_bayar=49000)
    assert "Potongan deposit" not in kedaluwarsa and "Potongan deposit" not in tanpa_purna


def test_lunas_tanpa_tautan_paket_tanpa_pilihan_kelas_tetapi_chip_dan_laporan_tetap():
    html = _lunas(tautan_paket=False, harga_kelas=HARGA, nominal_bayar=49000)
    assert "Lunas · laporan terbit" in html and "Buka laporan lengkap" in html
    assert f'href="{RUTE_PAKET}"' not in html and "Daftar kelas" not in html
    assert "Private" not in html and "Potongan deposit" not in html


def test_pilihan_kelas_berupa_tautan_ke_paket_dengan_harga_dari_harga_kelas():
    html = _lunas(tautan_paket=True, harga_kelas=HARGA, nominal_bayar=49000)
    assert f'<a class="ortu-opsi-kelas-st" href="{RUTE_PAKET}"><b>Private</b>' in html
    assert f'<a class="ortu-opsi-kelas-st" href="{RUTE_PAKET}"><b>Mini Class</b>' in html
    assert rupiah(640000) in html and rupiah(300000) in html
    assert html.count(f'href="{RUTE_PAKET}"') == 3  # dua opsi + satu tombol Daftar kelas


def test_pilihan_kelas_tanpa_form_button_dan_tanpa_kata_terlarang():
    html = _lunas(tautan_paket=True, harga_kelas=HARGA, nominal_bayar=49000)
    assert "<form" not in html and "<button" not in html
    assert "pilih" not in html and "Guru" not in html and "48 jam" not in html


def test_pilihan_kelas_galat_harga_tampil_tanpa_angka():
    html = _lunas(tautan_paket=True, harga_kelas={"private": None, "mini": None}, nominal_bayar=49000)
    assert "<b>Private</b>" in html and "<b>Mini Class</b>" in html
    assert rupiah(640000) not in html and rupiah(300000) not in html


def test_halaman_isi_meneruskan_nominal_bayar_dari_data_ke_kartu():
    data = DataOrangTua("Anak Sintetis", {"status": "belum_mulai"}, None, pesanan_pages.STATUS_SUDAH_DIBAYAR,
                        purna=KEADAAN_AKTIF, nominal_bayar=55000)
    html = halaman.halaman_isi(data, False, tautan_paket=True, harga_kelas=HARGA).decode()
    assert "Potongan deposit Peta Rp55.000 untuk tagihan bulan pertama" in html


# --- Pembacaan data: nominal dan harga (tanpa DB admin nyata) ---------------------------------

def _pesanan_minimal(baris) -> sqlite3.Connection:
    kon = sqlite3.connect(":memory:")
    kon.row_factory = sqlite3.Row
    kon.execute("CREATE TABLE pesanan_order (order_id TEXT, akun_id TEXT, siswa_id INTEGER, rupiah INTEGER)")
    kon.executemany("INSERT INTO pesanan_order VALUES (?, ?, ?, ?)", baris)
    return kon


def test_rupiah_order_membaca_nominal_milik_akun_dan_anak_itu_saja():
    kon = _pesanan_minimal([("o1", "akun-a", 1, 49000), ("o2", "akun-b", 1, 55000)])
    try:
        assert orang_tua_data._rupiah_order(kon, "akun-a", 1) == 49000
        assert orang_tua_data._rupiah_order(kon, "akun-b", 1) == 55000
        assert orang_tua_data._rupiah_order(kon, "akun-a", 2) is None
    finally:
        kon.close()


def test_nominal_lunas_tanpa_status_sudah_dibayar_tidak_membaca_apa_pun():
    assert orang_tua_data.nominal_lunas("akun-a", 1, pesanan_pages.STATUS_BELUM_BAYAR) is None


def test_galat_baca_harga_kelas_menghasilkan_none_per_produk(monkeypatch):
    def rusak(*_args, **_kwargs):
        raise admin_store_core.StoreBelumSiap("belum dipasang")

    monkeypatch.setattr(orang_tua_http.admin_store, "buka_baca", rusak)
    assert orang_tua_http._harga_kelas() == {"private": None, "mini": None}


def test_harga_kelas_memetakan_harga_aktif_private_dan_mini(monkeypatch):
    @contextmanager
    def kon_palsu(*_args, **_kwargs):
        yield object()

    monkeypatch.setattr(orang_tua_http.admin_store, "buka_baca", kon_palsu)
    monkeypatch.setattr(harga, "harga_aktif", lambda _kon, kode: HARGA[kode])
    assert orang_tua_http._harga_kelas() == HARGA

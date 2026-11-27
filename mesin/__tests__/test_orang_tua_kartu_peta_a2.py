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
import harian_langganan_ringkas
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
    html = _sebelum_bayar(tautan_paket=True, harga_kelas=HARGA)
    assert "<form" not in html and "<button" not in html and "<input" not in html


def test_sebelum_bayar_memuat_kalimat_resmi_tidak_dapat_dikembalikan_harfiah_dari_funnel():
    kalimat = "Laporan langsung terbit setelah pembayaran terverifikasi, jadi pembayaran tidak dapat dikembalikan."
    assert funnel_pages.COPY_PEMBATALAN_BUTIR[0][0].strip() == kalimat
    assert kalimat in _sebelum_bayar()


def test_sebelum_bayar_tanpa_tautan_kelas_atau_langganan_walau_paket_dan_langganan_aktif():
    # Satu pintu per kartu: kelas dan langganan dibuka lewat kartu yang sudah ada di halaman, bukan dari kartu gelap.
    html = _sebelum_bayar(tautan_paket=True, harga_kelas=HARGA)
    assert "Lihat kelas" not in html and "Langganan" not in html
    assert f'href="{RUTE_PAKET}"' not in html and f'href="{RUTE_LANGGANAN}"' not in html


def test_status_butuh_bayar_memakai_kartu_gelap_dengan_lencana_status_tanpa_kalimat_qris():
    for status in STATUS_BUTUH_BAYAR:
        html = halaman._blok_pesanan(status, True)
        assert "Buka Peta Kemampuan · Rp49.000" in html, status
        assert pesanan_pages.COPY_STATUS[status][0] in html, status
        assert "QRIS" not in html, status


def test_kedaluwarsa_dan_ditolak_menampilkan_kalimat_status_di_kartu_gelap():
    for status in (pesanan_pages.STATUS_KEDALUWARSA, pesanan_pages.STATUS_DITOLAK):
        html = halaman._blok_pesanan(status, True)
        assert pesanan_pages.COPY_STATUS[status][1] in html, status


def test_belum_bayar_tanpa_kalimat_status_karena_kalimatnya_memuat_qris():
    html = halaman._blok_pesanan(pesanan_pages.STATUS_BELUM_BAYAR, True)
    assert pesanan_pages.COPY_STATUS[pesanan_pages.STATUS_BELUM_BAYAR][1] not in html


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


def test_pilihan_kelas_berupa_informasi_dengan_harga_dan_satu_pintu_daftar_kelas():
    html = _lunas(tautan_paket=True, harga_kelas=HARGA, nominal_bayar=49000)
    assert '<div class="ortu-opsi-kelas-st"><b>Private</b>' in html
    assert '<div class="ortu-opsi-kelas-st"><b>Mini Class</b>' in html
    assert html.count('class="ortu-opsi-kelas-st"') == 2 and '<a class="ortu-opsi-kelas-st"' not in html
    assert rupiah(640000) in html and rupiah(300000) in html
    assert html.count(f'href="{RUTE_PAKET}"') == 1  # satu-satunya pintu kelas: tombol Daftar kelas


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


# --- halaman penuh: satu pintu kelas, tanpa kartu kelas ganda ---------------------------------

LANGGANAN = harian_langganan_ringkas.Ringkasan("langganan", "2026-12-23T03:00:00", 2, None)


def _kartu_pesanan_dari(html: str) -> str:
    awal = html.index('id="ortu-pesanan"')
    return html[awal:html.index("</section>", awal)]


def test_halaman_penuh_lunas_dengan_paket_hanya_satu_pintu_kelas_tanpa_kartu_kelas_ganda():
    data = DataOrangTua("Anak Sintetis", {"status": "belum_mulai"}, None, pesanan_pages.STATUS_SUDAH_DIBAYAR,
                        langganan=LANGGANAN, purna=KEADAAN_AKTIF, nominal_bayar=49000)
    html = halaman.halaman_isi(data, False, tautan_paket=True, harga_kelas=HARGA).decode()
    assert _kartu_pesanan_dari(html).count(f'href="{RUTE_PAKET}"') == 1
    assert html.count(f'href="{RUTE_PAKET}"') == 1
    assert 'id="ortu-paket"' not in html  # kartu kelas lama tidak tampil ganda di samping blok kelas Peta


def test_halaman_penuh_belum_bayar_tanpa_tautan_kelas_atau_langganan_di_kartu_pesanan():
    data = DataOrangTua("Anak Sintetis", {"status": "belum_mulai"}, None, pesanan_pages.STATUS_BELUM_BAYAR,
                        langganan=LANGGANAN)
    html = halaman.halaman_isi(data, False, tautan_paket=True, harga_kelas=HARGA).decode()
    kartu = _kartu_pesanan_dari(html)
    assert "Buka Peta Kemampuan · Rp49.000" in kartu
    assert f'href="{RUTE_PAKET}"' not in kartu and f'href="{RUTE_LANGGANAN}"' not in kartu
    assert 'id="ortu-paket"' in html  # belum lunas: kartu kelas lama tetap menjadi pintu kelas

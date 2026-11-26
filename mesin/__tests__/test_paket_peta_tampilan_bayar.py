"""Font dan angka bayar murid: Paket Belajar (`lg-`), Latihan Harian, dan Peta (scoped, token global tetap).

Murni render (data sintetis). Token `design_tokens` dibiarkan; penyesuaian hanya di CSS `lg-` dan kelas
`pesanan-nominal` yang hanya dimuat di halaman murid.
"""
import re

import pytest

import design_tokens as T
import harian_langganan_style as lg
import kelas_pages as kelas
import pesanan_dasar as d
import pesanan_pages as peta
import pesanan_permukaan
import pesanan_rekening
import pesanan_transfer_pages as tp
import pesanan_transfer_tampil as tt
from cek_pages import _e
from funnel_pages import COPY_HARGA

MURID = ("akun-uji", pesanan_permukaan.PERAN_MURID)
GURU = ("akun-uji", "guru")
NOMINAL_PAKET = "Rp49.000"
SOROT_PAKET = f'<strong class="pesanan-nominal">{NOMINAL_PAKET}</strong>'
TAMPILAN_BAYAR = {"status": d.STATUS_BELUM_BAYAR, "nama_anak": "Anak Sintetis", "qr": False, "aksi": None,
                  "boleh_ulang": False, "belum_terperiksa": False}
REKENING = pesanan_rekening.RekeningPublik("Bank Contoh", "1234567890", "1234 5678 90", "PT Contoh Sintetis")


def _aturan(css, selektor):
    cocok = re.search(re.escape(selektor) + r" \{([^}]*)\}", css)
    assert cocok, f"aturan {selektor} tidak ditemukan"
    return cocok.group(1)


def _token(aksi):
    return "tok-" + aksi


def _transfer(status, nominal=49321):
    return tt.TampilanTransfer(status=status, nominal=nominal, kedaluwarsa="2026-11-19T10:00:00",
                               alasan_tolak=None, jumlah_bukti=0, boleh_tagihan=False, boleh_unggah=True)


# --- CSS lg- (Paket Belajar & Latihan Harian) -----------------------------------------------

def test_lg_kecil_naik_ke_ukuran_badan_layar():
    assert f"font-size: {T.UKURAN_BADAN_LAYAR}" in _aturan(lg.GAYA_LANGGANAN_HARIAN, ".lg-kecil")


def test_lg_ket_naik_ke_095rem():
    assert "font-size: .95rem" in _aturan(lg.GAYA_LANGGANAN_HARIAN, ".lg-ket")


def test_lg_harga_memakai_ukuran_angka_dewasa():
    assert f"800 {T.UKURAN_ANGKA_DEWASA}/1.2" in _aturan(lg.GAYA_LANGGANAN_HARIAN, ".lg-harga")


def test_lg_nominal_tetap_tebal():
    assert "font: 800 " in _aturan(lg.GAYA_LANGGANAN_HARIAN, ".lg-nominal")


def test_token_global_ukuran_teks_tidak_berubah():
    assert T.UKURAN_TEKS_LABEL == ".875rem"
    assert T.UKURAN_TEKS_BANTUAN == ".9rem"
    assert T.UKURAN_BADAN_LAYAR == "16px"


def test_gaya_lg_hanya_dimuat_di_halaman_paket_dan_latihan():
    assert ".lg-kecil {" in kelas.halaman_info("Judul", "Teks").decode()
    assert ".lg-kecil {" not in peta.halaman_info(MURID, "Judul", "Teks").decode()


# --- Peta murid: penekanan nominal (scoped ke murid) ----------------------------------------

def test_gaya_pesanan_nominal_hanya_dimuat_di_halaman_peta_murid():
    assert ".pesanan-nominal {" in peta.halaman_info(MURID, "Judul", "Teks").decode()
    assert ".pesanan-nominal {" not in peta.halaman_info(GURU, "Judul", "Teks").decode()


def test_harga_paket_di_halaman_bayar_murid_ditebalkan_teks_tetap():
    # Arrange / Act
    html = peta.halaman_status(MURID, TAMPILAN_BAYAR, "tok").decode()

    # Assert
    assert SOROT_PAKET in html
    assert _e(COPY_HARGA) in html.replace(SOROT_PAKET, NOMINAL_PAKET)


def test_kartu_pesan_murid_menebalkan_nominal_paket():
    html = peta.halaman_belum_memesan(MURID, "tok").decode()
    assert f"{SOROT_PAKET}, sekali bayar" in html


def test_harga_paket_halaman_guru_tanpa_penekanan():
    html = peta.halaman_status(GURU, TAMPILAN_BAYAR, "tok").decode()
    assert "pesanan-nominal" not in html


def test_total_transfer_murid_ditebalkan_dan_guru_tidak():
    # Arrange
    tampilan = _transfer(d.STATUS_BELUM_BAYAR)

    # Act
    murid = tp.blok_transfer(tampilan, REKENING, _token, pesanan_permukaan.RUTE_MURID)
    guru = tp.blok_transfer(tampilan, REKENING, _token, pesanan_permukaan.RUTE_GURU)

    # Assert
    assert '<strong class="pesanan-nominal">Rp49.321</strong>' in murid
    assert "pesanan-nominal" not in guru
    assert "<strong>Rp49.321</strong>" in guru


@pytest.mark.parametrize("status", [d.STATUS_DITOLAK, d.STATUS_MENUNGGU_VERIFIKASI])
def test_total_transfer_murid_ditebalkan_di_status_lain(status):
    tampilan = _transfer(status)
    murid = tp.blok_transfer(tampilan, REKENING, _token, pesanan_permukaan.RUTE_MURID)
    assert '<strong class="pesanan-nominal">Rp49.321</strong>' in murid

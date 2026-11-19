"""Renderer blok transfer + kamus status (tanpa DB/HTTP): nominal persis, escape, tanpa KeyError."""
from __future__ import annotations

import pytest

import pesanan_dasar as d
import pesanan_pages as halaman
import pesanan_rekening
import pesanan_transfer_pages as tp
import pesanan_transfer_tampil as tt
from pesanan_http_kit import teks_tampak

REKENING = pesanan_rekening.RekeningPublik("Bank Contoh", "1234567890", "1234 5678 90", "PT Contoh Sintetis")
IDENT = ("guru", "guru")


def _t(status=d.STATUS_BELUM_BAYAR, **ganti):
    dasar = dict(status=status, nominal=None, kedaluwarsa="2026-11-19T10:00:00", alasan_tolak=None,
                 jumlah_bukti=0, boleh_tagihan=False, boleh_unggah=False)
    dasar.update(ganti)
    return tt.TampilanTransfer(**dasar)


def _token(aksi):
    return "tok-" + aksi


def _tampilan(status, **ganti):
    dasar = {"status": status, "nama_anak": "Anak Sintetis", "qr": False, "aksi": None,
             "boleh_ulang": False, "belum_terperiksa": False}
    dasar.update(ganti)
    return dasar


def test_rupiah_memakai_titik_ribuan():
    assert tp.rupiah(49123) == "Rp49.123"
    assert tp.rupiah(49000) == "Rp49.000"


def test_waktu_wib_dari_utc_naif():
    assert tp.waktu_wib("2026-11-19T10:00:00") == "19 November 2026 pukul 17.00 WIB"
    assert tp.waktu_wib("2026-12-31T20:30:00") == "1 Januari 2027 pukul 03.30 WIB"


@pytest.mark.parametrize("status", d.STATUS_TURUNAN)
def test_kamus_status_punya_semua_status_turunan(status):
    judul, kalimat = halaman.COPY_STATUS[status]
    assert judul and kalimat


@pytest.mark.parametrize("status", d.STATUS_TURUNAN)
def test_halaman_status_tidak_keyerror_untuk_semua_status(status):
    isi = halaman.halaman_status(IDENT, _tampilan(status), None).decode()
    assert halaman.COPY_STATUS[status][0] in isi


def test_teks_status_baru_sesuai_permintaan():
    assert halaman.COPY_STATUS[d.STATUS_MENUNGGU_VERIFIKASI][0] == "Bukti diterima, menunggu pemeriksaan"
    assert halaman.COPY_STATUS[d.STATUS_DITOLAK][0] == "Bukti belum sesuai"


def test_belum_ada_tagihan_hanya_tombol_buat_tagihan_tanpa_rekening():
    isi = tp.blok_transfer(_t(boleh_tagihan=True), REKENING, _token)
    assert "Bayar lewat transfer" in isi and 'action="/pesanan/tagihan"' in isi
    assert 'value="tok-tagihan"' in isi
    assert "1234" not in isi and "PT Contoh" not in isi and "multipart" not in isi


def test_tagihan_menampilkan_rekening_nominal_persis_batas_waktu_dan_form_unggah():
    isi = tp.blok_transfer(_t(nominal=49321, boleh_unggah=True), REKENING, _token)
    teks = teks_tampak(isi)
    for harus in ("Bank Contoh", "1234 5678 90", "PT Contoh Sintetis", "Rp49.321", "19 November 2026 pukul 17.00 WIB"):
        assert harus in teks
    assert "persis" in teks.lower()
    assert 'action="/pesanan/bukti"' in isi and 'enctype="multipart/form-data"' in isi
    assert 'name="berkas"' in isi and 'name="token" value="tok-bukti"' in isi
    assert isi.count("Rp49.321") >= 1 and "Rp49.000" not in teks


def test_ditolak_menampilkan_alasan_ter_escape_dan_unggah_ulang():
    isi = tp.blok_transfer(
        _t(d.STATUS_DITOLAK, nominal=49100, alasan_tolak="Nominal <b>kurang</b> & salah", boleh_unggah=True),
        REKENING, _token)
    assert "&lt;b&gt;kurang&lt;/b&gt; &amp; salah" in isi and "<b>kurang</b>" not in isi
    assert "Unggah ulang" in isi and 'action="/pesanan/bukti"' in isi


def test_menunggu_verifikasi_tanpa_form_apa_pun():
    isi = tp.blok_transfer(_t(d.STATUS_MENUNGGU_VERIFIKASI, nominal=49100, jumlah_bukti=1), REKENING, _token)
    assert "<form" not in isi and "Rp49.100" in isi


def test_batas_bukti_tercapai_dijelaskan_tanpa_form():
    isi = tp.blok_transfer(_t(d.STATUS_DITOLAK, nominal=49100, jumlah_bukti=5, alasan_tolak="x"),
                           REKENING, _token)
    assert "<form" not in isi and "5" in teks_tampak(isi)


@pytest.mark.parametrize("status", [d.STATUS_SUDAH_DIBAYAR, d.STATUS_KEDALUWARSA, d.STATUS_DIREFUND,
                                    d.STATUS_PERLU_DIPERIKSA])
def test_status_lain_tidak_memunculkan_blok(status):
    assert tp.blok_transfer(_t(status, nominal=49100), REKENING, _token) == ""


def test_halaman_status_menyisipkan_blok_transfer_sebelum_qris():
    tampilan = _tampilan(d.STATUS_BELUM_BAYAR, qr=True, qris=True,
                         blok_transfer='<div class="kartu-st"><h2>Bayar lewat transfer</h2></div>')
    isi = halaman.halaman_status(IDENT, tampilan, None).decode()
    assert isi.index("Bayar lewat transfer") < isi.index('src="/pesanan/qr"')
    assert "Pilihan kedua" in isi


def test_hanya_transfer_tanpa_gambar_qr_dan_tanpa_kalimat_qris():
    tampilan = _tampilan(d.STATUS_BELUM_BAYAR, qris=False,
                         blok_transfer='<div class="kartu-st"><h2>Bayar lewat transfer</h2></div>')
    isi = halaman.halaman_status(IDENT, tampilan, None).decode()
    assert "/pesanan/qr" not in isi and "QRIS" not in isi and "Kode QR belum tersedia" not in isi


def test_tanpa_transfer_halaman_midtrans_tidak_berubah():
    isi = halaman.halaman_status(IDENT, _tampilan(d.STATUS_BELUM_BAYAR, qr=True), None).decode()
    assert "Pindai kode QRIS" in isi and "Pilihan kedua" not in isi and "transfer" not in isi.lower()

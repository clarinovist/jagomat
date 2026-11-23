"""Kartu Peta Kemampuan di halaman orang tua: satu pintu ke pembayaran akun anak (F2c)."""
import orang_tua_pages as halaman
import pesanan_pages
import pesanan_permukaan


def test_tanpa_pesanan_dan_cek_selesai_menawarkan_lanjut_ke_pembayaran():
    # Arrange / Act
    html = halaman._blok_pesanan(None, True)
    # Assert
    assert 'href="%s"' % pesanan_permukaan.RUTE_MURID.status in html
    assert "Lanjut ke pembayaran" in html


def test_tanpa_pesanan_dan_cek_belum_selesai_kartu_tidak_tampil():
    assert halaman._blok_pesanan(None, False) == ""


def test_belum_bayar_tidak_mengulang_instruksi_qris_dan_menautkan_pembayaran():
    status = next(s for s in pesanan_pages.COPY_STATUS if s != pesanan_pages.STATUS_SUDAH_DIBAYAR)
    html = halaman._blok_pesanan(status, True)
    assert "QRIS" not in html
    assert pesanan_permukaan.RUTE_MURID.status in html


def test_sudah_dibayar_menampilkan_status_tanpa_tombol_bayar():
    html = halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True)
    assert "Pembayaran diterima" in html
    assert pesanan_permukaan.RUTE_MURID.status not in html

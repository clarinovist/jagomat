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


def test_sudah_dibayar_dengan_purna_menambah_satu_baris_janji_dan_tautan_deposit_tanpa_form():
    # Arrange
    import pesanan_voucher_pages as hv
    from dataclasses import replace
    from pesanan_murid_kit import KEADAAN_TERLAMBAT as DASAR
    # Act
    html = halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True, DASAR)
    # Assert
    assert hv.teks_janji(DASAR) in html and html.count(hv.COPY_JANJI) == 1
    assert "<button" not in html and "<form" not in html and "pilih" not in html
    assert f'href="{pesanan_permukaan.RUTE_MURID.status}"' in html
    assert "Lihat deposit &amp; rincian pesanan" in html
    assert "Akses laporan lengkap menyusul" in html

    terbit = halaman._blok_pesanan(
        pesanan_pages.STATUS_SUDAH_DIBAYAR, True, replace(DASAR, terbit="2026-11-19T10:00:00", terlambat=False))
    assert halaman.COPY_PESANAN_TERBIT in terbit
    assert "Akses laporan lengkap menyusul" not in terbit
    assert f'href="{pesanan_permukaan.RUTE_MURID.status}"' in terbit


def test_belum_dibayar_dengan_purna_tidak_menambah_baris_janji():
    from pesanan_murid_kit import KEADAAN_TERLAMBAT as DASAR
    status = next(s for s in pesanan_pages.COPY_STATUS if s != pesanan_pages.STATUS_SUDAH_DIBAYAR)
    assert "dijanjikan" not in halaman._blok_pesanan(status, True, DASAR)


def test_sudah_dibayar_tanpa_purna_tetap_seperti_semula():
    html = halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True, None)
    assert "dijanjikan" not in html


def test_sudah_dibayar_menampilkan_status_tanpa_tombol_bayar():
    html = halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True)
    assert "Pembayaran diterima" in html
    assert pesanan_permukaan.RUTE_MURID.status not in html

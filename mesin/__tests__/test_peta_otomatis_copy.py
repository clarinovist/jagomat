"""Copy Peta otomatis (26 Nov 2026): laporan terbit tanpa Guru, tanpa janji 48 jam, refund sesuai keputusan Pemilik.

Data sintetis saja. Tiap teks yang berubah dicek: (a) tidak memuat kata "Guru" pada bagian yang berubah,
(b) tidak memuat "48 jam", (c) memuat kalimat baru yang diputuskan Pemilik PERSIS.
"""
import dataclasses

import admin_antrean
import cek_pages
import funnel_landing_pages
import funnel_pages
import peta_contoh_data
import peta_lembar
import pesanan_pages

KALIMAT_REFUND = "Laporan langsung terbit setelah pembayaran terverifikasi, jadi pembayaran tidak dapat dikembalikan."
HASIL_SINTETIS = {"status": "selesai", "skor": 72, "kategori": "Cukup baik",
                  "ringkasan": {"kuat": ["Pola bilangan"], "perlu": ["Statistika"]}, "jumlah_soal": 15}


def _tanpa_guru(teks: str) -> None:
    assert "guru" not in teks.lower(), teks


def _tanpa_48_jam(teks: str) -> None:
    assert "48 jam" not in teks, teks


def test_refund_pesanan_memuat_kalimat_disetujui_tanpa_guru_dan_48_jam():
    # Arrange: teks refund dari modul pesanan (dipakai halaman status dan kartu refund)
    teks = pesanan_pages.COPY_REFUND

    # Act
    html = pesanan_pages._catatan_refund()

    # Assert
    assert KALIMAT_REFUND in teks and KALIMAT_REFUND in html
    _tanpa_48_jam(teks)
    _tanpa_guru(teks)


def test_status_sudah_dibayar_memakai_kalimat_laporan_disiapkan():
    # Arrange
    judul, kalimat = pesanan_pages.COPY_STATUS[pesanan_pages.STATUS_SUDAH_DIBAYAR]

    # Act / Assert
    assert kalimat == "Pembayaran diterima. Laporan sedang disiapkan."
    _tanpa_guru(kalimat)
    _tanpa_48_jam(kalimat)
    assert "Perkiraan terbit" not in kalimat and judul == "Pembayaran diterima"


def test_pembatalan_paket_memuat_kalimat_disetujui_dan_halaman_tanpa_48_jam():
    # Arrange
    butir_refund = funnel_pages.COPY_PEMBATALAN_BUTIR[0]
    butir_laporan = funnel_pages.COPY_PEMBATALAN_BUTIR[2]

    # Act
    html = funnel_pages.halaman_paket_coba().decode()

    # Assert
    assert funnel_pages.COPY_TIDAK_KEMBALI.startswith(KALIMAT_REFUND)
    assert KALIMAT_REFUND in funnel_pages.COPY_PEMBATALAN and KALIMAT_REFUND in html
    assert "karena Guru langsung" not in funnel_pages.COPY_PEMBATALAN
    assert "karena Guru langsung" not in html
    for teks in (butir_refund[0] + butir_refund[1], butir_laporan[0] + butir_laporan[1], funnel_pages.COPY_PEMBATALAN):
        _tanpa_48_jam(teks)
    _tanpa_48_jam(html)


def test_pengantar_dan_isi_paket_tidak_mengklaim_guru_menulis_laporan():
    # Arrange
    isi_laporan = funnel_pages.COPY_PAKET_ISI[0]

    # Act
    html = funnel_pages.halaman_paket_coba().decode()

    # Assert
    for teks in (funnel_pages.COPY_PENGANTAR_PAKET, isi_laporan):
        assert "menulis laporannya" not in teks and "Guru kami membaca" not in teks
        assert "ditinjau Guru" not in teks and "catatan dari Guru" not in teks.lower()
    assert "menulis laporannya" not in html and "Guru kami membaca" not in html


def test_landing_cek_kemampuan_tanpa_frasa_guru_dan_48_jam_lama():
    # Arrange
    frasa_lama = ("Ditinjau Guru Jagomat", "dibaca Guru", "belum ditinjau Guru", "catatan dari Guru",
                  "karena Guru langsung", "Contoh cara Guru Jagomat", "Guru langsung", "48 jam")

    # Act
    html = funnel_landing_pages.isi_cek_kemampuan()

    # Assert
    for frasa in frasa_lama:
        assert frasa not in html, frasa
    assert KALIMAT_REFUND in html


def test_label_gratis_sama_dengan_label_cek_dan_tanpa_guru():
    # Arrange / Act
    label = cek_pages.COPY_LABEL_GAMBARAN
    gratis = funnel_landing_pages.COPY_GRATIS_CATATAN

    # Assert
    assert label == "Gambaran awal · hasil otomatis"
    assert label in gratis
    _tanpa_guru(label)
    _tanpa_guru(gratis)


def test_copy_cek_gratis_tanpa_kata_guru():
    # Arrange
    teks = list(cek_pages.COPY_NOTICE) + list(cek_pages.COPY_KUNCI_BUTIR) + [cek_pages.COPY_KUNCI_CATATAN]

    # Act
    html = cek_pages.halaman_hasil(("guru", "guru"), HASIL_SINTETIS, "Anak Sintetis", "123.tok").decode()

    # Assert
    for kalimat in teks:
        _tanpa_guru(kalimat)
    assert "Di langkah mana salahnya" in cek_pages.COPY_KUNCI_BUTIR
    assert "belum ditinjau" not in html


def test_lembar_tanpa_guru_paraf_dan_kolom_tinjauan():
    # Arrange
    tinjau = peta_contoh_data.DATA_CONTOH
    belum = dataclasses.replace(tinjau, ditinjau=False, catatan_guru="")

    # Act
    isi_belum = peta_lembar.render_lembar(belum, contoh=True)
    isi_tinjau = peta_lembar.render_lembar(tinjau, contoh=True)

    # Assert
    for isi in (isi_belum, isi_tinjau):
        assert "Temuan Guru" not in isi and "peta-l-paraf-st" not in isi and "Ditinjau oleh" not in isi
        _tanpa_48_jam(isi)
    _tanpa_guru(isi_belum)
    assert "Temuan: di langkah mana salahnya" in isi_belum
    assert "Ringkasan satu halaman dari cek matematika." in isi_belum


def test_antrean_admin_peta_tidak_menyuruh_guru_menyusun():
    # Arrange
    kalimat = admin_antrean.KALIMAT_PETA_BELUM_TERBIT

    # Act / Assert
    _tanpa_guru(kalimat)
    _tanpa_48_jam(kalimat)
    assert "batas tunggu" not in kalimat
    assert kalimat == "Laporan belum terbit otomatis; periksa bahan cek atau terbitkan manual."

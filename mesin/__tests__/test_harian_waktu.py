"""Hari kalender WIB (UTC+7 tetap) untuk batas harian Latihan Harian; epoch literal, tanpa jam sistem."""
import harian_waktu as w

T0 = 1_800_000_000  # 2027-01-15 08:00:00 UTC = 15:00 WIB (Jumat)


def test_awal_hari_wib_adalah_tengah_malam_wib():
    assert w.awal_hari_wib(T0) == T0 - 15 * 3600
    assert w.awal_hari_wib(T0 - 15 * 3600) == T0 - 15 * 3600
    assert w.awal_hari_wib(T0 - 15 * 3600 - 1) == T0 - 15 * 3600 - 86400


def test_batas_hari_wib_setengah_terbuka():
    awal, akhir = w.batas_hari_wib(T0)

    assert akhir - awal == 86400 and awal <= T0 < akhir
    assert w.batas_hari_wib(akhir)[0] == akhir


def test_tanggal_wib_berbeda_dari_tanggal_utc_setelah_17_utc():
    assert w.tanggal_wib(T0) == "2027-01-15"
    assert w.tanggal_wib(T0 + 9 * 3600 - 1) == "2027-01-15"  # 23:59:59 WIB
    assert w.tanggal_wib(T0 + 9 * 3600) == "2027-01-16"  # 00:00:00 WIB = 17:00 UTC


def test_kini_baku_utc():
    assert w.kini_baku(T0) == "2027-01-15T08:00:00"


def test_tujuh_hari_hingga_terlama_dulu():
    hari = w.tujuh_hari_hingga(T0)

    assert hari == ("2027-01-09", "2027-01-10", "2027-01-11", "2027-01-12", "2027-01-13", "2027-01-14", "2027-01-15")


def test_pekan_wib_senin_sampai_minggu():
    assert w.pekan_wib(T0) == ("2027-01-11", "2027-01-12", "2027-01-13", "2027-01-14", "2027-01-15", "2027-01-16",
                               "2027-01-17")  # 2027-01-15 hari Jumat
    assert w.pekan_wib(T0 + 9 * 3600)[0] == "2027-01-11"  # Sabtu 00:00 WIB masih pekan yang sama

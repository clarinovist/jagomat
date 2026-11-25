"""Aturan harga admin (konstanta dan nominal turunan), tanpa DB dan tanpa jaringan.

Modul daun: dipakai bersama `schema_harga` (batas CHECK) dan `harga`/`harga_validasi` (aturan domain),
supaya batas rentang dan kelipatan hanya didefinisikan sekali. Namanya sengaja tanpa kata schema/store/
migrat/database.

Keputusan Pemilik (25 Nov 2026): Private disimpan per BULAN (Rp640.000; per pertemuan 1/8 hanya informasi),
Mini Rp300.000 per bulan (8 pertemuan), Peta Rp49.000 hanya-baca. Rentang yang boleh disimpan admin:
Rp10.000..Rp9.000.000, kelipatan Rp1.000. Harga Latihan Harian TIDAK di sini (konstanta modul sendiri).
"""
import pesanan_dasar as d
import schema_transfer as st

PERTEMUAN_PER_BULAN = 8
# Target keputusan Pemilik: Mini boleh masuk sampai pertemuan ke-3 mulai, sisa minimal 5 pertemuan.
# Belum sama dengan jadwal_store.TUTUP_SETELAH_PERTEMUAN_MULAI (= 2 saat ini, sisa minimal 6); jangan diubah
# di sini tanpa menyelaraskan jadwal_store, dan tidak ada tes drift untuk konstanta ini.
SISA_PERTEMUAN_MIN = 5
HARGA_MIN = 10_000
HARGA_MAKS = 9_000_000
KELIPATAN = 1_000
BATAS_OLEH = 100
KODE_PRODUK = ("private", "mini", "peta")
ALLOW_UBAH = ("private", "mini")

KODE_MIN = st.KODE_MIN
KODE_MAKS = st.KODE_MAKS
BATAS_RUPIAH = st.BATAS_RUPIAH
RUPIAH_DEPOSIT = d.RUPIAH_PAKET  # sama dengan paket_belajar_katalog.RUPIAH_DEPOSIT (dijaga tes drift)


def nominal_proporsional(harga_bulanan, sisa):
    """Nominal untuk `sisa` pertemuan dari harga satu bulan, dibulatkan ke rupiah terdekat (setengah naik).

    Aritmetika bilangan bulat: (harga * sisa + 4) // 8 untuk 8 pertemuan. Menolak sisa di luar
    [SISA_PERTEMUAN_MIN, PERTEMUAN_PER_BULAN].
    """
    if type(sisa) is not int or not SISA_PERTEMUAN_MIN <= sisa <= PERTEMUAN_PER_BULAN:
        raise ValueError("sisa pertemuan harus bilangan bulat %d sampai %d" % (SISA_PERTEMUAN_MIN, PERTEMUAN_PER_BULAN))
    return (harga_bulanan * sisa + PERTEMUAN_PER_BULAN // 2) // PERTEMUAN_PER_BULAN

"""Validator perubahan harga admin: aturan murni (tanpa DB) terhadap harga produk lain.

Setiap aturan adalah fungsi sendiri supaya punya tes dan pesan galat sendiri:
(a) bilangan bulat asli, (b) rentang, (c) kelipatan, (d) Peta hanya-baca, (e) nominal positif setelah deposit,
(f) pita nominal lintas produk tak beririsan, (g) batas atas bersama kode unik.

Pita: nominal n menjadi total transfer n + kode unik (KODE_MIN..KODE_MAKS), jadi pita [n+1, n+999]. Dua pita
beririsan bila selisih nominal <= 998 (KODE_MAKS - KODE_MIN). Tes katalog (test_paket_belajar_katalog) menuntut
selisih > KODE_MAKS (999) untuk SEMUA pasangan nominal, jadi satu aturan itu dipakai untuk semua pasangan:
selisih harus lebih dari KODE_MAKS. Batas ini satu rupiah lebih ketat daripada batas irisan pita murni
(999 tidak beririsan secara matematis, tetapi ditolak katalog).
"""
import harian_langganan_dasar as harian
from harga_aturan import (
    ALLOW_UBAH, BATAS_RUPIAH, HARGA_MAKS, HARGA_MIN, KELIPATAN, KODE_MAKS, KODE_PRODUK, PERTEMUAN_PER_BULAN,
    RUPIAH_DEPOSIT, SISA_PERTEMUAN_MIN, nominal_proporsional,
)


def periksa_kode_produk(kode):
    if type(kode) is not str or kode not in KODE_PRODUK:
        raise ValueError("kode produk harga tidak dikenal")


def periksa_bisa_diubah(kode):
    if kode not in ALLOW_UBAH:
        raise ValueError("Peta belum bisa diatur; harga Peta hanya-baca")


def periksa_tipe(rupiah):
    if type(rupiah) is not int:
        raise ValueError("harga harus bilangan bulat rupiah")


def periksa_rentang(rupiah):
    if not HARGA_MIN <= rupiah <= HARGA_MAKS:
        raise ValueError("harga di luar rentang %d sampai %d rupiah" % (HARGA_MIN, HARGA_MAKS))


def periksa_kelipatan(rupiah):
    if rupiah % KELIPATAN != 0:
        raise ValueError("harga harus kelipatan %d rupiah" % KELIPATAN)


def harga_kandidat(kode, rupiah, harga_lain):
    """Harga semua produk dengan nilai kandidat untuk `kode`; nilai lama `kode` di harga_lain diabaikan."""
    hilang = [p for p in KODE_PRODUK if p != kode and p not in harga_lain]
    if hilang:
        raise ValueError("harga produk lain tidak lengkap: %s" % ", ".join(hilang))
    return {p: rupiah if p == kode else harga_lain[p] for p in KODE_PRODUK}


def periksa_nominal_positif(harga):
    """Nominal setelah potongan deposit Peta harus positif; Mini diperiksa pada sisa minimum (terkecil)."""
    if harga["private"] - RUPIAH_DEPOSIT <= 0:
        raise ValueError("nominal Private setelah potongan deposit harus positif")
    minimum_mini = nominal_proporsional(harga["mini"], SISA_PERTEMUAN_MIN)
    if minimum_mini - RUPIAH_DEPOSIT <= 0:
        raise ValueError("nominal Mini Class setelah potongan deposit harus positif")


def _entri_kelas(harga):
    private, mini = harga["private"], harga["mini"]
    entri = [("kelas", "Private", private), ("kelas", "Private, potongan deposit", private - RUPIAH_DEPOSIT)]
    for sisa in range(SISA_PERTEMUAN_MIN, PERTEMUAN_PER_BULAN + 1):
        nominal = nominal_proporsional(mini, sisa)
        entri.append(("kelas", "Mini Class %d pertemuan" % sisa, nominal))
        entri.append(("kelas", "Mini Class %d pertemuan, potongan deposit" % sisa, nominal - RUPIAH_DEPOSIT))
    return entri


def _entri_harian():
    return [("harian", paket.nama, paket.rupiah) for paket in harian.PAKET.values()]


def nominal_per_modul(harga):
    """Semua nominal dasar (sebelum kode unik) per modul: kelas, peta, dan harian."""
    peta = [("peta", "Peta", harga["peta"])]
    return _entri_kelas(harga) + peta + _entri_harian()


def periksa_pita(entri):
    """Tolak dua nominal lintas atau dalam modul yang selisihnya <= KODE_MAKS (lihat docstring modul)."""
    urut = sorted(entri, key=lambda e: e[2])
    for (modul_a, label_a, nilai_a), (modul_b, label_b, nilai_b) in zip(urut, urut[1:]):
        selisih = nilai_b - nilai_a
        if selisih <= KODE_MAKS:
            raise ValueError(
                "nominal %s (%s) %d dan %s (%s) %d beririsan pada kode unik: selisih harus lebih dari %d rupiah"
                % (modul_a, label_a, nilai_a, modul_b, label_b, nilai_b, KODE_MAKS))


def periksa_batas_atas(entri):
    tertinggi = max(nilai for _, _, nilai in entri)
    if tertinggi + KODE_MAKS > BATAS_RUPIAH:
        raise ValueError("nominal tertinggi ditambah kode unik melewati batas %d rupiah" % BATAS_RUPIAH)


def validasi_harga(kode, rupiah, harga_lain):
    """Lolos (None) atau ValueError berbahasa Indonesia. harga_lain: harga aktif produk lain."""
    periksa_kode_produk(kode)
    periksa_bisa_diubah(kode)
    periksa_tipe(rupiah)
    periksa_rentang(rupiah)
    periksa_kelipatan(rupiah)
    harga = harga_kandidat(kode, rupiah, harga_lain)
    periksa_nominal_positif(harga)
    entri = nominal_per_modul(harga)
    periksa_pita(entri)
    periksa_batas_atas(entri)

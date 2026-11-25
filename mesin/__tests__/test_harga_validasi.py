"""Validator harga admin: tiap aturan (a)-(g) punya tes dengan pesan galat sendiri.

Input tiap tes dipilih agar hanya aturan itu yang menolak (dicek dengan menghitung, bukan menebak); pesan
diasertsi dengan match supaya aturan lain yang kebetulan menolak tidak lolos diam-diam.
"""
import pytest

import harga
import harga_validasi as hv

LAIN_PRIVATE = {"mini": 300_000, "peta": 49_000}
LAIN_MINI = {"private": 640_000, "peta": 49_000}


def test_harga_awal_setiap_produk_lolos_validator():
    awal = harga.HARGA_AWAL
    assert hv.validasi_harga("private", awal["private"], {"mini": awal["mini"], "peta": awal["peta"]}) is None
    assert hv.validasi_harga("mini", awal["mini"], {"private": awal["private"], "peta": awal["peta"]}) is None


def test_kode_tak_dikenal_ditolak():
    with pytest.raises(ValueError, match="kode produk"):
        hv.validasi_harga("harian", 39_000, LAIN_PRIVATE)


@pytest.mark.parametrize("rupiah", [49_000, 50_000])
def test_peta_hanya_baca_berapa_pun_nilainya(rupiah):
    with pytest.raises(ValueError, match="Peta belum bisa diatur"):
        hv.validasi_harga("peta", rupiah, {"private": 640_000, "mini": 300_000})


@pytest.mark.parametrize("rupiah", [True, 640_000.0, "640000"])
def test_harga_harus_bilangan_bulat_asli(rupiah):
    with pytest.raises(ValueError, match="bilangan bulat"):
        hv.validasi_harga("private", rupiah, LAIN_PRIVATE)


def test_rentang_batas_bawah_dan_atas_pada_aturan_murni():
    hv.periksa_rentang(10_000)
    hv.periksa_rentang(9_000_000)
    with pytest.raises(ValueError, match="rentang"):
        hv.periksa_rentang(9_999)
    with pytest.raises(ValueError, match="rentang"):
        hv.periksa_rentang(9_001_000)


def test_rentang_maksimum_ditolak_lewat_validator():
    with pytest.raises(ValueError, match="rentang"):
        hv.validasi_harga("private", 9_001_000, LAIN_PRIVATE)


def test_kelipatan_aturan_murni():
    hv.periksa_kelipatan(640_000)
    with pytest.raises(ValueError, match="kelipatan"):
        hv.periksa_kelipatan(640_500)


def test_kelipatan_ditolak_lewat_validator_tanpa_konflik_pita():
    with pytest.raises(ValueError, match="kelipatan"):
        hv.validasi_harga("mini", 310_500, LAIN_MINI)


def test_nominal_positif_setelah_deposit_aturan_murni():
    dasar = {"private": 49_001, "mini": 300_000, "peta": 49_000}
    hv.periksa_nominal_positif(dasar)
    with pytest.raises(ValueError, match="positif"):
        hv.periksa_nominal_positif({**dasar, "private": 49_000})
    with pytest.raises(ValueError, match="positif"):
        hv.periksa_nominal_positif({**dasar, "mini": 78_000})


def test_nominal_positif_ditolak_lewat_validator_mini_kecil():
    with pytest.raises(ValueError, match="positif"):
        hv.validasi_harga("mini", 70_000, LAIN_MINI)


def test_nominal_positif_private_ditolak_lewat_validator_tanpa_bentrok_pita():
    with pytest.raises(ValueError, match="positif"):
        hv.validasi_harga("private", 40_000, LAIN_PRIVATE)


def test_pita_selisih_998_dan_999_ditolak_selisih_1000_lolos_aturan_murni():
    with pytest.raises(ValueError, match="beririsan"):
        hv.periksa_pita([("kelas", "a", 1_000), ("harian", "b", 1_998)])
    with pytest.raises(ValueError, match="beririsan"):
        hv.periksa_pita([("kelas", "a", 1_000), ("harian", "b", 1_999)])
    with pytest.raises(ValueError, match="beririsan"):
        hv.periksa_pita([("kelas", "a", 1_000), ("kelas", "b", 1_999)])
    hv.periksa_pita([("kelas", "a", 1_000), ("harian", "b", 2_000)])


def test_pita_beririsan_selisih_875_ditolak_dan_menyebut_modul():
    with pytest.raises(ValueError, match="beririsan") as galat:
        hv.validasi_harga("mini", 557_000, LAIN_MINI)
    assert "kelas" in str(galat.value) and "harian" in str(galat.value)


def test_pita_selisih_1000_lolos_lewat_validator():
    assert hv.validasi_harga("mini", 560_000, LAIN_MINI) is None


def test_pita_memakai_kandidat_bukan_harga_basi_di_harga_lain():
    basi = {"private": 640_000, "peta": 49_000, "mini": 300_000}
    with pytest.raises(ValueError, match="beririsan"):
        hv.validasi_harga("mini", 557_000, basi)


def test_deposit_private_sama_dengan_harian_tahunan_ditolak():
    with pytest.raises(ValueError, match="beririsan"):
        hv.validasi_harga("private", 398_000, LAIN_PRIVATE)


def test_batas_atas_aturan_murni_dengan_kode_unik():
    hv.periksa_batas_atas([("kelas", "a", 9_999_000)])
    with pytest.raises(ValueError, match="batas"):
        hv.periksa_batas_atas([("kelas", "a", 9_999_500)])


def test_harga_lain_wajib_lengkap():
    with pytest.raises(ValueError, match="tidak lengkap"):
        hv.validasi_harga("private", 640_000, {"peta": 49_000})


def test_himpunan_nominal_harga_awal_sesuai_turunan():
    entri = hv.nominal_per_modul(dict(harga.HARGA_AWAL))
    assert {nominal for _, _, nominal in entri} == {
        640_000, 591_000, 187_500, 138_500, 225_000, 176_000, 262_500, 213_500,
        300_000, 251_000, 49_000, 39_000, 349_000,
    }

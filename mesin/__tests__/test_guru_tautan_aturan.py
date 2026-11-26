"""Aturan murni tautan kode anak guru: kode, normalisasi, status turunan, batas waktu, dan batas guru/kode (data sintetis)."""

import hashlib
import re
from datetime import timedelta

import pytest

import guru_tautan_aturan as A

ALFABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
POLA_TAMPIL = re.compile(r"[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}")
POLA_HASH = re.compile(r"[0-9a-f]{64}")
KODE_CONTOH = "ABCDEFGHJKMNPQRS"
TAMPIL_CONTOH = "ABCD-EFGH-JKMN-PQRS"
KODE_LAMA = "ABCDEFGHJKMN"
TAMPIL_LAMA = "ABCD-EFGH-JKMN"
DIBUAT = "2026-11-10T10:00:00"
KEDALUWARSA = "2026-11-17T10:00:00"
PADA_TOLAK = "2026-11-10T10:00:00"


# --- konstanta --------------------------------------------------------------------------

def test_konstanta_sesuai_rancangan_batas_dan_status():
    assert A.KEDALUWARSA == timedelta(days=7)
    assert A.JEDA_TOLAK == timedelta(days=7)
    assert A.GAGAL_PER_GURU == 5
    assert A.JENDELA_GURU == timedelta(hours=1)
    assert A.PERMINTAAN_PER_KODE == 10
    assert A.JENDELA_KODE == timedelta(days=1)
    assert A.GAGAL_PER_IP == 20
    assert A.JENDELA_IP_DETIK == 3600
    assert A.PANJANG_KODE == 16
    assert A.ALFABET == ALFABET
    assert (A.STATUS_MENUNGGU, A.STATUS_SETUJU, A.STATUS_TOLAK, A.STATUS_KEDALUWARSA, A.STATUS_BATAL) == (
        "menunggu", "setuju", "tolak", "kedaluwarsa", "batal",
    )
    assert (A.PERAN_ORANG_TUA, A.PERAN_ADMIN) == ("orang_tua", "admin")


# --- kode acak dan tampilan -------------------------------------------------------------

def test_buat_kode_enam_belas_karakter_dari_alfabet_crockford():
    # Arrange / Act
    kode = A.buat_kode()

    # Assert
    assert len(kode) == 16
    assert set(kode) <= set(ALFABET)


def test_buat_kode_seribu_kali_menghasilkan_seribu_kode_berbeda():
    # Arrange / Act
    hasil = {A.buat_kode() for _ in range(1000)}

    # Assert
    assert len(hasil) == 1000


def test_tampilkan_membentuk_blok_empat_karakter_dengan_tanda_hubung():
    assert A.tampilkan(KODE_CONTOH) == TAMPIL_CONTOH


def test_tampilan_kode_acak_cocok_pola_xxxx_xxxx_xxxx_xxxx():
    assert POLA_TAMPIL.fullmatch(A.tampilkan(A.buat_kode()))


@pytest.mark.parametrize(
    "kode",
    [None, "ABCD-EFGH", "abcd-efgh-jkmn-pqrs", TAMPIL_LAMA, 123],
)
def test_tampilkan_menolak_kode_tidak_kanonik(kode):
    with pytest.raises(ValueError):
        A.tampilkan(kode)


# --- normalisasi ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "masukan",
    [
        pytest.param("ABCD-EFGH-JKMN-PQRS", id="tampil-kanonik"),
        pytest.param("abcd-efgh-jkmn-pqrs", id="huruf-kecil"),
        pytest.param("ABCD EFGH JKMN PQRS", id="spasi"),
        pytest.param("  abcd efgh-jkmn\tpqrs  ", id="spasi-tepi-dan-campur"),
        pytest.param("ABCDEFGHJKMNPQRS", id="tanpa-pemisah"),
    ],
)
def test_normalkan_menerima_penulisan_yang_setara(masukan):
    assert A.normalkan(masukan) == KODE_CONTOH


def test_normalkan_memetakan_i_dan_l_ke_satu_serta_o_ke_nol():
    assert A.normalkan("ILOO-ILOO-ILOO-ILOO") == "1100110011001100"


@pytest.mark.parametrize(
    "masukan",
    [
        pytest.param(None, id="none"),
        pytest.param(123456789012, id="int"),
        pytest.param(b"ABCDEFGHJKMNPQRS", id="bytes"),
        pytest.param(["ABCDEFGHJKMNPQRS"], id="daftar"),
        pytest.param("", id="kosong"),
        pytest.param("   ", id="hanya-spasi"),
        pytest.param(KODE_LAMA, id="dua-belas-karakter-format-lama"),
        pytest.param(TAMPIL_LAMA, id="tampil-dua-belas-karakter-format-lama"),
        pytest.param("ABCD-EFGH-JKMN-PQR", id="lima-belas-karakter"),
        pytest.param("ABCD-EFGH-JKMN-PQRST", id="tujuh-belas-karakter"),
        pytest.param("ABCD-EFGH-JKMN-PQRU", id="u-tidak-ada-di-alfabet"),
        pytest.param("ABCD-EFGH-JKMN-PQR!", id="karakter-asing"),
        pytest.param("ABCD-EFGH-JKMN-PQR\x00", id="karakter-nul"),
        pytest.param("ABCDEFGHJKMNPQRé", id="latin-diakritik"),
        pytest.param("ABCDEFGHJKMNPQR\U0001F600", id="emoji"),
        pytest.param("ABCDEFGHJKMNPQR٣", id="digit-arab"),
        pytest.param("ABCDEFGHJKMNPQRı", id="i-tanpa-titik-naik-ke-I"),
        pytest.param("ABCDEFGHJKMNPQRſ", id="s-panjang-naik-ke-S"),
        pytest.param("A" * 65, id="melebihi-64-karakter"),
        pytest.param("ABCD-" * 40, id="sangat-panjang-setelah-strip"),
    ],
)
def test_normalkan_mengembalikan_none_untuk_masukan_tidak_sah(masukan):
    assert A.normalkan(masukan) is None


@pytest.mark.parametrize("masukan", [object(), 1.5, float("nan"), {"k": "v"}, "\x00" * 10, "é" * 70])
def test_normalkan_dan_hash_kode_tidak_pernah_raise_untuk_masukan_apa_pun(masukan):
    assert A.normalkan(masukan) is None
    assert A.hash_kode(masukan) is None


@pytest.mark.parametrize("panjang", [12, 15, 17])
def test_panjang_selain_enam_belas_ditolak_normalkan_hash_dan_tampilkan(panjang):
    # Arrange: karakter sah semua, hanya panjangnya yang salah
    kode = (KODE_CONTOH * 2)[:panjang]

    # Act / Assert
    assert A.normalkan(kode) is None
    assert A.hash_kode(kode) is None
    with pytest.raises(ValueError):
        A.tampilkan(kode)


# --- hash -------------------------------------------------------------------------------

def test_hash_kode_adalah_sha256_dari_bentuk_kanonik():
    # Arrange
    diharapkan = hashlib.sha256(KODE_CONTOH.encode("ascii")).hexdigest()

    # Act / Assert
    assert A.hash_kode(TAMPIL_CONTOH) == diharapkan


def test_hash_kode_sama_untuk_penulisan_yang_setara():
    assert A.hash_kode(KODE_CONTOH) is not None
    assert A.hash_kode("abcd-efgh-jkmn-pqrs") == A.hash_kode("ABCD EFGH JKMN PQRS") == A.hash_kode(KODE_CONTOH)


def test_hash_kode_beda_untuk_kode_yang_berbeda():
    # Arrange
    kode_lain = "ABCDEFGHJKMNPQR1"

    # Act / Assert
    assert A.hash_kode(kode_lain) is not None
    assert A.hash_kode(KODE_CONTOH) != A.hash_kode(kode_lain)


def test_kode_format_lama_dua_belas_karakter_tidak_menghasilkan_hash():
    assert A.hash_kode(KODE_LAMA) is None
    assert A.hash_kode(TAMPIL_LAMA) is None


def test_hash_kode_berbentuk_hex_enam_puluh_empat_karakter():
    assert POLA_HASH.fullmatch(A.hash_kode(A.buat_kode()))


# --- status turunan permintaan ----------------------------------------------------------

def _status(**ubah):
    data = {"kedaluwarsa": KEDALUWARSA, "hasil_putusan": None, "kode_dicabut": False, "kini": "2026-11-12T10:00:00"}
    return A.status_permintaan(**{**data, **ubah})


def test_status_menunggu_sebelum_kedaluwarsa():
    assert _status() == "menunggu"


def test_status_kedaluwarsa_tepat_pada_batas_tujuh_hari():
    assert _status(kini=KEDALUWARSA) == "kedaluwarsa"


def test_status_masih_menunggu_satu_detik_sebelum_batas():
    assert _status(kini="2026-11-17T09:59:59") == "menunggu"


def test_status_kedaluwarsa_setelah_batas():
    assert _status(kini="2026-11-18T00:00:00") == "kedaluwarsa"


def test_status_setuju_dan_tolak_mengikuti_putusan():
    assert _status(hasil_putusan="setuju") == "setuju"
    assert _status(hasil_putusan="tolak") == "tolak"


def test_putusan_mengalahkan_kedaluwarsa_dan_batal():
    assert _status(hasil_putusan="setuju", kode_dicabut=True, kini="2026-11-20T00:00:00") == "setuju"


def test_kode_dicabut_menjadi_batal_sebelum_kedaluwarsa():
    assert _status(kode_dicabut=True) == "batal"


def test_batal_mengalahkan_kedaluwarsa():
    assert _status(kode_dicabut=True, kini="2026-11-20T00:00:00") == "batal"


def test_status_menolak_hasil_putusan_tidak_dikenal():
    with pytest.raises(ValueError):
        _status(hasil_putusan="ya")


# --- waktu ------------------------------------------------------------------------------

def test_hitung_kedaluwarsa_tepat_tujuh_hari_setelah_dibuat():
    assert A.hitung_kedaluwarsa(DIBUAT) == KEDALUWARSA


def test_hitung_kedaluwarsa_melewati_pergantian_bulan():
    assert A.hitung_kedaluwarsa("2026-11-28T12:00:00") == "2026-12-05T12:00:00"


def test_waktu_mundur_mengurangi_durasi_tepat():
    assert A.waktu_mundur(DIBUAT, timedelta(days=1)) == "2026-11-09T10:00:00"


@pytest.mark.parametrize("nilai", ["2026-11-10T10:00:00", "2026-02-28T23:59:59"])
def test_waktu_sah_menerima_format_baku(nilai):
    assert A.waktu_sah(nilai) is True


@pytest.mark.parametrize(
    "nilai",
    [
        None,
        1,
        "2026-11-10 10:00:00",
        "2026-1-5T10:00:00",
        "2026-02-30T10:00:00",
        "2026-11-10T10:00",
        "2026-11-10T10:00:00Z",
        "2026-11-10T10:00:00\n",
    ],
)
def test_waktu_sah_menolak_selain_format_baku(nilai):
    assert A.waktu_sah(nilai) is False


# --- jeda tolak -------------------------------------------------------------------------

def test_jeda_tolak_masih_berlaku_satu_detik_sebelum_tujuh_hari():
    assert A.dalam_jeda_tolak(PADA_TOLAK, "2026-11-17T09:59:59") is True


def test_jeda_tolak_berakhir_tepat_pada_tujuh_hari():
    assert A.dalam_jeda_tolak(PADA_TOLAK, KEDALUWARSA) is False


def test_jeda_tolak_tidak_berlaku_setelah_tujuh_hari():
    assert A.dalam_jeda_tolak(PADA_TOLAK, "2026-11-18T10:00:00") is False


def test_jeda_tolak_berlaku_tepat_saat_ditolak():
    assert A.dalam_jeda_tolak(PADA_TOLAK, PADA_TOLAK) is True


# --- batas guru dan kode ----------------------------------------------------------------

@pytest.mark.parametrize(("jumlah", "diblokir"), [(0, False), (4, False), (5, True), (6, True)])
def test_guru_diblokir_mulai_dari_gagal_kelima(jumlah, diblokir):
    assert A.guru_diblokir(jumlah) is diblokir


@pytest.mark.parametrize(("jumlah", "penuh"), [(0, False), (9, False), (10, True), (11, True)])
def test_kode_penuh_mulai_dari_permintaan_kesepuluh(jumlah, penuh):
    assert A.kode_penuh(jumlah) is penuh

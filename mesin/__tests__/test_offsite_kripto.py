"""Format off-site: pola id ASCII ketat, cek tipe meta, validasi kunci publik RSA >= 3072."""
import hashlib
import subprocess

import pytest

from offsite_kit import SCRIPTS, buat_pasangan_kunci  # noqa: F401

import offsite_kripto as kripto  # noqa: E402

ID = "20260101-000000"
HEX = "ab" * 32


def _meta(**ubah):
    meta = kripto.bangun_meta(ID, 10, HEX, HEX, HEX)
    meta.update(ubah)
    return meta


@pytest.fixture(scope="module")
def pem_2048(tmp_path_factory):
    return buat_pasangan_kunci(tmp_path_factory.mktemp("k2048"), bit=2048)[1]


@pytest.fixture(scope="module")
def pem_3072(tmp_path_factory):
    return buat_pasangan_kunci(tmp_path_factory.mktemp("k3072"), bit=3072)[1]


@pytest.fixture(scope="module")
def pem_ec(tmp_path_factory):
    direktori = tmp_path_factory.mktemp("kec")
    privat, publik = direktori / "ec.pem", direktori / "ec-pub.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "EC", "-pkeyopt",
                    "ec_paramgen_curve:P-256", "-out", str(privat)], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(privat), "-pubout", "-out", str(publik)],
                   check=True, capture_output=True)
    return publik


# --- L6: pola ASCII, tanpa celah newline/angka Unicode ---

@pytest.mark.parametrize("nilai", [
    ID + "\n", "\n" + ID, "٢٠٢٦٠١٠١-٠٠٠٠٠٠", "２０２６０１０１-０００００１", ID + " ", ""])
def test_pola_id_menolak_newline_dan_angka_unicode(nilai):
    assert kripto.POLA_ID.fullmatch(nilai) is None


def test_pola_id_menerima_id_sah():
    assert kripto.POLA_ID.fullmatch(ID)


@pytest.mark.parametrize("nilai", [HEX + "\n", HEX.upper(), "٠" * 64])
def test_pola_hex_menolak_newline_huruf_besar_dan_unicode(nilai):
    assert kripto.POLA_HEX.fullmatch(nilai) is None


def test_periksa_meta_menolak_id_berakhir_newline():
    with pytest.raises(kripto.GalatKripto):
        kripto.periksa_meta(_meta(id=ID + "\n"), ID + "\n")


# --- L12: tipe ketat ---

def test_meta_sah_diterima():
    assert kripto.periksa_meta(_meta(), ID)["kunci_publik_sha256"] == HEX


@pytest.mark.parametrize("ubah", [
    {"format": True}, {"format": 1.0}, {"ukuran": 10.0}, {"ukuran": True}, {"ukuran": 0},
    {"kunci_publik_sha256": "x"}, {"kunci_publik_sha256": HEX + "\n"},
], ids=["format-true", "format-float", "ukuran-float", "ukuran-true", "ukuran-nol",
        "sidik-pendek", "sidik-newline"])
def test_periksa_meta_menolak_tipe_longgar(ubah):
    with pytest.raises(kripto.GalatKripto):
        kripto.periksa_meta(_meta(**ubah), ID)


@pytest.mark.parametrize("nilai", [True, 200000.0, "200000"], ids=["true", "float", "teks"])
def test_periksa_meta_menolak_iter_bukan_int_murni(nilai):
    meta = _meta()
    meta["alg"]["iter"] = nilai

    with pytest.raises(kripto.GalatKripto):
        kripto.periksa_meta(meta, ID)


def test_periksa_meta_menolak_tanpa_sidik_kunci():
    meta = _meta()
    del meta["kunci_publik_sha256"]

    with pytest.raises(kripto.GalatKripto):
        kripto.periksa_meta(meta, ID)


def test_mac_mengikat_sidik_kunci_publik(tmp_path):
    cipher = tmp_path / "c"
    cipher.write_bytes(b"isi")
    sandi = "a" * 64

    mac_a = kripto.hitung_mac(sandi, ID, cipher, "1" * 64)
    mac_b = kripto.hitung_mac(sandi, ID, cipher, "2" * 64)

    assert mac_a != mac_b


# --- L9: kunci publik RSA >= 3072 bit + sidik jari ---

def test_kunci_rsa_3072_diterima_dan_sidik_jari_sama_dengan_der_sha256(pem_3072):
    sidik = kripto.validasi_kunci_publik("openssl", pem_3072)

    der = subprocess.run(["openssl", "pkey", "-pubin", "-in", str(pem_3072), "-outform", "DER"],
                         check=True, capture_output=True).stdout
    assert sidik == hashlib.sha256(der).hexdigest() and kripto.POLA_HEX.fullmatch(sidik)


def test_kunci_rsa_2048_ditolak_dengan_pesan_batas_bit(pem_2048):
    with pytest.raises(kripto.GalatKripto, match="3072"):
        kripto.validasi_kunci_publik("openssl", pem_2048)


def test_kunci_bukan_rsa_ditolak(pem_ec):
    with pytest.raises(kripto.GalatKripto, match="RSA"):
        kripto.validasi_kunci_publik("openssl", pem_ec)


def test_pem_rusak_ditolak(tmp_path):
    rusak = tmp_path / "rusak.pem"
    rusak.write_text("-----BEGIN PUBLIC KEY-----\nbukan-base64!!\n-----END PUBLIC KEY-----\n")

    with pytest.raises(kripto.GalatKripto):
        kripto.validasi_kunci_publik("openssl", rusak)


@pytest.mark.parametrize("teks,bit", [
    ("Public-Key: (3072 bit)\nModulus:\n  00:aa\nExponent: 65537 (0x10001)\n", 3072),
    ("RSA Public-Key: (4096 bit)\nModulus:\n  00:aa\nExponent: 65537 (0x10001)\n", 4096),
])
def test_urai_bit_rsa_dari_keluaran_openssl_baru_dan_libressl(teks, bit):
    assert kripto.urai_bit_rsa(teks) == bit


@pytest.mark.parametrize("teks", [
    "Public-Key: (3072 bit)\npub:\n  04:aa\nP:\n  00:bb\n",          # mirip DSA: tanpa Modulus
    "Public-Key: (256 bit)\npub:\n  04:aa\nASN1 OID: prime256v1\n",   # EC
    "ED25519 Public-Key:\npub:\n  aa\n",
    "Modulus:\n  00:aa\nExponent: 65537 (0x10001)\n",                 # tanpa baris bit
    "Public-Key: (3072 bit)\nModulus:\n  00:aa\n",                    # tanpa Exponent
    "",
])
def test_urai_bit_rsa_menolak_yang_bukan_rsa(teks):
    with pytest.raises(kripto.GalatKripto):
        kripto.urai_bit_rsa(teks)

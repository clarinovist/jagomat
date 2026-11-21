"""Klien S3/R2: SigV4 terhadap vektor resmi AWS + server tiruan yang memverifikasi."""
import hashlib
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.append(str(SCRIPTS))
import r2_s3  # noqa: E402
from s3_tiruan_kit import AKSES_UJI, BUCKET_UJI, RAHASIA_UJI, S3Tiruan  # noqa: E402

# Vektor resmi AWS Signature V4 Test Suite (salinan primer: suite.fixture.js milik
# @smithy/signature-v4). Region us-east-1, service "service", 20150830T123600Z.
AKSES_AWS = "AKIDEXAMPLE"
RAHASIA_AWS = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
TGL = "20150830T123600Z"
HOST_AWS = "example.amazonaws.com"
ALFABET = "-._~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
VEKTOR_SUITE = [
    ("get-vanilla", "/", [], {}, "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"),
    ("get-vanilla-query-order-key-case", "/", [("Param2", "value2"), ("Param1", "value1")], {},
     "b97d918cfa904a5beff61c982a1b6f458b799221646efd99d3219ec94cdf2500"),
    ("get-vanilla-query-unreserved", "/", [(ALFABET, ALFABET)], {},
     "9c3e54bfcdf0b19771a7f523ee5669cdf59bc7cc0884027167c21bb143a40197"),
    ("get-unreserved", "/" + ALFABET, [], {},
     "07ef7494c76fa4850883e2b006601f940f8a34d404d0cfa977f52a65bbf5f24f"),
    ("get-header-value-order", "/", [], {"my-header1": "value4,value1,value3,value2"},
     "08c7e5a9acfcfeb3ab6b2185e75ce8b1deb5e634ec47601a50643f830c755c01"),
    ("get-header-value-trim", "/", [], {"my-header1": "value1", "my-header2": '"a   b   c"'},
     "acc3ed3afb60bb290fc8d2dd0098b9911fcaa05412b367055dee359757a9c736"),
]


@pytest.mark.parametrize("nama,path,query,ekstra,tanda", VEKTOR_SUITE, ids=[v[0] for v in VEKTOR_SUITE])
def test_tandatangani_cocok_vektor_resmi_aws(nama, path, query, ekstra, tanda):
    headers = {"host": HOST_AWS, "x-amz-date": TGL, **ekstra}

    hasil = r2_s3.tandatangani("GET", path, query, headers, r2_s3.HASH_KOSONG,
                         AKSES_AWS, RAHASIA_AWS, "us-east-1", "service")

    assert hasil.endswith("Signature=" + tanda)
    assert "Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request" in hasil


def test_tandatangani_cocok_contoh_s3_get_object_dokumentasi_aws():
    # Contoh "GET Object" (Range) pada dokumentasi SigV4 S3; nilai dari ingatan, bukan salinan primer.
    headers = {"host": "examplebucket.s3.amazonaws.com", "range": "bytes=0-9",
               "x-amz-content-sha256": r2_s3.HASH_KOSONG, "x-amz-date": "20130524T000000Z"}

    hasil = r2_s3.tandatangani("GET", "/test.txt", [], headers, r2_s3.HASH_KOSONG,
                         "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                         "us-east-1", "s3")

    assert hasil.endswith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


@pytest.fixture()
def s3():
    with S3Tiruan() as server:
        yield server


def _klien(s3, **kw):
    kw.setdefault("tidur", lambda _detik: None)
    return r2_s3.KlienR2(s3.url, BUCKET_UJI, AKSES_UJI, RAHASIA_UJI, **kw)


def test_put_lalu_list_memverifikasi_tanda_tangan_dan_hash_payload(s3, tmp_path):
    berkas = tmp_path / "x.bin"
    berkas.write_bytes(b"isi sintetis\x00\xff" * 1000)

    _klien(s3).put_objek("vps/20260101-000000/data.enc", berkas)

    assert s3.objek["vps/20260101-000000/data.enc"][0] == berkas.read_bytes()
    daftar = _klien(s3).daftar_objek("vps/")
    assert [(o.kunci, o.ukuran) for o in daftar] == [("vps/20260101-000000/data.enc", 14000)]
    assert s3.kunci_diverifikasi == 2


def test_kunci_dengan_karakter_khusus_tetap_lolos_tanda_tangan(s3, tmp_path):
    berkas = tmp_path / "x"
    berkas.write_bytes(b"a")

    _klien(s3).put_objek("vps/a b+c/ü~.enc", berkas)

    assert "vps/a b+c/ü~.enc" in s3.objek


def test_list_paginasi_dengan_token_berisi_karakter_khusus(s3):
    for i in range(7):
        s3.taruh(f"vps/{i:02d}", b"x")
    s3.taruh("harian/lain", b"x")
    s3.ukuran_halaman = 3

    daftar = _klien(s3).daftar_objek("vps/")

    assert [o.kunci for o in daftar] == [f"vps/{i:02d}" for i in range(7)]
    daftar_list = [p for p in s3.permintaan if p[0] == "GET"]
    assert len(daftar_list) == 3  # 3 + 3 + 1


def test_list_membaca_last_modified_sebagai_epoch_utc(s3):
    s3.taruh("vps/a", b"xy", diubah=1_700_000_000)

    (objek,) = _klien(s3).daftar_objek("vps/")

    assert objek.diubah == 1_700_000_000 and objek.ukuran == 2


def test_hapus_dan_ambil_objek(s3, tmp_path):
    s3.taruh("vps/a", b"halo")
    tujuan = tmp_path / "unduh"

    _klien(s3).ambil_objek("vps/a", tujuan)
    _klien(s3).hapus_objek("vps/a")

    assert tujuan.read_bytes() == b"halo" and "vps/a" not in s3.objek


def test_rahasia_salah_ditolak_tanpa_membocorkan_isi_respons(s3):
    klien = r2_s3.KlienR2(s3.url, BUCKET_UJI, AKSES_UJI, "rahasia-lain", tidur=lambda _: None)

    with pytest.raises(r2_s3.GalatS3) as info:
        klien.daftar_objek("vps/")

    pesan = str(info.value)
    assert "403" in pesan and "SignatureDoesNotMatch" in pesan
    assert AKSES_UJI not in pesan and "rahasia" not in pesan


def test_status_5xx_dicoba_ulang_tiga_kali_lalu_gagal(s3, tmp_path):
    berkas = tmp_path / "x"
    berkas.write_bytes(b"a")
    s3.gagal[("PUT", "vps/a")] = 500
    jeda = []

    with pytest.raises(r2_s3.GalatS3, match="HTTP 500"):
        _klien(s3, tidur=jeda.append).put_objek("vps/a", berkas)

    assert len([p for p in s3.permintaan if p == ("PUT", "vps/a")]) == 3
    assert len(jeda) == 2


def test_status_4xx_tidak_dicoba_ulang(s3):
    with pytest.raises(r2_s3.GalatS3, match="HTTP 404"):
        _klien(s3).ambil_objek("vps/tidak-ada", Path("/dev/null"))

    assert len(s3.permintaan) == 1


@pytest.mark.parametrize("endpoint", [
    "http://r2.example.com", "ftp://x", "https://x/jalur", "x.example.com", "https://"])
def test_endpoint_tidak_sah_ditolak(endpoint):
    with pytest.raises(ValueError):
        r2_s3.KlienR2(endpoint, BUCKET_UJI, "a", "b")


def test_nama_bucket_tidak_sah_ditolak():
    with pytest.raises(ValueError):
        r2_s3.KlienR2("https://x.r2.cloudflarestorage.com", "../Bucket", "a", "b")


def test_sha256_berkas_cocok_hashlib(tmp_path):
    berkas = tmp_path / "x"
    berkas.write_bytes(b"abc" * 100000)

    assert r2_s3.sha256_berkas(berkas) == hashlib.sha256(b"abc" * 100000).hexdigest()

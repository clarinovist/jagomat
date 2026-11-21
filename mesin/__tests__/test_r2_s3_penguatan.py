"""Klien R2 pasca-tinjauan: tolak DTD/entity, retry 429, nama kelas galat, batas unduhan."""
from pathlib import Path
import ssl
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.append(str(SCRIPTS))
import r2_s3  # noqa: E402
from s3_tiruan_kit import AKSES_UJI, BUCKET_UJI, RAHASIA_UJI, S3Tiruan  # noqa: E402

DOKUMEN_ENTITY = (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "AAAA">]>'
                  b'<ListBucketResult><IsTruncated>false</IsTruncated>'
                  b'<Contents><Key>&a;</Key><LastModified>2026-01-01T00:00:00.000Z</LastModified>'
                  b'<Size>1</Size></Contents></ListBucketResult>')


@pytest.fixture()
def s3():
    with S3Tiruan() as server:
        yield server


def _klien(s3, **kw):
    kw.setdefault("tidur", lambda _detik: None)
    return r2_s3.KlienR2(s3.url, BUCKET_UJI, AKSES_UJI, RAHASIA_UJI, **kw)


def _klien_polos():
    return r2_s3.KlienR2("http://127.0.0.1:1", BUCKET_UJI, AKSES_UJI, RAHASIA_UJI,
                         tidur=lambda _d: None)


def _paksa_respons(monkeypatch, status, isi):
    monkeypatch.setattr(r2_s3.KlienR2, "_sekali", lambda self, *a, **k: (status, isi))


def _awasi_parser(monkeypatch):
    diurai = []
    asli = r2_s3.ET.fromstring
    monkeypatch.setattr(r2_s3.ET, "fromstring",
                        lambda *a, **k: (diurai.append(1), asli(*a, **k))[1])
    return diurai


@pytest.mark.parametrize("isi", [
    DOKUMEN_ENTITY,
    DOKUMEN_ENTITY.replace(b"DOCTYPE", b"doctype"),
    DOKUMEN_ENTITY.replace(b"<!ENTITY", b"<!entity").replace(b"<!DOCTYPE", b"<!DocType"),
    DOKUMEN_ENTITY.decode().encode("utf-16"),
], ids=["besar", "kecil", "campur", "utf16"])
def test_list_menolak_respons_berisi_doctype_atau_entity_tanpa_mengurai(monkeypatch, isi):
    _paksa_respons(monkeypatch, 200, isi)
    diurai = _awasi_parser(monkeypatch)

    with pytest.raises(r2_s3.GalatS3, match="tidak terbaca"):
        _klien_polos().daftar_objek("vps/")

    assert diurai == []


def test_badan_galat_berisi_doctype_tidak_diurai_dan_kode_jadi_strip(monkeypatch):
    _paksa_respons(monkeypatch, 403, DOKUMEN_ENTITY)
    diurai = _awasi_parser(monkeypatch)

    with pytest.raises(r2_s3.GalatS3, match=r"HTTP 403 -$"):
        _klien_polos().daftar_objek("vps/")

    assert diurai == []


def test_status_429_dicoba_ulang_dengan_jeda(s3, tmp_path):
    berkas = tmp_path / "x"
    berkas.write_bytes(b"a")
    s3.gagal[("PUT", "vps/a")] = 429
    jeda = []

    with pytest.raises(r2_s3.GalatS3, match="HTTP 429"):
        _klien(s3, tidur=jeda.append).put_objek("vps/a", berkas)

    assert len([p for p in s3.permintaan if p == ("PUT", "vps/a")]) == 3
    assert len(jeda) == 2


def test_galat_jaringan_menyebut_nama_kelas_galat_tanpa_rahasia(tmp_path):
    berkas = tmp_path / "x"
    berkas.write_bytes(b"a")

    with pytest.raises(r2_s3.GalatS3) as info:
        _klien_polos().put_objek("vps/a", berkas)  # port 1: ditolak

    pesan = str(info.value)
    assert "ConnectionRefusedError" in pesan and "HTTP 599" not in pesan
    assert AKSES_UJI not in pesan and RAHASIA_UJI not in pesan and "127.0.0.1" not in pesan


def test_galat_tls_menyebut_kelas_galat_tanpa_detail(monkeypatch):
    def tls_gagal(self, *a, **k):
        raise ssl.SSLCertVerificationError("detail sensitif https://x?k=RAHASIA")

    monkeypatch.setattr(r2_s3.KlienR2, "_sekali", tls_gagal)

    with pytest.raises(r2_s3.GalatS3) as info:
        _klien_polos().hapus_objek("vps/a")

    assert "SSLCertVerificationError" in str(info.value) and "RAHASIA" not in str(info.value)


def test_ambil_objek_melebihi_batas_ditolak_dan_tidak_menulis_lebih(s3, tmp_path, monkeypatch):
    monkeypatch.setattr(r2_s3, "BLOK", 16)
    s3.taruh("vps/a", b"x" * 1000)
    tujuan = tmp_path / "unduh"

    with pytest.raises(r2_s3.GalatS3, match="melebihi batas"):
        _klien(s3).ambil_objek("vps/a", tujuan, maks_byte=100)

    assert tujuan.stat().st_size <= 100


def test_ambil_objek_tepat_di_batas_diterima(s3, tmp_path):
    s3.taruh("vps/a", b"x" * 100)
    tujuan = tmp_path / "unduh"

    _klien(s3).ambil_objek("vps/a", tujuan, maks_byte=100)

    assert tujuan.stat().st_size == 100


def test_galat_404_membawa_status_untuk_pemanggil(s3):
    with pytest.raises(r2_s3.GalatS3) as info:
        _klien(s3).ambil_objek("vps/tidak-ada", Path("/dev/null"))

    assert info.value.status == 404


@pytest.mark.parametrize("bucket", ["bucket-uji\n", "bucket-uji\n\n"])
def test_nama_bucket_berakhir_newline_ditolak(bucket):
    with pytest.raises(ValueError):
        r2_s3.KlienR2("https://x.r2.cloudflarestorage.com", bucket, "a", "b")

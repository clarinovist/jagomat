"""Parser multipart sempit bukti: satu berkas + satu token, selain itu ditolak."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bukti_multipart as bm  # noqa: E402
from bukti_kit import BATAS, JPEG, bagian, bukti, multipart, tipe_konten  # noqa: E402

TIPE = tipe_konten()


def test_bagian_sah_mengembalikan_token_dan_isi_persis():
    isi = JPEG + b"\r\n--lain\r\n" + bytes(range(256))
    hasil = bm.parse(bukti("tok.en-1", isi), TIPE)
    assert hasil == bm.BuktiForm(token="tok.en-1", isi=isi)


def test_isi_kosong_tetap_terurai_untuk_ditolak_penangan():
    assert bm.parse(bukti("t", b""), TIPE).isi == b""


def test_nama_berkas_dan_tipe_klaim_diabaikan():
    tubuh = bukti("t", JPEG, nama_berkas="../../etc/passwd.png", tipe="application/pdf")
    assert bm.parse(tubuh, TIPE).isi == JPEG


def test_urutan_berkas_lalu_token_diterima():
    tubuh = multipart([bagian("berkas", JPEG, nama_berkas="a.jpg"), bagian("token", b"t")])
    assert bm.parse(tubuh, TIPE) == bm.BuktiForm("t", JPEG)


@pytest.mark.parametrize("tubuh", [
    multipart([bagian("berkas", JPEG, nama_berkas="a.jpg")]),                      # tanpa token
    multipart([bagian("token", b"t")]),                                           # tanpa berkas
    multipart([bagian("token", b"t"), bagian("token", b"u"),
               bagian("berkas", JPEG, nama_berkas="a")]),                          # token ganda
    multipart([bagian("token", b"t"), bagian("berkas", JPEG, nama_berkas="a"),
               bagian("berkas", JPEG, nama_berkas="b")]),                          # berkas ganda
    multipart([bagian("token", b"t"), bagian("berkas", JPEG, nama_berkas="a"),
               bagian("order_id", b"ord_1")]),                                    # field asing
    multipart([bagian("token", b"t"), bagian("berkas", JPEG, nama_berkas="a")], tutup=False),
    b"",
    b"sampah tanpa batas",
    b"preamble\r\n" + bukti("t", JPEG),
])
def test_bentuk_tidak_sah_ditolak(tubuh):
    assert bm.parse(tubuh, TIPE) is None


@pytest.mark.parametrize("tipe", [
    "", "application/x-www-form-urlencoded", "multipart/form-data", "multipart/form-data; boundary=",
    "multipart/mixed; boundary=" + BATAS, "multipart/form-data; boundary=" + "a" * 71,
    'multipart/form-data; boundary="bad\r\nboundary"', "multipart/form-data; boundary=a b\tc",
])
def test_content_type_atau_batas_tidak_sah_ditolak(tipe):
    assert bm.parse(bukti("t", JPEG), tipe) is None


def test_batas_dengan_tanda_kutip_diterima():
    assert bm.parse(bukti("t", JPEG), 'multipart/form-data; boundary="%s"' % BATAS).isi == JPEG


def test_terlalu_banyak_bagian_ditolak():
    banyak = [bagian("token", b"t")] + [bagian("berkas", JPEG, nama_berkas="a")] * (bm.BATAS_BAGIAN + 1)
    assert bm.parse(multipart(banyak), TIPE) is None


def test_kepala_bagian_terlalu_panjang_ditolak():
    panjang = bagian("token", b"t").replace(b'name="token"', b'name="token"; x="' + b"a" * 5000 + b'"')
    assert bm.parse(multipart([panjang, bagian("berkas", JPEG, nama_berkas="a")]), TIPE) is None


def test_token_bukan_utf8_atau_terlalu_panjang_ditolak():
    assert bm.parse(multipart([bagian("token", b"\xff\xfe"), bagian("berkas", JPEG, nama_berkas="a")]), TIPE) is None
    panjang = b"a" * (bm.BATAS_TOKEN + 1)
    assert bm.parse(multipart([bagian("token", panjang), bagian("berkas", JPEG, nama_berkas="a")]), TIPE) is None


def test_hanya_satu_crlf_penutup_dibuang_dari_isi():
    isi = JPEG + b"\r\n"
    assert bm.parse(bukti("t", isi), TIPE).isi == isi

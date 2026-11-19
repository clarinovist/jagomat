"""Pembantu bersama tes bukti transfer: bytes berkas SINTETIS dan pembuat multipart.

Isi berkas hanya header generik + pengisi (bukan foto/dokumen sungguhan, tanpa data anak,
nomor HP, nama asli, atau rekening asli).
"""
from __future__ import annotations

import hashlib

BATAS = "----batas-sintetis-0123456789"
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 48 + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 24
PDF = b"%PDF-1.4\n%sintetis\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
TEKS_PALSU = b"ini teks biasa, bukan gambar, walau dinamai .jpg"


def sha256(isi: bytes) -> str:
    return hashlib.sha256(isi).hexdigest()


def bagian(nama: str, isi: bytes, *, nama_berkas=None, tipe=None) -> bytes:
    kepala = 'Content-Disposition: form-data; name="%s"' % nama
    if nama_berkas is not None:
        kepala += '; filename="%s"' % nama_berkas
    if tipe is not None:
        kepala += "\r\nContent-Type: %s" % tipe
    return kepala.encode() + b"\r\n\r\n" + isi


def multipart(bagian_bagian, *, batas: str = BATAS, tutup: bool = True) -> bytes:
    tubuh = b""
    for b in bagian_bagian:
        tubuh += b"--" + batas.encode() + b"\r\n" + b + b"\r\n"
    return tubuh + (b"--" + batas.encode() + b"--\r\n" if tutup else b"")


def bukti(token: str, isi: bytes, *, nama_berkas="bukti.jpg", tipe="image/jpeg",
          batas: str = BATAS) -> bytes:
    """Tubuh multipart sah: field `token` lalu satu berkas `berkas`."""
    return multipart([bagian("token", token.encode()),
                      bagian("berkas", isi, nama_berkas=nama_berkas, tipe=tipe)], batas=batas)


def tipe_konten(batas: str = BATAS) -> str:
    return "multipart/form-data; boundary=" + batas

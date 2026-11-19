"""Parser multipart/form-data SEMPIT untuk unggah bukti transfer.

`http.server` tidak punya parser multipart dan satu form tidak sepadan dengan dependensi
baru. Bentuk yang diterima hanya: tepat satu bagian `token` (teks) dan tepat satu bagian
`berkas`; bagian lain, ganda, tanpa penutup, atau berlebih = ditolak (None). Nama berkas dan
Content-Type klaim klien diabaikan sepenuhnya (tipe diputuskan dari isi oleh pemanggil).
Salinan terpisah dari `attachments._parsing_multipart` (yang hanya mengenal field `foto`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from email.message import Message
import re
from typing import Optional

BATAS_BAGIAN = 4
BATAS_KEPALA = 1024
BATAS_TOKEN = 256
_BATAS_PANJANG_BOUNDARY = 70
_POLA_BOUNDARY = re.compile(r"[0-9A-Za-z'()+_,./:=?-]{1,%d}" % _BATAS_PANJANG_BOUNDARY)
_POLA_DISPOSISI = re.compile(
    r'form-data;\s*name="(token|berkas)"(?:;\s*filename="[^"\r\n]*")?', re.IGNORECASE)
_CRLF = b"\r\n"
_TUTUP = (b"--", b"--\r\n")


@dataclass(frozen=True)
class BuktiForm:
    token: str
    isi: bytes = field(repr=False)


def _boundary(content_type) -> Optional[str]:
    if type(content_type) is not str or not content_type:
        return None
    pesan = Message()
    pesan["Content-Type"] = content_type
    if pesan.get_content_type() != "multipart/form-data":
        return None
    nilai = pesan.get_param("boundary")
    if type(nilai) is not str or _POLA_BOUNDARY.fullmatch(nilai) is None:
        return None
    return nilai


def _potong(tubuh: bytes, boundary: str):
    """Daftar bagian mentah (tanpa CRLF depan) atau None bila kerangka tidak utuh."""
    awal = b"--" + boundary.encode("ascii")
    if not tubuh.startswith(awal + _CRLF):
        return None
    potongan = tubuh[len(awal):].split(_CRLF + awal)
    if potongan[-1] not in _TUTUP or not 1 <= len(potongan) - 1 <= BATAS_BAGIAN:
        return None
    bagian = potongan[:-1]
    return [b[len(_CRLF):] for b in bagian] if all(b.startswith(_CRLF) for b in bagian) else None


def _nama_bagian(kepala: bytes) -> Optional[str]:
    if len(kepala) > BATAS_KEPALA:
        return None
    try:
        baris = kepala.decode("utf-8", "strict").split("\r\n")
    except UnicodeDecodeError:
        return None
    disposisi = [b.split(":", 1)[1].strip() for b in baris if b.lower().startswith("content-disposition:")]
    if len(disposisi) != 1:
        return None
    cocok = _POLA_DISPOSISI.fullmatch(disposisi[0])
    return None if cocok is None else cocok.group(1).lower()


def _token(isi: bytes) -> Optional[str]:
    if len(isi) > BATAS_TOKEN:
        return None
    try:
        return isi.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None


def parse(tubuh: bytes, content_type) -> Optional[BuktiForm]:
    """Urai tubuh multipart menjadi `BuktiForm(token, isi)`; bentuk tidak sah -> None."""
    boundary = _boundary(content_type)
    if boundary is None or type(tubuh) is not bytes:
        return None
    bagian = _potong(tubuh, boundary)
    if bagian is None:
        return None
    diambil: dict = {}
    for mentah in bagian:
        kepala, pemisah, isi = mentah.partition(_CRLF + _CRLF)
        nama = _nama_bagian(kepala) if pemisah else None
        if nama is None or nama in diambil:
            return None
        diambil[nama] = isi
    if set(diambil) != {"token", "berkas"}:
        return None
    token = _token(diambil["token"])
    return None if token is None else BuktiForm(token=token, isi=diambil["berkas"])

"""Pengirim email transaksional lewat Resend (stdlib saja, tanpa dependensi).

Gagal tertutup: kunci API kosong menghasilkan `ditahan` tanpa menyentuh transport. Masukan divalidasi di batas
sistem sebelum kirim, dan karakter kendali (termasuk CR/LF) ditolak agar tidak bisa menyisipkan header. Galat
jaringan, timeout, dan respons galat dipetakan ke `gagal` tanpa melempar, serta tanpa menyalin badan respons,
kunci, penerima, atau isi. Tidak ada retry di dalam fungsi; idempotensi lewat header `Idempotency-Key`.
Alihan 3xx tidak diikuti, supaya kunci tidak terbawa ke alamat lain.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Tuple

URL_RESEND = "https://api.resend.com/emails"
PENGIRIM_BAWAAN = "Jagomat <no-reply@jagomat.id>"
ENV_KUNCI = "RESEND_API_KEY"
ENV_PENGIRIM = "SUREL_PENGIRIM"
USER_AGENT = "jagomat-surel/1.0"
TIMEOUT_DETIK = 15
PANJANG_ALAMAT_MAKS = 254
PANJANG_NAMA_PENGIRIM_MAKS = 100
PANJANG_SUBJEK_MAKS = 200
PANJANG_TEKS_MAKS = 10000
PANJANG_KUNCI_MAKS = 256
PANJANG_KUNCI_IDEMPOTENSI_MAKS = 256
BARIS_TEKS_DIIZINKAN = "\r\n\t"
KODE_SUKSES = (200, 201)
KODE_TERLALU_BANYAK = 429
KODE_KLIEN_MIN = 400
KODE_SERVER_MIN = 500
KODE_SERVER_MAKS = 600

STATUS_TERKIRIM = "terkirim"
STATUS_DITAHAN = "ditahan"
STATUS_GAGAL = "gagal"

ALASAN_MASUKAN = "masukan tidak sah"
ALASAN_DITAHAN = "kunci API belum diatur"
ALASAN_JARINGAN = "gagal menghubungi layanan surel"
ALASAN_DITOLAK = "ditolak layanan"
ALASAN_LAYANAN_GALAT = "layanan galat"
ALASAN_TERLALU_BANYAK = "terlalu banyak permintaan"
ALASAN_RESPONS_TIDAK_SAH = "respons layanan tidak sah"

_ALAMAT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_PENGIRIM_BERNAMA = re.compile(r'[^<>@",;]{1,%d}<(?P<alamat>[^<>]+)>' % PANJANG_NAMA_PENGIRIM_MAKS)
_TERLIHAT_ASCII = re.compile(r"[\x21-\x7e]+")

Transport = Callable[[str, Mapping[str, str], bytes, float], Tuple[int, bytes]]


@dataclass(frozen=True)
class HasilKirim:
    status: str
    kode_http: Optional[int]
    id_surel: Optional[str]
    alasan: str


def _gagal(alasan: str, kode: Optional[int] = None) -> HasilKirim:
    return HasilKirim(STATUS_GAGAL, kode, None, alasan)


def _kendali_terlarang(nilai: str, izinkan: str = "") -> bool:
    """True bila ada karakter kendali (kategori Cc) yang tidak termasuk `izinkan`; CR/LF ditolak kecuali diizinkan."""
    return any(unicodedata.category(karakter) == "Cc" and karakter not in izinkan for karakter in nilai)


def alamat_sah(nilai) -> bool:
    """Satu alamat email sederhana: tanpa spasi, koma, titik koma, kurung sudut, atau dua '@'."""
    return (isinstance(nilai, str) and len(nilai) <= PANJANG_ALAMAT_MAKS
            and _ALAMAT.fullmatch(nilai) is not None and not _kendali_terlarang(nilai))


def _teks_dalam_batas(nilai, maks: int) -> bool:
    return isinstance(nilai, str) and 1 <= len(nilai) <= maks


def _subjek_sah(subjek) -> bool:
    return _teks_dalam_batas(subjek, PANJANG_SUBJEK_MAKS) and not _kendali_terlarang(subjek)


def _teks_sah(teks) -> bool:
    return _teks_dalam_batas(teks, PANJANG_TEKS_MAKS) and not _kendali_terlarang(teks, BARIS_TEKS_DIIZINKAN)


def _kunci_idempotensi_sah(nilai) -> bool:
    return (_teks_dalam_batas(nilai, PANJANG_KUNCI_IDEMPOTENSI_MAKS)
            and _TERLIHAT_ASCII.fullmatch(nilai) is not None)


def _pengirim_sah(pengirim) -> bool:
    if not isinstance(pengirim, str) or _kendali_terlarang(pengirim):
        return False
    bernama = _PENGIRIM_BERNAMA.fullmatch(pengirim)
    return alamat_sah(bernama.group("alamat") if bernama else pengirim)


def _masukan_sah(penerima, subjek, teks, kunci_idempotensi, pengirim) -> bool:
    return (alamat_sah(penerima) and _subjek_sah(subjek) and _teks_sah(teks)
            and _kunci_idempotensi_sah(kunci_idempotensi) and _pengirim_sah(pengirim))


def _kunci_efektif(kunci_api) -> Optional[str]:
    """Kunci dari parameter (atau env bila None), dipangkas. "" bila kosong; None bila tipe atau isinya tidak sah."""
    mentah = os.environ.get(ENV_KUNCI, "") if kunci_api is None else kunci_api
    if not isinstance(mentah, str):
        return None
    kunci = mentah.strip()
    if kunci and (len(kunci) > PANJANG_KUNCI_MAKS or _TERLIHAT_ASCII.fullmatch(kunci) is None):
        return None
    return kunci


def _pengirim_efektif(pengirim) -> object:
    if pengirim is not None:
        return pengirim
    return (os.environ.get(ENV_PENGIRIM) or "").strip() or PENGIRIM_BAWAAN


def _badan_permintaan(pengirim: str, penerima: str, subjek: str, teks: str) -> bytes:
    muatan = {"from": pengirim, "to": [penerima], "subject": subjek, "text": teks}
    return json.dumps(muatan).encode("ascii")


def _header_permintaan(kunci: str, kunci_idempotensi: str) -> dict:
    return {
        "Authorization": "Bearer " + kunci,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Idempotency-Key": kunci_idempotensi,
    }


class _PenolakAlihan(urllib.request.HTTPRedirectHandler):
    """Alihan 3xx tidak diikuti: URL tetap, dan kunci tidak ikut terbawa ke alamat lain."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_PenolakAlihan)


def _transport_bawaan(url: str, headers: Mapping[str, str], badan: bytes, timeout: float) -> Tuple[int, bytes]:
    permintaan = urllib.request.Request(url, data=badan, headers=dict(headers), method="POST")
    try:
        with _OPENER.open(permintaan, timeout=timeout) as respons:
            return respons.status, respons.read()
    except urllib.error.HTTPError as galat:
        return galat.code, b""


def _id_surel(badan) -> Optional[str]:
    try:
        muatan = json.loads(badan)
    except (TypeError, ValueError):
        return None
    if not isinstance(muatan, dict):
        return None
    id_surel = muatan.get("id")
    return id_surel if isinstance(id_surel, str) and id_surel else None


def _hasil_dari_respons(kode: int, badan) -> HasilKirim:
    if kode in KODE_SUKSES:
        id_surel = _id_surel(badan)
        if id_surel is None:
            return _gagal(ALASAN_RESPONS_TIDAK_SAH, kode)
        return HasilKirim(STATUS_TERKIRIM, kode, id_surel, "")
    if kode == KODE_TERLALU_BANYAK:
        return _gagal(ALASAN_TERLALU_BANYAK, kode)
    if KODE_KLIEN_MIN <= kode < KODE_SERVER_MIN:
        return _gagal(ALASAN_DITOLAK, kode)
    if KODE_SERVER_MIN <= kode < KODE_SERVER_MAKS:
        return _gagal(ALASAN_LAYANAN_GALAT, kode)
    return _gagal(ALASAN_RESPONS_TIDAK_SAH, kode)


def _kirim_ke_layanan(penerima: str, subjek: str, teks: str, kunci_idempotensi: str, kunci: str,
                      pengirim: str, transport: Optional[Transport]) -> HasilKirim:
    badan = _badan_permintaan(pengirim, penerima, subjek, teks)
    headers = _header_permintaan(kunci, kunci_idempotensi)
    jalur = _transport_bawaan if transport is None else transport
    try:
        kode, badan_respons = jalur(URL_RESEND, headers, badan, TIMEOUT_DETIK)
    except (OSError, http.client.HTTPException):
        return _gagal(ALASAN_JARINGAN)
    return _hasil_dari_respons(kode, badan_respons)


def kirim(penerima, subjek, teks, *, kunci_idempotensi, kunci_api=None, pengirim=None,
          transport: Optional[Transport] = None) -> HasilKirim:
    """Kirim satu email teks polos. Urutan: masukan (gagal), kunci (ditahan bila kosong), lalu layanan."""
    pengirim_tuju = _pengirim_efektif(pengirim)
    if not _masukan_sah(penerima, subjek, teks, kunci_idempotensi, pengirim_tuju):
        return _gagal(ALASAN_MASUKAN)
    kunci = _kunci_efektif(kunci_api)
    if kunci is None:
        return _gagal(ALASAN_MASUKAN)
    if not kunci:
        return HasilKirim(STATUS_DITAHAN, None, None, ALASAN_DITAHAN)
    return _kirim_ke_layanan(penerima, subjek, teks, kunci_idempotensi, kunci, pengirim_tuju, transport)

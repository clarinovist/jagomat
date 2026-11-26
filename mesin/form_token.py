"""Token form anti-CSRF: HMAC-SHA256 berumur pendek, terikat ke akun dan sesi.

Modul bersama untuk setiap form yang butuh token. Pemanggil memberi `domain`
(prefiks HMAC unik per form) dan `aksi` (tindakan spesifik) sendiri, sehingga
token satu form tidak berlaku di form lain.

Format token: "<kedaluwarsa_unix>.<hmac_sha256_hex>". Kunci HMAC diturunkan dari
kunci sandi akun (`auth`), jadi ganti sandi atau revisi akun membatalkan semua
token lama.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import auth

UMUR_BAWAAN_DETIK = 900
BATAS_PANJANG_TOKEN = 256


def _periksa_argumen(domain, aksi) -> None:
    if type(domain) is not bytes or not domain:
        raise ValueError("domain token harus bytes tak kosong")
    if type(aksi) is not str or not aksi:
        raise ValueError("aksi token harus str tak kosong")


def _badan_terikat(principal, sesi, aksi: str, kedaluwarsa: int) -> bytes:
    isi = [
        principal.id_akun,
        principal.revisi_auth,
        hashlib.sha256((sesi or "").encode()).hexdigest(),
        aksi,
        kedaluwarsa,
    ]
    return json.dumps(isi, separators=(",", ":")).encode()


def _hitung_mac(principal, sesi, *, domain: bytes, aksi: str, kedaluwarsa: int):
    """MAC hex, atau None bila akun pemegang token tidak ditemukan."""
    akun = auth.cari_akun(principal.pengguna)
    if akun is None:
        return None
    badan = _badan_terikat(principal, sesi, aksi, kedaluwarsa)
    return hmac.new(bytes.fromhex(akun["kunci"]), domain + badan, hashlib.sha256).hexdigest()


def _pecah_token(token):
    """(kedaluwarsa, tanda) bila bentuk token masuk akal; None bila tidak."""
    if type(token) is not str or not 0 < len(token) <= BATAS_PANJANG_TOKEN:
        return None
    awal, titik, tanda = token.partition(".")
    if not titik or not awal.isascii() or not awal.isdigit():
        return None
    # compare_digest melempar TypeError untuk str non-ASCII: token rusak harus ditolak, bukan menjatuhkan request.
    if not tanda.isascii():
        return None
    return int(awal), tanda


def buat_token(principal, sesi, *, domain: bytes, aksi: str,
               umur: int = UMUR_BAWAAN_DETIK) -> str:
    """Token berumur `umur` detik, terikat ke akun, sesi, aksi, dan domain."""
    _periksa_argumen(domain, aksi)
    kedaluwarsa = int(time.time()) + umur
    # Akun hilang: mac None, sehingga token berbentuk "<exp>.None" dan tak pernah sah.
    mac = _hitung_mac(principal, sesi, domain=domain, aksi=aksi, kedaluwarsa=kedaluwarsa)
    return f"{kedaluwarsa}.{mac}"


def token_sah(principal, sesi, token, *, domain: bytes, aksi: str) -> bool:
    """True hanya untuk token utuh, belum kedaluwarsa, dan cocok dengan konteks ini."""
    _periksa_argumen(domain, aksi)
    pecahan = _pecah_token(token)
    if pecahan is None:
        return False
    kedaluwarsa, tanda = pecahan
    if int(time.time()) >= kedaluwarsa:
        return False
    harap = _hitung_mac(principal, sesi, domain=domain, aksi=aksi, kedaluwarsa=kedaluwarsa)
    return harap is not None and hmac.compare_digest(tanda, harap)

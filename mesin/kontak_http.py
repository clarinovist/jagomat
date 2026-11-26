"""Rute guru `GET/POST /akun/kontak`: lengkapi nomor WhatsApp akun sendiri.

Dipanggil setelah palang sandi guru/admin di dispatcher. Aturan yang ditegakkan
di sini (bukan di halaman):

- `id_akun` HANYA dari principal sesi server; form tidak punya field itu dan
  field tak dikenal (mis. `id_akun`, `pemilik`) membuat permintaan ditolak
  tanpa efek.
- Hanya peran guru. Admin tidak punya kontak pembayar, jadi admin menerima 404
  yang byte-identik dengan rute tak dikenal (tidak mengakui halaman ini ada).
  Murid dan anonim sudah dihentikan palang sandi (401) sebelum modul ini.
- Token form ditandatangani HMAC (terikat akun, revisi auth, sesi, dan waktu
  habis); token salah/kedaluwarsa/milik akun lain ditolak sebelum validasi.
- Nomor tidak masuk URL (PRG memakai kode pesan tetap), log, atau pesan galat.
  Satu-satunya pantulan adalah atribut `value` input pemilik (di-escape).
"""
from __future__ import annotations

import time  # dipertahankan: tes memonkeypatch kontak_http.time
import urllib.parse
from datetime import datetime, timezone

import database
import form_token
import kontak_akun
import kontak_pages
import registration_contact
from learning_cycle_http import GalatForm, _batasi_laju
from support_pages import halaman_pesan

RUTE = "/akun/kontak"
BATAS_FORM = 4096
BATAS_KOLOM_FORM = 8
KUNCI_FORM = frozenset({"token", "wa"})
UMUR_TOKEN_DETIK = 900
_AKSI_TOKEN = "kontak"
_DOMAIN_TOKEN = b"kontak-form-v1:"


def _tidak_ada(penangan) -> None:
    """Jawaban sama persis dengan fallthrough rute tak dikenal."""
    penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _principal_guru(penangan):
    """Principal guru dari sesi server; None untuk admin, mode lokal, atau selain guru."""
    principal = penangan._principal()
    if principal is None or principal.peran != "guru":
        return None
    return principal


def buat_token(principal, sesi) -> str:
    """Token form berumur pendek, terikat ke akun dan sesi pemegangnya."""
    return form_token.buat_token(
        principal, sesi, domain=_DOMAIN_TOKEN, aksi=_AKSI_TOKEN, umur=UMUR_TOKEN_DETIK,
    )


def token_sah(principal, sesi, token) -> bool:
    """True hanya untuk token utuh, belum kedaluwarsa, dan cocok dengan akun+sesi ini."""
    return form_token.token_sah(principal, sesi, token, domain=_DOMAIN_TOKEN, aksi=_AKSI_TOKEN)


def _kode_pesan(jalur_penuh: str) -> str:
    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    nilai = (kueri.get("pesan") or [""])[0]
    return nilai if nilai in kontak_pages.PESAN_SUKSES else ""


def _baca_form(penangan):
    """Form urlencoded kecil dengan kunci tunggal; None bila tidak sah."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None or penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        return None
    try:
        pasangan = urllib.parse.parse_qs(
            tubuh.decode("utf-8", "strict"), keep_blank_values=True,
            strict_parsing=bool(tubuh), max_num_fields=BATAS_KOLOM_FORM,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(nilai) != 1 for nilai in pasangan.values()):
        return None
    return {kunci: nilai[0] for kunci, nilai in pasangan.items()}


def _kirim_form(penangan, principal, nilai_wa: str, *, kode: int = 200,
                kode_pesan: str = "", galat: str = "") -> None:
    token = buat_token(principal, penangan._ambil_token())
    isi = kontak_pages.halaman_kontak(
        (principal.pengguna, principal.peran), token, nilai_wa,
        kode_pesan=kode_pesan, galat=galat,
    )
    penangan._kirim_privat(isi, kode)


def tangani_get(penangan, jalur: str) -> bool:
    """GET: form berisi nomor milik akun sesi sendiri (atau kosong)."""
    if jalur != RUTE:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan)
        return True
    with database.buka() as kon:
        baris = kontak_akun.ambil(kon, principal.id_akun)
    _kirim_form(
        penangan, principal, baris["wa"] if baris else "",
        kode_pesan=_kode_pesan(penangan.path),
    )
    return True


def _simpan(principal, wa: str) -> None:
    """Satu transaksi sendiri: upsert kontak di akun sesi lalu commit."""
    sekarang = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        kontak_akun.simpan(kon, principal.id_akun, wa, sekarang)
        kon.commit()


def _galat_laju(penangan, galat: GalatForm) -> None:
    if galat.status == 429:
        penangan._kirim(halaman_pesan(
            "Terlalu banyak permintaan",
            "<h1>Terlalu banyak permintaan</h1><p>Coba lagi sebentar.</p>"), 429)
    else:
        penangan._tolak_isian(galat.status)


def tangani_post(penangan, jalur: str) -> bool:
    """POST: validasi, simpan di akun sesi, lalu PRG ke halaman dengan kode pesan tetap."""
    if jalur != RUTE:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan)
        return True
    try:
        _batasi_laju(penangan, principal.pengguna)
    except GalatForm as galat:
        _galat_laju(penangan, galat)
        return True
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM:
        penangan._tolak_isian()
        return True
    if not token_sah(principal, penangan._ambil_token(), data["token"]):
        penangan._tolak_isian(403)
        return True
    wa = kontak_akun.normalisasi_wa(data["wa"])
    if wa is None:
        _kirim_form(
            penangan, principal, registration_contact.echo_wa(data),
            kode=400, galat=registration_contact.PESAN_WA_WAJIB,
        )
        return True
    _simpan(principal, wa)
    _alihkan(penangan, RUTE + "?pesan=tersimpan")
    return True

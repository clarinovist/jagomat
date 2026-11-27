"""Rute guru usulan jadwal tetap: `GET` dan `POST /guru/jadwal-tetap` (Fase 3d, WP2).

Identitas HANYA dari sesi: `guru_akun` = `id_akun` principal peran guru. Tidak ada id dari URL atau form.

Gerbang `guru_jadwal_tetap_aturan.guru_jadwal_tetap_aktif()` mati, atau principal bukan guru (admin, murid, mode lokal),
menjawab 404 identik rute tak dikenal (`lembaga_http._tidak_ada`) tanpa membaca atau membuat DB. Anonim sudah
dijawab palang sandi sebelum dispatcher ini.

Urutan POST, berhenti tanpa tulis pada langkah pertama yang gagal: gerbang dan principal (404), laju (kunci pengguna,
hanya setelah principal diketahui), baca form (400), token (403), buang `token` lalu `blok_dari_form` (400 generik),
`dasar.usul` (batas harian 409, galat lain 503). Sukses dan no-op sama-sama PRG 303 ke `?pesan=tersimpan`.
"""
from __future__ import annotations

import html
import logging
import urllib.parse
from typing import Optional

import form_token
import guru_jadwal_http as jadwal_http
import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as dasar
import guru_jadwal_tetap_pages as halaman
import lembaga_http
from learning_cycle_http import GalatForm, _batasi_laju
from support_pages import halaman_pesan

_log = logging.getLogger(__name__)

RUTE = "/guru/jadwal-tetap"
DOMAIN_TOKEN_JADWAL_TETAP = b"guru-jadwal-tetap-form-v1:"
AKSI_USUL = "usul"
KUNCI_TOKEN = "token"
PESAN_TERSIMPAN = "tersimpan"
BATAS_FORM = 2048
BATAS_KOLOM = len(aturan.KUNCI_FORM) + 1  # 28 field jadwal ditambah token
JUDUL_TOLAK = "Jadwal belum bisa disimpan"
TEKS_FORM_TIDAK_SAH = ("Isian jadwal tidak sah. Periksa tiap blok: jam dalam kelipatan 30 menit, minimal 60 menit, "
                       "mulai dan selesai diisi bersama, dan blok dalam satu hari tidak boleh tumpang tindih.")
TEKS_BATAS = (f"Anda sudah mengirim {aturan.BATAS_USULAN_PER_HARI} usulan dalam 24 jam terakhir. "
              "Coba lagi nanti.")
TEKS_GALAT_SIMPAN = "Jadwal belum bisa disimpan sekarang. Coba lagi sebentar."
TEKS_LAJU = "Coba lagi sebentar."


# --- token ------------------------------------------------------------------------------------

def _buat_token(principal, penangan) -> str:
    return form_token.buat_token(principal, penangan._ambil_token(), domain=DOMAIN_TOKEN_JADWAL_TETAP,
                                 aksi=AKSI_USUL)


def _token_sah(principal, penangan, token) -> bool:
    return form_token.token_sah(principal, penangan._ambil_token(), token, domain=DOMAIN_TOKEN_JADWAL_TETAP,
                                aksi=AKSI_USUL)


# --- baca keadaan (GET) -----------------------------------------------------------------------

def _blok_dari_baris(baris: Optional[dict]) -> Optional[tuple]:
    """Blok terurut dari teks tersimpan. None bila tak ada baris; teks tak sah melempar ValueError."""
    return None if baris is None else aturan.urai_blok(baris["blok"])


def _keadaan(guru_akun: str) -> dict:
    """Keadaan untuk halaman. Galat baca atau teks tersimpan tak sah = `tidak_terbaca`, tanpa data sama sekali."""
    try:
        aktif = _blok_dari_baris(dasar.aktif(guru_akun))
        menunggu = _blok_dari_baris(dasar.menunggu(guru_akun))
        ditolak = dasar.ditolak_terakhir(guru_akun) is not None
    except (dasar.GalatTetap, ValueError) as galat:
        _log.warning("jadwal tetap guru tidak terbaca: %s", type(galat).__name__)
        return {"tidak_terbaca": True, "aktif": None, "menunggu": None, "ditolak": False, "pilihan": ()}
    pilihan = menunggu if menunggu is not None else (aktif or ())
    return {"tidak_terbaca": False, "aktif": aktif, "menunggu": menunggu, "ditolak": ditolak, "pilihan": pilihan}


def _tersimpan(penangan) -> bool:
    kueri = urllib.parse.parse_qs(urllib.parse.urlsplit(penangan.path).query)
    return kueri.get("pesan", []) == [PESAN_TERSIMPAN]


def _kirim_halaman(penangan, principal, tersimpan: bool) -> None:
    keadaan = _keadaan(principal.id_akun)
    token = None if keadaan["tidak_terbaca"] else _buat_token(principal, penangan)
    tampilan = {**keadaan, "token": token, "tersimpan": tersimpan}
    penangan._kirim_privat(halaman.halaman_tetap(jadwal_http._ident(principal), tampilan))


# --- baca form (POST) -------------------------------------------------------------------------

def _baca_formulir(penangan) -> Optional[dict]:
    """Form urlencoded dengan kunci tunggal; field kosong dipertahankan. None bila tidak sah."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None or penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        return None
    try:
        pasangan = urllib.parse.parse_qs(
            tubuh.decode("utf-8", "strict"), keep_blank_values=True,
            strict_parsing=bool(tubuh), max_num_fields=BATAS_KOLOM,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(nilai) != 1 for nilai in pasangan.values()):
        return None
    return {kunci: nilai[0] for kunci, nilai in pasangan.items()}


def _tanpa_token(formulir: dict) -> dict:
    return {nama: nilai for nama, nilai in formulir.items() if nama != KUNCI_TOKEN}


def _teks_blok(penangan, formulir: dict) -> Optional[str]:
    """Teks kanonik dari 28 field formulir. Isian tak sah dibalas 400 generik tanpa gema; None setelah dibalas."""
    try:
        return aturan.kanonik(aturan.blok_dari_form(formulir))
    except ValueError:
        _kirim_tolak(penangan, 400, JUDUL_TOLAK, TEKS_FORM_TIDAK_SAH)
        return None


# --- balasan ----------------------------------------------------------------------------------

def _kirim_tolak(penangan, kode: int, judul: str, teks: str) -> None:
    isi = halaman_pesan(judul, f"<h1>{html.escape(judul)}</h1><p>{html.escape(teks)}</p>")
    penangan._kirim_privat(isi, kode)


def _kirim_galat_laju(penangan, galat: GalatForm) -> None:
    if galat.status == 429:
        _kirim_tolak(penangan, 429, JUDUL_TOLAK, TEKS_LAJU)
    else:
        penangan._tolak_isian(galat.status)


def _kirim_galat_simpan(penangan, galat: dasar.GalatTetap) -> None:
    if galat.kind == dasar.KIND_BATAS:
        _kirim_tolak(penangan, 409, JUDUL_TOLAK, TEKS_BATAS)
        return
    _log.warning("usulan jadwal tetap gagal disimpan: %s", galat.kind)
    _kirim_tolak(penangan, 503, JUDUL_TOLAK, TEKS_GALAT_SIMPAN)


# --- POST -------------------------------------------------------------------------------------

def _simpan(penangan, principal, teks_blok: str, kini: str) -> None:
    try:
        dasar.usul(guru_akun=principal.id_akun, blok=teks_blok, dibuat=kini)
    except dasar.GalatTetap as galat:
        _kirim_galat_simpan(penangan, galat)
        return
    lembaga_http._alihkan(penangan, f"{RUTE}?pesan={PESAN_TERSIMPAN}")


def _proses_post(penangan, principal, kini: str) -> None:
    try:
        _batasi_laju(penangan, principal.pengguna)
    except GalatForm as galat:
        _kirim_galat_laju(penangan, galat)
        return
    formulir = _baca_formulir(penangan)
    if formulir is None:
        penangan._tolak_isian()
        return
    if not _token_sah(principal, penangan, formulir.get(KUNCI_TOKEN)):
        penangan._tolak_isian(403)
        return
    teks_blok = _teks_blok(penangan, _tanpa_token(formulir))
    if teks_blok is None:
        return
    _simpan(penangan, principal, teks_blok, kini)


# --- dispatcher -------------------------------------------------------------------------------

def tangani_get(penangan, jalur: str) -> bool:
    """GET `/guru/jadwal-tetap`. False untuk jalur lain."""
    if jalur != RUTE:
        return False
    principal = jadwal_http._principal_guru(penangan)
    if principal is None or not aturan.guru_jadwal_tetap_aktif():
        lembaga_http._tidak_ada(penangan)
        return True
    _kirim_halaman(penangan, principal, _tersimpan(penangan))
    return True


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/guru/jadwal-tetap`. Dipanggil setelah palang sandi dan guard asal dispatcher."""
    if jalur != RUTE:
        return False
    principal = jadwal_http._principal_guru(penangan)
    if principal is None or not aturan.guru_jadwal_tetap_aktif():
        lembaga_http._tidak_ada(penangan)
        return True
    _proses_post(penangan, principal, jadwal_http._kini())
    return True

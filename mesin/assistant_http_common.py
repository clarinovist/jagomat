"""Primitive HTTP bersama untuk Pendamping."""
from __future__ import annotations

import html
import os
import re
import threading
import time
import urllib.parse

import assistant_navigation
import assistant_pages
import sessions


_BATAS_FORM = 12_000

_BATAS_PER_MENIT = 30

_riwayat_laju = {}

_kunci_laju = threading.Lock()

class GalatForm(ValueError):
    def __init__(self, pesan: str, status: int = 400):
        super().__init__(pesan)
        self.status = status

def aktif() -> bool:
    return os.environ.get("PENDAMPING_AKTIF", "0") == "1"

def _kirim_privat(penangan, isi: bytes, kode: int = 200) -> None:
    penangan.send_response(kode)
    penangan.send_header("Content-Type", "text/html; charset=utf-8")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("Referrer-Policy", "no-referrer")
    penangan.send_header("X-Robots-Tag", "noindex, nofollow")
    penangan.send_header("X-Frame-Options", "DENY")
    penangan.send_header(
        "Content-Security-Policy",
        "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
    )
    penangan.end_headers()
    penangan.wfile.write(isi)

def _kirim_host_privat(penangan, isi: bytes, kode: int = 200) -> None:
    """Respons host privat tanpa script atau koneksi pihak ketiga."""
    penangan.send_response(kode)
    penangan.send_header("Content-Type", "text/html; charset=utf-8")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("Referrer-Policy", "no-referrer")
    penangan.send_header("X-Robots-Tag", "noindex, nofollow")
    penangan.send_header("X-Frame-Options", "DENY")
    penangan.send_header(
        "Content-Security-Policy",
        "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
    )
    penangan.end_headers()
    penangan.wfile.write(isi)

def _redirect(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("Referrer-Policy", "no-referrer")
    penangan.send_header("X-Robots-Tag", "noindex, nofollow")
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()

def _principal(penangan):
    token = penangan._ambil_token()
    return sessions.ambil_principal_pendamping(token)

def _tolak_login(penangan, tujuan: str = '') -> None:
    _kirim_privat(
        penangan,
        assistant_pages._bingkai(
            "Perlu masuk",
            '<section class="pendamping-panel"><h1 id="judul-pendamping">Perlu masuk lagi</h1>'
            '<p>Pendamping hanya tersedia untuk akun orang tua dengan sesi terbaru.</p>'
            f'<p><a href="{html.escape(assistant_navigation.tautan_masuk(tujuan), quote=True)}">Masuk</a></p></section>',
        ),
        401,
    )

def _tidak_ada(penangan) -> None:
    _kirim_privat(
        penangan,
        assistant_pages._bingkai(
            "404", '<section class="pendamping-panel"><h1 id="judul-pendamping">Halaman tidak ada</h1></section>'
        ),
        404,
    )

def _usulan_berubah(penangan, galat, *, chat_id='', usulan_id='') -> None:
    """Gunakan penolakan aman yang sama untuk tinjauan dan konfirmasi."""
    _kirim_privat(
        penangan,
        assistant_pages._bingkai(
            "Usulan berubah",
            '<section class="pendamping-panel"><h1 id="judul-pendamping">Usulan perlu ditinjau ulang</h1>'
            f'<p role="alert">{html.escape(str(galat))}</p>'
            + (f'<p><a href="/pendamping/usulan/{html.escape(usulan_id)}">Tinjau kembali</a></p>'
               if usulan_id and 'kedaluwarsa' in str(galat).lower() else '')
            + (f'<p><a href="/pendamping/chat/{html.escape(chat_id)}">Kembali ke percakapan</a></p>' if chat_id else '')
            + '</section>',
        ),
        409,
    )

def _baca_form(penangan) -> dict[str, str]:
    asal = penangan.headers.get("Origin")
    situs = penangan.headers.get("Sec-Fetch-Site")
    if asal == "null":
        silang = situs != "same-origin"
    else:
        silang = bool(asal) and urllib.parse.urlsplit(asal).netloc != penangan.headers.get("Host")
    if (not asal and situs != "same-origin") or silang or situs == "cross-site":
        raise GalatForm("Permintaan harus berasal dari situs ini.", 403)
    panjang = penangan.headers.get("Content-Length", "0")
    if not re.fullmatch(r"[0-9]+", panjang) or penangan.headers.get("Transfer-Encoding"):
        raise GalatForm("Panjang isian tidak dikenal.")
    if int(panjang) > _BATAS_FORM:
        raise GalatForm("Isian terlalu besar.", 413)
    if penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        raise GalatForm("Format isian tidak dikenal.")
    try:
        mentah = penangan.rfile.read(int(panjang)).decode("utf-8")
        data = urllib.parse.parse_qs(
            mentah, keep_blank_values=True, errors="strict", max_num_fields=8
        )
    except (UnicodeError, ValueError) as galat:
        raise GalatForm("Isian tidak dapat dibaca.") from galat
    if any(len(nilai) != 1 for nilai in data.values()):
        raise GalatForm("Isian ganda tidak diizinkan.")
    return {nama: nilai[0] for nama, nilai in data.items()}

def _batasi_laju(penangan, account_id: str) -> None:
    kini = time.monotonic()
    ip = penangan.client_address[0] if penangan.client_address else "unknown"
    kunci = (account_id, ip)
    with _kunci_laju:
        aktif = tuple(waktu for waktu in _riwayat_laju.get(kunci, ()) if kini - waktu < 60)
        if len(aktif) >= _BATAS_PER_MENIT:
            raise GalatForm("Terlalu banyak permintaan. Coba lagi sebentar.", 429)
        _riwayat_laju[kunci] = (*aktif, kini)

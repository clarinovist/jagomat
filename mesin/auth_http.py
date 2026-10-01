"""Rute HTTP login dan logout.

Renderer login tetap disediakan façade ``web.Penangan`` agar API pemanggil lama
bertahan. Modul ini hanya mengatur parsing, autentikasi, sesi, cookie, dan redirect.
"""
from __future__ import annotations

import urllib.parse

import auth
import sessions
from assistant_navigation import tujuan_lanjut


def tangani_get(penangan, jalur: str) -> bool:
    """Render GET /masuk dengan tujuan lanjut yang sudah dikanonkan."""
    if jalur != "/masuk":
        return False
    galat = ""
    q = urllib.parse.parse_qs(
        urllib.parse.urlparse(penangan.path).query,
        keep_blank_values=True,
    )
    if q.get("galat"):
        galat = q["galat"][0]
    nilai_lanjut = q.get("lanjut", [])
    lanjut = tujuan_lanjut(nilai_lanjut[0]) if len(nilai_lanjut) == 1 else ""
    penangan._kirim(
        penangan._halaman_masuk_stitch(galat=galat, lanjut=lanjut)
    )
    return True


def proses_masuk(penangan, data: dict) -> None:
    """Autentikasi dan buat sesi, dengan rate limit serta redirect per peran."""
    nama = (data.get("nama") or "").strip()
    sandi = data.get("sandi") or ""
    lanjut = tujuan_lanjut(data.get("lanjut", ""))
    ip = penangan.client_address[0] if penangan.client_address else "unknown"
    if not nama or not sandi:
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Nama dan sandi wajib diisi.", lanjut=lanjut
            )
        )
        return
    if sessions.sedang_diblokir(nama, ip):
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Terlalu banyak percobaan. Coba lagi 15 menit lagi.",
                lanjut=lanjut,
            ),
            429,
        )
        return
    principal = auth.autentikasi(nama, sandi)
    if principal is None:
        sessions.catat_gagal(nama, ip)
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Nama atau sandi belum cocok. Coba lagi, atau minta gurumu.",
                lanjut=lanjut,
            )
        )
        return
    token = sessions.buat_dari_principal(principal)
    if token is None:
        sessions.catat_gagal(nama, ip)
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Akun berubah saat masuk. Coba lagi.", lanjut=lanjut
            ),
            409,
        )
        return
    sessions.catat_berhasil(principal.pengguna, ip)
    tujuan = (
        "/murid" if principal.peran == "murid"
        else "/admin" if principal.peran == "admin"
        else "/guru"
    )
    if principal.peran == "guru" and lanjut:
        tujuan = lanjut
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Set-Cookie", penangan._set_cookie(token))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def tangani_post(penangan, jalur: str) -> bool:
    """Tangani POST login/logout tanpa mengambil rute akun lain."""
    if jalur == "/masuk":
        panjang = int(penangan.headers.get("Content-Length", 0) or 0)
        mentah = penangan.rfile.read(panjang).decode("utf-8") if panjang else ""
        bidang = urllib.parse.parse_qs(mentah, keep_blank_values=True)
        data = {kunci: nilai[0] for kunci, nilai in bidang.items()}
        if len(bidang.get("lanjut", [])) != 1:
            data.pop("lanjut", None)
        penangan._handle_masuk(data)
        return True
    if jalur != "/keluar":
        return False

    token = penangan._ambil_token()
    if token:
        sessions.hapus(token)
    penangan.send_response(303)
    penangan.send_header("Location", "/masuk")
    penangan.send_header("Set-Cookie", penangan._set_cookie(None))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True

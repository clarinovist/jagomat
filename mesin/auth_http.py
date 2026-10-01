"""Rute HTTP login dan logout.

Modul ini memiliki renderer login, parsing, autentikasi, sesi, cookie, dan redirect.
Façade ``web.Penangan`` tetap tersedia agar API pemanggil lama bertahan.
"""
from __future__ import annotations

import html
import urllib.parse

import auth
import brand
import design_tokens as T
import sessions
from assistant_navigation import tujuan_lanjut


def halaman_masuk(galat: str = "", *, lanjut: str = "") -> bytes:
    """Render form masuk editorial; façade lama tetap berada di ``web``."""
    from style_stitch import gaya_stitch
    from teacher_style import SKRIP_MATA_SANDI

    lanjut = tujuan_lanjut(lanjut)
    isian_lanjut = (
        f'<input type="hidden" name="lanjut" value="{html.escape(lanjut)}">'
        if lanjut else ""
    )
    kabar = (
        '<div class="masuk-galat-st" id="galat-masuk" role="alert" aria-atomic="true">'
        '<b>Periksa kembali</b>'
        f'<p>{html.escape(galat)}</p></div>' if galat else ""
    )
    deskripsi_galat = ' aria-describedby="galat-masuk"' if galat else ""
    body = f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul("Masuk"))}</title>
{brand.tag_kepala()}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">
<style>{gaya_stitch()}</style></head>
<body class="st">
<main class="masuk-badan-st" aria-labelledby="judul-masuk">
  <div class="masuk-kepala-st">
    <a class="masuk-brand-st" href="/" aria-label="{html.escape(T.NAMA_PRODUK)} — kembali ke beranda">
      {brand.mark("topbar", kelas="ik-owl")}
      <span class="nama-brand">{html.escape(T.NAMA_PRODUK)}</span>
      <span class="masuk-beranda-st" aria-hidden="true">/ beranda</span>
    </a>
  </div>
  <div class="masuk-panel-st">
    <div class="masuk-catatan-st" aria-hidden="true">
      <p class="masuk-alis-st">LEMBAR BARU, SEMANGAT BARU</p>
      <p class="masuk-pesan-st">Mulai lagi,<br><span>dengan caramu.</span></p>
      <div class="masuk-buku-st">
        <span class="masuk-coret-st">✳</span>
        <img class="masuk-maskot-st" src="/aset/maskot-menyapa-v3-240.png"
             width="240" height="240" alt="">
        <span class="masuk-catatan-kecil-st">Satu langkah dulu.</span>
      </div>
    </div>
    <section class="masuk-kartu-st" aria-labelledby="judul-masuk">
      <div class="masuk-sapaan-st">
        <p class="masuk-alis-st">AKUN BELAJARMU</p>
        <h1 class="masuk-judul-st" id="judul-masuk">Selamat datang kembali</h1>
        <p class="masuk-sub-st">{html.escape(T.TAGLINE)}</p>
      </div>
      {kabar}
      <form class="masuk-form-st" method="post" action="/masuk"{deskripsi_galat}>
        {isian_lanjut}
        <div class="masuk-field-st">
          <label for="nama">Nama pengguna</label>
          <input type="text" id="nama" name="nama" autocomplete="username"
                 aria-describedby="petunjuk-nama" required>
          <p class="masuk-petunjuk-st" id="petunjuk-nama">Gunakan nama pengguna saat mendaftar,
          atau akun dari orang tua atau guru.</p>
        </div>
        <div class="masuk-field-st">
          <label for="sandi">Kata sandi</label>
          <input type="password" id="sandi" name="sandi" autocomplete="current-password" required>
        </div>
        <button class="masuk-tombol-st" type="submit">
          Masuk <span aria-hidden="true">→</span>
        </button>
      </form>
      <p class="masuk-link-st"><a href="/lupa-sandi">Lupa sandi?</a></p>
    </section>
  </div>
</main>
<script>{SKRIP_MATA_SANDI}</script>
</body></html>"""
    return body.encode()


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

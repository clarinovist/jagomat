"""Rute HTTP login dan logout.

Modul ini memiliki renderer login, parsing, autentikasi, sesi, cookie, dan redirect.
Façade ``web.Penangan`` tetap tersedia agar API pemanggil lama bertahan.
"""
from __future__ import annotations

import html
import logging
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import auth
import brand
import database
import design_tokens as T
import funnel_flag
import ip_klien
import kontak_akun
import laju_masuk
import sessions
from assistant_navigation import tujuan_lanjut as _tujuan_pendamping

RUTE_LANJUT_MULAI = "/cek-kemampuan/mulai"
RUTE_LANJUT_HASIL = "/cek-kemampuan/hasil"
# Dua tujuan cek persis; hanya berlaku saat sakelar funnel hidup dan hanya
# diikuti untuk peran guru (lihat `proses_masuk`). Bukan prefiks, bukan URL bebas.
TUJUAN_LANJUT_CEK = frozenset({RUTE_LANJUT_MULAI, RUTE_LANJUT_HASIL})

# DRAF: teks final menunggu persetujuan Pemilik
COPY_SERAH_ALIS = "UNTUK ORANG TUA"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_SERAH_JUDUL = "Serahkan ke Ayah/Bunda"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_SERAH_SUB = (
    "Masukkan sandi untuk melihat hasil. Hasil hanya untuk orang tua, jadi anak "
    "tidak melihat skor atau catatan kelemahannya sendiri."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_SERAH_LIPAT = "Anak mengerjakan di HP sendiri?"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_SERAH_LIPAT_ISI = (
    "Di HP anak hanya muncul layar selesai. Hasilnya terbuka di akun orang tua: "
    "masuk lewat HP Anda dengan nama pengguna dan sandi."
)
_IKON_GEMBOK = (
    '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/></svg>'
)


def tujuan_lanjut(nilai: str) -> str:
    """Tujuan lanjut login: dua rute cek persis (funnel hidup) atau aturan Pendamping."""
    if type(nilai) is str and nilai in TUJUAN_LANJUT_CEK and funnel_flag.funnel_aktif():
        return nilai
    return _tujuan_pendamping(nilai)


def _sapaan_masuk(lanjut: str) -> str:
    """Judul kartu login; varian serah-ke-orang-tua hanya untuk lanjut ke hasil cek."""
    if lanjut == RUTE_LANJUT_HASIL:
        return (
            '<div class="masuk-sapaan-st">'
            f'<span class="funnel-gembok-st">{_IKON_GEMBOK}</span>'
            f'<p class="masuk-alis-st">{html.escape(COPY_SERAH_ALIS)}</p>'
            f'<h1 class="masuk-judul-st" id="judul-masuk">{html.escape(COPY_SERAH_JUDUL)}</h1>'
            f'<p class="masuk-sub-st">{html.escape(COPY_SERAH_SUB)}</p></div>'
        )
    return f"""<div class="masuk-sapaan-st">
        <p class="masuk-alis-st">AKUN BELAJARMU</p>
        <h1 class="masuk-judul-st" id="judul-masuk">Selamat datang kembali</h1>
        <p class="masuk-sub-st">{html.escape(T.TAGLINE)}</p>
      </div>"""


def _lipat_serah(lanjut: str) -> str:
    if lanjut != RUTE_LANJUT_HASIL:
        return ""
    return (
        '<details class="funnel-lipat-st">'
        f"<summary>{html.escape(COPY_SERAH_LIPAT)}</summary>"
        f"<p>{html.escape(COPY_SERAH_LIPAT_ISI)}</p></details>"
    )


def halaman_masuk(galat: str = "", *, lanjut: str = "") -> bytes:
    """Render form masuk editorial; façade lama tetap berada di ``web``."""
    from font_lokal import tag_font_lokal, tanpa_impor_font_cdn
    from style_stitch import gaya_stitch
    from offline_browser import SKRIP_OFFLINE
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
{tag_font_lokal()}<style>{tanpa_impor_font_cdn(gaya_stitch())}</style></head>
<body class="st">
<main class="masuk-badan-st" aria-labelledby="judul-masuk">
  <div class="masuk-kepala-st">
    <a class="masuk-brand-st" href="/" aria-label="{html.escape(T.NAMA_PRODUK)} — kembali ke beranda">
      {brand.mark("topbar", kelas="ik-owl")}
      <span class="nama-brand">{html.escape(T.NAMA_PRODUK)}</span>    </a>
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
      {_sapaan_masuk(lanjut)}
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
      <p class="masuk-link-st"><a href="/lupa-sandi">Lupa sandi?</a></p>{_lipat_serah(lanjut)}
    </section>
  </div>
</main>
<script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_OFFLINE}</script>
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


_log = logging.getLogger(__name__)
# Login tidak boleh tertahan oleh penulisan aktivitas (mis. DB sibuk saat registrasi).
TIMEOUT_AKTIVITAS_DETIK = 0.5


def _catat_aktivitas_masuk(principal) -> None:
    """Majukan `aktivitas_terakhir` kontak akun yang baru login (fail-open).

    Hanya akun yang sudah punya baris kontak yang ditulis, maksimal sekali per
    hari. Kegagalan apa pun (DB sibuk, berkas hilang, galat lain) tidak boleh
    menggagalkan login; hanya jenis galatnya yang dicatat, tanpa nomor atau
    id_akun.
    """
    try:
        uri = Path(database.BAWAAN).resolve().as_uri() + "?mode=rw"
        waktu = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        kon = sqlite3.connect(uri, uri=True, timeout=TIMEOUT_AKTIVITAS_DETIK)
        try:
            kontak_akun.sentuh_aktivitas(kon, principal.id_akun, waktu)
            kon.commit()
        finally:
            kon.close()
    except Exception as galat:  # noqa: BLE001 - fail-open disengaja
        _log.warning("Catat aktivitas login gagal: %s", type(galat).__name__)


def proses_masuk(penangan, data: dict) -> None:
    """Autentikasi dan buat sesi, dengan rate limit serta redirect per peran."""
    nama = (data.get("nama") or "").strip()
    sandi = data.get("sandi") or ""
    lanjut = tujuan_lanjut(data.get("lanjut", ""))
    ip = ip_klien.ip_klien(penangan.headers, penangan.client_address)
    if not nama or not sandi:
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Nama dan sandi wajib diisi.", lanjut=lanjut
            )
        )
        return
    if laju_masuk.sedang_diblokir(nama, ip):
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
        laju_masuk.catat_gagal(nama, ip)
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Nama atau sandi belum cocok. Coba lagi, atau minta gurumu.",
                lanjut=lanjut,
            )
        )
        return
    token = sessions.buat_dari_principal(principal)
    if token is None:
        laju_masuk.catat_gagal(nama, ip)
        penangan._kirim(
            penangan._halaman_masuk_stitch(
                "Akun berubah saat masuk. Coba lagi.", lanjut=lanjut
            ),
            409,
        )
        return
    laju_masuk.catat_berhasil(principal.pengguna, ip)
    _catat_aktivitas_masuk(principal)
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
        tubuh = penangan._baca_tubuh(8192)
        if tubuh is None:
            penangan._tolak_isian(413)
            return True
        try:
            mentah = tubuh.decode("utf-8", "strict")
        except UnicodeDecodeError:
            penangan._tolak_isian(400)
            return True
        bidang = urllib.parse.parse_qs(
            mentah, keep_blank_values=True, max_num_fields=32
        )
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
        import tirai_orang_tua
        tirai_orang_tua.tutup_sesi(token)
    penangan.send_response(303)
    penangan.send_header("Location", "/masuk")
    penangan.send_header("Set-Cookie", penangan._set_cookie(None))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()
    return True

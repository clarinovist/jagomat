"""Aset brand: berkas statis (/aset/<nama>) + tag kepala HTML.

Aplikasi ini tidak punya penyaji berkas statis umum — satu-satunya yang ada
sebelum ini adalah /lampiran/berkas/<id> (foto lembar anak, ber-palang).
Modul ini menambah permukaan kedua yang sengaja dibuat sesempit mungkin:

  - **Allow-list**, bukan penggabungan path. Nama yang tidak terdaftar =
    404 sebelum menyentuh filesystem, jadi traversal `../` mustahil secara
    konstruksi, bukan karena sanitasi yang harus benar.
  - **Publik**: favicon dibutuhkan browser sebelum login. Rute ini
    didaftarkan sebelum palang guru — karena itu isinya hanya berkas brand
    statis. Tidak menyentuh basis data, tidak menyentuh data anak.
  - Cache satu tahun + immutable: berkasnya tidak pernah berubah tanpa
    ganti nama.

`manifest.json` sengaja TIDAK berupa berkas: ia di-generate dari
design_tokens supaya nama produk & warna tema tetap bersumber dari satu
tempat. Menyalin nama ke berkas JSON statis berarti brand punya dua sumber
kebenaran yang bisa berbeda diam-diam.
"""
from __future__ import annotations

import functools
import html
import json
from pathlib import Path

import design_tokens as T
from adegan_awal_data import IKON_DIDUKUNG
from font_lokal import ASET_FONT

# Domain kanonis produksi. og:image, og:url, dan tautan sesi butuh URL
# absolut agar crawler serta fallback berbagi tanpa JS memakai domain resmi.
URL_SITUS = "https://jagomat.id"

def _esc(teks: str) -> str:
    return html.escape(teks, quote=True)


FOLDER_ASET = Path(__file__).resolve().parent / "aset"

# Allow-list = kontrak rute. Menambah berkas ke mesin/aset/ tanpa
# mendaftarkannya di sini berarti berkas itu tidak terlayani (dan guard
# test_brand.py akan merah).
ASET: dict[str, str] = {
    "mark-sederhana.svg": "image/svg+xml",
    "mark-penuh.svg": "image/svg+xml",
    "mark-tinta.svg": "image/svg+xml",
    "lockup-horizontal.svg": "image/svg+xml",
    "lockup-cetak.svg": "image/svg+xml",
    "lockup-hero.svg": "image/svg+xml",
    "favicon.svg": "image/svg+xml",
    "favicon.ico": "image/x-icon",
    "apple-touch-180.png": "image/png",
    "pwa-192.png": "image/png",
    "pwa-512.png": "image/png",
    "og-image.png": "image/png",
    # Aset maskot lama tetap terlayani untuk halaman yang masih di cache.
    # Isi URL immutable tidak diganti; halaman baru memakai versi v3.
    "maskot-netral-240.png": "image/png",
    "maskot-netral-96.png": "image/png",
    "maskot-merayakan-240.png": "image/png",
    "maskot-merayakan-96.png": "image/png",
    "maskot-menunjuk-240.png": "image/png",
    "maskot-menunjuk-96.png": "image/png",
}

# Enam crop dari satu master yang disetujui, masing-masing 240px dan 96px.
# Nama berkas berversi agar cache immutable tidak menampilkan maskot lama.
POSE_MASKOT = ("menyapa", "menunjuk", "berpikir", "membaca", "menulis", "merayakan")
ASET.update({
    f"maskot-{pose}-{versi}-{px}.png": "image/png"
    for pose in POSE_MASKOT for versi in ("v2", "v3") for px in (240, 96)
})

# Sepuluh pose tambahan (disetujui Pemilik 24 Nov 2026), satu gambar per pose, gaya sama
# dengan v3. Berkas berversi v4; pose v3 tidak diganti. Pemakaian per layar menyusul.
POSE_MASKOT_V4 = (
    "semangat", "menyemangati", "terkejut", "berhitung", "memeriksa", "istirahat",
    "bingung", "menunggu", "mencari", "terkunci",
)
ASET.update({
    f"maskot-{pose}-v4-{px}.png": "image/png"
    for pose in POSE_MASKOT_V4 for px in (240, 96)
})

# Ikon benda untuk adegan visual Matematika Awal; daftar namanya satu-satunya
# di `adegan_awal_data.IKON_DIDUKUNG`. WebP RGBA 192x192, URL immutable bernama
# versi; isi berkas tidak diganti.
ASET.update({f"ikon-{nama}-v1.webp": "image/webp" for nama in IKON_DIDUKUNG})

# Webfont merek same-origin (daftar tunggal di `font_lokal.BERKAS_FONT`).
ASET.update(ASET_FONT)

NAMA_MANIFEST = "manifest.json"


@functools.lru_cache(maxsize=None)
def _isi(nama: str) -> bytes:
    """Isi berkas aset, di-cache di memori.

    Aset kecil dan tidak pernah berubah selama proses hidup, jadi
    membacanya sekali lebih murah daripada I/O per permintaan favicon.
    """
    return (FOLDER_ASET / nama).read_bytes()


def manifest() -> bytes:
    """manifest.json PWA — di-generate, bukan berkas statis.

    Nama produk dan warna tema berasal dari design_tokens supaya tidak ada
    nilai brand yang terduplikasi di berkas JSON terpisah.
    """
    isi = {
        "name": T.NAMA_PRODUK,
        "short_name": T.NAMA_PRODUK,
        "description": T.TAGLINE,
        "start_url": "/",
        "display": "standalone",
        "background_color": T.LATAR_MURID,
        "theme_color": T.AKSEN_MURID_UTAMA,
        "icons": [
            {"src": "/aset/pwa-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/aset/pwa-512.png", "sizes": "512x512", "type": "image/png"},
            {
                "src": "/aset/pwa-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return json.dumps(isi, ensure_ascii=False, indent=2).encode("utf-8")


def berkas(nama: str) -> tuple[bytes, str] | None:
    """(isi, mime) untuk nama aset, atau None kalau tidak diizinkan.

    Nama diperiksa lewat allow-list SEBELUM menyentuh filesystem — jadi
    `../`, path absolut, dan nama berkas aplikasi tidak pernah sampai ke
    lapisan I/O sama sekali.
    """
    if nama == NAMA_MANIFEST:
        return manifest(), "application/json; charset=utf-8"
    mime = ASET.get(nama)
    if mime is None:
        return None
    try:
        return _isi(nama), mime
    except OSError:
        return None


def tag_kepala(og: dict[str, str] | None = None, cetak: bool = False) -> str:
    """Blok <link>+<meta> brand untuk <head> — ditulis sekali, dipakai semua.

    Sebelum ini tidak satu pun halaman punya favicon: tab browser
    menampilkan ikon kosong di landing, halaman masuk, dan halaman anak.
    Menyalin blok ini per template berarti template ke-15 lahir tanpa
    favicon tanpa ada yang sadar — guard di test_brand.py menolak itu.

    og  = {"judul": ..., "deskripsi": ..., "jalur": "/"} untuk halaman
          publik yang di-share (WhatsApp/Facebook). URL-nya dibuat absolut
          dari URL_SITUS: crawler menolak path relatif.
    cetak = True untuk lembar A4 — favicon saja, tanpa og/manifest yang
            tidak ada artinya di kertas.
    """
    baris = [
        '<link rel="icon" href="/aset/favicon.svg" type="image/svg+xml">',
        '<link rel="alternate icon" href="/aset/favicon.ico" sizes="any">',
        '<link rel="apple-touch-icon" href="/aset/apple-touch-180.png">',
    ]
    if cetak:
        return "\n".join(baris)
    baris += [
        '<link rel="manifest" href="/aset/manifest.json">',
        f'<meta name="theme-color" content="{T.AKSEN_MURID_UTAMA}">',
        f'<meta name="application-name" content="{_esc(T.NAMA_PRODUK)}">',
    ]
    if og:
        judul = og.get("judul") or T.NAMA_PRODUK
        deskripsi = og.get("deskripsi") or T.TAGLINE
        url = URL_SITUS + (og.get("jalur") or "/")
        baris += [
            f'<meta name="description" content="{_esc(deskripsi)}">',
            f'<meta property="og:title" content="{_esc(judul)}">',
            f'<meta property="og:description" content="{_esc(deskripsi)}">',
            f'<meta property="og:type" content="website">',
            f'<meta property="og:url" content="{_esc(url)}">',
            f'<meta property="og:image" content="{_esc(URL_SITUS)}/aset/og-image.png">',
            f'<meta property="og:site_name" content="{_esc(T.NAMA_PRODUK)}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{_esc(judul)}">',
            f'<meta name="twitter:description" content="{_esc(deskripsi)}">',
            f'<meta name="twitter:image" content="{_esc(URL_SITUS)}/aset/og-image.png">',
        ]
    return "\n".join(baris)


def mark(ukuran: str = "topbar", kelas: str = "") -> str:
    """<img> lambang Jagomat — satu lambang untuk semua permukaan.

    Sebelum ini ada EMPAT lambang berbeda yang dipakai sebagai logo: glyph
    'school' (topi wisuda) di topbar guru, 'pets' (jejak kaki) di halaman
    anak, SVG owl di halaman murid legacy, dan teks polos tanpa ikon di
    topbar guru non-Stitch. Anak melihat jejak kaki, orang tua melihat topi
    wisuda — dua produk berbeda di mata pengguna yang sama.

    ukuran: "topbar" (<=32px, mark sederhana), "badge", atau "hero"
    (>=48px, mark penuh dengan detail). Nilainya dari design_tokens supaya
    tidak lahir lagi beda 20,8 vs 21,6 px.
    """
    px = {
        "topbar": T.LOGO_TOPBAR,
        "badge": T.LOGO_BADGE,
        "hero": T.LOGO_HERO,
    }[ukuran]
    # Mark sederhana dirancang untuk ukuran kecil (detail dibuang supaya
    # tetap terbaca); mark penuh untuk ukuran besar.
    berkas_mark = "mark-penuh.svg" if ukuran == "hero" else "mark-sederhana.svg"
    atribut_kelas = f' class="{kelas}"' if kelas else ""
    return (
        f'<img src="/aset/{berkas_mark}" alt=""{atribut_kelas} '
        f'width="{px.rstrip("px")}" height="{px.rstrip("px")}" '
        f'style="width:{px};height:{px};flex:none">'
    )


def judul(halaman: str = "") -> str:
    """Judul <title> dengan pola tunggal: "<Halaman> · Jagomat".

    Audit 3 Sep: pemisah campur (— di sebagian halaman, · di sebagian
    lain) dan ENAM halaman tanpa nama brand sama sekali di tab browser —
    "Akun", "Laporan Putri", "Panel Pengelola", "Sesi #1 — Cetak", "Sesi #1
    — Lampiran", "Hapus sesi #3?". Tab yang tidak menyebut produk membuat
    orang tua dengan banyak tab tidak tahu mana yang ini.

    Nama halaman yang SUDAH mengandung brand (dengan pemisah apa pun)
    dinormalisasi, bukan ditumpuk jadi "Daftar — Jagomat · Jagomat".
    """
    nama = (halaman or "").strip()
    if not nama or nama == T.NAMA_PRODUK:
        return T.NAMA_PRODUK
    for pemisah in (" · ", " — ", " &middot; ", " - "):
        akhiran = f"{pemisah}{T.NAMA_PRODUK}"
        if nama.endswith(akhiran):
            nama = nama[: -len(akhiran)].strip()
            break
    if not nama:
        return T.NAMA_PRODUK
    return f"{nama} · {T.NAMA_PRODUK}"


def maskot(pose: str = "menyapa", px: int = 240, alt: str = "", kelas: str = "") -> str:
    """<img> maskot ayam jago.

    Maskot BUKAN logo: ia hiasan/pendamping, bukan penanda identitas. Karena
    itu default `alt=""` — pembaca layar melewatinya, dan anak yang memakai
    pembaca layar tidak mendengar "gambar ayam" sebelum tiap sapaan. Isi
    `alt` hanya kalau maskotnya benar-benar membawa informasi.

    px: 240 (sapaan/banner) atau 96 (inline kecil). Dua berkas terpisah,
    bukan satu besar yang di-scale CSS — halaman anak sering dibuka di HP.
    """
    if pose not in POSE_MASKOT and pose not in POSE_MASKOT_V4:
        raise ValueError(f"pose maskot tidak dikenal: {pose!r}")
    if px not in (240, 96):
        raise ValueError(f"ukuran maskot tidak tersedia: {px}")
    versi = "v3" if pose in POSE_MASKOT else "v4"
    berkas_maskot = f"maskot-{pose}-{versi}-{px}.png"
    atribut_kelas = f' class="{kelas}"' if kelas else ""
    return (
        f'<img src="/aset/{berkas_maskot}" alt="{_esc(alt)}"{atribut_kelas} '
        f'width="{px}" height="{px}" loading="lazy" decoding="async" '
        f'style="max-width:{px}px;height:auto">'
    )

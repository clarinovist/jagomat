"""Webfont merek same-origin (keputusan pemilik 22 Nov 2026).

Plus Jakarta Sans (`FONT_HEADLINE`) dan Be Vietnam Pro (`FONT_BODY`) disajikan dari
`/aset/` sebagai TTF apa adanya (lisensi SIL OFL), jadi halaman guru yang memuat
data anak, termasuk yang privat, tetap memakai font merek tanpa memanggil host
pihak ketiga. Nama berkas berversi karena rute `/aset/` bersifat immutable;
mengganti isi berkas berarti menaikkan `-v1` dan mendaftarkan nama baru.

Modul ini tidak mengimpor `brand` agar `brand.ASET` bisa memakai `ASET_FONT`.
"""

from __future__ import annotations

MIME_FONT = "font/ttf"

# (keluarga CSS, bobot, nama berkas di mesin/aset/). Satu-satunya daftar font lokal.
BERKAS_FONT: tuple[tuple[str, int, str], ...] = (
    ("Be Vietnam Pro", 400, "font-be-vietnam-pro-400-v1.ttf"),
    ("Be Vietnam Pro", 600, "font-be-vietnam-pro-600-v1.ttf"),
    ("Be Vietnam Pro", 700, "font-be-vietnam-pro-700-v1.ttf"),
    ("Plus Jakarta Sans", 400, "font-plus-jakarta-sans-400-v1.ttf"),
    ("Plus Jakarta Sans", 600, "font-plus-jakarta-sans-600-v1.ttf"),
    ("Plus Jakarta Sans", 700, "font-plus-jakarta-sans-700-v1.ttf"),
    ("Plus Jakarta Sans", 800, "font-plus-jakarta-sans-800-v1.ttf"),
)

# Daftar untuk allow-list rute `/aset/` (`brand.ASET`).
ASET_FONT: dict[str, str] = {nama: MIME_FONT for _, _, nama in BERKAS_FONT}

# Baris @import Google Fonts di `GAYA_STITCH` (satu baris utuh). Shell guru
# membuangnya karena font merek sudah lokal; Material Symbols tetap lewat
# <link> khusus halaman nonprivat.
IMPOR_FONT_CDN = (
    "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700"
    "&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');"
)


def _aturan(keluarga: str, bobot: int, nama: str) -> str:
    return (
        f'@font-face{{font-family:"{keluarga}";font-style:normal;font-weight:{bobot};'
        f'font-display:swap;src:url("/aset/{nama}") format("truetype");}}'
    )


CSS_FONT_LOKAL = "\n".join(_aturan(*baris) for baris in BERKAS_FONT)


def tag_font_lokal() -> str:
    """Tag <style> berisi @font-face lokal, disisipkan di <head> semua halaman guru."""
    return f"<style>{CSS_FONT_LOKAL}</style>"


def tanpa_impor_font_cdn(css: str) -> str:
    """Salinan CSS tanpa @import font Google; tidak mengubah argumen."""
    return css.replace(IMPOR_FONT_CDN, "")

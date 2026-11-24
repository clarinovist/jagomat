"""Bingkai presentasional untuk pesan singkat; tanpa akses data atau routing."""

import html

import brand
import design_tokens as T
from font_lokal import tag_font_lokal, tanpa_impor_font_cdn
from murid_shell import bungkus_murid, kepala_murid, topbar_murid
from style_stitch import gaya_stitch


JUDUL_TIDAK_ADA = "404"


def _hiasan(judul: str) -> str:
    """Maskot untuk semua halaman 404. Satu masukan -> satu body, jadi 404 'tak ada' dan 'bukan milikmu' tetap identik."""
    if judul != JUDUL_TIDAK_ADA:
        return ""
    return brand.maskot("bingung", 96, kelas="pesan-maskot-st")


def _catatan(isi: str, hiasan: str = "") -> str:
    return f"""<section class="pesan-catatan-st">
<p class="pesan-alis-st">CATATAN DARI {html.escape(T.NAMA_PRODUK.upper())}</p>
{hiasan}{isi}
</section>"""


def _topbar_pesan() -> str:
    """Lockup topbar guru (`st-topbar`) tanpa menu dan tanpa tautan: halaman pesan bisa anonim."""
    return (f'<header class="st-topbar"><span class="brand">{brand.mark("topbar")}'
            f'<span class="nama">{html.escape(T.NAMA_PRODUK)}</span></span></header>')


def halaman_pesan(judul: str, isi: str) -> bytes:
    """Bungkus markup tepercaya dari router tanpa mengubah pesan atau aksinya.

    ``isi`` sudah di-escape oleh pemanggil bila memuat nilai dinamis. Tidak
    menambah tautan: kapabilitas halaman token tetap terbatas pada sesi itu.
    Input sama menghasilkan body identik, termasuk semua jalur 404.
    """
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}{tag_font_lokal()}<style>{tanpa_impor_font_cdn(gaya_stitch())}</style></head>
<body class="st"><div class="bungkus-st shell-guru-st">{_topbar_pesan()}
<main class="pesan-editorial-st">{_catatan(isi, _hiasan(judul))}</main></div></body></html>""".encode()


def halaman_pesan_murid(judul: str, isi: str) -> bytes:
    """Varian `halaman_pesan` untuk jalur anak: shell murid (topbar bersama, font lokal).

    Slot kanan topbar sengaja kosong: tidak menambah tautan, jadi halaman token
    (`/mulai/<token>`) tidak pernah menautkan ke /murid. Input sama menghasilkan
    body identik, termasuk semua jalur 404.
    """
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}{kepala_murid(gaya_stitch())}</head>
<body class="st">{bungkus_murid(topbar_murid() + '<main class="pesan-editorial-st">' + _catatan(isi, _hiasan(judul)) + '</main>')}</body></html>""".encode()

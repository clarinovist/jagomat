"""Bingkai presentasional untuk pesan singkat; tanpa akses data atau routing."""

import html

import brand
import design_tokens as T
from murid_shell import bungkus_murid, kepala_murid, topbar_murid
from style_stitch import gaya_stitch


def _catatan(isi: str) -> str:
    return f"""<section class="pesan-catatan-st">
<p class="pesan-alis-st">CATATAN DARI {html.escape(T.NAMA_PRODUK.upper())}</p>
{isi}
</section>"""


def halaman_pesan(judul: str, isi: str) -> bytes:
    """Bungkus markup tepercaya dari router tanpa mengubah pesan atau aksinya.

    ``isi`` sudah di-escape oleh pemanggil bila memuat nilai dinamis. Tidak
    menambah tautan: kapabilitas halaman token tetap terbatas pada sesi itu.
    Input sama menghasilkan body identik, termasuk semua jalur 404.
    """
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}<style>{gaya_stitch()}</style></head>
<body class="st"><main class="pesan-editorial-st">
<header class="pesan-brand-st">{brand.mark("topbar")}<span>{html.escape(T.NAMA_PRODUK)}</span></header>
{_catatan(isi)}
</main></body></html>""".encode()


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
<body class="st">{bungkus_murid(topbar_murid() + '<main class="pesan-editorial-st">' + _catatan(isi) + '</main>')}</body></html>""".encode()

"""Komponen HTML bersama halaman anak: chip status, pil filter, disclosure, banner tautan, kartu sesi."""
from html import escape

NADA_CHIP = ("perhatian", "baik", "netral", "info")


def chip_status(teks, nada="netral"):
    if nada not in NADA_CHIP:
        raise ValueError("nada chip tidak dikenal: %r" % (nada,))
    return '<span class="anak-chip-st anak-chip-%s-st">%s</span>' % (nada, escape(str(teks)))


def pil_filter(teks, href, aktif=False):
    atribut = ' aria-current="true"' if aktif else ""
    return '<a class="anak-pil-st" href="%s"%s>%s</a>' % (escape(href, quote=True), atribut, escape(str(teks)))


def disclosure(judul, isi_html, terbuka=False):
    return '<details class="anak-disclosure-st"%s><summary>%s</summary>%s</details>' % (
        " open" if terbuka else "", escape(str(judul)), isi_html)


def banner_tautan(isi_html, href, teks_tautan):
    return ('<a class="anak-banner-st" href="%s"><span>%s</span>'
            '<span class="anak-banner-tautan-st">%s</span></a>') % (
                escape(href, quote=True), isi_html, escape(str(teks_tautan)))


def kartu_sesi(*, judul, sub, tanggal_html="", chip_html="", aksi_html="", peringatan=""):
    tanggal = '<div class="anak-kartu-tanggal-st">%s</div>' % tanggal_html if tanggal_html else ""
    catatan = '<span class="anak-kartu-peringatan-st">%s</span>' % escape(str(peringatan)) if peringatan else ""
    return ('<div class="anak-kartu-sesi-st">%s<div class="anak-kartu-isi-st"><strong>%s</strong>'
            '<small>%s</small>%s</div>%s%s</div>') % (
                tanggal, escape(str(judul)), escape(str(sub)), catatan, chip_html, aksi_html)

"""Shell bersama halaman anak: satu topbar, satu kolom, ikon lokal, font same-origin.

Keputusan pemilik 22 Nov 2026 (audit area anak, Fase 1): semua permukaan murid (beranda,
lembar kerja, hasil, pesan, Latihan Lomba, masuk) memakai topbar yang sama, logo + nama
di kiri dengan ukuran yang sama dan satu slot aksi di kanan, di dalam satu kolom
`T.LEBAR_KONTEN` yang sama di HP maupun desktop. Font merek disajikan dari `/aset/`
(`font_lokal`) dan ikon berupa SVG inline, jadi halaman anak tidak memanggil host
pihak ketiga. Murni render: tanpa DB, tanpa skrip.

Semua aturan diikat ke `.murid-wadah-st` / `.murid-topbar-st` supaya tidak bocor ke halaman
guru yang memuat CSS yang sama.
"""
from __future__ import annotations

import html

import brand
import design_tokens as T
from font_lokal import tag_font_lokal, tanpa_impor_font_cdn

ALAMAT_BERANDA = "/murid"
ALAMAT_KELUAR = "/keluar"
PANAH_KEMBALI = '<span aria-hidden="true">←</span>'

_BENTUK_IKON = {
    "panah": '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    "buku": '<path d="M12 6c-3-2-7-2-9-1v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-2-1-6-1-9 1Zm0 0v14"/>',
    "grafik": '<path d="M4 20h17M7 16v-5m5 5V5m5 11V8"/>',
    "bilangan": '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 7h8M8 12h1m6 0h1m-8 5h1m6 0h1"/>',
    "jam": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "lipat": '<path d="m9 5 7 7-7 7"/>',
    "kamera": '<path d="M4 8h3l2-3h6l2 3h3v11H4Z"/><circle cx="12" cy="13" r="3.5"/>',
    "tutup": '<path d="M6 6l12 12M18 6 6 18"/>',
    "piala": '<path d="M8 4h8v5a4 4 0 0 1-8 0Zm0 2H5v1a3 3 0 0 0 3 3m8-4h3v1a3 3 0 0 1-3 3m-4 3v4m-3 3h6"/>',
    "lampu": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.3 1 2.1h5c0-.8.4-1.6 1-2.1A6 6 0 0 0 12 3Z"/>',
}


def ikon_murid(nama: str) -> str:
    """Ikon dekoratif lokal (aria-hidden, stroke currentColor); setiap kontrol tetap bernama teks."""
    if nama not in _BENTUK_IKON:
        raise ValueError(f"ikon murid tidak dikenal: {nama!r}")
    return (
        '<svg class="murid-ikon-st" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{_BENTUK_IKON[nama]}</svg>'
    )


def topbar_murid(kanan: str = "") -> str:
    """Satu bentuk header anak: logo + nama di kiri, `kanan` (markup tepercaya) di kanan.

    Slot kanan boleh kosong (tautan HP tanpa login tidak boleh menautkan ke /murid).
    Slot adalah anak langsung header supaya lebar dan posisinya sama di semua halaman.
    """
    return (
        '<header class="murid-topbar-st">'
        f'<span class="murid-brand-st">{brand.mark("topbar")}<span>{html.escape(T.NAMA_PRODUK)}</span></span>'
        f'{kanan}</header>'
    )


def aksi_topbar(alamat: str, teks: str, awalan: str = "") -> str:
    """Tautan slot kanan ("Tutup", "Beranda", "Sesi lain"); `awalan` = markup ikon/panah tepercaya."""
    return f'<a href="{html.escape(alamat, quote=True)}">{awalan}{html.escape(teks)}</a>'


def tombol_keluar() -> str:
    """Form keluar akun murid untuk slot kanan beranda."""
    return f'<form method="post" action="{ALAMAT_KELUAR}"><button type="submit">Keluar</button></form>'


def bungkus_murid(isi: str) -> str:
    """Wadah kolom tunggal; topbar dan isi halaman menjadi anak langsungnya."""
    return f'<div class="murid-wadah-st">{isi}</div>'


def kepala_murid(css: str, cetak: bool = True) -> str:
    """Isi <head> bersama: @font-face lokal + <style> (@import font Google dibuang) + CSS shell.

    `cetak` menambah aturan sembunyikan topbar di kertas; Latihan Lomba tidak dicetak
    dan menjaga CSS-nya bebas `display:none` (kontrol tersembunyi hanya lewat sr-saja).
    """
    return f"{tag_font_lokal()}<style>{tanpa_impor_font_cdn(css)}{GAYA_SHELL_MURID}{GAYA_CETAK_MURID if cetak else ''}</style>"


_W = ".murid-wadah-st"
_TOPBAR = ".murid-topbar-st"
# Selektor aksi kanan: dipakai bersama oleh aturan dasar dan hover/fokus.
AKSI_TOPBAR = f"{_TOPBAR} > a, {_TOPBAR} button"

GAYA_SHELL_MURID = f"""
/* Shell murid: kolom tunggal T.LEBAR_KONTEN + gutter, sama di HP dan desktop. */
.murid-ikon-st {{ display: block; width: 1.35rem; height: 1.35rem; flex: none; }}
{_W} {{
  width: 100%; max-width: calc({T.LEBAR_KONTEN} + 2 * {T.ANAK_GUTTER});
  margin-inline: auto; padding: {T.SP_5} {T.ANAK_GUTTER} 0;
}}
@media (max-width: {T.ANAK_BATAS_HP}) {{
  {_W} {{ padding-inline: {T.SP_4}; padding-top: {T.SP_4}; }}
}}
{_W} > :is(.kerja-badan-st, .pesan-editorial-st, .murid-kanvas-st, .isi) {{
  max-width: none; margin-inline: 0; padding-inline: 0;
}}

/* Topbar: lockup kiri (ukuran sama di semua halaman), satu slot aksi kanan. */
{_TOPBAR} {{
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_3};
  min-height: {T.TARGET_SENTUH}; margin: 0 0 {T.SP_5}; padding: 0 0 {T.SP_4};
  border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; font-family: {T.FONT_HEADLINE};
}}
{_TOPBAR} .murid-brand-st {{
  display: inline-flex; align-items: center; flex: none; gap: {T.SP_2};
  min-height: {T.TARGET_SENTUH}; color: {T.AKSEN_TEAL_TUA};
  font: 800 1.5rem/1.4 {T.FONT_HEADLINE}; letter-spacing: -.04em;
}}
{_TOPBAR} > :not(.murid-brand-st) {{ margin-left: auto; }}
{_TOPBAR} form {{ margin: 0; }}
{AKSI_TOPBAR} {{
  display: inline-flex; align-items: center; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} {T.SP_3}; border: 0; border-radius: {T.RADIUS_SEDANG}; background: none;
  color: {T.AKSEN_TEAL_TUA}; font: 700 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE};
  text-decoration: none; cursor: pointer;
}}
{_TOPBAR} > a:hover, {_TOPBAR} button:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
{_TOPBAR} :is(a, button):focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
{_TOPBAR} .murid-ikon-st {{ width: 1rem; height: 1rem; }}
"""

GAYA_CETAK_MURID = f"""
@media print {{
  {_TOPBAR} {{ display: none; }}
}}
"""

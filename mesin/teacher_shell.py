"""Bingkai, topbar, dan shell bersama halaman orang tua/guru."""
from __future__ import annotations

import html

import brand
import design_tokens as T
import profile_workspace
from style_stitch import GAYA_STITCH
from teacher_style import (
    GAYA_GURU as GAYA,
    SKRIP_CEGAH_KIRIM_GANDA,
    SKRIP_MATA_SANDI,
)


def _badge_peran(peran: str) -> str:
    """Penanda peran pengelola yang dipakai kedua varian topbar."""
    if peran == "admin":
        return '<span class="badge-peran badge-peran-admin">Pengelola</span>'
    if peran == "guru":
        return '<span class="badge-peran badge-peran-guru">Orang Tua / Guru</span>'
    return ""


def _topbar(pengguna: str, peran: str) -> str:
    """Topbar legacy halaman pengelola dengan menu CSS-only."""
    if peran == "admin":
        brand_href, item = "/admin", (
            '<a href="/admin">Dashboard admin</a>'
            '<a href="/admin/ai">Pengaturan AI</a>'
            '<a href="/akun?section=akun">Ganti sandi</a>'
        )
    else:
        brand_href, item = "/guru", '<a href="/akun">Akun &amp; Siswa</a>'
    siapa = html.escape(pengguna) if pengguna else ""
    return (
        f'<div class="topbar">'
        f'<a class="brand" href="{brand_href}">'
        f'{brand.mark("topbar")}<span>{T.NAMA_PRODUK}</span></a>'
        f'<nav class="topbar-navigasi">'
        f'<details class="menu-pengguna">'
        f'<summary>{siapa} {_badge_peran(peran)}</summary>'
        f'<div class="menu-isi">{item}'
        f'<div class="menu-pisah"></div>'
        f'<form method="post" action="/keluar" style="margin:0">'
        f'<button type="submit">Keluar</button>'
        f"</form></div></details></nav></div>"
    )


def _topbar_stitch(pengguna: str, peran: str) -> str:
    """Topbar Stitch dengan menu akun CSS-only dan satu pintu keluar."""
    if peran == "admin":
        brand_href, item = "/admin", (
            '<a href="/admin">Dashboard admin</a>'
            '<a href="/admin/ai">Pengaturan AI</a>'
            '<a href="/akun?section=akun">Ganti sandi</a>'
        )
    else:
        brand_href, item = "/guru", '<a href="/akun">Akun &amp; Siswa</a>'
    siapa = html.escape(pengguna) if pengguna else ""
    ringkasan_akun = (
        '<summary><span class="identitas-akun-st">'
        f'{_badge_peran(peran)}<span class="nama-akun-st">{siapa}</span></span>'
        '<span class="panah-akun-st" aria-hidden="true">⌄</span></summary>'
        if siapa else '<summary aria-label="Menu pendamping">Menu</summary>'
    )
    return (
        '<div class="st-topbar">'
        f'<a class="brand" href="{brand_href}">'
        f'{brand.mark("topbar")}'
        f'<span class="nama">{html.escape(T.NAMA_PRODUK)}</span>'
        "</a>"
        '<nav class="topbar-navigasi" aria-label="Menu akun">'
        '<details class="menu-pengguna">'
        f'{ringkasan_akun}<div class="menu-isi">{item}'
        '<div class="menu-pisah"></div>'
        '<form method="post" action="/keluar" style="margin:0">'
        '<button type="submit" class="cta">Keluar</button>'
        "</form></div></details></nav></div>"
    )


def _halaman(
    judul: str, isi: str, ident: tuple[str, str] | None = None,
    stitch: bool = False, kelas_bungkus: str = "", id_utama: str = "",
    privat: bool = False,
) -> bytes:
    """Bingkai halaman pengelola legacy maupun Stitch."""
    if stitch:
        from style_stitch import gaya_stitch, CSS_SESI
        batang = _topbar_stitch(*ident) if ident else ""
        kelas = f"bungkus-st {kelas_bungkus}".strip()
        buka_isi = (
            f'<main class="sesi-badan-st" aria-labelledby="{html.escape(id_utama)}">'
            if id_utama else '<div class="sesi-badan-st">'
        )
        tutup_isi = "</main>" if id_utama else "</div>"
        font = "" if privat else """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Material+Symbols+Outlined&display=swap" rel="stylesheet">"""
        gaya = gaya_stitch()
        if 'akun-editorial-st' in kelas_bungkus.split():
            from question_variants_ui import GAYA_VARIASI
            gaya += GAYA_VARIASI
        if privat:
            gaya = gaya.replace(
                "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');",
                "",
            )
        return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}
{font}
<style>{GAYA}{gaya}{CSS_SESI}</style></head>
<body class="st"><div class="{kelas}">{batang}{buka_isi}{isi}{tutup_isi}</div>{'' if privat else f'<script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script>'}</body></html>""".encode()
    batang = _topbar(*ident) if ident else ""
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala()}<style>{GAYA}</style></head>
<body><div class="bungkus">{batang}{isi}</div><script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script></body></html>""".encode()


def _halaman_stitch(
    judul: str, isi: str, ident: tuple[str, str] | None = None,
    kelas_bungkus: str = "", privat: bool = False,
) -> bytes:
    """Bingkai halaman Stitch untuk dashboard dan workspace anak."""
    batang = _topbar_stitch(*ident) if ident else ""
    kelas = f"bungkus-st {kelas_bungkus}".strip()
    font = "" if privat else """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap" rel="stylesheet">"""
    gaya = GAYA_STITCH
    if "profil-workspace-st" in kelas_bungkus:
        from question_variants_ui import GAYA_VARIASI
        gaya += profile_workspace.GAYA_PROFIL + GAYA_VARIASI
    if privat:
        gaya = gaya.replace(
            "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');",
            "",
        )
    skrip = "" if privat else f"<script>{SKRIP_MATA_SANDI}</script><script>{SKRIP_CEGAH_KIRIM_GANDA}</script>"
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(brand.judul(judul))}</title>
{brand.tag_kepala(cetak=privat)}
{font}
<style>{gaya}</style></head>
<body class="st"><div class="{kelas}">{batang}{isi}</div>{skrip}</body></html>""".encode()

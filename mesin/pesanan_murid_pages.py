"""Bingkai halaman pesanan untuk akun anak (murid): shell murid + gaya kartu/tombol akun.

Murni render, tanpa DB. Isi kartu (status, transfer, QR) dirakit oleh `pesanan_pages` yang sama
dengan sisi guru; modul ini hanya membungkusnya dengan topbar/kolom murid dan menyediakan
kartu "Pesan" untuk anak yang belum punya pesanan. Tidak ada kontak orang tua di sini.
"""
from __future__ import annotations

import brand
import design_tokens as T
from account_style import GAYA_AKUN
from cek_pages import _a, _e
from murid_shell import PANAH_KEMBALI, aksi_topbar, bungkus_murid, kepala_murid, topbar_murid
from style_stitch import gaya_stitch

KELAS_UTAMA = "pendamping-editorial-st akun-editorial-st akun-sempit-st funnel-halaman-st"
COPY_JUDUL_PESAN = "Pesan Peta Kemampuan"
COPY_TOMBOL_PESAN = "Pesan Peta Kemampuan"
# Tautan kembali topbar murid untuk Paket, Latihan Harian, dan Peta (dimasuki dari Halaman Ayah/Bunda).
# TUJUAN sama dengan `orang_tua_style.RUTE`, LABEL sama dengan `orang_tua_pages.COPY_JUDUL` (dijaga tes).
TUJUAN_ORANG_TUA = "/murid/orang-tua"
LABEL_ORANG_TUA = "Halaman Ayah/Bunda"
# Penekanan nominal bayar Peta: hanya dimuat di shell murid (kelas `pesanan-nominal` tidak ada di halaman guru).
GAYA_PESANAN_MURID = f"""
.pesanan-nominal {{ font-size: {T.UKURAN_BAGIAN_STITCH}; font-weight: 800; }}
"""


def halaman_murid(judul: str, id_judul: str, isi: str, beranda: str, label_beranda: str,
                  css_tambahan: str = "") -> bytes:
    """Halaman pesanan dalam shell murid; `isi` adalah markup tepercaya dari renderer pesanan.

    `css_tambahan` (CSS tepercaya dari modul gaya, bukan masukan pengguna) ditambahkan setelah `GAYA_AKUN`;
    kosong (bawaan) berarti byte halaman sama dengan sebelum parameter ini ada (halaman Peta pesanan).
    """
    topbar = topbar_murid(aksi_topbar(beranda, label_beranda, PANAH_KEMBALI))
    utama = f'<main class="{KELAS_UTAMA}" aria-labelledby="{_a(id_judul)}">{isi}</main>'
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(brand.judul(judul))}</title>
{brand.tag_kepala()}{kepala_murid(gaya_stitch() + GAYA_AKUN + css_tambahan)}</head>
<body class="st">{bungkus_murid(topbar + utama)}</body></html>""".encode()


def harga_tebal(kalimat: str, nominal: str) -> str:
    """Kalimat harga ter-escape dengan `nominal` (sudah diformat, mis. `Rp49.000`) dibungkus `pesanan-nominal`.

    Teks yang tampak tetap sama. Tanpa `nominal`, atau bila tidak ditemukan dalam kalimat, hasilnya kalimat biasa.
    """
    teks, sorot = _e(kalimat), _e(nominal)
    if not sorot or sorot not in teks:
        return teks
    return teks.replace(sorot, f'<strong class="pesanan-nominal">{sorot}</strong>', 1)


def kartu_pesan(rute_pesan: str, token: str, harga: str, nominal: str = "") -> str:
    """Kartu pertama kali memesan: harga dari domain (nominal ditebalkan bila diberikan) + satu tombol POST bertoken."""
    return (
        '<div class="kartu-st">'
        f"<h2>{_e(COPY_JUDUL_PESAN)}</h2><p>{harga_tebal(harga, nominal)}</p>"
        f'<form method="post" action="{_a(rute_pesan)}">'
        f'<input type="hidden" name="token" value="{_a(token)}">'
        '<p class="akun-aksi-sandi">'
        f'<button type="submit" class="tombol-utama-akun">{_e(COPY_TOMBOL_PESAN)}</button></p>'
        "</form></div>"
    )

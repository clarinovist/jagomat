"""Halaman `/akun/kontak`: guru melengkapi nomor WhatsApp akunnya sendiri.

Hanya HTML native (tanpa JS). Penjelasan memakai `COPY_FUNNEL_WA` dari
`registration_contact` supaya teksnya satu sumber. Satu-satunya tempat nomor
muncul adalah atribut `value` input milik pemiliknya (di-escape); tidak pernah
di pesan galat, judul, atau URL.
"""
from __future__ import annotations

import html

import kontak_akun
import registration_contact
from teacher_shell import _halaman

PESAN_SUKSES = {"tersimpan": "Nomor WhatsApp sudah disimpan."}
KELAS_BUNGKUS = "pendamping-editorial-st akun-editorial-st akun-sempit-st"


def _kabar(kode_pesan: str, galat: str) -> str:
    pesan = PESAN_SUKSES.get(kode_pesan, "")
    isi = f'<div class="pesan" role="status">{html.escape(pesan)}</div>' if pesan else ""
    if galat:
        isi += f'<div class="pesan galat" role="alert">{html.escape(galat)}</div>'
    return isi


def _form(token: str, nilai_wa: str) -> str:
    return (
        '<div class="kartu-st"><form method="post" action="/akun/kontak">'
        f'<input type="hidden" name="token" value="{html.escape(token, quote=True)}">'
        '<label for="wa-kontak">Nomor WhatsApp</label>'
        '<input id="wa-kontak" type="tel" name="wa" required inputmode="tel" '
        'autocomplete="tel" placeholder="mis. 0812 3456 7890" '
        f'maxlength="{kontak_akun.PANJANG_MASUKAN_MAKS}" '
        f'aria-describedby="petunjuk-wa-kontak" value="{html.escape(nilai_wa, quote=True)}">'
        f'<p class="sub" id="petunjuk-wa-kontak">'
        f'{html.escape(registration_contact.COPY_FUNNEL_WA)}</p>'
        '<p class="akun-aksi-sandi">'
        '<button type="submit" class="tombol-utama-akun">Simpan nomor</button>'
        '<a href="/akun">Kembali ke akun</a></p>'
        "</form></div>"
    )


def halaman_kontak(
    ident: tuple[str, str],
    token: str,
    nilai_wa: str = "",
    *,
    kode_pesan: str = "",
    galat: str = "",
) -> bytes:
    """Form kontak untuk guru; `nilai_wa` hanya nomor milik pemilik sesi atau echo-nya."""
    return _halaman(
        "Nomor WhatsApp",
        '<div class="jejak"><a href="/akun">&larr; Akun</a></div>'
        '<header class="editorial-kepala-st"><div>'
        '<p class="editorial-alis-st">AKUN KELUARGA</p>'
        '<h1 id="judul-kontak">Nomor WhatsApp</h1>'
        '<p class="sub">Lengkapi nomor WhatsApp Anda sebelum membuat pesanan.</p>'
        f"</div></header>{_kabar(kode_pesan, galat)}{_form(token, nilai_wa)}",
        ident=ident,
        stitch=True,
        kelas_bungkus=KELAS_BUNGKUS,
        id_utama="judul-kontak",
        privat=True,
        keluar_topbar=False,
    )

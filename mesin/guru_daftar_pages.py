"""Isi halaman daftar guru mandiri (`/daftar?peran=guru`; gerbang env DAFTAR_GURU).

Renderer terpisah: `landing.halaman_daftar` memilihnya hanya saat `mode_guru` benar, sehingga form lama tidak berubah
byte-per-byte. Hanya nama pengguna, sandi, dan persetujuan; tanpa profil anak, kontak, atau PIN. Semua isian di-escape dan sandi
tidak pernah dikembalikan ke halaman. Tanpa JS baru (toggle mata sandi dari skrip kerangka publik).
"""
from __future__ import annotations

import daftar_anak_pages as bentuk
import daftar_cek_pages as cek

RUTE = "/daftar?peran=guru"
COPY_JUDUL = "Daftar sebagai guru"
COPY_SAPA = "Halo, Bapak/Ibu Guru! Buat akun untuk mulai memakai Jagomat."
COPY_NAMA = "Nama pengguna"
COPY_PETUNJUK_NAMA = (
    "Dipakai untuk masuk: tanpa spasi (3–40 karakter), huruf, angka, titik, garis bawah, atau tanda hubung."
)
COPY_PETUNJUK_SANDI = "Minimal 8 karakter. Simpan baik-baik; tim tidak bisa melihat sandi Anda."
COPY_SETUJU = (
    "Saya menyetujui "
    '<a href="/syarat-penggunaan">Syarat Penggunaan</a> dan memahami '
    '<a href="/kebijakan-privasi">Kebijakan Privasi</a>.'
)
COPY_TOMBOL = "Buat akun guru"
COPY_KAKI = "Tanpa email. Untuk bergabung ke lembaga Jagomat, hubungi tim setelah mendaftar."

_PERSETUJUAN = (
    '<div class="daftar-persetujuan-st"><label class="koreksi-centang-st" for="setuju">'
    '<input type="checkbox" id="setuju" name="setuju" value="1" required>'
    f"<span>{COPY_SETUJU}</span></label></div>"
)


def isi_daftar_guru(*, kotak: str = "", deskripsi: str = "", token: str = "", nama: str = "") -> str:
    """Isi `<main>` form daftar guru; pemanggil membungkus dengan kerangka publik."""
    akun = (
        bentuk._field("nama", COPY_NAMA, "nama", nilai=nama, petunjuk=COPY_PETUNJUK_NAMA,
                      ekstra=' autocomplete="username" maxlength="40"')
        + bentuk._field("sandi", "Sandi", "sandi", tipe="password", petunjuk=COPY_PETUNJUK_SANDI,
                        ekstra=' autocomplete="new-password" minlength="8"')
    )
    return (
        '<main class="funnel-alur-st funnel-daftar-st" aria-labelledby="judul-daftar">'
        f"{cek._appbar()}"
        f'<p class="funnel-gelembung-st">{bentuk._e(COPY_SAPA)}</p>'
        f'<h1 class="funnel-alur-judul-st" id="judul-daftar">{bentuk._e(COPY_JUDUL)}</h1>'
        f"{kotak}"
        f'<form class="masuk-form-st funnel-form-st" method="post" action="{RUTE}"{deskripsi}>'
        f"{token}"
        '<section class="funnel-seksi-st" aria-labelledby="judul-seksi-akun">'
        f'{cek._judul_seksi(1, "Akun masuk", "judul-seksi-akun")}{akun}</section>'
        f"{_PERSETUJUAN}"
        '<button class="masuk-tombol-st funnel-cta-st" type="submit">'
        f'{COPY_TOMBOL} <span aria-hidden="true">&rarr;</span></button></form>'
        f'<p class="funnel-kaki-st">{bentuk._e(COPY_KAKI)}</p></main>'
    )

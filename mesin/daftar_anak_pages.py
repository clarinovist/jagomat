"""Isi halaman daftar mode anak (`/daftar` saat sakelar DAFTAR_AKUN_ANAK hidup dan lembaga antrean siap).

Renderer terpisah dari form daftar biasa dan form jalur cek: `landing.halaman_daftar` memilihnya hanya saat
`mode_anak` benar, sehingga form lama tidak berubah byte-per-byte. Satu form untuk orang tua mendaftarkan
anak: nama login anak, sandi anak (toggle mata dari skrip kerangka publik), nama lengkap anak, kelas, WA orang
tua, persetujuan orang tua/wali, dan PIN tirai opsional (4 digit + ulangi). Server tetap otoritatif.

Tanpa JS baru. Semua nilai isian di-escape; sandi dan PIN tidak pernah dikembalikan ke halaman. Nomor
WhatsApp hanya muncul di atribut `value` input (di-escape) saat validasi gagal.
"""
from __future__ import annotations

import html

import daftar_cek_pages as cek
import kontak_akun

COPY_JUDUL = "Daftarkan anak"
COPY_SAPA = "Halo, Bunda/Ayah! Isi data anak di sini, lalu anak bisa langsung mulai belajar."
COPY_NAMA_LOGIN = "Nama login anak"
COPY_PETUNJUK_LOGIN = (
    "Dipakai anak untuk masuk: tanpa spasi (3–40 karakter), huruf, angka, titik, garis bawah, atau tanda hubung."
)
COPY_SANDI = "Sandi anak"
COPY_PETUNJUK_SANDI = "Minimal 8 karakter. Simpan baik-baik; anak memakainya untuk masuk."
COPY_NAMA_LENGKAP = "Nama lengkap anak"
COPY_PETUNJUK_LENGKAP = "Wajib diisi (1–80 karakter). Dipakai tim agar anak tidak tertukar."
COPY_KELAS = "Kelas berapa sekarang?"
COPY_PIN = "PIN untuk Bunda/Ayah (opsional)"
COPY_PIN_ULANG = "Ulangi PIN"
COPY_PETUNJUK_PIN = (
    "4 angka untuk menutup halaman Bunda/Ayah di akun anak. Boleh dikosongkan; ini tirai, bukan pengaman data."
)
COPY_WA_PETUNJUK = (
    "Nomor WhatsApp Bunda/Ayah dipakai tim untuk mengirim hasil dan mengonfirmasi jadwal. "
    "Hanya tim yang melihatnya; tidak pernah ditampilkan ke anak."
)
COPY_SETUJU = (
    "Saya orang tua/wali anak ini, dan saya menyetujui "
    '<a href="/syarat-penggunaan">Syarat Penggunaan</a> dan memahami '
    '<a href="/kebijakan-privasi">Kebijakan Privasi</a>.'
)
COPY_TOMBOL = "Daftarkan anak &amp; mulai"
COPY_KAKI = "Tanpa email. Satu akun untuk satu anak."


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def _field(id_, label, nama, *, tipe="text", nilai="", petunjuk="", ekstra="", wajib=True) -> str:
    id_petunjuk = "petunjuk-" + id_
    nilai_attr = ' value="%s"' % _e(nilai) if nilai != "" else ""
    return (
        '<div class="masuk-field-st">'
        f'<label for="{id_}">{_e(label)}</label>'
        f'<input type="{tipe}" id="{id_}" name="{nama}"{" required" if wajib else ""} '
        f'aria-describedby="{id_petunjuk}"{ekstra}{nilai_attr}>'
        f'<p class="daftar-petunjuk-st" id="{id_petunjuk}">{_e(petunjuk)}</p></div>'
    )


def _bagian_akun(nama: str) -> str:
    return (
        _field("nama", COPY_NAMA_LOGIN, "nama", nilai=nama, petunjuk=COPY_PETUNJUK_LOGIN,
               ekstra=' autocomplete="username" maxlength="40"')
        + _field("sandi", COPY_SANDI, "sandi", tipe="password", petunjuk=COPY_PETUNJUK_SANDI,
                 ekstra=' autocomplete="new-password" minlength="8"')
    )


def _bagian_anak(nama_lengkap: str, kelas_sekolah) -> str:
    pil = "".join(cek._pil_kelas(k, kelas_sekolah) for k in cek.KELAS_PILIHAN)
    return (
        _field("nama-lengkap-anak", COPY_NAMA_LENGKAP, "nama_lengkap", nilai=nama_lengkap,
               petunjuk=COPY_PETUNJUK_LENGKAP, ekstra=' maxlength="80" autocomplete="off"')
        + '<fieldset class="funnel-kelas-st">'
        f"<legend>{_e(COPY_KELAS)}</legend>"
        f'<div class="funnel-kelas-grid-st">{pil}</div></fieldset>'
    )


def _bagian_orang_tua(wa: str) -> str:
    pin = ' inputmode="numeric" pattern="[0-9]{4}" maxlength="4" autocomplete="off"'
    return (
        _field("wa-daftar", "Nomor WhatsApp orang tua", "wa", tipe="tel", nilai=wa, petunjuk=COPY_WA_PETUNJUK,
               ekstra=' autocomplete="tel" inputmode="tel" maxlength="%d"' % kontak_akun.PANJANG_MASUKAN_MAKS)
        + _field("pin", COPY_PIN, "pin", tipe="password", petunjuk=COPY_PETUNJUK_PIN, wajib=False, ekstra=pin)
        + _field("pin-ulang", COPY_PIN_ULANG, "pin_ulang", tipe="password", petunjuk="Samakan dengan PIN di atas.",
                 wajib=False, ekstra=pin)
    )


_PERSETUJUAN = (
    '<div class="daftar-persetujuan-st"><label class="koreksi-centang-st" for="setuju">'
    '<input type="checkbox" id="setuju" name="setuju" value="1" required>'
    f"<span>{COPY_SETUJU}</span></label></div>"
)


def isi_daftar_anak(
    *, kotak: str = "", deskripsi: str = "", token: str = "", nama: str = "", nama_lengkap: str = "",
    kelas_sekolah=None, wa: str = "", jalur_cek: bool = False,
) -> str:
    """Isi `<main>` form daftar mode anak; pemanggil membungkus dengan kerangka publik.

    `jalur_cek` meneruskan penanda `jalur=cek` agar tautan lama /daftar?jalur=cek tetap sah saat dikirim ulang.
    """
    penanda = '<input type="hidden" name="jalur" value="cek">' if jalur_cek else ""
    return (
        '<main class="funnel-alur-st funnel-daftar-st" aria-labelledby="judul-daftar">'
        f"{cek._appbar()}"
        f'<p class="funnel-gelembung-st">{_e(COPY_SAPA)}</p>'
        f'<h1 class="funnel-alur-judul-st" id="judul-daftar">{_e(COPY_JUDUL)}</h1>'
        f"{kotak}"
        f'<form class="masuk-form-st funnel-form-st" method="post" action="/daftar"{deskripsi}>'
        f"{token}{penanda}"
        '<section class="funnel-seksi-st" aria-labelledby="judul-seksi-anak">'
        f'{cek._judul_seksi(1, "Data anak", "judul-seksi-anak")}{_bagian_anak(nama_lengkap, kelas_sekolah)}</section>'
        '<section class="funnel-seksi-st" aria-labelledby="judul-seksi-akun">'
        f'{cek._judul_seksi(2, "Akun masuk anak", "judul-seksi-akun")}{_bagian_akun(nama)}</section>'
        '<section class="funnel-seksi-st" aria-labelledby="judul-seksi-ortu">'
        f'{cek._judul_seksi(3, "Untuk Bunda/Ayah", "judul-seksi-ortu")}{_bagian_orang_tua(wa)}</section>'
        f"{_PERSETUJUAN}"
        '<button class="masuk-tombol-st funnel-cta-st" type="submit">'
        f'{COPY_TOMBOL} <span aria-hidden="true">&rarr;</span></button></form>'
        f'<p class="funnel-kaki-st">{_e(COPY_KAKI)}</p></main>'
    )

"""Isi halaman daftar jalur cek (`/daftar?jalur=cek`, funnel Fase 3).

Renderer terpisah dari form daftar biasa: `landing.halaman_daftar` memilihnya
hanya saat `jalur_cek` benar (sakelar funnel hidup), jadi form lama tidak
berubah byte-per-byte. Tetap SATU form: akun dan data anak dikirim ke
`/daftar` dalam satu transaksi, hanya tampilannya dua bagian bernomor.

Tanpa JS baru. Tab "Sudah punya akun" adalah tautan ke login dengan `lanjut`
kembali ke halaman siap mulai; pilihan kelas adalah radio native bergaya.
Nilai isian di-escape; nomor WhatsApp hanya muncul di atribut `value`.
"""
from __future__ import annotations

import html

import brand
import design_tokens as T
import registration_contact

RUTE_MASUK_CEK = "/masuk?lanjut=/cek-kemampuan/mulai"
KELAS_PILIHAN = (1, 2, 3, 4, 5, 6)
COPY_APPBAR = "Cek Kemampuan gratis"
COPY_SAPA = "Halo! Yuk lihat di langkah mana anak mulai bingung. Gratis."
COPY_TAB_BARU = "Buat akun gratis"
COPY_TAB_LAMA = "Sudah punya akun"
COPY_JUDUL = "Buat akun orang tua"
COPY_SANDI = "Minimal 8 karakter. Simpan baik-baik, nanti dipakai untuk membuka hasil."
COPY_ANAK_SAPA = "Siapa jagoan yang mau dicek hari ini?"
COPY_ANAK_NAMA = "Cukup nama panggilan atau inisial. Nama ini yang menyapa anak di layar."
COPY_KELAS_LABEL = "Kelas berapa sekarang?"
COPY_KELAS_BANTUAN = "Wajib dipilih. Soal menyesuaikan kelas ini (Kurikulum Merdeka)."
COPY_KELAS_WAJIB = "Pilih kelas anak dulu, ya. Soal cek menyesuaikan kelasnya."
COPY_TOMBOL = "Buat akun & lanjut"
COPY_KAKI = "Tanpa email. Tanpa kartu pembayaran. Tiap anak 1 kali cek gratis."


def _e(teks) -> str:
    return html.escape(str(teks), quote=True)


def _appbar() -> str:
    return (
        '<header class="funnel-appbar-st">'
        f'<a class="brand" href="/">{brand.mark("topbar")}<span>{_e(T.NAMA_PRODUK)}</span></a>'
        f'<span class="funnel-appbar-label-st">{_e(COPY_APPBAR)}</span></header>'
    )


def _sapa() -> str:
    return (
        '<div class="funnel-sapa-st" aria-hidden="true">'
        '<img class="funnel-sapa-maskot-st" src="/aset/maskot-menyapa-v3-240.png" '
        'width="240" height="240" alt="">'
        f'<p class="funnel-gelembung-st">{_e(COPY_SAPA)}</p></div>'
    )


def _tab() -> str:
    return (
        '<nav class="funnel-tab-st" aria-label="Akun">'
        f'<span aria-current="page">{_e(COPY_TAB_BARU)}</span>'
        f'<a href="{_e(RUTE_MASUK_CEK)}">{_e(COPY_TAB_LAMA)}</a></nav>'
    )


def _judul_seksi(nomor: int, teks: str, id_judul: str) -> str:
    return (
        '<div class="funnel-seksi-kepala-st">'
        f'<span class="funnel-nomor-st" aria-hidden="true">{nomor}</span>'
        f'<h2 class="funnel-seksi-judul-st" id="{id_judul}">{_e(teks)}</h2></div>'
    )


def _field_akun(nama: str) -> str:
    return (
        '<div class="masuk-field-st">'
        '<label for="nama">Nama pengguna</label>'
        '<input type="text" id="nama" name="nama" autocomplete="username" required '
        f'aria-describedby="petunjuk-nama-daftar" value="{_e(nama)}">'
        f'<p class="daftar-petunjuk-st" id="petunjuk-nama-daftar">{_e(registration_contact.PETUNJUK_NAMA_FUNNEL)}</p>'
        "</div>"
        '<div class="masuk-field-st">'
        '<label for="sandi">Kata sandi</label>'
        '<input type="password" id="sandi" name="sandi" autocomplete="new-password" '
        'required minlength="8" aria-describedby="petunjuk-sandi-daftar">'
        f'<p class="daftar-petunjuk-st" id="petunjuk-sandi-daftar">{_e(COPY_SANDI)}</p>'
        "</div>"
    )


def _pil_kelas(kelas: int, terpilih) -> str:
    centang = " checked" if kelas == terpilih else ""
    return (
        '<label class="funnel-kelas-pil-st">'
        f'<input type="radio" name="kelas_sekolah" value="{kelas}" required{centang}>'
        f"<span>{kelas}<small>SD</small></span></label>"
    )


def _field_anak(nama_anak: str, kelas_sekolah) -> str:
    pil = "".join(_pil_kelas(k, kelas_sekolah) for k in KELAS_PILIHAN)
    return (
        f'<p class="funnel-anak-sapa-st">{_e(COPY_ANAK_SAPA)}</p>'
        '<div class="masuk-field-st">'
        '<label for="nama-anak-daftar">Nama panggilan anak</label>'
        '<input type="text" id="nama-anak-daftar" name="nama_anak" required maxlength="40" '
        f'autocomplete="off" value="{_e(nama_anak)}" aria-describedby="petunjuk-anak-daftar">'
        f'<p class="daftar-petunjuk-st" id="petunjuk-anak-daftar">{_e(COPY_ANAK_NAMA)}</p></div>'
        '<fieldset class="funnel-kelas-st" aria-describedby="petunjuk-kelas-daftar">'
        f"<legend>{_e(COPY_KELAS_LABEL)}</legend>"
        f'<div class="funnel-kelas-grid-st">{pil}</div>'
        f'<p class="daftar-petunjuk-st" id="petunjuk-kelas-daftar">{_e(COPY_KELAS_BANTUAN)}</p>'
        "</fieldset>"
    )


_PERSETUJUAN = (
    '  <div class="daftar-persetujuan-st">\n'
    '   <label class="koreksi-centang-st" for="setuju">\n'
    '    <input type="checkbox" id="setuju" name="setuju" value="1" required>\n'
    "    <span>Saya orang tua/wali atau pendidik yang bertanggung jawab, dan saya\n"
    '    menyetujui <a href="/syarat-penggunaan">Syarat Penggunaan</a> dan\n'
    '    memahami <a href="/kebijakan-privasi">Kebijakan Privasi</a>.</span>\n'
    "   </label>\n"
    "  </div>"
)
_SETUJU_KESEPAKATAN = '<input type="hidden" name="setuju" value="1">'


def _tombol(kesepakatan: str) -> str:
    if kesepakatan:
        return ""
    return (
        '<button class="masuk-tombol-st funnel-cta-st" type="submit">'
        f'{_e(COPY_TOMBOL)} <span aria-hidden="true">&rarr;</span></button>'
    )


def isi_daftar_cek(
    *, kotak: str = "", deskripsi: str = "", token: str = "", profil_lama: str = "",
    nama: str = "", nama_anak: str = "", kelas_sekolah=None, wa: str = "",
    analitik: str = "", kesepakatan: str = "",
) -> str:
    """Isi `<main>` form daftar jalur cek; pemanggil membungkus dengan kerangka publik.

    `kesepakatan` (bila ada) menggantikan centang wajib dengan `setuju=1`
    tersembunyi dan membawa tombol setujunya sendiri, sama seperti form biasa.
    """
    setuju = _SETUJU_KESEPAKATAN if kesepakatan else _PERSETUJUAN
    return (
        '<main class="funnel-alur-st funnel-daftar-st" aria-labelledby="judul-daftar">'
        f'{_appbar()}{_sapa()}'
        f'<h1 class="funnel-alur-judul-st" id="judul-daftar">{_e(COPY_JUDUL)}</h1>'
        f"{_tab()}{kotak}"
        f'<form class="masuk-form-st funnel-form-st" method="post" action="/daftar"{deskripsi}>'
        f"{token}"
        '<section class="funnel-seksi-st" aria-labelledby="judul-seksi-akun">'
        f'{_judul_seksi(1, "Akun orang tua", "judul-seksi-akun")}'
        f"{_field_akun(nama)}{registration_contact.field_form(wa)}</section>"
        '<section class="funnel-seksi-st" aria-labelledby="judul-seksi-anak">'
        f'{_judul_seksi(2, "Data anak", "judul-seksi-anak")}'
        f"{_field_anak(nama_anak, kelas_sekolah)}</section>"
        f"{profil_lama}\n{setuju}\n  {analitik}\n  {kesepakatan}\n  {_tombol(kesepakatan)}"
        "</form>"
        f'<p class="funnel-kaki-st">{_e(COPY_KAKI)}</p>'
        "</main>"
    )

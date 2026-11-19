"""Halaman siap mulai dan halaman QR cek gratis (funnel Fase 3, sisi orang tua).

Renderer murni, tanpa JS: tidak membuka basis data dan tidak membuat token.
Halaman siap mulai punya tiga bentuk menurut `StatusCek`:

- belum mulai: info, tips, pemberitahuan data, centang persetujuan, dua pilihan
  perangkat dalam satu form ke `/cek-kemampuan/mulai`;
- sedang berjalan: kartu anak dengan jumlah soal terjawab (tanpa benar/salah) dan
  dua pilihan perangkat ke `/cek-kemampuan/tautan`, tanpa persetujuan ulang dan
  tanpa memakai laju "mulai";
- kelas belum diisi: pesan jujur dan tautan ke halaman akun, tanpa tombol buntu.

Nama panggilan anak di-escape dan hanya tampil di badan halaman.
"""
from __future__ import annotations

import share_links
from cek_pages import (
    COPY_NOTICE, COPY_NOTICE_JUDUL, COPY_SETUJU, KELAS_BUNGKUS, KELAS_BUNGKUS_TAUTAN, RUTE_HASIL,
    RUTE_MULAI, RUTE_TAUTAN, _a, _bungkus, _daftar, _e, _galat, _kepala,
)
from cek_status import STATUS_BERJALAN, StatusCek

CARA_HP_INI = "hp_ini"
CARA_HP_ANAK = "hp_anak"
RUTE_KELAS = "/akun?section=siswa"

# DRAF: teks final menunggu persetujuan Pemilik
COPY_CARA_WAJIB = "Pilih dulu anak mengerjakan di HP mana, ya."
# DRAF: teks final menunggu persetujuan Pemilik
COPY_MENGERJAKAN_DI = "Anak mengerjakan di mana?"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_HP_INI = "Kerjakan di HP ini"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_HP_INI_KET = (
    "Serahkan HP ke anak setelah menekan tombol ini. Anda keluar dari akun di HP ini; "
    "masuk lagi nanti untuk melihat hasil."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_HP_ANAK = "Di HP/tablet anak"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_HP_ANAK_KET = "Pindai kode QR dari perangkat anak. Anda tetap masuk di HP ini."
# DRAF: teks final menunggu persetujuan Pemilik
COPY_LANJUT_HP_INI = "Lanjutkan di HP ini"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_LANJUT_HP_ANAK = "Buat tautan baru untuk HP anak"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_LANJUT_HP_ANAK_KET = "Tautan lama berhenti berlaku. Jawaban yang sudah tersimpan tidak hilang."
# DRAF: teks final menunggu persetujuan Pemilik
COPY_DATA_JUDUL = "Data apa yang disimpan?"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_TANPA_KELAS = (
    "Kelas anak belum diisi, jadi soal cek belum bisa disiapkan. Isi kelasnya dulu di "
    "halaman akun, lalu buka halaman ini lagi."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_ISI_KELAS = "Isi kelas anak"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_QR_JUDUL = "Pindai dari HP anak"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_QR_SUDAH = "Sudah terbuka di HP anak"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_TIPS = (
    ("amber", "Siapkan kertas dan pensil untuk coretan (ada juga papan coret di layar)."),
    ("teal", "Biarkan anak mengerjakan sendiri. Kalau dibantu, hasilnya tidak menunjukkan kemampuan aslinya."),
    ("koral", "Bilang ke anak: ini bukan ulangan. Tidak tahu itu boleh."),
)

_SVG = (
    '<svg width="{u}" height="{u}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
)
_D_PENSIL = '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/><path d="M14.5 6.5l3 3"/>'
_D_ORANG = '<circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"/>'
_D_HATI = '<path d="M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z"/>'
_D_HP = '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>'
_D_QR = (
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
    '<rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3M21 14v.01M14 21h7v-4"/>'
)
_IKON_TIPS = {"amber": _D_PENSIL, "teal": _D_ORANG, "koral": _D_HATI}


def _ubin(warna: str, d: str, ukuran: int = 18, besar: bool = False) -> str:
    kelas = "funnel-ubin-st funnel-ubin-besar-st" if besar else "funnel-ubin-st"
    return f'<span class="{kelas} funnel-ubin-{warna}-st">{_SVG.format(u=ukuran, d=d)}</span>'


def _kartu_anak(status: StatusCek) -> str:
    awal = _e(status.nama_anak[:1].upper())
    kelas = f" · kelas {status.kelas}" if type(status.kelas) is int else ""
    if status.status == STATUS_BERJALAN and status.terjawab > 0:
        pita = (
            '<span class="funnel-pita-st funnel-pita-jalan-st">'
            f"Sedang berjalan · {status.terjawab} dari {status.jumlah_soal} soal</span>"
            f'<progress class="funnel-progres-st" max="{status.jumlah_soal}" '
            f'value="{status.terjawab}">{status.terjawab}</progress>'
        )
    else:
        pita = '<span class="funnel-pita-st funnel-pita-belum-st">Belum mulai</span>'
    return (
        '<section class="funnel-kartu-anak-st" aria-label="Anak yang dicek">'
        f'<span class="funnel-avatar-st" aria-hidden="true">{awal}</span>'
        f'<div class="funnel-kartu-anak-meta-st"><b>{_e(status.nama_anak)}{kelas}</b>{pita}</div>'
        "</section>"
    )


def _info(status: StatusCek) -> str:
    butir = (
        (f"{status.jumlah_soal} soal", "pilihan ganda"), ("±25 menit", "tanpa batas waktu"),
        ("Boleh jeda", "jawaban tersimpan"), ("Gratis", "hasil langsung keluar"),
    )
    kotak = "".join(f"<div><b>{_e(b)}</b><span>{_e(k)}</span></div>" for b, k in butir)
    return f'<div class="funnel-info-st">{kotak}</div>'


def _tips() -> str:
    butir = "".join(
        f"<li>{_ubin(warna, _IKON_TIPS[warna])}<span>{_e(teks)}</span></li>" for warna, teks in COPY_TIPS
    )
    return f'<ul class="funnel-tips-st">{butir}</ul>'


def _lipat_data() -> str:
    return (
        '<details class="funnel-lipat-st">'
        f"<summary>{_e(COPY_DATA_JUDUL)}</summary>"
        f"<p><b>{_e(COPY_NOTICE_JUDUL)}</b></p><ul>{_daftar(COPY_NOTICE)}</ul></details>"
    )


def _setuju() -> str:
    return (
        '<label class="funnel-setuju-st" for="setuju-cek">'
        '<input type="checkbox" id="setuju-cek" name="setuju" value="1" required>'
        f"<span>{_e(COPY_SETUJU)}</span></label>"
    )


def _pilihan(cara: str, ikon: str, warna: str, judul: str, ket: str) -> str:
    return (
        f'<button type="submit" name="cara" value="{cara}" class="funnel-alat-st">'
        f'{_ubin(warna, ikon, 24, True)}<span><b>{_e(judul)}</b><small>{_e(ket)}</small></span></button>'
    )


def _form(aksi: str, token: str, isi: str) -> str:
    return (
        f'<form class="funnel-form-st" method="post" action="{aksi}">'
        f'<input type="hidden" name="token" value="{_a(token)}">{isi}</form>'
    )


def _bagian_belum_mulai(status: StatusCek, token: str) -> str:
    isi = (
        _setuju()
        + f'<h2 class="funnel-sub-judul-st">{_e(COPY_MENGERJAKAN_DI)}</h2>'
        + '<div class="funnel-pilih-alat-st">'
        + _pilihan(CARA_HP_INI, _D_HP, "teal", COPY_HP_INI, COPY_HP_INI_KET)
        + _pilihan(CARA_HP_ANAK, _D_QR, "koral", COPY_HP_ANAK, COPY_HP_ANAK_KET)
        + "</div>"
    )
    return (
        '<h2 class="funnel-sub-judul-st">Sebelum mulai</h2>'
        f"{_info(status)}{_tips()}{_lipat_data()}{_form(RUTE_MULAI, token, isi)}"
    )


def _bagian_berjalan(status: StatusCek, token: str) -> str:
    teks = (
        f"Anak sudah mengerjakan {status.terjawab} dari {status.jumlah_soal} soal. "
        "Jawaban yang tersimpan tidak hilang."
        if status.terjawab > 0 else
        "Cek sudah disiapkan. Pilih perangkat yang dipakai anak untuk mengerjakan."
    )
    isi = (
        '<div class="funnel-pilih-alat-st">'
        + _pilihan(CARA_HP_INI, _D_HP, "teal", COPY_LANJUT_HP_INI, COPY_HP_INI_KET)
        + _pilihan(CARA_HP_ANAK, _D_QR, "koral", COPY_LANJUT_HP_ANAK, COPY_LANJUT_HP_ANAK_KET)
        + "</div>"
    )
    return f'<p class="funnel-bantuan-st">{_e(teks)}</p>{_form(RUTE_TAUTAN, token, isi)}'


def _bagian_tanpa_kelas() -> str:
    return (
        '<div class="kartu-st">'
        f"<p>{_e(COPY_TANPA_KELAS)}</p>"
        f'<p class="funnel-tautan-baris-st"><a class="funnel-tautan-st" href="{RUTE_KELAS}">'
        f"{_e(COPY_ISI_KELAS)}</a></p></div>"
    )


def halaman_mulai(ident, status: StatusCek, token: str, *, galat: str = "") -> bytes:
    """Halaman siap mulai; `token` = token form untuk aksi bentuk halaman ini (mulai atau tautan)."""
    if status.status == STATUS_BERJALAN:
        bagian = _bagian_berjalan(status, token)
    elif type(status.kelas) is not int:
        bagian = _bagian_tanpa_kelas()
    else:
        bagian = _bagian_belum_mulai(status, token)
    isi = (
        _kepala("CEK KEMAMPUAN GRATIS", "Mulai cek kemampuan", "judul-cek-mulai")
        + _galat(galat) + _kartu_anak(status) + bagian
    )
    return _bungkus(ident, "Mulai cek kemampuan", "judul-cek-mulai",
                    f'<div class="funnel-alur-st">{isi}</div>', kelas=KELAS_BUNGKUS)


def halaman_tautan(ident, nama_anak: str, tautan: str) -> bytes:
    """Lembar QR untuk HP anak; hanya di respons POST pembuatnya."""
    from teacher_print_pages import _blok_qr

    isi = (
        _kepala("MULAI DI HP ANAK", COPY_QR_JUDUL, "judul-cek-tautan", nama_anak)
        + '<section class="funnel-lembar-st bagikan-kartu-st" aria-labelledby="label-tautan">'
        '<span class="funnel-pegangan-st" aria-hidden="true"></span>'
        f"{_blok_qr(tautan)}"
        '<label id="label-tautan" for="tautan-sesi">Atau kirim tautan ini ke HP anak</label>'
        f'<input id="tautan-sesi" type="text" readonly value="{_a(tautan)}" '
        'aria-describedby="petunjuk-tautan" spellcheck="false">'
        '<p id="petunjuk-tautan" class="sub">Pilih seluruh isi kotak, lalu salin. '
        f"Tautan berlaku {_e(share_links.LABEL_MASA_BERLAKU)}, atau sampai cek selesai "
        "maupun tautan baru dibuat.</p>"
        '<p class="bagikan-perhatian-st">Siapa pun yang memegang tautan dapat mengerjakan '
        "cek ini tanpa masuk. Berikan hanya kepada anak yang dituju. Tautan ini hanya "
        "tampil di halaman ini; bila hilang, buat tautan baru dari halaman siap mulai. "
        "Jangan masuk sebagai guru di HP anak.</p>"
        f'<p class="funnel-lembar-aksi-st"><a class="funnel-cta-tautan-st" href="{RUTE_MULAI}">'
        f"{_e(COPY_QR_SUDAH)}</a>"
        f'<a class="funnel-tautan-st" href="{RUTE_HASIL}">Kembali ke halaman hasil</a></p>'
        "</section>"
    )
    return _bungkus(ident, "Tautan untuk anak", "judul-cek-tautan",
                    f'<div class="funnel-alur-st">{isi}</div>', kelas=KELAS_BUNGKUS_TAUTAN)

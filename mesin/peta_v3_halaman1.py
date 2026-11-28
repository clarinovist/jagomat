"""Halaman 1 laporan Peta versi 3 (F6): kepala merek dengan tombol unduh, hero maskot, dan kartu skor.

Maskot dan logo memakai aset same-origin yang sudah ada (`brand`), dengan atribut style dibuang. Tombol unduh memakai
`SKRIP_CETAK` yang sudah ada; tanpa JS tombolnya disembunyikan lewat `<noscript>`, seperti laporan versi 2.
"""
from __future__ import annotations

import brand
import design_tokens as T
import peta_v3_aturan as aturan
import peta_v3_grafik as grafik
from peta_v3_html import e, gabung, tanggal, tanpa_style

COPY_JUDUL = "Peta Kemampuan"
COPY_INFO = "Hasil cek kemampuan"
COPY_INFO_KELAS = "Kelas %d SD"
COPY_UNDUH = "Unduh PDF"
COPY_GELEMBUNG = "Gambaran kemampuan anak"
COPY_KUAT_HERO = "Anak sudah cukup baik di %s."
COPY_BELUM_HERO = "%s masih perlu dilatih dulu."
COPY_PERLU_HERO = "%s perlu diperkuat."
COPY_SKOR_JUDUL = "Skor keseluruhan"
COPY_SKOR_BENAR = "%d dari %d soal benar"
COPY_JUMLAH_MATERI = "%d materi"
NOSCRIPT_SEMBUNYI_CETAK = "<noscript><style>.ortu-peta-v3-cetak-baris-st{display:none}</style></noscript>"
UKURAN_MASKOT = 96
POSE_MASKOT = "berpikir"
KELAS_LEGENDA = {
    aturan.STATUS_DIKUASAI: "dikuasai",
    aturan.STATUS_PERLU: "perlu",
    aturan.STATUS_BELUM: "belum",
}
SEPARATOR_INFO = " · "


def _baris_info(isi: dict) -> str:
    potongan = [COPY_INFO]
    if isi["kelas"] is not None:
        potongan.append(COPY_INFO_KELAS % isi["kelas"])
    potongan.append(tanggal(isi["tanggal_cek"]))
    return SEPARATOR_INFO.join(potongan)


def _tombol_unduh() -> str:
    return (f'<p class="ortu-peta-v3-cetak-baris-st"><button type="button" class="ortu-peta-v3-cetak-st" '
            f'data-peta-cetak>{e(COPY_UNDUH)}</button></p>{NOSCRIPT_SEMBUNYI_CETAK}')


def kepala(isi: dict) -> str:
    """Merek, judul "Peta Kemampuan", baris informasi cek, dan tombol unduh (tanpa JS disembunyikan)."""
    merek = (f'<p class="ortu-peta-v3-merek-st">{tanpa_style(brand.mark("badge"))}'
             f'<span><b>{e(T.NAMA_PRODUK)}</b><small>{e(T.TAGLINE)}</small></span></p>')
    judul = (f'<div class="ortu-peta-v3-judul-st"><h2>{e(COPY_JUDUL)}</h2>'
             f'<p>{e(_baris_info(isi))}</p></div>')
    return f'<header class="ortu-peta-v3-kepala-st">{merek}{judul}{_tombol_unduh()}</header>'


def _nama_status(daftar: list, status: str) -> list:
    return [materi["materi"] for materi in daftar if materi["status"] == status]


def kalimat_ringkas(daftar: list) -> list:
    """Kalimat hero dari status per materi: yang sudah baik, yang belum dikuasai, lalu yang perlu diperkuat."""
    kalimat = []
    kuat = _nama_status(daftar, aturan.STATUS_DIKUASAI)
    belum = _nama_status(daftar, aturan.STATUS_BELUM)
    perlu = _nama_status(daftar, aturan.STATUS_PERLU)
    if kuat:
        kalimat.append(COPY_KUAT_HERO % gabung(kuat))
    if belum:
        kalimat.append(COPY_BELUM_HERO % gabung(belum))
    if perlu:
        kalimat.append(COPY_PERLU_HERO % gabung(perlu))
    return kalimat


def hero(isi: dict, daftar: list) -> str:
    """Hero: maskot, gelembung, label kategori skor, dan kalimat ringkas dari status per materi."""
    maskot = tanpa_style(brand.maskot(POSE_MASKOT, UKURAN_MASKOT, kelas="ortu-peta-v3-maskot-st"))
    kalimat = "".join(f"<p>{e(teks)}</p>" for teks in kalimat_ringkas(daftar))
    return (f'<section class="ortu-peta-v3-hero-st" aria-label="{e(COPY_GELEMBUNG)}">{maskot}'
            f'<div><span class="ortu-peta-v3-gelembung-st">{e(COPY_GELEMBUNG)}</span>'
            f'<p class="ortu-peta-v3-kategori-st">{e(isi["kategori"])}</p>{kalimat}</div></section>')


def _legenda_skor(daftar: list) -> str:
    butir = []
    for status in aturan.URUTAN_STATUS:
        jumlah = len(_nama_status(daftar, status))
        butir.append(f'<li><span class="ortu-peta-v3-titik-st ortu-peta-v3-titik-{KELAS_LEGENDA[status]}-st" '
                     f'aria-hidden="true"></span>{e(status)}<b>{e(COPY_JUMLAH_MATERI % jumlah)}</b></li>')
    return f'<ul class="ortu-peta-v3-legenda-st">{"".join(butir)}</ul>'


def kartu_skor(isi: dict, daftar: list) -> str:
    """Kartu skor: donat skor/100 di kiri; judul, hitungan materi per status, dan soal benar di kanan."""
    benar = isi["grid"].count(1)
    teks = (f'<div class="ortu-peta-v3-skor-teks-st"><h3 id="ortu-peta-v3-h-skor">{e(COPY_SKOR_JUDUL)}</h3>'
            f'{_legenda_skor(daftar)}'
            f'<p class="ortu-peta-v3-ket-st">{e(COPY_SKOR_BENAR % (benar, isi["jumlah_soal"]))}</p></div>')
    return (f'<section class="ortu-peta-v3-kartu-st ortu-peta-v3-skor-kartu-st" aria-labelledby="ortu-peta-v3-h-skor">'
            f'<div class="ortu-peta-v3-skor-st">{grafik.donat(int(isi["skor"]))}{teks}</div></section>')

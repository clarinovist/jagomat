"""Halaman publik `/contoh-peta-kemampuan`: contoh laporan Peta Kemampuan SINTETIS.

Renderer murni: tanpa data keluarga/anak, tanpa form, tanpa JS. Bar penguasaan
memakai `<div>` dengan lebar persen lewat atribut `style` (CSS saja). Satu CTA
utama (`_cta_utama`) ke `/daftar?jalur=cek`. Kerangka mengikuti `funnel_pages`.
"""
from __future__ import annotations

import funnel_pages as P

_e = P._e

# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_LABEL = (
    "Contoh ilustrasi dengan data sintetis, bukan hasil anak sungguhan. "
    "Laporan sungguhan berbeda untuk tiap anak."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL = "Beginilah laporan yang Anda terima."
COPY_CONTOH_ANAK = "Aisyah · kelas 4"
COPY_CONTOH_SKOR = 72
COPY_CONTOH_KATEGORI = "Cukup baik"
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL_MATERI = "Penguasaan per materi"
COPY_CONTOH_CHIP_KUAT = "Kuat"
COPY_CONTOH_CHIP_PERKUAT = "Perlu diperkuat"
BATAS_KUAT_PERSEN = 70
CONTOH_MATERI = (
    ("Penjumlahan dan pengurangan", 90),
    ("Perkalian", 55),
    ("Pembagian", 60),
    ("Pecahan", 40),
    ("Soal cerita", 35),
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL_POLA = "Pola kesalahan"
COPY_CONTOH_POLA = (
    "Soal cerita: kalimat soal belum diubah jadi operasi yang tepat "
    "(6 dari 9 soal cerita salah di langkah ini).",
    "Perkalian bersusun: hasil kali satuan lupa dibawa ke puluhan.",
    "Pecahan: penyebut dijumlahkan langsung.",
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL_URUTAN = "Urutan belajar prioritas"
COPY_CONTOH_URUTAN = (
    "Soal cerita: mengubah kalimat soal menjadi operasi.",
    "Perkalian bersusun: membawa hasil ke puluhan.",
    "Pecahan: menyamakan penyebut sebelum menjumlahkan.",
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL_LANGKAH = "Satu langkah minggu ini"
COPY_CONTOH_LANGKAH = (
    "Latihan 10 menit per hari pada perkalian bersusun, dengan menulis angka "
    "yang dibawa di atas kolom puluhan."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL_CATATAN = "Catatan guru (contoh)"
COPY_CONTOH_CATATAN = (
    "Aisyah teliti dan cepat di hitungan dasar, itu modal yang bagus. "
    "Soal cerita akan terasa lebih ringan kalau kalimatnya dibaca pelan-pelan "
    "dulu sebelum memilih operasi."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_PENUTUP = "Peringkat dan perbandingan dengan anak lain tidak ditampilkan."
COPY_CONTOH_CTA = P.COPY_CTA


def _bar_materi(nama: str, persen: int) -> str:
    kuat = persen >= BATAS_KUAT_PERSEN
    kelas = "funnel-bar-kuat-st" if kuat else "funnel-bar-lemah-st"
    chip = COPY_CONTOH_CHIP_KUAT if kuat else COPY_CONTOH_CHIP_PERKUAT
    ikon = P._ikon(P._D_CENTANG if kuat else P._D_SERU, 16, "2.6")
    return (
        f'<li class="funnel-bar-baris-st"><div class="funnel-bar-kepala-st">'
        f'<span class="funnel-bar-nama-st">{_e(nama)}</span>'
        f'<span class="funnel-bar-persen-st">{persen}%</span>'
        f'<span class="funnel-bar-chip-st {kelas}">{ikon}{_e(chip)}</span></div>'
        f'<div class="funnel-bar-trek-st" role="img" aria-label="{_e(nama)} {persen}%">'
        f'<div class="funnel-bar-isi-st {kelas}" style="width:{persen}%"></div></div></li>'
    )


def _ringkasan() -> str:
    return f"""
<div class="funnel-contoh-kartu-st">
  <p class="funnel-anak-st">{_e(COPY_CONTOH_ANAK)}</p>
  <div class="funnel-skor-baris-st">
    <div class="funnel-cincin-st" role="img" aria-label="Skor {COPY_CONTOH_SKOR} dari 100"><span class="funnel-cincin-dalam-st"><b>{COPY_CONTOH_SKOR}<small>dari 100</small></b></span></div>
    <div class="funnel-kategori-st">{_e(COPY_CONTOH_KATEGORI)}<small>Kategori kemampuan</small></div>
  </div>
</div>"""


def _bagian(judul: str, isi: str, id_: str) -> str:
    return (
        f'\n<section class="funnel-contoh-bagian-st" aria-labelledby="{id_}">'
        f'<h2 id="{id_}">{_e(judul)}</h2>{isi}</section>'
    )


def _penguasaan() -> str:
    bar = "".join(_bar_materi(n, p) for n, p in CONTOH_MATERI)
    return _bagian(COPY_CONTOH_JUDUL_MATERI, f'<ul class="funnel-bar-daftar-st">{bar}</ul>', "judul-materi")


def _pola() -> str:
    li = "".join(f"<li>{P._ikon(P._D_INFO, 20, '2.2')}<span>{_e(b)}</span></li>" for b in COPY_CONTOH_POLA)
    return _bagian(COPY_CONTOH_JUDUL_POLA, f'<ul class="funnel-contoh-pola-st">{li}</ul>', "judul-pola")


def _urutan() -> str:
    li = "".join(f"<li>{_e(b)}</li>" for b in COPY_CONTOH_URUTAN)
    return _bagian(COPY_CONTOH_JUDUL_URUTAN, f'<ol class="funnel-contoh-urutan-st">{li}</ol>', "judul-urutan")


def _langkah_catatan() -> str:
    langkah = _bagian(COPY_CONTOH_JUDUL_LANGKAH, f'<p class="funnel-contoh-langkah-st">{_e(COPY_CONTOH_LANGKAH)}</p>', "judul-langkah-minggu")
    catatan = _bagian(COPY_CONTOH_JUDUL_CATATAN, f'<p class="funnel-contoh-catatan-st">{_e(COPY_CONTOH_CATATAN)}</p>', "judul-catatan-guru")
    return langkah + catatan


def halaman_contoh_peta(dukungan=None) -> bytes:
    """Contoh laporan Peta Kemampuan (sintetis) dengan satu CTA utama."""
    isi = f"""{P._topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st funnel-contoh-halaman-st" id="konten" tabindex="-1">
<header class="funnel-bagian-st">
  <p class="funnel-alis-st">{_e(P.NAMA_PAKET)}</p>
  <h1 class="funnel-judul-halaman-st">{_e(COPY_CONTOH_JUDUL)}</h1>
  <p class="funnel-contoh-label-st" role="note">{_e(COPY_CONTOH_LABEL)}</p>
</header>
{_ringkasan()}{_penguasaan()}{_pola()}{_urutan()}{_langkah_catatan()}{P.kartu_profil_guru()}
<div class="funnel-aksi-st">
  <p>{_e(COPY_CONTOH_PENUTUP)}</p>
  {P._cta_utama(COPY_CONTOH_CTA)}
</div>
</main>
{P._footer(dukungan)}"""
    return P._bungkus("Contoh Peta Kemampuan", isi)

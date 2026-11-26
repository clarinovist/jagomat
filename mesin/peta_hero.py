"""Hero penawaran Peta Kemampuan: bagian atas yang ramai untuk halaman produk dan halaman bayar (butir QA #9 dan #10).

Peta adalah lead magnet, jadi bagian penawarannya harus menarik mata (maskot, stiker, harga). Blok instruksi bayar
di bawahnya tetap tenang (kebijakan "halaman uang = tenang"). Stiker "Laporan otomatis" menyatakan laporan terbit
tanpa tinjauan Guru; halaman produk (`funnel_pages.COPY_PAKET_ISI`) perlu diselaraskan
terpisah. Satu maskot per layar; pemanggil memuat `playful_style.GAYA_CERIA`.
"""
from __future__ import annotations

import html

import design_tokens as T
import playful_components as C

JUDUL_PETA = "Lihat di materi mana anak masih sering salah. Tahu satu langkah berikutnya."
ALIS_PETA = "PETA KEMAMPUAN"
TINGKAT_JUDUL = (1, 2, 3)


# Judul h1 di hero halaman produk: ukuran judul bagian, bukan ukuran angka besar funnel.
GAYA_HERO_PETA = f".ceria-hero h1 {{ font-size: {T.UKURAN_JUDUL_STITCH}; line-height: 1.15; font-weight: 800; }}"
GAYA_INLINE_MASKOT = ' style="max-width:96px;height:auto"'


def hero_peta(*, tingkat: int = 2, id_judul: str = "", tanpa_gaya_inline: bool = False) -> str:
    """Hero teal: gelembung maskot, judul (h`tingkat`, id opsional), harga, dan dua stiker.

    `tanpa_gaya_inline`: halaman funnel publik melarang atribut style (CSP); maskot dirender tanpanya.
    """
    if tingkat not in TINGKAT_JUDUL:
        raise ValueError(f"tingkat judul tidak dikenal: {tingkat!r}")
    atribut_id = f' id="{html.escape(id_judul, quote=True)}"' if id_judul else ""
    judul = f"<h{tingkat}{atribut_id}>{html.escape(JUDUL_PETA)}</h{tingkat}>"
    maskot = C.maskot_bicara("menunjuk", "Yuk lihat ", "peta belajar anak", "!")
    if tanpa_gaya_inline:
        maskot = maskot.replace(GAYA_INLINE_MASKOT, "")
    return C.hero(
        maskot
        + f'<p class="ceria-alis-hero">{ALIS_PETA}</p>'
        + judul
        + f"<p>{C.sorot('Rp49.000')} sekali bayar, bukan langganan.</p>"
        + C.stiker("Laporan otomatis") + C.stiker("Jadi potongan kelas", "kanan"),
        konfeti=True)

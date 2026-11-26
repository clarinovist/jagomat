"""Halaman publik `/contoh-peta-kemampuan`: contoh laporan Peta Kemampuan v1 SINTETIS.

Merender contoh laporan yang bentuknya identik dengan laporan nyata yang diterima orang tua
di `/murid/orang-tua` (`peta_laporan_ortu_pages.blok_peta`), Zero-JS, tanpa tab Pola kesalahan,
tanpa donat pola, tanpa peringkat/persentil, dan tanpa lencana. Satu CTA utama (`funnel_pages._cta_utama`)
ke `/daftar?jalur=cek` ada di kartu langkah berikutnya (`peta_misi._program`).
Kerangka mengikuti `funnel_pages` dan CSS mengikuti `orang_tua_style` + `playful_style`.
"""
from __future__ import annotations

import cek_gratis_skor
import funnel_pages as P
import peta_contoh_data
import peta_lembar
import peta_misi
import peta_laporan_ortu_pages
from orang_tua_style import GAYA_ORTU
from playful_style import GAYA_CERIA

_e = P._e

# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_LABEL = (
    "Contoh ilustrasi dengan data sintetis, bukan hasil anak sungguhan. "
    "Laporan sungguhan berbeda untuk tiap anak."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL = "Beginilah laporan yang Anda terima."
JUDUL_HALAMAN = "Contoh Peta Kemampuan"

_BENAR_CONTOH = 11
_TOTAL_CONTOH = 15
_SKOR_CONTOH = cek_gratis_skor.hitung_skor(_BENAR_CONTOH, _TOTAL_CONTOH)

CONTOH_PETA_V1 = {
    "isi": {
        "versi": 1,
        "kelas": 4,
        "tanggal_cek": "2026-11-18",
        "skor": _SKOR_CONTOH,
        "kategori": cek_gratis_skor.kategori_dari_skor(_SKOR_CONTOH),
        "jumlah_soal": _TOTAL_CONTOH,
        "per_materi": [
            {"materi": "Berhitung", "benar": 5, "total": 5},
            {"materi": "Bangun datar", "benar": 4, "total": 5},
            {"materi": "Pengukuran", "benar": 2, "total": 5},
        ],
        "kuat": ["Berhitung", "Bangun datar"],
        "perlu_dilatih": ["Pengukuran", "Bangun datar"],
        "ringkasan_perlu": ["Pengukuran"],
    },
    "catatan": (
        "Aisyah sudah mantap di hitungan dasar. Fokus latihan berikutnya adalah Pengukuran "
        "(terutama mengubah satuan panjang dan membaca soal cerita ukuran) sebanyak 10 menit sehari."
    ),
    "diterbitkan": "2026-11-20 10:00:00",
}


def halaman_lembar_contoh() -> bytes:
    """Lembar 1 halaman A4 (sintetis) untuk `/contoh-peta-kemampuan/lembar`."""
    return peta_lembar.halaman_lembar(peta_contoh_data.DATA_CONTOH, contoh=True)


def halaman_contoh_peta(dukungan=None, profil=None, *, harga_mini=None) -> bytes:
    """Contoh laporan Peta Kemampuan v1 (sintetis) dengan satu CTA utama.

    `harga_mini` = harga bulanan Mini Class aktif dari admin; None = harga katalog.
    """
    # contoh mewakili laporan terbit otomatis: tanpa lencana dan catatan Guru (kunci `oleh_sistem`)
    blok_laporan = peta_laporan_ortu_pages.blok_peta({**CONTOH_PETA_V1, "oleh_sistem": True})
    batas = P._kartu_batas()
    program = peta_misi._program(P._cta_utama(P.COPY_CTA), harga_mini=harga_mini)
    isi = f"""{P._topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st" id="konten" tabindex="-1">
<header class="funnel-bagian-st">
  <p class="funnel-alis-st">{_e(P.NAMA_PAKET)}</p>
  <h1 class="funnel-judul-halaman-st">{_e(COPY_CONTOH_JUDUL)}</h1>
  <p class="funnel-contoh-label-st" role="note">{_e(COPY_CONTOH_LABEL)}</p>
  <p class="funnel-catatan-st">Contoh untuk Aisyah · Kelas 4 · {_TOTAL_CONTOH} soal</p>
</header>
<div class="funnel-alur-st">
{blok_laporan}
{batas}
{program}
</div>
{P.kartu_profil_guru(profil)}
</main>
{P._footer(dukungan)}"""
    return P._bungkus(JUDUL_HALAMAN, isi, css_tambahan=GAYA_CERIA + GAYA_ORTU)

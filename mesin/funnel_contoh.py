"""Halaman publik `/contoh-peta-kemampuan`: contoh laporan Peta Kemampuan SINTETIS.

Memakai renderer laporan playful `peta_laporan` dengan data contoh `peta_contoh_data`
(Aisyah, kelas 4, semua angka saling cocok; posisi dihitung `peta_posisi`).
Tanpa data keluarga/anak dan tanpa form. Satu CTA utama (`funnel_pages._cta_utama`)
ke `/daftar?jalur=cek` ada di panel Misi berikutnya. JS hanya skrip polos berhash CSP
(`peta_browser`); tanpa JS semua panel tampil berurutan. Kerangka mengikuti `funnel_pages`.
"""
from __future__ import annotations

import funnel_pages as P
import peta_contoh_data
import peta_laporan
import peta_lembar

_e = P._e

# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_LABEL = (
    "Contoh ilustrasi dengan data sintetis, bukan hasil anak sungguhan. "
    "Laporan sungguhan berbeda untuk tiap anak."
)
# DRAF: teks final menunggu persetujuan Pemilik
COPY_CONTOH_JUDUL = "Beginilah laporan yang Anda terima."
JUDUL_HALAMAN = "Contoh Peta Kemampuan"


def halaman_lembar_contoh() -> bytes:
    """Lembar 1 halaman A4 (sintetis) untuk `/contoh-peta-kemampuan/lembar`."""
    return peta_lembar.halaman_lembar(peta_contoh_data.DATA_CONTOH, contoh=True)


def halaman_contoh_peta(dukungan=None) -> bytes:
    """Contoh laporan Peta Kemampuan (sintetis) dengan satu CTA utama."""
    laporan = peta_laporan.render_laporan(peta_contoh_data.DATA_CONTOH, contoh=True)
    isi = f"""{P._topbar(tautan_funnel=True)}
<main class="landing-bungkus-st funnel-halaman-st peta-halaman-st" id="konten" tabindex="-1">
<header class="funnel-bagian-st">
  <p class="funnel-alis-st">{_e(P.NAMA_PAKET)}</p>
  <h1 class="funnel-judul-halaman-st">{_e(COPY_CONTOH_JUDUL)}</h1>
  <p class="funnel-contoh-label-st" role="note">{_e(COPY_CONTOH_LABEL)}</p>
</header>
{laporan}{P.kartu_profil_guru()}
</main>
{P._footer(dukungan)}"""
    return P._bungkus(JUDUL_HALAMAN, isi)

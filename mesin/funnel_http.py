"""Rute GET publik funnel Cek Kemampuan: `/cek-kemampuan`, `/paket-coba`, `/contoh-peta-kemampuan`.

Dipanggil sebelum `_lolos_sandi`: publik untuk anonim dan guru. Tidak ada
handler POST. Sakelar `FUNNEL_AKTIF` mati (bawaan) -> halaman status "belum
dibuka" dengan kode 200, tanpa form dan tanpa tautan ke jalur cek.
Tidak membaca data keluarga atau anak.
"""
from __future__ import annotations

JALUR_FUNNEL = ("/cek-kemampuan", "/paket-coba", "/contoh-peta-kemampuan")


def _dukungan():
    import admin_store
    import support_settings

    try:
        return support_settings.baca_publik(admin_store.BAWAAN)
    except admin_store.StoreBelumSiap:
        return None


def tangani_get(penangan, jalur: str) -> bool:
    """Render halaman funnel atau status belum dibuka; False bila bukan rutenya."""
    if jalur not in JALUR_FUNNEL:
        return False
    import funnel_flag
    import funnel_pages

    dukungan = _dukungan()
    if not funnel_flag.funnel_aktif():
        penangan._kirim(funnel_pages.halaman_belum_dibuka(dukungan))
        return True
    if jalur == "/cek-kemampuan":
        penangan._kirim(funnel_pages.halaman_cek_kemampuan(dukungan))
    elif jalur == "/contoh-peta-kemampuan":
        import funnel_contoh

        penangan._kirim(funnel_contoh.halaman_contoh_peta(dukungan))
    else:
        penangan._kirim(funnel_pages.halaman_paket_coba(dukungan))
    return True

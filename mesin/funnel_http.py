"""Rute GET publik funnel Cek Kemampuan: `/cek-kemampuan`, `/paket-coba`,
`/contoh-peta-kemampuan`, dan lembar 1 halaman `/contoh-peta-kemampuan/lembar`.

Dipanggil sebelum `_lolos_sandi`: publik untuk anonim dan guru. Tidak ada
handler POST. Sakelar `FUNNEL_AKTIF` mati (bawaan) -> halaman status "belum
dibuka" dengan kode 200, tanpa form dan tanpa tautan ke jalur cek.
Tidak membaca data keluarga atau anak.

Semua respons funnel membawa `Content-Security-Policy` berhash (`web.csp_tautan`):
hash dihitung dari skrip inline yang benar-benar ada di respons, jadi skrip laporan
playful (`peta_browser`) dan skrip kerangka halaman publik dikenali, dan skrip lain
diblokir. Perilaku `Penangan._kirim` untuk rute lain tidak berubah.
"""
from __future__ import annotations

JALUR_LEMBAR_CONTOH = "/contoh-peta-kemampuan/lembar"
JALUR_FUNNEL = ("/cek-kemampuan", "/paket-coba", "/contoh-peta-kemampuan", JALUR_LEMBAR_CONTOH)


def _dukungan():
    import admin_store
    import support_settings

    try:
        return support_settings.baca_publik(admin_store.BAWAAN)
    except admin_store.StoreBelumSiap:
        return None


def _kirim_funnel(penangan, isi: bytes, kode: int = 200) -> None:
    """Kirim halaman funnel + CSP berhash dari skrip inline di `isi`."""
    import web

    penangan.send_response(kode)
    penangan.send_header("Content-Type", "text/html; charset=utf-8")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.send_header("Content-Security-Policy", web.csp_tautan(isi))
    penangan.end_headers()
    penangan.wfile.write(isi)


def _halaman(jalur: str, dukungan) -> bytes:
    import funnel_contoh
    import funnel_pages

    if jalur == "/cek-kemampuan":
        return funnel_pages.halaman_cek_kemampuan(dukungan)
    if jalur == "/contoh-peta-kemampuan":
        return funnel_contoh.halaman_contoh_peta(dukungan)
    if jalur == JALUR_LEMBAR_CONTOH:
        return funnel_contoh.halaman_lembar_contoh()
    return funnel_pages.halaman_paket_coba(dukungan)


def tangani_get(penangan, jalur: str) -> bool:
    """Render halaman funnel atau status belum dibuka; False bila bukan rutenya."""
    if jalur not in JALUR_FUNNEL:
        return False
    import funnel_flag
    import funnel_pages

    dukungan = _dukungan()
    if not funnel_flag.funnel_aktif():
        _kirim_funnel(penangan, funnel_pages.halaman_belum_dibuka(dukungan))
        return True
    _kirim_funnel(penangan, _halaman(jalur, dukungan))
    return True

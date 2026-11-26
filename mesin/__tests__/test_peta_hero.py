"""Hero penawaran Peta Kemampuan di halaman produk dan halaman bayar (butir QA #9 dan #10, 25 Nov 2026).

Peta adalah lead magnet: bagian atas ramai (maskot, stiker, harga), blok instruksi bayar tetap tenang. Semua klaim di hero
memakai kalimat yang sudah ada di halaman produk. Satu maskot per layar; guru lama tidak mendapat hero.
"""
from __future__ import annotations

import pytest

import funnel_pages
import pesanan_dasar as d
import pesanan_pages as halaman
import peta_hero
from test_pesanan_transfer_pages import _tampilan

IDENT_MURID = ("akun", "murid")
IDENT_GURU = ("guru", "guru")
PENANDA_GAYA = ".ceria-hero"


def _jumlah_maskot(isi: str) -> int:
    return isi.count('class="ceria-maskot"') + isi.count("funnel-maskot-st")


def test_hero_memuat_harga_klaim_yang_sudah_ada_dan_satu_maskot():
    isi = peta_hero.hero_peta()
    assert "Rp49.000" in isi and "sekali bayar" in isi.lower()
    assert "Laporan otomatis" in isi and "Jadi potongan kelas" in isi
    assert funnel_pages.COPY_JUDUL_PAKET_HALAMAN in isi
    assert 'class="ceria-hero"' in isi and _jumlah_maskot(isi) == 1


def test_hero_tanpa_gaya_inline_untuk_halaman_funnel_publik():
    assert 'style="' in peta_hero.hero_peta()
    assert 'style="' not in peta_hero.hero_peta(tanpa_gaya_inline=True)
    assert "max-width:96px" not in funnel_pages.halaman_paket_coba().decode()   # halaman tersaji dicek test_funnel_public


def test_gaya_hero_h1_css_valid_dan_terpasang_di_halaman_produk():
    assert peta_hero.GAYA_HERO_PETA.count("{") == 1 and peta_hero.GAYA_HERO_PETA.count("}") == 1
    assert peta_hero.GAYA_HERO_PETA in funnel_pages.halaman_paket_coba().decode()


def test_hero_tingkat_judul_dan_id_bisa_diatur_dan_di_escape():
    isi = peta_hero.hero_peta(tingkat=1, id_judul="judul-paket")
    assert '<h1 id="judul-paket">' in isi
    assert "<h2" in peta_hero.hero_peta()
    with pytest.raises(ValueError):
        peta_hero.hero_peta(tingkat=4)


def test_halaman_produk_peta_memakai_hero_dan_gaya_ceria_dan_tetap_satu_cta():
    isi = funnel_pages.halaman_paket_coba().decode()
    assert 'class="ceria-hero"' in isi and PENANDA_GAYA in isi
    assert isi.count('href="/daftar?jalur=cek"') == 1
    assert 'id="judul-paket"' in isi and _jumlah_maskot(isi) == 1


def test_halaman_bayar_belum_bayar_murid_punya_hero_di_atas_blok_bayar_yang_tenang():
    isi = halaman.halaman_status(IDENT_MURID, _tampilan(d.STATUS_BELUM_BAYAR), None).decode()
    assert 'class="ceria-hero"' in isi and PENANDA_GAYA in isi and "Rp49.000" in isi
    assert _jumlah_maskot(isi) == 1
    assert isi.index("ceria-hero") < isi.index("Menunggu pembayaran")   # hero dulu, lalu status/instruksi


@pytest.mark.parametrize("status", [d.STATUS_SUDAH_DIBAYAR, d.STATUS_MENUNGGU_VERIFIKASI, d.STATUS_PERLU_DIPERIKSA,
                                    d.STATUS_KEDALUWARSA, d.STATUS_DIREFUND, d.STATUS_DITOLAK])
def test_status_selain_belum_bayar_tanpa_hero_dan_maksimal_satu_maskot(status):
    isi = halaman.halaman_status(IDENT_MURID, _tampilan(status), None).decode()
    assert 'class="ceria-hero"' not in isi and _jumlah_maskot(isi) <= 1


def test_guru_lama_tidak_mendapat_hero():
    isi = halaman.halaman_status(IDENT_GURU, _tampilan(d.STATUS_BELUM_BAYAR), None).decode()
    assert 'class="ceria-hero"' not in isi

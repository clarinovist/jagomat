"""CTA pesan di halaman hasil cek (Fase 3c-3) dan kestabilan halaman hasil Fase 2.

Gerbang tertutup: halaman hasil identik byte-per-byte dengan Fase 2 (golden dari renderer,
dihitung SEBELUM perubahan; respons HTTP membawa token berbasis waktu sehingga golden
dipatok di tingkat renderer dan HTTP dibuktikan lewat ketiadaan CTA).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_pages  # noqa: E402
import funnel_pages  # noqa: E402
import pesanan  # noqa: E402
import pesanan_http  # noqa: E402
from pesanan_http_kit import (  # noqa: E402
    AKUN_A, HASIL, PESAN, POLA_TOKEN, bayar, cek_selesai, jam, keluarga, mulai_cek, minta_mentah,
    server, tertutup,
)

HASIL_SELESAI = {"status": "selesai", "skor": 72, "kategori": "Cukup baik",
                 "ringkasan": {"kuat": ["Pola bilangan"], "perlu": ["Statistika"]}, "jumlah_soal": 15}
HASIL_BELUM = {"status": "belum_selesai", "skor": None, "kategori": None,
               "ringkasan": {"kuat": [], "perlu": []}, "jumlah_soal": 15}
# sha256 keluaran Fase 2 (halaman_hasil tanpa argumen pesan), diambil sebelum perubahan 3c-3.
# Diperbarui 19 Nov 2026: dua perubahan copy yang disengaja (nama tampilan "Peta Kemampuan" pada tautan CTA dan tiga
# butir "batas hasil" di funnel_pages.COPY_BATAS_HASIL). Dibuktikan lewat diff HTML: hanya empat baris itu yang
# berubah, CSS dan struktur identik. Bukan perubahan perilaku.
GOLDEN_SELESAI = "6b6efb26e5dbd394d8187e12a0e9ad7de8a79892709823e09932b7b8e2535efd"
GOLDEN_BELUM = "dd0dbade640c366361af10b7a2ddb52539682a97dc1b5374d8ba3e21405b88bc"


def _render(hasil, **kw):
    return cek_pages.halaman_hasil(("guru", "guru"), hasil, "Anak Sintetis", "123.tok", **kw)


def test_renderer_tanpa_token_pesan_byte_identik_dengan_fase_2():
    assert hashlib.sha256(_render(HASIL_SELESAI)).hexdigest() == GOLDEN_SELESAI
    assert hashlib.sha256(_render(HASIL_BELUM)).hexdigest() == GOLDEN_BELUM
    assert _render(HASIL_SELESAI, token_pesan=None) == _render(HASIL_SELESAI)


def test_renderer_dengan_token_pesan_menambah_hanya_form_pesan():
    isi = _render(HASIL_SELESAI, token_pesan="9.abc").decode()
    assert f'action="{PESAN}"' in isi and 'value="9.abc"' in isi and funnel_pages.COPY_HARGA in isi
    assert "Rp" + format(pesanan.RUPIAH_PAKET, ",").replace(",", ".") in funnel_pages.COPY_HARGA
    assert cek_pages.COPY_TOMBOL_PESAN in isi
    # hasil belum selesai tidak pernah memuat CTA pesan, bagaimanapun argumennya
    assert PESAN not in _render(HASIL_BELUM, token_pesan="9.abc").decode()


def test_gerbang_tertutup_halaman_hasil_selesai_tanpa_cta_pesan(tertutup):
    cek_selesai(tertutup)
    kode, isi, _t = minta_mentah(tertutup, HASIL, AKUN_A)
    assert kode == 200 and "Skor keseluruhan" in isi
    assert PESAN not in isi and cek_pages.COPY_TOMBOL_PESAN not in isi
    assert isi.count('name="token"') == 0  # hasil selesai Fase 2 tidak punya form sama sekali


def test_gerbang_terbuka_hasil_selesai_menampilkan_form_pesan_dengan_token_sah(bayar):
    cek_selesai(bayar)
    kode, isi, _t = minta_mentah(bayar, HASIL, AKUN_A)
    assert kode == 200 and f'action="{PESAN}"' in isi and cek_pages.COPY_TOMBOL_PESAN in isi
    tok = POLA_TOKEN.search(isi).group(1)
    from pesanan_http_kit import principal_basic_untuk
    assert pesanan_http.token_sah(principal_basic_untuk(AKUN_A), None, "pesan", tok)
    assert not pesanan_http.token_sah(principal_basic_untuk(AKUN_A), None, "buat", tok)


def test_gerbang_terbuka_hasil_belum_selesai_tanpa_form_pesan(bayar):
    mulai_cek(bayar, AKUN_A)
    kode, isi, _t = minta_mentah(bayar, HASIL, AKUN_A)
    assert kode == 200 and PESAN not in isi


def test_gerbang_terbuka_tetapi_funnel_mati_hasil_tanpa_cta(bayar, monkeypatch):
    cek_selesai(bayar)
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    kode, isi, _t = minta_mentah(bayar, HASIL, AKUN_A)
    assert PESAN not in isi and "belum dibuka" in isi.lower()

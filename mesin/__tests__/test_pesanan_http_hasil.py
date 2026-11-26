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
# sha256 keluaran halaman_hasil tanpa argumen pesan (kontrak: tanpa token_pesan tidak ada byte CTA pesan).
# Diperbarui 19 Nov 2026 dua kali, keduanya perubahan tampilan yang disengaja, bukan perilaku:
# (1) nama tampilan "Peta Kemampuan" pada tautan CTA dan tiga butir "batas hasil" di COPY_BATAS_HASIL;
# (2) desain ulang sisi orang tua sesuai prototipe (kepala skor dengan cincin, "X dari 15 soal benar", chip
# ringkasan, daftar terkunci, kotak batas, tautan contoh, tautan ke halaman siap mulai di hasil belum selesai).
# Kontrak "tanpa byte pesan" dijaga eksplisit oleh test_cta_pesan_tidak_meninggalkan_byte_saat_token_none.
# Diperbarui 24 Nov 2026 (golden sebelumnya di 0ac865e): CSS bersama (gerakan/pose maskot + shell murid)
# dan satu butir `COPY_KUNCI_BUTIR` ("Analisis kesalahan" -> "Catatan dari guru"); kontrak "tanpa byte pesan" tetap.
# Diperbarui 26 Nov 2026 (Peta otomatis, keputusan Pemilik: tanpa penyebutan Guru di jalur Peta): HANYA teks
# `COPY_LABEL_GAMBARAN`, `COPY_KUNCI_BUTIR[1]`, dan `COPY_KUNCI_CATATAN` di cek_pages (diverifikasi: dengan ketiga
# konstanta lama dipasang di memori, hash kembali ke nilai sebelumnya); struktur dan CSS tidak berubah.
GOLDEN_SELESAI = "4b6458efe6236269c8632a8af1fa11befbc6a5805290d5d9097bd1d611a38564"
GOLDEN_BELUM = "faf2aed98b1ae7588872e7365306a7ab624859b8d73f55241dbd3809b1456844"


def _render(hasil, **kw):
    return cek_pages.halaman_hasil(("guru", "guru"), hasil, "Anak Sintetis", "123.tok", **kw)


def test_renderer_tanpa_token_pesan_byte_identik_dengan_fase_2():
    assert hashlib.sha256(_render(HASIL_SELESAI)).hexdigest() == GOLDEN_SELESAI
    assert hashlib.sha256(_render(HASIL_BELUM)).hexdigest() == GOLDEN_BELUM
    assert _render(HASIL_SELESAI, token_pesan=None) == _render(HASIL_SELESAI)


def test_cta_pesan_tidak_meninggalkan_byte_saat_token_none():
    tanpa = _render(HASIL_SELESAI)
    dengan = _render(HASIL_SELESAI, token_pesan="9.abc")
    blok = cek_pages._blok_pesan("9.abc").encode()
    assert cek_pages._blok_pesan(None) == "" and blok in dengan
    assert dengan.replace(blok, b"") == tanpa


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

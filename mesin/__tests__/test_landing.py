"""Navigasi landing: satu pintu Masuk, brand = link beranda.

Kontrak:
1. /daftar: brand = anchor link ke /; nav hanya "Masuk"; tidak ada
   duplikat "Sudah punya akun? Masuk" di bawah form.
2. Homepage: nav hanya "Masuk" — sebagai tombol outline (tombol-putih),
   tetap kalah menonjol dari CTA coral; hero single CTA; footer tanpa /masuk.
3. Kedua halaman: tepat 1 href="/masuk".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import account_pages  # noqa: E402
import design_tokens as T  # noqa: E402
import support_settings  # noqa: E402
import web  # noqa: E402
from landing import (  # noqa: E402
    halaman_daftar,
    halaman_kebijakan,
    halaman_landing,
    halaman_lupa_sandi,
)


def _html(func, *a, **kw) -> str:
    if func in (halaman_landing, halaman_kebijakan, halaman_lupa_sandi) and 'dukungan' not in kw:
        kw['dukungan'] = support_settings.proyeksi_publik(support_settings.KonfigurasiDukungan(
            '082137111988', 'weekday_0900_1700_wib', 1, 3, 1, 1, 'sistem_uji'))
    return func(*a, **kw).decode()


# ──────────────────── halaman_daftar ────────────────────

def test_daftar_brand_adalah_link_beranda():
    h = _html(halaman_daftar)
    assert '<a class="brand" href="/">' in h


def test_daftar_tidak_ada_beranda_di_nav():
    h = _html(halaman_daftar)
    assert ">Beranda</a>" not in h


def test_daftar_href_masuk_tepat_satu():
    h = _html(halaman_daftar)
    assert h.count('href="/masuk"') == 1


def test_daftar_tidak_ada_duplikat_bawah_form():
    h = _html(halaman_daftar)
    assert "Sudah punya akun?" not in h


# ──────────────────── halaman_landing ───────────────────

def test_landing_href_masuk_tepat_satu():
    h = _html(halaman_landing)
    assert h.count('href="/masuk"') == 1


def test_landing_masuk_tombol_outline_di_nav():
    """Dulu Masuk sengaja teks polos (single-CTA), tapi tampilannya
    seperti lupa didesain. Sekarang tombol outline — tetap kalah
    menonjol dari CTA coral."""
    h = _html(halaman_landing)
    assert '<a class="tombol-putih" href="/masuk">Masuk</a>' in h


def test_landing_footer_tanpa_masuk():
    h = _html(halaman_landing)
    footer_start = h.index("<footer")
    footer = h[footer_start:]
    assert 'href="/masuk"' not in footer


def test_landing_brand_adalah_link_beranda():
    h = _html(halaman_landing)
    assert '<a class="brand" href="/">' in h


def test_landing_hero_single_cta():
    h = _html(halaman_landing)
    assert "Buat akun pendamping." in h
    # satu-satunya tombol-putih di halaman adalah "Masuk" di nav —
    # hero tetap punya CTA tunggal coral
    assert h.count('class="tombol-putih"') == 1


# ─────────────────── halaman_kebijakan ───────────────────

def test_kebijakan_tautan_sumber_aktif():
    """Tiga sumber menaut /kebijakan-privasi: footer landing, consent
    /daftar, dan consent anak-baru (account_pages.py). Halaman tujuannya
    wajib ada."""
    assert 'href="/kebijakan-privasi"' in _html(halaman_landing)
    assert 'href="/kebijakan-privasi"' in _html(halaman_daftar)
    sumber = Path(account_pages.__file__).read_text(encoding="utf-8")
    assert 'href="/kebijakan-privasi"' in sumber


def test_kebijakan_halaman_statis_lengkap():
    h = _html(halaman_kebijakan)
    assert "<h1>Kebijakan Privasi</h1>" in h
    assert '<a class="brand" href="/">' in h  # brand = link beranda
    assert h.count('href="/masuk"') == 1
    for bagian in ("Data yang dikumpulkan", "Data anak", "Siapa yang bisa melihat",
                   "Data yang tidak dikumpulkan", "penghapusan data"):
        assert bagian in h, f"bagian {bagian} hilang"


def test_kebijakan_sebut_laporan_pihak_ketiga():
    """Keterbukaan jujur: variasi cerita mengirim teks soal ke layanan AI."""
    h = _html(halaman_kebijakan)
    assert "layanan AI" in h
    assert "Terakhir diperbarui 30 September 2026" in h
    assert "sengaja mengunggah foto" in h
    assert "Pastikan izin orang tua/wali sudah ada" in h
    assert "belum memiliki gerbang persetujuan khusus" in h
    assert "Hasil AI hanya berupa usulan" in h
    assert "penyedia font tampilan" in h
    assert "Selain akses pengelola untuk dukungan operasional" in h
    assert "tidak terlihat oleh akun keluarga lain" in h
    assert "mengelola data murid semua" in h
    assert "termasuk profil, sesi, jawaban, koreksi" in h
    assert "lampiran, dan akun login murid" in h
    assert "tidak dapat mengubah akun atau" in h
    assert "sandi sesama pengelola" in h
    assert "tidak bisa mengubah data anak" not in h
    assert "Tidak ada pihak lain" not in h


def test_kebijakan_penghapusan_menunjuk_kontak():
    """Hapus seluruh keluarga hanya memulai proses manusia terverifikasi."""
    h = _html(halaman_kebijakan)
    assert "0821 3711 1988" in h
    assert "Penghapusan memerlukan verifikasi independen" in h


# ─────────────────── halaman_lupa_sandi ─────────────────

def test_lupa_sandi_renders_sebagai_html():
    h = _html(halaman_lupa_sandi)
    assert h.startswith("<!DOCTYPE html")


def test_lupa_sandi_memuat_judul_dan_panduan_murid():
    """Panduan murid harus konkret sampai tombolnya — bukan sekadar
    "hubungi kami": jalurnya kartu Akun latihan -> Setel sandi baru."""
    h = _html(halaman_lupa_sandi)
    assert "Lupa sandi?" in h
    assert "gurumu" in h
    assert "Akun latihan" in h
    assert "Setel sandi baru" in h


def test_lupa_sandi_panduan_orang_tua():
    h = _html(halaman_lupa_sandi)
    assert "dukungan" in h
    assert "daftar sendiri" in h
    assert "0821 3711 1988" in h
    assert "verifikasi independen" in h


def test_lupa_sandi_jelaskan_tanpa_email():
    """Aplikasi sengaja tanpa email — halaman ini harus menjelaskan itu
    apa adanya, bukan mengarang janji reset mandiri yang tidak ada."""
    h = _html(halaman_lupa_sandi)
    assert "tidak menyimpan email" in h


def test_lupa_sandi_murni_panduan_tanpa_form():
    """Tidak ada form apa pun di sini — reset mandiri memang tidak ada,
    halaman ini hanya menunjukkan jalurnya."""
    h = _html(halaman_lupa_sandi)
    assert "<form" not in h

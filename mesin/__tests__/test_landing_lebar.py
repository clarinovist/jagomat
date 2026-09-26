"""Landing lebar penuh — mengikuti mockup Stitch landing_page_desktop.

Keluhan nyata (4 Sep): di laptop 1512px konten landing hanya 736px
(48,7%) karena memakai kerangka form `publik-*-st` yang diklem
T.LEBAR_KONTEN=46rem. Mockup punya container 1200px + hero 2 kolom.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import design_tokens as T  # noqa: E402
from landing import halaman_landing  # noqa: E402
from style_stitch import GAYA_STITCH  # noqa: E402


def _html() -> str:
    return halaman_landing().decode()


# ──────────────── lebar: akar keluhan "cuma separo" ────────────────

def test_token_lebar_landing_lebih_lebar_dari_konten_baca():
    """Landing permukaan marketing, bukan kolom baca/form.

    46rem itu benar untuk form daftar & halaman kebijakan; di landing
    ia menyisakan 776px kosong pada layar 1512px.
    """
    def _rem(nilai: str) -> float:
        return float(nilai.replace("rem", ""))

    assert _rem(T.LEBAR_LANDING) > _rem(T.LEBAR_KONTEN)
    assert _rem(T.LEBAR_LANDING) >= 70  # >= 1120px, sekelas mockup 1200px


def test_bungkus_landing_pakai_token_lebar_landing():
    assert f".landing-bungkus-st" in GAYA_STITCH
    blok = GAYA_STITCH.split(".landing-bungkus-st", 1)[1].split("}", 1)[0]
    assert T.LEBAR_LANDING in blok, (
        "bungkus landing tidak memakai LEBAR_LANDING — halaman kembali "
        "terklem selebar form"
    )


def test_landing_tidak_memakai_bungkus_form_46rem():
    """Regresi persis yang dikeluhkan: markup landing memakai
    .publik-bungkus-st (46rem) sehingga tampil separo layar."""
    h = _html()
    assert 'class="publik-bungkus-st"' not in h
    assert 'class="publik-kartu-st"' not in h


def test_hero_dua_kolom_di_layar_lebar():
    """Mockup: teks kiri, kartu demo kanan. Di HP tetap satu kolom."""
    assert ".landing-hero-st" in GAYA_STITCH
    assert "grid-template-columns" in GAYA_STITCH.split(
        ".landing-hero-st", 1
    )[1][:1200]


# ──────────────── isi hero mengikuti mockup ────────────────

def test_hero_punya_kalimat_proposisi_bukan_hanya_nama_produk():
    h = _html()
    assert "Kenali kebutuhan. Dampingi latihan. Cek pemahaman." in h


def test_hero_masih_menyebut_nama_dan_tagline():
    h = _html()
    assert T.NAMA_PRODUK in h
    assert T.TAGLINE in h


def test_kartu_demo_menampilkan_diagnosis_nyata():
    """Bukti visual fitur inti — sama seperti mockup (345+128 → 463,
    kode H salah hitung)."""
    h = _html()
    assert "345" in h and "128" in h
    assert "landing-demo-st" in h
    assert "Salah hitung" in h


def test_kode_demo_konsisten_dengan_taksonomi():
    """Landing tidak boleh mengarang kode di luar B/K/H/E/T/N."""
    h = _html()
    for label in ("Salah baca", "Salah konsep", "Salah hitung"):
        assert label in h


def test_pill_fitur_ada():
    h = _html()
    assert "landing-pill-st" in h


# ──────────────── kejujuran klaim ────────────────

def test_tidak_mengklaim_tulis_tangan():
    """Mockup menulis 'Tulis Tangan'; aplikasi tidak punya input tulis
    tangan — yang ada foto lembar + AI vision yang dikonfirmasi guru."""
    h = _html().lower()
    assert "tulis tangan" not in h


def test_tidak_mengklaim_gratis_komersial():
    """Jangan menjanjikan akses gratis saat penawaran publik belum dibuka."""
    h = _html().lower()
    assert "gratis" not in h
    assert "paket dan pembayaran publik sedang disiapkan" in h


# ──────────────── contoh dan bantuan pendamping ────────────────

def test_landing_memuat_contoh_diagnosis_bkh():
    """Tiga contoh B/K/H dengan penanda ilustrasi, bukan data anak."""
    h = _html()
    for frasa in ("Salah konsep", "Salah baca", "Salah hitung",
                  "5/7", "Contoh tertulis"):
        assert frasa in h, f"contoh diagnosis kehilangan: {frasa}"


def test_landing_memuat_bantuan_pendamping_bukan_rekrutmen_pilot():
    rendah = _html().lower()
    assert 'id="judul-pendamping-landing"' in rendah
    assert "pendamping membantu lewat percakapan" in rendah
    for frasa in ("ikut pilot", "10–20 keluarga", "6 sesi", "testimoni"):
        assert frasa not in rendah


def test_landing_faq_tanpa_js():
    """FAQ memakai <details> bawaan browser — tanpa <script> baru di
    blok konten yang ditambahkan. <script> mata sandi + cegah kirim
    ganda adalah bawaan kerangka _halaman_publik_stitch di ekor
    halaman, jadi batasnya </section> terakhir, bukan akhir body."""
    h = _html()
    assert h.count("<details>") >= 5
    konten = h.split('<section class="landing-faq-st"', 1)[1].split("</section>", 1)[0]
    assert "<details>" in konten
    assert "<script" not in konten


def test_landing_footer_memuat_kontak_wa():
    """Footer menaut kebijakan + kontak WA dari T.WA_SUPPORT (sumber
    tunggal, bukan nomor literal di markup)."""
    h = _html()
    footer = h[h.index("<footer"):]
    assert 'href="/kebijakan-privasi"' in footer
    assert T.WA_SUPPORT in footer


def test_landing_tetap_single_cta():
    """Blok baru tidak boleh menambah CTA tandingan — satu-satunya
    anchor coral tetap "Mulai — daftar sekarang" ke /daftar. (Hitungan
    dibatasi ke markup <a>, karena string "tombol-coral" juga muncul di
    blok <style> CSS.)"""
    h = _html()
    assert h.count('href="/daftar"') == 1
    assert h.count('<a class="tombol-coral"') == 1


# ──────────────── zero-JS & kontrol mati ────────────────

def test_landing_tanpa_kontrol_mati():
    """Mockup memakai <button> yang tidak melakukan apa pun. Di produk,
    tombol yang tidak bisa ditekan = bug."""
    h = _html()
    assert "<button" not in h
    assert "<input" not in h


def test_landing_tanpa_cdn_tailwind():
    h = _html()
    assert "tailwindcss" not in h
    assert "tailwind.config" not in h


def test_logo_dari_brand_bukan_url_asing():
    h = _html()
    assert "googleusercontent" not in h
    assert 'src="/aset/' in h


# ──────────────── kontrak lama tidak boleh pecah ────────────────

def test_kontrak_navigasi_tetap():
    h = _html()
    assert h.count('href="/masuk"') == 1
    assert '<a class="brand" href="/">' in h
    assert h.count('class="tombol-putih"') == 1
    assert "Mulai — daftar sekarang" in h


def test_footer_tetap_menaut_kebijakan_tanpa_masuk():
    h = _html()
    footer = h[h.index("<footer"):]
    assert 'href="/kebijakan-privasi"' in footer
    assert 'href="/masuk"' not in footer

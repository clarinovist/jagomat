"""Permukaan publik funnel Cek Kemampuan (Fase 1), data sepenuhnya sintetis.

Sakelar `FUNNEL_AKTIF` menjaga rilis, jadi tes memeriksa kedua arahnya lewat
server nyata (`http_test_kit.ServerUji`) dan renderer langsung.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand  # noqa: E402
import funnel_pages  # noqa: E402
import funnel_style  # noqa: E402
import landing  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

RUTE = ("/cek-kemampuan", "/paket-coba")
CTA = 'href="/daftar?jalur=cek"'
KATA_TERLARANG = ("diagnosis lengkap", "pasti akurat", "Rp200.000", "Rp151.000", "nilai pasti naik")


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


def _badan(isi: str) -> str:
    """Badan halaman tanpa blok <style>, dan tanpa lambang brand (style bawaan <img>)."""
    badan = isi.rsplit("</style>", 1)[1]
    return badan.replace(brand.mark("topbar"), "")


@pytest.mark.parametrize("jalur", RUTE)
def test_sakelar_mati_status_belum_dibuka_tanpa_cta_dan_form(server, jalur):
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    assert "belum dibuka" in isi.lower()
    assert "/daftar?jalur=cek" not in isi
    assert "<form" not in isi
    assert 'href="/"' in isi and 'href="/masuk"' in isi


@pytest.mark.parametrize("nilai", ["0", "", "true", "2", " 11 "])
@pytest.mark.parametrize("jalur", RUTE)
def test_nilai_sakelar_selain_satu_tetap_mati(server, monkeypatch, jalur, nilai):
    monkeypatch.setenv("FUNNEL_AKTIF", nilai)
    kode, isi, _ = server.minta(jalur)
    assert kode == 200 and "belum dibuka" in isi.lower()
    assert "/daftar?jalur=cek" not in isi


@pytest.mark.parametrize("jalur", RUTE)
def test_sakelar_hidup_halaman_penuh_satu_cta(server, monkeypatch, jalur):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    kode, isi, _ = server.minta(jalur)
    assert kode == 200
    assert isi.count(CTA) == 1
    assert "<form" not in isi
    assert "belum dibuka" not in isi.lower()
    for kata in KATA_TERLARANG:
        assert kata.lower() not in isi.lower(), kata
    assert 'style="' not in _badan(isi)
    assert "contoh ilustrasi" in isi.lower() or jalur == "/paket-coba"


def test_cek_kemampuan_punya_label_contoh_dan_anchor(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _, isi, _ = server.minta("/cek-kemampuan")
    assert "contoh ilustrasi, bukan hasil anak sungguhan" in isi.lower()
    assert 'id="contoh-hasil"' in isi


def test_paket_coba_memakai_kalimat_disetujui_dan_jujur(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _, isi, _ = server.minta("/paket-coba")
    assert funnel_pages.COPY_BUKAN_LANGGANAN == "Bukan langganan, jadi bulan depan tidak ada tagihan lagi."
    for kalimat in (
        funnel_pages.COPY_TIDAK_KEMBALI,
        funnel_pages.COPY_KONSULTASI,
        funnel_pages.COPY_DEPOSIT,
        funnel_pages.COPY_PAKET_DARI_HASIL,
        *funnel_pages.COPY_BATAS_HASIL,
    ):
        assert kalimat in isi
    for tebal, sisa in funnel_pages.COPY_PEMBATALAN_BUTIR:
        assert f"<b>{tebal}</b>{sisa}" in isi
    assert funnel_pages.COPY_PEMBATALAN.startswith("Peta Kemampuan tidak bisa dikembalikan")
    assert "kamu" not in funnel_pages.COPY_PEMBATALAN.lower().split()
    assert "Biar harapannya pas" in isi


def _teks(isi: str) -> str:
    badan = _badan(isi).split("<footer", 1)[0]
    badan = re.sub(r"<svg.*?</svg>", " ", badan, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", badan).split())


def test_landing_memakai_nama_peta_kemampuan_bukan_paket_coba(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    for jalur in RUTE:
        _, isi, _ = server.minta(jalur)
        assert "Peta Kemampuan" in isi
        assert "Paket Coba" not in isi
    assert "Paket Coba" not in landing.halaman_landing().decode()


def test_kalimat_deposit_dan_terlambat_draf5_dipakai_harfiah():
    ks = "Rp49.000 Anda menjadi potongan biaya bulan pertama kelas Jagomat, bila Anda daftar dalam 90 hari"
    assert funnel_pages.COPY_PAKET_ISI[2] == ks
    assert funnel_pages.COPY_TIDAK_KEMBALI == "Peta Kemampuan tidak bisa dikembalikan karena Guru langsung mengerjakan laporannya. Rp49.000 Anda menjadi potongan biaya bulan pertama kelas Jagomat, bila Anda daftar dalam 90 hari."
    assert funnel_pages.COPY_DEPOSIT == "Rp49.000 Anda menjadi potongan biaya bulan pertama kelas Jagomat, bila Anda daftar dalam 90 hari."
    assert funnel_pages.COPY_PEMBATALAN_BUTIR[0] == ("Peta Kemampuan tidak bisa dikembalikan karena Guru langsung mengerjakan laporannya. ", "Rp49.000 Anda menjadi potongan biaya bulan pertama kelas Jagomat, bila Anda daftar dalam 90 hari.")
    assert funnel_pages.COPY_PEMBATALAN_BUTIR[2] == (
        "Laporan terbit dalam 48 jam setelah pembayaran.",
        " Kalau terlambat, hubungi tim lewat WhatsApp. Kami bantu sampai laporan Anda terbit.")
    for kalimat in (funnel_pages.COPY_TIDAK_KEMBALI, funnel_pages.COPY_DEPOSIT, *funnel_pages.COPY_PAKET_ISI,
                    *(a + b for a, b in funnel_pages.COPY_PEMBATALAN_BUTIR)):
        assert "program belajar" not in kalimat and "dicatat oleh tim" not in kalimat
        for lama in ("voucher", "3×24", "uang kembali penuh", "memilih tetap menunggu", "halaman pesanan",
                     "otomatis memotong", "otomatis dipotong", "pola kesalahan", "pola salah"):
            assert lama not in kalimat.lower(), lama
    assert not hasattr(funnel_pages, "COPY_PIL_VOUCHER")


def test_paket_coba_menyatakan_tidak_dapat_dikembalikan(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _, isi, _ = server.minta("/paket-coba")
    assert "tidak bisa dikembalikan" in isi
    assert "menjadi potongan biaya bulan pertama kelas Jagomat" in isi
    assert "Jadi potongan kelas Jagomat" in isi and "voucher" not in _teks(isi).lower()


def test_landing_ringkas_dan_tanpa_penanda_mockup(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _, isi, _ = server.minta("/cek-kemampuan")
    jumlah = len(_teks(isi).split())
    assert jumlah <= 900, jumlah  # landing playful v4: cerita, demo, hasil gratis, FAQ ikut terhitung
    for penanda in ("[nama, latar", "Draf:", "Kuota masih usulan"):
        assert penanda not in isi
    utama = isi.split('id="konten"', 1)[1].split("</main>", 1)[0]
    assert "<script" not in utama
    assert funnel_pages.MASKOT_MENYAPA in isi


@pytest.mark.parametrize("aktif", [None, "1"])
@pytest.mark.parametrize("jalur", RUTE)
def test_anonim_dan_guru_login_sama_sama_200(server, monkeypatch, jalur, aktif):
    if aktif:
        monkeypatch.setenv("FUNNEL_AKTIF", aktif)
    anonim = server.minta(jalur)
    guru = server.minta(jalur, auth=("guru", SANDI_GURU))
    assert anonim[0] == guru[0] == 200
    assert "perlu masuk" not in guru[1].lower()


@pytest.mark.parametrize("aktif", [None, "1"])
@pytest.mark.parametrize("jalur", RUTE)
def test_post_bukan_halaman_funnel(server, monkeypatch, jalur, aktif):
    if aktif:
        monkeypatch.setenv("FUNNEL_AKTIF", aktif)
    for auth in (None, ("guru", SANDI_GURU)):
        kode, isi, _ = server.minta(jalur, data={}, auth=auth)
        assert kode != 200
        assert CTA not in isi and "belum dibuka" not in isi.lower()


def test_landing_mati_tanpa_tautan_funnel(monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    isi = landing.halaman_landing().decode()
    assert "/cek-kemampuan" not in isi
    assert funnel_style.GAYA_FUNNEL.split("\n")[2] not in isi  # CSS funnel tidak ikut
    assert isi.count('href="/masuk"') == 1


def test_landing_hidup_tepat_satu_tautan_di_nav(monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    isi = landing.halaman_landing().decode()
    assert isi.count('href="/cek-kemampuan"') == 1
    assert isi.count('href="/masuk"') == 1
    nav = isi.split('<nav class="topbar-navigasi"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/cek-kemampuan">Cek kemampuan</a>' in nav


def test_landing_hidup_hanya_beda_satu_baris_nav(monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    mati = landing.halaman_landing().decode()
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    hidup = landing.halaman_landing().decode()
    baris_mati = mati.rsplit("</style>", 1)[1].splitlines()
    baris_hidup = hidup.rsplit("</style>", 1)[1].splitlines()
    tambahan = [b for b in baris_hidup if b not in baris_mati]
    assert tambahan == ['<a class="landing-nav-st" href="/cek-kemampuan">Cek kemampuan</a>']


def test_css_funnel_tanpa_hex_dan_dipasang_saat_hidup(monkeypatch):
    sumber = Path(funnel_style.__file__).read_text()
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
    assert "!important" not in funnel_style.GAYA_FUNNEL
    from style_stitch import gaya_stitch

    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    assert ".funnel-harga-st" not in gaya_stitch()
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    assert ".funnel-harga-st" in gaya_stitch()


def test_markup_halaman_tanpa_hex_literal_dan_kelas_funnel_terdefinisi():
    for fn in (funnel_pages.halaman_cek_kemampuan, funnel_pages.halaman_paket_coba):
        badan = _badan(fn().decode())
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", re.sub(r'href="#[\w-]+"', "", badan))
        for kelas in set(re.findall(r"funnel-[a-z-]+-st", badan)):
            assert f".{kelas}" in funnel_style.GAYA_FUNNEL, kelas


def test_isi_paket_tidak_menjanjikan_latihan_30_hari_yang_belum_ada():
    # Audit 21 Nov 2026: tidak ada akses/kode latihan 30 hari; janji yang belum bisa dipenuhi tidak dipajang.
    for butir in funnel_pages.COPY_PAKET_ISI:
        assert "30 hari" not in butir
    halaman = funnel_pages.halaman_paket_coba().decode("utf-8")
    assert "Latihan 30 hari" not in halaman


"""Narasi publik sesuai produk, tanpa janji pilot atau fitur yang belum dibuka."""
from html.parser import HTMLParser

import pytest

from landing import halaman_landing


class _TeksPublik(HTMLParser):
    """Ambil teks terlihat, bukan nama kelas CSS atau skrip kerangka."""

    def __init__(self, sumber):
        super().__init__()
        self.lewati = False
        self.teks = []
        self.meta = {}
        self.feed(sumber)

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.lewati = True
        if tag == "meta":
            atribut = dict(attrs)
            self.meta[atribut.get("property", atribut.get("name"))] = atribut.get("content", "")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.lewati = False

    def handle_data(self, data):
        if not self.lewati:
            self.teks.append(data)


@pytest.fixture
def publik():
    return _TeksPublik(halaman_landing().decode())


def _teks(publik):
    return " ".join(" ".join(publik.teks).split())


def test_tidak_merekrut_pilot_atau_menjanjikan_checkout(publik):
    teks = _teks(publik).lower()
    for lama in ("pilot", "10–20 keluarga", "testimoni", "gratis", "harga belum diputuskan"):
        assert lama not in teks
    assert "paket dan pembayaran publik sedang disiapkan" in teks
    assert "qris sudah tersedia" not in teks


def test_rencana_melampaui_diagnosis_dan_latihan_ulang(publik):
    teks = _teks(publik).lower()
    for bagian in ("pemetaan", "fokus", "contoh", "latihan terbimbing", "penguatan",
                   "cek berjeda", "cek berkala", "tinjau dan konfirmasi", "latihan manual"):
        assert bagian in teks
    assert "sistem mendiagnosis:" not in teks


def test_langkah_cara_kerja_tidak_memakai_teks_tebal_gelap():
    """CSS existing membuat b gelap dan memisahkannya sebagai item flex."""
    sumber = halaman_landing().decode()
    cara = sumber.split('<section class="landing-kartu-st landing-cara-st">', 1)[1]
    daftar = cara.split("<ol>", 1)[1].split("</ol>", 1)[0]
    assert "Tinjau dan konfirmasi" in daftar
    assert "<b>" not in daftar


def test_penguasaan_bukan_nilai_atau_klaim_seluruh_kurikulum(publik):
    teks = _teks(publik).lower()
    assert "peta penguasaan" in teks
    assert "bisa menjelaskan" in teks
    assert "bukan nilai rapor atau ukuran seluruh kurikulum" in teks


def test_contoh_tidak_memvonis_penyebab_atau_waktu_pemulihan(publik):
    teks = _teks(publik).lower()
    for lama in ("4–6 minggu", "2–3 minggu", "gejala terburu-buru", "caranya sudah benar"):
        assert lama not in teks
    assert "dugaan awal" in teks
    assert "bukan diagnosis dari jawaban akhir saja" in teks
    assert "473" in teks and "463" in teks


def test_pendamping_bersyarat_dan_bukan_pengganti_penilaian(publik):
    teks = _teks(publik).lower()
    assert "pendamping" in teks
    assert "bila fitur aktif dan kamu menyetujui" in teks
    assert "bukan penentu diagnosis atau pengganti tinjauanmu" in teks


def test_privasi_mengungkap_pengiriman_ai_dan_izin(publik):
    teks = _teks(publik).lower()
    assert "server pengelola" in teks
    assert "layanan ai pihak ketiga" in teks
    assert "foto lembar" in teks
    assert "izin orang tua/wali" in teks
    assert "persetujuan terpisah" in teks
    assert "bukan cloud pihak ketiga" not in teks


def test_deskripsi_share_mencerminkan_rencana_dan_penguasaan(publik):
    deskripsi = publik.meta["og:description"].lower()
    assert "rencana belajar" in deskripsi
    assert "peta penguasaan" in deskripsi
    assert "pilot" not in deskripsi

"""Narasi publik sesuai produk, tanpa janji pilot atau fitur yang belum dibuka."""
from html.parser import HTMLParser
import re

import pytest

from landing import halaman_landing
import subscription_packages as paket


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
    for lama in ("pilot", "10–20 keluarga", "testimoni", "harga belum diputuskan",
                 "coba gratis sekarang", "qris sudah tersedia"):
        assert lama not in teks
    assert "penawaran belum dibuka" in teks
    assert "tanggal pembukaan dan ketentuan peserta promo belum diumumkan" in teks
    assert "pendaftaran saat ini belum mengaktifkan masa coba atau promo" in teks
    assert "tidak memicu pembayaran" in teks


def test_penawaran_hero_tidak_menjanjikan_aktivasi_saat_daftar():
    sumber = halaman_landing().decode()
    hero = sumber.split('<div class="landing-hero-teks-st">', 1)[1].split('</div>', 1)[0]
    teks = _teks(_TeksPublik(hero)).lower()
    assert "rencana penawaran: coba gratis 30 hari" in teks
    assert "mulai rp25.000/bulan untuk 1 profil anak" in teks
    assert "3 periode berbayar pertama bagi peserta promo" in teks
    assert "penawaran belum dibuka; pendaftaran belum mengaktifkan masa coba atau promo" in teks


def test_rincian_harga_konsisten_dengan_domain():
    sumber = halaman_landing().decode()
    kartu = re.findall(r'<section class="landing-paket-kartu-st[^\"]*" data-paket="([^\"]+)">(.*?)</section>', sumber, re.S)
    assert len(kartu) == 4
    for (kode, isi), periode in zip(kartu, ("bulanan", "bulanan", "tahunan", "tahunan")):
        teks = _teks(_TeksPublik(isi))
        p = paket.ambil_paket(kode)
        harga = paket.penawaran(kode, periode, 1, peserta_promo=True, periode_dibayar=0)
        assert p.nama in teks and "1 profil anak termasuk" in teks
        for nominal in (harga.rupiah, harga.normal):
            assert f"Rp{nominal:,}".replace(",", ".") in teks
        assert "Lalu " + f"Rp{harga.normal:,}".replace(",", ".") in teks
        if periode == "tahunan":
            assert "Dibayar sekaligus di muka" in teks and "Tahun pertama bagi peserta promo" in teks
        else:
            assert "3 periode berbayar pertama bagi peserta promo" in teks
        if kode == "jago_pro":
            assert "50 balasan Pendamping AI" in teks and "5 pembacaan foto" in teks
        else:
            assert "Tanpa Pendamping AI dan pembacaan foto" in teks


def test_durasi_dan_syarat_promo_tidak_menyesatkan(publik):
    teks = _teks(publik).lower()
    assert f"coba gratis {paket.DURASI_COBA // 86400} hari" in teks
    for ketentuan in (
        "satu kali untuk semua member", "bukan paket gratis permanen",
        "10 balasan ai + 2 pembacaan foto selama 30 hari",
        "3 periode yang dibayar, bukan 3 bulan sejak daftar",
        "tahun berbayar pertama", "bukan diskon yang ditumpuk",
        "tanpa promo, berlaku tarif normal", "termasuk pajak bila berlaku",
        "kuota ai tidak dikalikan jumlah anak", "rp10.000/bulan", "rp100.000/tahun",
        "dalam 7 × 24 jam sejak pembayaran berhasil", "nominal yang dibayar",
        "bukan janji waktu dana kembali", "tidak otomatis ditagih",
    ):
        assert ketentuan in teks
    assert "100 akun publik" not in teks and "8 minggu" not in teks


def test_faq_biaya_sesuai_harga_dan_status_penawaran():
    sumber = halaman_landing().decode()
    faq = sumber.split('<summary>Bagaimana dengan biaya?</summary>', 1)[1].split('</details>', 1)[0]
    teks = _teks(_TeksPublik(faq)).lower()
    for frasa in ("coba gratis 30 hari untuk semua member", "jago atau jago pro",
                  "rp25.000/bulan bagi peserta promo", "bulanan atau tahunan", "penawaran belum dibuka",
                  "belum mengaktifkan masa coba atau promo", "tidak memicu pembayaran"):
        assert frasa in teks
    assert 'href="#harga"' in faq


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

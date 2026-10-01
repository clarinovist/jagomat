"""Copy akses awal harus sesuai fitur publik yang benar-benar aktif."""
from html.parser import HTMLParser

import pytest

from landing import halaman_landing


class _TeksPublik(HTMLParser):
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


def test_hero_akses_awal_nonkomersial_dan_audiens_utama(publik):
    teks = _teks(publik)
    assert "Pahami cara berpikir anak. Dampingi langkah berikutnya." in teks
    assert "Buat akun pendamping." in teks
    assert "Akses awal nonkomersial" in teks
    assert "orang tua yang ingin membantu anak kelas 3–6" in teks
    assert "Guru dan pendamping les juga dapat memakai alur yang sama" in teks


def test_klaim_komersial_nonaktif_tidak_kembali_ke_alur_utama(publik):
    teks = _teks(publik).lower()
    for klaim in (
        "30 hari gratis", "coba gratis", "harga promo", "refund",
        "pengembalian dana", "rp25.000", "rp235.000", "rp49.000",
        "balasan ai", "pembacaan foto selama", "pilih periode pembayaran",
    ):
        assert klaim not in teks
    assert "jago/jago pro sedang disiapkan" in teks
    assert "pendaftaran saat ini tidak mengaktifkan paket, masa coba, promo, atau pembayaran" in teks


def test_faq_menjawab_alur_biaya_privasi_recourse_dan_batas(publik):
    teks = _teks(publik).lower()
    for frasa in (
        "siapa yang paling cocok", "bagaimana memulai latihan pertama",
        "apakah paket atau pembayaran sudah aktif", "bagaimana jagomat memakai data dan ai",
        "lupa sandi bagaimana", "bagaimana meminta penghapusan data keluarga",
        "bukan pengganti seluruh pelajaran sekolah", "bukan", "janji prestasi kompetisi",
    ):
        assert frasa in teks


def test_langkah_belajar_melampaui_diagnosis_dan_latihan_ulang(publik):
    teks = _teks(publik).lower()
    for bagian in ("latihan awal", "periksa hasil bersama", "langkah berikutnya",
                   "catatan awal", "bisa menjelaskan", "latihan manual"):
        assert bagian in teks
    for jargon in ("pemetaan", "intervensi", "latihan terbimbing", "penguatan mandiri",
                   "evaluasi berjeda", "checkpoint", "putaran"):
        assert jargon not in teks
    assert "sistem mendiagnosis:" not in teks


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
    assert "izin orang tua/wali" in teks
    assert "persetujuan terpisah" in teks


def test_deskripsi_share_berfokus_pendampingan_bukan_kompetisi(publik):
    deskripsi = publik.meta["og:description"].lower()
    assert "memahami cara berpikir" in deskripsi
    assert "langkah belajar berikutnya" in deskripsi
    assert "osn" not in deskripsi and "sasmo" not in deskripsi

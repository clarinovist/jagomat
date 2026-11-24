"""Renderer murni kartu "Data cek untuk laporan" di Detail order admin (D1): copy, escape, tanpa form/JS.

Tes di sini menjadi sasaran mutation di `test_admin_pesanan_cek_mutation.py`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pesanan_detail_pages as dp  # noqa: E402

ORDER = "ord_" + "a" * 32
JUDUL = "Data cek untuk laporan"
TERLARANG = ("kunci", "malrule", "diagnos", "kode_final", "pembahasan", "jawaban benar", "tel:", "wa.me",
             "<form", "<button", "<script", "<input")
PER_MATERI = [{"materi": "Berhitung di sekolah", "benar": 5, "total": 5},
              {"materi": "Bangun datar", "benar": 0, "total": 2}]


def _cek(**ganti):
    dasar = {"status": "selesai", "kelas": 4, "skor": 47, "kategori": "Perlu penguatan", "jumlah_soal": 15,
             "selesai_pada": "2026-11-18T09:00:00", "ringkasan_kuat": ["Berhitung di sekolah"],
             "ringkasan_perlu": ["Bangun datar"], "per_materi": PER_MATERI, "bahan": "ada", "hari_tersisa": 12}
    return {**dasar, **ganti}


def _detail(**ganti):
    dasar = {"order_id": ORDER, "akun": "akun_a1a1a1a1", "status": "sudah_dibayar", "dibuat": "2026-11-18T10:00:00",
             "kedaluwarsa": "2026-11-19T10:00:00", "cara": "qris", "nominal": None, "jumlah_bukti": 0,
             "langkah": ({"kode": "dibuat", "waktu": "2026-11-18T10:00:00", "jumlah": 0},)}
    return {**dasar, **ganti}


def _halaman(**ganti):
    return dp.halaman(_detail(**ganti), gerbang_terbuka=True, forms={})


def _kartu(isi: str) -> str:
    """Hanya <section> kartu data cek (bingkai/kartu lain boleh memuat kata yang dilarang di kartu ini)."""
    bagian = [b for b in isi.split("<section") if "<h2>%s</h2>" % JUDUL in b]
    assert len(bagian) == 1, "kartu data cek harus tepat satu"
    return bagian[0].split("</section>")[0]


def _teks(kartu: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", kartu))


def test_tanpa_kunci_cek_tidak_ada_kartu():
    assert JUDUL not in _halaman()


def test_kartu_tampil_setelah_kartu_voucher_dan_sebelum_perjalanan():
    isi = _halaman(cek=_cek())
    assert isi.index(JUDUL) < isi.index("<h2>Perjalanan order</h2>")
    isi_purna = _halaman(cek=_cek(), purna={"terpasang": False})
    assert isi_purna.index(dp.COPY_JUDUL_PURNA) < isi_purna.index(JUDUL)


def test_cek_tidak_terbaca_menampilkan_pesan_tanpa_tabel():
    kartu = _kartu(_halaman(cek=None))
    assert "Data cek tidak terbaca" in kartu and "<table" not in kartu


def test_bahan_ada_menampilkan_kelas_skor_ringkasan_tabel_dan_sisa_hari():
    teks = _teks(_kartu(_halaman(cek=_cek())))
    assert "Kelas 4" in teks and "47" in teks and "Perlu penguatan" in teks
    assert "Berhitung di sekolah" in teks and "Bangun datar" in teks
    assert "Data per materi dihapus otomatis dalam 12 hari (retensi 30 hari). Buat draf laporan sebelum itu." in teks
    kartu = _kartu(_halaman(cek=_cek()))
    assert re.search(r'<th scope="row">Berhitung di sekolah</th>\s*<td>5</td>\s*<td>5</td>', kartu)
    assert re.search(r'<th scope="row">Bangun datar</th>\s*<td>0</td>\s*<td>2</td>', kartu)


def test_bahan_dihapus_menampilkan_pesan_tanpa_tabel_dan_tanpa_hitungan_hari():
    kartu = _kartu(_halaman(cek=_cek(bahan="dihapus", per_materi=[], hari_tersisa=None)))
    assert "Data per materi sudah dihapus (retensi 30 hari)" in kartu
    assert "<table" not in kartu and "dalam" not in kartu


def test_belum_dinilai_menampilkan_pesan_tanpa_tabel():
    kartu = _kartu(_halaman(cek=_cek(bahan="belum_dinilai", per_materi=[], hari_tersisa=3)))
    assert "Belum dinilai" in kartu and "<table" not in kartu and "dihapus otomatis" not in kartu


def test_cek_belum_selesai_tanpa_skor_menampilkan_belum_selesai():
    kartu = _kartu(_halaman(cek=_cek(status="belum_selesai", skor=None, kategori=None, selesai_pada=None,
                                     ringkasan_kuat=[], ringkasan_perlu=[], per_materi=[], bahan="belum_dinilai",
                                     hari_tersisa=None)))
    assert "Cek belum selesai" in kartu and "Belum dinilai" in kartu and "None" not in kartu


def test_kelas_kosong_tampil_strip_bukan_none():
    kartu = _kartu(_halaman(cek=_cek(kelas=None)))
    assert "None" not in kartu and "Kelas" in kartu


def test_semua_nilai_di_escape():
    jahat = "<script>alert(1)</script>"
    cek = _cek(kategori=jahat, ringkasan_kuat=[jahat], ringkasan_perlu=[jahat], selesai_pada=jahat,
               per_materi=[{"materi": jahat, "benar": 1, "total": 2}])
    isi = _halaman(cek=cek)
    assert "<script>alert(1)" not in _kartu(isi)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in _kartu(isi)


@pytest.mark.parametrize("cek", [
    None, _cek(), _cek(bahan="dihapus", per_materi=[], hari_tersisa=None),
    _cek(bahan="belum_dinilai", per_materi=[], hari_tersisa=None),
    _cek(status="belum_selesai", skor=None, kategori=None, selesai_pada=None, ringkasan_kuat=[],
         ringkasan_perlu=[], per_materi=[], bahan="belum_dinilai", hari_tersisa=None),
])
def test_kartu_tanpa_kata_terlarang_form_tombol_atau_skrip(cek):
    kartu = _kartu(_halaman(cek=cek)).lower()
    assert [k for k in TERLARANG if k in kartu] == []


@pytest.mark.parametrize("status,berlaku", [
    ("sudah_dibayar", True), ("belum_bayar", False), ("kedaluwarsa", False), ("perlu_diperiksa", False),
    ("menunggu_verifikasi", False), ("ditolak", False), ("direfund", False),
])
def test_gerbang_kartu_cek_hanya_untuk_status_sudah_dibayar(status, berlaku):
    import pesanan_admin_order as po
    assert po.kartu_cek_berlaku(status) is berlaku

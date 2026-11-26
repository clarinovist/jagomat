"""Laporan Peta yang diterbitkan sistem (`oleh_sistem`) dan copy jalur Peta di halaman orang tua.

Data sintetis. Kontrak: dict `peta` boleh memuat `oleh_sistem` (bool). Tanpa kunci atau False berarti laporan Guru
(jalur lama), dan keluarannya harus identik dengan sebelum kunci itu ada (sidik SHA-256 di bawah). Laporan sistem tidak
memuat lencana, blok catatan, atau kata "Guru", dan teks catatan sistem tidak pernah tampil.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import orang_tua_pages as halaman  # noqa: E402
import peta_laporan_ortu_pages as blok  # noqa: E402
import pesanan_pages  # noqa: E402
from orang_tua_data import DataOrangTua  # noqa: E402
from pesanan_murid_kit import KEADAAN_TERLAMBAT  # noqa: E402

CATATAN_SISTEM_UJI = "CATATAN_SISTEM_UJI_TIDAK_BOLEH_TAMPIL"
# Sidik keluaran blok_peta(_peta_guru()) dari kode SEBELUM kunci oleh_sistem ada (26 Nov 2026).
SIDIK_LAPORAN_GURU = "5046c82f4093a66ff2e993199b7a89deac895b360a99fff667c63ef03bd46d59"


def _isi() -> dict:
    return {
        "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
        "jumlah_soal": 15,
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 7}],
        "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran"], "ringkasan_perlu": ["Pengukuran"],
    }


def _peta_guru() -> dict:
    catatan = "Anak sudah mantap berhitung.\nLatih pengukuran tiga kali seminggu.\n\nBagus <b>sekali</b> & rapi."
    return {"isi": _isi(), "catatan": catatan, "diterbitkan": "2026-11-24 15:00:00"}


def _peta_sistem() -> dict:
    return {**_peta_guru(), "catatan": CATATAN_SISTEM_UJI, "oleh_sistem": True}


def _sidik(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _bagian(html: str, id_bagian: str) -> str:
    cocok = re.search(r'<section[^>]*id="%s".*?</section>' % id_bagian, html, re.S)
    return cocok.group(0) if cocok else ""


def _halaman_dengan(peta=None, purna=None, status=pesanan_pages.STATUS_SUDAH_DIBAYAR) -> str:
    data = DataOrangTua(
        nama_anak="Anak Uji", hasil_cek={"status": "belum_mulai"}, laporan=None,
        status_pesanan=status, purna=purna, peta=peta,
    )
    return halaman.halaman_isi(data, ada_pin=False).decode("utf-8")


def test_laporan_guru_tanpa_kunci_oleh_sistem_identik_dengan_keluaran_lama():
    # Arrange
    peta = _peta_guru()
    # Act
    html = blok.blok_peta(peta)
    # Assert
    assert _sidik(html) == SIDIK_LAPORAN_GURU


def test_laporan_guru_dengan_oleh_sistem_false_identik_dengan_keluaran_lama():
    html = blok.blok_peta({**_peta_guru(), "oleh_sistem": False})
    assert _sidik(html) == SIDIK_LAPORAN_GURU


def test_laporan_guru_tetap_menampilkan_lencana_dan_catatan_guru():
    html = blok.blok_peta(_peta_guru())
    assert "Ditinjau Guru Jagomat" in html and "Catatan dari Guru" in html
    assert "Anak sudah mantap berhitung." in html


def test_catatan_guru_tetap_di_escape_pada_jalur_lama():
    html = blok.blok_peta(_peta_guru())
    assert "Bagus &lt;b&gt;sekali&lt;/b&gt; &amp; rapi." in html
    assert "<b>sekali</b>" not in html


def test_laporan_sistem_tanpa_lencana_guru_dan_blok_catatan():
    html = blok.blok_peta(_peta_sistem())
    assert "Ditinjau Guru" not in html and "Catatan dari Guru" not in html
    assert "ortu-peta-catatan-st" not in html
    assert "Guru" not in html


def test_laporan_sistem_tidak_pernah_memuat_teks_catatan_sistem():
    html = blok.blok_peta(_peta_sistem())
    assert CATATAN_SISTEM_UJI not in html


def test_laporan_sistem_tetap_menampilkan_skor_materi_dan_latihan():
    html = blok.blok_peta(_peta_sistem())
    assert "Peta Kemampuan lengkap" in html and "dari 100" in html and "Perlu penguatan" in html
    assert "Penguasaan per materi" in html and "Yang paling perlu dilatih dulu" in html
    assert "Ini gambaran kemampuan anak dari cek yang sudah dikerjakan." in html


def test_pesanan_lunas_tanpa_laporan_memakai_kalimat_sedang_disiapkan():
    html = halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True)
    assert "Pembayaran diterima. Laporan sedang disiapkan." in html
    assert "Guru" not in html and "48 jam" not in html


def test_tawaran_peta_menjanjikan_terbit_setelah_verifikasi_dengan_harga_pakai_konstanta():
    html = halaman._blok_pesanan(None, True)
    assert ("Laporan lengkap langsung terbit setelah pembayaran terverifikasi. "
            "Peta Kemampuan Rp49.000, dibayar sekali tanpa tagihan berulang.") in html
    assert "Guru" not in html and "48 jam" not in html


def test_janji_terbit_pesanan_tidak_menyebut_guru_atau_48_jam():
    html = halaman._blok_pesanan(pesanan_pages.STATUS_SUDAH_DIBAYAR, True, KEADAAN_TERLAMBAT)
    assert "Guru" not in html and "48 jam" not in html


def test_semua_status_pesanan_di_halaman_orang_tua_bebas_kata_guru_dan_48_jam():
    for status in pesanan_pages.COPY_STATUS:
        html = halaman._blok_pesanan(status, True)
        assert "Guru" not in html and "48 jam" not in html, status


def test_halaman_lunas_tanpa_laporan_bagian_pesanan_bebas_guru():
    bagian = _bagian(_halaman_dengan(peta=None), "ortu-pesanan")
    assert "Laporan sedang disiapkan" in bagian
    assert "Guru" not in bagian and "48 jam" not in bagian


def test_halaman_lunas_tanpa_kartu_kosong_laporan_dari_guru():
    halaman_html = _halaman_dengan(peta=None)
    assert "Laporan dari Guru" not in halaman_html and "Belum ada laporan dari Guru." not in halaman_html


def test_halaman_belum_bayar_tetap_menampilkan_kartu_kosong_laporan_guru_lama():
    halaman_html = _halaman_dengan(peta=None, status=pesanan_pages.STATUS_BELUM_BAYAR)
    assert "Belum ada laporan dari Guru." in halaman_html


def test_halaman_laporan_sistem_bagian_peta_dan_pesanan_bebas_guru():
    halaman_html = _halaman_dengan(peta=_peta_sistem(), purna=None)
    for id_bagian in ("ortu-peta", "ortu-pesanan"):
        bagian = _bagian(halaman_html, id_bagian)
        assert bagian, id_bagian
        assert "Guru" not in bagian and "48 jam" not in bagian, id_bagian
    assert "Laporan Peta Kemampuan sudah tersedia di halaman ini." in _bagian(halaman_html, "ortu-pesanan")
    assert CATATAN_SISTEM_UJI not in halaman_html

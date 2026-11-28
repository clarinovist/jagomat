"""Halaman 2 laporan Peta versi 3 (F6): cara mengerjakan, saran di rumah, rekomendasi, catatan kaki, dan penutup.

Semua angka berasal dari isi versi 3 (`menit_total`, `rata_detik_soal` atau `rata_detik`, `jumlah_cepat`, `dilewati`,
`soal`). Rata-rata dipakai dari `rata_detik_soal`; bila None, jatuh ke `rata_detik`. Kartu tanpa data tidak dibuat.
Tidak ada aspek berpikir, jenis kesalahan, atau pola salah di sini: datanya belum ada di snapshot.
"""
from __future__ import annotations

import design_tokens as T
import peta_laporan_snapshot as snap
import peta_v3_grafik as grafik
from peta_laporan_ortu_v2 import TEKS_REKOMENDASI
from peta_saran_rumah import pilih_saran
from peta_v3_html import e, kartu, tanggal

COPY_CARA = "Cara mengerjakan"
COPY_UBIN_MENIT = "%d menit"
COPY_UBIN_MENIT_KET = "Total waktu untuk %d soal"
COPY_UBIN_RATA = "%d detik"
COPY_UBIN_RATA_KET = "Rata-rata per soal"
COPY_UBIN_CEPAT = "%d soal"
COPY_UBIN_CEPAT_KET = "Dijawab di bawah %d detik dan salah"
COPY_UBIN_LEWAT = "%d soal"
COPY_UBIN_LEWAT_KET = "Dilewati."
COPY_UBIN_LEWAT_NOL = "Dilewati. Anak mencoba semua soal."
COPY_TERLAMA = "Soal nomor %d butuh waktu paling lama, %d detik."
COPY_RUMAH = "Yang bisa dilakukan di rumah"
COPY_REKOM = "Rekomendasi pendampingan"
COPY_CATATAN = ("Laporan otomatis dari %d soal cek kemampuan, %s. Hasil ini membaca pola dari soal yang dikerjakan, "
                "bukan ujian menyeluruh atau tes psikologi.")
COPY_PENUTUP = "Setiap jawaban salah adalah petunjuk, bukan nilai akhir. Anak bisa"
COPY_PENUTUP_SOROT = "jago karena tahu caranya"


def _rata_detik(isi: dict):
    """Rata-rata per soal: `rata_detik_soal` bila ada, selain itu `rata_detik` (None bila keduanya tak ada)."""
    if isi["rata_detik_soal"] is not None:
        return isi["rata_detik_soal"]
    return isi["rata_detik"]


def _ubin(isi: dict) -> list:
    """Pasangan (angka, keterangan) untuk kartu cara mengerjakan; kartu tanpa data tidak dibuat."""
    ubin = []
    if isi["menit_total"] is not None:
        ubin.append((COPY_UBIN_MENIT % isi["menit_total"], COPY_UBIN_MENIT_KET % isi["jumlah_soal"]))
    rata = _rata_detik(isi)
    if rata is not None:
        ubin.append((COPY_UBIN_RATA % rata, COPY_UBIN_RATA_KET))
    ubin.append((COPY_UBIN_CEPAT % isi["jumlah_cepat"], COPY_UBIN_CEPAT_KET % snap.AMBANG_CEPAT_DETIK))
    keterangan_lewat = COPY_UBIN_LEWAT_NOL if isi["dilewati"] == 0 else COPY_UBIN_LEWAT_KET
    ubin.append((COPY_UBIN_LEWAT % isi["dilewati"], keterangan_lewat))
    return ubin


def _html_ubin(ubin: list) -> str:
    butir = "".join(f"<li><b>{e(angka)}</b><span>{e(keterangan)}</span></li>" for angka, keterangan in ubin)
    return f'<ul class="ortu-peta-v3-ubin-st">{butir}</ul>'


def _sorot_terlama(isi: dict) -> str:
    terlama = grafik.soal_terlama(isi["soal"])
    if terlama is None:
        return ""
    return f'<p class="ortu-peta-v3-sorot-st">{e(COPY_TERLAMA % (terlama["nomor"], terlama["detik"]))}</p>'


def bagian_cara(isi: dict) -> str:
    """Cara mengerjakan: kartu angka, grafik waktu per nomor (SVG + teks sr-only), dan soal paling lama."""
    isi_kartu = _html_ubin(_ubin(isi)) + grafik.grafik_waktu(isi["soal"], _rata_detik(isi)) + _sorot_terlama(isi)
    return kartu("ortu-peta-v3-h-cara", COPY_CARA, isi_kartu)


def bagian_rumah(isi: dict) -> str:
    """Saran di rumah dari templat tetap (`peta_saran_rumah`); kosong bila tak ada saran yang cocok."""
    saran = pilih_saran(isi["perlu_dilatih"], isi["dilewati"])
    if not saran:
        return ""
    butir = "".join(f"<li>{e(teks)}</li>" for teks in saran)
    return kartu("ortu-peta-v3-h-rumah", COPY_RUMAH, f'<ul class="ortu-peta-v3-saran-st">{butir}</ul>')


def bagian_rekomendasi(kategori: str) -> str:
    """Satu kalimat tetap per kategori skor (tanpa tautan pilihan kelas; keputusan Pemilik menunggu)."""
    kalimat = TEKS_REKOMENDASI.get(kategori)
    if kalimat is None:
        return ""
    return kartu("ortu-peta-v3-h-rekom", COPY_REKOM, f'<p>{e(kalimat)}</p>', "ortu-peta-v3-rekom-kartu-st")


def catatan_kaki(isi: dict) -> str:
    """Keterangan asal laporan: jumlah soal, tanggal cek, dan batas pembacaan (bukan tes psikologi)."""
    teks = COPY_CATATAN % (isi["jumlah_soal"], tanggal(isi["tanggal_cek"]))
    return f'<p class="ortu-peta-v3-catatan-st">{e(teks)}</p>'


def penutup() -> str:
    """Kutipan penutup dengan kalimat merek; tanpa gambar kedua agar halaman tetap memegang satu maskot."""
    return ('<section class="ortu-peta-v3-penutup-st" aria-label="Pesan penutup"><blockquote>'
            f'<p>{e(COPY_PENUTUP)} <span>{e(COPY_PENUTUP_SOROT)}</span>.</p>'
            f'<footer>Tim {e(T.NAMA_PRODUK)}</footer></blockquote></section>')

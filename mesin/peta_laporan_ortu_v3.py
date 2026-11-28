"""Blok "Peta Kemampuan" versi 3 untuk halaman orang tua (F6): renderer MURNI, tanpa DB, tanpa token, tanpa jam.

Dipanggil `peta_laporan_ortu_pages.blok_peta` untuk `peta["isi"]["versi"] == 3`. Susunan mengikuti mockup "Laporan Peta
Kemampuan v2": halaman 1 (kepala, hero, skor, peta pulau, detail, temuan, urutan, perilaku belajar) lalu halaman 2
(cara mengerjakan, saran di rumah, rekomendasi, catatan kaki, penutup). Bagian yang datanya belum ada (aspek berpikir,
jenis kesalahan, pola salah) TIDAK dibuat. Tanpa nama anak, kontak, kunci, malrule, teks soal, atau peringkat.
"""
from __future__ import annotations

import peta_laporan_ortu_pages as v1
import peta_v3_aturan as aturan
import peta_v3_halaman1 as halaman1
import peta_v3_halaman2 as halaman2
import peta_v3_materi as materi
import peta_v3_perilaku as perilaku
from peta_browser import SKRIP_CETAK

KELAS_KARTU = "ortu-kartu-st ortu-peta-st ortu-peta-v3-st"


def _halaman_1(isi: dict, daftar: list) -> str:
    return (
        halaman1.kepala(isi)
        + f'<div class="ortu-peta-v3-atas-st">{halaman1.hero(isi, daftar)}{halaman1.kartu_skor(isi, daftar)}</div>'
        + materi.bagian_peta(daftar, isi["kelas"])
        + '<div class="ortu-peta-v3-bawah-st">' + materi.bagian_detail(daftar)
        + '<div class="ortu-peta-v3-kolom-st">' + materi.bagian_temuan(daftar) + materi.bagian_urutan(daftar)
        + "</div></div>"
        + perilaku.bagian_perilaku(isi, daftar)
    )


def _halaman_2(peta: dict, oleh_sistem: bool) -> str:
    isi = peta["isi"]
    kolom_kanan = (halaman2.bagian_rekomendasi(isi["kategori"]) + v1._catatan_bila_guru(peta, oleh_sistem)
                   + halaman2.catatan_kaki(isi))
    return ('<div class="ortu-peta-v3-halaman2-st">' + halaman2.bagian_cara(isi)
            + '<div class="ortu-peta-v3-dua-st">' + halaman2.bagian_rumah(isi)
            + '<div class="ortu-peta-v3-kolom-st">' + kolom_kanan + "</div></div>"
            + halaman2.penutup() + "</div>")


def blok_peta_v3(peta: dict) -> str:
    """HTML blok Peta Kemampuan versi 3; `oleh_sistem` (False bila absen) menyembunyikan catatan Guru."""
    isi = peta["isi"]
    oleh_sistem = bool(peta.get("oleh_sistem", False))
    daftar = aturan.daftar_materi_berstatus(isi["per_materi"])
    return (f'<section class="{KELAS_KARTU}" id="{v1.ID_BLOK}">'
            f'<div class="ortu-peta-v3-isi-st">{_halaman_1(isi, daftar)}{_halaman_2(peta, oleh_sistem)}</div>'
            f'<script>{SKRIP_CETAK}</script></section>')

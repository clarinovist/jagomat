"""Registri sakelar fitur untuk halaman admin: label, dampak, akibat mati, kelompok, dan pembaca env lama.

Murni data dan fungsi kecil. Env hanya dipakai sebagai nilai awal (seed) saat admin pertama kali mengubah
sakelar; env yang tidak sah dibaca sebagai mati (fail-closed) dan tidak merambat ke halaman admin.
Teks ditulis untuk Pemilik (bukan developer): tanpa istilah teknis, tanpa tanda kutip/ampersand pada `dampak`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

import choice_pages
import akses_harian
import contest_gate
import daftar_anak_gate
import feature_switch
import funnel_flag
import guru_daftar_gate
import paket_belajar_gate
import pesanan_transfer_gerbang
import story_frames

KELOMPOK_PENJUALAN = "penjualan"
KELOMPOK_BELAJAR = "belajar"
KELOMPOK = (KELOMPOK_PENJUALAN, KELOMPOK_BELAJAR)


@dataclass(frozen=True)
class InfoSakelar:
    """Teks tampilan satu sakelar, kelompok di halaman, dan cara membaca nilai env lamanya.

    `akibat_mati` = kalimat akibat yang dibacakan pada konfirmasi sebelum fitur yang sedang aktif dimatikan."""

    label: str
    dampak: str
    akibat_mati: str
    kelompok: str
    dari_env: Callable[[], bool]


_INFO = {
    "FUNNEL_AKTIF": InfoSakelar(
        label="Cek Kemampuan dan Paket Coba",
        dampak="Saat aktif, guru bisa memakai Cek Kemampuan dan Paket Coba. "
               "Saat mati, halamannya tampil belum dibuka.",
        akibat_mati="Halaman Cek Kemampuan dan Paket Coba tampil 'belum dibuka' untuk semua pengunjung.",
        kelompok=KELOMPOK_PENJUALAN,
        dari_env=funnel_flag.dari_env),
    "PESANAN_TRANSFER_AKTIF": InfoSakelar(
        label="Pembayaran transfer rekening",
        dampak="Saat aktif, guru melihat pilihan bayar lewat transfer rekening. "
               "Syaratnya: Cek Kemampuan sudah dibuka dan rekening tujuan sudah diisi.",
        akibat_mati="Guru tidak lagi melihat pilihan bayar lewat transfer rekening.",
        kelompok=KELOMPOK_PENJUALAN,
        dari_env=pesanan_transfer_gerbang.dari_env),
    "OSN_CETAK_RINGKAS": InfoSakelar(
        label="Cetak pilihan ganda ringkas",
        dampak="Memakai tata letak cetak pilihan ganda yang lebih ringkas pada lembar latihan.",
        akibat_mati="Lembar latihan pilihan ganda kembali memakai tata letak cetak yang lama.",
        kelompok=KELOMPOK_BELAJAR,
        dari_env=choice_pages.dari_env),
    "OSN_BANK_KALIMAT": InfoSakelar(
        label="Bank kalimat soal",
        dampak="Memakai bank kalimat soal terkurasi untuk soal yang baru dibuat.",
        akibat_mati="Soal yang dibuat sesudah ini tidak lagi memakai bank kalimat terkurasi. "
                    "Soal yang sudah ada tidak berubah.",
        kelompok=KELOMPOK_BELAJAR,
        dari_env=story_frames.dari_env),
    "OSN_LOMBA": InfoSakelar(
        label="Latihan Lomba (Grand Final)",
        dampak="Membuka latihan lomba bertimer untuk murid beserta riwayatnya untuk guru. "
               "Saat mati, halaman lomba tidak bisa dibuka sama sekali.",
        akibat_mati="Murid dan guru tidak bisa membuka halaman Latihan Lomba; halamannya tampil seperti tidak ada.",
        kelompok=KELOMPOK_BELAJAR,
        dari_env=contest_gate.dari_env),
    "DAFTAR_AKUN_ANAK": InfoSakelar(
        label="Pendaftaran akun anak",
        dampak="Saat aktif dan lembaga antrean sudah diatur di server, pendaftaran publik membuat akun anak "
               "yang dipegang koordinator lembaga, bukan akun guru untuk orang tua. "
               "Saat aktif tetapi lembaga antrean belum siap, pendaftaran ditolak dengan pesan belum dibuka. "
               "Saat mati, pendaftaran membuat akun guru seperti biasa.",
        akibat_mati="Pendaftar baru kembali membuat akun guru untuk orang tua. Akun anak yang sudah dibuat tetap bisa masuk.",
        kelompok=KELOMPOK_PENJUALAN,
        dari_env=daftar_anak_gate.dari_env),
    "LATIHAN_HARIAN": InfoSakelar(
        label="Latihan Harian",
        dampak="Saat aktif, murid bisa berlatih soal harian per tingkat: satu sesi gratis per hari, tanpa batas "
               "untuk pelanggan dan murid les. Saat mati, fitur ini tidak tampil dan halamannya tampil seperti tidak ada.",
        akibat_mati="Murid dan orang tua tidak bisa membuka Latihan Harian; halamannya tampil seperti tidak ada.",
        kelompok=KELOMPOK_BELAJAR,
        dari_env=akses_harian.dari_env),
    "PAKET_BELAJAR": InfoSakelar(
        label="Paket Belajar 1 Bulan",
        dampak="Saat aktif, orang tua bisa memilih paket belajar Private atau Mini Class, membayar lewat transfer "
               "rekening, dan admin menyetujui bukti bayarnya. Saat mati, halaman paket tampil seperti tidak ada "
               "dan Latihan Harian tidak berubah.",
        akibat_mati="Orang tua tidak bisa memilih atau membayar paket belajar baru; halamannya tampil seperti tidak ada. "
                    "Paket yang sudah disetujui tetap tercatat.",
        kelompok=KELOMPOK_PENJUALAN,
        dari_env=paket_belajar_gate.dari_env),
    "DAFTAR_GURU": InfoSakelar(
        label="Pendaftaran guru mandiri",
        dampak="Saat aktif, guru bisa membuat akun sendiri lewat tautan daftar guru, tanpa menunggu admin. "
               "Akun baru tidak otomatis masuk lembaga; admin memasukkannya lewat Tambah guru di halaman lembaga. "
               "Saat mati, tautan daftar guru tampil belum dibuka dan tidak ada akun yang dibuat.",
        akibat_mati="Tautan daftar guru tampil belum dibuka; guru baru hanya bisa dibuat oleh admin. "
                    "Akun guru yang sudah dibuat tetap bisa masuk.",
        kelompok=KELOMPOK_PENJUALAN,
        dari_env=guru_daftar_gate.dari_env),
}

if tuple(_INFO) != feature_switch.NAMA_SAKELAR:
    raise RuntimeError("Registri sakelar harus memuat tepat nama dan urutan NAMA_SAKELAR.")


def info(nama: str) -> InfoSakelar:
    """Info satu sakelar; nama di luar daftar = KeyError (kesalahan programmer)."""
    return _INFO[nama]


def nama_kelompok(kelompok: str) -> tuple:
    """Nama sakelar dalam satu kelompok, urutan registri."""
    return tuple(nama for nama, data in _INFO.items() if data.kelompok == kelompok)


def _baca_env(nama: str) -> bool:
    try:
        return bool(_INFO[nama].dari_env())
    except ValueError:
        return False


def seed_env() -> Dict[str, bool]:
    """Nilai awal semua sakelar dari env lama untuk feature_switch.daftar/ubah."""
    return {nama: _baca_env(nama) for nama in feature_switch.NAMA_SAKELAR}

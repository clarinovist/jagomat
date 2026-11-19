"""Registri empat sakelar fitur untuk halaman admin: label, dampak, dan pembaca env lama.

Murni data dan fungsi kecil. Env hanya dipakai sebagai nilai awal (seed) saat admin pertama kali mengubah
sakelar; env yang tidak sah dibaca sebagai mati (fail-closed) dan tidak merambat ke halaman admin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

import choice_pages
import feature_switch
import funnel_flag
import pesanan_transfer_gerbang
import story_frames


@dataclass(frozen=True)
class InfoSakelar:
    """Teks tampilan satu sakelar dan cara membaca nilai env lamanya."""

    label: str
    dampak: str
    dari_env: Callable[[], bool]


_INFO = {
    "FUNNEL_AKTIF": InfoSakelar(
        "Cek Kemampuan dan Paket Coba",
        "Membuka jalur Cek Kemampuan dan Paket Coba bagi guru; saat mati halamannya tampil belum dibuka.",
        funnel_flag.dari_env),
    "PESANAN_TRANSFER_AKTIF": InfoSakelar(
        "Pembayaran transfer rekening",
        "Menampilkan jalur bayar lewat transfer rekening bagi guru; gerbang tetap menunggu funnel, "
        "runtime produksi, dan rekening terisi.",
        pesanan_transfer_gerbang.dari_env),
    "OSN_CETAK_RINGKAS": InfoSakelar(
        "Cetak pilihan ganda ringkas",
        "Memakai tata letak cetak pilihan ganda yang lebih ringkas pada lembar latihan.",
        choice_pages.dari_env),
    "OSN_BANK_KALIMAT": InfoSakelar(
        "Bank kalimat soal",
        "Memakai bank kalimat soal terkurasi untuk snapshot soal yang baru dibuat.",
        story_frames.dari_env),
}

if tuple(_INFO) != feature_switch.NAMA_SAKELAR:
    raise RuntimeError("Registri sakelar harus memuat tepat nama dan urutan NAMA_SAKELAR.")


def info(nama: str) -> InfoSakelar:
    """Info satu sakelar; nama di luar daftar = KeyError (kesalahan programmer)."""
    return _INFO[nama]


def _baca_env(nama: str) -> bool:
    try:
        return bool(_INFO[nama].dari_env())
    except ValueError:
        return False


def seed_env() -> Dict[str, bool]:
    """Nilai awal keempat sakelar dari env lama untuk feature_switch.daftar/ubah."""
    return {nama: _baca_env(nama) for nama in feature_switch.NAMA_SAKELAR}

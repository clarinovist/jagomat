"""Sakelar penulis soal Bilangan Dasar: pembaca mengenal semua jenis, writer bertahap.

Inventaris pembaca (`Topik.komposisi`, REGISTRI, label, kartu) selalu memuat
semua jenis supaya sesi/bank yang sudah ada tetap terbaca. Jenis baru hanya
boleh DIBUAT bila `OSN_DASAR_LENGKAP=1`; bawaan 0 mempertahankan perilaku
produksi (10 soal `tambah_dasar`). Recovery `39fcfa7` belum mengenal jenis baru,
jadi aktivasi menunggu ulasan guru, pasangan recovery baru, dan izin rilis.
"""
from __future__ import annotations

import os

NAMA_SAKELAR = "OSN_DASAR_LENGKAP"
LEVEL_DASAR = ("P1", "P2")
JUMLAH_SOAL_LEMBAR = 10
TEMPLATE_AWAL = "tambah_dasar"
# Jenis yang hanya dibuat saat sakelar hidup.
TEMPLATE_BARU = frozenset({
    "kurang_dasar", "bilangan_hilang", "nilai_tempat", "bandingkan_bilangan",
})
PESAN_BELUM_DIBUKA = "Materi ini belum dibuka."

KETERANGAN_MATI = {
    "P1": "Hasil penjumlahan sampai 10",
    "P2": "Hasil penjumlahan 11–20, termasuk melewati 10",
}
KETERANGAN_HIDUP = {
    "P1": "Campuran penjumlahan, pengurangan, bilangan yang hilang sampai 10, nilai tempat, dan membandingkan",
    "P2": "Campuran penjumlahan, pengurangan, bilangan yang hilang sampai 20, nilai tempat, dan membandingkan sampai 100",
}


def dasar_lengkap_aktif() -> bool:
    """Hanya "0" atau "1"; nilai lain ditolak keras agar salah ketik terlihat."""
    nilai = os.environ.get(NAMA_SAKELAR, "0").strip()
    if nilai not in ("0", "1"):
        raise ValueError(f"{NAMA_SAKELAR} hanya menerima 0 atau 1")
    return nilai == "1"


def pilih_komposisi_writer():
    """Override writer saat registrasi: mati -> hanya tambah_dasar; hidup -> None."""
    if dasar_lengkap_aktif():
        return None
    return {level: (TEMPLATE_AWAL,) * JUMLAH_SOAL_LEMBAR for level in LEVEL_DASAR}


def keterangan_level():
    """Teks pilihan UI mengikuti apa yang benar-benar dibuat writer."""
    return dict(KETERANGAN_HIDUP if dasar_lengkap_aktif() else KETERANGAN_MATI)


def template_dibuka(template_id: str) -> bool:
    """Palang pembuat per template; pembaca histori tidak memakainya."""
    return template_id not in TEMPLATE_BARU or dasar_lengkap_aktif()


def pastikan_template_dibuka(template_ids) -> None:
    """Tolak pembuatan soal dari jenis baru saat sakelar mati."""
    if not all(template_dibuka(t) for t in template_ids):
        raise ValueError(PESAN_BELUM_DIBUKA)

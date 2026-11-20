"""Sakelar Bilangan Sekolah: pembaca mengenal topik, pembuat dan penawaran dikunci.

Inventaris pembaca (`topics.PAKET`, REGISTRI, label, kartu, inventaris visual)
selalu memuat topik `bilangan-sekolah` supaya sesi/bank yang kelak ada tetap
terbaca. Topik hanya boleh DIBUAT dan DITAWARKAN bila `OSN_BILANGAN_SEKOLAH=1`;
bawaan 0 menjaga perilaku aplikasi persis seperti sebelum topik ada. Sakelar
ini env-only (pola `OSN_DASAR_LENGKAP`), dibaca tiap panggilan, dan sengaja
tidak masuk `sakelar_registry.py`.

Ini hanya SAKELAR pembuatan. Larangan masuk Campuran, siklus terpandu,
Pendamping, dan sisi murid adalah palang terpisah (`Topik.hanya_manual`), yang
berlaku saat sakelar hidup maupun mati. Aktivasi menunggu ulasan batas rentang
oleh Guru, pin recovery yang mengenali ID baru, dan izin rilis.
"""
from __future__ import annotations

import os

NAMA_SAKELAR = "OSN_BILANGAN_SEKOLAH"
TOPIK_ID = "bilangan-sekolah"
# Jenis yang hanya boleh DIBUAT saat sakelar hidup (Tahap A + B: lima jenis).
TEMPLATE_BARU = frozenset({
    "nilai_tempat_besar", "urutkan_bilangan", "tambah_kurang_bersusun",
    "kali_bagi_sekolah", "kalimat_matematika",
})
PESAN_BELUM_DIBUKA = "Materi ini belum dibuka."


def bilangan_sekolah_aktif() -> bool:
    """Hanya "0" atau "1"; nilai lain ditolak keras agar salah ketik terlihat."""
    nilai = os.environ.get(NAMA_SAKELAR, "0").strip()
    if nilai not in ("0", "1"):
        raise ValueError(f"{NAMA_SAKELAR} hanya menerima 0 atau 1")
    return nilai == "1"


def topik_dibuka(topik_id: str) -> bool:
    """Palang penawaran topik; topik lain tidak terpengaruh sakelar ini."""
    return topik_id != TOPIK_ID or bilangan_sekolah_aktif()


def template_dibuka(template_id: str) -> bool:
    """Palang pembuat per template; pembaca histori tidak memakainya."""
    return template_id not in TEMPLATE_BARU or bilangan_sekolah_aktif()


def pastikan_template_dibuka(template_ids) -> None:
    """Tolak pembuatan soal dari jenis baru saat sakelar mati."""
    if not all(template_dibuka(t) for t in template_ids):
        raise ValueError(PESAN_BELUM_DIBUKA)

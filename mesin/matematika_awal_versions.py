"""Sakelar Matematika Awal: pembaca mengenal topik, pembuat dan penawaran dikunci.

Inventaris pembaca (`topics.PAKET`, REGISTRI, label, kartu, inventaris visual)
selalu memuat topik `matematika-awal` supaya sesi/bank yang kelak ada tetap
terbaca. Topik hanya boleh DIBUAT dan DITAWARKAN bila `OSN_MATEMATIKA_AWAL=1`.

BAWAAN 1 (keputusan pemilik 21 Nov 2026), BEDA dari `school_numbers_versions`
yang bawaan 0: topik menyala sendiri kecuali dimatikan dengan "0". Nilai selain
"0"/"1" ditolak keras agar salah ketik terlihat. Sakelar ini env-only (pola
`OSN_DASAR_LENGKAP`), dibaca tiap panggilan, dan sengaja tidak masuk
`sakelar_registry.py`.

Ini hanya SAKELAR pembuatan. Larangan masuk Campuran, siklus terpandu,
Pendamping, dan sisi murid adalah palang terpisah (`Topik.hanya_manual`), yang
berlaku saat sakelar hidup maupun mati. Karena topik memuat level P3 sampai P6,
gerbang `OSN_MATERI_DASAR` (`question_context.topik_dasar`) tidak lagi menutupnya.
Sebelum deploy: ulasan Mutia atas rentang dan malrule, pin recovery yang
mengenali ID baru, dan izin rilis.

Tiap jenis baru WAJIB masuk `TEMPLATE_BARU`; `test_matematika_awal_sakelar`
mengunci himpunan ini sama persis dengan `Topik.templates`. Sengaja daftar
eksplisit (bukan dibaca dari topik) supaya modul ini tidak mengimpor topik.
"""
from __future__ import annotations

import os

NAMA_SAKELAR = "OSN_MATEMATIKA_AWAL"
TOPIK_ID = "matematika-awal"
BAWAAN = "1"
TEMPLATE_BARU = frozenset({
    "kenali_bentuk",
    "ukur_satuan_tak_baku",
    "baca_diagram_gambar",
    "pola_posisi",
    "pecahan_setengah",
    "waktu_berat_awal",
    "turus_gambar_awal",
    "ukur_konversi_awal",
    "bandingkan_ciri_bangun",
    "peluang_dasar",
    "bilang_benda_awal",
    "tambah_kurang_20",
    "tambah_kurang_100",
    "unsur_bangun_datar",
    "pecahan_senilai_desimal",
    "luas_petak_volume_kubus",
    "ciri_komposisi_bangun",
    "keliling_gabungan",
    "pecahan_bilangan_asli_desimal",
    "pecahan_campur_awal",
    "kenali_bangun_awal",
    "baca_jam_awal",
    "ukur_sudut_awal",
    "tampak_kubus_awal",
    "piktogram_lima_awal",
})
PESAN_BELUM_DIBUKA = "Materi ini belum dibuka."


def matematika_awal_aktif() -> bool:
    """Hanya "0" atau "1" (bawaan "1"); nilai lain ditolak keras."""
    nilai = os.environ.get(NAMA_SAKELAR, BAWAAN).strip()
    if nilai not in ("0", "1"):
        raise ValueError(f"{NAMA_SAKELAR} hanya menerima 0 atau 1")
    return nilai == "1"


def topik_dibuka(topik_id: str) -> bool:
    """Palang penawaran topik; topik lain tidak terpengaruh sakelar ini."""
    return topik_id != TOPIK_ID or matematika_awal_aktif()


def template_dibuka(template_id: str) -> bool:
    """Palang pembuat per template; pembaca histori tidak memakainya."""
    return template_id not in TEMPLATE_BARU or matematika_awal_aktif()


def pastikan_template_dibuka(template_ids) -> None:
    """Tolak pembuatan soal dari jenis baru saat sakelar mati."""
    if not all(template_dibuka(t) for t in template_ids):
        raise ValueError(PESAN_BELUM_DIBUKA)

"""Baseline perilaku SEBELUM topik matematika-awal ada (HEAD 63f8756, 21 Nov 2026).

Nilai beku di bawah direkam dari pohon yang belum diubah, lewat jalur kode yang
sama dengan `baseline_bilangan_sekolah.ukur` (komposisi Campuran, daftar
Latihan manual, pemilih siklus, katalog Pendamping, katalog target mastery),
dengan OSN_BILANGAN_SEKOLAH=0, dalam DUA keadaan OSN_MATERI_DASAR (0 dan 1;
produksi boleh menyalakan yang kedua, jadi itu kasus yang lebih kuat).

Bawaan sakelar matematika-awal adalah 1, jadi identitas "perilaku lama" hanya
diuji dengan OSN_MATEMATIKA_AWAL=0 yang DIPASANG tes. Pembaca (registri, daftar
topik, daftar konteks) tetap mengenal topik dan jenisnya saat sakelar mati; yang
dibekukan di sini adalah isi lama, dan isi baru hanya boleh BERTAMBAH.

Kalau salah satu nilai berubah saat sakelar mati, perilaku aplikasi berubah: cari
penyebabnya, jangan perbarui angkanya.
"""
from __future__ import annotations

from baseline_bilangan_sekolah import sidik, sidik_terukur  # noqa: F401  (dipakai tes)

TOPIK = "matematika-awal"
TEMPLATE_AWAL = ("kenali_bentuk",)

# kunci -> sidik per keadaan OSN_MATERI_DASAR ("0" / "1").
SIDIK_BASELINE = {
    "0": {
        "campuran_komposisi": "c23df069c56127270ca6",
        "campuran_writer": "c23df069c56127270ca6",
        "campuran_templates": "af2e0863f001b153b99a",
        "daftar_topik_latihan": "32b5a5761cb26441d466",
        "katalog_penawaran": "af2e0863f001b153b99a",
        "katalog_target": "ff0d46793b3634a8a29e",
        "lintas_topik": "daa3ca1701bcbeb6abdc",
        "lintas_topik_40": "f1837d6c7e62c8384cfd",
        "override_html": "5b232cdfe19b16616717",
        "pemilih_pemetaan_html": "96c934284b47c4d5c3c0",
    },
    "1": {
        "campuran_komposisi": "c23df069c56127270ca6",
        "campuran_writer": "c23df069c56127270ca6",
        "campuran_templates": "af2e0863f001b153b99a",
        "daftar_topik_latihan": "f0fc71b8c0d0d3413387",
        "katalog_penawaran": "f43554db45fa42d36df2",
        "katalog_target": "ff0d46793b3634a8a29e",
        "lintas_topik": "daa3ca1701bcbeb6abdc",
        "lintas_topik_40": "f1837d6c7e62c8384cfd",
        "override_html": "5b232cdfe19b16616717",
        "pemilih_pemetaan_html": "96c934284b47c4d5c3c0",
    },
}
# Daftar Latihan manual sebelum topik ada, OSN_BILANGAN_SEKOLAH=0, OSN_MATERI_DASAR=1.
DAFTAR_LATIHAN_BASELINE = {
    "0": [
        "aritmatika-lanjut", "aritmetika-dasar", "berhitung-sekolah", "campuran",
        "geometri-datar", "geometri-ruang", "kombinatorik", "logika", "pengukuran",
        "pola-bilangan", "statistika", "teori-bilangan",
    ],
    "1": [
        "aritmatika-lanjut", "aritmetika-dasar", "berhitung-sekolah", "bilangan-dasar",
        "campuran", "geometri-datar", "geometri-ruang", "kombinatorik", "logika",
        "pengukuran", "pola-bilangan", "statistika", "teori-bilangan",
    ],
}
# Pembaca: isi lama (sudah memuat bilangan-sekolah, yang pembacanya sakelar-bebas).
SIDIK_REGISTRI_LAMA = "055ff09e07fcb7ce3b36"
JUMLAH_REGISTRI_LAMA = 111
TOPIK_LAMA = [
    "aritmatika-lanjut", "aritmetika-dasar", "berhitung-sekolah", "bilangan-dasar",
    "bilangan-sekolah", "campuran", "geometri-datar", "geometri-ruang", "kombinatorik",
    "logika", "pengukuran", "pola-bilangan", "statistika", "teori-bilangan",
]
SIDIK_KONTEKS_LAMA = "513eb3718ebe796dbf18"


def konteks_lama() -> list:
    """Daftar konteks sekarang tanpa topik baru, urut tetap (untuk disidik)."""
    import question_context
    import topics
    baru = set(topics.ambil(TOPIK).templates)
    return sorted((k.template_id, k.profil_parameter)
                  for k in question_context.daftar_konteks() if k.template_id not in baru)

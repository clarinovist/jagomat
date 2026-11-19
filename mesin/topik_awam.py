"""Nama topik untuk pembaca awam (anak dan orang tua).

Satu sumber label topik di layar anak (`cek_anak_komponen`) dan ringkasan hasil
orang tua (`cek_gratis_skor`). Nama resmi paket topik (`topics.ambil(...).nama`)
tetap dipakai pada lembar soal dan penilaian guru; modul ini hanya untuk
permukaan awam yang sudah memakai nama pendek sejak Keputusan 19.

Ringkasan lama menyimpan nama resmi ke kolom `cek_gratis.ringkasan`, sehingga
`dari_nama_lama()` memetakannya ke nama baru saat render. Nama yang tidak dikenal
dikembalikan apa adanya (data warisan tidak boleh membuat halaman 500).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

# Urutan mengikuti `cek_gratis_skor.semua_topik_cek()`; nilai adalah label awam.
NAMA_AWAM: Dict[str, str] = {
    "pola-bilangan": "Pola bilangan",
    "statistika": "Statistika",
    "geometri-datar": "Geometri datar",
    "bilangan-dasar": "Bilangan dasar",
    "berhitung-sekolah": "Berhitung",
    "pengukuran": "Pengukuran",
    "aritmetika-dasar": "Aritmetika dasar",
    "aritmatika-lanjut": "Aritmetika lanjut",
}


def nama(topik_id: str) -> str:
    """Label awam untuk topik cek; `KeyError` bila topik di luar daftar."""
    return NAMA_AWAM[topik_id]


@lru_cache(maxsize=1)
def _peta_nama_lama() -> Dict[str, str]:
    import topics

    peta = {}
    for topik_id, awam in NAMA_AWAM.items():
        try:
            peta[topics.ambil(topik_id).nama] = awam
        except KeyError:
            continue
    return peta


def dari_nama_lama(label: str) -> str:
    """Nama topik resmi (data tersimpan lama) menjadi label awam; lainnya utuh."""
    return _peta_nama_lama().get(label, label)

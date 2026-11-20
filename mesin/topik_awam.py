"""Nama topik untuk pembaca awam (anak dan orang tua).

Satu sumber label topik di layar anak (`cek_anak_komponen`) dan ringkasan hasil
orang tua (`cek_gratis_skor`). Nama resmi paket topik (`topics.ambil(...).nama`)
tetap dipakai pada lembar soal dan penilaian guru; modul ini hanya untuk
permukaan awam yang sudah memakai nama pendek sejak Keputusan 19.

Label yang tampil adalah label EFEKTIF: bawaan kode (`NAMA_AWAM`, dari
`kurikulum_katalog`) atau label yang diubah admin (`kurikulum_override`), dibaca
saat request (cache TTL pendek di store). DB override hilang atau rusak berarti
label bawaan. `NAMA_AWAM` sendiri tetap konstanta bawaan kode, tidak pernah berubah.

Ringkasan lama menyimpan nama resmi ke kolom `cek_gratis.ringkasan`, sehingga
`dari_nama_lama()` memetakannya ke label efektif saat render. Ringkasan yang sudah
menyimpan label awam (bawaan atau hasil ubah admin) ditampilkan apa adanya: hasil
cek yang sudah dinilai tidak berubah ketika label diubah. Nama yang tidak dikenal
dikembalikan apa adanya (data warisan tidak boleh membuat halaman 500).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

import kurikulum_katalog
import kurikulum_override

# Urutan dan label dari `kurikulum_katalog` (satu sumber peta kurikulum). Bawaan kode.
NAMA_AWAM: Dict[str, str] = kurikulum_katalog.label_awam()


def nama(topik_id: str) -> str:
    """Label awam EFEKTIF untuk topik cek; `KeyError` bila topik di luar daftar."""
    bawaan = NAMA_AWAM[topik_id]
    return kurikulum_override.label_efektif().get(topik_id, bawaan)


@lru_cache(maxsize=1)
def _peta_nama_resmi() -> Dict[str, str]:
    """nama resmi paket -> topik_id, tanpa nama yang sama persis dengan sebuah label bawaan.

    Nama yang sama dengan label bawaan (mis. "Statistika") tidak dipetakan: teks itu
    sudah sah sebagai label tersimpan dan harus tetap utuh. Tidak bergantung pada
    override, jadi aman di-cache.
    """
    import topics

    bawaan = set(kurikulum_katalog.label_awam().values())
    peta = {}
    for topik_id in NAMA_AWAM:
        try:
            resmi = topics.ambil(topik_id).nama
        except KeyError:
            continue
        if resmi not in bawaan:
            peta[resmi] = topik_id
    return peta


def bentrok_nama_resmi(label: str) -> bool:
    """True bila `label` sama persis dengan nama resmi yang dipetakan `dari_nama_lama` ke topik.

    Label seperti itu tidak boleh dipakai: teks tersimpannya akan dibaca sebagai nama lama
    dan berubah mengikuti label topik lain.
    """
    return label in _peta_nama_resmi()


def dari_nama_lama(label: str) -> str:
    """Nama topik resmi (data tersimpan lama) menjadi label awam efektif; lainnya utuh.

    Label awam yang sudah tersimpan (bawaan maupun hasil ubah admin) sengaja TIDAK dipetakan
    ulang: ringkasan yang sudah dinilai harus tetap sama walau label topiknya diubah kemudian.
    """
    topik_id = _peta_nama_resmi().get(label)
    return label if topik_id is None else nama(topik_id)

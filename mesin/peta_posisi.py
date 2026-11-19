"""Posisi anak di antara anak sekelas: persentil dan peringkat. Fungsi murni.

Aturan (Keputusan 19, PANDUAN-LAPORAN-PETA-KEMAMPUAN §4):

- Pembanding = skor anak kelas yang sama yang sudah ikut Cek Jagomat. Daftar itu
  SUDAH memuat skor anak yang sedang dilaporkan, jadi peringkat tidak pernah
  melebihi penyebut. Fungsi ini tidak bisa memeriksa hal tersebut; pemanggil yang
  menjaganya.
- Kurang dari `MINIMAL_PEMBANDING` pembanding: tidak ada posisi (None), laporan
  menampilkan "Peringkat muncul setelah cukup data".
- Persentil = (jumlah skor lebih rendah + setengah jumlah skor sama) / jumlah
  pembanding x 100, dibulatkan SETENGAH KE ATAS (bukan pembulatan bankir), memakai
  aritmetika bilangan bulat yang sama dengan `cek_gratis_skor.hitung_skor`.
- Peringkat = 1 + jumlah skor yang lebih tinggi; penyebutnya jumlah pembanding.
"""
from __future__ import annotations

from dataclasses import dataclass

from cek_gratis_skor import hitung_skor

MINIMAL_PEMBANDING = 30
SKOR_MIN = 0
SKOR_MAKS = 100


@dataclass(frozen=True)
class HasilPosisi:
    """Posisi satu skor di antara daftar pembanding."""

    persentil: int
    peringkat: int
    penyebut: int


def _skor_sah(nilai) -> bool:
    return type(nilai) is int and SKOR_MIN <= nilai <= SKOR_MAKS


def _periksa_masukan(skor, skor_pembanding, minimal) -> tuple:
    if not _skor_sah(skor):
        raise ValueError("skor harus bilangan bulat 0..100")
    if type(minimal) is not int or minimal < 1:
        raise ValueError("minimal harus bilangan bulat positif")
    try:
        daftar = tuple(skor_pembanding)
    except TypeError:
        raise ValueError("skor pembanding harus berupa daftar skor") from None
    if not all(_skor_sah(butir) for butir in daftar):
        raise ValueError("setiap skor pembanding harus bilangan bulat 0..100")
    return daftar


def hitung_posisi(skor: int, skor_pembanding, minimal: int = MINIMAL_PEMBANDING):
    """Persentil dan peringkat `skor`; None bila pembanding kurang dari `minimal`.

    ValueError bila `skor`, `minimal`, atau isi `skor_pembanding` tidak sah
    (bukan int 0..100; bool ditolak).
    """
    daftar = _periksa_masukan(skor, skor_pembanding, minimal)
    jumlah = len(daftar)
    if jumlah < minimal:
        return None
    lebih_rendah = sum(1 for butir in daftar if butir < skor)
    sama = sum(1 for butir in daftar if butir == skor)
    lebih_tinggi = jumlah - lebih_rendah - sama
    # (rendah + sama/2) / jumlah x 100 = hitung_skor(2*rendah + sama, 2*jumlah).
    persentil = hitung_skor(2 * lebih_rendah + sama, 2 * jumlah)
    return HasilPosisi(persentil=persentil, peringkat=1 + lebih_tinggi, penyebut=jumlah)

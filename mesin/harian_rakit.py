"""Rakit satu sesi Latihan Harian: 10 soal PG 4 opsi campuran bab satu tingkat (+ maks 2 ulangan tingkat bawah).

Murni dan deterministik dari `seed` sesi (disimpan di DB oleh pemanggil, dibangkitkan dari `secrets`): RNG
berbasis string, bukan `hash()`. Soal diambil bergiliran dari sumber (bab) yang diacak supaya tersebar, jenis
soal dipilih acak dari sumber itu, dan tiap soal dalam satu sesi punya tanda tangan berbeda. Hanya jenis soal yang
lolos audit PG (`harian_tingkat.sumber_layak`) yang dipakai. Tanpa DB.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import List, Set, Tuple

import harian_pg
import harian_tingkat as tingkat_mod

JUMLAH_SOAL = 10
MAKS_ULANGAN = 2
SEED_MIN, SEED_MAKS = 1, 2 ** 31 - 1
MAKS_COBA_PER_RUJUKAN = 200


class TingkatKosong(ValueError):
    """Tingkat ini tidak punya satu pun jenis soal layak (atau tak cukup soal berbeda)."""


@dataclass(frozen=True)
class SoalRakitan:
    nomor: int
    sumber: str
    ulangan: bool
    soal: harian_pg.SoalPg


def _satu_soal(sumber: tingkat_mod.Sumber, rng: random.Random, terpakai: Set[str]) -> harian_pg.SoalPg:
    rujukan = list(sumber.refs)
    rng.shuffle(rujukan)
    for topik, tid, level in rujukan:
        for _ in range(MAKS_COBA_PER_RUJUKAN):
            try:
                soal = harian_pg.buat_soal_pg(topik, tid, level, rng.randrange(SEED_MIN, SEED_MAKS + 1))
            except harian_pg.SoalTidakLayak:
                continue
            if soal.tanda_tangan not in terpakai:
                return soal
    raise TingkatKosong("sumber %s tidak menghasilkan soal baru" % sumber.label)


def _ambil(kumpulan: Tuple[tingkat_mod.Sumber, ...], banyak: int, ulangan: bool, rng: random.Random,
           terpakai: Set[str]) -> List[Tuple[str, bool, harian_pg.SoalPg]]:
    urut = list(kumpulan)
    rng.shuffle(urut)
    hasil = []
    for i in range(banyak):
        sumber = urut[i % len(urut)]
        soal = _satu_soal(sumber, rng, terpakai)
        terpakai.add(soal.tanda_tangan)
        hasil.append((sumber.label, ulangan, soal))
    return hasil


def rakit_sesi(kode: str, seed: int) -> Tuple[SoalRakitan, ...]:
    """`JUMLAH_SOAL` soal untuk tingkat `kode` dari `seed`; `KeyError` bila kode bukan tingkat sah."""
    if type(seed) is not int or not SEED_MIN <= seed <= SEED_MAKS:
        raise ValueError("seed sesi tidak sah")
    tingkat = tingkat_mod.ambil_tingkat(kode)
    utama = tingkat_mod.sumber_layak(kode)
    if not utama:
        raise TingkatKosong("tingkat %s belum punya soal layak" % kode)
    bawah = tingkat_mod.sumber_layak(tingkat.bawah) if tingkat.bawah else ()
    banyak_ulangan = MAKS_ULANGAN if bawah else 0
    rng = random.Random("harian-v1|%d|%s" % (seed, kode))
    terpakai: Set[str] = set()
    daftar = _ambil(utama, JUMLAH_SOAL - banyak_ulangan, False, rng, terpakai)
    daftar += _ambil(bawah, banyak_ulangan, True, rng, terpakai) if bawah else []
    rng.shuffle(daftar)
    return tuple(SoalRakitan(i, label, ulangan, soal) for i, (label, ulangan, soal) in enumerate(daftar, 1))

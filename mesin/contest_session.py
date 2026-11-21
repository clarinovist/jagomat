"""Perakit sesi Latihan Lomba: 10 soal (8 PG + 2 isian) dari kumpulan template.

Aturan rakitan: tiap topik 2-3 soal; dua isian dari topik berbeda; satu template paling
banyak sekali; paling banyak satu soal berbahasa Inggris; banyak soal tiap tingkat dalam batas
(mudah 2-4, sedang 2-5, sulit 2-4); urut kasar mudah ke sulit; posisi kunci A-D seimbang (dua per
huruf); tidak memakai ulang soal yang `tanda_tangan`-nya dilarang (soal dari beberapa sesi terakhir);
jenis soal dari dua sesi terakhir dihindari selama masih memungkinkan (rotasi).
Murni dan deterministik untuk `seed` yang sama; tidak menyentuh DB.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import AbstractSet, Dict, List, Optional, Sequence, Tuple

import contest_core as C

JUMLAH_SOAL = 10
JUMLAH_ISIAN = 2
JUMLAH_PG = JUMLAH_SOAL - JUMLAH_ISIAN
SOAL_PER_TOPIK_DASAR = 2          # tiap topik minimal dua; sisanya dibagi ke topik berbeda
MAKS_INGGRIS = 1
BATAS_PER_TINGKAT = {1: (2, 4), 2: (2, 5), 3: (2, 4)}   # (minimal, maksimal) soal per tingkat
RIWAYAT_SESI = 5                  # soal dari sesi sejauh ini yang tidak boleh diulang
ROTASI_SESI = 2                   # jenis soal (template) dari sesi sejauh ini dihindari selama bisa
MAKS_PERCOBAAN_RAKIT = 200
MAKS_PERCOBAAN_VARIAN = 30


class GagalMerakitSesi(RuntimeError):
    """Kumpulan template tidak cukup (atau varian habis) untuk merakit sesi yang sah."""


@dataclass(frozen=True)
class ButirSesi:
    nomor: int
    soal: C.SoalLomba
    pilihan: Tuple[str, ...]            # () untuk isian
    gambar_pilihan: Tuple[str, ...]     # () untuk isian; ("",)*4 bila pilihan teks
    posisi_kunci: int                   # 0-3 (A-D); -1 untuk isian


@dataclass(frozen=True)
class Sesi:
    seed: int
    butir: Tuple[ButirSesi, ...]


def _kelompokkan(pool: Sequence[C.Template]) -> Dict[Tuple[str, str], List[C.Template]]:
    kelompok: Dict[Tuple[str, str], List[C.Template]] = {}
    for template in sorted(pool, key=lambda t: t.id):
        kelompok.setdefault((template.topik, template.jenis), []).append(template)
    return kelompok


def _pilih_template(rng: random.Random,
                    kelompok: Dict[Tuple[str, str], List[C.Template]]) -> Optional[List[C.Template]]:
    jumlah = {topik: SOAL_PER_TOPIK_DASAR for topik in C.TOPIK}
    for topik in rng.sample(C.TOPIK, JUMLAH_SOAL - SOAL_PER_TOPIK_DASAR * len(C.TOPIK)):
        jumlah[topik] += 1
    bertopik_isian = [t for t in C.TOPIK if kelompok.get((t, C.JENIS_ISIAN))]
    if len(bertopik_isian) < JUMLAH_ISIAN:
        return None
    topik_isian = rng.sample(bertopik_isian, JUMLAH_ISIAN)
    terpilih: List[C.Template] = []
    for topik in C.TOPIK:
        isian = 1 if topik in topik_isian else 0
        calon_pg = kelompok.get((topik, C.JENIS_PG), [])
        if len(calon_pg) < jumlah[topik] - isian:
            return None
        terpilih += rng.sample(calon_pg, jumlah[topik] - isian)
        if isian:
            terpilih += rng.sample(kelompok[(topik, C.JENIS_ISIAN)], 1)
    keluarga = [template.keluarga or template.id for template in terpilih]
    return terpilih if len(set(keluarga)) == len(keluarga) else None


def _tingkat_seimbang(templates: Sequence[C.Template]) -> bool:
    tingkat = [t.tingkat for t in templates]
    return all(minimal <= tingkat.count(level) <= maksimal
               for level, (minimal, maksimal) in BATAS_PER_TINGKAT.items())


def _bangun_semua(rng: random.Random, templates: Sequence[C.Template],
                  terlarang: AbstractSet[str]) -> Optional[List[C.SoalLomba]]:
    hasil: List[C.SoalLomba] = []
    for template in templates:        # template berbeda semua, jadi tanda tangan antarsoal pasti berbeda
        for _ in range(MAKS_PERCOBAAN_VARIAN):
            soal = C.buat_soal(template, random.Random(rng.getrandbits(64)))
            if C.tanda_tangan(soal) in terlarang:
                continue
            hasil.append(soal)
            break
        else:
            return None
    return hasil


def _susun(seed: int, rng: random.Random, soal_semua: Sequence[C.SoalLomba]) -> Sesi:
    diacak = list(soal_semua)
    rng.shuffle(diacak)
    urut = sorted(diacak, key=lambda soal: soal.tingkat)    # stabil: seri tetap acak
    posisi = iter(C.posisi_seimbang(JUMLAH_PG, rng))
    butir = []
    for nomor, soal in enumerate(urut, start=1):
        if soal.jenis == C.JENIS_ISIAN:
            butir.append(ButirSesi(nomor, soal, (), (), -1))
            continue
        letak = next(posisi)
        pilihan = C.susun_pilihan(soal, letak, rng)
        butir.append(ButirSesi(nomor, soal, pilihan, C.gambar_pilihan(soal, pilihan), letak))
    return Sesi(seed=seed, butir=tuple(butir))


def _rakit(seed: int, pool: Sequence[C.Template], tanda_terlarang: AbstractSet[str]) -> Sesi:
    rng = random.Random(seed)
    kelompok = _kelompokkan(pool)
    for _ in range(MAKS_PERCOBAAN_RAKIT):
        templates = _pilih_template(rng, kelompok)
        if templates is None or not _tingkat_seimbang(templates):
            continue
        soal_semua = _bangun_semua(rng, templates, tanda_terlarang)
        if soal_semua is None or sum(1 for s in soal_semua if s.inggris) > MAKS_INGGRIS:
            continue
        return _susun(seed, rng, soal_semua)
    raise GagalMerakitSesi(
        f"tidak bisa merakit sesi dari {len(pool)} template setelah {MAKS_PERCOBAAN_RAKIT} percobaan")


def rakit_sesi(seed: int, pool: Sequence[C.Template], tanda_terlarang: AbstractSet[str],
               template_dihindari: AbstractSet[str] = frozenset()) -> Sesi:
    """Rakit satu sesi.

    `tanda_terlarang`: tanda tangan soal dari `RIWAYAT_SESI` sesi terakhir (wajib tidak dipakai ulang).
    `template_dihindari`: id template dari `ROTASI_SESI` sesi terakhir; dihindari agar jenis soal
    berganti-ganti, tetapi dilepas bila tanpa mereka sesi tidak bisa dirakit (tidak pernah gagal karenanya).
    """
    if template_dihindari:
        segar = [template for template in pool if template.id not in template_dihindari]
        try:
            return _rakit(seed, segar, tanda_terlarang)
        except GagalMerakitSesi:
            pass
    return _rakit(seed, pool, tanda_terlarang)

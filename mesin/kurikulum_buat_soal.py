"""Pembuat contoh soal untuk halaman admin "Buat soal" per bab Kurikulum Merdeka.

Murni dan deterministik dari `seed` (RNG berbasis string, bukan `hash()`), tanpa DB: soal TIDAK disimpan.
Soal dibagi bergiliran antar template bab di level kelasnya, tanpa tanda tangan kembar. Template yang
palang rilisnya tertutup dikeluarkan (generator `buat_soal` sendiri tidak memeriksa palang itu).
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, replace
from typing import Deque, Dict, Iterator, List, Optional, Tuple

import generator
import kurikulum_kelas as kk
import kurikulum_kelas_hitung as hitung
import topics
from templates import Soal

JUMLAH_PILIHAN = (5, 10, 20, 30)
JUMLAH_BAWAAN = 10
SEED_MIN, SEED_MAKS = 1, 2 ** 31
MAKS_UNDI_PER_SLOT = 200  # undian ulang untuk template tanpa enumerator sebelum dianggap habis


@dataclass(frozen=True)
class ItemSoal:
    nomor: int
    soal: Soal
    paket: topics.Topik
    nama_grup: str


@dataclass(frozen=True)
class HasilBuat:
    item: Tuple[ItemSoal, ...]
    jumlah_diminta: int
    template_tertutup: Tuple[str, ...]
    ada_pelatih: bool  # ada grup bab ini yang tersedia di level kelas (walau mungkin tertutup)

    @property
    def bisa_dibuat(self) -> bool:
        return bool(self.item)


def _nama_grup_per_template(bab: kk.Bab, kelas: int) -> Dict[hitung.RefTemplate, str]:
    peta: Dict[hitung.RefTemplate, str] = {}
    for t, g, c in bab.pelatih:
        p = hitung.pelatih_kelas(t, g, c, kelas)
        for tid in p.template:
            peta.setdefault((t, tid), p.nama_grup)
    return peta


def _antrean_domain(paket: topics.Topik, tid: str, level: str, rng: random.Random) -> Optional[Deque[Soal]]:
    """Seluruh domain bersoal-bermalrule diacak (tanpa ulang), atau None bila topik tak punya enumerator untuk tid."""
    if paket.domain_parameter is None:
        return None
    try:
        parameter = paket.domain_parameter(tid, level)
    except KeyError:
        return None
    unik: Dict[str, Soal] = {}
    for p in parameter:
        s = replace(paket.templates[tid](**p), level=level)
        if s.malrule:
            unik.setdefault(s.tanda_tangan, s)
    urut: List[Soal] = list(unik.values())
    rng.shuffle(urut)
    return deque(urut)


def _sumber_soal(topik_id: str, tid: str, level: str, seed: int) -> Iterator[Soal]:
    """Aliran soal unik untuk satu template; selesai bila domain habis atau undian terus berulang."""
    paket = topics.ambil(topik_id)
    rng = random.Random("kurikulum-buat|%d|%s|%s|%s" % (seed, topik_id, tid, level))
    antrean = _antrean_domain(paket, tid, level, rng)
    if antrean is not None:
        while antrean:
            yield antrean.popleft()
        return
    terlihat = set()
    gagal = 0
    while gagal < MAKS_UNDI_PER_SLOT:
        soal = generator.buat_soal(tid, rng.randrange(SEED_MIN, SEED_MAKS + 1), level, topik_id)
        if soal.tanda_tangan in terlihat:
            gagal += 1
            continue
        gagal = 0
        terlihat.add(soal.tanda_tangan)
        yield soal


def buat_soal_bab(kelas: int, bab: kk.Bab, jumlah: int, seed: int) -> HasilBuat:
    """Hingga `jumlah` soal unik, bergiliran antar template bab yang tersedia dan dibuka di level kelas."""
    level = hitung.level_kelas(kelas)
    pelatih = tuple(hitung.pelatih_kelas(t, g, c, kelas) for t, g, c in bab.pelatih)
    semua = hitung.template_unik(pelatih)
    dibuka = tuple(r for r in semua if hitung.template_dibuka(r[1]))
    tertutup = tuple(tid for _t, tid in semua if not hitung.template_dibuka(tid))
    nama_grup = _nama_grup_per_template(bab, kelas)
    sumber = [(r, _sumber_soal(r[0], r[1], level, seed)) for r in dibuka]
    item: List[ItemSoal] = []
    while sumber and len(item) < jumlah:
        sisa = []
        for ref, aliran in sumber:
            if len(item) >= jumlah:
                sisa.append((ref, aliran))
                continue
            soal = next(aliran, None)
            if soal is None:
                continue  # template ini habis
            item.append(ItemSoal(len(item) + 1, soal, topics.ambil(ref[0]), nama_grup[ref]))
            sisa.append((ref, aliran))
        sumber = sisa
    return HasilBuat(tuple(item), jumlah, tertutup, any(p.tersedia for p in pelatih))

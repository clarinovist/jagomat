"""Perakit sesi Latihan Lomba: Latihan 10 soal (8 PG + 2 isian) atau Simulasi 35 soal (30 PG + 5 isian).

Aturan rakitan: tiap topik 2-3 soal; dua isian dari topik berbeda; satu template paling
banyak sekali; paling banyak satu soal berbahasa Inggris; banyak soal tiap tingkat dalam batas
(mudah 2-4, sedang 2-5, sulit 2-4); urut kasar mudah ke sulit; posisi kunci A-D seimbang (dua per
huruf); tidak memakai ulang soal yang `tanda_tangan`-nya dilarang (soal dari beberapa sesi terakhir);
jenis soal dari dua sesi terakhir dihindari selama masih memungkinkan (rotasi).

Simulasi (format lomba asli, jalur perakitan terpisah supaya Latihan tetap identik per seed): sebaran topik tetap
`SEBARAN_SIMULASI` (Bilangan 9, Operasi 9, Pengukuran 8, Bangun 9); lima isian tersebar di minimal tiga topik
(maks dua per topik); satu jenis soal (keluarga template) paling banyak dua kali dengan angka/gambar berbeda; tidak
ada soal kembar (tanda tangan unik); paling banyak dua soal berbahasa Inggris; tingkat dalam batas proporsional;
urut kasar mudah ke sulit; posisi kunci 30 PG seimbang (7-8 per huruf); tanpa rotasi jenis.

`rakit_dengan_pelonggaran`: bila larangan soal dari sesi-sesi terakhir membuat perakitan gagal, larangan dari
sesi tertua dilepas lebih dulu, sampai tanpa larangan, supaya anak tidak melihat galat.
Murni dan deterministik untuk `seed` yang sama; tidak menyentuh DB.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from collections import Counter
from typing import AbstractSet, Dict, List, Optional, Sequence, Tuple

import contest_core as C
from contest_paket import MODE_LATIHAN, MODE_SIMULASI, PAKET_AKTIF

JUMLAH_SOAL = PAKET_AKTIF.jumlah_soal
JUMLAH_ISIAN = PAKET_AKTIF.jumlah_isian
JUMLAH_PG = JUMLAH_SOAL - JUMLAH_ISIAN
SOAL_PER_TOPIK_DASAR = 2          # tiap topik minimal dua; sisanya dibagi ke topik berbeda
MAKS_INGGRIS = 1
BATAS_PER_TINGKAT = {1: (2, 4), 2: (2, 5), 3: (2, 4)}   # (minimal, maksimal) soal per tingkat
RIWAYAT_SESI = 5                  # soal dari sesi sejauh ini yang tidak boleh diulang
ROTASI_SESI = 2                   # jenis soal (template) dari sesi sejauh ini dihindari selama bisa
MAKS_PERCOBAAN_RAKIT = 200
MAKS_PERCOBAAN_VARIAN = 30

JUMLAH_SOAL_SIMULASI = PAKET_AKTIF.jumlah_soal_simulasi
JUMLAH_ISIAN_SIMULASI = PAKET_AKTIF.jumlah_isian_simulasi
SEBARAN_SIMULASI = {"bilangan": 9, "operasi": 9, "pengukuran": 8, "bangun": 9}   # ikut PDF contoh lomba
MIN_TOPIK_ISIAN_SIMULASI = 3
MAKS_ISIAN_PER_TOPIK_SIMULASI = 2
MAKS_PAKAI_JENIS_SIMULASI = 2      # satu keluarga template (jenis soal) paling banyak dua kali per simulasi
MAKS_INGGRIS_SIMULASI = 2
BATAS_PER_TINGKAT_SIMULASI = {1: (7, 14), 2: (7, 17), 3: (7, 14)}   # Latihan x3,5 dibulatkan


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
    return _susun_jumlah(seed, rng, soal_semua, JUMLAH_PG)


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


def _keluarga(template: C.Template) -> str:
    return template.keluarga or template.id


def _ambil_berganda(rng: random.Random, calon: Sequence[C.Template], banyak: int) -> Optional[List[C.Template]]:
    """`banyak` template dari `calon`, tiap template paling banyak MAKS_PAKAI_JENIS_SIMULASI kali."""
    wadah = [template for template in calon for _ in range(MAKS_PAKAI_JENIS_SIMULASI)]
    if len(wadah) < banyak:
        return None
    return rng.sample(wadah, banyak)


def _isian_per_topik(rng: random.Random, kelompok: Dict[Tuple[str, str], List[C.Template]]) -> Optional[Dict[str, int]]:
    slot = [topik for topik in C.TOPIK if kelompok.get((topik, C.JENIS_ISIAN))
            for _ in range(MAKS_ISIAN_PER_TOPIK_SIMULASI)]
    if len(slot) < JUMLAH_ISIAN_SIMULASI:
        return None
    hitung = Counter(rng.sample(slot, JUMLAH_ISIAN_SIMULASI))
    return dict(hitung) if len(hitung) >= MIN_TOPIK_ISIAN_SIMULASI else None


def _pilih_template_simulasi(rng: random.Random,
                             kelompok: Dict[Tuple[str, str], List[C.Template]]) -> Optional[List[C.Template]]:
    isian = _isian_per_topik(rng, kelompok)
    if isian is None:
        return None
    terpilih: List[C.Template] = []
    for topik in C.TOPIK:
        banyak_isian = isian.get(topik, 0)
        pg = _ambil_berganda(rng, kelompok.get((topik, C.JENIS_PG), []), SEBARAN_SIMULASI[topik] - banyak_isian)
        isi = _ambil_berganda(rng, kelompok.get((topik, C.JENIS_ISIAN), []), banyak_isian)
        if pg is None or isi is None:
            return None
        terpilih += pg + isi
    if max(Counter(_keluarga(t) for t in terpilih).values()) > MAKS_PAKAI_JENIS_SIMULASI:
        return None
    tingkat = Counter(t.tingkat for t in terpilih)
    if not all(minimal <= tingkat[level] <= maksimal
               for level, (minimal, maksimal) in BATAS_PER_TINGKAT_SIMULASI.items()):
        return None
    return terpilih


def _bangun_unik(rng: random.Random, templates: Sequence[C.Template],
                 terlarang: AbstractSet[str]) -> Optional[List[C.SoalLomba]]:
    """Seperti `_bangun_semua`, tetapi template boleh berulang: tanda tangan soal dalam satu sesi wajib unik."""
    dipakai = set(terlarang)
    hasil: List[C.SoalLomba] = []
    for template in templates:
        for _ in range(MAKS_PERCOBAAN_VARIAN):
            soal = C.buat_soal(template, random.Random(rng.getrandbits(64)))
            tanda = C.tanda_tangan(soal)
            if tanda in dipakai:
                continue
            dipakai.add(tanda)
            hasil.append(soal)
            break
        else:
            return None
    return hasil


def _rakit_simulasi(seed: int, pool: Sequence[C.Template], tanda_terlarang: AbstractSet[str]) -> Sesi:
    rng = random.Random(seed)
    kelompok = _kelompokkan(pool)
    for _ in range(MAKS_PERCOBAAN_RAKIT):
        templates = _pilih_template_simulasi(rng, kelompok)
        if templates is None:
            continue
        soal_semua = _bangun_unik(rng, templates, tanda_terlarang)
        if soal_semua is None or sum(1 for s in soal_semua if s.inggris) > MAKS_INGGRIS_SIMULASI:
            continue
        return _susun_jumlah(seed, rng, soal_semua, JUMLAH_SOAL_SIMULASI - JUMLAH_ISIAN_SIMULASI)
    raise GagalMerakitSesi(
        f"tidak bisa merakit simulasi dari {len(pool)} template setelah {MAKS_PERCOBAAN_RAKIT} percobaan")


def _susun_jumlah(seed: int, rng: random.Random, soal_semua: Sequence[C.SoalLomba], jumlah_pg: int) -> Sesi:
    """Acak, urutkan mudah ke sulit, lalu tata pilihan dengan posisi kunci seimbang untuk `jumlah_pg` soal PG."""
    diacak = list(soal_semua)
    rng.shuffle(diacak)
    urut = sorted(diacak, key=lambda soal: soal.tingkat)    # stabil: seri tetap acak
    posisi = iter(C.posisi_seimbang(jumlah_pg, rng))
    butir = []
    for nomor, soal in enumerate(urut, start=1):
        if soal.jenis == C.JENIS_ISIAN:
            butir.append(ButirSesi(nomor, soal, (), (), -1))
            continue
        letak = next(posisi)
        pilihan = C.susun_pilihan(soal, letak, rng)
        butir.append(ButirSesi(nomor, soal, pilihan, C.gambar_pilihan(soal, pilihan), letak))
    return Sesi(seed=seed, butir=tuple(butir))


def rakit_dengan_pelonggaran(seed: int, pool: Sequence[C.Template],
                             larangan_per_sesi: Sequence[AbstractSet[str]],
                             template_dihindari: AbstractSet[str] = frozenset(),
                             mode: str = MODE_LATIHAN) -> Sesi:
    """Rakit sesi dengan larangan soal dari sesi-sesi terakhir (`larangan_per_sesi`: terbaru dulu).

    Percobaan pertama memakai semua larangan (sama dengan `rakit_sesi`). Bila gagal, larangan sesi TERTUA
    dilepas satu per satu sampai tanpa larangan; baru bila itu pun gagal, `GagalMerakitSesi` dilempar.
    """
    for banyak in range(len(larangan_per_sesi), -1, -1):
        terlarang = frozenset().union(*larangan_per_sesi[:banyak])
        try:
            return rakit_sesi(seed, pool, terlarang, template_dihindari=template_dihindari, mode=mode)
        except GagalMerakitSesi:
            if banyak == 0:
                raise
    raise GagalMerakitSesi("tidak ada percobaan perakitan")   # tak terjangkau: range selalu memuat 0


def rakit_sesi(seed: int, pool: Sequence[C.Template], tanda_terlarang: AbstractSet[str],
               template_dihindari: AbstractSet[str] = frozenset(), mode: str = MODE_LATIHAN) -> Sesi:
    """Rakit satu sesi.

    `tanda_terlarang`: tanda tangan soal dari `RIWAYAT_SESI` sesi terakhir (wajib tidak dipakai ulang).
    `template_dihindari`: id template dari `ROTASI_SESI` sesi terakhir; dihindari agar jenis soal
    berganti-ganti, tetapi dilepas bila tanpa mereka sesi tidak bisa dirakit (tidak pernah gagal karenanya).
    `mode`: Latihan (bawaan, jalur lama apa adanya) atau Simulasi (tanpa rotasi jenis).
    """
    if mode == MODE_SIMULASI:
        return _rakit_simulasi(seed, pool, tanda_terlarang)
    if mode != MODE_LATIHAN:
        raise ValueError(f"mode tidak dikenal: {mode!r}")
    if template_dihindari:
        segar = [template for template in pool if template.id not in template_dihindari]
        try:
            return _rakit(seed, segar, tanda_terlarang)
        except GagalMerakitSesi:
            pass
    return _rakit(seed, pool, tanda_terlarang)

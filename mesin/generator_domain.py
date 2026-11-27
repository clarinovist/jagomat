"""Domain soal sah per (template, level), dihitung sekali per proses.

Topik `unik_per_lembar` dan admin kurikulum sama-sama butuh sidik jari seluruh
domain parameter satu template di satu level. Enumerasi penuh (render tiap
parameter, hitung sidik jari, saring malrule) mahal: ratusan milidetik untuk
matematika-awal. Hasilnya hanya bergantung pada fungsi template, enumerator,
`template_id`, dan level, jadi dihitung sekali dan dipakai bersama.

Yang disimpan hanya sidik jari (string) dan indeks parameter, bukan objek
`Soal`: `Soal.parameter` adalah dict yang bisa diubah, dan enumerator
berkontrak "dict baru setiap panggilan". Soal yang benar-benar dipakai
dirender ulang dari satu parameter segar.

Modul ini murni: tanpa DB, tanpa env, tanpa RNG, dan tidak mengimpor
`generator` (menghindari impor melingkar).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Callable


@dataclass(frozen=True)
class DomainSidik:
    """Sidik jari domain satu template di satu level.

    `tanda` dan `indeks` sejajar. Urutan = urutan kemunculan PERTAMA sidik jari
    itu; `indeks` = posisi parameter TERAKHIR yang menghasilkannya. Itu persis
    perilaku dict `{tanda_tangan: Soal}` lama (nilai ditimpa, posisi kunci tetap).
    """

    jumlah_parameter: int
    tanda: tuple[str, ...]
    indeks: tuple[int, ...]
    himpunan: frozenset[str]


@lru_cache(maxsize=None)
def domain_sidik(
    templat: Callable[..., object],
    enumerator: Callable[[str, str], tuple],
    template_id: str,
    level: str,
) -> DomainSidik:
    """Bangun (atau ambil dari cache) sidik jari domain; hanya soal bermalrule.

    Kunci cache memakai objek fungsi, bukan id topik, supaya paket ad-hoc
    (gabungan) dan test yang mengganti template otomatis dapat entri baru.
    Galat enumerator/template merambat apa adanya dan tidak di-cache.
    """
    parameter = enumerator(template_id, level)
    posisi: dict[str, int] = {}
    for i, p in enumerate(parameter):
        soal = replace(templat(**p), level=level)
        if soal.malrule:
            posisi[soal.tanda_tangan] = i
    return DomainSidik(
        jumlah_parameter=len(parameter),
        tanda=tuple(posisi),
        indeks=tuple(posisi.values()),
        himpunan=frozenset(posisi),
    )


def bersihkan_cache_domain() -> None:
    """Kosongkan cache; untuk test yang mengubah internal enumerator/template."""
    domain_sidik.cache_clear()

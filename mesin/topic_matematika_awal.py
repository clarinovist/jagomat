"""Matematika Awal (P1/P2 dan kelak P3–P6 jarang), khusus Latihan manual dan lembar cetak.

Topik lintas bab Kurikulum Merdeka SD yang belum punya soal (bentuk, ukuran,
diagram, pola, pecahan sederhana, waktu, peluang). Semua soal teks, tanpa gambar.
Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis
pasti dari satu jawaban. Tiap jenis ada di modul `awal_<jenis>.py`-nya sendiri
dan berhenti pada kunci dihitung dari parameter + solver terpisah di tes.

CARA MENAMBAH SATU JENIS: tulis modul `awal_<jenis>.py` (fungsi soal, `LEVEL`,
`domain_parameter(level)`, `parameter(rng, level)`), lalu tambahkan SATU entri
`Jenis(...)` di `JENIS` di bawah. Komposisi, registri template, sampler,
enumerator domain, dan judul bagian dibangun dari `JENIS`. Titik sentuh lain
(sakelar, label, kartu rumus, inventaris visual, PG, pancingan) ada di
checklist laporan tahap 2; `test_matematika_awal_*` mengunci yang bisa dikunci.

Palang: topik ini `hanya_manual`, jadi tidak ikut Campuran, siklus terpandu,
mastery, atau Pendamping karena belum punya grup mastery, kartu intervensi, dan
playbook. Pembuatan soal di balik `OSN_MATEMATIKA_AWAL` (bawaan 1, lihat
`matematika_awal_versions`); pembaca histori selalu mengenal topik dan jenisnya.
Kunci dan malrule dihitung dari parameter; kunci dicek solver terpisah yang
hanya membaca teks (test_matematika_awal_domain).
"""
from __future__ import annotations

import random
from typing import Callable, NamedTuple

import awal_kenali_bentuk as kenali_bentuk
from templates import Soal
from topics import Topik, daftarkan

TOPIK_ID = "matematika-awal"
# Panjang satu lembar; jenis level itu diulang bergiliran sampai penuh.
JUMLAH_SOAL_LEMBAR = 10
BAGIAN = "A"


class Jenis(NamedTuple):
    """Satu jenis soal: template, sampler, level pemakai, dan enumerator domain sahnya."""

    template_id: str
    fungsi: Callable[..., Soal]
    sampler: Callable[[random.Random, str], dict]  # (rng, level) -> parameter
    level: tuple
    domain_parameter: Callable[[str], tuple]  # level -> parameter sah (tuple of dict)


# Urutan = urutan kemunculan di lembar sebelum dikocok. TAMBAH JENIS BARU DI SINI.
JENIS = (
    Jenis(kenali_bentuk.TEMPLATE_ID, kenali_bentuk.kenali_bentuk, kenali_bentuk.parameter,
          kenali_bentuk.LEVEL, kenali_bentuk.domain_parameter),
)
_PER_ID = {j.template_id: j for j in JENIS}
if len(_PER_ID) != len(JENIS):
    raise RuntimeError("template_id jenis Matematika Awal tidak unik")
LEVEL_TOPIK = tuple(sorted({lv for j in JENIS for lv in j.level}))
PROFIL_LEVEL = {level: {} for level in LEVEL_TOPIK}


def _komposisi(level: str) -> tuple:
    """Jenis level itu, diulang bergiliran sampai JUMLAH_SOAL_LEMBAR."""
    jenis = [j.template_id for j in JENIS if level in j.level]
    return tuple(jenis[i % len(jenis)] for i in range(JUMLAH_SOAL_LEMBAR))


KOMPOSISI = {level: _komposisi(level) for level in LEVEL_TOPIK}


def _jenis(template_id: str, level: str) -> Jenis:
    if template_id not in _PER_ID:
        raise KeyError(template_id)
    jenis = _PER_ID[template_id]
    if level not in jenis.level:
        raise ValueError(f"jenis {template_id} tidak tersedia untuk level {level!r}")
    return jenis


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    return _jenis(template_id, level).sampler(rng, level)


def domain_parameter(template_id: str, level: str) -> tuple:
    """Seluruh parameter sah satu jenis di satu level; dict baru setiap panggilan."""
    return _jenis(template_id, level).domain_parameter(level)


daftarkan(Topik(
    id=TOPIK_ID,
    nama="Matematika Awal",
    judul_lembar="Latihan Matematika Awal",
    judul_penilaian="Penilaian — Matematika Awal",
    templates={j.template_id: j.fungsi for j in JENIS},
    komposisi=KOMPOSISI,
    profil=PROFIL_LEVEL,
    judul_bagian={BAGIAN: "Matematika Awal"},
    parameter_untuk=_parameter,
    unik_per_lembar=True,
    domain_parameter=domain_parameter,
    hanya_manual=True,
))

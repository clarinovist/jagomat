"""Fase 0 Task 0.2: guard variasi parameter lintas paket.

Mencegah kambuhnya pola "parameter hardcoded sedikit" (contoh nyata yang
ditemukan saat diskusi seed: pecahan_operasi_campuran memilih dari 2
kombinasi per level — dua anak beda seed bisa dapat soal pecahan
identik). Paket baru WAJIB rentang parameter lebar.

Pengecualian sempit: keputusan pengguna 30 Okt 2026 untuk bilangan-dasar
P1/P2 membatasi hasil sampai 20. Domain sah memang kecil (45/145 pasangan),
bukan sampler hardcoded; jangan memperlebar angka atau variasi nama/benda.
Tiap (template, level) wajib >=ceil(90% domain enumerator) dalam 500 seed,
dan seluruh sampel wajib anggota domain. Topik lain tetap >=200.

Kontrak yang diuji:
  - tiap (template, level) di paket BARU (di luar 19 template asli)
    punya >= 200 kombinasi parameter unik dari 500 seed;
  - paket LAMA diverifikasi tidak kambuh ke pola 2-combo (>= 3 kombinasi);
  - lembar dari seed berbeda mayoritas berbeda tanda tangan (>= 90%).
"""

from __future__ import annotations

import sys
from math import ceil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
from generator import buat_lembar, buat_soal  # noqa: E402

JUMLAH_SEED = 500
BATAS_UNIK_BARU = 200
BATAS_UNIK_LAMA = 3  # paket lama cukup tidak kambuh ke 2-combo
MIN_LEMBAR_BEDA = 0.9

# 19 template asli dari 2 paket pertama (pola-bilangan + aritmetika-dasar).
# Paket baru tidak boleh mengubah daftar ini — mereka diuji dengan
# BATAS_UNIK_BARU yang lebih ketat.
_TEMPLATE_BAWAAN: frozenset[str] = frozenset(
    {
        # pola-bilangan (16 template)
        "deret_aritmetika",
        "deret_aritmetika_turun",
        "deret_geometri",
        "deret_bertingkat",
        "siklus_huruf",
        "siklus_warna",
        "korek_api",
        "titik_segitiga",
        "deret_terbalik_aritmetika",
        "deret_terbalik_geometri",
        "siklus_hari",
        "jumlah_siklus",
        "suku_ke_n",
        "sisa_bagi_siklus",
        "pola_pecahan",
        "jumlah_deret",
        # aritmetika-dasar (3 template)
        "urutan_operasi_1",
        "fpb_dua_bilangan",
        "pecahan_operasi_campuran",
    }
)


def _canonical(p: dict) -> tuple:
    """Serialize parameter to hashable tuple (list -> tuple)."""
    items = []
    for k in sorted(p):
        v = p[k]
        if isinstance(v, list):
            v = tuple(v)
        items.append((k, v))
    return tuple(items)


def _pasangan_pakai() -> list[tuple[str, str, str]]:
    """(topik_id, level, template_id) untuk tiap template yang dipakai.

    Hanya template yang sudah terimplementasi di `paket.templates` yang
    diuji — komposisi boleh mendaftarkan id yang belum ada saat paket
    masih dibangun bertahap (Task 1.1 mulai dari #1 #2). Begitu semua
    template masuk, seluruh (template, level) kena uji.
    """
    hasil: list[tuple[str, str, str]] = []
    for topik_id in topics.daftar_topik():
        paket = topics.ambil(topik_id)
        for level in paket.komposisi:
            for template_id in set(paket.komposisi[level]):
                if template_id in paket.templates:
                    hasil.append((topik_id, level, template_id))
    return hasil


def _kombinasi_unik(topik_id: str, level: str, template_id: str) -> set[tuple]:
    unik: set[tuple] = set()
    for seed in range(1, JUMLAH_SEED + 1):
        s = buat_soal(template_id, seed, level=level, topik=topik_id)
        unik.add(_canonical(s.parameter))
    return unik


def test_template_baru_punya_cukup_kombinasi():
    """Paket baru (di luar 19 template asli) harus >= 200 kombinasi.

    Template lama sengaja tidak diwajibkan 200 (rentang eksponensial
    dibatasi, P3 dibatasi desain). Tapi harus >= 3 = tidak kambuh ke
    pola hardcoded 2-combo (pecahan sudah diperbaiki).
    """
    for topik_id, level, template_id in _pasangan_pakai():
        unik = _kombinasi_unik(topik_id, level, template_id)
        if topik_id == "bilangan-dasar":
            from topic_basic_numbers import domain_parameter
            domain = {_canonical(p) for p in domain_parameter(template_id, level)}
            assert domain, (topik_id, template_id, level)
            assert unik <= domain, ("sampler keluar domain", topik_id, level, unik - domain)
            batas = ceil(0.9 * len(domain))
        else:
            batas = BATAS_UNIK_BARU if template_id not in _TEMPLATE_BAWAAN else BATAS_UNIK_LAMA
        assert len(unik) >= batas, (
            f"{topik_id}/{template_id}@{level}: "
            f"cuma {len(unik)} kombinasi unik (batas {batas})"
        )


def _paket_lengkap(topik_id: str) -> bool:
    """True jika semua template di komposisi sudah terimplementasi.

    Paket yang masih dibangun bertahap (Task 1.1 mulai #1 #2) tidak
    bisa membangun lembar penuh — skip dari test lembar signature.
    """
    paket = topics.ambil(topik_id)
    for level in paket.komposisi:
        for tid in set(paket.komposisi[level]):
            if tid not in paket.templates:
                return False
    return True


def test_lembar_seed_beda_mayoritas_berbeda():
    """Lembar dari seed berbeda harus mayoritas menghasilkan lembar beda."""
    for topik_id in topics.daftar_topik():
        if not _paket_lengkap(topik_id):
            continue
        paket = topics.ambil(topik_id)
        for level in paket.komposisi:
            tanda = {
                buat_lembar(seed, level=level, topik=topik_id).tanda_tangan
                for seed in range(1, JUMLAH_SEED + 1)
            }
            assert len(tanda) >= JUMLAH_SEED * MIN_LEMBAR_BEDA, (
                f"{topik_id}@{level}: cuma {len(tanda)}/{JUMLAH_SEED} lembar beda"
            )

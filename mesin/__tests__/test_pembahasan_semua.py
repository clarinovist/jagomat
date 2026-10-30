"""Pengunci roller pembahasan (feedback Filia poin 5, tahap 2).

pembahasan ("Perhitungan/Langkah") sudah hidup untuk statistika; orang tua
harus melihatnya untuk SEMUA topik. Roll di sini per modul besar, tapi
kontraknya satu:

1. Setiap template TERDAFTAR di setiap topik menghasilkan pembahasan
   tak-kosong (string mana pun sah — bentuknya bebas per template).
2. pembahasan TIDAK ikut tanda_tangan (bank soal & replay kebal).
3. pembahasan tak berisi KUNCI mentah yang bisa dipakai menebak tanpa
   kerja: cek lembut — kunci tak boleh sama dengan SELURUH string
   pembahasan (pembahasan selalu lebih panjang dari angka kuncinya).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
from templates import LEVEL  # noqa: E402


SEMUA_TOPIK = [
    t for t in topics.daftar_topik()
    if t != "campuran"  # campuran mendelegasikan ke topik pemilik
]


@pytest.mark.parametrize("topik_id", SEMUA_TOPIK)
def test_semua_template_punya_pembahasan(topik_id):
    paket = topics.ambil(topik_id)
    for level in LEVEL:
        urutan = paket.komposisi.get(level)
        if not urutan:
            continue
        for template_id in sorted(set(urutan)):
            rng_seed = abs(hash((topik_id, template_id))) % 100000
            import random
            rng = random.Random(rng_seed)
            from templates import REGISTRI
            template_fn = REGISTRI[template_id]
            # parameter via paket masing-masing (kunci-arg: template_id)
            param = paket.parameter_untuk(template_id, rng, level) if paket.parameter_untuk else {}
            if not param:
                continue
            soal = template_fn(**param)
            assert getattr(soal, "pembahasan", ""), (
                f"{topik_id}@{level}: template {template_id} tanpa pembahasan"
            )


@pytest.mark.parametrize("topik_id", SEMUA_TOPIK)
def test_pembahasan_tak_mengubah_tanda_tangan(topik_id):
    paket = topics.ambil(topik_id)
    import random
    rng = random.Random(7)
    from templates import REGISTRI
    lvl = LEVEL[-1]
    for template_id in sorted(set(paket.komposisi.get(lvl, ())))[:6]:
        param = paket.parameter_untuk(template_id, rng, lvl) if paket.parameter_untuk else {}
        if not param:
            continue
        soal = REGISTRI[template_id](**param)
        butir = ",".join(f"{k}={soal.parameter[k]}" for k in sorted(soal.parameter))
        assert soal.tanda_tangan == f"{soal.level}|{template_id}({butir})"


@pytest.mark.parametrize("topik_id", SEMUA_TOPIK)
def test_pembahasan_bukan_kunci_mentah(topik_id):
    """Pembahasan harus lebih dari sekadar angka kunci: minimal ada teks."""
    paket = topics.ambil(topik_id)
    import random
    rng = random.Random(3)
    from templates import REGISTRI
    lvl = next(lv for lv in LEVEL if paket.komposisi.get(lv))
    for template_id in sorted(set(paket.komposisi.get(lvl, ())))[:6]:
        param = paket.parameter_untuk(template_id, rng, lvl) if paket.parameter_untuk else {}
        if not param:
            continue
        soal = REGISTRI[template_id](**param)
        pb = getattr(soal, "pembahasan", "")
        if not pb:
            continue  # sudah dicakup test lain
        assert pb.strip() != soal.kunci.strip(), (
            f"{topik_id}/{template_id}: pembahasan = kunci mentah"
        )


def test_pembahasan_tidak_generik():
    """Pembahasan harus MENJELASKAN caranya, bukan mengulang jawabannya.

    Bentuk lama "Langkah: jawaban benar = X. Cocokkan dengan caramu
    sendiri, ya." tidak mengajari apa pun — anak yang salah tetap tidak
    tahu langkahnya. Sejak halaman hasil anak dibuka (poin b feedback
    Filia), pembahasan wajib memuat langkah/rumusnya.
    """
    import random

    from templates import REGISTRI

    pelanggar = []
    for topik_id in SEMUA_TOPIK:
        paket = topics.ambil(topik_id)
        for level in LEVEL:
            for template_id in sorted(set(paket.komposisi.get(level, ()))):
                rng = random.Random(abs(hash((topik_id, template_id))) % 99991)
                param = (
                    paket.parameter_untuk(template_id, rng, level)
                    if paket.parameter_untuk else {}
                )
                if not param:
                    continue
                pb = getattr(REGISTRI[template_id](**param), "pembahasan", "")
                if "Cocokkan dengan caramu" in pb:
                    pelanggar.append((topik_id, template_id))
    assert not pelanggar, (
        f"{len(set(pelanggar))} template masih memakai pembahasan generik: "
        f"{sorted(set(pelanggar))[:6]}"
    )

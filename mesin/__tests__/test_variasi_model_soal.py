"""Pengunci feedback Filia poin 2 (opsi A) — variasi MODEL soal antar-seed.

Klaim Filia: "no.1,4,7 modus lagi; no.3,5,8 rata-rata sama persis modelnya."
Akar masalah (diverifikasi sesi lain dengan mengukur generator): komposisi
menaruh template BERULANG di POSISI TETAP, jadi antar-seed berdekatan posisi
yang sama sering bermodel identik — yang berulang adalah POLA (template +
varian), bukan hanya angkanya (angka sudah unik 87% lewat tanda_tangan).

Yang diukur di sini = fraksi posisi yang (template_id, varian)-nya SAMA
dengan seed SEBELUMNYA, dirata-rata atas 500 seed berurutan.

Baseline (sebelum fix, diukur 1 Sep 2026):
  - P5 ~56.9%  (setup bilang ~55%)
  - P3 ~67.5%  (hanya 2 template, modus terkunci)
  - P4 ~45.2%
  - P6 ~56.4%

Target opsi A: P5 turun ke < 25%. P3/P4/P6 dilaporkan; P4/P6 juga harus
< 25%; P3 (2 template saja) tidak bisa ditekan di bawah ~1/3 secara
struktural tanpa menambah varian/template (itu opsi B), jadi dibatasi
jauh di bawah baseline (< 50%).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generator  # noqa: E402

JUMLAH_SEED = 500
from templates import LEVEL
from topics import ambil


def _fraksi_pola_sama(level: str, n_seed: int = JUMLAH_SEED) -> float:
    """Rata-rata fraksi posisi dgn (template,varian) sama dgn seed sebelum."""
    prev: list[tuple[str, str]] | None = None
    total_pos = 0
    total_sama = 0
    for seed in range(1, n_seed + 1):
        lembar = generator.buat_lembar(seed, level=level, topik="statistika")
        now = [(s.template_id, s.parameter.get("varian", "-")) for s in lembar.soal]
        if prev is not None:
            total_sama += sum(1 for a, b in zip(prev, now) if a == b)
            total_pos += len(now)
        prev = now
    return total_sama / total_pos


@pytest.mark.parametrize("level", [lv for lv in LEVEL if lv in ambil("statistika").komposisi])
def test_posisi_tidak_terkunci_pada_model_yang_sama(level):
    """Cetak angka per level & pastikan jauh di bawah baseline terkunci."""
    f = _fraksi_pola_sama(level)
    batas = 0.50 if level == "P3" else 0.40
    assert f < batas, (
        f"statistika@{level}: {f*100:.1f}% posisi bermodel sama dgn seed "
        f"sebelumnya (batas {batas*100:.0f}%) — komposisi masih terkunci?"
    )


def test_P5_di_bawah_25_persen():
    """Batas keras dari setup: P5 (soundgarden klaim Filia) < 25%."""
    f = _fraksi_pola_sama("P5")
    assert f < 0.25, (
        f"P5 statistika: {f*100:.1f}% masih di atas 25% — "
        "variasi model antar-seed belum cukup"
    )


def test_P4_dan_P6_juga_di_bawah_25_persen():
    for level in ("P4", "P6"):
        f = _fraksi_pola_sama(level)
        assert f < 0.25, f"{level}: {f*100:.1f}% masih di atas 25%"


def test_tidak_ada_template_mendominasi_melebihi_ceil_n_3():
    """Batas komposisi: satu template maks ceil(n/3) kali per lembar.

    P3 sengaja tidak diuji: komposisinya cuma 2 template (median_modus,
    diagram_batang_garis) @ 5 soal masing-masing utk 10 posisi — batas
    ceil(10/3)=4 secara matematis TIDAK bisa dipenuhi (2×4=8 < 10) tanpa
    menambah template, yang dilarang oleh opsi A. P4/P5/P6 semua di
    bawah batas dan WAJIB terjaga setelah acak-posisi.
    """
    for level in ("P4", "P5", "P6"):
        for seed in range(1, 120):
            lembar = generator.buat_lembar(seed, level=level, topik="statistika")
            n = len(lembar.soal)
            cap = (n + 2) // 3  # ceil(n/3)
            from collections import Counter

            cnt = Counter(s.template_id for s in lembar.soal)
            pelanggar = {t: c for t, c in cnt.items() if c > cap}
            assert not pelanggar, (
                f"statistika@{level}/seed {seed}: {pelanggar} melebihi cap {cap}"
            )

"""Data materi Kurikulum Merdeka per kelas (`kurikulum_kelas`): bentuk, rujukan grup, dan isolasi impor."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kurikulum_katalog as kat  # noqa: E402
import kurikulum_kelas as kk  # noqa: E402

AKAR_MESIN = Path(__file__).resolve().parent.parent
GRUP_KATALOG = frozenset((e.topik_id, kode) for e in kat.KATALOG for kode, _n, _p in e.grup)


def test_kelas_satu_sampai_enam_lengkap_dan_berurutan():
    assert [k.kelas for k in kk.KELAS] == [1, 2, 3, 4, 5, 6]
    assert all(k.bab for k in kk.KELAS)


@pytest.mark.parametrize("kelas", kk.KELAS, ids=lambda k: "kelas%d" % k.kelas)
def test_nomor_bab_berurutan_mulai_satu(kelas):
    assert [b.nomor for b in kelas.bab] == list(range(1, len(kelas.bab) + 1))


def test_judul_dan_sub_materi_tak_kosong():
    for k in kk.KELAS:
        for b in k.bab:
            assert b.judul.strip(), (k.kelas, b.nomor)
            assert b.sub_materi and all(s.strip() for s in b.sub_materi), (k.kelas, b.nomor)


def test_setiap_pelatih_menunjuk_grup_katalog_dengan_kecocokan_sah():
    for k in kk.KELAS:
        for b in k.bab:
            for topik_id, kode, cocok in b.pelatih:
                assert (topik_id, kode) in GRUP_KATALOG, (k.kelas, b.nomor, topik_id, kode)
                assert cocok in kk.KECOCOKAN_BAB, (k.kelas, b.nomor, cocok)


def test_tidak_ada_pelatih_ganda_dalam_satu_bab():
    for k in kk.KELAS:
        for b in k.bab:
            kunci = [(t, g) for t, g, _c in b.pelatih]
            assert len(kunci) == len(set(kunci)), (k.kelas, b.nomor)


def test_total_empat_puluh_bab_dan_sumber_tercatat():
    assert sum(len(k.bab) for k in kk.KELAS) == 40
    assert "2022" in kk.SUMBER_BAB


def test_grup_terpakai_hanya_berisi_grup_katalog():
    assert kk.grup_terpakai() <= GRUP_KATALOG


def test_modul_tidak_masuk_penutupan_impor_generator():
    kode = ("import sys; sys.path.insert(0, %r); import generator; "
            "sys.exit(1 if 'kurikulum_kelas' in sys.modules else 0)" % str(AKAR_MESIN))
    assert subprocess.run([sys.executable, "-c", kode]).returncode == 0


def test_modul_hanya_mengimpor_stdlib():
    sumber = (AKAR_MESIN / "kurikulum_kelas.py").read_text(encoding="utf-8")
    impor = [b for b in sumber.splitlines() if b.startswith(("import ", "from "))]
    assert impor == ["from __future__ import annotations", "from dataclasses import dataclass",
                     "from typing import Tuple"]

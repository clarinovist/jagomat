"""Keselarasan lintas-modul: daftar topik/label/grup harus cocok dengan registry paket.

Peta kurikulum (label awam, topik cek per kelas, grup mastery) ada di beberapa
modul aplikasi; mesin soal ada di `topics.PAKET`. Tes ini menjaga keduanya tetap
sejalan tanpa mengubah perilaku apa pun.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis_skor  # noqa: E402
import mastery_catalog  # noqa: E402
import topics  # noqa: E402
import topik_awam  # noqa: E402


def _paket() -> dict:
    topics.daftar_topik()  # memuat registry secara malas
    return topics.PAKET


def _topik_cek_per_kelas() -> list:
    return [(kelas, t) for kelas in sorted(cek_gratis_skor.TOPIK_PER_KELAS)
            for t in cek_gratis_skor.TOPIK_PER_KELAS[kelas]]


@pytest.mark.parametrize("kelas,topik_id", _topik_cek_per_kelas())
def test_topik_cek_per_kelas_ada_di_registry(kelas, topik_id):
    assert topik_id in _paket()


def test_topik_dasar_ada_di_registry():
    assert cek_gratis_skor.TOPIK_DASAR in _paket()


@pytest.mark.parametrize("topik_id", sorted(topik_awam.NAMA_AWAM))
def test_label_awam_hanya_untuk_topik_di_registry(topik_id):
    assert topik_id in _paket()


@pytest.mark.parametrize("topik_id", sorted(mastery_catalog.KELOMPOK))
def test_kelompok_mastery_hanya_untuk_topik_di_registry(topik_id):
    assert topik_id in _paket()


def _pola_kelompok() -> list:
    return [(topik_id, kode, pola_id)
            for topik_id, grup in mastery_catalog.KELOMPOK.items()
            for kode, _nama, pola in grup for pola_id in pola]


@pytest.mark.parametrize("topik_id,kode,pola_id", _pola_kelompok())
def test_pola_kelompok_ada_di_template_topiknya(topik_id, kode, pola_id):
    assert pola_id in _paket()[topik_id].templates


def test_tidak_ada_topik_manual_saja_di_cek_per_kelas():
    manual = {t for t, paket in _paket().items() if paket.hanya_manual}
    dipakai = {t for _kelas, t in _topik_cek_per_kelas()}
    assert not (manual & dipakai)


def test_topik_cek_per_kelas_dan_dasar_punya_label_awam():
    topik_cek = {t for _kelas, t in _topik_cek_per_kelas()}
    topik_cek.add(cek_gratis_skor.TOPIK_DASAR)
    assert topik_cek <= set(topik_awam.NAMA_AWAM)


# --- Fase 1: modul-modul membaca dari katalog tunggal ---

import subprocess  # noqa: E402

import kurikulum_katalog  # noqa: E402


def test_nama_awam_diturunkan_dari_katalog():
    assert list(topik_awam.NAMA_AWAM.items()) == list(kurikulum_katalog.label_awam().items())


def test_kelompok_mastery_diturunkan_dari_katalog():
    assert list(mastery_catalog.KELOMPOK.items()) == list(kurikulum_katalog.kelompok_mastery().items())


def test_topik_cek_diturunkan_dari_katalog():
    assert cek_gratis_skor.TOPIK_PER_KELAS == kurikulum_katalog.TOPIK_CEK_PER_KELAS
    assert cek_gratis_skor.TOPIK_DASAR == kurikulum_katalog.TOPIK_CEK_DASAR


def test_katalog_tidak_masuk_penutupan_impor_generator():
    kode = ("import sys; sys.path.insert(0, %r); import generator; "
            "sys.exit(1 if 'kurikulum_katalog' in sys.modules else 0)"
            % str(Path(__file__).resolve().parent.parent))
    assert subprocess.run([sys.executable, "-c", kode]).returncode == 0


def test_katalog_hanya_mengimpor_stdlib():
    sumber = (Path(__file__).resolve().parent.parent / "kurikulum_katalog.py").read_text(encoding="utf-8")
    impor = [b for b in sumber.splitlines() if b.startswith(("import ", "from "))]
    assert impor == ["from __future__ import annotations", "from dataclasses import dataclass",
                     "from typing import Dict, Optional, Tuple"]

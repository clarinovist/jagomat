"""Gerbang fitur Latihan Lomba: bawaan mati; hanya nilai persis "1" yang menyalakan."""
import pytest

import contest_gate as G


def test_bawaan_mati_bila_env_tidak_diatur(monkeypatch):
    monkeypatch.delenv("OSN_LOMBA", raising=False)
    assert G.aktif() is False


def test_nilai_satu_menyalakan(monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    assert G.aktif() is True


@pytest.mark.parametrize("nilai", ["", "0", "2", "true", "ya", "01", "on"])
def test_nilai_lain_tetap_mati(monkeypatch, nilai):
    monkeypatch.setenv("OSN_LOMBA", nilai)
    assert G.aktif() is False

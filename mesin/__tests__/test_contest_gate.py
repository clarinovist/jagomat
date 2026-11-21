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


# --- sakelar admin menggantikan env sebagai sumber utama -------------------------------------

import sqlite3
from contextlib import closing

import feature_switch

SEED = {nama: False for nama in feature_switch.NAMA_SAKELAR}


@pytest.fixture
def berkas_sakelar(tmp_path, monkeypatch):
    path = tmp_path / "sakelar.db"
    monkeypatch.setenv(feature_switch.ENV_BERKAS_DB, str(path))
    feature_switch.bersihkan_cache()
    yield path
    feature_switch.bersihkan_cache()


def _atur(path, aktif):
    feature_switch.ubah("OSN_LOMBA", aktif, actor_id="uji", revisi_diharapkan=1, seed=SEED, path=path)


def test_tanpa_berkas_sakelar_gerbang_mengikuti_env(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    assert G.aktif() is True
    feature_switch.bersihkan_cache()
    monkeypatch.setenv("OSN_LOMBA", "0")
    assert G.aktif() is False


def test_sakelar_hidup_menyalakan_gerbang_walau_env_mati(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")
    _atur(berkas_sakelar, True)
    assert G.aktif() is True


def test_sakelar_mati_mematikan_gerbang_walau_env_menyala(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    _atur(berkas_sakelar, False)
    feature_switch.bersihkan_cache()
    assert G.aktif() is False


def test_berkas_sakelar_rusak_mematikan_gerbang_walau_env_menyala(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    berkas_sakelar.write_text("bukan sqlite")
    assert G.aktif() is False


def test_perubahan_sakelar_berlaku_setelah_cache_dibersihkan(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")
    _atur(berkas_sakelar, True)
    assert G.aktif() is True
    feature_switch.ubah("OSN_LOMBA", False, actor_id="uji", revisi_diharapkan=2, seed=SEED, path=berkas_sakelar)
    assert G.aktif() is False        # ubah() membersihkan cache sendiri

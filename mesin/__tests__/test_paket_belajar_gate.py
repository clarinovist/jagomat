"""Gerbang Paket Belajar: sakelar admin PAKET_BELAJAR bawaan mati, terdaftar di akhir, dan tidak menyentuh harian."""
import pytest

import akses_harian
import feature_switch as fs
import paket_belajar_gate as gate
import sakelar_registry


@pytest.fixture(autouse=True)
def _sakelar_terisolasi(tmp_path, monkeypatch):
    monkeypatch.setenv(fs.ENV_BERKAS_DB, str(tmp_path / "sakelar.db"))
    monkeypatch.delenv("PAKET_BELAJAR", raising=False)
    monkeypatch.delenv("LATIHAN_HARIAN", raising=False)
    fs.bersihkan_cache()
    yield
    fs.bersihkan_cache()


def test_bawaan_mati_dan_hanya_nilai_satu_menyalakan(monkeypatch):
    assert gate.aktif() is False
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    assert gate.aktif() is True
    for nilai in ("true", "0", "", "2", "yes"):
        monkeypatch.setenv("PAKET_BELAJAR", nilai)
        assert gate.aktif() is False


def test_baris_db_menang_atas_env(monkeypatch):
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    seed = sakelar_registry.seed_env()
    assert seed["PAKET_BELAJAR"] is True
    fs.ubah("PAKET_BELAJAR", False, actor_id="tes", revisi_diharapkan=1, seed=seed)
    assert gate.aktif() is False


def test_terdaftar_di_akhir_nama_sakelar_dengan_urutan_registri_sama():
    assert fs.NAMA_SAKELAR[-1] == "PAKET_BELAJAR" and fs.NAMA_SAKELAR.count("PAKET_BELAJAR") == 1
    assert tuple(sakelar_registry._INFO) == fs.NAMA_SAKELAR
    info = sakelar_registry.info("PAKET_BELAJAR")
    assert info.dari_env is gate.dari_env
    assert info.kelompok in sakelar_registry.KELOMPOK
    assert not any(c in info.dampak for c in "\"'&")


def test_tidak_memengaruhi_sakelar_latihan_harian(monkeypatch):
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    assert akses_harian.aktif() is False
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    assert akses_harian.aktif() is True and gate.aktif() is False


def test_nama_sakelar_gerbang_sama_dengan_daftar_utama():
    assert gate.NAMA_SAKELAR in fs.NAMA_SAKELAR

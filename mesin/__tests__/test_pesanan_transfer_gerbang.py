"""Gerbang transfer rekening: sakelar tepat "1" + funnel + runtime produksi + rekening terisi."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pesanan_rekening  # noqa: E402
import pesanan_transfer_gerbang as g  # noqa: E402

REKENING = pesanan_rekening.RekeningPublik("Bank Contoh", "1234567890", "1234 5678 90", "PT Contoh Sintetis")
RUNTIME = object()


@pytest.fixture()
def siap(monkeypatch):
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "1")
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    monkeypatch.setattr(g.pesanan_rekening, "baca_publik", lambda path=None: REKENING)


def test_semua_syarat_terpenuhi_mengembalikan_rekening(siap):
    assert g.rekening_bila_terbuka(RUNTIME) == REKENING


def test_bawaan_tertutup_tanpa_env(monkeypatch):
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF", raising=False)
    assert g.transfer_aktif() is False


@pytest.mark.parametrize("nilai", ["", " 1", "1 ", "true", "01", "0", "yes", "1\n", "ON", "11"])
def test_hanya_tepat_satu_membuka_sakelar(monkeypatch, nilai):
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", nilai)
    assert g.transfer_aktif() is False


def test_nilai_satu_membuka_sakelar(monkeypatch):
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", "1")
    assert g.transfer_aktif() is True


@pytest.mark.parametrize("nilai", ["", " 1", "true", "0"])
def test_sakelar_salah_menutup_gerbang(siap, monkeypatch, nilai):
    monkeypatch.setenv("PESANAN_TRANSFER_AKTIF", nilai)
    assert g.rekening_bila_terbuka(RUNTIME) is None


def test_tanpa_env_menutup_gerbang(siap, monkeypatch):
    monkeypatch.delenv("PESANAN_TRANSFER_AKTIF")
    assert g.rekening_bila_terbuka(RUNTIME) is None


@pytest.mark.parametrize("funnel", ["0", "", "true"])
def test_funnel_mati_menutup_gerbang(siap, monkeypatch, funnel):
    monkeypatch.setenv("FUNNEL_AKTIF", funnel)
    assert g.rekening_bila_terbuka(RUNTIME) is None


def test_runtime_tidak_ada_menutup_gerbang(siap):
    assert g.rekening_bila_terbuka(None) is None


def test_rekening_belum_diisi_menutup_gerbang(siap, monkeypatch):
    monkeypatch.setattr(g.pesanan_rekening, "baca_publik", lambda path=None: None)
    assert g.rekening_bila_terbuka(RUNTIME) is None


@pytest.mark.parametrize("galat", [RuntimeError("x"), OSError("x"), KeyError("x"), Exception("x")])
def test_galat_apa_pun_menutup_gerbang(siap, monkeypatch, galat):
    def _gagal(path=None):
        raise galat
    monkeypatch.setattr(g.pesanan_rekening, "baca_publik", _gagal)
    assert g.rekening_bila_terbuka(RUNTIME) is None


def test_gerbang_tidak_bergantung_sakelar_atau_tahap_midtrans():
    pohon = ast.parse(Path(g.__file__).read_text())
    nama = {n.id for n in ast.walk(pohon) if isinstance(n, ast.Name)}
    nama |= {n.attr for n in ast.walk(pohon) if isinstance(n, ast.Attribute)}
    impor = {a.name for n in ast.walk(pohon) if isinstance(n, ast.Import) for a in n.names}
    impor |= {n.module for n in ast.walk(pohon) if isinstance(n, ast.ImportFrom)}
    assert not nama & {"baca_gerbang", "sakelar_efektif", "konfigurasi_pembayaran", "baca_tahap"}
    assert not any("subscription" in m or "launch" in m or "midtrans" in m for m in impor)

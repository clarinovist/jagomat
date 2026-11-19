"""Karakterisasi enam pembaca sakelar env (F0): kunci perilaku sebelum refactor.

Tes ini mengunci perilaku kode SAAT INI, bukan kebijakan ideal: mana yang
memangkas spasi tepi (funnel, cetak ringkas), mana yang membandingkan mentah
(transfer, pendamping, bank kalimat), dan mana yang menolak nilai asing dengan
ValueError. Hijau terhadap kode apa adanya; refactor tidak boleh mengubah hasil.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai_policy  # noqa: E402
import assistant_http_common  # noqa: E402
import choice_pages  # noqa: E402
import funnel_flag  # noqa: E402
import pesanan_transfer_gerbang  # noqa: E402
import story_frames  # noqa: E402

SAKELAR = (
    "FUNNEL_AKTIF",
    "PESANAN_TRANSFER_AKTIF",
    "PENDAMPING_AKTIF",
    "AI_NONAKTIF",
    "OSN_CETAK_RINGKAS",
    "OSN_BANK_KALIMAT",
)


@pytest.fixture(autouse=True)
def sakelar_bersih(monkeypatch):
    """Hapus keenam sakelar sebelum tiap tes agar tak mewarisi env luar."""
    for nama in SAKELAR:
        monkeypatch.delenv(nama, raising=False)


def _atur(monkeypatch, nama, nilai):
    """Set env; nilai None berarti variabel dibiarkan tidak ada."""
    if nilai is None:
        monkeypatch.delenv(nama, raising=False)
    else:
        monkeypatch.setenv(nama, nilai)


# --- 1. funnel_flag: FUNNEL_AKTIF, spasi di tepi di-strip ---

@pytest.mark.parametrize("nilai,harapan", [
    (None, False), ("", False), ("0", False), ("true", False), ("01", False),
    ("1", True), (" 1 ", True),
], ids=["tanpa-env", "kosong", "nol", "true", "nol-satu", "satu", "satu-spasi"])
def test_funnel_aktif_menstrip_spasi_tepi(monkeypatch, nilai, harapan):
    _atur(monkeypatch, "FUNNEL_AKTIF", nilai)
    hasil = funnel_flag.funnel_aktif()
    assert hasil is harapan


# --- 2. pesanan_transfer_gerbang: PESANAN_TRANSFER_AKTIF, TANPA strip ---

@pytest.mark.parametrize("nilai,harapan", [
    (None, False), ("0", False), ("true", False), ("01", False),
    (" 1", False), ("1 ", False), ("1", True),
], ids=["tanpa-env", "nol", "true", "nol-satu", "spasi-depan", "spasi-belakang", "satu"])
def test_transfer_aktif_membandingkan_mentah_tanpa_strip(monkeypatch, nilai, harapan):
    _atur(monkeypatch, "PESANAN_TRANSFER_AKTIF", nilai)
    hasil = pesanan_transfer_gerbang.transfer_aktif()
    assert hasil is harapan


# --- 3. ai_policy: PENDAMPING_AKTIF + penghenti global AI_NONAKTIF ---

def test_nama_fitur_pendamping_dan_cerita_sah_di_daftar_fitur():
    assert "pendamping" in ai_policy.FITUR
    assert "cerita" in ai_policy.FITUR


@pytest.mark.parametrize("nilai,harapan", [
    ("1", True), (None, False), ("0", False), (" 1", False), ("true", False),
], ids=["satu", "tanpa-env", "nol", "spasi-depan", "true"])
def test_deployment_pendamping_hanya_tepat_satu(monkeypatch, nilai, harapan):
    _atur(monkeypatch, "PENDAMPING_AKTIF", nilai)
    hasil = ai_policy.deployment_mengizinkan("pendamping")
    assert hasil is harapan


def test_ai_nonaktif_menghentikan_pendamping_walau_sakelar_hidup(monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    monkeypatch.setenv("AI_NONAKTIF", "1")
    hasil = ai_policy.deployment_mengizinkan("pendamping")
    assert hasil is False


@pytest.mark.parametrize("nonaktif,harapan", [
    (None, True), ("1", False),
], ids=["tanpa-ai-nonaktif", "ai-nonaktif-satu"])
def test_deployment_cerita_hanya_tergantung_ai_nonaktif(monkeypatch, nonaktif, harapan):
    _atur(monkeypatch, "AI_NONAKTIF", nonaktif)
    hasil = ai_policy.deployment_mengizinkan("cerita")
    assert hasil is harapan


# --- 4. assistant_http_common: PENDAMPING_AKTIF, TANPA strip ---

@pytest.mark.parametrize("nilai,harapan", [
    ("1", True), (None, False), ("0", False), (" 1", False), ("true", False),
], ids=["satu", "tanpa-env", "nol", "spasi-depan", "true"])
def test_assistant_aktif_hanya_tepat_satu(monkeypatch, nilai, harapan):
    _atur(monkeypatch, "PENDAMPING_AKTIF", nilai)
    hasil = assistant_http_common.aktif()
    assert hasil is harapan


# --- 5. choice_pages: OSN_CETAK_RINGKAS, di-strip, nilai asing ValueError ---

@pytest.mark.parametrize("nilai,harapan", [
    (None, False), ("0", False), ("1", True), (" 1 ", True),
], ids=["tanpa-env", "nol", "satu", "satu-spasi"])
def test_cetak_ringkas_nilai_sah_setelah_strip(monkeypatch, nilai, harapan):
    _atur(monkeypatch, "OSN_CETAK_RINGKAS", nilai)
    hasil = choice_pages.cetak_ringkas_aktif()
    assert hasil is harapan


@pytest.mark.parametrize("nilai", ["", "2", "true"], ids=["kosong", "dua", "true"])
def test_cetak_ringkas_nilai_asing_ditolak_valueerror(monkeypatch, nilai):
    _atur(monkeypatch, "OSN_CETAK_RINGKAS", nilai)
    with pytest.raises(ValueError, match="OSN_CETAK_RINGKAS"):
        choice_pages.cetak_ringkas_aktif()


# --- 6. story_frames: OSN_BANK_KALIMAT, TANPA strip, nilai asing ValueError ---

@pytest.mark.parametrize("nilai,harapan", [
    (None, False), ("0", False), ("1", True),
], ids=["tanpa-env", "nol", "satu"])
def test_bank_kalimat_nilai_sah_tanpa_strip(monkeypatch, nilai, harapan):
    _atur(monkeypatch, "OSN_BANK_KALIMAT", nilai)
    hasil = story_frames.aktif()
    assert hasil is harapan


@pytest.mark.parametrize("nilai", [" 1", "", "true"], ids=["spasi-depan", "kosong", "true"])
def test_bank_kalimat_nilai_asing_ditolak_valueerror(monkeypatch, nilai):
    _atur(monkeypatch, "OSN_BANK_KALIMAT", nilai)
    with pytest.raises(ValueError, match="OSN_BANK_KALIMAT"):
        story_frames.aktif()

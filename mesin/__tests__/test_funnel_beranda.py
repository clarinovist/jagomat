"""Beranda `/` memakai landing Cek Kemampuan saat funnel hidup (keputusan pemilik 20 Nov 2026).

Sakelar mati -> landing lama tetap jadi cadangan (bukan halaman "belum dibuka").
Guru/admin yang login tetap ke berandanya sendiri. Data sepenuhnya sintetis.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import funnel_pages  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

CTA = 'href="/daftar?jalur=cek"'
PENANDA_FUNNEL = "contoh ilustrasi, bukan hasil anak sungguhan"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


def test_funnel_hidup_beranda_anonim_sama_dengan_cek_kemampuan(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    kode, isi, header = server.minta("/")
    _, isi_cek, header_cek = server.minta("/cek-kemampuan")
    assert kode == 200
    assert isi == isi_cek
    assert isi.count(CTA) == 1
    assert PENANDA_FUNNEL in isi.lower()
    assert header.get("Content-Security-Policy") == header_cek.get("Content-Security-Policy")


def test_funnel_mati_beranda_tetap_landing_lama(server):
    kode, isi, _ = server.minta("/")
    assert kode == 200
    assert "belum dibuka" not in isi.lower()
    assert CTA not in isi
    assert PENANDA_FUNNEL not in isi.lower()
    assert 'href="/masuk"' in isi


def test_funnel_hidup_guru_login_tetap_ke_berandanya(server, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    kode, isi, _ = server.minta("/", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert PENANDA_FUNNEL not in isi.lower()
    assert CTA not in isi


def test_landing_funnel_tetap_punya_tautan_masuk(monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    isi = funnel_pages.halaman_cek_kemampuan().decode()
    assert 'href="/masuk"' in isi

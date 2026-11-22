"""Pesan di /masuk saat anak membuka halaman murid tanpa sesi sah.

Audit area anak 22 Nov 2026 (#15): anak yang belum pernah masuk tidak boleh
melihat "Sesi kamu sudah habis". Pesan itu hanya untuk kuki sesi yang ada tetapi
tidak sah lagi (kedaluwarsa, akun lain masuk, atau peran bukan murid).
Status dan tujuan redirect tidak berubah: tetap 303 ke /masuk.
"""
from __future__ import annotations

import pytest

from http_test_kit import ServerUji

PESAN_HABIS = "Sesi kamu sudah habis"


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "sakelar.db"))
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


@pytest.mark.parametrize("jalur", ["/murid", "/murid/kerjakan/1", "/murid/lomba"])
def test_belum_pernah_masuk_tidak_melihat_pesan_sesi_habis(server, jalur):
    kode, isi, _ = server.minta(jalur)
    assert kode == 200 and 'action="/masuk"' in isi
    assert PESAN_HABIS not in isi


@pytest.mark.parametrize("jalur", ["/murid", "/murid/kerjakan/1", "/murid/lomba"])
def test_kuki_sesi_tidak_sah_tetap_melihat_pesan_sesi_habis(server, jalur):
    kode, isi, _ = server.minta(jalur, cookie="token-kedaluwarsa-sintetis")
    assert kode == 200 and 'action="/masuk"' in isi
    assert PESAN_HABIS in isi

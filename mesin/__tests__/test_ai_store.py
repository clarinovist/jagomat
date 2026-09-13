"""Regresi guard atomik, persistensi, dan konfigurasi pengendali AI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai_policy  # noqa: E402
import ai_store  # noqa: E402


def test_default_disetujui_tampil_dalam_storage(tmp_path):
    path = tmp_path / "ai.db"
    ai_store.siapkan(path, sekarang=1)
    with ai_store.buka(path) as kon:
        utama, batas = ai_store.konfigurasi(kon)
    assert utama["request_akun_harian"] == 20
    assert utama["uji_harian"] == 3
    assert utama["uji_cooldown_detik"] == 600
    assert (batas["global"]["batas_harian"], batas["global"]["batas_bulanan"]) == (1_000_000, 20_000_000)
    assert (batas["pendamping"]["batas_harian"], batas["pendamping"]["batas_bulanan"]) == (500_000, 10_000_000)
    assert (batas["cerita"]["batas_harian"], batas["lampiran"]["batas_harian"]) == (300_000, 150_000)


def test_reservasi_paralel_tidak_menembus_pagu(tmp_path, monkeypatch):
    path = tmp_path / "ai.db"
    ai_store.siapkan(path, sekarang=1)
    monkeypatch.setenv("AI_HARD_CEILING_BULANAN_USD", "100")
    with ai_store.buka(path) as kon:
        kon.execute("UPDATE batas_fitur SET batas_harian=5000 WHERE fitur='global'")
        kon.execute("UPDATE batas_fitur SET batas_harian=5000 WHERE fitur='cerita'")

    def coba(n):
        try:
            ai_store.reservasi(path, f"op{n}", "cerita", f"akun{n}", "m", 5000, sekarang=100)
            return True
        except ai_store.Ditolak:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        hasil = list(pool.map(coba, (1, 2)))
    assert sorted(hasil) == [False, True]
    with ai_store.buka(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM ledger").fetchone()[0] == 1


def test_unknown_usage_tetap_menghabiskan_reservasi(tmp_path):
    path = tmp_path / "ai.db"
    ai_store.siapkan(path, sekarang=1)
    ai_store.reservasi(path, "op", "cerita", "akun", "m", 5000, sekarang=100)
    ai_store.selesaikan(path, "op", status="tak_pasti", kategori="timeout", sekarang=101)
    with ai_store.buka(path) as kon:
        assert ai_store.ringkasan(kon, sekarang=101)["cerita"]["harian"] == 5000


def test_revisi_stale_ditolak_tanpa_perubahan(tmp_path):
    path = tmp_path / "ai.db"
    ai_store.siapkan(path, sekarang=1)
    nilai = {
        "dihentikan": 0, "request_akun_harian": 20, "uji_harian": 3,
        "uji_cooldown_detik": 600,
    }
    for fitur in ai_policy.FITUR:
        nilai[f"aktif_{fitur}"] = 1
    for fitur, (harian, bulanan) in ai_policy.DEFAULT_LIMIT.items():
        nilai[f"harian_{fitur}"] = harian
        nilai[f"bulanan_{fitur}"] = bulanan
    assert ai_store.ubah(path, nilai, "akun_admin", revisi=1, sekarang=2) == 2
    with pytest.raises(ai_store.Ditolak, match="tab lain"):
        ai_store.ubah(path, nilai, "akun_admin", revisi=1, sekarang=3)

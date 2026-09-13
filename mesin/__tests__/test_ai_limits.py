"""Guard aktual outbound AI dan perubahan pengaturan saat request berjalan."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai_policy  # noqa: E402
import ai_service  # noqa: E402
import ai_store  # noqa: E402


def _nilai(path, **ganti):
    with ai_store.buka(path) as kon:
        utama, _ = ai_store.konfigurasi(kon)
    nilai = {
        "dihentikan": 0, "request_akun_harian": 20, "uji_harian": 3,
        "uji_cooldown_detik": 600,
    }
    for fitur in ai_policy.FITUR:
        nilai[f"aktif_{fitur}"] = 1
    for fitur, (harian, bulanan) in ai_policy.DEFAULT_LIMIT.items():
        nilai[f"harian_{fitur}"] = harian
        nilai[f"bulanan_{fitur}"] = bulanan
    nilai.update(ganti)
    ai_store.ubah(path, nilai, "admin", revisi=utama["revisi"])


def test_global_off_menolak_sebelum_network(monkeypatch):
    path = ai_service.path_store()
    _nilai(path, dihentikan=1)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sintetis")
    terpanggil = []
    with pytest.raises(ai_service.AIUnavailable):
        ai_service.panggil("cerita", "akun", lambda: terpanggil.append(1))
    assert terpanggil == []


def test_hasil_dibuang_bila_revisi_berubah_saat_network(monkeypatch):
    path = ai_service.path_store()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sintetis")

    def provider():
        _nilai(path, dihentikan=1)
        return {"hasil": "usang"}

    with pytest.raises(ai_service.AIUnavailable, match="hasil dibuang"):
        ai_service.panggil("cerita", "akun", provider, operasi_id="op_usang")
    with ai_store.buka(path) as kon:
        baris = kon.execute("SELECT status,biaya FROM ledger WHERE operasi_id='op_usang'").fetchone()
        assert tuple(baris) == ("selesai", ai_policy.RESERVASI_MICRO_USD["cerita"])

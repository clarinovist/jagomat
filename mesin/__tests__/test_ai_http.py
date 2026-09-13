"""Palang HTTP dan UI pengaturan AI khusus pengelola."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai_store  # noqa: E402
import auth  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

SANDI_ADMIN = "sandi-pengelola-ai-123"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("pengelola-ai", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI)
    yield server
    server.berhenti()


def test_hanya_admin_bisa_membaca_dan_angka_default_tampil(server):
    assert server.minta("/admin/ai")[0] == 404
    kode, isi, _ = server.minta("/admin/ai", auth=("guru", SANDI_GURU))
    assert kode == 404
    assert "USD 20.00" not in isi
    kode, isi, header = server.minta("/admin/ai", auth=("pengelola-ai", SANDI_ADMIN))
    assert kode == 200
    for teks in ("USD 1.00", "USD 20.00", "USD 0.50", "USD 10.00", "USD 0.30", "USD 6.00", "USD 0.15", "USD 3.00", "USD 0.05"):
        assert teks in isi
    assert "DEEPSEEK_API_KEY" not in isi
    assert 'name="request_akun_harian"' in isi
    assert 'value="20"' in isi
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert header["X-Frame-Options"] == "DENY"
    assert "noindex" in header["X-Robots-Tag"]


def test_get_admin_ai_tidak_memanggil_provider(server, monkeypatch):
    import assistant_client
    monkeypatch.setattr(assistant_client, "kirim", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("network")))
    assert server.minta("/admin/ai", auth=("pengelola-ai", SANDI_ADMIN))[0] == 200


def test_post_tanpa_csrf_ditolak_dan_tidak_mengubah(server):
    path = Path(__import__("os").environ["AI_BERKAS_DB"])
    with ai_store.buka(path) as kon:
        revisi = ai_store.konfigurasi(kon)[0]["revisi"]
    kode, _, _ = server.minta(
        "/admin/ai/pengaturan", auth=("pengelola-ai", SANDI_ADMIN),
        data={"revisi": str(revisi)},
    )
    assert kode == 403
    with ai_store.buka(path) as kon:
        assert ai_store.konfigurasi(kon)[0]["revisi"] == revisi


def test_admin_bisa_mengubah_semua_pagu_yang_tampil(server):
    kode, isi, _ = server.minta("/admin/ai", auth=("pengelola-ai", SANDI_ADMIN))
    assert kode == 200
    import re
    csrf = re.search(r'name="csrf" value="([^"]+)"', isi).group(1)
    data = {
        "csrf": csrf, "tinjauan": re.search(r'name="tinjauan" value="([^"]+)"', isi).group(1),
        "reauth": SANDI_ADMIN, "revisi": "1", "request_akun_harian": "25",
        "uji_harian": "4", "uji_cooldown_menit": "15",
    }
    for fitur in ("pendamping", "cerita", "lampiran", "uji_sintetis"):
        data[f"aktif_{fitur}"] = "1"
    for fitur in ("global", "pendamping", "cerita", "lampiran", "uji_sintetis"):
        data[f"harian_{fitur}"] = "0.25"
        data[f"bulanan_{fitur}"] = "2.50"
    kode, _, header = server.minta(
        "/admin/ai/pengaturan", auth=("pengelola-ai", SANDI_ADMIN), data=data,
    )
    assert kode == 200  # urllib mengikuti 303 ke halaman hasil
    with ai_store.buka(Path(__import__("os").environ["AI_BERKAS_DB"])) as kon:
        utama, batas = ai_store.konfigurasi(kon)
        assert utama["request_akun_harian"] == 25
        assert batas["global"]["batas_harian"] == 250_000
        assert batas["lampiran"]["batas_bulanan"] == 2_500_000
        assert kon.execute("SELECT COUNT(*) FROM audit_konfigurasi").fetchone()[0] > 0

"""Kontrak precedence dispatcher utama tanpa menjalankan handler fitur."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web  # noqa: E402


def _rekam(monkeypatch, jejak, modul, fungsi, label, *, hasil=False):
    target = importlib.import_module(modul)

    def panggil(*_args, **_kwargs):
        jejak.append(label)
        return hasil

    monkeypatch.setattr(target, fungsi, panggil)


def _penangan(jalur, jejak):
    penangan = object.__new__(web.Penangan)
    penangan.path = jalur
    penangan.server = object()

    def lolos_sandi():
        jejak.append("palang-guru")
        return True

    penangan._lolos_sandi = lolos_sandi
    penangan._kirim = lambda _isi, kode=200: jejak.append(f"respons-{kode}")
    return penangan


def _pasang_get_false(monkeypatch, jejak):
    pasangan = (
        ("subscription_produksi", "pastikan_terpasang", "runtime-langganan"),
        ("subscription_callback", "tangani_get", "callback-langganan"),
        ("subscription_produksi_http", "tangani_get", "langganan-produksi"),
        ("subscription_http", "tangani_get", "langganan"),
        ("admin_http", "tangani_get", "admin"),
        ("admin_http", "tangani_akun_admin", "akun-admin"),
        ("ai_http", "tangani_get", "ai"),
        ("assistant_http", "tangani_get", "pendamping"),
        ("share_http", "tangani_tautan_get", "tautan-bagikan"),
        ("public_http", "tangani_get", "publik"),
        ("auth_http", "tangani_get", "autentikasi"),
        ("registration_http", "tangani_get", "pendaftaran"),
        ("teacher_http", "tangani_beranda_get", "beranda-guru"),
        ("attachment_http", "tangani_get", "lampiran"),
        ("session_http", "tangani_hapus_get", "hapus-sesi"),
        ("session_http", "tangani_get", "sesi"),
        ("session_http", "tangani_lembar_get", "lembar"),
        ("account_http", "tangani_get", "akun-guru"),
        ("teacher_http", "tangani_profil_get", "profil-guru"),
    )
    for modul, fungsi, label in pasangan:
        _rekam(monkeypatch, jejak, modul, fungsi, label)


def test_dispatch_get_berurutan_hingga_fallback(monkeypatch):
    jejak = []
    _pasang_get_false(monkeypatch, jejak)

    _penangan("/akun", jejak)._rute_get()

    assert jejak == [
        "runtime-langganan",
        "callback-langganan",
        "langganan-produksi",
        "langganan",
        "admin",
        "akun-admin",
        "ai",
        "pendamping",
        "tautan-bagikan",
        "publik",
        "autentikasi",
        "pendaftaran",
        "beranda-guru",
        "palang-guru",
        "lampiran",
        "hapus-sesi",
        "sesi",
        "lembar",
        "akun-guru",
        "profil-guru",
        "respons-404",
    ]


def test_fallback_admin_mendahului_seluruh_rute_lokal_get(monkeypatch):
    jejak = []
    _pasang_get_false(monkeypatch, jejak)
    _rekam(monkeypatch, jejak, "admin_http", "tidak_ada", "fallback-admin", hasil=True)

    _penangan("/admin/rute-tidak-ada", jejak)._rute_get()

    assert jejak == [
        "runtime-langganan",
        "callback-langganan",
        "langganan-produksi",
        "langganan",
        "admin",
        "ai",
        "fallback-admin",
    ]


def test_rute_murid_get_mendahului_palang_guru(monkeypatch):
    jejak = []
    _pasang_get_false(monkeypatch, jejak)
    _rekam(monkeypatch, jejak, "student_http", "tangani_get", "murid", hasil=True)
    penangan = _penangan("/murid/latihan", jejak)
    penangan._lolos_sandi = lambda: (_ for _ in ()).throw(
        AssertionError("palang guru terpanggil sebelum rute murid selesai")
    )

    penangan._rute_get()

    assert jejak[-1] == "murid"
    assert "lampiran" not in jejak


def _pasang_post_false(monkeypatch, jejak):
    pasangan = (
        ("subscription_produksi", "pastikan_terpasang", "runtime-langganan"),
        ("subscription_callback", "tangani_post", "callback-langganan"),
        ("subscription_produksi_http", "tangani_post", "langganan-produksi"),
        ("subscription_http", "tangani_post", "langganan"),
        ("admin_http", "tangani_post", "admin"),
        ("ai_http", "tangani_post", "ai"),
        ("product_analytics_http", "tangani_post", "analitik"),
        ("assistant_http", "tangani_inline_post", "pendamping-inline"),
        ("assistant_http", "tangani_post", "pendamping"),
        ("share_http", "tangani_tautan_post", "tautan-bagikan"),
        ("student_http", "tangani_post", "murid"),
        ("auth_http", "tangani_post", "autentikasi"),
        ("registration_http", "tangani_post", "pendaftaran"),
        ("share_http", "tangani_guru_post", "bagikan-guru"),
        ("account_http", "tangani_post", "akun-guru"),
        ("session_http", "tangani_latihan_serupa", "latihan-serupa"),
        ("session_http", "tangani_cerita_post", "cerita"),
        ("session_http", "tangani_pembuatan_gabungan", "sesi-gabungan"),
        ("session_http", "tangani_pembuatan_remedial", "sesi-remedial"),
        ("session_http", "tangani_pembuatan_biasa", "sesi-biasa"),
        ("attachment_http", "tangani_post", "lampiran"),
        ("session_http", "tangani_hapus_post", "hapus-sesi"),
        ("session_http", "tangani_review_post", "review-sesi"),
    )
    for modul, fungsi, label in pasangan:
        _rekam(monkeypatch, jejak, modul, fungsi, label)


def test_dispatch_post_berurutan_hingga_fallback(monkeypatch):
    jejak = []
    _pasang_post_false(monkeypatch, jejak)

    _penangan("/rute-tidak-ada", jejak)._rute_post()

    assert jejak == [
        "runtime-langganan",
        "callback-langganan",
        "langganan-produksi",
        "langganan",
        "admin",
        "ai",
        "analitik",
        "pendamping-inline",
        "pendamping",
        "tautan-bagikan",
        "murid",
        "autentikasi",
        "pendaftaran",
        "palang-guru",
        "bagikan-guru",
        "akun-guru",
        "latihan-serupa",
        "cerita",
        "sesi-gabungan",
        "sesi-remedial",
        "sesi-biasa",
        "lampiran",
        "hapus-sesi",
        "review-sesi",
        "respons-404",
    ]


def test_rute_murid_post_mendahului_palang_guru(monkeypatch):
    jejak = []
    _pasang_post_false(monkeypatch, jejak)
    _rekam(monkeypatch, jejak, "student_http", "tangani_post", "murid", hasil=True)
    penangan = _penangan("/murid/kerjakan/1", jejak)
    penangan._lolos_sandi = lambda: (_ for _ in ()).throw(
        AssertionError("palang guru terpanggil sebelum rute murid selesai")
    )

    penangan._rute_post()

    assert jejak[-1] == "murid"
    assert "bagikan-guru" not in jejak

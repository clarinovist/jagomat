"""Gerbang pembayaran: tiga syarat; FUNNEL_AKTIF saja tidak pernah membuka pembayaran."""
import itertools
import sqlite3

import pytest

import funnel_flag
import pesanan
import subscription as sub
import subscription_produksi
from pesanan_kit import siapkan_db

NILAI = (True, False, None, 1, 0, "True", "1", [], 1.0)
TAHAP = ("nonaktif", "rekonsiliasi", "checkout", "penegakan", "", None, 2, "CHECKOUT")


def test_tabel_kebenaran_gerbang_hanya_true_pada_ketiga_syarat():
    for funnel, sakelar, tahap in itertools.product(NILAI, NILAI, TAHAP):
        diharapkan = (funnel is True and sakelar is True and tahap in ("checkout", "penegakan"))
        assert pesanan.gerbang_pembayaran(funnel, sakelar, tahap) is diharapkan, (funnel, sakelar, tahap)


def test_funnel_aktif_saja_tidak_membuka_pembayaran():
    assert pesanan.gerbang_pembayaran(True, False, "penegakan") is False
    assert pesanan.gerbang_pembayaran(True, True, "rekonsiliasi") is False
    assert pesanan.gerbang_pembayaran(True, None, "checkout") is False
    assert pesanan.gerbang_pembayaran(True, True, "checkout") is True
    assert pesanan.gerbang_pembayaran(True, True, "penegakan") is True
    assert pesanan.gerbang_pembayaran(False, True, "penegakan") is False


KESIAPAN = {"provider_produksi": True, "callback": True, "recovery": True, "kebijakan": True}


@pytest.fixture
def db_tahap(tmp_path):
    path = siapkan_db(tmp_path)
    return path


def _atur_tahap(path, tahap):
    with sqlite3.connect(path) as kon:
        kon.execute("UPDATE pembayaran_konfigurasi SET tahap=? WHERE id=1", (tahap,))


def test_baca_gerbang_menyambung_fungsi_existing_lewat_monkeypatch(db_tahap, monkeypatch):
    panggilan = []
    monkeypatch.setattr(funnel_flag, "funnel_aktif", lambda: panggilan.append("funnel") or True)
    monkeypatch.setattr(subscription_produksi, "sakelar_efektif",
                        lambda path, kesiapan: panggilan.append(("sakelar", path, kesiapan))
                        or sub.Sakelar(True, True, True, False))
    _atur_tahap(db_tahap, "checkout")
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is True
    assert panggilan == ["funnel", ("sakelar", db_tahap, KESIAPAN)]


def test_baca_gerbang_tiap_syarat_gagal_membuat_false(db_tahap, monkeypatch):
    _atur_tahap(db_tahap, "checkout")
    ok = sub.Sakelar(True, True, True, False)
    monkeypatch.setattr(subscription_produksi, "sakelar_efektif", lambda p, k: ok)
    monkeypatch.setattr(funnel_flag, "funnel_aktif", lambda: True)
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is True
    monkeypatch.setattr(funnel_flag, "funnel_aktif", lambda: False)
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is False
    monkeypatch.setattr(funnel_flag, "funnel_aktif", lambda: True)
    monkeypatch.setattr(subscription_produksi, "sakelar_efektif",
                        lambda p, k: sub.Sakelar(True, False, True, False))
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is False
    monkeypatch.setattr(subscription_produksi, "sakelar_efektif", lambda p, k: ok)
    _atur_tahap(db_tahap, "rekonsiliasi")
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is False


def test_baca_gerbang_runtime_tak_terpasang_atau_galat_fail_closed(db_tahap, monkeypatch, tmp_path):
    _atur_tahap(db_tahap, "penegakan")
    monkeypatch.setattr(funnel_flag, "funnel_aktif", lambda: True)
    assert pesanan.baca_gerbang(db_tahap, None) is False          # secret/runtime hilang
    assert pesanan.baca_gerbang(tmp_path / "tidak-ada.db", KESIAPAN) is False
    monkeypatch.setattr(subscription_produksi, "sakelar_efektif",
                        lambda p, k: (_ for _ in ()).throw(RuntimeError("rusak")))
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is False


def test_baca_gerbang_dengan_fungsi_nyata_mengikuti_tahap_tanpa_menebak(db_tahap, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    for tahap, harapan in (("nonaktif", False), ("rekonsiliasi", False),
                           ("checkout", True), ("penegakan", True)):
        _atur_tahap(db_tahap, tahap)
        assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is harapan, tahap
    _atur_tahap(db_tahap, "penegakan")
    assert pesanan.baca_gerbang(db_tahap, dict(KESIAPAN, recovery=False)) is False
    assert pesanan.baca_gerbang(db_tahap, dict(KESIAPAN, callback=False)) is False
    monkeypatch.setenv("FUNNEL_AKTIF", "0")
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is False
    monkeypatch.delenv("FUNNEL_AKTIF")
    assert pesanan.baca_gerbang(db_tahap, KESIAPAN) is False


def test_baca_gerbang_pembaca_disuntik_menggantikan_default(db_tahap):
    assert pesanan.baca_gerbang(db_tahap, None, funnel=lambda: True, sakelar=lambda: True,
                                tahap=lambda: "checkout") is True
    assert pesanan.baca_gerbang(db_tahap, None, funnel=lambda: True, sakelar=lambda: True,
                                tahap=lambda: "nonaktif") is False
    assert pesanan.baca_gerbang(db_tahap, None, funnel=lambda: True, sakelar=lambda: 1,
                                tahap=lambda: "checkout") is False

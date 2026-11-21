"""Metrik runtime lewat HTTP: pemasangan di web.py, rute `/admin/metrik`, dan pencetak di serve.py.

Data sintetis. Singleton `metrik_runtime.METRIK` direset sebelum tiap test.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import metrik_runtime as M  # noqa: E402
import web  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, SANDI_MURID, _login, _minta, server,  # noqa: F401
)

TOKEN_PANJANG = "Zk3p9QxVbN7mTrLw2YdHcF8sAeJuGo5iXq1WnBvRtUy4"


@pytest.fixture(autouse=True)
def metrik_bersih():
    M.METRIK.atur_ulang()
    yield
    M.METRIK.atur_ulang()


# --- /admin/metrik ---------------------------------------------------------------------

def test_admin_mendapat_json_no_store_tanpa_path_mentah(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _minta(server, "/mulai/" + TOKEN_PANJANG)
    _minta(server, "/laporan-ortu/" + TOKEN_PANJANG + "?nama=BudiSintetis")
    _minta(server, "/rahasia-anak-budi")
    kode, isi, header = _minta(server, "/admin/metrik", cookie=token)
    assert kode == 200
    assert header["Content-Type"].startswith("application/json")
    assert header["Cache-Control"] == "no-store"
    data = json.loads(isi)
    assert {"uptime_detik", "rute", "sqlite_locked", "cpu", "galat_metrik"} <= set(data)
    for terlarang in (TOKEN_PANJANG, "BudiSintetis", "rahasia", "budi"):
        assert terlarang not in isi
    assert "GET /mulai" in data["rute"] and "GET /laporan-ortu" in data["rute"]
    assert "GET lainnya" in data["rute"]


def test_selain_admin_sama_dengan_404_admin_lain(server):
    acuan = _minta(server, "/admin/tidak-ada")[:2]
    assert acuan[0] == 404
    anonim = _minta(server, "/admin/metrik")[:2]
    guru = _minta(server, "/admin/metrik", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    murid = _minta(server, "/admin/metrik", auth_basic=("feby", SANDI_MURID))[:2]
    assert anonim == guru == murid == acuan
    assert "uptime_detik" not in anonim[1]


def test_query_string_ditolak_seperti_rute_admin_lain(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    assert _minta(server, "/admin/metrik?x=1", cookie=token)[0] == 404


# --- pemasangan di do_GET / do_POST ------------------------------------------------------

def test_request_tercatat_dengan_status_dan_label(server):
    _minta(server, "/masuk")
    _minta(server, "/masuk", data={"nama": "Salah", "sandi": "salah"})
    rute = M.METRIK.ringkasan()["rute"]
    assert rute["GET /masuk"]["n"] == 1 and rute["GET /masuk"]["status"]["2xx"] == 1
    assert rute["POST /masuk"]["n"] == 1
    assert sum(rute["POST /masuk"]["status"].values()) == 1


def test_galat_locked_tercatat_dan_respons_500_tetap_sama(server, monkeypatch):
    kode_normal, isi_normal, _ = _minta(server, "/masuk")
    assert kode_normal == 200

    def rusak(self):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(web.Penangan, "_rute_get", rusak)
    kode, isi, _ = _minta(server, "/guru")
    assert kode == 500
    assert "locked" not in isi                       # respons 500 lama: tanpa detail galat
    ringkas = M.METRIK.ringkasan()
    assert ringkas["sqlite_locked"] == 1
    assert ringkas["rute"]["GET /guru"]["status"]["5xx"] == 1


def test_galat_selain_locked_tidak_menaikkan_penghitung_respons_tetap_500(server, monkeypatch):
    def rusak(self):
        raise sqlite3.OperationalError("no such table: x")
    monkeypatch.setattr(web.Penangan, "_rute_post", rusak)
    kode, _, _ = _minta(server, "/masuk", data={"a": "b"})
    assert kode == 500
    ringkas = M.METRIK.ringkasan()
    assert ringkas["sqlite_locked"] == 0
    assert ringkas["rute"]["POST /masuk"]["status"]["5xx"] == 1


def test_kode_metrik_rusak_tidak_mengubah_respons(server, monkeypatch):
    def rusak(*a, **k):
        raise RuntimeError("rusak sintetis")
    monkeypatch.setattr(M.METRIK, "catat_request", rusak)
    kode, _, _ = _minta(server, "/masuk")
    assert kode == 200
    assert M.METRIK.ringkasan()["galat_metrik"] >= 1


def test_status_tidak_bocor_antar_request_pada_koneksi_yang_sama(server):
    """Handler dipakai ulang oleh keep-alive: status harus direset tiap request."""
    class Palsu(web.Penangan):
        def __init__(self):  # tanpa socket
            self.path = "/guru"
            self._status_metrik = 404
    p = Palsu()
    p._rute_get = lambda: None          # tidak mengirim respons apa pun
    p.do_GET()
    r = M.METRIK.ringkasan()["rute"]["GET /guru"]
    assert sum(r["status"].values()) == 0   # 404 lama tidak ikut terhitung


# --- serve.py: pencetak berkala --------------------------------------------------------

def test_pemeliharaan_admin_memulai_dan_menghentikan_pencetak(tmp_path, monkeypatch):
    import admin_maintenance
    import serve
    monkeypatch.setattr(admin_maintenance, "jalankan", lambda *a, **k: None)
    panggilan = []
    monkeypatch.setattr(serve.metrik_runtime, "mulai_pencetak", lambda: panggilan.append("mulai"))
    monkeypatch.setattr(serve.metrik_runtime, "hentikan_pencetak", lambda: panggilan.append("henti"))
    p = serve.PemeliharaanAdmin(tmp_path / "a.db", tmp_path / "t.db")
    p.mulai()
    p.tutup()
    assert panggilan == ["mulai", "henti"]


def test_mulai_pencetak_idempoten_dan_berhenti_bersih():
    M.mulai_pencetak(interval=0.01, tulis=lambda b: None)
    M.mulai_pencetak(interval=0.01, tulis=lambda b: None)   # kedua kali: tidak ganda
    M.hentikan_pencetak()
    M.hentikan_pencetak()                                   # aman dipanggil ulang

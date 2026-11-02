"""Banner offline berhash CSP: hanya event, tanpa IO; hash cocok di tiap shell."""

from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth
import database
import offline_browser as O
from http_test_kit import SANDI_GURU, ServerUji


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("admin-offline", "sandi-admin-offline-123", "admin")
    with s.buka() as kon:
        s.anak = database.tambah_siswa(kon, "Anak Offline", "P3", pemilik="guru")
    try:
        yield s
    finally:
        s.berhenti()


def _skrip(isi: str):
    return re.findall(r"<script>(.*?)</script>", isi, re.S)


def test_skrip_hanya_event_dan_tanpa_io():
    for terlarang in (
        "fetch(", "XMLHttpRequest", "localStorage", "sessionStorage",
        "setTimeout", "setInterval", "sendBeacon", "WebSocket",
    ):
        assert terlarang not in O.SKRIP_OFFLINE
    assert "addEventListener('offline'" in O.SKRIP_OFFLINE
    assert "addEventListener('online'" in O.SKRIP_OFFLINE
    assert "banner.hidden = true" in O.SKRIP_OFFLINE
    assert O.PESAN_OFFLINE in O.SKRIP_OFFLINE
    assert O.PESAN_ONLINE in O.SKRIP_OFFLINE


def test_hash_offline_cocok_dengan_skrip():
    assert O.HASH_OFFLINE == base64.b64encode(
        hashlib.sha256(O.SKRIP_OFFLINE.encode("utf-8")).digest()
    ).decode("ascii")


def test_daftar_dan_masuk_memuat_banner_tanpa_csp_publik(server):
    for jalur in ("/daftar", "/masuk"):
        kode, isi, header = server.minta(jalur)
        assert kode == 200
        assert O.SKRIP_OFFLINE in _skrip(isi)
        assert ".banner-offline-st {" in isi
        assert "Content-Security-Policy" not in header


def test_guru_csp_mengizinkan_offline_dan_catatan_sinyal(server):
    kode, isi, header = server.minta("/guru", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert _skrip(isi).count(O.SKRIP_OFFLINE) == 1
    assert "'sha256-" + O.HASH_OFFLINE + "'" in header["Content-Security-Policy"]
    assert O.CATATAN_SINYAL in isi


def test_akun_hash_gabungan_mencakup_offline(server):
    kode, isi, header = server.minta("/akun", auth=("guru", SANDI_GURU))
    assert kode == 200
    skrip = _skrip(isi)
    assert len(skrip) == 1 and O.SKRIP_OFFLINE in skrip[0]
    digest = base64.b64encode(
        hashlib.sha256(skrip[0].encode()).digest()
    ).decode("ascii")
    assert "script-src 'sha256-" + digest + "'" in header["Content-Security-Policy"]


def test_halaman_anak_privat_memuat_offline_dan_hashnya(server):
    kode, isi, header = server.minta(
        f"/anak/{server.anak}", auth=("guru", SANDI_GURU)
    )
    assert kode == 200
    assert O.SKRIP_OFFLINE in _skrip(isi)
    assert "'sha256-" + O.HASH_OFFLINE + "'" in header["Content-Security-Policy"]

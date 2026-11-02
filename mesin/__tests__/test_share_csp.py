"""CSP halaman bearer `/mulai/<token>`: skrip inline berhash, tanpa unsafe-inline."""
from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import share_links  # noqa: E402
import web  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

POLA_SKRIP = re.compile(rb"<script>(.*?)</script>", re.S)


def _hash(isi: bytes) -> str:
    return base64.b64encode(hashlib.sha256(isi).digest()).decode("ascii")


def _direktif(csp: str) -> dict[str, list[str]]:
    return {
        bagian.split()[0]: bagian.split()[1:]
        for bagian in csp.split(";")
        if bagian.strip()
    }


def test_csp_tautan_hash_setiap_skrip_inline():
    isi = (
        b"<html><body><script>var a=1;</script>"
        b"<script>var b=2;</script></body></html>"
    )
    direktif = _direktif(web.csp_tautan(isi))
    assert direktif["script-src"] == [
        "'sha256-" + _hash(b"var a=1;") + "'",
        "'sha256-" + _hash(b"var b=2;") + "'",
    ]
    assert "'unsafe-inline'" not in direktif["script-src"]
    assert direktif["default-src"] == ["'none'"]
    assert direktif["connect-src"] == ["'self'"]
    assert direktif["frame-ancestors"] == ["'none'"]
    assert direktif["base-uri"] == ["'none'"]


def test_csp_tautan_tanpa_skrip_mengunci_script_src():
    direktif = _direktif(web.csp_tautan(b"<html><body>tanpa skrip</body></html>"))
    assert direktif["script-src"] == ["'none'"]


def test_csp_tautan_tidak_mengizinkan_skrip_beratribut():
    """Skrip dengan atribut tidak dihash: fail-closed, bukan diizinkan diam-diam."""
    direktif = _direktif(web.csp_tautan(b'<script type="module">x()</script>'))
    assert direktif["script-src"] == ["'none'"]


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


def test_halaman_mulai_memakai_csp_berhash(server):
    with server.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Tautan CSP", "P3", pemilik="guru")
        sesi = database.buat_sesi(kon, anak, seed=7, jumlah_soal=1)
        token = share_links.buat(kon, sesi)

    kode, isi, tajuk = server.minta(f"/mulai/{token}", biner=True)
    assert kode == 200
    csp = tajuk["Content-Security-Policy"]
    direktif = _direktif(csp)
    skrip = POLA_SKRIP.findall(isi)
    assert skrip, "halaman mulai wajib memuat skrip timer/penjaga"
    harap = ["'sha256-" + _hash(badan) + "'" for badan in skrip]
    assert sorted(direktif["script-src"]) == sorted(harap)
    assert "'unsafe-inline'" not in direktif["script-src"]
    assert direktif["frame-ancestors"] == ["'none'"]
    assert direktif["form-action"] == ["'self'"]
    assert direktif["connect-src"] == ["'self'"]
    assert tajuk["Referrer-Policy"] == "no-referrer"
    assert tajuk["X-Frame-Options"] == "DENY"

"""CSP berhash untuk semua rute funnel publik. Hash dihitung dari body aktual (generik).

Tidak memakai jumlah skrip tetap: halaman lain (mis. `/cek-kemampuan`) boleh menambah skrip,
selama setiap `<script>` polos di body punya hash yang cocok di header.
"""
from __future__ import annotations

import base64
import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from http_test_kit import ServerUji  # noqa: E402

RUTE = ("/cek-kemampuan", "/paket-coba", "/contoh-peta-kemampuan", "/contoh-peta-kemampuan/lembar")
POLA_SKRIP = re.compile(rb"<script>(.*?)</script>", re.S)
POLA_SKRIP_BERATRIBUT = re.compile(rb"<script\s[^>]*>", re.I)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("FUNNEL_AKTIF", raising=False)
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        yield uji
    finally:
        uji.berhenti()


def _hash(badan: bytes) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(badan).digest()).decode("ascii") + "'"


def _direktif(csp: str) -> dict:
    hasil = {}
    for bagian in csp.split(";"):
        potong = bagian.split()
        if potong:
            hasil[potong[0]] = potong[1:]
    return hasil


@pytest.mark.parametrize("jalur", RUTE)
def test_header_csp_cocok_dengan_skrip_di_body(server, monkeypatch, jalur):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    kode, isi, tajuk = server.minta(jalur, biner=True)
    assert kode == 200
    direktif = _direktif(tajuk["Content-Security-Policy"])
    skrip = POLA_SKRIP.findall(isi)
    assert skrip, "kerangka halaman publik selalu membawa skrip"
    assert not POLA_SKRIP_BERATRIBUT.search(isi), "skrip beratribut tidak akan di-hash"
    assert sorted(set(direktif["script-src"])) == sorted({_hash(b) for b in skrip})
    assert "'unsafe-inline'" not in direktif["script-src"] and "'unsafe-eval'" not in direktif["script-src"]


@pytest.mark.parametrize("jalur", RUTE)
def test_direktif_lain_membatasi_halaman(server, monkeypatch, jalur):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _kode, _isi, tajuk = server.minta(jalur, biner=True)
    direktif = _direktif(tajuk["Content-Security-Policy"])
    assert direktif["default-src"] == ["'none'"]
    assert direktif["img-src"] == ["'self'", "data:"]
    assert direktif["style-src"] == ["'unsafe-inline'"] and direktif["font-src"] == ["'self'"]
    assert direktif["frame-ancestors"] == ["'none'"] and direktif["base-uri"] == ["'none'"]
    assert direktif["form-action"] == ["'self'"] and direktif["connect-src"] == ["'self'"]


@pytest.mark.parametrize("jalur", RUTE)
def test_sakelar_mati_tetap_membawa_csp_berhash(server, jalur):
    kode, isi, tajuk = server.minta(jalur, biner=True)
    assert kode == 200 and b"belum dibuka" in isi.lower()
    skrip = POLA_SKRIP.findall(isi)
    assert sorted(set(_direktif(tajuk["Content-Security-Policy"])["script-src"])) == sorted({_hash(b) for b in skrip})


def test_skrip_laporan_dan_cetak_ikut_ter_hash(server, monkeypatch):
    import peta_browser

    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _k, _i, laporan = server.minta("/contoh-peta-kemampuan", biner=True)
    _k, _i, lembar = server.minta("/contoh-peta-kemampuan/lembar", biner=True)
    assert _hash(peta_browser.SKRIP_PETA.encode()) in laporan["Content-Security-Policy"]
    assert _hash(peta_browser.SKRIP_CETAK.encode()) in lembar["Content-Security-Policy"]
    assert _hash(peta_browser.SKRIP_PETA.encode()) not in lembar["Content-Security-Policy"]


def test_skrip_peta_tanpa_atribut_dan_statis():
    import peta_browser

    for skrip in (peta_browser.SKRIP_PETA, peta_browser.SKRIP_CETAK):
        assert "</script" not in skrip.lower()
        assert "%(" not in skrip and "{{" not in skrip


def test_rute_lain_tidak_berubah_tanpa_csp_funnel(server):
    kode, _isi, tajuk = server.minta("/masuk", biner=True)
    assert kode == 200
    # Halaman kredensial tetap dengan CSP-nya sendiri, bukan buatan helper funnel.
    assert "Content-Security-Policy" in tajuk
    kode, _isi, tajuk = server.minta("/aset/favicon.svg", biner=True)
    assert kode == 200 and "Content-Security-Policy" not in tajuk

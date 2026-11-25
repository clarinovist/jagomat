"""Pembantu bersama tes surel: transport palsu dan isolasi jaringan serta environment.

`isolasi_surel` memasang `urllib.request.urlopen` dan `OpenerDirector.open` agar melempar `LarangJaringan`,
sehingga koneksi nyata membuat tes merah dan tidak diam-diam. Variabel env surel juga dikosongkan supaya
kunci milik mesin pengembang tidak terbaca. Semua nilai di sini sintetis.
"""
import urllib.request

import pytest

ALAMAT_SINTETIS_ADMIN = "admin@contoh.test"
KUNCI_SINTETIS = "re_kunci_tes_sintetis"
ENV_SUREL = ("RESEND_API_KEY", "SUREL_PENGIRIM", "SUREL_ADMIN")


class LarangJaringan(RuntimeError):
    """Galat yang sengaja tidak ditangkap modul surel: tes yang membuka jaringan harus merah."""


def _larang(*_args, **_kwargs):
    raise LarangJaringan("tes surel dilarang membuka jaringan")


class TransportPalsu:
    """Transport `(url, headers, badan, timeout) -> (kode, badan)` yang merekam setiap panggilan."""

    def __init__(self, kode=200, badan=b'{"id":"email_tes_1"}', galat=None):
        self._kode = kode
        self._badan = badan
        self._galat = galat
        self.panggilan = []

    def __call__(self, url, headers, badan, timeout):
        self.panggilan.append({"url": url, "headers": dict(headers), "badan": badan, "timeout": timeout})
        if self._galat is not None:
            raise self._galat
        return self._kode, self._badan


@pytest.fixture
def isolasi_surel(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _larang)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _larang)
    for nama in ENV_SUREL:
        monkeypatch.delenv(nama, raising=False)

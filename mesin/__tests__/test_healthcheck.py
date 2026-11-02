"""Perilaku healthcheck container: 401 sehat, 200 palang jebol, mati sakit.

Kontrak yang dijaga (lihat docstring `mesin/healthcheck.py` dan komentar
HEALTHCHECK di `mesin/Dockerfile`):

  - 401 di rute data guru = server hidup DAN palang sandi aktif → exit 0;
  - 200 di rute yang sama = palang jebol, data anak bisa dibaca siapa saja
    → exit bukan 0, supaya deploy/rollback otomatis menolak image itu;
  - tidak menjawab (koneksi ditolak/timeout) = proses mati → exit bukan 0.

Test ini mengeksekusi `main()` sungguhan tanpa jaringan dan tanpa data anak:
`urllib.request.urlopen` dipalsukan per kasus, lalu dikembalikan monkeypatch.
"""
import importlib.util
from pathlib import Path
import urllib.error

import pytest


AKAR = Path(__file__).resolve().parents[2]
SPEK = importlib.util.spec_from_file_location(
    "healthcheck_uji", AKAR / "mesin/healthcheck.py",
)
healthcheck = importlib.util.module_from_spec(SPEK)
SPEK.loader.exec_module(healthcheck)


class _Jawaban:
    """Respons minimal mirip `http.client.HTTPResponse` sebagai context manager."""

    def __init__(self, kode):
        self.status = kode

    def __enter__(self):
        return self

    def __exit__(self, *info):
        return False


def _palsukan(monkeypatch, urlopen):
    """Ganti urlopen pada modul healthcheck saja, tanpa menyentuh jaringan."""
    monkeypatch.setattr(healthcheck.urllib.request, "urlopen", urlopen)


def test_401_dihitung_sehat(monkeypatch):
    """Tanpa kredensial rute data guru wajib 401; itu bukti hidup + palang aktif."""
    def urlopen(url, timeout):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

    _palsukan(monkeypatch, urlopen)
    assert healthcheck.main() == 0


def test_200_berarti_palang_jebol_dan_sakit(monkeypatch, capsys):
    """Berkas sandi hilang dari volume: aplikasi tetap jalan tapi rute data
    terbuka. Healthcheck harus gagal, bukan melaporkan sehat."""
    _palsukan(monkeypatch, lambda url, timeout: _Jawaban(200))
    assert healthcheck.main() != 0
    assert "palang tidak aktif" in capsys.readouterr().err


@pytest.mark.parametrize("galat", [
    urllib.error.URLError("koneksi ditolak"),
    ConnectionResetError("proses mati"),
    TimeoutError("timeout"),
])
def test_koneksi_gagal_dihitung_sakit(monkeypatch, capsys, galat):
    def urlopen(url, timeout):
        raise galat

    _palsukan(monkeypatch, urlopen)
    assert healthcheck.main() != 0
    assert "tidak menjawab" in capsys.readouterr().err

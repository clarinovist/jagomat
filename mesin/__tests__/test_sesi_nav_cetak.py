"""Navigasi alat sesi guru: pil Cetak harus terlihat di setiap tab sesi."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="guru")
        sesi = database.buat_sesi(kon, anak, seed=17, jumlah_soal=1)
    yield s, sesi
    s.berhenti()


def _pil(isi: str) -> str:
    cocok = re.search(r'<nav class="pil-sesi-st".*?</nav>', isi, re.S)
    assert cocok, "pil navigasi sesi tidak ada"
    return cocok.group(0)


def _tautan_pil(pil: str) -> list[tuple[str, str]]:
    return re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', pil)


@pytest.mark.parametrize("sufiks", ["", "/cetak", "/lampiran"])
def test_pil_cetak_tampil_di_semua_tab_sesi(server, sufiks):
    s, sesi = server
    kode, isi, _ = s.minta(f"/sesi/{sesi}{sufiks}", auth=("guru", SANDI_GURU))
    assert kode == 200
    tautan = _tautan_pil(_pil(isi))
    assert (f"/sesi/{sesi}/cetak", "Cetak") in tautan


def test_pil_cetak_aktif_hanya_di_halaman_cetak(server):
    s, sesi = server
    _, isi_cetak, _ = s.minta(f"/sesi/{sesi}/cetak", auth=("guru", SANDI_GURU))
    _, isi_koreksi, _ = s.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    aktif_cetak = re.search(
        r'<a [^>]*href="/sesi/\d+/cetak"[^>]*>', _pil(isi_cetak)
    ).group(0)
    aktif_koreksi = re.search(
        r'<a [^>]*href="/sesi/\d+/cetak"[^>]*>', _pil(isi_koreksi)
    ).group(0)
    assert 'aria-current="page"' in aktif_cetak
    assert 'aria-current="page"' not in aktif_koreksi


def test_urutan_pil_koreksi_cetak_lampiran(server):
    s, sesi = server
    _, isi, _ = s.minta(f"/sesi/{sesi}", auth=("guru", SANDI_GURU))
    jalur = [h for h, _ in _tautan_pil(_pil(isi))]
    assert jalur == [
        f"/sesi/{sesi}",
        f"/sesi/{sesi}/cetak",
        f"/sesi/{sesi}/lampiran",
    ]

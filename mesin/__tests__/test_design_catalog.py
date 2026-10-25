"""Katalog design system: luring, tanpa skrip, dan contoh tetap memakai kelas CSS nyata."""
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import re

import pytest

import design_roles as R

SKRIP = Path(__file__).resolve().parents[2] / "scripts" / "design_catalog.py"


@pytest.fixture(scope="module")
def katalog():
    spec = importlib.util.spec_from_file_location("katalog_desain_uji", SKRIP)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class _Kelas(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.kelas, self.iframe = set(), []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.kelas.update((a.get("class") or "").split())
        if tag == "iframe":
            self.iframe.append(a)


def test_ekspor_menulis_index_dan_tidak_menimpa(katalog, tmp_path):
    folder = tmp_path / "katalog"
    berkas = katalog.ekspor(folder)
    assert berkas == folder / "index.html" and berkas.stat().st_size > 0
    awal = berkas.read_bytes()
    with pytest.raises(FileExistsError):
        katalog.ekspor(folder)
    assert berkas.read_bytes() == awal


def test_katalog_luring_tanpa_skrip_dan_jaringan(katalog):
    isi = katalog.bangun_html()
    assert "<script" not in isi.lower()
    assert not re.search(r"https?://|@import\s+(?:url|[\"'])", isi)
    parser = _Kelas(isi)
    assert len(parser.iframe) == len(katalog.demo())
    for frame in parser.iframe:
        assert "sandbox" in frame and frame["srcdoc"].startswith("<!doctype html>")
        assert "<script" not in frame["srcdoc"].lower()


def test_setiap_pasangan_peran_dan_status_kontras_tampil(katalog):
    isi = katalog.bangun_html()
    for nama, daftar in R.PERMUKAAN.items():
        assert f"<h3>{nama}</h3>" in isi
        for p in daftar:
            assert katalog._e(p.depan.selektor) in isi
    assert "GAGAL<" not in isi, "kegagalan kontras tak tercatat tampil di katalog"


def test_kelas_contoh_ada_di_css_permukaannya(katalog):
    """Contoh yang memakai kelas tanpa aturan CSS berarti katalog sudah basi (semua demo)."""
    hilang = {}
    for demo in katalog.demo():
        kelas = sorted(k for k in _Kelas(demo.isi).kelas
                       if not re.search(r"\." + re.escape(k) + r"(?![\w-])", demo.css))
        if kelas:
            hilang[demo.judul] = kelas
    assert katalog.demo() and not hilang, hilang


def test_ekspor_gagal_tidak_meninggalkan_folder(katalog, tmp_path, monkeypatch):
    def rusak():
        raise ValueError("render gagal")
    monkeypatch.setattr(katalog, "bangun_html", rusak)
    with pytest.raises(ValueError):
        katalog.ekspor(tmp_path / "katalog")
    assert not (tmp_path / "katalog").exists()


def test_katalog_membuang_webfont(katalog):
    assert katalog.tanpa_webfont("@import url('https://fonts.googleapis.com/x');a{}") == "a{}"

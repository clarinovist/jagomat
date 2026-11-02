"""Kontrak UI masuk editorial, tanpa mengubah autentikasi atau sesi."""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import design_tokens as T
import sessions
import web
from http_test_kit import ServerUji
from landing import halaman_daftar
from style_stitch import GAYA_STITCH
from teacher_style import SKRIP_MATA_SANDI


class _Markup(HTMLParser):
    """Baca atribut dan label tanpa bergantung urutan atribut HTML."""

    def __init__(self, sumber):
        super().__init__()
        self.elemen = []
        self.feed(sumber)

    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))

    def cari(self, tag):
        return [atribut for nama, atribut in self.elemen if nama == tag]


def _halaman(galat=""):
    return web.Penangan._halaman_masuk_stitch(None, galat).decode()


def _aturan(selector):
    cocok = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", GAYA_STITCH)
    assert cocok, "Aturan khusus login belum tersedia: " + selector
    return cocok.group(1)


def _kontras(teks, latar):
    def luminansi(warna):
        warna = warna.lstrip("#")
        if len(warna) == 3:
            warna = "".join(h * 2 for h in warna)
        rgb = [int(warna[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * bobot for c, bobot in zip(linear, (.2126, .7152, .0722)))

    terang, gelap = sorted((luminansi(teks), luminansi(latar)), reverse=True)
    return (terang + .05) / (gelap + .05)


def test_logo_satu_pintu_beranda_dan_lupa_sandi_tetap():
    markup = _Markup(_halaman())
    tautan = markup.cari("a")
    assert [a["href"] for a in tautan] == ["/", "/lupa-sandi"]
    assert tautan[0]["class"] == "masuk-brand-st"
    assert "beranda" in tautan[0]["aria-label"]
    assert T.NAMA_PRODUK in tautan[0]["aria-label"]


def test_main_heading_dan_label_pengguna_jelas():
    h = _halaman()
    markup = _Markup(h)
    assert len(markup.cari("main")) == len(markup.cari("h1")) == 1
    assert markup.cari("main")[0]["aria-labelledby"] == markup.cari("h1")[0]["id"]
    assert "Selamat datang kembali" in h
    assert '<label for="nama">Nama pengguna</label>' in h
    nama = next(e for e in markup.cari("input") if e.get("name") == "nama")
    assert nama["aria-describedby"] == "petunjuk-nama"
    assert 'id="petunjuk-nama"' in h
    assert "akun dari orang tua atau guru" in h


@pytest.mark.parametrize("galat", ["", "Nama atau sandi belum cocok.", "Terlalu banyak percobaan. Coba lagi 15 menit lagi."])
def test_kontrak_form_dan_skrip_mata_tidak_berubah(galat):
    h = _halaman(galat)
    markup = _Markup(h)
    formulir = markup.cari("form")
    assert len(formulir) == 1
    assert formulir[0]["method"] == "post"
    assert formulir[0]["action"] == "/masuk"
    assert "novalidate" not in formulir[0]
    kolom = markup.cari("input")
    assert len(kolom) == 2
    for e, nama, tipe, pelengkap in zip(kolom, ("nama", "sandi"), ("text", "password"), ("username", "current-password")):
        assert e["name"] == e["id"] == nama
        assert e["type"] == tipe
        assert e["autocomplete"] == pelengkap
        assert "required" in e
        assert "autofocus" not in e
        assert "value" not in e
    assert len(markup.cari("button")) == 1  # Mata ditambahkan skrip existing.
    assert markup.cari("button")[0]["type"] == "submit"
    from offline_browser import SKRIP_OFFLINE
    assert re.findall(r"<script>(.*?)</script>", h, re.S) == [
        SKRIP_MATA_SANDI, SKRIP_OFFLINE]


def test_galat_punya_semantik_dan_relasi_ke_form():
    markup = _Markup(_halaman("Nama atau sandi belum cocok."))
    galat = next(e for _, e in markup.elemen if e.get("class") == "masuk-galat-st")
    assert galat["role"] == "alert"
    assert galat["aria-atomic"] == "true"
    assert galat["id"] == markup.cari("form")[0]["aria-describedby"]
    assert not any("aria-invalid" in e for e in markup.cari("input"))
    normal = _Markup(_halaman())
    assert "aria-describedby" not in normal.cari("form")[0]
    assert not any(e.get("role") == "alert" for _, e in normal.elemen)


def test_galat_tetap_teks_bukan_markup():
    """Escaping existing dipertahankan saat membungkus pesan untuk aksesibilitas."""
    h = _halaman('<b data-contoh="galat">Contoh & pesan</b>')
    assert '&lt;b data-contoh=&quot;galat&quot;&gt;Contoh &amp; pesan&lt;/b&gt;' in h
    assert not any("data-contoh" in e for _, e in _Markup(h).elemen)


def test_maskot_lokal_dekoratif_dan_ukurannya_tetap():
    gambar = [e for e in _Markup(_halaman()).cari("img") if e.get("class") == "masuk-maskot-st"]
    assert len(gambar) == 1
    assert gambar[0]["src"] == "/aset/maskot-menyapa-v3-240.png"
    assert gambar[0]["alt"] == ""
    assert gambar[0]["width"] == gambar[0]["height"] == "240"


def test_kontras_tombol_dan_tautan_memenuhi_teks_kecil():
    tombol = _aturan(".masuk-badan-st .masuk-tombol-st")
    tautan = _aturan(".masuk-badan-st .masuk-link-st a")
    latar = re.search(r"background:\s*(#[0-9a-fA-F]+)", tombol).group(1)
    teks = re.search(r"(?<!-)color:\s*(#[0-9a-fA-F]+)", tombol).group(1)
    warna_tautan = re.search(r"(?<!-)color:\s*(#[0-9a-fA-F]+)", tautan).group(1)
    assert _kontras(teks, latar) >= 4.5
    assert _kontras(warna_tautan, T.LATAR_KARTU) >= 4.5
    assert T.TARGET_SENTUH in tautan
    assert "filter: none" in _aturan(".masuk-badan-st .masuk-tombol-st:hover")
    assert "outline:" in _aturan(".masuk-badan-st :is(a, button, input):focus-visible")
    bantuan = _aturan(".masuk-badan-st .masuk-petunjuk-st")
    warna_bantuan = re.search(r"(?<!-)color:\s*(#[0-9a-fA-F]+)", bantuan).group(1)
    assert _kontras(warna_bantuan, T.LATAR_KARTU) >= 4.5


def test_override_form_dibatasi_ke_login():
    blok = GAYA_STITCH.split("/* ══ Form login editorial", 1)[1].split("/* ── Halaman publik", 1)[0]
    bersih = re.sub(r"/\*.*?\*/", "", "/*" + blok, flags=re.S)
    for selector in re.findall(r"([^{}]+)\{", bersih):
        if selector.strip().startswith("@media"):
            continue
        selector = re.sub(r":is\([^)]*\)", "", selector)
        assert all(s.strip().startswith(".masuk-badan-st ") for s in selector.split(","))
    # Halaman daftar tidak terjangkau oleh semua override di atas.
    assert not any("masuk-badan-st" in e.get("class", "").split()
                   for _, e in _Markup(halaman_daftar().decode()).elemen)


def test_responsif_dan_warna_dari_token():
    sumber = (Path(__file__).resolve().parent.parent / "style_stitch.py").read_text()
    kanvas = sumber.split("/* ── Halaman masuk editorial", 1)[1].split("/* Galat / error flash", 1)[0]
    override = sumber.split("/* ══ Form login editorial", 1)[1].split("/* ── Halaman publik", 1)[0]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", kanvas + override)
    assert "@media (max-width: 59.99rem), (max-height: 36rem)" in kanvas
    assert ".masuk-catatan-st {{ display: none; }}" in kanvas
    assert "minmax(0, 1fr)" in kanvas


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Server sintetis untuk memeriksa UI dari respons GET/POST sebenarnya."""
    monkeypatch.setattr(sessions, "BERKAS_SESI", tmp_path / "sesi.json")
    monkeypatch.setattr(sessions, "_jalur_dari_kunci_ip", {})
    s = ServerUji(tmp_path, monkeypatch)
    try:
        yield s
    finally:
        s.berhenti()


def test_ui_normal_dan_galat_lewat_rute_yang_sama(server):
    kode, isi, _ = server.minta("/masuk")
    assert kode == 200
    assert "Selamat datang kembali" in isi
    assert len(_Markup(isi).cari("form")) == 1
    kode, isi, _ = server.minta("/masuk", data={"nama": "guru", "sandi": "contoh-salah"})
    assert kode == 200
    assert "Nama atau sandi belum cocok." in isi
    markup = _Markup(isi)
    assert markup.cari("form")[0]["aria-describedby"] == "galat-masuk"
    assert any(e.get("role") == "alert" for _, e in markup.elemen)
    assert "contoh-salah" not in isi


def test_ui_galat_pembatasan_tetap_bisa_dibaca(server):
    for _ in range(5):
        server.minta("/masuk", data={"nama": "guru", "sandi": "contoh-salah"})
    kode, isi, _ = server.minta("/masuk", data={"nama": "guru", "sandi": "contoh-salah"})
    assert kode == 429
    assert "Terlalu banyak percobaan. Coba lagi 15 menit lagi." in isi
    assert _Markup(isi).cari("form")[0]["aria-describedby"] == "galat-masuk"
    assert 'href="/lupa-sandi"' in isi

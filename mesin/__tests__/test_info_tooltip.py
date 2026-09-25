"""Komponen Info "ⓘ": satu baris di layar, sisanya bubble (25 Sep 2026).

Keputusan pengguna: layar guru maksimal satu baris penjelasan; detail masuk
bubble ikon ⓘ yang muncul saat kursor mendekat atau saat difokus keyboard
(komponen Figma `Jagomat/Info`). Kontrak yang dijaga berkas ini:

- markup `<button class="info" aria-label>` berisi `<span class="info-bubble"
  role="tooltip">` sehingga pembaca layar tetap dapat isinya;
- CSS menampilkan bubble pada :hover, :focus-visible (keyboard), dan :focus
  (tap di perangkat sentuh yang memfokus tombol) — bukan atribut `title=`;
- bubble tidak boleh memuat data anak, angka, atau kunci;
- tidak ada JS tambahan dan tombol bukan submit.

Contoh pertama: beranda guru (/guru), kalimat disetujui 26 Sep 2026.
Contoh kedua (26 Sep 2026): tab "Buat latihan" (/anak/<id>) — catatan kaki
"Latihan bebas tidak mengubah progres rencana terpandu." pindah ke bubble.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database
import design_tokens as T
import teacher_pages
from style_stitch import GAYA_STITCH
from teacher_style import SKRIP_CEGAH_KIRIM_GANDA, SKRIP_MATA_SANDI

TEKS_DISETUJUI = (
    "Setiap anak punya halaman sendiri: buat latihan, rencana belajar, "
    "dan riwayat."
)

TEKS_LATIHAN = "Latihan bebas tidak mengubah progres rencana terpandu."


class _BacaInfo(HTMLParser):
    """Kumpulkan tiap tombol .info beserta teks bubble-nya."""

    def __init__(self, sumber: str):
        super().__init__()
        self.tombol = []          # list[(atribut_tombol, isi_bubble)]
        self._atribut = None
        self._isi = None
        self.feed(sumber)

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        if tag == "button" and "info" in (atribut.get("class") or "").split():
            self._atribut, self._isi = atribut, None
        elif (tag == "span" and self._atribut is not None
              and atribut.get("role") == "tooltip"):
            self._isi = ""

    def handle_data(self, data):
        if self._atribut is not None and self._isi is not None:
            self._isi += data

    def handle_endtag(self, tag):
        if tag == "button" and self._atribut is not None:
            self.tombol.append((self._atribut, self._isi))
            self._atribut, self._isi = None, None


def _isi_rule(penanda: str) -> str:
    """Body rule GAYA_STITCH pertama yang selector-nya memuat penanda."""
    for cocok in re.finditer(r"([^{}]+)\{([^{}]*)\}", GAYA_STITCH):
        if penanda in cocok.group(1):
            return cocok.group(2)
    return ""


def _kontras(teks: str, latar: str) -> float:
    def luminansi(warna):
        nilai = warna.lstrip("#")
        rgb = [int(nilai[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                  for c in rgb]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))

    terang, gelap = sorted((luminansi(teks), luminansi(latar)), reverse=True)
    return (terang + .05) / (gelap + .05)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _dashboard(db) -> str:
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "AnakSintetis", pemilik="ortu", tingkat="P5")
        database.tambah_siswa(kon, "AnakSintetisDua", pemilik="ortu", tingkat="P3")
        database.buat_sesi(kon, a, seed=11, topik="statistika")
        return teacher_pages.halaman_utama_stitch(
            kon, pemilik="ortu", peran="guru"
        ).decode()


def _profil_latihan(db) -> str:
    """Render tab "Buat latihan" (/anak/<id>) — layar padat teks kedua."""
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "AnakSintetis", pemilik="ortu", tingkat="P5")
        baris = kon.execute("SELECT * FROM siswa WHERE id = ?", (a,)).fetchone()
        return teacher_pages.halaman_anak(
            kon, baris, peran="guru", pengguna="ortu"
        ).decode()


def test_petunjuk_satu_baris_plus_tombol_info(db):
    h = _dashboard(db)
    assert "Pilih nama untuk mulai." in h
    # Kalimat lama pindah ke bubble — tidak lagi memadati layar.
    assert "membuka rencana belajar dan riwayat sesi" not in h
    tombol = _BacaInfo(h).tombol
    assert len(tombol) == 1
    atribut, isi = tombol[0]
    assert atribut["type"] == "button"                      # bukan submit
    assert atribut.get("aria-label") == TEKS_DISETUJUI      # pembaca layar dapat isinya
    assert isi == TEKS_DISETUJUI                            # isi bubble
    assert "title" not in atribut                           # bukan andalan title=


def test_css_menampilkan_bubble_saat_hover_dan_fokus():
    dasar = _isi_rule(".info-bubble")
    assert dasar, "aturan dasar .info-bubble hilang"
    assert "hidden" in dasar and "opacity: 0" in dasar      # sembunyi sebelum dibuka
    assert T.LATAR_TOOLTIP in dasar and T.TEKS_TOOLTIP in dasar
    assert T.RADIUS_KARTU in dasar
    assert f"max-width: min({T.LEBAR_TOOLTIP}" in dasar

    assert "visible" in _isi_rule(".info:hover .info-bubble")
    assert "visible" in _isi_rule(".info:focus-visible .info-bubble")
    # :focus menutup tap di HP yang memfokus tombol tanpa :focus-visible.
    assert "visible" in _isi_rule(".info:focus .info-bubble")

    assert T.TARGET_INFO in _isi_rule(".info ")              # kotak sentuh 26x26
    assert T.UKURAN_INFO in _isi_rule(".info::before")       # lingkaran ikon 18px
    assert _kontras(T.TEKS_TOOLTIP, T.LATAR_TOOLTIP) >= 4.5


def test_css_kotak_sentuh_tidak_dilarkan_aturan_permukaan():
    """Permukaan punya min-height 48px untuk `button`; ⓘ wajib tetap 26x26."""
    for selector in (".pendamping-editorial-st .info:is(button)",
                     ".profil-formulaire-st .info:is(button)"):
        isi = _isi_rule(selector)
        assert isi, "exemption kotak sentuh hilang: " + selector
        assert "min-height: 0" in isi


def test_bubble_tanpa_data_anak_atau_kunci(db):
    h = _dashboard(db)
    nama = set(re.findall(r"AnakSintetis\w*", h))
    assert nama == {"AnakSintetis", "AnakSintetisDua"}       # fixture benar-benar tampil
    tombol = _BacaInfo(h).tombol
    assert tombol
    for _, isi in tombol:
        assert isi == TEKS_DISETUJUI                        # teks statis, bukan dinamis
        assert not re.search(r"\d", isi)                    # tanpa angka (id/jumlah)
        for n in nama:
            assert n not in isi
        assert "kunci" not in isi.lower()
        assert "malrule" not in isi.lower()


def test_tanpa_js_tambahan(db):
    h = _dashboard(db)
    assert re.findall(r"<script>(.*?)</script>", h, re.S) == [
        SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA,
    ]
    assert not re.search(r"\son(?:click|focus|mouseenter|mousemove|mouseover)\s*=", h)
    assert "data-tooltip" not in h


# ── Layar kedua: tab "Buat latihan" (/anak/<id>) ─────────────────────────


def test_buat_latihan_catatan_kaki_pindah_ke_bubble(db):
    h = _profil_latihan(db)
    assert "Pilih materi dan bentuk latihan." in h
    # Paragraf catatan kaki tidak lagi berdiri sendiri di layar.
    assert ('<p class="sub">Latihan bebas tidak mengubah progres rencana terpandu.</p>'
            not in h)
    tombol = _BacaInfo(h).tombol
    assert len(tombol) == 1
    atribut, isi = tombol[0]
    assert atribut["type"] == "button"
    assert atribut.get("aria-label") == TEKS_LATIHAN
    assert isi == TEKS_LATIHAN            # pindah apa adanya, tanpa makna baru
    assert "title" not in atribut         # bukan andalan title= (HP)


def test_buat_latihan_bubble_tanpa_data_anak_atau_kunci(db):
    h = _profil_latihan(db)
    nama = set(re.findall(r"AnakSintetis\w*", h))
    assert nama                            # fixture benar-benar tampil
    tombol = _BacaInfo(h).tombol
    assert tombol
    for _, isi in tombol:
        assert isi == TEKS_LATIHAN         # teks statis, bukan dinamis
        assert not re.search(r"\d", isi)   # tanpa angka (id/jumlah)
        for n in nama:
            assert n not in isi
        assert "kunci" not in isi.lower()
        assert "malrule" not in isi.lower()


def test_buat_latihan_tanpa_js_tambahan(db):
    h = _profil_latihan(db)
    skrip = re.findall(r"<script>(.*?)</script>", h, re.S)
    assert len(skrip) == 3                 # skrip bagikan + dua skrip global lama
    assert "bagikan" in skrip[0]
    assert skrip[1] == SKRIP_MATA_SANDI
    assert skrip[2] == SKRIP_CEGAH_KIRIM_GANDA
    for s in skrip:
        assert "info-bubble" not in s and ".info" not in s
    assert not re.search(r"\son(?:click|focus|mouseenter|mousemove|mouseover)\s*=", h)

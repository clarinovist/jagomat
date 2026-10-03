"""Toggle mata sandi harus sampai ke SEMUA permukaan Stitch.

Dua cacat nyata yang dijaga di sini (4 Sep 2026):

1. `/masuk` merakit shell HTML-nya sendiri (`web._halaman_masuk_stitch`),
   tidak lewat `teacher_pages._halaman`, jadi SKRIP_MATA_SANDI tidak
   pernah ikut — kolom sandi login tanpa tombol mata sama sekali.
2. Halaman publik (`/daftar`) memuat skripnya, tapi CSS `.kolom-sandi` /
   `.tombol-mata` hanya hidup di GAYA_GURU yang tidak dimuat di sana —
   tombolnya lahir tanpa posisi absolut, nongol di bawah kolom.

Assertion sengaja pada MARKER (nama kelas + potongan skrip), bukan pada
nilai sandi apa pun.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import landing  # noqa: E402
import style_stitch  # noqa: E402
import web  # noqa: E402


class _Kosong:
    """Stand-in instance: _halaman_masuk_stitch murni render, tanpa self."""


# Marker yang HANYA ada di SKRIP_MATA_SANDI, bukan di CSS. Dua kali lulus
# palsu saat mutation testing: "tombol-mata" kini juga nama kelas di
# GAYA_STITCH, dan "input[type=password]" muncul di komentar CSS-nya.
# Identifier JS internal aman — ia tak punya alasan muncul di prosa CSS.
MARKER_SKRIP = "ikonSembunyi"


def _html_masuk(galat: str = "") -> str:
    return web.Penangan._halaman_masuk_stitch(_Kosong(), galat).decode()


def test_masuk_memuat_skrip_mata_sandi():
    h = _html_masuk()
    assert 'type="password"' in h, "prasyarat: /masuk punya kolom sandi"
    assert "tombol-mata" in h, "/masuk tanpa skrip mata sandi"
    assert MARKER_SKRIP in h, "/masuk tanpa skrip mata sandi (CSS saja tidak cukup)"
    assert "Tampilkan sandi" in h


def test_masuk_memuat_css_kolom_sandi():
    """Skrip tanpa CSS = tombol telanjang di bawah kolom, bukan di dalamnya.

    Assert pada SELEKTOR (`.kolom-sandi {`), bukan pada string telanjang:
    skrip JS-nya sendiri memuat 'kolom-sandi' sebagai nilai className, jadi
    `".kolom-sandi" in h` lulus palsu meski CSS-nya tidak ada.
    """
    h = _html_masuk()
    assert ".kolom-sandi {" in h
    assert ".tombol-mata {" in h


def test_masuk_galat_tetap_punya_mata():
    """Jalur gagal login juga dirender ulang — jangan sampai kehilangan."""
    h = _html_masuk("Nama atau sandi belum cocok.")
    assert MARKER_SKRIP in h
    assert "masuk-galat-st" in h


def test_daftar_punya_skrip_dan_css_mata():
    h = landing.halaman_daftar().decode()
    assert 'type="password"' in h
    assert MARKER_SKRIP in h
    assert ".kolom-sandi {" in h, "/daftar memuat skrip tapi CSS-nya tidak ikut"


def test_marker_skrip_tidak_ada_di_css():
    """Meta-guard. Marker yang bocor ke CSS membuat SEMUA test di berkas ini
    lulus palsu — sudah kejadian dua kali. Kunci invariannya di sini."""
    import teacher_style

    assert MARKER_SKRIP in teacher_style.SKRIP_MATA_SANDI
    assert MARKER_SKRIP not in style_stitch.GAYA_STITCH
    assert MARKER_SKRIP not in teacher_style.GAYA_GURU


def test_css_mata_ada_di_gaya_stitch():
    """Sumbernya harus GAYA_STITCH supaya semua permukaan Stitch dapat."""
    css = style_stitch.GAYA_STITCH
    assert ".kolom-sandi {" in css
    assert ".tombol-mata {" in css


def test_tombol_mata_tidak_menutup_border_input():
    """Regresi: latar opak .tombol-mata memotong garis border input sandi
    di halaman ber-wrap pendamping-editorial-st — garisnya hilang di
    sebelah mata. Tombolnya lebih tinggi dari input, jadi latarnya harus
    transparan."""
    css = style_stitch.GAYA_STITCH
    aturan = re.search(r'\.pendamping-editorial-st \.tombol-mata \{([^}]*)\}', css)
    assert aturan, "aturan khusus .tombol-mata di scope pendamping hilang"
    assert 'background: none' in aturan.group(1)
    gabungan = re.search(
        r'\.pendamping-editorial-st :is\(\.tombol-ikon-st, \.tombol-mata\) \{([^}]*)\}',
        css,
    )
    assert gabungan, "aturan gabungan .tombol-ikon-st/.tombol-mata hilang"
    assert 'background' not in gabungan.group(1)

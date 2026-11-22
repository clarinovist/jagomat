"""Regresi lintas rute: semua halaman guru memakai shell yang sama (keputusan pemilik 22 Nov 2026).

Halaman dirender lewat server HTTP sungguhan (ServerUji) dengan data sintetis. Yang dijaga:
satu topbar (markup identik), satu menu akun (Ruang guru, Akun & Siswa, satu form Keluar
bergaya tautan bahaya), font merek lokal tanpa pihak ketiga, satu wadah `LEBAR_SHELL_GURU`,
dan paling banyak satu pemicu Tanya per halaman.
"""
import re
import sys
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import design_tokens as T  # noqa: E402
import shell_guru_style  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

GURU = ("guru", SANDI_GURU)
NAMA_ANAK = "Anak Sintetis"


@pytest.fixture(scope="module")
def halaman(tmp_path_factory):
    """Semua rute guru dirender sekali: {nama_rute: html}."""
    mp = MonkeyPatch()
    mp.setenv("OSN_LOMBA", "1")
    server = ServerUji(tmp_path_factory.mktemp("shell-guru"), mp)
    try:
        with server.buka() as kon:
            anak = database.tambah_siswa(kon, NAMA_ANAK, "P5", pemilik="guru")
            sesi = database.buat_sesi(kon, anak, seed=42, level="P5", jumlah_soal=2)
        rute = {"guru": "/guru", "sesi": f"/sesi/{sesi}",
                "laporan-ortu": f"/anak/{anak}/laporan-ortu", "lomba": f"/anak/{anak}/lomba"}
        rute.update({f"anak-{s}": f"/anak/{anak}?section={s}"
                     for s in ("rencana", "latihan", "riwayat", "perkembangan")})
        rute.update({f"akun-{s}": f"/akun?section={s}" for s in ("akun", "siswa", "langganan")})
        hasil = {}
        for nama, jalur in rute.items():
            kode, isi, _ = server.minta(jalur, auth=GURU)
            assert kode == 200, (nama, kode)
            hasil[nama] = isi
        yield hasil
    finally:
        server.berhenti()
        mp.undo()


def _topbar(isi: str) -> str:
    cocok = re.search(r'<div class="st-topbar">.*?</nav></div>', isi, re.S)
    assert cocok, "topbar tidak ditemukan"
    return cocok.group(0)


def _topbar_normal(isi: str) -> str:
    """Topbar tanpa pemicu Tanya (ikut di nav pada profil anak) dan tanpa penanda halaman aktif."""
    bagian = _topbar(isi)
    menu = bagian.split("</details>", 1)[0]
    return menu.replace(' aria-current="page"', "")


def test_semua_rute_memakai_markup_topbar_identik(halaman):
    acuan = _topbar_normal(halaman["guru"])
    beda = [nama for nama, isi in halaman.items() if _topbar_normal(isi) != acuan]
    assert not beda, f"topbar berbeda dari /guru di: {beda}"


def test_menu_akun_identik_dengan_satu_form_keluar_bergaya_tautan_bahaya(halaman):
    for nama, isi in halaman.items():
        menu = _topbar(isi).split('<div class="menu-isi">', 1)[1]
        assert '<a href="/guru"' in menu and ">Ruang guru</a>" in menu, nama
        assert '<a href="/akun"' in menu and "Akun &amp; Siswa</a>" in menu, nama
        assert menu.index('class="menu-pisah"') < menu.index("/keluar"), nama
        assert isi.count('action="/keluar"') == 1, nama
        assert '<button type="submit" class="menu-keluar-st">Keluar</button>' in menu, nama
        assert 'class="cta"' not in isi and "akun-form-keluar" not in isi, nama


def test_menu_menandai_halaman_induk_yang_sedang_dibuka(halaman):
    assert '<a href="/guru" aria-current="page">' in _topbar(halaman["guru"])
    for nama in ("akun-akun", "akun-siswa", "akun-langganan"):
        assert '<a href="/akun" aria-current="page">' in _topbar(halaman[nama]), nama
    assert "aria-current" not in _topbar(halaman["sesi"]).split("</details>", 1)[0]


def test_keluar_bergaya_tautan_bahaya_bukan_tombol_solid():
    css = shell_guru_style.GAYA_SHELL_GURU
    aturan = re.search(r"\.menu-keluar-st \{([^}]*)\}", css).group(1)
    assert f"color: {T.AKSEN_KORAL_TUA}" in aturan
    assert "background: transparent" in aturan and "box-shadow: none" in aturan


def test_font_merek_lokal_tanpa_pihak_ketiga_di_halaman_privat(halaman):
    for nama, isi in halaman.items():
        assert "/aset/font-" in isi and "@font-face" in isi, nama
        if nama == "guru":  # /guru nonprivat: Material Symbols tetap dari CDN (keputusan 22 Nov, F1)
            continue
        assert "fonts.googleapis.com" not in isi and "fonts.gstatic.com" not in isi, nama


def test_wadah_semua_halaman_guru_memakai_token_lebar_shell(halaman):
    assert T.LEBAR_SHELL_GURU == "60rem"
    wadah = f"max-width: calc({T.LEBAR_SHELL_GURU} + 2 * {T.ANAK_GUTTER})"
    for nama, isi in halaman.items():
        assert re.search(r'<div class="bungkus-st shell-guru-st[ "]', isi), nama
        assert wadah in isi, nama
        assert f"max-width: min(12rem" in isi, nama  # menu akun tidak melebihi layar sempit


def test_topbar_tidak_lagi_lebih_sempit_dari_wadah_di_css_halaman():
    css = shell_guru_style.GAYA_SHELL_GURU
    topbar = re.search(r"body\.st \.bungkus-st\.shell-guru-st > \.st-topbar \{([^}]*)\}", css).group(1)
    assert "max-width: none" in topbar and "width: 100%" in topbar


def test_kolom_baca_sempit_diletakkan_di_tengah_wadah():
    css = shell_guru_style.GAYA_SHELL_GURU
    aturan = re.search(r"\.shell-guru-st:is\(([^)]*)\) > :not\(\.st-topbar\) \{([^}]*)\}", css)
    for kelas in (".guru-beranda-st", ".bagikan-editorial-st", ".akun-sempit-st"):
        assert kelas in aturan.group(1)
    assert f"max-width: {T.LEBAR_KONTEN}" in aturan.group(2) and "margin-inline: auto" in aturan.group(2)


def test_paling_banyak_satu_pemicu_tanya_per_halaman(halaman):
    for nama, isi in halaman.items():
        assert isi.count('class="pendamping-pemicu"') <= 1, nama
    for nama in ("anak-rencana", "anak-latihan", "anak-riwayat", "anak-perkembangan", "sesi"):
        assert halaman[nama].count('class="pendamping-pemicu"') == 1, nama
        assert ">Tanya</span>" in halaman[nama], nama
    for nama in ("guru", "akun-akun", "laporan-ortu", "lomba"):
        assert "pendamping-pemicu" not in halaman[nama].split("</style>")[-1], nama

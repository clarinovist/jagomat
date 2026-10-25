"""Peta peran design system: token mencapai aturan CSS nyata dan kontrasnya terjaga."""
import ast
import importlib
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import design_roles as R
import design_tokens as T

ROOT = Path(__file__).resolve().parent.parent
UJI = "__uji__"
SEMUA_SISI = sorted(
    {s for daftar in R.PERMUKAAN.values() for p in daftar for s in (p.depan, p.belakang)},
    key=lambda s: (s.modul, s.konstanta, s.selektor, s.properti, s.token),
)


def _css_dengan(modul, konstanta, token):
    """Evaluasi assignment pertama konstanta dengan satu token ditukar penanda."""
    module = importlib.import_module(modul)
    tree = ast.parse((ROOT / (modul + ".py")).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == konstanta for t in n.targets))
    lingkup = dict(vars(module), T=SimpleNamespace(**dict(vars(T), **{token: UJI})))
    css = eval(compile(ast.Expression(node.value), modul, "eval"), lingkup)
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _selektor(daftar):
    """Pisahkan daftar selektor pada koma tingkat atas (bukan di dalam :is())."""
    hasil, kedalaman, awal = [], 0, 0
    for i, c in enumerate(daftar):
        kedalaman += {"(": 1, ")": -1}.get(c, 0)
        if c == "," and kedalaman == 0:
            hasil.append(daftar[awal:i])
            awal = i + 1
    hasil.append(daftar[awal:])
    return {" ".join(s.split()) for s in hasil}


def _aturan(css, selektor):
    return [isi for daftar, isi in re.findall(r"([^{}]+)\{([^{}]+)\}", css)
            if selektor in _selektor(daftar)]


def _deklarasi(properti):
    return re.compile(r"(?:^|;)\s*" + re.escape(properti) + r"\s*:[^;]*" + UJI)


@pytest.mark.parametrize("sisi", SEMUA_SISI, ids=lambda s: f"{s.modul}:{s.selektor}:{s.properti}:{s.token}")
def test_token_peran_mencapai_aturan_css_yang_dirujuk(sisi):
    tukar = sisi.alias or sisi.token
    aturan = _aturan(_css_dengan(sisi.modul, sisi.konstanta, tukar), sisi.selektor)
    assert aturan, f"selektor tidak ditemukan: {sisi.selektor}"
    assert any(_deklarasi(sisi.properti).search(isi) for isi in aturan), sisi
    if sisi.alias:
        properti = re.fullmatch(r"var\((--[a-z-]+)\)", getattr(T, sisi.alias)).group(1)
        css = _css_dengan(sisi.modul, sisi.konstanta, sisi.token)
        assert _deklarasi(properti).search(css), f"{sisi.token} tidak dipasang ke {properti}"


def test_semua_token_peran_berupa_warna_hex():
    for sisi in SEMUA_SISI:
        assert re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", R.nilai(sisi)), sisi


@pytest.mark.parametrize("permukaan", sorted(R.PERMUKAAN))
def test_satu_peran_satu_token_per_permukaan(permukaan):
    peta = R.peta_peran(permukaan)
    assert peta and all(hasattr(T, token) for token in peta.values())


def test_kontras_hanya_gagal_pada_pengecualian_tercatat():
    """Kegagalan baru maupun pengecualian basi sama-sama memerahkan test."""
    gagal = R.kegagalan()
    assert set(gagal) == set(R.PENGECUALIAN), {k: round(v, 2) for k, v in gagal.items()}
    assert all(alasan.strip() for alasan in R.PENGECUALIAN.values())


def test_pemeriksa_kontras_bereaksi_pada_nilai_token():
    """Menukar coral terang dengan coral teks-aman menghapus kegagalan badge baru."""
    kunci = ("dasar", "badge_baru_teks", "badge_baru_latar")
    diperbaiki = SimpleNamespace(**dict(vars(T), AKSEN_MURID_KORAL=T.AKSEN_KORAL_TUA))
    rusak = SimpleNamespace(**dict(vars(T), TEKS_UTAMA=T.LATAR_MURID))
    assert kunci in R.kegagalan(T) or kunci not in R.PENGECUALIAN
    assert kunci not in R.kegagalan(diperbaiki)
    assert ("dasar", "teks_utama", "latar_halaman") in R.kegagalan(rusak)


@pytest.mark.parametrize("depan,belakang,harapan", (
    ("#777777", "#ffffff", 4.478089453577214),
    ("#000", "#fff", 21.0),
    ("#fff", "#fff", 1.0),
))
def test_rasio_kontras_memakai_luminansi_srgb(depan, belakang, harapan):
    assert R.rasio_kontras(depan, belakang) == pytest.approx(harapan)
    assert R.rasio_kontras(belakang, depan) == pytest.approx(harapan)


def test_warna_tidak_valid_ditolak():
    with pytest.raises(ValueError):
        R.rasio_kontras("var(--admin-teks)", "#fff")

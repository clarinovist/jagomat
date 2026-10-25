"""Peta peran design system: token mencapai aturan CSS nyata dan kontrasnya terjaga."""
import ast
from functools import lru_cache
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
# Nilai aksen terang (dan alias statusnya) diganti penanda saat memindai CSS.
TERANG = {"AKSEN_MURID_UTAMA": "__teal__", "STATUS_KUAT": "__teal__",
          "AKSEN_MURID_KORAL": "__koral__", "STATUS_SALAH": "__koral__",
          "AKSEN_MURID_AMBER": "__amber__", "STATUS_LEMAH": "__amber__", "BADGE_ADMIN_BG": "__amber__"}


def _ns(**tukar):
    return SimpleNamespace(**dict(vars(T), **tukar))


@lru_cache(maxsize=None)
def _definisi(modul):
    """Assignment GAYA*/CSS* tingkat atas sebuah modul, diurai sekali."""
    tree = ast.parse((ROOT / (modul + ".py")).read_text())
    return tuple((t.id, n.value) for n in tree.body if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name) and t.id.startswith(("GAYA", "CSS")))


def _evaluasi(modul, simpul, namespace_token):
    module = importlib.import_module(modul)
    css = eval(compile(ast.Expression(simpul), modul, "eval"), dict(vars(module), T=namespace_token))
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S) if isinstance(css, str) else ""


def _css_dengan(modul, konstanta, token):
    """Evaluasi assignment PERTAMA konstanta (blok `+=` sesudahnya tidak ikut) dengan token ditukar."""
    simpul = next(v for nama, v in _definisi(modul) if nama == konstanta)
    return _evaluasi(modul, simpul, _ns(**{token: UJI}))


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


def _deklarasi(properti, penanda=UJI):
    return re.compile(r"(?:^|;)\s*" + re.escape(properti) + r"\s*:[^;]*" + penanda)


@pytest.mark.parametrize("sisi", SEMUA_SISI, ids=lambda s: f"{s.modul}:{s.selektor}:{s.properti}:{s.token}")
def test_token_peran_mencapai_aturan_css_yang_dirujuk(sisi):
    tukar = sisi.alias or sisi.token
    aturan = _aturan(_css_dengan(sisi.modul, sisi.konstanta, tukar), sisi.selektor)
    assert aturan, f"selektor tidak ditemukan: {sisi.selektor}"
    assert any(_deklarasi(sisi.properti).search(isi) for isi in aturan), sisi
    if sisi.alias:
        properti = re.fullmatch(r"var\((--[a-z-]+)\)", getattr(T, sisi.alias)).group(1)
        pemasang = _aturan(_css_dengan(sisi.modul, sisi.konstanta, sisi.token), sisi.pemasang)
        assert any(_deklarasi(properti).search(isi) for isi in pemasang), \
            f"{sisi.token} tidak dipasang ke {properti} di {sisi.pemasang}"


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


@pytest.mark.parametrize("tukar,kunci", (
    ({"AKSEN_KORAL_TUA": T.AKSEN_MURID_KORAL}, ("dasar", "badge_baru_teks", "badge_baru_latar")),
    ({"BORDER_KONTROL": T.BORDER_VARIAN}, ("dasar", "batas_kontrol", "latar_kartu")),
    ({"FOKUS_AKSEN": T.AKSEN_MURID_UTAMA}, ("dasar", "fokus", "latar_halaman")),
    ({"BORDER_KONTROL": "#BFB39A"}, ("profil", "batas_kontrol", "latar_kartu")),
    ({"AKSEN_TEAL_TUA": T.AKSEN_MURID_UTAMA}, ("murid", "nomor_teks", "nomor_latar")),
    ({"KODE_SALAH_BACA_TEKS": "#a4700f"}, ("tinjauan", "kode_lama_B_teks", "kode_lama_B_latar")),
))
def test_pemeriksa_kontras_menangkap_nilai_lama_yang_gagal(tukar, kunci):
    """Mengembalikan nilai sebelum perbaikan 25 Okt memunculkan lagi kegagalannya."""
    assert kunci not in R.kegagalan(T)
    assert kunci in R.kegagalan(_ns(**tukar))


def test_pemeriksa_kontras_menangkap_teks_tak_terbaca():
    assert ("dasar", "teks_utama", "latar_halaman") in R.kegagalan(_ns(TEKS_UTAMA=T.LATAR_MURID))


def _pemakaian_aksen_terang():
    """Aturan dengan aksen terang sebagai warna teks, atau latar teks putih."""
    temuan = set()
    for path in sorted(ROOT.glob("*.py")):
        if path.stem in ("design_tokens", "design_roles") or not re.search(r"^(GAYA|CSS)", path.read_text(), re.M):
            continue
        for nama, simpul in _definisi(path.stem):
            css = _evaluasi(path.stem, simpul, _ns(**TERANG))
            for daftar, isi in re.findall(r"([^{}]+)\{([^{}]+)\}", css):
                warna = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", isi)
                latar = re.search(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", isi)
                teks_terang = warna and "__" in warna.group(1)
                latar_putih = (latar and re.search(r"__(teal|koral)__", latar.group(1)) and warna
                               and warna.group(1).strip().lower() in ("#fff", "#ffffff"))
                if teks_terang or latar_putih:
                    temuan.add((path.stem, nama, " ".join(daftar.split())))
    return temuan


def test_aksen_terang_bukan_teks_kecuali_tercatat():
    """Teal/coral/amber terang gagal 4,5:1 sebagai teks; izin harus beralasan dan tidak basi."""
    assert _pemakaian_aksen_terang() == set(R.AKSEN_TERANG_DIIZINKAN)
    assert all(alasan.strip() for alasan in R.AKSEN_TERANG_DIIZINKAN.values())


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

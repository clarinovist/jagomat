"""Ekspor token untuk alat desain: nilai identik sumber, peran valid, tanpa menimpa."""
import importlib.util
import json
from pathlib import Path
import re

import pytest

import design_roles as R
import design_tokens as T

SKRIP = Path(__file__).resolve().parents[2] / "scripts" / "design_tokens_export.py"
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
ALIAS = re.compile(r"\{([^{}]+)\}")
GEOMETRI = ("POLA_", "STAT_", "GEO_", "RUANG_", "JAM_", "VENN_", "PETA_", "PETAK_",
            "OBJEK_", "SLOT_", "TIM_", "SUSUNAN_", "FASE6_")


@pytest.fixture(scope="module")
def ekspor():
    spec = importlib.util.spec_from_file_location("ekspor_token_uji", SKRIP)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _daun(pohon, jalur=()):
    """(jalur, simpul) untuk setiap token DTCG (simpul ber-$value)."""
    if "$value" in pohon:
        yield jalur, pohon
        return
    for kunci, anak in pohon.items():
        if not kunci.startswith("$") and isinstance(anak, dict):
            yield from _daun(anak, jalur + (kunci,))


def _token_sederhana():
    """Token string bernilai tunggal di design_tokens (bukan adapter var/teks merek)."""
    return {k: v for k, v in vars(T).items()
            if k.isupper() and isinstance(v, str) and not v.startswith("var(")
            and k not in ("NAMA_PRODUK", "TAGLINE") and not k.startswith(GEOMETRI)}


def test_ekspor_menulis_json_css_dan_tidak_menimpa(ekspor, tmp_path):
    folder = tmp_path / "token"
    json_path, css_path = ekspor.ekspor(folder)
    assert (json_path, css_path) == (folder / "tokens.json", folder / "tokens.css")
    awal = (json_path.read_bytes(), css_path.read_bytes())
    with pytest.raises(FileExistsError):
        ekspor.ekspor(folder)
    assert (json_path.read_bytes(), css_path.read_bytes()) == awal


def test_nilai_json_identik_dengan_design_tokens(ekspor):
    data = ekspor.bangun_json()
    token = [(j, s) for j, s in _daun(data) if j[0] != "peran"]
    assert token
    for jalur, simpul in token:
        assert simpul["$value"] == getattr(T, jalur[-1]), jalur
    nama_json = {j[-1] for j, _ in token}
    warna_sumber = {k for k, v in _token_sederhana().items() if HEX.fullmatch(v)}
    assert warna_sumber <= nama_json, sorted(warna_sumber - nama_json)


def test_json_tanpa_geometri_soal_dan_adapter_tema(ekspor):
    teks = json.dumps(ekspor.bangun_json()) + ekspor.bangun_css()
    assert "var(--" not in teks
    for awalan in GEOMETRI:
        assert f'"{awalan}' not in teks and f"--{awalan.lower().replace('_', '-')}" not in teks


def test_token_rumit_tetap_tercatat_hanya_di_css(ekspor):
    data = ekspor.bangun_json()
    hanya_css = data["$extensions"]["jagomat"]["hanya_css"]
    assert "UKURAN_JUDUL_DEWASA" in hanya_css and "BAYANGAN_KARTU" in hanya_css
    nama_json = {j[-1] for j, _ in _daun(data)}
    assert not set(hanya_css) & nama_json


def test_peran_tiap_permukaan_merujuk_token_yang_benar(ekspor):
    data = ekspor.bangun_json()
    assert set(data["peran"]) == set(R.PERMUKAAN)
    for permukaan, peta in data["peran"].items():
        assert set(peta) == set(R.peta_peran(permukaan))
        for peran, simpul in peta.items():
            sasaran = ALIAS.fullmatch(simpul["$value"]).group(1).split(".")
            tujuan = data
            for kunci in sasaran:
                tujuan = tujuan[kunci]
            assert sasaran[-1] == R.peta_peran(permukaan)[peran]
            assert tujuan["$value"] == getattr(T, sasaran[-1])


def test_css_memuat_semua_token_bernilai_tunggal(ekspor):
    css = ekspor.bangun_css()
    for nama, nilai in _token_sederhana().items():
        assert f"--{nama.lower().replace('_', '-')}: {nilai};" in css, nama
    assert "var(--" not in css


def test_skrip_tidak_menulis_hex_sendiri():
    assert not HEX.search(SKRIP.read_text(encoding="utf-8"))

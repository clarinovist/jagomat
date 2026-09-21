"""Draft memetakan tugas, bukan profil, kemampuan, atau bukti anak."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import ast

import pytest

import generator
import skill_demand_draft as draft


def test_dua_tugas_pada_profil_sama_tidak_diratakan():
    hasil = {}
    for seed in range(25):
        soal = generator.buat_soal(draft.POLA_PILOT, seed, "P6", "geometri-datar")
        hasil[soal.parameter["varian"]] = draft.petakan_draft(
            soal.template_id, soal.parameter, "teks-v1").id
    assert set(hasil) == {"keliling", "balik_luas"}
    assert len(set(hasil.values())) == 2


@pytest.mark.parametrize("profil", ("P3", "P4", "P5", "P6"))
def test_angka_dan_profil_bukan_id_tuntutan(profil):
    langsung = draft.petakan_draft(draft.POLA_PILOT, {"varian": "keliling", "p": 8, "l": 3}, "teks-v1")
    besar = draft.petakan_draft(draft.POLA_PILOT, {"varian": "keliling", "p": 38, "l": 23}, "teks-v1")
    soal = generator.buat_soal(draft.POLA_PILOT, 1, profil, "geometri-datar")
    assert draft.petakan_draft(soal.template_id, soal.parameter, "teks-v1") == draft.petakan_draft(
        replace(soal, level="P3").template_id, soal.parameter, "teks-v1")
    assert langsung.id == besar.id == "persegi-panjang.keliling-langsung.v1"
    assert draft.deskriptor(langsung.id) == langsung
    with pytest.raises(FrozenInstanceError):
        langsung.id = "lain"


@pytest.mark.parametrize("parameter", (
    {}, {"varian": "asing", "p": 8, "K": 22},
    {"varian": "keliling", "p": 8},
    {"varian": "keliling", "p": 8, "l": 3, "K": 22},
    {"varian": "keliling", "p": True, "l": 3},
    {"varian": "keliling", "p": 8.0, "l": 3},
    {"varian": "keliling", "p": 0, "l": 3},
    {"varian": "keliling", "p": 8, "l": -3},
    {"varian": "balik_luas", "p": 8, "K": 21},
    {"varian": "balik_luas", "p": 8, "K": 16},
    {"varian": "balik_luas", "p": 8, "K": 12},
    [], None,
))
def test_parameter_ambigu_tidak_fallback(parameter):
    with pytest.raises(ValueError):
        draft.petakan_draft(draft.POLA_PILOT, parameter, "teks-v1")


def test_batas_pilot_dan_versi_eksplisit():
    assert draft.petakan_draft("luas_kotak_satuan", {}, "teks-v1") is None
    with pytest.raises(ValueError, match="versi"):
        draft.petakan_draft(draft.POLA_PILOT, {}, "teks-v1", versi="aktif-v2")
    with pytest.raises(ValueError, match="versi"):
        draft.deskriptor(draft.DESKRIPTOR[0].id, "aktif-v2")
    with pytest.raises(ValueError, match="tidak dikenal"):
        draft.deskriptor("P6")
    with pytest.raises(ValueError, match="representasi"):
        draft.petakan_draft(draft.POLA_PILOT, {"varian": "keliling", "p": 8, "l": 3}, "asing-v1")
    assert draft.petakan_draft(draft.POLA_PILOT, {"varian": "balik_luas", "p": 8, "K": 22},
                               "geometri_datar-v1").id == "persegi-panjang.luas-dari-keliling.v1"


def test_draft_dan_codec_belum_dipanggil_runtime():
    akar = Path(__file__).resolve().parents[1]
    modul = {"skill_demand_draft", "session_demand_contract"}
    for path in akar.glob("*.py"):
        if path.stem in modul:
            continue
        pohon = ast.parse(path.read_text())
        for node in ast.walk(pohon):
            if isinstance(node, ast.Import):
                assert not {n.name for n in node.names} & modul, path.name
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in modul, path.name
    assert not hasattr(draft, "katalog_aktif")

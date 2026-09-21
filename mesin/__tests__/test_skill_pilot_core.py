"""Kontrak pilot: tugas terpisah, variasi nyata, profil eksplisit dan materi sesuai."""
from collections import UserString
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest
import generator
import skill_pilot as p
from skill_pilot_selector import pilih_probe
from skill_pilot_materials import pilihan_materi


def konteks(identitas=p.LANGSUNG, profil="P3", mode="teks-v1"):
    return p.KonteksPilot(identitas, profil, mode)


@pytest.mark.parametrize("profil", ("P3", "P4", "P5", "P6"))
@pytest.mark.parametrize("mode", p.REPRESENTASI)
def test_generator_historis_dan_dua_varian_tetap_terpisah(profil, mode):
    for seed in range(25):
        soal = generator.buat_soal(p.POLA, seed, profil, "geometri-datar")
        identitas = p.LANGSUNG if soal.parameter["varian"] == "keliling" else p.BALIK
        k = konteks(identitas, profil, mode)
        assert len(p.sidik_variasi(k, soal.template_id, soal.parameter)) == 64
        for malrule in soal.malrule:
            p.validasi_fokus(k, (soal.template_id, malrule.kode, malrule.id))
        if profil != "P3":
            salah = konteks(p.BALIK if identitas == p.LANGSUNG else p.LANGSUNG, profil, mode)
            with pytest.raises(ValueError, match="varian"):
                p.sidik_variasi(salah, soal.template_id, soal.parameter)


@pytest.mark.parametrize("identitas,profil,mode,versi", (
    (p.BALIK,"P3","teks-v1",p.VERSI_RUBRIK),
    (p.PRASYARAT,"P4","teks-v1",p.VERSI_RUBRIK),
    (p.LANGSUNG,"P6","asing",p.VERSI_RUBRIK),
    (p.LANGSUNG,"P3","teks-v1","draft-v1"),
    (p.LANGSUNG,UserString("P3"),"teks-v1",p.VERSI_RUBRIK),
    (p.LANGSUNG,"P3","teks-v1",UserString(p.VERSI_RUBRIK)),
    ("asing","P3","teks-v1",p.VERSI_RUBRIK),
))
def test_konteks_asing_tidak_fallback(identitas, profil, mode, versi):
    with pytest.raises(ValueError):
        p.KonteksPilot(identitas,profil,mode,versi)


def test_variasi_kisi_bukan_hiasan_atau_satuan_atau_orientasi():
    k = konteks(p.PRASYARAT)
    awal = {"p":8,"l":3,"satuan":"cm","konteks":"ubin"}
    sidik = p.sidik_variasi(k,p.POLA_KISI,awal)
    for perubahan in ({"konteks":"keramik"}, {"satuan":"m"}, {"p":3,"l":8}):
        assert p.sidik_variasi(k,p.POLA_KISI,{**awal,**perubahan}) == sidik
    assert p.sidik_variasi(k,p.POLA_KISI,{**awal,"l":4}) != sidik
    assert len(p.TUNTUTAN) == 2 and p.RUJUKAN_LUAS not in p.TUNTUTAN


@pytest.mark.parametrize("parameter", (
    {"varian":"keliling","p":True,"l":3},
    {"varian":"keliling","p":8,"l":3,"asing":1},
    {"varian":"keliling","p":38,"l":3},
    {"varian":"keliling","p":3,"l":6},
    {"varian":"keliling","p":3,"l":5},
))
def test_parameter_p3_tidak_diperluas_atau_direka(parameter):
    with pytest.raises(ValueError):
        p.sidik_variasi(konteks(),p.POLA,parameter)


def test_batas_balik_dan_prasyarat():
    for parameter in ({"varian":"balik_luas","p":8,"K":21},
                      {"varian":"balik_luas","p":8,"K":16},
                      {"varian":"balik_luas","p":31,"K":70}):
        with pytest.raises(ValueError):
            p.sidik_variasi(konteks(p.BALIK,"P4"),p.POLA,parameter)
    with pytest.raises(ValueError):
        p.sidik_variasi(konteks(p.PRASYARAT),p.POLA_KISI,
                        {"p":3,"l":7,"satuan":"cm","konteks":"ubin"})


def test_profil_tujuan_bukan_naik_otomatis():
    with pytest.raises(ValueError, match="eksplisit"):
        p.profil_tujuan(konteks(),p.BALIK)
    assert p.profil_tujuan(konteks(),p.BALIK,"P6") == "P6"
    assert p.profil_tujuan(konteks(profil="P5"),p.BALIK) == "P5"
    with pytest.raises(ValueError):
        p.profil_tujuan(konteks(),p.BALIK,"P3")


@pytest.mark.parametrize("identitas,profil", ((p.LANGSUNG,"P3"),(p.LANGSUNG,"P4"),
                                              (p.BALIK,"P4"),(p.PRASYARAT,"P3")))
def test_selector_deterministik_baru_dan_murni(identitas, profil):
    k = konteks(identitas,profil)
    a = pilih_probe(k,10,4)
    assert a == pilih_probe(k,10,4)
    assert len({b.sidik_variasi for b in a}) == 4
    assert all(b.konteks == k and b.soal.level == profil for b in a)
    lama = tuple(b.sidik_variasi for b in a)
    b = pilih_probe(k,10,4,sidik_terpakai=lama)
    assert not set(lama) & {x.sidik_variasi for x in b}


def test_selector_tidak_menyembunyikan_kuota_gagal():
    with pytest.raises(ValueError, match="belum cukup"):
        pilih_probe(konteks(p.BALIK,"P4"),1,4,batas=1)
    for seed,jumlah in ((True,4),(0,True),(-1,4),(1,0),(1,16)):
        with pytest.raises(ValueError): pilih_probe(konteks(),seed,jumlah)


def test_malrule_dan_materi_cocok_tugas():
    k = konteks(p.BALIK,"P4")
    fokus = (p.POLA,"K","datar.balik_lupa_bagi_dua")
    soal = pilih_probe(k,1,4,fokus=fokus)
    assert all(any(m.id == fokus[2] for m in s.soal.malrule) for s in soal)
    materi = pilihan_materi(k,fokus)
    assert len(materi) == 2
    assert materi[0].pendekatan_id != materi[1].pendekatan_id
    assert "22 ÷ 2" in materi[0].contoh_terbimbing
    assert "22 − 8 − 8" in materi[1].contoh_terbimbing
    assert "24 cm²" in materi[0].contoh_terbimbing
    for salah in ((p.POLA,"K","datar.tukar_luas"),(p.POLA,UserString("K"),None),
                  (p.POLA,"H","datar.balik_lupa_bagi_dua")):
        with pytest.raises(ValueError): pilihan_materi(k,salah)
    assert len(pilihan_materi(k,(p.POLA,"T",None))) == 1
    for kode in ("B","H","E","N"):
        assert pilihan_materi(k,(p.POLA,kode,None))[0].tersedia


def test_selector_deterministik_antarproses():
    source = """import json
from skill_pilot import *
from skill_pilot_selector import pilih_probe
print(json.dumps([(p.seed_sumber,p.soal.tanda_tangan,p.sidik_variasi) for p in pilih_probe(KonteksPilot(BALIK,'P4','teks-v1'),71,4)]))
"""
    hasil=[]
    for seed in ("1","731"):
        hasil.append(subprocess.check_output([sys.executable,"-B","-c",source],
                     cwd=str(Path(__file__).resolve().parents[1]),
                     env={**os.environ,"PYTHONHASHSEED":seed}))
    assert hasil[0] == hasil[1]

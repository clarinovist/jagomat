"""Pencocokan format harus longgar pada penulisan, ketat pada makna soal."""

from __future__ import annotations

from dataclasses import replace
import random

import pytest

from diagnosis import diagnosa, setara
from topic_advanced_arithmetic import satuan_konversi
from topic_number_patterns import deret_aritmetika
from topics import ambil


DERET = deret_aritmetika(6, 12, 4, 3)
KONVERSI = satuan_konversi("m_ke_km", 71000)
VARIAN = (
    ("km_ke_m", 71, "m", "km"),
    ("m_ke_km", 71000, "km", "m"),
    ("jam_ke_menit", 71, "menit", "jam"),
    ("menit_ke_jam", 4260, "jam", "menit"),
    ("kg_ke_g", 71, "g", "kg"),
    ("g_ke_kg", 71000, "kg", "g"),
    ("liter_ke_ml", 71, "ml", "liter"),
    ("ml_ke_liter", 71000, "liter", "ml"),
)


def _nilai(soal, jawaban, cara="Saya hitung", belum=False, kunci=None):
    malrule = [
        {"malrule_id": m.id, "jawaban": m.jawaban, "kode": m.kode, "alasan": m.alasan}
        for m in soal.malrule
    ]
    return diagnosa(
        soal.kunci if kunci is None else kunci, jawaban, cara, "", belum,
        malrule, soal.minta_restatement, soal=soal,
    )


@pytest.mark.parametrize("jawaban", [
    "54,66,78", "54, 66, 78", "54 66 78", "54 dan 66 dan 78",
    " 54 ,66, 78 ", "54\n66\n78", "54,66 dan 78", "５４，６６，７８",
])
def test_daftar_setara_tanpa_tergantung_spasi(jawaban):
    assert _nilai(DERET, jawaban).benar


@pytest.mark.parametrize("jawaban", [
    "78,66,54", "54,66", "54,66,78,90", "54,66,79", "54.66.78",
    "54,66,,78", ",54,66,78", "54,66,78,", "54 66 dan dan 78",
    "54,66,78 km", "hasilnya 54,66,78", "54,66,78/1", "54,66,78.0",
    "54,6,6,78", "54,,66,78", "54dan66dan78", ".54,66,78", "",
])
def test_daftar_salah_atau_rusak_tidak_dilonggarkan(jawaban):
    assert not _nilai(DERET, jawaban).benar


def test_desimal_tidak_berubah_menjadi_daftar():
    assert setara("0,85", "0.85")
    assert not setara("0,85", "0, 85")
    assert not setara("0 85", "0.85")
    soal = deret_aritmetika(0, 85, 1, 2)
    assert setara("0,85", "0, 85", soal=soal)
    assert not setara("0.85", "0, 85", soal=soal)
    satu_isian = deret_aritmetika(0, 85, 1, 1)
    assert not setara("0,85", "0, 85", soal=satu_isian)


def test_daftar_turun_tetap_mendukung_minus_unicode():
    soal = deret_aritmetika(6, -12, 4, 3)
    assert _nilai(soal, "−42,−54,−66").benar


@pytest.mark.parametrize("malrule", DERET.malrule, ids=lambda m: m.id)
def test_malrule_daftar_dan_satu_isian_tetap_terdeteksi(malrule):
    u = _nilai(DERET, malrule.jawaban.replace(", ", ","))
    assert not u.benar
    assert (u.kode, u.malrule_id, u.yakin) == (malrule.kode, malrule.id, True)


@pytest.mark.parametrize("varian,nilai,satuan,salah", VARIAN)
@pytest.mark.parametrize("format_jawaban", ["{angka}", "{angka}{satuan}", "{angka} {satuan}", " {angka}  {satuan} "])
def test_satuan_tujuan_delapan_varian_diterima(varian, nilai, satuan, salah, format_jawaban):
    soal = satuan_konversi(varian, nilai)
    jawaban = format_jawaban.format(angka=soal.kunci, satuan=satuan.upper())
    assert _nilai(soal, jawaban).benar


@pytest.mark.parametrize("varian,nilai,satuan,salah", VARIAN)
def test_satuan_sumber_dan_satuan_asing_ditolak(varian, nilai, satuan, salah):
    soal = satuan_konversi(varian, nilai)
    for akhiran in (salah, "kgkm", satuan + " " + satuan, satuan + "2", satuan + "/jam"):
        assert not _nilai(soal, soal.kunci + akhiran).benar
    for mal in soal.malrule:
        u = _nilai(soal, mal.jawaban + satuan)
        assert (u.benar, u.kode, u.malrule_id) == (False, mal.kode, mal.id)
        u_salah = _nilai(soal, mal.jawaban + salah)
        assert not u_salah.benar and u_salah.malrule_id is None


@pytest.mark.parametrize("jawaban", [
    "71000km", "70km", "71 m", "71 kg", "71kmabc", "71 km atau 71 m",
    "71km2", "71km²", "71km/jam", "71,0,0km", "71..km", "71,km", "71 km 0",
    "71km=71", "km71", "hasilnya 71km", ".71km", ",71km", "",
])
def test_konversi_tidak_mengambil_sebagian_jawaban(jawaban):
    assert not _nilai(KONVERSI, jawaban).benar


def test_toleransi_tidak_menyebar_ke_template_atau_varian_asing():
    assert not setara("71km", "71")
    assert not setara("71km", "71", soal=DERET)
    for soal in (
        replace(KONVERSI, template_id="kecepatan_jarak_waktu"),
        replace(KONVERSI, parameter={"varian": "asing", "nilai": 71000}),
    ):
        assert not _nilai(soal, "71km").benar
        assert _nilai(soal, "71").benar


@pytest.mark.parametrize("soal,jawaban,kunci_tersimpan", [
    (KONVERSI, "72km", "72"), (DERET, "55,67,79", "55, 67, 79"),
])
def test_metadata_tidak_mengganti_kunci_tersimpan(soal, jawaban, kunci_tersimpan):
    assert _nilai(soal, jawaban, kunci=kunci_tersimpan).benar
    assert not _nilai(soal, soal.kunci, kunci=kunci_tersimpan).benar


@pytest.mark.parametrize("soal,jawaban", [(DERET, "54,66,78"), (KONVERSI, "71km")])
@pytest.mark.parametrize("cara,belum,kode", [
    ("", False, "N"), ("[pilihan] tebak", False, "N"),
    ("[pilihan] bingung", False, None), ("Saya hitung", True, None),
])
def test_format_benar_tidak_melewati_syarat_diagnosis(soal, jawaban, cara, belum, kode):
    u = _nilai(soal, jawaban, cara, belum)
    assert not u.benar and u.kode == kode


@pytest.mark.parametrize("topik,template,level", [
    ("pola-bilangan", "deret_aritmetika", level) for level in ("P3", "P4", "P5", "P6")
] + [
    ("aritmatika-lanjut", "satuan_konversi", level) for level in ("P5", "P6")
])
def test_kunci_dan_malrule_lintas_seed_level(topik, template, level):
    paket = ambil(topik)
    for seed in range(25):
        parameter = paket.parameter_untuk(template, random.Random(seed), level)
        soal = paket.templates[template](**parameter)
        assert _nilai(soal, soal.kunci).benar
        if template == "deret_aritmetika":
            def tulis(jawaban):
                return jawaban.replace(", ", ",")
        else:
            tujuan = next(satuan for varian, _, satuan, _ in VARIAN if varian == parameter["varian"])

            def tulis(jawaban):
                return jawaban + tujuan
        assert _nilai(soal, tulis(soal.kunci)).benar
        for m in soal.malrule:
            u = _nilai(soal, tulis(m.jawaban))
            assert (u.benar, u.kode, u.malrule_id) == (False, m.kode, m.id)

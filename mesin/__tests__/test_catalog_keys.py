"""Regresi audit katalog: oracle dari fakta mentah, bukan rumus kunci lama."""
from fractions import Fraction

import pytest

from diagnosis import diagnosa
from generator import buat_soal


def angka(teks):
    return Fraction(teks.replace(",", "."))


@pytest.fixture(autouse=True)
def writer_katalog(monkeypatch):
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")


def _diagnosis(soal, jawaban):
    aturan = [dict(malrule_id=m.id, jawaban=m.jawaban, kode=m.kode, alasan=m.alasan)
              for m in soal.malrule]
    return diagnosa(soal.kunci, jawaban, "perhitungan sintetis", "", False,
                    aturan, soal.minta_restatement, soal=soal)


@pytest.mark.parametrize("level", ("P3", "P6"))
def test_umur_dari_perjalanan_waktu(level):
    varian = set()
    for seed in range(600):
        soal = buat_soal("soal_umur", seed, level, "logika")
        p = soal.parameter
        varian.add(p["tanya"])
        if p["tanya"] == "n_tahun":
            # Cari waktu yang memenuhi fakta; tidak membalik rumus sampler.
            solusi = [tahun for tahun in range(100)
                      if p["a"] + tahun == sum([p["b"] + tahun] * p["k"])]
        else:
            # Hitung berapa kelompok umur anak menyusun umur ayah saat itu.
            solusi = [rasio for rasio in range(1, 100)
                      if sum([p["b"] + p["n"]] * rasio) == p["a"] + p["n"]]
        assert len(solusi) == 1
        assert angka(soal.kunci) == solusi[0], (level, seed, p, soal.kunci, solusi)
        assert _diagnosis(soal, str(solusi[0])).benar
    assert varian == {"n_tahun", "kali_umur"}


@pytest.mark.parametrize("template", ("perbandingan_senilai", "perbandingan_berbalik", "kerja_bersama"))
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_konservasi_besaran_tanpa_pembulatan(template, level):
    for seed in range(600):
        soal = buat_soal(template, seed, level, "aritmatika-lanjut")
        p, jawaban = soal.parameter, angka(soal.kunci)
        if template == "perbandingan_senilai":
            # Kedua perbandingan harus menyatakan resep yang sama.
            assert jawaban / p["n"] == Fraction(p["q"], p["p"]), (seed, p, jawaban)
        elif template == "perbandingan_berbalik":
            # Jumlah unit kerja tidak berubah ketika pekerja diganti.
            assert sum([jawaban] * p["a2"]) == sum([p["b1"]] * p["a1"]), (seed, p, jawaban)
        else:
            # Pada waktu selesai kontribusi kedua pelaku tepat satu pekerjaan.
            assert jawaban / p["a"] + jawaban / p["b"] == 1, (seed, p, jawaban)


@pytest.mark.parametrize("template,level", (("lingkaran_keliling_luas", "P5"),
                                           ("lingkaran_keliling_luas", "P6"), ("juring", "P6")))
def test_geometri_memenuhi_pi_dan_bagian_putaran(template, level):
    for seed in range(600):
        soal = buat_soal(template, seed, level, "geometri-datar")
        p, jawaban = soal.parameter, angka(soal.kunci)
        pi = Fraction(22, 7) if p["r"] % 7 == 0 else Fraction("3.14")
        if template == "lingkaran_keliling_luas":
            pembagi = 2 * p["r"] if p["varian"] == "keliling" else p["r"] ** 2
            assert jawaban / pembagi == pi, (seed, p, jawaban)
        else:
            # Bandingkan bagian putaran dengan lingkaran penuh; keliling
            # juring harus terlebih dulu melepas dua sisi lurus.
            busur_atau_luas = jawaban if p["varian"] == "luas_juring" else jawaban - 2 * p["r"]
            penuh = pi * (p["r"] ** 2 if p["varian"] == "luas_juring" else 2 * p["r"])
            assert busur_atau_luas / penuh == Fraction(p["s"], 360), (seed, p, jawaban)


@pytest.mark.parametrize("level", ("P4", "P5"))
def test_paritas_teks_dan_persamaan_deret(level):
    for seed in range(600):
        soal = buat_soal("paritas", seed, level, "teori-bilangan")
        p = soal.parameter
        suku = list(range(p["a"], p["a"] + 2 * p["n"], 2))
        jenis = "ganjil" if p["a"] % 2 else "genap"
        assert f"bilangan {jenis}" in soal.teks, (seed, p, soal.teks)
        assert all(x % 2 == p["a"] % 2 for x in suku)
        assert 1 <= p["a"] <= 15 and 2 <= p["n"] <= 20
        assert angka(soal.kunci) == sum(suku)
        assert f"({suku[0]} + {suku[-1]}) : 2 = {sum(suku)}" in soal.pembahasan


@pytest.mark.parametrize("tid,seed,jawaban", (("perbandingan_senilai", 6, "16/5"),
    ("perbandingan_berbalik", 3, "12,50"), ("kerja_bersama", 15, "8/5")))
def test_diagnosis_pecahan_setara_dan_format_salah(tid, seed, jawaban):
    soal = buat_soal(tid, seed, "P5", "aritmatika-lanjut")
    assert _diagnosis(soal, jawaban).benar
    for buruk in ("1/0", "1+2", "1, 2", jawaban + " kg", "nan", "", "1e3"):
        assert not _diagnosis(soal, buruk).benar


def test_kontrak_presisi_tetap_terlihat_pada_visual(monkeypatch):
    from question_views import penyajian_dari_soal
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "geometri-datar")
    for tid in ("lingkaran_keliling_luas", "juring"):
        soal = buat_soal(tid, 0, "P6", "geometri-datar")
        assert "tanpa pembulatan" in penyajian_dari_soal(soal).teks_soal
        assert "tanpa pembulatan" in soal.teks


@pytest.mark.parametrize('pembilang,penyebut,teks', ((1,8,'0,125'),(-1,2,'-0,5'),
    (1,3,'1/3'),(4,2,'2'),(0,7,'0'),(314,100,'3,14')))
def test_format_rasional_eksak(pembilang,penyebut,teks):
    from catalog_exact import format_angka,baca_angka
    nilai=Fraction(pembilang,penyebut)
    assert format_angka(nilai)==teks
    assert baca_angka(teks)==nilai


def test_parser_eksak_tidak_diterapkan_ke_histori():
    from diagnosis import setara
    from templates import REGISTRI
    lama=REGISTRI['perbandingan_senilai'](p=5,q=1,n=8)
    assert not setara('4/2',lama.kunci,soal=lama)
    baru=REGISTRI['perbandingan_senilai'](p=5,q=1,n=8,versi_katalog=2)
    assert setara('8/5',baru.kunci,soal=baru)
    assert not setara('1,6001',baru.kunci,soal=baru)

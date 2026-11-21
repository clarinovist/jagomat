"""Tes template Latihan Lomba topik Bilangan (id berawalan `bil_`).

Dasar: jangkar soal contoh lomba, hitung ulang dari gambar SVG, pengecoh tulisan tangan,
kasus tepi, dan pembahasan yang konsisten dengan kunci.
"""
import itertools
import json
import random
import re
import xml.etree.ElementTree as ET

import pytest

import contest_core as C
import contest_templates  # noqa: F401  (mendaftarkan semua template)

ID_BILANGAN = (
    "bil_kartu_nilai_tempat", "bil_nilai_angka", "bil_genap_ganjil",
    "bil_pola_bertambah", "bil_dua_angka_jumlah", "bil_selisih_kartu",
    "bil_pola_berulang", "bil_syarat_jumlah_angka", "bil_cacah_syarat",
)
SEED_GAMBAR = 60
SEED_PEMBAHASAN = 200


def _t(template_id):
    return C.ambil(template_id)


def _soal(template_id, seed):
    return C.buat_soal(_t(template_id), random.Random(seed))


def _nilai_pengecoh(soal):
    return [p.nilai for p in soal.pengecoh]


def _label(soal, nilai):
    return next(p.kesalahan for p in soal.pengecoh if p.nilai == nilai)


def _atribut(svg, nama):
    return [e.get(nama) for e in ET.fromstring(svg).iter() if e.get(nama) is not None]


# --- f. tingkat dan jenis sesuai daftar tugas ----------------------------------------------

@pytest.mark.parametrize("template_id,jenis,tingkat", [
    ("bil_kartu_nilai_tempat", C.JENIS_PG, 1),
    ("bil_nilai_angka", C.JENIS_PG, 1),
    ("bil_genap_ganjil", C.JENIS_PG, 1),
    ("bil_pola_bertambah", C.JENIS_PG, 2),
    ("bil_dua_angka_jumlah", C.JENIS_ISIAN, 2),
    ("bil_selisih_kartu", C.JENIS_ISIAN, 2),
    ("bil_pola_berulang", C.JENIS_PG, 3),
    ("bil_syarat_jumlah_angka", C.JENIS_PG, 3),
    ("bil_cacah_syarat", C.JENIS_PG, 3),
])
def test_tingkat_dan_jenis_sesuai_daftar_tugas(template_id, jenis, tingkat):
    template = _t(template_id)
    assert (template.topik, template.jenis, template.tingkat) == ("bilangan", jenis, tingkat)


def test_sembilan_template_bilangan_terdaftar_tepat():
    terdaftar = {t.id for t in C.semua() if t.id.startswith("bil_")}
    assert terdaftar == set(ID_BILANGAN)


# --- a. jangkar PDF ------------------------------------------------------------------------

def test_jangkar_pdf_no_2_tiga_kartu_sepuluh_dan_tujuh_kartu_satu_bernilai_37():
    soal = _t("bil_kartu_nilai_tempat").bangun({"ratusan": 0, "puluhan": 3, "satuan": 7})
    assert soal.kunci == "37"
    assert set(_nilai_pengecoh(soal)) == {"73", "10", "310"}


def test_jangkar_pdf_no_5_nilai_angka_8_pada_6845_adalah_800():
    soal = _t("bil_nilai_angka").bangun({"angka": [6, 8, 4, 5], "tanya": 1})
    assert soal.kunci == "800"
    assert set(_nilai_pengecoh(soal)) == {"8", "80", "845"}


def test_jangkar_pdf_no_9_kartu_genap_dari_3_8_5_2_6_9_10_ada_4():
    soal = _t("bil_genap_ganjil").bangun({"kartu": [3, 8, 5, 2, 6, 9, 10], "jenis": "genap"})
    assert soal.kunci == "4"
    assert "3" in _nilai_pengecoh(soal) and "7" in _nilai_pengecoh(soal)


def test_jangkar_pdf_no_13_pola_permen_segitiga_ke_5_adalah_15():
    soal = _t("bil_pola_bertambah").bangun({"jenis": "segitiga", "m": 1, "n": 5})
    assert soal.kunci == "15"
    assert set(_nilai_pengecoh(soal)) == {"14", "30", "25"}


def test_jangkar_pdf_no_17_kartu_4_0_7_selisih_terbesar_terkecil_333():
    soal = _t("bil_selisih_kartu").bangun({"kartu": [4, 0, 7]})
    assert soal.kunci == "333"
    assert soal.jenis == C.JENIS_ISIAN and soal.pengecoh == ()


def test_jangkar_pdf_no_22_terkecil_jumlah_10_berbeda_semua_adalah_109():
    soal = _t("bil_syarat_jumlah_angka").bangun({"urutan": "terkecil", "k": 10})
    assert soal.kunci == "109"
    assert set(_nilai_pengecoh(soal)) == {"118", "127", "190"}


def test_jangkar_pdf_no_27_bilangan_10_sampai_50_puluhan_lebih_besar_ada_11():
    soal = _t("bil_cacah_syarat").bangun({"syarat": "puluhan_lebih", "a": 10, "b": 50})
    assert soal.kunci == "11"
    assert set(_nilai_pengecoh(soal)) == {"9", "15", "41"}


def test_jangkar_pdf_no_30_manik_merah_biru_biru_kuning_30_pertama_biru_15():
    soal = _t("bil_pola_berulang").bangun(
        {"pola": ["merah", "biru", "biru", "kuning"], "n": 30, "warna": "biru"})
    assert soal.kunci == "15"
    assert {"14", "16"} <= set(_nilai_pengecoh(soal))
    assert "sisa" in _label(soal, "14")


def test_jangkar_pdf_isian_1_dua_angka_berjumlah_5_ada_5():
    soal = _t("bil_dua_angka_jumlah").bangun({"angka": 2, "k": 5, "syarat": "tanpa"})
    assert soal.kunci == "5"


# --- b. gambar sesuai soal: hitung ulang dari SVG ------------------------------------------

@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_kartu_nilai_tempat_gambar_menjumlah_ke_kunci_dan_cocok_parameter(seed):
    soal = _soal("bil_kartu_nilai_tempat", seed)
    p = json.loads(soal.parameter)
    kartu = [int(x) for x in _atribut(soal.svg, "data-kartu")]
    assert kartu.count(100) == p["ratusan"]
    assert kartu.count(10) == p["puluhan"]
    assert kartu.count(1) == p["satuan"]
    assert sum(kartu) == int(soal.kunci)


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_nilai_angka_gambar_dan_teks_memberi_kunci(seed):
    soal = _soal("bil_nilai_angka", seed)
    angka = [int(x) for x in _atribut(soal.svg, "data-kartu")]
    ditanya = int(re.search(r"Nilai angka (\d) pada", soal.teks).group(1))
    assert angka.count(ditanya) == 1
    posisi = angka.index(ditanya)
    assert ditanya * 10 ** (len(angka) - 1 - posisi) == int(soal.kunci)


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_genap_ganjil_gambar_dan_teks_memberi_kunci(seed):
    soal = _soal("bil_genap_ganjil", seed)
    kartu = [int(x) for x in _atribut(soal.svg, "data-kartu")]
    sisa = 0 if "bilangan genap" in soal.teks else 1
    assert "bilangan ganjil" in soal.teks or sisa == 0
    assert sum(1 for k in kartu if k % 2 == sisa) == int(soal.kunci)
    assert 6 <= len(kartu) <= 8 and 0 not in kartu


def _hitung_per_pola(svg):
    akar = ET.fromstring(svg)
    return [sum(1 for c in g.iter() if c.get("data-permen"))
            for g in akar.iter() if g.get("data-pola")]


def _ekstrapolasi(banyak, n):
    selisih = [b - a for a, b in zip(banyak, banyak[1:])]
    selisih2 = [b - a for a, b in zip(selisih, selisih[1:])]
    assert len(set(selisih2)) == 1, "pola tergambar tidak beraturan"
    nilai, langkah = banyak[-1], selisih[-1]
    for _ in range(n - len(banyak)):
        langkah += selisih2[0]
        nilai += langkah
    return nilai


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_pola_bertambah_gambar_diekstrapolasi_sama_dengan_kunci(seed):
    soal = _soal("bil_pola_bertambah", seed)
    n = int(re.search(r"pola ke-(\d+)", soal.teks).group(1))
    banyak = _hitung_per_pola(soal.svg)
    assert len(banyak) == 4
    assert _ekstrapolasi(banyak, n) == int(soal.kunci)


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_pola_berulang_gambar_menghasilkan_kunci(seed):
    soal = _soal("bil_pola_berulang", seed)
    manik = _atribut(soal.svg, "data-manik")
    n, warna = re.search(r"antara (\d+) manik pertama, ada berapa manik (\w+)\?", soal.teks).groups()
    periode = next(p for p in range(1, len(manik) + 1)
                   if all(manik[i] == manik[i % p] for i in range(len(manik))))
    assert int(n) % periode != 0
    ke_n = [manik[i % periode] for i in range(int(n))]
    assert ke_n.count(warna) == int(soal.kunci)
    assert len(manik) >= 2 * periode


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_selisih_kartu_gambar_memberi_kunci_dengan_brute_force(seed):
    soal = _soal("bil_selisih_kartu", seed)
    kartu = [int(x) for x in _atribut(soal.svg, "data-kartu")]
    assert len(kartu) == 3
    bilangan = [100 * a + 10 * b + c for a, b, c in itertools.permutations(kartu) if a != 0]
    assert max(bilangan) - min(bilangan) == int(soal.kunci)


# --- c. pengecoh bermakna (ditulis tangan) -------------------------------------------------

def test_pengecoh_kartu_tanpa_puluhan_dan_hanya_tiga_yang_sah():
    soal = _t("bil_kartu_nilai_tempat").bangun({"ratusan": 2, "puluhan": 0, "satuan": 5})
    assert soal.kunci == "205"
    assert set(_nilai_pengecoh(soal)) == {"250", "7", "5"}
    assert "menukar" in _label(soal, "250")
    assert "ratusan" in _label(soal, "5")


def test_pengecoh_kartu_menggabungkan_banyak_kartu_dengan_tulisan_10():
    soal = _t("bil_kartu_nilai_tempat").bangun({"ratusan": 0, "puluhan": 3, "satuan": 7})
    assert "10" in _label(soal, "310") and "puluhan" in _label(soal, "310")
    assert "menjumlah" in _label(soal, "10")


def test_pengecoh_nilai_angka_di_tempat_ratusan_paling_kiri():
    soal = _t("bil_nilai_angka").bangun({"angka": [7, 2, 5], "tanya": 0})
    assert soal.kunci == "700"
    assert _nilai_pengecoh(soal) == ["7", "70", "725"]
    assert "angkanya sendiri" in _label(soal, "7")


def test_pengecoh_nilai_angka_tanpa_pengecoh_cukup_diulang_sebagai_parametertidaksah():
    with pytest.raises(C.ParameterTidakSah):
        _t("bil_nilai_angka").bangun({"angka": [9, 0, 3], "tanya": 2})


def test_pengecoh_genap_ganjil_tanpa_kartu_10():
    soal = _t("bil_genap_ganjil").bangun({"kartu": [1, 3, 5, 2, 4, 7], "jenis": "ganjil"})
    assert soal.kunci == "4"
    assert _nilai_pengecoh(soal) == ["2", "6", "5"]
    assert "bukan ganjil" in _label(soal, "2")


def test_pengecoh_pola_tambah_tetap_berhenti_terlalu_cepat_dan_terlalu_jauh():
    soal = _t("bil_pola_bertambah").bangun({"jenis": "tambah", "a": 2, "d": 3, "n": 6})
    assert soal.kunci == "17"
    assert _nilai_pengecoh(soal) == ["14", "20", "18"]
    assert "terlalu cepat" in _label(soal, "14")


def test_pengecoh_pola_berulang_membulatkan_ke_atas_dan_lupa_sisa():
    soal = _t("bil_pola_berulang").bangun(
        {"pola": ["hijau", "merah", "hijau", "biru", "biru"], "n": 23, "warna": "hijau"})
    assert soal.kunci == "10"
    assert _nilai_pengecoh(soal) == ["8", "12", "7"]
    assert "sisa" in _label(soal, "8")


def test_pengecoh_syarat_jumlah_angka_terbesar_memuat_kembar_kedua_dan_tukar():
    soal = _t("bil_syarat_jumlah_angka").bangun({"urutan": "terbesar", "k": 20})
    assert soal.kunci == "983"
    assert _nilai_pengecoh(soal) == ["992", "974", "938"]
    assert "kembar" in _label(soal, "992")
    assert "menukar" in _label(soal, "938")


def test_pengecoh_cacah_syarat_kembar_memakai_selisih_satu_dan_semua_bilangan():
    soal = _t("bil_cacah_syarat").bangun({"syarat": "kembar", "a": 11, "b": 55})
    assert soal.kunci == "5"
    assert _nilai_pengecoh(soal) == ["3", "13", "45"]
    assert "batas" in _label(soal, "3")


# --- d. kasus tepi -------------------------------------------------------------------------

def test_tepi_kartu_nilai_tempat_tanpa_ratusan_tidak_menggambar_kartu_100():
    soal = _t("bil_kartu_nilai_tempat").bangun({"ratusan": 0, "puluhan": 4, "satuan": 2})
    assert "100" not in _atribut(soal.svg, "data-kartu")
    assert "kartu 100" not in soal.teks
    assert soal.kunci == "42"


def test_tepi_kartu_nilai_tempat_tanpa_puluhan_tetap_jujur():
    soal = _t("bil_kartu_nilai_tempat").bangun({"ratusan": 3, "puluhan": 0, "satuan": 5})
    assert soal.kunci == "305"
    assert "10" not in _atribut(soal.svg, "data-kartu")


def test_tepi_nilai_angka_bilangan_memuat_nol_nilai_tempat_tetap_benar():
    soal = _t("bil_nilai_angka").bangun({"angka": [3, 0, 8, 5], "tanya": 2})
    assert soal.kunci == "80"
    assert "0" in _atribut(soal.svg, "data-kartu")


def test_tepi_genap_ganjil_semua_kartu_dua_digit_hanya_10():
    soal = _t("bil_genap_ganjil").bangun({"kartu": [10, 1, 3, 5, 7, 9], "jenis": "genap"})
    assert soal.kunci == "1"
    assert "10" in _atribut(soal.svg, "data-kartu")


def test_tepi_sampler_genap_ganjil_tidak_pernah_memakai_nol_atau_di_atas_10():
    for seed in range(200):
        p = _t("bil_genap_ganjil").sampler(random.Random(seed))
        assert all(1 <= v <= 10 for v in p["kartu"]) and len(set(p["kartu"])) == len(p["kartu"])


def test_tepi_pola_segitiga_berlipat_dua_memberi_28_pada_pola_ke_n_enam():
    soal = _t("bil_pola_bertambah").bangun({"jenis": "segitiga", "m": 2, "n": 6})
    assert soal.kunci == "42"
    assert _hitung_per_pola(soal.svg) == [2, 6, 12, 20]


def test_tepi_pola_berulang_sisa_tanpa_warna_yang_ditanya():
    soal = _t("bil_pola_berulang").bangun(
        {"pola": ["merah", "biru", "kuning"], "n": 21 + 1, "warna": "kuning"})
    assert soal.kunci == "7"
    assert "tidak memuat" in soal.pembahasan[-2]


def test_tepi_pola_berulang_sampler_menolak_pola_berperiode_lebih_kecil():
    diterima = 0
    for seed in range(300):
        try:
            p = _t("bil_pola_berulang").sampler(random.Random(seed))
        except C.ParameterTidakSah:
            continue
        diterima += 1
        pola = p["pola"]
        assert len(set(pola)) >= 2 and p["n"] % len(pola) != 0
        assert not any(len(pola) % d == 0 and pola == pola[:d] * (len(pola) // d)
                       for d in range(1, len(pola)))
    assert diterima > 50


@pytest.mark.parametrize("k,terkecil,terbesar", [(3, "102", "210"), (24, "789", "987")])
def test_tepi_syarat_jumlah_angka_ujung_rentang_k(k, terkecil, terbesar):
    assert _t("bil_syarat_jumlah_angka").bangun({"urutan": "terkecil", "k": k}).kunci == terkecil
    assert _t("bil_syarat_jumlah_angka").bangun({"urutan": "terbesar", "k": k}).kunci == terbesar


def test_tepi_cacah_syarat_ditolak_bila_kedua_batas_tidak_memenuhi_syarat():
    with pytest.raises(C.ParameterTidakSah):
        _t("bil_cacah_syarat").bangun({"syarat": "kembar", "a": 12, "b": 54})


def test_tepi_cacah_syarat_jumlah_angka_memakai_k():
    soal = _t("bil_cacah_syarat").bangun({"syarat": "jumlah_k", "a": 19, "b": 40, "k": 10})
    assert soal.kunci == "3"      # 19, 28, 37
    assert "jumlah kedua angkanya 10" in soal.teks


def test_tepi_dua_angka_jumlah_nol_boleh_di_satuan_tetapi_bukan_di_depan():
    soal = _t("bil_dua_angka_jumlah").bangun({"angka": 2, "k": 2, "syarat": "tanpa"})
    assert soal.kunci == "2"       # 11 dan 20 (02 bukan bilangan dua angka)


def test_tepi_dua_angka_jumlah_tiga_angka_dengan_syarat_genap():
    soal = _t("bil_dua_angka_jumlah").bangun({"angka": 3, "k": 4, "syarat": "genap"})
    assert soal.kunci == "6"       # 112, 130, 202, 220, 310, 400
    assert "tiga angka" in soal.teks and "genap" in soal.teks


def test_tepi_dua_angka_jumlah_berbeda_dua_angka():
    assert _t("bil_dua_angka_jumlah").bangun(
        {"angka": 2, "k": 6, "syarat": "berbeda"}).kunci == "5"   # 15,24,42,51,60


def test_tepi_selisih_kartu_nol_ditempatkan_bukan_di_depan():
    assert _t("bil_selisih_kartu").bangun({"kartu": [0, 5, 5]}).kunci == "45"   # 550 - 505


def test_tepi_selisih_kartu_hanya_satu_susunan_diulang_sebagai_parametertidaksah():
    for kartu in ([0, 0, 5], [3, 3, 3], [0, 0, 0]):
        with pytest.raises(C.ParameterTidakSah):
            _t("bil_selisih_kartu").bangun({"kartu": kartu})


# --- e. pembahasan konsisten ---------------------------------------------------------------

@pytest.mark.parametrize("template_id", ID_BILANGAN)
def test_pembahasan_langkah_terakhir_memuat_kunci_dan_tidak_ada_langkah_kosong(template_id):
    for seed in range(SEED_PEMBAHASAN):
        soal = _soal(template_id, seed)
        assert 1 <= len(soal.pembahasan) <= C.MAKS_LANGKAH
        assert all(langkah.strip() for langkah in soal.pembahasan)
        assert soal.kunci in soal.pembahasan[-1], (soal.parameter, soal.pembahasan)


@pytest.mark.parametrize("template_id", ID_BILANGAN)
def test_soal_isian_tanpa_pengecoh_dan_pg_punya_tiga_pengecoh_berlabel(template_id):
    for seed in range(20):
        soal = _soal(template_id, seed)
        if soal.jenis == C.JENIS_ISIAN:
            assert soal.pengecoh == ()
        else:
            assert len(soal.pengecoh) == 3
            assert all(p.kesalahan.strip() for p in soal.pengecoh)


@pytest.mark.parametrize("template_id", ID_BILANGAN)
def test_teks_tanpa_markup_dan_dalam_batas_panjang(template_id):
    for seed in range(50):
        soal = _soal(template_id, seed)
        assert "<" not in soal.teks and ">" not in soal.teks
        assert len(soal.teks) <= C.MAKS_TEKS

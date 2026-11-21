"""Tes template Operasi Hitung (Latihan Lomba): jangkar PDF, gambar dihitung ulang, pengecoh, tepi."""
import json
import random
import re
import xml.etree.ElementTree as ET

import pytest

import contest_core as C
import contest_templates

KATALOG = {t.id: t for t in contest_templates.katalog() if t.id.startswith("ops_")}
SEED = range(40)
SEED_PEMBAHASAN = range(200)
MINUS = "−"
KAKI = {"ayam": 2, "bebek": 2, "sapi": 4, "kambing": 4, "kucing": 4}
INGGRIS = {"ops_inggris_dua_langkah", "ops_inggris_jumlah_selisih"}
# id: (jenis, tingkat)
METADATA = {
    "ops_hitung_gambar": ("pg", 1), "ops_kaki_hewan": ("pg", 1),
    "ops_kotak_kosong": ("pg", 2), "ops_cerita_dua_langkah": ("pg", 2),
    "ops_berbagi_sisa": ("isian", 2), "ops_inggris_dua_langkah": ("pg", 2),
    "ops_deret_pasangan": ("pg", 3), "ops_jumlah_selisih": ("pg", 3), "ops_umur": ("pg", 3),
    "ops_ayam_kambing": ("isian", 3), "ops_inggris_jumlah_selisih": ("pg", 3),
}


def soal_dari(template_id, **parameter):
    """Bangun soal dari parameter tulisan tangan lewat putaran JSON seperti `buat_soal`."""
    return KATALOG[template_id].bangun(json.loads(C.kanonik(parameter)))


def soal_acak(template_id, seed):
    return C.buat_soal(KATALOG[template_id], random.Random(seed))


def peta_pengecoh(soal):
    return {p.nilai: p.kesalahan for p in soal.pengecoh}


def elemen_objek(svg):
    akar = ET.fromstring(svg)
    return [e for e in akar.iter() if "data-objek" in e.attrib], akar


def tanda_operasi(akar):
    """Tanda + / − pada gambar, urut dari kiri ke kanan."""
    tanda = [(float(e.attrib["x"]), e.text) for e in akar.iter()
             if e.tag.endswith("text") and e.text in ("+", MINUS)]
    return [t for _, t in sorted(tanda)]


def test_kesebelas_template_terdaftar_dengan_jenis_dan_tingkat_sesuai_tugas():
    assert set(KATALOG) == set(METADATA)
    for template_id, (jenis, tingkat) in METADATA.items():
        assert (KATALOG[template_id].jenis, KATALOG[template_id].tingkat) == (jenis, tingkat)
        assert KATALOG[template_id].topik == "operasi"


def test_hanya_dua_template_berbahasa_inggris_dan_tanpa_gambar_pilihan():
    for template_id in KATALOG:
        for seed in range(5):
            soal = soal_acak(template_id, seed)
            assert soal.inggris == (template_id in INGGRIS)
            assert soal.kunci_svg == "" and all(p.svg == "" for p in soal.pengecoh)


# ------------------------------------------------------------------ jangkar PDF
def test_jangkar_pdf_1_hitung_gambar_9_tambah_6_kurang_7_adalah_8():
    soal = soal_dari("ops_hitung_gambar", benda=0, n=[9, 6, 7], op=["+", "-"])
    peta = peta_pengecoh(soal)
    assert soal.kunci == "8"
    assert "operasi kedua" in peta["22"]            # 9 + 6 + 7
    assert "langkah kedua" in peta["15"]            # berhenti di 9 + 6


def test_jangkar_pdf_7_kaki_tiga_ayam_dua_sapi_adalah_14():
    soal = soal_dari("ops_kaki_hewan", daftar=[["ayam", 3], ["sapi", 2]])
    peta = peta_pengecoh(soal)
    assert soal.kunci == "14"
    assert set(peta) == {"5", "20", "10"}
    assert "banyak hewan" in peta["5"] and "berkaki 4" in peta["20"] and "berkaki 2" in peta["10"]


def test_jangkar_pdf_11_ibu_ambil_2_dari_23_sisanya_untuk_3_anak_adalah_7():
    soal = soal_dari("ops_berbagi_sisa", benda=0, awal=23, ambil=2, anak=3)
    assert soal.kunci == "7"
    assert "kue" in soal.teks and "3 anak" in soal.teks


def test_jangkar_pdf_15_cerita_indonesia_45_kurang_18_tambah_12_adalah_39():
    soal = soal_dari("ops_cerita_dua_langkah", nama="Siti", benda="kelereng", pola="kt",
                     aksi=0, a=45, b=18, c=12)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "39"
    assert "langkah kedua" in peta["27"] and "kedua tanda" in peta["51"]
    assert "45 butir kelereng" in soal.teks and "18 butir kelereng" in soal.teks


def test_jangkar_pdf_15_versi_inggris_sederhana_adalah_39():
    soal = soal_dari("ops_inggris_dua_langkah", nama="Siti", benda=0, pola="kt", aksi=0,
                     a=45, b=18, c=12)
    assert soal.kunci == "39" and soal.inggris
    assert set(peta_pengecoh(soal)) == {"27", "15", "51"}
    assert soal.teks == "Siti has 45 marbles. Siti gives away 18, then buys 12. " \
                        "How many marbles does Siti have now?"


def test_jangkar_pdf_18_kotak_kosong_kali_6_kurang_15_sama_33_adalah_8():
    soal = soal_dari("ops_kotak_kosong", lambang=0, a=6, b=15, c=33, bentuk="kurang", balik=0)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "8"
    assert soal.teks.startswith("\U0001F381 × 6 − 15 = 33.")
    assert "membalik" in peta["3"]                   # (33 - 15) / 6
    assert "sebelum membagi" in peta["48"]           # 33 + 15 lupa dibagi 6


def test_jangkar_pdf_23_deret_genap_2_sampai_20_adalah_110():
    soal = soal_dari("ops_deret_pasangan", awal=2, beda=2, suku=10)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "110"
    assert soal.teks == "2 + 4 + 6 + 8 + 10 + 12 + 14 + 16 + 18 + 20 = ..."
    assert "banyak suku" in peta["220"] and "satu pasangan" in peta["88"]
    assert "22" in soal.pembahasan[0] and "5 pasangan" in soal.pembahasan[2]


def test_jangkar_pdf_24_jumlah_30_selisih_8_yang_besar_adalah_19():
    soal = soal_dari("ops_jumlah_selisih", mode="cerita", tanya="besar", jumlah=30, selisih=8,
                     idx=0, n1="Rudi", n2="Dina")
    peta = peta_pengecoh(soal)
    assert soal.kunci == "19"
    assert set(peta) == {"22", "15", "11"}
    assert "tanpa membagi dua" in peta["22"] and "tanpa memakai selisih" in peta["15"]
    assert "lebih kecil" in peta["11"]


def test_jangkar_pdf_24_versi_inggris_dengan_lambang_kucing_dan_anjing_adalah_19():
    soal = soal_dari("ops_inggris_jumlah_selisih", tanya="besar", jumlah=30, selisih=8, idx=1)
    assert soal.kunci == "19" and soal.inggris
    assert set(peta_pengecoh(soal)) == {"22", "15", "11"}
    assert soal.teks == f"If \U0001F431 + \U0001F436 = 30 and \U0001F431 {MINUS} \U0001F436 = 8, " \
                        f"then \U0001F431 = ..."


def test_jangkar_pdf_28_umur_12_dan_5_jumlah_33_adalah_8_tahun_lagi():
    soal = soal_dari("ops_umur", n1="Rudi", n2="Dina", a=12, b=5, jumlah=33)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "8"
    assert "tanpa membagi dua" in peta["16"] and "dengan 4" in peta["4"]


def test_jangkar_pdf_isian_2_sepuluh_kepala_dua_puluh_delapan_kaki_empat_kambing():
    soal = soal_dari("ops_ayam_kambing", dua="ayam", empat="kambing", kepala=10, kaki=28)
    assert soal.kunci == "4"
    assert "10 kepala" in soal.teks and "28 kaki" in soal.teks and "kambing" in soal.teks


# ------------------------------------------------------------------ gambar dihitung ulang
@pytest.mark.parametrize("seed", SEED)
def test_gambar_hitung_menghasilkan_kunci_dan_cocok_dengan_parameter(seed):
    soal = soal_acak("ops_hitung_gambar", seed)
    parameter = json.loads(soal.parameter)
    elemen, akar = elemen_objek(soal.svg)
    kelompok = [sum(1 for e in elemen if e.attrib["data-kelompok"] == str(i)) for i in range(3)]
    tanda = tanda_operasi(akar)
    hasil = kelompok[0]
    for operasi, banyak in zip(tanda, kelompok[1:]):
        hasil = hasil + banyak if operasi == "+" else hasil - banyak
    assert kelompok == parameter["n"] and len(elemen) == sum(kelompok)
    assert tanda == [MINUS if t == "-" else "+" for t in parameter["op"]]
    assert len({e.attrib["data-objek"] for e in elemen}) == 1
    assert str(hasil) == soal.kunci


@pytest.mark.parametrize("seed", SEED)
def test_gambar_kaki_hewan_kakinya_dihitung_dari_gambar_sama_dengan_kunci(seed):
    soal = soal_acak("ops_kaki_hewan", seed)
    parameter = json.loads(soal.parameter)
    elemen, _ = elemen_objek(soal.svg)
    cacah = {}
    for e in elemen:
        cacah[e.attrib["data-objek"]] = cacah.get(e.attrib["data-objek"], 0) + 1
    assert cacah == {nama: banyak for nama, banyak in parameter["daftar"]}
    assert len(cacah) == 2
    assert str(sum(KAKI[nama] * banyak for nama, banyak in cacah.items())) == soal.kunci


@pytest.mark.parametrize("seed", SEED)
def test_gambar_berbagi_sisa_benda_dan_anak_sesuai_parameter_dan_kunci(seed):
    soal = soal_acak("ops_berbagi_sisa", seed)
    parameter = json.loads(soal.parameter)
    elemen, _ = elemen_objek(soal.svg)
    anak = sum(1 for e in elemen if e.attrib["data-objek"] == "anak")
    benda = len(elemen) - anak
    assert (benda, anak) == (parameter["awal"], parameter["anak"])
    assert (benda - parameter["ambil"]) % anak == 0
    assert str((benda - parameter["ambil"]) // anak) == soal.kunci


# ------------------------------------------------------------------ pengecoh tulisan tangan
def test_pengecoh_hitung_gambar_urutan_operasi_kurang_tambah():
    soal = soal_dari("ops_hitung_gambar", benda=1, n=[10, 3, 4], op=["-", "+"])
    peta = peta_pengecoh(soal)
    assert soal.kunci == "11"
    assert "operasi kedua" in peta["3"]              # 10 - 3 - 4
    assert "operasi pertama" in peta["17"]           # 10 + 3 + 4
    assert "langkah kedua" in peta["7"]              # berhenti di 10 - 3


def test_pengecoh_hitung_gambar_dua_penjumlahan():
    soal = soal_dari("ops_hitung_gambar", benda=2, n=[5, 4, 3], op=["+", "+"])
    peta = peta_pengecoh(soal)
    assert soal.kunci == "12"
    assert set(peta) == {"6", "4", "9"}
    assert "operasi kedua" in peta["6"] and "operasi pertama" in peta["4"]
    assert "langkah kedua" in peta["9"]


def test_pengecoh_kotak_kosong_bentuk_tambah_membalik_dengan_tanda_salah():
    soal = soal_dari("ops_kotak_kosong", lambang=1, a=4, b=8, c=36, bentuk="tambah", balik=1)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "7"
    assert soal.teks.startswith("4 × \U0001F34E + 8 = 36.")
    assert "membalik" in peta["11"]                  # (36 + 8) / 4
    assert "sebelum membagi" in peta["28"] and "mengabaikan 8" in peta["9"]


def test_pengecoh_cerita_tambah_kurang_lupa_langkah_kedua_dan_balik_tanda():
    soal = soal_dari("ops_cerita_dua_langkah", nama="Budi", benda="stiker", pola="tk", aksi=1,
                     a=30, b=12, c=20)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "22"
    assert "langkah kedua" in peta["42"]             # 30 + 12
    assert "menambah juga" in peta["62"]             # 30 + 12 + 20
    assert "kedua tanda" in peta["38"]               # 30 - 12 + 20


def test_pengecoh_jumlah_selisih_bila_yang_kecil_ditanya():
    soal = soal_dari("ops_jumlah_selisih", mode="lambang", tanya="kecil", jumlah=30, selisih=8,
                     idx=3, n1="", n2="")
    peta = peta_pengecoh(soal)
    assert soal.kunci == "11"
    assert soal.teks == f"⚽ + \U0001F3C0 = 30. ⚽ {MINUS} \U0001F3C0 = 8. Nilai \U0001F3C0 adalah ..."
    assert "tanpa membagi dua" in peta["22"] and "lebih besar" in peta["19"]


def test_pengecoh_umur_bukan_pembagian_dua_dan_selisih_satu():
    soal = soal_dari("ops_umur", n1="Kia", n2="Budi", a=10, b=6, jumlah=40)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "12"
    assert "tanpa membagi dua" in peta["24"] and "dengan 4" in peta["6"]


def test_pengecoh_deret_lupa_satu_pasangan_dan_pasangan_berlebih():
    soal = soal_dari("ops_deret_pasangan", awal=1, beda=2, suku=8)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "64"
    assert "banyak suku" in peta["128"] and "lupa satu pasangan" in peta["48"]
    assert "terlalu banyak" in peta["80"]


def test_pengecoh_kaki_hewan_bebek_dan_kucing_dengan_urutan_jenis_terbalik():
    soal = soal_dari("ops_kaki_hewan", daftar=[["kucing", 3], ["bebek", 4]])
    peta = peta_pengecoh(soal)
    assert soal.kunci == "20"
    assert set(peta) == {"7", "28", "14"}
    assert "banyak hewan" in peta["7"] and "berkaki 4" in peta["28"] and "berkaki 2" in peta["14"]


def test_pengecoh_inggris_dua_langkah_pola_tambah_kurang():
    soal = soal_dari("ops_inggris_dua_langkah", nama="Dina", benda=3, pola="tk", aksi=1,
                     a=30, b=12, c=20)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "22" and soal.inggris
    assert set(peta) == {"42", "62", "38"}
    assert "langkah kedua" in peta["42"] and "menambah juga" in peta["62"]
    assert "kedua tanda" in peta["38"]


def test_pengecoh_inggris_jumlah_selisih_bila_yang_kecil_ditanya():
    soal = soal_dari("ops_inggris_jumlah_selisih", tanya="kecil", jumlah=30, selisih=8, idx=0)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "11" and soal.inggris
    assert set(peta) == {"22", "19", "15"}
    assert "tanpa membagi dua" in peta["22"] and "lebih besar" in peta["19"]


def test_pengecoh_inggris_jumlah_selisih_jumlah_ganjil_tanpa_separuh_jumlah():
    soal = soal_dari("ops_inggris_jumlah_selisih", tanya="kecil", jumlah=25, selisih=11, idx=2)
    peta = peta_pengecoh(soal)
    assert soal.kunci == "7"
    assert set(peta) == {"14", "18", "11"}
    assert soal.teks == f"If \U0001F34C + \U0001F347 = 25 and \U0001F34C {MINUS} \U0001F347 = 11, " \
                        f"then \U0001F347 = ..."


# ------------------------------------------------------------------ kasus tepi
def test_tepi_hitung_gambar_semua_pola_operator_muncul_dan_hasil_selalu_positif():
    pola = set()
    for seed in range(300):
        soal = soal_acak("ops_hitung_gambar", seed)
        pola.add(tuple(json.loads(soal.parameter)["op"]))
        assert int(soal.kunci) >= 1
    assert pola == {("+", "-"), ("-", "+"), ("+", "+"), ("-", "-")}


def test_tepi_inggris_dua_langkah_kata_kerja_tiap_pola_dan_hasil_positif():
    tk = soal_dari("ops_inggris_dua_langkah", nama="Raka", benda=5, pola="tk", aksi=0, a=20, b=5, c=24)
    kt = soal_dari("ops_inggris_dua_langkah", nama="Maya", benda=2, pola="kt", aksi=2, a=21, b=20, c=5)
    assert tk.kunci == "1" and tk.teks == ("Raka has 20 books. Raka buys 5 more, then gives away 24. "
                                           "How many books does Raka have now?")
    assert kt.kunci == "6" and "sells 20, then gets 5 more" in kt.teks
    for seed in range(300):
        assert int(soal_acak("ops_inggris_dua_langkah", seed).kunci) >= 1


def test_tepi_inggris_jumlah_selisih_selisih_terbesar_dan_kecil_satu():
    soal = soal_dari("ops_inggris_jumlah_selisih", tanya="besar", jumlah=26, selisih=12, idx=4)
    assert soal.kunci == "19" and "then \U0001F430 = ..." in soal.teks
    assert int(soal_dari("ops_inggris_jumlah_selisih", tanya="kecil", jumlah=8, selisih=2, idx=0).kunci) == 3
    for seed in range(300):
        parameter = json.loads(soal_acak("ops_inggris_jumlah_selisih", seed).parameter)
        assert parameter["jumlah"] > parameter["selisih"] and (parameter["jumlah"] - parameter["selisih"]) % 2 == 0


def test_tepi_kaki_hewan_paling_sedikit_dan_paling_banyak():
    kecil = soal_dari("ops_kaki_hewan", daftar=[["bebek", 1], ["kucing", 1]])
    besar = soal_dari("ops_kaki_hewan", daftar=[["ayam", 6], ["kambing", 5]])
    assert (kecil.kunci, besar.kunci) == ("6", "32")
    assert len(elemen_objek(besar.svg)[0]) == 11


def test_tepi_kotak_kosong_urutan_kali_dan_dua_bentuk_muncul_di_seed_acak():
    teks = [soal_acak("ops_kotak_kosong", seed).teks for seed in range(200)]
    assert any(re.match(r"\S+ × \d+", t) for t in teks) and any(re.match(r"\d+ × \S+", t) for t in teks)
    assert any(f" {MINUS} " in t for t in teks) and any(" + " in t.split("=")[0] for t in teks)


def test_tepi_cerita_uang_berformat_rupiah_titik_ribuan_dan_konsisten_di_semua_pilihan():
    soal = soal_dari("ops_cerita_dua_langkah", nama="Tia", benda="uang", pola="tk", aksi=0,
                     a=90, b=5, c=20)
    semua = [soal.kunci] + [p.nilai for p in soal.pengecoh]
    assert soal.kunci == "Rp75.000" and soal.nilai is None
    assert all(re.fullmatch(r"Rp\d{1,3}(\.\d{3})+", nilai) for nilai in semua)
    assert "Rp90.000" in soal.teks and "Rp5.000" in soal.teks


def test_tepi_cerita_uang_dan_benda_keduanya_muncul_dan_uang_tak_bernilai_angka():
    soal_semua = [soal_acak("ops_cerita_dua_langkah", seed) for seed in range(200)]
    uang = [s for s in soal_semua if s.kunci.startswith("Rp")]
    benda = [s for s in soal_semua if s.kunci.isdigit()]
    assert uang and benda and all(s.nilai is None for s in uang)
    assert all(s.nilai == int(s.kunci) for s in benda)


def test_tepi_deret_terpendek_enam_suku_dari_satu_dan_ujung_ujung_sama():
    soal = soal_dari("ops_deret_pasangan", awal=1, beda=1, suku=6)
    assert soal.kunci == "21"
    assert soal.teks == "1 + 2 + 3 + 4 + 5 + 6 = ..."


def test_tepi_deret_kelipatan_lima_dan_beda_sepuluh():
    assert soal_dari("ops_deret_pasangan", awal=5, beda=5, suku=8).kunci == "180"
    assert soal_dari("ops_deret_pasangan", awal=10, beda=10, suku=12).kunci == "780"


def test_tepi_ayam_kambing_hampir_semua_empat_kaki_dan_hampir_semua_dua_kaki():
    hampir_empat = soal_dari("ops_ayam_kambing", dua="bebek", empat="sapi", kepala=8, kaki=30)
    hampir_dua = soal_dari("ops_ayam_kambing", dua="ayam", empat="kucing", kepala=20, kaki=44)
    assert (hampir_empat.kunci, hampir_dua.kunci) == ("7", "2")


def test_tepi_ayam_kambing_hanya_ada_satu_pembagian_untuk_seribu_seed():
    for seed in range(1000):
        p = json.loads(soal_acak("ops_ayam_kambing", seed).parameter)
        cocok = [k for k in range(p["kepala"] + 1)
                 if 2 * (p["kepala"] - k) + 4 * k == p["kaki"] and 1 <= k <= p["kepala"] - 1]
        assert len(cocok) == 1


def test_tepi_parameter_tidak_masuk_akal_ditolak_sebagai_parameter_tidak_sah():
    with pytest.raises(C.ParameterTidakSah):
        soal_dari("ops_umur", n1="Kia", n2="Budi", a=10, b=6, jumlah=39)       # selisih ganjil
    with pytest.raises(C.ParameterTidakSah):
        soal_dari("ops_berbagi_sisa", benda=0, awal=23, ambil=1, anak=3)        # tidak habis dibagi
    with pytest.raises(C.ParameterTidakSah):
        soal_dari("ops_ayam_kambing", dua="ayam", empat="sapi", kepala=10, kaki=29)


def test_pembahasan_jumlah_selisih_cerita_ditutup_kalimat_cerita_bukan_nilai_benda():
    soal = soal_dari("ops_jumlah_selisih", mode="cerita", tanya="besar", jumlah=25, selisih=11,
                     idx=3, n1="Siti", n2="Joko")
    assert soal.pembahasan[-1] == "Jadi permen Siti ada 18."


def test_tepi_jumlah_selisih_jumlah_ganjil_tidak_memakai_pengecoh_separuh_jumlah():
    soal = soal_dari("ops_jumlah_selisih", mode="lambang", tanya="besar", jumlah=25, selisih=11,
                     idx=0, n1="", n2="")
    assert soal.kunci == "18"
    assert all("tanpa memakai selisih" not in p.kesalahan for p in soal.pengecoh)


# ------------------------------------------------------------------ nama, bahasa, pembahasan
@pytest.mark.parametrize("template_id", ["ops_cerita_dua_langkah", "ops_inggris_dua_langkah",
                                         "ops_jumlah_selisih", "ops_umur"])
def test_nama_dalam_cerita_hanya_dari_daftar_nama_anak(template_id):
    for seed in range(100):
        parameter = json.loads(soal_acak(template_id, seed).parameter)
        for kunci in ("nama", "n1", "n2"):
            if parameter.get(kunci):
                assert parameter[kunci] in C.NAMA_ANAK


def test_nama_umur_dan_jumlah_selisih_selalu_dua_orang_berbeda():
    for seed in range(200):
        for template_id in ("ops_umur", "ops_jumlah_selisih"):
            parameter = json.loads(soal_acak(template_id, seed).parameter)
            if parameter.get("n1"):
                assert parameter["n1"] != parameter["n2"]


@pytest.mark.parametrize("template_id", sorted(INGGRIS))
def test_soal_inggris_memakai_kata_sederhana_tanpa_kata_indonesia_umum(template_id):
    for seed in range(100):
        teks = soal_acak(template_id, seed).teks
        assert re.search(r"\b(How many|If)\b", teks)
        assert not re.search(r"\b(berapa|punya|dan|adalah|lebih)\b", teks, re.IGNORECASE)


@pytest.mark.parametrize("template_id", sorted(KATALOG))
def test_pembahasan_memuat_kunci_di_langkah_terakhir_dan_tanpa_langkah_kosong(template_id):
    for seed in SEED_PEMBAHASAN:
        soal = soal_acak(template_id, seed)
        assert soal.pembahasan and all(baris.strip() for baris in soal.pembahasan)
        assert soal.kunci in soal.pembahasan[-1], (soal.teks, soal.pembahasan)


@pytest.mark.parametrize("template_id", sorted(KATALOG))
def test_teks_tanpa_markup_dan_aria_label_gambar_tanpa_angka(template_id):
    for seed in range(60):
        soal = soal_acak(template_id, seed)
        assert "<" not in soal.teks and ">" not in soal.teks
        if soal.svg:
            assert not re.search(r"aria-label=\"[^\"]*[0-9]", soal.svg)

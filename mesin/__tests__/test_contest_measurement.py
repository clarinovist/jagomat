"""Tes template Pengukuran Latihan Lomba: jangkar PDF, gambar dibaca ulang, pengecoh, kasus tepi."""
import datetime
import json
import math
import random
import re
import xml.etree.ElementTree as ET

import pytest

import contest_core as C
import contest_templates

NS = "{http://www.w3.org/2000/svg}"
SEED_GAMBAR = 40
SEED_PEMBAHASAN = 200
SEED_SAPUAN = 1000
BAGIAN_JAM_24 = {"pagi": range(6, 12), "siang": range(12, 15), "sore": range(15, 18), "malam": range(18, 24)}
HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
         "Oktober", "November", "Desember")
DAFTAR = {  # id -> (jenis, tingkat)
    "ukur_jam_analog": ("pg", 1), "ukur_minggu_hari": ("pg", 1),
    "ukur_uang_kembalian": ("pg", 2), "ukur_panjang_klip": ("pg", 2),
    "ukur_lama_kegiatan": ("pg", 2), "ukur_kalender_hari": ("pg", 2),
    "ukur_kalender_n_hari_lagi": ("pg", 3), "ukur_timbangan_berantai": ("pg", 3),
    "ukur_lama_menit": ("isian", 3),
}


def _t(template_id):
    return C.ambil(template_id)


def _bangun(template_id, parameter):
    return _t(template_id).bangun(json.loads(C.kanonik(parameter)))


def _soal(template_id, seed):
    return C.buat_soal(_t(template_id), random.Random(seed))


def _label(soal):
    return {p.nilai: p.kesalahan for p in soal.pengecoh}


def _sudut(garis):
    dx = float(garis.get("x2")) - float(garis.get("x1"))
    dy = float(garis.get("y2")) - float(garis.get("y1"))
    return math.degrees(math.atan2(dx, -dy)) % 360


def _baca_jam(grup):
    """(angka jam 1-12, menit) dari sudut kedua jarum di dalam satu <g data-jam>."""
    jarum = {g.get("data-jarum"): g for g in grup.iter(NS + "line") if g.get("data-jarum")}
    menit = round(_sudut(jarum["menit"]) / 6) % 60
    sudut_jam = _sudut(jarum["jam"])
    jam12 = round((sudut_jam - menit * 0.5) / 30) % 12 or 12
    harapan = (jam12 % 12) * 30 + menit * 0.5          # jarum pendek wajib ikut bergeser per menit
    assert abs((sudut_jam - harapan + 180) % 360 - 180) < 1, (jam12, menit, sudut_jam)
    return jam12, menit


def _bagian(teks):
    return re.search(r"\b(pagi|siang|sore|malam)\b", teks.lower()).group(1)


def _menit_hari(jam12, menit, bagian):
    jam = next(h for h in BAGIAN_JAM_24[bagian] if h % 12 == jam12 % 12)
    return jam * 60 + menit


def _fmt_durasi(menit):
    jam, sisa = divmod(menit, 60)
    return " ".join(([f"{jam} jam"] if jam else []) + ([f"{sisa} menit"] if sisa else []))


def _jam_gambar(soal):
    akar = ET.fromstring(soal.svg)
    return [_baca_jam(g) for g in akar.iter(NS + "g") if g.get("data-jam")], akar


# --- tingkat dan jenis -----------------------------------------------------------------------

@pytest.mark.parametrize("template_id", sorted(DAFTAR))
def test_jenis_dan_tingkat_sesuai_daftar_tugas(template_id):
    template = _t(template_id)
    assert (template.jenis, template.tingkat, template.topik) == (*DAFTAR[template_id], "pengukuran")


def test_tepat_sembilan_template_pengukuran_terdaftar():
    ids = {t.id for t in contest_templates.katalog() if t.topik == "pengukuran"}
    assert ids == set(DAFTAR)


# --- jangkar PDF -----------------------------------------------------------------------------

def test_jangkar_pdf_no4_jam_analog_pagi_0830():
    soal = _bangun("ukur_jam_analog", {"bagian": "pagi", "jam12": 8, "menit": 30, "nama": "Rudi"})
    assert soal.kunci == "08.30"
    assert {"06.40", "09.30", "08.00"} <= set(_label(soal))


def test_jangkar_pdf_no8_tiga_minggu_empat_hari():
    soal = _bangun("ukur_minggu_hari", {"nama": "Kia", "cerita": 0, "n": 3, "m": 4})
    assert soal.kunci == "25" and soal.nilai == 25
    assert _label(soal)["21"] == "lupa menambah sisa hari"


def test_jangkar_pdf_no12_kembalian_enam_ribu_empat_ribu_lima_ratus():
    soal = _bangun("ukur_uang_kembalian", {"nama": "Doni", "benda": ["roti", "buku tulis"],
                                           "harga": [6000, 4500], "bayar": 20000})
    assert soal.kunci == "Rp9.500"
    assert set(_label(soal)) <= {"Rp14.000", "Rp15.500", "Rp8.500", "Rp10.500", "Rp10.000", "Rp9.000"}


def test_jangkar_pdf_no16_klip_tiga_cm_enam_dan_empat_klip():
    soal = _bangun("ukur_panjang_klip", {"k": 3, "benda": ["pensil", "krayon"], "klip": [6, 4],
                                         "tanya": "selisih"})
    assert soal.kunci == "6 cm"
    assert {"2 cm", "30 cm"} <= set(_label(soal))


def test_jangkar_pdf_no19_sembilan_sampai_sebelas_tiga_puluh():
    soal = _bangun("ukur_lama_kegiatan", {"bagian": "pagi", "j1": 9, "m1": 0, "j2": 11, "m2": 30,
                                          "nama": "Rudi", "kegiatan": "bermain"})
    assert soal.kunci == "2 jam 30 menit"
    assert set(_label(soal)) == {"2 jam", "3 jam 30 menit", "3 jam"}


def test_jangkar_pdf_no21_semangka_melon_apel_jeruk():
    soal = _bangun("ukur_timbangan_berantai", {"objek": ["semangka", "melon", "apel", "jeruk"],
                                               "rasio": [2, 3, 2], "urutan": [0, 1, 2]})
    assert soal.kunci == "12" and soal.nilai == 12
    assert list(_label(soal)) == ["7", "6", "2"]


def test_jangkar_pdf_no25_satu_maret_minggu_ke_dua_puluh_lima_maret_rabu():
    soal = _bangun("ukur_kalender_hari", {"t1": [2026, 3, 1], "t2": [2026, 3, 25]})
    assert soal.kunci == "Rabu"
    assert "1 Maret 2026 hari Minggu" in soal.teks


def test_jangkar_pdf_isian3_lima_belas_tiga_puluh_ke_tujuh_belas_nol_nol():
    soal = _bangun("ukur_lama_menit", {"bagian": "sore", "j1": 15, "m1": 30, "j2": 17, "m2": 0,
                                       "nama": "Doni", "kegiatan": "belajar"})
    assert soal.kunci == "90" and soal.nilai == 90 and soal.pengecoh == ()


# --- gambar dibaca ulang ---------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_jam_analog_sudut_jarum_kembali_jadi_waktu_di_kunci(seed):
    soal = _soal("ukur_jam_analog", seed)
    parameter = json.loads(soal.parameter)
    ((jam12, menit),), akar = _jam_gambar(soal)
    assert (jam12, menit) == (parameter["jam12"], parameter["menit"])
    waktu = _menit_hari(jam12, menit, _bagian(soal.teks))
    assert soal.kunci == f"{waktu // 60:02d}.{waktu % 60:02d}"
    assert akar.get("aria-label") == "Jam analog"


def test_jam_analog_tidak_menampilkan_waktu_digital():
    for seed in range(SEED_GAMBAR):
        for soal in (_soal("ukur_jam_analog", seed), _soal("ukur_lama_kegiatan", seed),
                     _soal("ukur_lama_menit", seed)):
            isi = [e.text for e in ET.fromstring(soal.svg).iter(NS + "text")]
            assert all(t == "\u2192" or (t.isdigit() and 1 <= int(t) <= 12) for t in isi), isi


@pytest.mark.parametrize("template_id", ["ukur_lama_kegiatan", "ukur_lama_menit"])
@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_dua_jam_dibaca_ulang_dari_gambar_sama_dengan_kunci(template_id, seed):
    soal = _soal(template_id, seed)
    parameter = json.loads(soal.parameter)
    (awal, akhir), _ = _jam_gambar(soal)
    bagian = _bagian(soal.teks)
    assert bagian == parameter["bagian"]
    assert awal == (parameter["j1"] % 12 or 12, parameter["m1"])
    assert akhir == (parameter["j2"] % 12 or 12, parameter["m2"])
    lama = _menit_hari(*akhir, bagian) - _menit_hari(*awal, bagian)
    assert lama > 0
    assert soal.kunci == (str(lama) if soal.jenis == "isian" else _fmt_durasi(lama))


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_klip_dihitung_ulang_dari_gambar_sama_dengan_parameter_dan_kunci(seed):
    soal = _soal("ukur_panjang_klip", seed)
    parameter = json.loads(soal.parameter)
    akar = ET.fromstring(soal.svg)
    klip = {}
    for elemen in akar.iter(NS + "rect"):
        if elemen.get("data-klip"):
            klip[elemen.get("data-baris")] = klip.get(elemen.get("data-baris"), 0) + 1
    benda = [e.get("data-objek") for e in akar.iter(NS + "text") if e.get("data-objek")]
    assert benda == parameter["benda"]
    assert [klip[b] for b in benda] == parameter["klip"]
    k = int(re.search(r"Satu klip kertas panjangnya (\d+) cm", soal.teks).group(1))
    a, b = (klip[x] for x in benda)
    assert soal.kunci == f"{abs(a - b) * k if parameter['tanya'] == 'selisih' else (a + b) * k} cm"
    assert ("selisih" in soal.teks) == (parameter["tanya"] == "selisih")


@pytest.mark.parametrize("seed", range(SEED_GAMBAR))
def test_timbangan_berantai_diikuti_dari_gambar_sama_dengan_kunci(seed):
    soal = _soal("ukur_timbangan_berantai", seed)
    parameter = json.loads(soal.parameter)
    baris = {}
    for e in ET.fromstring(soal.svg).iter(NS + "text"):
        if e.get("data-rantai"):
            baris.setdefault(e.get("data-rantai"), []).append((e.get("data-sisi"), e.get("data-objek")))
    assert sorted(baris) == ["1", "2", "3"]
    peta = {}
    for isi in baris.values():
        kiri = [o for sisi, o in isi if sisi == "kiri"]
        kanan = [o for sisi, o in isi if sisi == "kanan"]
        assert len(kiri) == 1 and len(set(kanan)) == 1
        peta[kiri[0]] = (kanan[0], len(kanan))
    tujuan, awal = re.search(r"Berapa banyak (\w+) yang beratnya sama dengan 1 (\w+)\?", soal.teks).groups()
    sekarang, kali = awal, 1
    while sekarang != tujuan:
        sekarang, jumlah = peta[sekarang]
        kali *= jumlah
    assert str(kali) == soal.kunci
    assert [peta[o][1] for o in parameter["objek"][:3]] == parameter["rasio"]


def test_timbangan_berantai_urutan_baris_di_gambar_mengikuti_parameter():
    soal = _bangun("ukur_timbangan_berantai", {"objek": ["semangka", "melon", "apel", "jeruk"],
                                               "rasio": [2, 3, 2], "urutan": [2, 0, 1]})
    kiri = [e.get("data-objek") for e in ET.fromstring(soal.svg).iter(NS + "text")
            if e.get("data-sisi") == "kiri"]
    assert kiri == ["apel", "semangka", "melon"] and soal.kunci == "12"


# --- pengecoh bermakna (ditulis tangan) --------------------------------------------------------

def test_pengecoh_jam_sore_lewat_seperempat_ditulis_tangan():
    soal = _bangun("ukur_jam_analog", {"bagian": "sore", "jam12": 4, "menit": 15, "nama": "Tia"})
    assert soal.kunci == "16.15"
    label = _label(soal)
    assert label["15.20"] == "menukar fungsi jarum pendek dan jarum panjang"
    assert label["17.15"].startswith("membaca jam mengikuti angka berikutnya")
    assert label["16.00"] == "melupakan menit dan hanya membaca jarum pendek"


def test_pengecoh_uang_ditulis_tangan_untuk_dua_parameter():
    soal = _bangun("ukur_uang_kembalian", {"nama": "Sari", "benda": ["roti", "penghapus"],
                                           "harga": [3500, 2000], "bayar": 10000})
    assert soal.kunci == "Rp4.500"
    assert list(_label(soal)) == ["Rp6.500", "Rp8.000", "Rp3.500"]
    assert _label(soal)["Rp6.500"] == "mengurangi uang bayar hanya dengan harga benda pertama"


def test_pengecoh_klip_total_ditulis_tangan():
    soal = _bangun("ukur_panjang_klip", {"k": 2, "benda": ["pulpen", "sendok"], "klip": [5, 3],
                                         "tanya": "total"})
    assert soal.kunci == "16 cm"
    assert _label(soal)["8 cm"] == "menjumlahkan banyak klip tanpa mengalikan panjang satu klip"
    assert "4 cm" in _label(soal)


def test_pengecoh_kalender_lintas_bulan_menganggap_tiga_puluh_hari():
    soal = _bangun("ukur_kalender_hari", {"t1": [2026, 3, 28], "t2": [2026, 4, 3]})
    assert soal.kunci == "Jumat" and "Sabtu" in soal.teks
    assert _label(soal)["Kamis"] == "menganggap setiap bulan 30 hari"


def test_pengecoh_hari_lagi_ditulis_tangan():
    soal = _bangun("ukur_kalender_n_hari_lagi", {"tahun": 2026, "bulan": 12, "hari": 28, "n": 12,
                                                 "tanya": "hari"})
    assert "Senin, 28 Desember 2026" in soal.teks and soal.kunci == "Sabtu"
    assert _label(soal)["Senin"] == "mengira hari yang sama dengan hari ini"
    assert {"Minggu", "Jumat"} <= set(_label(soal))


# --- kasus tepi ------------------------------------------------------------------------------

def test_tepi_jam_dua_belas_siang_kedua_jarum_di_angka_dua_belas():
    soal = _bangun("ukur_jam_analog", {"bagian": "siang", "jam12": 12, "menit": 0, "nama": "Eko"})
    assert soal.kunci == "12.00"
    (jam12, menit), = _jam_gambar(soal)[0]
    assert (jam12, menit) == (12, 0)


def test_tepi_menit_nol_tetap_punya_tiga_pengecoh_berbeda():
    soal = _bangun("ukur_jam_analog", {"bagian": "pagi", "jam12": 6, "menit": 0, "nama": "Eko"})
    assert soal.kunci == "06.00" and len({p.nilai for p in soal.pengecoh}) == 3


def test_tepi_tanggal_di_luar_kalender_2026_2027_ditolak():
    for parameter in ({"tahun": 2027, "bulan": 12, "hari": 31, "n": 60, "tanya": "tanggal"},
                      {"tahun": 2025, "bulan": 12, "hari": 31, "n": 10, "tanya": "hari"}):
        with pytest.raises(C.ParameterTidakSah):
            _bangun("ukur_kalender_n_hari_lagi", parameter)
    with pytest.raises(C.ParameterTidakSah):
        _bangun("ukur_kalender_hari", {"t1": [2027, 12, 20], "t2": [2028, 1, 5]})


def test_tepi_akhir_bulan_tepat_satu_bulan_depan_tanpa_langkah_nol_hari():
    soal = _bangun("ukur_kalender_n_hari_lagi", {"tahun": 2027, "bulan": 1, "hari": 31, "n": 29,
                                                 "tanya": "tanggal"})
    assert soal.kunci == "1 Maret 2027" and "Maju 0 hari" not in " ".join(soal.pembahasan)


def test_tepi_lintas_tahun_dan_februari_tidak_kabisat():
    assert _bangun("ukur_kalender_n_hari_lagi", {"tahun": 2026, "bulan": 12, "hari": 28, "n": 12,
                                                 "tanya": "tanggal"}).kunci == "9 Januari 2027"
    assert _bangun("ukur_kalender_n_hari_lagi", {"tahun": 2027, "bulan": 2, "hari": 20, "n": 15,
                                                 "tanya": "tanggal"}).kunci == "7 Maret 2027"


def test_tepi_kalender_hari_ke_tanggal_lebih_awal_mundur():
    soal = _bangun("ukur_kalender_hari", {"t1": [2026, 3, 25], "t2": [2026, 3, 1]})
    assert soal.kunci == "Minggu" and "mundur" in soal.pembahasan[-2]


def test_tepi_lama_kegiatan_satu_jam_pas_dan_empat_puluh_lima_menit():
    satu = _bangun("ukur_lama_kegiatan", {"bagian": "siang", "j1": 12, "m1": 30, "j2": 13, "m2": 30,
                                          "nama": "Eko", "kegiatan": "belajar"})
    menit = _bangun("ukur_lama_kegiatan", {"bagian": "malam", "j1": 19, "m1": 15, "j2": 20, "m2": 0,
                                           "nama": "Eko", "kegiatan": "belajar"})
    assert (satu.kunci, menit.kunci) == ("1 jam", "45 menit")


def test_tepi_selang_waktu_keluar_bagian_hari_ditolak():
    with pytest.raises(C.ParameterTidakSah):
        _bangun("ukur_lama_kegiatan", {"bagian": "pagi", "j1": 11, "m1": 30, "j2": 12, "m2": 15,
                                       "nama": "Eko", "kegiatan": "belajar"})


def test_tepi_jam_tidak_ada_pada_bagian_hari_ditolak():
    with pytest.raises(C.ParameterTidakSah):
        _bangun("ukur_jam_analog", {"bagian": "pagi", "jam12": 12, "menit": 0, "nama": "Eko"})


def test_tepi_kembalian_pecahan_lima_ratus_memakai_titik_ribuan_konsisten():
    soal = _bangun("ukur_uang_kembalian", {"nama": "Eko", "benda": ["roti", "balon"],
                                           "harga": [9500, 9500], "bayar": 20000})
    assert soal.kunci == "Rp1.000"
    assert all(re.fullmatch(r"Rp\d{1,3}(\.\d{3})*", n) for n in [soal.kunci, *_label(soal)])


# --- kalender nyata, uang, tingkat sapuan ------------------------------------------------------

def test_kalender_hari_di_teks_sama_dengan_kalender_asli_untuk_semua_seed():
    for seed in range(SEED_SAPUAN):
        soal = _soal("ukur_kalender_hari", seed)
        t1, t2 = (datetime.date(*t) for t in json.loads(soal.parameter).values())
        assert f"{t1.day} {BULAN[t1.month - 1]} {t1.year} hari {HARI[t1.weekday()]}" in soal.teks
        assert soal.kunci == HARI[t2.weekday()]


def test_kalender_n_hari_lagi_tanggal_selalu_lintas_bulan_dan_tahun_terjangkau():
    tahun_akhir, bulan_akhir = set(), set()
    for seed in range(SEED_SAPUAN):
        soal = _soal("ukur_kalender_n_hari_lagi", seed)
        p = json.loads(soal.parameter)
        akhir = datetime.date(p["tahun"], p["bulan"], p["hari"]) + datetime.timedelta(days=p["n"])
        if p["tanya"] == "tanggal":
            assert (akhir.year, akhir.month) != (p["tahun"], p["bulan"])
        tahun_akhir.add(akhir.year), bulan_akhir.add(akhir.month)
    assert tahun_akhir == {2026, 2027} and bulan_akhir == set(range(1, 13))


def test_kedua_jenis_pertanyaan_n_hari_lagi_muncul():
    tanya = {json.loads(_soal("ukur_kalender_n_hari_lagi", s).parameter)["tanya"] for s in range(60)}
    assert tanya == {"hari", "tanggal"}


@pytest.mark.parametrize("template_id", ["ukur_lama_kegiatan", "ukur_lama_menit"])
def test_durasi_tidak_pernah_menyeberang_bagian_hari_di_seribu_seed(template_id):
    for seed in range(SEED_SAPUAN):
        p = json.loads(_soal(template_id, seed).parameter)
        jam = BAGIAN_JAM_24[p["bagian"]]
        assert p["j1"] in jam and p["j2"] in jam
        assert (p["j1"], p["m1"]) < (p["j2"], p["m2"])


def test_lama_menit_selalu_memerlukan_pinjam_jam_dan_kunci_wajar():
    for seed in range(SEED_PEMBAHASAN):
        soal = _soal("ukur_lama_menit", seed)
        p = json.loads(soal.parameter)
        assert p["m2"] < p["m1"] and 35 <= soal.nilai <= 180 and soal.nilai % 5 == 0


def test_kapasitas_bermakna_tanpa_menghitung_nama_atau_cerita():
    jam = {(p["bagian"], p["jam12"], p["menit"]) for p in
           (json.loads(_soal("ukur_jam_analog", s).parameter) for s in range(SEED_SAPUAN))}
    minggu = {(p["n"], p["m"]) for p in
              (json.loads(_soal("ukur_minggu_hari", s).parameter) for s in range(SEED_SAPUAN))}
    klip = {(p["k"], tuple(p["klip"]), p["tanya"]) for p in
            (json.loads(_soal("ukur_panjang_klip", s).parameter) for s in range(SEED_SAPUAN))}
    assert len(jam) >= 150 and len(minggu) >= 50 and len(klip) >= 150


@pytest.mark.parametrize("template_id", sorted(DAFTAR))
def test_pembahasan_berakhir_dengan_kunci_dan_tidak_ada_langkah_kosong(template_id):
    for seed in range(SEED_PEMBAHASAN):
        soal = _soal(template_id, seed)
        assert all(langkah.strip() for langkah in soal.pembahasan)
        assert soal.kunci in soal.pembahasan[-1], (soal.pembahasan, soal.kunci)


@pytest.mark.parametrize("template_id", ["ukur_jam_analog", "ukur_lama_kegiatan", "ukur_lama_menit"])
def test_teks_soal_jam_selalu_menyebut_bagian_hari(template_id):
    for seed in range(SEED_GAMBAR):
        soal = _soal(template_id, seed)
        assert _bagian(soal.teks) == json.loads(soal.parameter)["bagian"]


def test_nama_dalam_cerita_hanya_dari_daftar_nama_anak():
    for template_id in ("ukur_jam_analog", "ukur_minggu_hari", "ukur_uang_kembalian",
                        "ukur_lama_kegiatan", "ukur_lama_menit"):
        for seed in range(SEED_GAMBAR):
            assert json.loads(_soal(template_id, seed).parameter)["nama"] in C.NAMA_ANAK


def test_gambar_tidak_membocorkan_angka_di_teks_alternatif():
    for template_id in ("ukur_jam_analog", "ukur_lama_kegiatan", "ukur_lama_menit",
                        "ukur_panjang_klip", "ukur_timbangan_berantai"):
        akar = ET.fromstring(_soal(template_id, 1).svg)
        assert not re.search(r"\d", akar.get("aria-label"))

"""Tes template topik Bangun Datar/Ruang Latihan Lomba: jangkar PDF, gambar dihitung ulang, pengecoh, tepi."""
import json
import math
import random
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from itertools import combinations, product

import pytest

import contest_core as C
import contest_templates

NS = "{http://www.w3.org/2000/svg}"
SEED_GAMBAR = 60
SEED_PEMBAHASAN = 200
SEL_PX, MARGIN_PX = 30, 14          # kisi sel (gambar_sel)
TEMPEL_PX, TEPI_TEMPEL_PX = 44, 46  # gambar_tempel
GARIS_PX, TEPI_GARIS_PX = 80, 28    # diagram_garis
TOLERANSI = 0.2
TABEL_TINGKAT = {
    "bgn_titik_sudut": (C.JENIS_PG, 1), "bgn_benda_ruang": (C.JENIS_PG, 1), "bgn_jumlah_sisi": (C.JENIS_PG, 1),
    "bgn_keliling_susun": (C.JENIS_PG, 2), "bgn_tempel_persegi": (C.JENIS_PG, 2),
    "bgn_rusuk_titik_sisi": (C.JENIS_PG, 2), "bgn_persegi_kisi": (C.JENIS_PG, 3),
    "bgn_segitiga_diagonal": (C.JENIS_ISIAN, 3), "bgn_kubus_berlapis": (C.JENIS_ISIAN, 3),
}
# Tabel tes sendiri (tulis tangan): titik sudut tiap bentuk dan emoji -> bangun ruang.
SUDUT = {"lingkaran": 0, "segitiga": 3, "persegi": 4, "persegi panjang": 4, "belah ketupat": 4,
         "jajar genjang": 4, "trapesium": 4, "layang-layang": 4, "segilima": 5, "segienam": 6}
EMOJI_BANGUN = {"\U0001F96B": "tabung", "\U0001F6E2️": "tabung", "\U0001F56F️": "tabung",
                "\U0001F3B2": "kubus", "\U0001F9CA": "kubus", "⚽": "bola", "\U0001F3C0": "bola",
                "\U0001F3BE": "bola", "\U0001F9F1": "balok", "\U0001F9C3": "balok"}
SYARAT = {"nol": lambda n, s: n == 0, "tiga": lambda n, s: n == 3, "lima": lambda n, s: n == 5,
          "enam": lambda n, s: n == 6, "lebih_empat": lambda n, s: n > 4,
          "empat_sama": lambda n, s: n == 4 and s, "empat_beda": lambda n, s: n == 4 and not s}


def _tpl(template_id):
    return C.ambil(template_id)


def _bangun(template_id, **parameter):
    return _tpl(template_id).bangun(json.loads(C.kanonik(parameter)))


def _soal(template_id, seed):
    return C.buat_soal(_tpl(template_id), random.Random(seed))


def _soal_banyak(template_id, jumlah=SEED_GAMBAR):
    return [_soal(template_id, seed) for seed in range(jumlah)]


def _param(soal):
    return json.loads(soal.parameter)


def _elemen(svg, tag):
    return [e for e in ET.fromstring(svg).iter() if e.tag == NS + tag]


def _beratribut(svg, nama):
    return [e for e in ET.fromstring(svg).iter() if e.get(nama) is not None]


def _pengecoh(soal):
    return {p.nilai: p.kesalahan for p in soal.pengecoh}


def _angka(el, nama):
    return float(el.get(nama))


def _sudut_dan_sama(svg):
    """Banyak titik sudut dan 'semua sisi sama' dibaca dari gambar pilihan (poligon/lingkaran)."""
    if _elemen(svg, "circle"):
        return 0, False
    titik = [tuple(map(float, t.split(","))) for t in _elemen(svg, "polygon")[0].get("points").split()]
    panjang = [math.dist(a, b) for a, b in zip(titik, titik[1:] + titik[:1])]
    return len(titik), max(panjang) - min(panjang) < TOLERANSI


def _sisi_terbuka(sel):
    """Keliling kotak satuan: sisi yang hanya dimiliki satu kotak (sisi tempel dibuang)."""
    hitung = {}
    for r, c in sel:
        for sisi in (((r, c), (r, c + 1)), ((r + 1, c), (r + 1, c + 1)),
                     ((r, c), (r + 1, c)), ((r, c + 1), (r + 1, c + 1))):
            hitung[sisi] = hitung.get(sisi, 0) + 1
    return sum(1 for v in hitung.values() if v == 1)


def _sel_dari_gambar(svg, ukuran, geser):
    """Sel (baris, kolom) dibaca dari posisi kotak; sekaligus cocokkan dengan atribut data-sel."""
    hasil = set()
    for el in _beratribut(svg, "data-sel"):
        kolom, baris = round((_angka(el, "x") - geser) / ukuran), round((_angka(el, "y") - geser) / ukuran)
        assert el.get("data-sel") == f"{baris},{kolom}"
        hasil.add((baris, kolom))
    return hasil


# ------------------------------------------------------------------ generik 9 template
@pytest.mark.parametrize("template_id,tabel", sorted(TABEL_TINGKAT.items()))
def test_jenis_dan_tingkat_sesuai_daftar_tugas(template_id, tabel):
    template = _tpl(template_id)
    assert (template.jenis, template.tingkat) == tabel


def test_semua_template_bangun_terdaftar_tepat_sembilan():
    ids = {t.id for t in contest_templates.katalog() if t.topik == "bangun"}
    assert ids == set(TABEL_TINGKAT)


@pytest.mark.parametrize("template_id", sorted(TABEL_TINGKAT))
def test_pembahasan_memuat_kunci_di_langkah_terakhir_dan_tanpa_langkah_kosong(template_id):
    for soal in _soal_banyak(template_id, SEED_PEMBAHASAN):
        assert soal.kunci in soal.pembahasan[-1], (soal.teks, soal.pembahasan)
        assert all(langkah.strip() for langkah in soal.pembahasan)


@pytest.mark.parametrize("template_id", sorted(TABEL_TINGKAT))
def test_semua_gambar_xml_sah_dan_aria_label_tanpa_angka(template_id):
    for soal in _soal_banyak(template_id):
        gambar = [soal.svg] + [p.svg for p in soal.pengecoh] + [soal.kunci_svg]
        for svg in filter(None, gambar):
            aria = ET.fromstring(svg).get("aria-label")
            assert aria and not re.search(r"[0-9]", aria)


# ------------------------------------------------------------------ bgn_titik_sudut
def test_titik_sudut_jangkar_pdf_no_3_lingkaran_tanpa_titik_sudut():
    soal = _bangun("bgn_titik_sudut", syarat="nol", bentuk=["belah ketupat", "lingkaran", "persegi", "segitiga"])
    assert soal.kunci == "lingkaran"
    assert set(_pengecoh(soal)) == {"belah ketupat", "persegi", "segitiga"}
    assert soal.teks == "Bangun yang TIDAK mempunyai titik sudut adalah ..."


def test_titik_sudut_gambar_pilihan_hanya_satu_yang_memenuhi_syarat_dan_itu_kunci():
    for soal in _soal_banyak("bgn_titik_sudut"):
        syarat = SYARAT[_param(soal)["syarat"]]
        pilihan = [(soal.kunci, soal.kunci_svg)] + [(p.nilai, p.svg) for p in soal.pengecoh]
        cocok = [nama for nama, svg in pilihan if syarat(*_sudut_dan_sama(svg))]
        assert cocok == [soal.kunci], (soal.teks, cocok)
        for nama, svg in pilihan:
            assert _elemen_data(svg, "data-bangun") == nama
            assert _sudut_dan_sama(svg)[0] == SUDUT[nama]


def _elemen_data(svg, nama):
    nilai = {e.get(nama) for e in _beratribut(svg, nama)}
    assert len(nilai) == 1
    return nilai.pop()


def test_titik_sudut_aria_label_pilihan_netral_tidak_membocorkan_bentuk():
    nama_bentuk = list(SUDUT) + ["sudut", "sisi"]
    for soal in _soal_banyak("bgn_titik_sudut"):
        aria = {ET.fromstring(s).get("aria-label") for s in [soal.kunci_svg] + [p.svg for p in soal.pengecoh]}
        assert aria == {"Gambar bentuk"}
        assert not any(nama in next(iter(aria)).lower() for nama in nama_bentuk)


def test_titik_sudut_pengecoh_berlabel_sifat_bentuk_yang_dipilih_salah():
    soal = _bangun("bgn_titik_sudut", syarat="tiga", bentuk=["belah ketupat", "lingkaran", "persegi", "segitiga"])
    assert soal.kunci == "segitiga"
    assert "mempunyai 4 titik sudut dan sisinya sama panjang" in _pengecoh(soal)["persegi"]
    assert "tidak mempunyai titik sudut" in _pengecoh(soal)["lingkaran"]


@pytest.mark.parametrize("syarat,pasangan", [("empat_sama", {"persegi", "belah ketupat"}),
                                             ("lebih_empat", {"segilima", "segienam"})])
def test_titik_sudut_tidak_pernah_memuat_dua_jawaban_benar_sekaligus(syarat, pasangan):
    soal_syarat = [s for s in _soal_banyak("bgn_titik_sudut", 400) if _param(s)["syarat"] == syarat]
    assert len(soal_syarat) >= 20
    for soal in soal_syarat:
        assert len(pasangan & set(_param(soal)["bentuk"])) == 1


def test_titik_sudut_empat_sisi_tidak_sama_hanya_memilih_bentuk_bersisi_beda():
    soal = _bangun("bgn_titik_sudut", syarat="empat_beda",
                   bentuk=["belah ketupat", "lingkaran", "persegi", "trapesium"])
    assert soal.kunci == "trapesium"


# ------------------------------------------------------------------ bgn_benda_ruang
def test_benda_ruang_jangkar_pdf_no_6_tabung():
    soal = _bangun("bgn_benda_ruang", tanya="tabung", benda=["bola sepak", "dadu", "kaleng", "kotak jus"])
    assert soal.kunci == "kaleng"
    assert _pengecoh(soal)["dadu"] == "memilih dadu, padahal dadu berbentuk kubus"
    assert set(_pengecoh(soal)) == {"bola sepak", "dadu", "kotak jus"}


def test_benda_ruang_gambar_emoji_hanya_satu_pilihan_berbentuk_yang_ditanya():
    for soal in _soal_banyak("bgn_benda_ruang"):
        tanya = _param(soal)["tanya"]
        pilihan = [(soal.kunci, soal.kunci_svg)] + [(p.nilai, p.svg) for p in soal.pengecoh]
        bangun_gambar = []
        for nama, svg in pilihan:
            teks = _elemen(svg, "text")
            assert len(teks) == 1 and teks[0].get("data-benda") == nama
            bangun_gambar.append(EMOJI_BANGUN[teks[0].text])
            assert teks[0].get("data-bangun") == bangun_gambar[-1]
            assert ET.fromstring(svg).get("aria-label") == "Gambar benda"
        assert sorted(bangun_gambar) == ["balok", "bola", "kubus", "tabung"]
        assert [n for (n, _), b in zip(pilihan, bangun_gambar) if b == tanya] == [soal.kunci]


def test_benda_ruang_tiap_bangun_punya_beberapa_benda_dan_semuanya_muncul():
    soal_semua = _soal_banyak("bgn_benda_ruang", 400)
    muncul = {}
    for soal in soal_semua:
        for nama in _param(soal)["benda"]:
            muncul.setdefault(BANGUN_DARI_NAMA[nama], set()).add(nama)
    assert set(muncul) == {"tabung", "kubus", "bola", "balok"}
    assert all(len(v) >= 2 for v in muncul.values())


BANGUN_DARI_NAMA = {"kaleng": "tabung", "drum minyak": "tabung", "lilin": "tabung", "dadu": "kubus",
                    "es batu": "kubus", "bola sepak": "bola", "bola basket": "bola", "bola tenis": "bola",
                    "batu bata": "balok", "kotak jus": "balok"}


def test_benda_ruang_kubus_dan_balok_tidak_tertukar_pada_kasus_mirip():
    soal = _bangun("bgn_benda_ruang", tanya="kubus", benda=["batu bata", "dadu", "lilin", "bola tenis"])
    assert soal.kunci == "dadu"
    soal = _bangun("bgn_benda_ruang", tanya="balok", benda=["batu bata", "es batu", "lilin", "bola tenis"])
    assert soal.kunci == "batu bata"


# ------------------------------------------------------------------ bgn_jumlah_sisi
def test_jumlah_sisi_jangkar_pdf_no_10_lima_belas():
    soal = _bangun("bgn_jumlah_sisi", bangun=["segitiga", "persegi", "persegi", "belah ketupat"])
    assert soal.kunci == "15"
    assert set(_pengecoh(soal)) == {"12", "16", "4"}
    assert "melewatkan bangun pertama" in _pengecoh(soal)["12"]
    assert "4 sisi" in _pengecoh(soal)["16"]
    assert "banyak bangun" in _pengecoh(soal)["4"]


def test_jumlah_sisi_gambar_jumlah_titik_poligon_sama_dengan_kunci():
    for soal in _soal_banyak("bgn_jumlah_sisi"):
        bentuk = _beratribut(soal.svg, "data-bangun")
        assert [e.get("data-bangun") for e in bentuk] == _param(soal)["bangun"]
        titik = [len(e.get("points").split()) for e in bentuk]
        assert [SUDUT[e.get("data-bangun")] for e in bentuk] == titik
        assert sum(titik) == int(soal.kunci) == soal.nilai


def test_jumlah_sisi_segienam_dan_segilima_dihitung_enam_dan_lima():
    soal = _bangun("bgn_jumlah_sisi", bangun=["segienam", "segilima", "segitiga"])
    assert soal.kunci == "14"
    assert soal.pembahasan[2] == "6 + 5 + 3 = 14"


# ------------------------------------------------------------------ bgn_keliling_susun
def test_keliling_susun_jangkar_pdf_no_14_dua_baris_empat_kolom():
    soal = _bangun("bgn_keliling_susun", sel=[[r, c] for r in range(2) for c in range(4)])
    assert soal.kunci == "12 cm"
    assert "banyak kotak" in _pengecoh(soal)["8 cm"]
    assert soal.nilai is None


def test_keliling_susun_gambar_dihitung_ulang_dari_posisi_kotak():
    for soal in _soal_banyak("bgn_keliling_susun"):
        sel = _sel_dari_gambar(soal.svg, SEL_PX, MARGIN_PX)
        assert sel == {tuple(s) for s in _param(soal)["sel"]}
        assert f"{_sisi_terbuka(sel)} cm" == soal.kunci


def test_keliling_susun_bentuk_u_keliling_lebih_besar_dari_persegi_panjang_pembungkus():
    soal = _bangun("bgn_keliling_susun", sel=[[0, 0], [0, 2], [1, 0], [1, 1], [1, 2]])
    assert soal.kunci == "12 cm"
    assert [p.nilai for p in soal.pengecoh] == ["5 cm", "6 cm", "16 cm"]


def test_keliling_susun_tangga_dan_huruf_l_dihitung_dari_sisi_terbuka():
    tangga = _bangun("bgn_keliling_susun", sel=[[0, 0], [1, 0], [1, 1], [2, 0], [2, 1], [2, 2]])
    huruf_l = _bangun("bgn_keliling_susun", sel=[[0, 0], [1, 0], [2, 0], [2, 1], [2, 2]])
    assert (tangga.kunci, huruf_l.kunci) == ("12 cm", "12 cm")
    assert tangga.pembahasan[1] == "Sisi kotak di tepi luar: atas 3, kanan 3, bawah 3, kiri 3, jumlahnya 12 sisi."


def test_keliling_susun_dua_kotak_berjajar_enam_senti():
    assert _bangun("bgn_keliling_susun", sel=[[0, 0], [0, 1]]).kunci == "6 cm"


# ------------------------------------------------------------------ bgn_tempel_persegi
def test_tempel_persegi_jangkar_pdf_no_20_dua_persegi_lima_senti():
    soal = _bangun("bgn_tempel_persegi", sisi=5, banyak=2, arah="mendatar")
    assert soal.kunci == "30 cm"
    pengecoh = _pengecoh(soal)
    assert set(pengecoh) == {"40 cm", "20 cm", "50 cm"}
    assert "tanpa mengurangi sisi yang ditempel" in pengecoh["40 cm"]
    assert "satu persegi saja" in pengecoh["20 cm"]
    assert "luas" in pengecoh["50 cm"]


def test_tempel_persegi_gambar_dihitung_ulang_dari_posisi_persegi():
    for soal in _soal_banyak("bgn_tempel_persegi"):
        p = _param(soal)
        sel = _sel_dari_gambar(soal.svg, TEMPEL_PX, TEPI_TEMPEL_PX)
        assert len(sel) == p["banyak"]
        assert (len({r for r, _ in sel}), len({c for _, c in sel})) == \
            ((1, p["banyak"]) if p["arah"] == "mendatar" else (p["banyak"], 1))
        assert f"{_sisi_terbuka(sel) * p['sisi']} cm" == soal.kunci
        assert {e.text for e in _elemen(soal.svg, "text")} == {f"{p['sisi']} cm"}
        assert f"{p['sisi']} cm" in soal.teks


def test_tempel_persegi_tiga_persegi_dua_senti_dan_arah_tegak_sama_kuncinya():
    mendatar = _bangun("bgn_tempel_persegi", sisi=2, banyak=3, arah="mendatar")
    tegak = _bangun("bgn_tempel_persegi", sisi=2, banyak=3, arah="tegak")
    assert (mendatar.kunci, tegak.kunci) == ("16 cm", "16 cm")
    assert _pengecoh(mendatar)["24 cm"].startswith("menjumlahkan keliling")
    assert mendatar.svg != tegak.svg


def test_tempel_persegi_pengecoh_sambungan_kurang_satu_sisi_untuk_tiga_persegi():
    soal = _bangun("bgn_tempel_persegi", sisi=10, banyak=3, arah="mendatar")
    assert soal.kunci == "80 cm"
    assert "hanya mengurangi satu sisi tempel" in _pengecoh(soal)["100 cm"]


# ------------------------------------------------------------------ bgn_rusuk_titik_sisi
def test_rusuk_titik_sisi_jangkar_pdf_no_26_empat_belas():
    soal = _bangun("bgn_rusuk_titik_sisi", suku=[["rusuk", "balok"], ["titik sudut", "kubus"], ["sisi", "balok"]],
                   tanda=[1, -1])
    assert soal.kunci == "14"
    assert soal.teks == "Banyak rusuk balok + banyak titik sudut kubus − banyak sisi balok = ..."
    pengecoh = _pengecoh(soal)
    assert set(pengecoh) == {"2", "10", "20"}
    assert "menukar banyak rusuk dengan banyak sisi" in pengecoh["2"]
    assert "menukar banyak titik sudut dengan banyak sisi" in pengecoh["10"]
    assert "lupa menghitung suku terakhir" in pengecoh["20"]


def _nilai_dari_gambar(svg):
    """Banyak rusuk/titik sudut/sisi tiap bangun dihitung dari elemen bertanda pada gambar."""
    peta = {"rusuk": "data-rusuk", "titik sudut": "data-titik", "sisi": "data-sisi"}
    return {nama: {sifat: len([e for e in _beratribut(svg, atribut) if e.get(atribut) == nama])
                   for sifat, atribut in peta.items()} for nama in ("balok", "kubus")}


def test_rusuk_titik_sisi_gambar_balok_dan_kubus_dihitung_ulang_sama_dengan_kunci():
    for soal in _soal_banyak("bgn_rusuk_titik_sisi"):
        hitung = _nilai_dari_gambar(soal.svg)
        assert hitung["balok"] == hitung["kubus"] == {"rusuk": 12, "titik sudut": 8, "sisi": 6}
        p = _param(soal)
        nilai = [hitung[bangun][sifat] for sifat, bangun in p["suku"]]
        assert str(nilai[0] + p["tanda"][0] * nilai[1] + p["tanda"][1] * nilai[2]) == soal.kunci
        garis_putus = [e for e in _elemen(soal.svg, "line") if e.get("stroke-dasharray")]
        assert len(garis_putus) == 6


def test_rusuk_titik_sisi_semua_suku_dijumlah_dan_sifat_berulang():
    soal = _bangun("bgn_rusuk_titik_sisi", suku=[["sisi", "kubus"], ["titik sudut", "balok"], ["rusuk", "balok"]],
                   tanda=[1, 1])
    assert soal.kunci == "26"
    soal = _bangun("bgn_rusuk_titik_sisi", suku=[["rusuk", "balok"], ["rusuk", "kubus"], ["titik sudut", "balok"]],
                   tanda=[1, -1])
    assert soal.kunci == "16"


def test_rusuk_titik_sisi_hasil_selalu_positif_dan_kunci_berbeda_banyak():
    soal_semua = _soal_banyak("bgn_rusuk_titik_sisi", 400)
    assert all(s.nilai >= 1 for s in soal_semua)
    assert len({s.kunci for s in soal_semua}) >= 8


def test_rusuk_titik_sisi_bangun_salah_tidak_mengubah_kunci_karena_sifat_sama():
    a = _bangun("bgn_rusuk_titik_sisi", suku=[["rusuk", "balok"], ["titik sudut", "kubus"], ["sisi", "balok"]],
                tanda=[1, -1])
    b = _bangun("bgn_rusuk_titik_sisi", suku=[["rusuk", "kubus"], ["titik sudut", "balok"], ["sisi", "kubus"]],
                tanda=[1, -1])
    assert a.kunci == b.kunci == "14"


# ------------------------------------------------------------------ bgn_persegi_kisi
def _hitung_persegi_gambar(sel, kecil, besar):
    return sum(1 for r, c in sel for k in range(kecil, (besar or 99) + 1)
               if all((r + i, c + j) in sel for i in range(k) for j in range(k)))


def test_persegi_kisi_jangkar_pdf_no_29_tiga_kali_tiga_empat_belas():
    soal = _bangun("bgn_persegi_kisi", baris=3, kolom=3, mode="semua")
    assert soal.kunci == "14"
    pengecoh = _pengecoh(soal)
    assert set(pengecoh) == {"9", "10", "16"}
    assert "hanya menghitung persegi kecil" in pengecoh["9"]
    assert "yang terbesar saja" in pengecoh["10"]


def test_persegi_kisi_gambar_dihitung_ulang_dari_sel_dan_atribut_baris_kolom():
    batas = {"semua": (1, None), "besar": (2, None), "dua": (2, 2)}
    for soal in _soal_banyak("bgn_persegi_kisi", 120):
        p = _param(soal)
        akar = ET.fromstring(soal.svg)
        assert (int(akar.get("data-baris")), int(akar.get("data-kolom"))) == (p["baris"], p["kolom"])
        sel = _sel_dari_gambar(soal.svg, SEL_PX, MARGIN_PX)
        assert len(sel) == p["baris"] * p["kolom"]
        assert str(_hitung_persegi_gambar(sel, *batas[p["mode"]])) == soal.kunci


@pytest.mark.parametrize("baris,kolom,mode,kunci", [
    (2, 2, "semua", "5"), (5, 5, "semua", "55"), (2, 5, "semua", "14"),
    (3, 3, "besar", "5"), (3, 3, "dua", "4"), (4, 5, "dua", "12")])
def test_persegi_kisi_nilai_tepi_dan_persegi_panjang(baris, kolom, mode, kunci):
    assert _bangun("bgn_persegi_kisi", baris=baris, kolom=kolom, mode=mode).kunci == kunci


def test_persegi_kisi_pengecoh_dua_kali_dua_tidak_menumpuk_dan_jumlah_kotak():
    soal = _bangun("bgn_persegi_kisi", baris=3, kolom=3, mode="dua")
    assert _pengecoh(soal)["1"] == "hanya menghitung persegi 2 x 2 yang tidak saling menumpuk"
    assert "9" in _pengecoh(soal)


def test_persegi_kisi_semua_kombinasi_kisi_dan_mode_punya_tiga_pengecoh_sah():
    for baris, kolom, mode in product(range(2, 6), range(2, 6), ("semua", "besar", "dua")):
        soal = _bangun("bgn_persegi_kisi", baris=baris, kolom=kolom, mode=mode)
        C.validasi_soal(soal)
        assert len(soal.pengecoh) == 3


# ------------------------------------------------------------------ bgn_segitiga_diagonal
def _ruas_dari_gambar(svg):
    hasil = []
    for el in _elemen(svg, "line"):
        nilai = [(_angka(el, nama) - TEPI_GARIS_PX) / GARIS_PX for nama in ("x1", "y1", "x2", "y2")]
        assert all(abs(v - round(v)) < 1e-6 for v in nilai)
        hasil.append((el.get("data-garis"), tuple(int(round(v)) for v in nilai)))
    return hasil


def _hitung_segitiga_gambar(ruas):
    """Segitiga pada gambar: tiga titik tak segaris yang ketiga sisinya tertutup garis yang tergambar."""
    def titik_potong(a, b):
        a1, b1, c1 = a[3] - a[1], a[0] - a[2], (a[3] - a[1]) * a[0] + (a[0] - a[2]) * a[1]
        a2, b2, c2 = b[3] - b[1], b[0] - b[2], (b[3] - b[1]) * b[0] + (b[0] - b[2]) * b[1]
        d = a1 * b2 - a2 * b1
        return None if d == 0 else (Fraction(c1 * b2 - c2 * b1, d), Fraction(a1 * c2 - a2 * c1, d))

    def di_ruas(t, r):
        silang = (r[2] - r[0]) * (t[1] - r[1]) - (r[3] - r[1]) * (t[0] - r[0])
        return silang == 0 and min(r[0], r[2]) <= t[0] <= max(r[0], r[2]) and min(r[1], r[3]) <= t[1] <= max(r[1], r[3])

    titik = {(Fraction(r[i]), Fraction(r[i + 1])) for r in ruas for i in (0, 2)}
    titik |= {t for a, b in combinations(ruas, 2) for t in [titik_potong(a, b)] if t and di_ruas(t, a) and di_ruas(t, b)}
    tertutup = lambda p, q: any(di_ruas(p, r) and di_ruas(q, r) for r in ruas)  # noqa: E731
    return sum(1 for a, b, c in combinations(titik, 3)
               if (b[0] - a[0]) * (c[1] - a[1]) != (b[1] - a[1]) * (c[0] - a[0])
               and tertutup(a, b) and tertutup(b, c) and tertutup(a, c))


def test_segitiga_diagonal_jangkar_pdf_isian_4_persegi_dua_diagonal_delapan():
    soal = _bangun("bgn_segitiga_diagonal", w=1, h=1, garis=[[0, 0, 1, 1], [0, 1, 1, 0]])
    assert (soal.kunci, soal.nilai, soal.pengecoh) == ("8", 8, ())
    assert soal.pembahasan[1] == "Banyaknya: ukuran ke-1: 4 buah, ukuran ke-2: 4 buah."


def test_segitiga_diagonal_gambar_dihitung_ulang_dari_garis_yang_tergambar():
    for soal in _soal_banyak("bgn_segitiga_diagonal", 120):
        p = _param(soal)
        ruas = _ruas_dari_gambar(soal.svg)
        assert [r for jenis, r in ruas if jenis == "dalam"] == [tuple(g) for g in p["garis"]]
        assert sum(1 for jenis, _ in ruas if jenis == "sisi") == 4
        assert str(_hitung_segitiga_gambar([r for _, r in ruas])) == soal.kunci


@pytest.mark.parametrize("w,h,garis,kunci", [
    (2, 2, [[0, 0, 2, 2], [1, 0, 1, 2]], "4"),
    (2, 2, [[0, 0, 2, 2], [0, 2, 2, 0], [1, 0, 1, 2]], "12"),
    (2, 2, [[0, 0, 2, 2], [0, 2, 2, 0], [1, 0, 1, 2], [0, 1, 2, 1]], "16"),
    (1, 1, [[0, 0, 1, 1]], "2"),
    (2, 1, [[0, 0, 2, 1], [0, 1, 2, 0]], "8")])
def test_segitiga_diagonal_gambar_tangan_dengan_hitungan_terkenal(w, h, garis, kunci):
    soal = _bangun("bgn_segitiga_diagonal", w=w, h=h, garis=garis)
    assert soal.kunci == kunci
    assert str(_hitung_segitiga_gambar([(0, 0, w, 0), (w, 0, w, h), (w, h, 0, h), (0, h, 0, 0)] + [tuple(g) for g in garis])) == kunci


def test_segitiga_diagonal_garis_dalam_tidak_pernah_berimpit_dan_jawaban_beragam():
    soal_semua = _soal_banyak("bgn_segitiga_diagonal", 400)
    assert len({s.kunci for s in soal_semua}) >= 10
    assert len({C.tanda_tangan(s) for s in soal_semua}) >= 100
    assert all(2 <= s.nilai <= 24 for s in soal_semua)


# ------------------------------------------------------------------ bgn_kubus_berlapis
def test_kubus_berlapis_jangkar_pdf_isian_5_empat_kali_tiga_dua_lapis():
    soal = _bangun("bgn_kubus_berlapis", baris=3, kolom=4, lapis=2)
    assert (soal.kunci, soal.nilai, soal.pengecoh) == ("24", 24, ())
    assert len(_beratribut(soal.svg, "data-kubus")) == 12
    assert "2 lapisan" in soal.teks


def test_kubus_berlapis_gambar_dihitung_ulang_kali_lapisan_sama_dengan_kunci():
    for soal in _soal_banyak("bgn_kubus_berlapis"):
        p = _param(soal)
        kubus = len(_beratribut(soal.svg, "data-kubus"))
        assert kubus == p["baris"] * p["kolom"]
        lapis = int(re.search(r"Ada (\d+) lapisan", soal.teks).group(1))
        assert lapis == p["lapis"]
        assert str(kubus * lapis) == soal.kunci


@pytest.mark.parametrize("baris,kolom,lapis,kunci", [(2, 2, 2, "8"), (5, 5, 5, "125"), (2, 5, 3, "30")])
def test_kubus_berlapis_nilai_tepi(baris, kolom, lapis, kunci):
    assert _bangun("bgn_kubus_berlapis", baris=baris, kolom=kolom, lapis=lapis).kunci == kunci

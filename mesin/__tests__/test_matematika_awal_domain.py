"""Matematika Awal, jenis kenali_bentuk (P1/P2): domain, solver teks, malrule, PG; komposisi topik.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal: fakta bangun datar
ditulis ulang di tes ini (bukan diimpor dari modul topik) dan teks ciri dibaca
lewat regex menjadi syarat yang dievaluasi terhadap fakta itu. Malrule hanya
HIPOTESIS kesalahan umum yang ditinjau guru; yang dijaga di sini: bukan kunci
(setelah normalisasi jawaban aplikasi), tidak kembar, dan selalu ada jalur K.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import diagnosis
import generator
import topics
from choice_generation import buat_lembar_pilihan, kandidat, kebijakan_soal
from baseline_matematika_awal import JENIS_PER_LEVEL, LEVEL_AWAL, TEMPLATE_AWAL
from templates import REGISTRI

TOPIK = "matematika-awal"
TID = "kenali_bentuk"
LEVEL = ("P1", "P2")
SEED = range(200)
VARIAN = ("dari_ciri", "benda", "banyak_sisi")
AKAR_MESIN = Path(__file__).resolve().parents[1]
UKURAN_DOMAIN = {"P1": 19, "P2": 26}
LEMBAR_PANJANG = 10

# ── fakta ditulis ulang di tes (sumber independen) ───────────────────────

HIMPUNAN_TES = {
    "P1": ("segitiga", "persegi", "lingkaran"),
    "P2": ("segitiga", "persegi", "persegi panjang", "lingkaran"),
}
SIFAT = {
    "segitiga": dict(sisi=3, sudut=3, bulat=False, semua_sama=False, berhadapan=False,
                     dua_ukuran=False, sudut_sama=False),
    "persegi": dict(sisi=4, sudut=4, bulat=False, semua_sama=True, berhadapan=True,
                    dua_ukuran=False, sudut_sama=True),
    "persegi panjang": dict(sisi=4, sudut=4, bulat=False, semua_sama=False, berhadapan=True,
                            dua_ukuran=True, sudut_sama=True),
    "lingkaran": dict(sisi=0, sudut=0, bulat=True, semua_sama=False, berhadapan=False,
                      dua_ukuran=False, sudut_sama=False),
}
BENDA_TES = {
    "uang logam": "lingkaran",
    "bagian depan jam dinding yang bulat": "lingkaran",
    "keping CD": "lingkaran",
    "kertas origami": "persegi",
    "satu kotak pada papan catur": "persegi",
    "satu permukaan dadu": "persegi",
    "penggaris segitiga": "segitiga",
    "potongan roti tawar persegi yang dipotong miring dari pojok ke pojok": "segitiga",
    "sampul buku tulis": "persegi panjang",
    "bendera Merah Putih": "persegi panjang",
    "pintu kelas yang dilihat dari depan": "persegi panjang",
}
# Pola ciri, urut dari yang paling spesifik; tiap pola membuang teks yang dikenalinya.
ATOM = (
    (r"tidak punya sudut sama sekali", lambda s, m: s["sudut"] == 0),
    (r"tidak punya sudut", lambda s, m: s["sudut"] == 0),
    (r"tidak punya sisi lurus", lambda s, m: s["sisi"] == 0),
    (r"berbentuk bulat", lambda s, m: s["bulat"]),
    (r"(\d) sisi yang semuanya sama panjang", lambda s, m: s["sisi"] == int(m[0]) and s["semua_sama"]),
    (r"(\d) sisi sama panjang", lambda s, m: s["sisi"] == int(m[0]) and s["semua_sama"]),
    (r"(\d) sisi, yaitu 2 sisi panjang dan 2 sisi pendek",
     lambda s, m: s["sisi"] == int(m[0]) and s["dua_ukuran"]),
    (r"(\d) sisi dengan sepasang sisi panjang dan sepasang sisi pendek",
     lambda s, m: s["sisi"] == int(m[0]) and s["dua_ukuran"]),
    (r"(\d) sudut sama besar", lambda s, m: s["sudut"] == int(m[0]) and s["sudut_sama"]),
    (r"sisi yang berhadapan sama panjang", lambda s, m: s["berhadapan"]),
    (r"tidak semua sisinya sama panjang", lambda s, m: not s["semua_sama"] and s["sisi"] > 0),
    (r"(\d) sisi lurus", lambda s, m: s["sisi"] == int(m[0])),
    (r"(\d) sisi dan (\d) sudut", lambda s, m: s["sisi"] == int(m[0]) and s["sudut"] == int(m[1])),
    (r"(\d) sisi", lambda s, m: s["sisi"] == int(m[0])),
    (r"(\d) sudut", lambda s, m: s["sudut"] == int(m[0])),
)
SISA_BOLEH = {"punya", "dan", "yang", ",", "tetapi", "dengan"}


def _syarat(klausa: str) -> list:
    sisa, syarat = klausa, []
    for pola, uji in ATOM:
        for cocok in re.finditer(pola, sisa):
            syarat.append((uji, cocok.groups()))
        sisa = re.sub(pola, " ", sisa)
    kata = set(sisa.replace(",", " , ").split())
    assert kata <= SISA_BOLEH, ("ciri tidak terbaca penuh", klausa, kata - SISA_BOLEH)
    assert syarat, ("ciri kosong", klausa)
    return syarat


def solver_dari_teks(teks: str, level: str) -> str:
    """Kunci dari teks saja; sengaja tidak memakai parameter atau modul topik."""
    cocok = re.fullmatch(r"Bangun apa yang (.+)\?", teks)
    if cocok:
        syarat = _syarat(cocok.group(1))
        lolos = [b for b in HIMPUNAN_TES[level]
                 if all(uji(SIFAT[b], m) for uji, m in syarat)]
        assert len(lolos) == 1, ("ciri harus menunjuk tepat satu bangun", teks, level, lolos)
        return lolos[0]
    cocok = re.fullmatch(r"Bentuk (.+) seperti bangun apa\?", teks)
    if cocok:
        assert cocok.group(1) in BENDA_TES, ("benda tidak dikenal", teks)
        bangun = BENDA_TES[cocok.group(1)]
        assert bangun in HIMPUNAN_TES[level], ("bangun di luar himpunan level", teks, level)
        return bangun
    cocok = re.fullmatch(r"Berapa banyak sisi (.+)\?", teks)
    if cocok:
        assert cocok.group(1) in HIMPUNAN_TES[level] and SIFAT[cocok.group(1)]["sisi"] > 0
        return str(SIFAT[cocok.group(1)]["sisi"])
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def _soal(level: str, seed: int):
    return generator._soal_layak(topics.ambil(TOPIK), TID, random.Random(seed), level)


def _domain(level: str) -> tuple:
    return topics.ambil(TOPIK).domain_parameter(TID, level)


def _soal_dari_parameter(parameter: dict, level: str):
    from dataclasses import replace
    return replace(REGISTRI[TID](**parameter), level=level)


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


# ── pendaftaran dan palang struktur ──────────────────────────────────────

def test_topik_terdaftar_memuat_dua_puluh_lima_jenis_dan_komposisi_level():
    paket = topics.ambil(TOPIK)
    assert tuple(paket.komposisi) == LEVEL_AWAL == ("P1", "P2", "P3", "P4", "P5", "P6")
    for level in LEVEL_AWAL:
        assert set(paket.komposisi[level]) == JENIS_PER_LEVEL[level]
        assert len(paket.komposisi_untuk(level)) == LEMBAR_PANJANG
    for level in LEVEL:
        assert TID in paket.komposisi[level]
    # komposisi persis sesuai keputusan pemilik (daftar eksplisit, bukan dibaca dari topik)
    assert JENIS_PER_LEVEL == {
        "P1": {"kenali_bentuk", "ukur_satuan_tak_baku", "baca_diagram_gambar",
               "bilang_benda_awal", "tambah_kurang_20", "kenali_bangun_awal"},
        "P2": {"kenali_bentuk", "baca_diagram_gambar", "pola_posisi", "pecahan_setengah",
               "waktu_berat_awal", "turus_gambar_awal", "tambah_kurang_100", "kenali_bangun_awal",
               "baca_jam_awal"},
        "P3": {"ukur_konversi_awal", "unsur_bangun_datar"},
        "P4": {"pecahan_senilai_desimal", "luas_petak_volume_kubus", "ciri_komposisi_bangun"},
        "P5": {"bandingkan_ciri_bangun", "keliling_gabungan", "ukur_sudut_awal", "piktogram_lima_awal"},
        "P6": {"peluang_dasar", "pecahan_bilangan_asli_desimal", "pecahan_campur_awal", "tampak_kubus_awal"},
    }
    assert set(paket.templates) == set(TEMPLATE_AWAL)
    assert len(paket.templates) == 25
    assert paket.hanya_manual is True
    assert paket.unik_per_lembar is True
    assert paket.nama == "Matematika Awal"
    assert TID in topics.registri() and TID in REGISTRI


def test_template_id_unik_global_dan_dimiliki_satu_topik():
    pemilik = [t for t in topics.daftar_topik() if TID in topics.ambil(t).templates]
    # Campuran dan paket sintetis tidak boleh memuatnya; pemilik asli tepat satu.
    assert pemilik == [TOPIK]
    assert topics.pemilik_template(TID) == TOPIK


def test_level_di_luar_komposisi_berperilaku_seperti_preseden():
    paket = topics.ambil(TOPIK)
    # Semua level P1-P6 punya jenis (P4 sejak gelombang 1); level yang ada tapi tanpa kenali_bentuk
    # menolak jenis ini.
    for level in ("P3", "P4", "P5", "P6"):
        with pytest.raises(ValueError, match="tidak tersedia untuk level"):
            generator.buat_soal(TID, 0, level, TOPIK)
    assert paket.komposisi_untuk("P4") == paket.komposisi["P4"]
    # Label level liar dari kolom teks bebas jatuh ke level pertama topik, bukan error.
    assert generator.buat_lembar(0, level="kelas 4", topik=TOPIK).level == "P1"
    with pytest.raises(ValueError):
        paket.parameter_untuk(TID, random.Random(0), "P3")
    with pytest.raises(KeyError):
        paket.parameter_untuk("tidak_ada", random.Random(0), "P1")
    with pytest.raises(KeyError):
        paket.domain_parameter("tidak_ada", "P1")
    with pytest.raises(ValueError):
        paket.domain_parameter(TID, "P3")


# ── domain dan sampler ───────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_domain_enumerator_eksplisit_dan_sampler_tetap_di_dalamnya(level):
    domain = _domain(level)
    assert len(domain) == UKURAN_DOMAIN[level]
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    paket = topics.ambil(TOPIK)
    for seed in SEED:
        p = paket.parameter_untuk(TID, random.Random(seed), level)
        assert json.dumps(p, sort_keys=True) in kanon, (level, seed, p)
    # dict baru tiap panggilan: pemanggil tidak boleh bisa menodai domain
    _domain(level)[0]["bangun"] = "rusak"
    assert _domain(level)[0]["bangun"] != "rusak"


@pytest.mark.parametrize("level", LEVEL)
def test_domain_mencakup_ketiga_varian_dan_hanya_bangun_level(level):
    domain = _domain(level)
    assert {p["varian"] for p in domain} == set(VARIAN)
    assert {p["bangun"] for p in domain if p["varian"] != "benda"} <= set(HIMPUNAN_TES[level])
    assert {p["bangun"] for p in domain} == set(HIMPUNAN_TES[level])
    if level == "P1":
        assert all(p["bangun"] != "persegi panjang" for p in domain)
        assert all(p["himpunan"] == "dasar" for p in domain)
    else:
        assert {"persegi panjang"} <= {p["bangun"] for p in domain}
        assert all(p["himpunan"] == "lengkap" for p in domain)
    assert all(p["bangun"] != "lingkaran" for p in domain if p["varian"] == "banyak_sisi")


@pytest.mark.parametrize("level", LEVEL)
def test_seluruh_domain_menghasilkan_soal_sah_dengan_kunci_solver(level):
    for p in _domain(level):
        soal = _soal_dari_parameter(p, level)
        assert soal.kunci == solver_dari_teks(soal.teks, level), (level, p, soal.teks)
        assert soal.parameter == p
        assert soal.kunci == soal.kunci.strip().lower()


@pytest.mark.parametrize("level", LEVEL)
def test_sapuan_seed_kunci_sama_dengan_solver(level):
    for seed in SEED:
        soal = _soal(level, seed)
        assert soal.kunci == solver_dari_teks(soal.teks, level), (level, seed, soal.teks)
        assert soal.level == level and soal.bagian == "A"


def test_p2_memuat_perbedaan_persegi_dan_persegi_panjang():
    teks = {_soal_dari_parameter(p, "P2").teks for p in _domain("P2")}
    kunci = {_soal_dari_parameter(p, "P2").kunci for p in _domain("P2")}
    assert {"persegi", "persegi panjang"} <= kunci
    assert any("berhadapan" in t for t in teks) and any("sama panjang" in t for t in teks)
    # P1 belum memperkenalkan persegi panjang sebagai jawaban ataupun pengecoh
    for p in _domain("P1"):
        soal = _soal_dari_parameter(p, "P1")
        assert soal.kunci != "persegi panjang"
        assert "persegi panjang" not in {m.jawaban for m in soal.malrule}
        assert "persegi panjang" not in soal.teks and "persegi panjang" not in soal.pembahasan


# ── malrule ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k(level):
    for p in _domain(level):
        soal = _soal_dari_parameter(p, level)
        kunci = _norm(soal.kunci)
        jawaban = [_norm(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (level, p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (level, p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (level, p, "tanpa jalur K")
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)


@pytest.mark.parametrize("level", LEVEL)
def test_malrule_nama_bangun_hanya_dari_himpunan_level(level):
    for p in _domain(level):
        soal = _soal_dari_parameter(p, level)
        if p["varian"] == "banyak_sisi":
            continue
        assert {m.jawaban for m in soal.malrule} == set(HIMPUNAN_TES[level]) - {soal.kunci}


def test_banyak_sisi_punya_jalur_k_dan_h():
    for level in LEVEL:
        for p in _domain(level):
            if p["varian"] != "banyak_sisi":
                continue
            soal = _soal_dari_parameter(p, level)
            kode = {m.kode for m in soal.malrule}
            assert kode == {"K", "H"}, (level, p)
            k = int(soal.kunci)
            h = {int(m.jawaban) for m in soal.malrule if m.kode == "H"}
            assert h == {k - 1, k + 1}
            assert 2 * k in {int(m.jawaban) for m in soal.malrule if m.kode == "K"}


def test_alasan_malrule_dan_pembahasan_bahasa_anak_tanpa_istilah_guru():
    terlarang = re.compile(r"malrule|diagnosis|kode intervensi|template|kunci|hipotesis", re.I)
    for level in LEVEL:
        for p in _domain(level):
            soal = _soal_dari_parameter(p, level)
            assert not terlarang.search(soal.teks), soal.teks
            assert not terlarang.search(soal.pembahasan), soal.pembahasan
            assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
            assert soal.pembahasan.strip() != soal.kunci
            assert "Cocokkan dengan caramu" not in soal.pembahasan
            assert len(soal.pembahasan) > 40


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", himpunan="dasar", bangun="persegi"),
    dict(varian="banyak_sisi", himpunan="entah", bangun="persegi"),
    dict(varian="banyak_sisi", himpunan="dasar", bangun="persegi panjang"),
    dict(varian="banyak_sisi", himpunan="lengkap", bangun="lingkaran"),
    dict(varian="banyak_sisi", himpunan="lengkap", bangun="belah ketupat"),
    dict(varian="dari_ciri", himpunan="dasar", bangun="persegi", ciri=3),
    dict(varian="dari_ciri", himpunan="dasar", bangun="persegi", ciri=-1),
    dict(varian="dari_ciri", himpunan="dasar", bangun="persegi", ciri="0"),
    dict(varian="dari_ciri", himpunan="dasar", bangun="persegi"),
    dict(varian="dari_ciri", himpunan="dasar", bangun="persegi", ciri=0, benda=0),
    dict(varian="benda", himpunan="dasar", bangun="persegi panjang", benda=0),
    dict(varian="benda", himpunan="lengkap", bangun="persegi", benda=9),
    dict(varian="benda", himpunan="lengkap", bangun="persegi"),
    dict(varian="banyak_sisi", himpunan="dasar", bangun="persegi", ciri=0),
    dict(varian="banyak_sisi", himpunan=None, bangun="persegi"),
    dict(varian="banyak_sisi", himpunan="dasar", bangun=["persegi"]),
])
def test_parameter_tidak_sah_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        REGISTRI[TID](**parameter)


def test_kunci_contoh_tangan():
    f = REGISTRI[TID]
    assert f(varian="banyak_sisi", himpunan="lengkap", bangun="persegi panjang").kunci == "4"
    assert f(varian="banyak_sisi", himpunan="dasar", bangun="segitiga").kunci == "3"
    assert f(varian="dari_ciri", himpunan="dasar", bangun="segitiga", ciri=0).kunci == "segitiga"
    assert f(varian="dari_ciri", himpunan="dasar", bangun="segitiga", ciri=0).teks == (
        "Bangun apa yang punya 3 sisi dan 3 sudut?")
    assert f(varian="benda", himpunan="dasar", bangun="lingkaran", benda=0).teks == (
        "Bentuk uang logam seperti bangun apa?")


def test_jawaban_isian_huruf_besar_dan_spasi_tetap_dianggap_benar():
    soal = REGISTRI[TID](varian="dari_ciri", himpunan="lengkap", bangun="persegi panjang", ciri=0)
    for ketikan in ("persegi panjang", "Persegi Panjang", "  PERSEGI   panjang. "):
        assert diagnosis.setara(ketikan, soal.kunci, soal=soal), ketikan
    assert not diagnosis.setara("persegipanjang", soal.kunci, soal=soal)
    assert not diagnosis.setara("persegi", soal.kunci, soal=soal)


# ── lembar ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_lembar_sepuluh_soal_tanpa_duplikat_dan_memuat_semua_varian(level):
    for seed in range(60):
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK)
        assert len(lembar.soal) == LEMBAR_PANJANG and lembar.level == level
        tanda = [s.tanda_tangan for s in lembar.soal]
        assert len(set(tanda)) == LEMBAR_PANJANG, (level, seed, "soal kembar dalam lembar")
        assert {s.template_id for s in lembar.soal} == JENIS_PER_LEVEL[level]
        assert {s.bagian for s in lembar.soal} == {"A"}
    varian = {s.parameter["varian"] for seed in range(30)
              for s in generator.buat_lembar(seed, level=level, topik=TOPIK).soal
              if s.template_id == TID}
    assert varian == set(VARIAN)


def test_judul_bagian_tunggal_dan_render_lembar_tanpa_kunci():
    import render
    paket = topics.ambil(TOPIK)
    assert set(paket.judul_bagian) == {"A"}
    lembar = generator.buat_lembar(3, level="P2", topik=TOPIK)
    html = render.lembar_soal(list(lembar.soal), topik_paket=paket)
    assert html.count('class="bagian"') == 1, "judul bagian berulang"
    for s in lembar.soal:
        assert s.teks.split("\n")[0] in html.replace("&#x27;", "'")


# ── pilihan ganda ────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_pilihan_ganda_seluruh_domain_dan_kebijakan_per_varian(level):
    for p in _domain(level):
        soal = _soal_dari_parameter(p, level)
        kebijakan, jenis = kebijakan_soal(soal)
        assert kebijakan == "tiga-v1"
        assert jenis == ("angka" if p["varian"] == "banyak_sisi" else "kategori")
        _, _, pengecoh = kandidat(soal)
        assert len(pengecoh) == 2 and soal.kunci not in pengecoh
        assert len({_norm(x) for x in pengecoh}) == 2


@pytest.mark.parametrize("level", LEVEL)
def test_pilihan_ganda_lembar_dibuat_untuk_banyak_seed(level):
    for seed in range(80):
        lembar = buat_lembar_pilihan(seed, level=level, topik=TOPIK)
        assert len(lembar.soal) == LEMBAR_PANJANG


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, os, sys
sys.path.insert(0, %(akar)r)
for k, v in {"OSN_PBKDF2_ITERASI": "1000", "OSN_MATEMATIKA_VERSI": "2",
             "OSN_TEORI_BILANGAN_VERSI": "2", "OSN_KATALOG_VERSI": "1"}.items():
    os.environ.setdefault(k, v)
import generator
hasil = []
for level in ("P1", "P2"):
    for seed in range(40):
        for s in generator.buat_lembar(seed, level=level, topik="matematika-awal").soal:
            hasil.append([s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                          [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
print(json.dumps(hasil))
"""


def _proses(hash_seed: str):
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSN_MATEMATIKA_AWAL")}
    env.update({"PYTHONHASHSEED": hash_seed, "OSN_MATERI_DASAR": "1"})
    hasil = subprocess.run([sys.executable, "-c", _KODE % {"akar": str(AKAR_MESIN)}],
                           env=env, capture_output=True, text=True, timeout=180)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 2 * 40 * LEMBAR_PANJANG

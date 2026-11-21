"""Matematika Awal, jenis ukur_sudut_awal (P5): domain, solver teks, malrule, PG, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (tanpa gambar), lihat
`sudut_solver_helpers`: letak kaki sudut pada kedua skala dibaca lewat regex dan besar sudut,
golongan, perbandingan, dan selisih dihitung dengan rumus sendiri. Malrule hanya HIPOTESIS
kesalahan umum untuk ditinjau guru; yang dijaga: bukan kunci, tidak kembar, selalu ada jalur K.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

import pytest

import awal_ukur_sudut_awal as jenis
import diagnosis
import generator
import matematika_awal_versions as versi
import kurikulum_cp
import kurikulum_katalog
import render
import rumus
import template_labels
import topics
from choice_generation import kandidat, kebijakan_soal
from multiple_choice import nilai_semantis
from sudut_solver_helpers import TANYA_BANDING, TANYA_BESAR, TANYA_JENIS, TANYA_SELISIH, solver_dari_teks
from templates import REGISTRI

TOPIK = "matematika-awal"
TID = "ukur_sudut_awal"
LEVEL = ("P5",)
VARIAN = ("baca_dari_nol", "baca_geser", "jenis_sudut", "banding", "selisih_dua")
SEED = range(200)
AKAR_MESIN = Path(__file__).resolve().parents[1]
UKURAN_DOMAIN = {"baca_dari_nol": 64, "baca_geser": 272, "jenis_sudut": 66, "banding": 544,
                 "selisih_dua": 544}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)


def _soal(p: dict):
    return jenis.ukur_sudut_awal(**p)


def _domain() -> tuple:
    return jenis.domain_parameter("P5")


def _varian(*nama) -> list:
    return [p for p in _domain() if p["varian"] in nama]


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == jenis.ukur_sudut_awal.__name__
    assert jenis.LEVEL == LEVEL and jenis.VARIAN == VARIAN
    for level in ("P1", "P2", "P4", "P6", "", None):
        with pytest.raises(ValueError):
            jenis.domain_parameter(level)
        with pytest.raises(ValueError):
            jenis.parameter(random.Random(0), level)


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat():
    domain = _domain()
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain) == 1490
    assert len({_soal(p).tanda_tangan for p in domain}) == len(domain)


def test_domain_dibangun_cepat_dan_urut_per_varian():
    awal = time.monotonic()
    domain = _domain()
    assert time.monotonic() - awal < 5
    urutan = [p["varian"] for p in domain]
    assert urutan == sorted(urutan, key=VARIAN.index), "domain harus urut menurut VARIAN"


def test_domain_dict_baru_setiap_panggilan_dan_sampler_murni():
    a = _domain()
    a[-1]["b"] = 999
    a[-1]["varian"] = "rusak"
    b = _domain()
    assert b[-1]["varian"] == "selisih_dua" and b[-1]["b"] != 999
    p = jenis.parameter(random.Random(0), "P5")
    q = jenis.parameter(random.Random(0), "P5")
    assert p == q and p is not q


def test_domain_rentang_kelipatan_dan_arah_tercakup():
    tunggal = _varian("baca_dari_nol", "jenis_sudut")
    assert {p["arah"] for p in tunggal} == {"kanan", "kiri"}
    assert all(p["sudut"] % 5 == 0 and 10 <= p["sudut"] <= 170 for p in tunggal)
    assert {p["sudut"] for p in _varian("baca_dari_nol")} == set(range(10, 171, 5)) - {90}
    assert {p["sudut"] for p in _varian("jenis_sudut")} == set(range(10, 171, 5))
    for p in _varian("baca_geser", "banding", "selisih_dua"):
        for kunci in ("a", "b", "c"):
            if kunci in p:
                assert p[kunci] % 10 == 0 and 10 <= p[kunci] <= 170
        assert len({v for k, v in p.items() if k in ("a", "b", "c")}) == 2, "dua sudut selalu berbeda"
    geser = _varian("baca_geser")
    assert any(p["a"] < p["b"] for p in geser) and any(p["a"] > p["b"] for p in geser)
    for varian in ("banding", "selisih_dua"):
        sub = _varian(varian)
        assert {p["arah"] for p in sub} == {"kanan", "kiri"}
        assert any(p["b"] < p["c"] for p in sub) and any(p["b"] > p["c"] for p in sub)


def test_sudut_siku_hanya_pada_jenis_sudut_dan_tiga_jenis_kunci_ada():
    assert all(p["sudut"] != 90 for p in _varian("baca_dari_nol"))
    kunci = {p["sudut"]: _soal(p).kunci for p in _varian("jenis_sudut")}
    assert {kunci[s] for s in kunci} == {"lancip", "siku", "tumpul"}
    assert [s for s, k in kunci.items() if k == "siku"] == [90]
    assert kunci[85] == "lancip" and kunci[95] == "tumpul"


def test_kunci_banding_seimbang_antara_b_dan_c_per_arah():
    for arah in ("kanan", "kiri"):
        hitung = {"B": 0, "C": 0}
        for p in _varian("banding"):
            if p["arah"] == arah:
                hitung[_soal(p).kunci] += 1
        assert hitung["B"] == hitung["C"] == 136, (arah, hitung)


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian = set()
    for seed in SEED:
        p = jenis.parameter(random.Random(seed), "P5")
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
    assert varian == set(VARIAN)


def test_sebaran_varian_pada_sampel_2000_hampir_seragam():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(2000):
        hitung[jenis.parameter(random.Random(seed), "P5")["varian"]] += 1
    assert all(320 <= n <= 480 for n in hitung.values()), hitung


# ── kunci lawan solver teks (seluruh domain) ─────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID


def test_kunci_berbentuk_angka_derajat_atau_kata_jenis_atau_huruf_menurut_varian():
    for p in _domain():
        kunci = _soal(p).kunci
        if p["varian"] == "jenis_sudut":
            assert kunci in ("lancip", "siku", "tumpul")
        elif p["varian"] == "banding":
            assert kunci in ("B", "C")
        else:
            assert re.fullmatch(r"\d{2,3}", kunci) and 10 <= int(kunci) <= 170, (p, kunci)


def test_sampel_seed_kunci_sama_dengan_solver_teks():
    for seed in SEED:
        soal = _soal(jenis.parameter(random.Random(seed), "P5"))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_solver_tidak_meloloskan_teks_ambigu_atau_tidak_konsisten():
    nol = "Kaki BA menunjuk angka 0 pada skala luar busur derajat."
    kaki = "Kaki BC menunjuk angka 70 pada skala luar dan angka 110 pada skala dalam."
    with pytest.raises(AssertionError):  # kedua angka tidak saling melengkapi 180
        solver_dari_teks(f"{nol} Kaki BC menunjuk angka 70 pada skala luar dan angka 100 pada skala dalam.\n"
                         f"{TANYA_BESAR}")
    with pytest.raises(AssertionError):  # kedua angka pada skala yang sama
        solver_dari_teks(f"{nol} Kaki BC menunjuk angka 70 pada skala luar dan angka 110 pada skala luar.\n"
                         f"{TANYA_BESAR}")
    with pytest.raises(AssertionError):  # tanpa kaki alas
        solver_dari_teks(f"{kaki}\n{TANYA_BESAR}")
    with pytest.raises(AssertionError):  # sisa teks tak terbaca
        solver_dari_teks(f"{nol} {kaki} Catatan.\n{TANYA_BESAR}")
    with pytest.raises(AssertionError):  # pertanyaan tak dikenal
        solver_dari_teks(f"{nol} {kaki}\nBerapa sudutnya?")
    with pytest.raises(AssertionError):
        solver_dari_teks(f"{nol} {kaki}\n{TANYA_BESAR}\nTambahan.")
    with pytest.raises(AssertionError):  # banding butuh dua kaki
        solver_dari_teks(f"{nol} {kaki}\n{TANYA_BANDING}")


def test_teks_contoh_tangan_tiap_varian():
    f = jenis.ukur_sudut_awal
    kanan = f("baca_dari_nol", arah="kanan", sudut=70)
    assert kanan.teks == (
        "Kaki BA menunjuk angka 0 pada skala luar busur derajat. "
        "Kaki BC menunjuk angka 70 pada skala luar dan angka 110 pada skala dalam.\n"
        "Berapa besar sudut ABC? Tulis angkanya saja.")
    assert kanan.kunci == "70"
    kiri = f("baca_dari_nol", arah="kiri", sudut=70)
    assert kiri.teks == (
        "Kaki BA menunjuk angka 0 pada skala dalam busur derajat. "
        "Kaki BC menunjuk angka 70 pada skala dalam dan angka 110 pada skala luar.\n"
        "Berapa besar sudut ABC? Tulis angkanya saja.")
    geser = f("baca_geser", a=30, b=110)
    assert geser.teks == (
        "Pada skala luar busur derajat, kaki BA menunjuk angka 30 dan kaki BC menunjuk angka 110.\n"
        "Berapa besar sudut ABC? Tulis angkanya saja.")
    assert geser.kunci == "80" and f("baca_geser", a=110, b=30).kunci == "80"
    jenis_ = f("jenis_sudut", arah="kanan", sudut=130)
    assert jenis_.teks.endswith("\nSudut ABC termasuk jenis apa? Tulis lancip, siku, atau tumpul.")
    assert jenis_.kunci == "tumpul"
    banding = f("banding", arah="kiri", b=40, c=110)
    assert banding.teks == (
        "Kaki OA menunjuk angka 0 pada skala dalam busur derajat. "
        "Kaki OB menunjuk angka 40 pada skala dalam dan angka 140 pada skala luar. "
        "Kaki OC menunjuk angka 110 pada skala dalam dan angka 70 pada skala luar.\n"
        "Sudut mana yang lebih besar, AOB atau AOC? Tulis B atau C.")
    assert banding.kunci == "C"
    selisih = f("selisih_dua", arah="kanan", b=150, c=60)
    assert selisih.teks.endswith("\nBerapa selisih besar sudut AOB dan sudut AOC? Tulis angkanya saja.")
    assert selisih.kunci == "90"


def test_pertanyaan_di_baris_terakhir_tanpa_digit_dan_pengantar_tanpa_gambar():
    for p in _domain()[::5]:
        soal = _soal(p)
        pengantar, tanya = soal.teks.split("\n")
        assert tanya in (TANYA_BESAR, TANYA_JENIS, TANYA_BANDING, TANYA_SELISIH)
        assert not re.search(r"\d", tanya), tanya
        assert "Perhatikan gambar" not in soal.teks
        assert pengantar.endswith(".") and soal.teks.count("?") == 1


def test_teks_memuat_dua_skala_dan_skala_alas_menurut_arah():
    for p in _varian("baca_dari_nol", "jenis_sudut", "banding", "selisih_dua"):
        pengantar = _soal(p).teks.split("\n")[0]
        nol, lain = ("luar", "dalam") if p["arah"] == "kanan" else ("dalam", "luar")
        assert pengantar.startswith(f"Kaki {'B' if 'sudut' in p else 'O'}A menunjuk angka 0 pada skala {nol}")
        assert pengantar.count(f"pada skala {nol}") >= 2 and pengantar.count(f"pada skala {lain}") >= 1


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        kunci = _norm(soal.kunci)
        jawaban = [_norm(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)
        assert not any(TERLARANG.search(m.alasan) for m in soal.malrule), p


def test_malrule_angka_sah_antara_5_dan_180_dan_kata_hanya_jenis_atau_huruf():
    for p in _domain():
        for m in _soal(p).malrule:
            if p["varian"] == "jenis_sudut":
                assert m.jawaban in ("lancip", "siku", "tumpul")
            elif p["varian"] == "banding":
                assert m.jawaban in ("B", "C")
            else:
                assert 5 <= int(m.jawaban) <= 180 and int(m.jawaban) % 5 == 0, (p, m.jawaban)


def test_malrule_baca_dari_nol_skala_salah_dan_meleset():
    m = _malrule(dict(varian="baca_dari_nol", arah="kanan", sudut=70))
    assert (m["salah_skala"].jawaban, m["salah_skala"].kode) == ("110", "K")
    assert (m["lebih_sepuluh"].jawaban, m["lebih_sepuluh"].kode) == ("80", "H")
    assert (m["kurang_sepuluh"].jawaban, m["kurang_lima"].jawaban) == ("60", "65")
    assert m["lebih_lima"].jawaban == "75"
    assert _malrule(dict(varian="baca_dari_nol", arah="kiri", sudut=70))["salah_skala"].jawaban == "110"
    ujung_bawah = _malrule(dict(varian="baca_dari_nol", arah="kanan", sudut=10))
    assert "kurang_sepuluh" not in ujung_bawah and ujung_bawah["kurang_lima"].jawaban == "5"
    ujung_atas = _malrule(dict(varian="baca_dari_nol", arah="kiri", sudut=170))
    assert ujung_atas["lebih_sepuluh"].jawaban == "180" and ujung_atas["salah_skala"].jawaban == "10"


def test_malrule_baca_dari_nol_dekat_sembilan_puluh_tetap_punya_jalur_k():
    m = _malrule(dict(varian="baca_dari_nol", arah="kanan", sudut=85))
    assert m["salah_skala"].jawaban == "95" and m["lebih_lima"].jawaban == "90"
    m95 = _malrule(dict(varian="baca_dari_nol", arah="kanan", sudut=95))
    assert m95["salah_skala"].jawaban == "85" and m95["kurang_lima"].jawaban == "90"
    kembar = _malrule(dict(varian="baca_dari_nol", arah="kanan", sudut=80))
    assert "lebih_sepuluh" in kembar and kembar["salah_skala"].jawaban == "100"


def test_malrule_jenis_sudut_salah_skala_siku_dibulatkan_dan_siku_dua_jalur_k():
    lancip = _malrule(dict(varian="jenis_sudut", arah="kanan", sudut=30))
    assert set(lancip) == {"salah_skala"} and lancip["salah_skala"].jawaban == "tumpul"
    tumpul = _malrule(dict(varian="jenis_sudut", arah="kiri", sudut=150))
    assert set(tumpul) == {"salah_skala"} and tumpul["salah_skala"].jawaban == "lancip"
    dekat = _malrule(dict(varian="jenis_sudut", arah="kanan", sudut=85))
    assert dekat["salah_skala"].jawaban == "tumpul"
    assert (dekat["dibulatkan_siku"].jawaban, dekat["dibulatkan_siku"].kode) == ("siku", "H")
    dekat_tumpul = _malrule(dict(varian="jenis_sudut", arah="kanan", sudut=100))
    assert dekat_tumpul["dibulatkan_siku"].jawaban == "siku" and dekat_tumpul["salah_skala"].jawaban == "lancip"
    jauh = _malrule(dict(varian="jenis_sudut", arah="kanan", sudut=70))
    assert "dibulatkan_siku" not in jauh
    siku = _malrule(dict(varian="jenis_sudut", arah="kanan", sudut=90))
    assert {m.jawaban for m in siku.values()} == {"lancip", "tumpul"}
    assert {m.kode for m in siku.values()} == {"K"}


def test_malrule_baca_geser_lupa_kurangi_campur_skala_dan_jumlah():
    m = _malrule(dict(varian="baca_geser", a=30, b=110))
    assert (m["lupa_kurangi"].jawaban, m["lupa_kurangi"].kode) == ("110", "K")
    assert (m["campur_skala"].jawaban, m["campur_skala"].kode) == ("40", "K")
    assert (m["jumlah_bukan_selisih"].jawaban, m["jumlah_bukan_selisih"].kode) == ("140", "K")
    assert m["lebih_sepuluh"].jawaban == "90" and m["kurang_sepuluh"].jawaban == "70"
    assert _malrule(dict(varian="baca_geser", a=110, b=30))["lupa_kurangi"].jawaban == "110"
    besar = _malrule(dict(varian="baca_geser", a=90, b=170))
    assert "jumlah_bukan_selisih" not in besar, "90 + 170 melewati 180"
    assert "campur_skala" not in besar, "campur skala sama dengan kunci bila salah satu kaki di 90"
    assert besar["lupa_kurangi"].jawaban == "170"
    nol = _malrule(dict(varian="baca_geser", a=70, b=110))
    assert "campur_skala" not in nol, "70 + 110 = 180: campur skala bernilai 0, bukan jawaban"


def test_malrule_banding_huruf_lawan_dan_pengecoh_tambahan():
    m = _malrule(dict(varian="banding", arah="kanan", b=40, c=110))
    assert set(m) == {"salah_skala"} and (m["salah_skala"].jawaban, m["salah_skala"].kode) == ("B", "K")
    assert _malrule(dict(varian="banding", arah="kiri", b=110, c=40))["salah_skala"].jawaban == "C"
    assert jenis.pengecoh_tambahan({"varian": "banding"}) == ("sama besar",)
    assert jenis.pengecoh_tambahan({"varian": "jenis_sudut"}) == ("lancip", "siku", "tumpul")
    assert jenis.pengecoh_tambahan({"varian": "baca_geser"}) == ()


def test_malrule_selisih_dua_sudut_besar_saja_campur_dan_jumlah():
    m = _malrule(dict(varian="selisih_dua", arah="kanan", b=40, c=80))
    assert (m["sudut_besar_saja"].jawaban, m["sudut_besar_saja"].kode) == ("80", "K")
    assert (m["campur_skala"].jawaban, m["campur_skala"].kode) == ("60", "K")
    assert (m["jumlah_bukan_selisih"].jawaban, m["jumlah_bukan_selisih"].kode) == ("120", "K")
    assert m["lebih_sepuluh"].jawaban == "50" and m["kurang_lima"].jawaban == "35"
    besar = _malrule(dict(varian="selisih_dua", arah="kiri", b=160, c=100))
    assert "jumlah_bukan_selisih" not in besar and besar["sudut_besar_saja"].jawaban == "160"


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_langkah():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan, (p, soal.pembahasan)
        assert len(soal.pembahasan) > 60 and soal.pembahasan.strip() != soal.kunci
        assert "derajat" in soal.pembahasan or p["varian"] == "banding"


def test_pembahasan_contoh_per_varian():
    f = jenis.ukur_sudut_awal
    nol = f("baca_dari_nol", arah="kiri", sudut=70).pembahasan
    assert "skala dalam" in nol and "Angka 110 pada skala luar tidak dipakai" in nol
    geser = f("baca_geser", a=30, b=110).pembahasan
    assert "110 dikurangi 30 sama dengan 80" in geser and "80 derajat" in geser
    jenis_ = f("jenis_sudut", arah="kanan", sudut=90).pembahasan
    assert "tepat 90 derajat, jadi sudut siku" in jenis_
    assert "jadi sudut lancip" in f("jenis_sudut", arah="kanan", sudut=20).pembahasan
    assert "jadi sudut tumpul" in f("jenis_sudut", arah="kiri", sudut=160).pembahasan
    banding = f("banding", arah="kanan", b=40, c=110).pembahasan
    assert "Angka 110 lebih besar dari 40, jadi sudut AOC yang lebih besar. Jawabannya C." in banding
    selisih = f("selisih_dua", arah="kanan", b=150, c=60).pembahasan
    assert "150 dikurangi 60 sama dengan 90" in selisih


# ── kartu rumus, label, katalog, pancingan, sakelar ──────────────────────

def test_kartu_rumus_label_katalog_dan_cp_terdaftar():
    kartu = rumus.kartu_untuk(TID)
    assert kartu is not None and kartu.judul.startswith("Mengukur dan membandingkan sudut")
    for kata in ("dua skala", "angka 0", "lancip", "siku", "tumpul", "skala yang sama"):
        assert kata in kartu.inti
    assert kartu.contoh.strip() and not TERLARANG.search(kartu.inti + kartu.contoh)
    assert TID in template_labels.NAMA_TIPE_SOAL
    grup = [g for entri in kurikulum_katalog.KATALOG if entri.topik_id == TOPIK for g in entri.grup]
    assert (TID, "Mengukur dan membandingkan sudut", (TID,)) in [tuple(g) for g in grup]
    assert kurikulum_cp.CP_PER_GRUP[(TOPIK, TID)] == (("C.pengukuran.3", "sebagian"),)


def test_pancingan_dan_template_baru_terdaftar():
    berkas = AKAR_MESIN / "konten" / "pancingan" / "matematika-awal.json"
    isi = json.loads(berkas.read_text(encoding="utf-8"))["template"][TID]
    assert len(isi["pertanyaan"]) == 3 and isi["tindak_lanjut"].strip()
    assert TID in versi.TEMPLATE_BARU
    assert TID in topics.ambil(TOPIK).templates and TID in REGISTRI
    assert topics.pemilik_template(TID) == TOPIK


def test_komposisi_topik_memuat_jenis_di_p5_saja_dan_hanya_manual():
    paket = topics.ambil(TOPIK)
    assert TID in paket.komposisi["P5"]
    for level in ("P1", "P2", "P3", "P4", "P6"):
        assert TID not in paket.komposisi[level]
        with pytest.raises(ValueError, match="tidak tersedia untuk level"):
            generator.buat_soal(TID, 0, level, TOPIK)
    assert paket.hanya_manual is True


def test_jenis_ini_tidak_masuk_keluarga_geometri_datar():
    assert TID not in topics.ambil("geometri-datar").templates
    assert topics.pemilik_template(TID) == TOPIK


# ── pilihan ganda ────────────────────────────────────────────────────────

def test_pilihan_ganda_seluruh_domain_tiga_opsi_pengecoh_cukup_dan_berbeda():
    for p in _domain():
        soal = _soal(p)
        kebijakan, jenis_kunci, pengecoh = kandidat(soal)
        kategori = p["varian"] in ("jenis_sudut", "banding")
        assert (kebijakan, jenis_kunci) == ("tiga-v1", "kategori" if kategori else "angka"), p
        assert len(pengecoh) == 2 and soal.kunci not in pengecoh, p
        semantik = {nilai_semantis(x, jenis_kunci) for x in pengecoh} | {nilai_semantis(soal.kunci, jenis_kunci)}
        assert len(semantik) == 3, p
        assert kebijakan_soal(soal) == (kebijakan, jenis_kunci)
        if p["varian"] == "jenis_sudut":
            assert set(pengecoh) | {soal.kunci} == {"lancip", "siku", "tumpul"}
        if p["varian"] == "banding":
            assert set(pengecoh) | {soal.kunci} == {"B", "C", "sama besar"}


def test_jawaban_tertulis_dibandingkan_dengan_kunci_tiap_jenis_kunci():
    angka = jenis.ukur_sudut_awal("baca_dari_nol", arah="kanan", sudut=70)
    assert diagnosis.setara("70", angka.kunci, soal=angka) and diagnosis.setara(" 70 ", angka.kunci, soal=angka)
    assert not diagnosis.setara("110", angka.kunci, soal=angka)
    kata = jenis.ukur_sudut_awal("jenis_sudut", arah="kanan", sudut=30)
    for ketikan in ("lancip", "Lancip", "  LANCIP. "):
        assert diagnosis.setara(ketikan, kata.kunci, soal=kata), ketikan
    assert not diagnosis.setara("tumpul", kata.kunci, soal=kata)
    huruf = jenis.ukur_sudut_awal("banding", arah="kanan", b=40, c=110)
    assert diagnosis.setara("C", huruf.kunci, soal=huruf) and diagnosis.setara(" c ", huruf.kunci, soal=huruf)
    assert not diagnosis.setara("B", huruf.kunci, soal=huruf)


# ── lembar cetak memakai bentuk TEKS yang bisa dijawab ───────────────────

def test_lembar_cetak_memakai_teks_lengkap_walau_flag_visual_menyala(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    lihat = set()
    for seed in range(150):
        lembar = generator.buat_lembar(seed, level="P5", topik=TOPIK)
        html = render.lembar_soal(list(lembar.soal), topik_paket=topics.ambil(TOPIK))
        assert "<svg" not in html
        for soal in lembar.soal:
            if soal.template_id != TID:
                continue
            lihat.add(soal.parameter["varian"])
            assert soal.penyajian is None
            assert solver_dari_teks(soal.teks) == soal.kunci
            assert soal.teks.split("\n")[0].split(" busur derajat")[0].split(". ")[0] in html
            assert "Perhatikan gambar busur" not in html
    assert lihat == set(VARIAN)


def test_lembar_p5_memuat_semua_jenis_tanpa_kembar():
    for seed in range(40):
        lembar = generator.buat_lembar(seed, level="P5", topik=TOPIK)
        # piktogram_lima_awal (jenis ke-24, 22 Nov 2026) menjadi jenis ke-4 di P5
        assert {s.template_id for s in lembar.soal} == {"bandingkan_ciri_bangun", "keliling_gabungan", TID,
                                                        "piktogram_lima_awal"}
        tanda = [s.tanda_tangan for s in lembar.soal]
        assert len(set(tanda)) == len(tanda), (seed, "soal kembar dalam lembar")


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("varian, isi", [
    ("tidak_ada", dict(arah="kanan", sudut=70)), (None, dict(arah="kanan", sudut=70)),
    (["baca_dari_nol"], dict(arah="kanan", sudut=70)),
    ("baca_dari_nol", dict(arah="kanan", sudut=90)), ("baca_dari_nol", dict(arah="kanan", sudut=5)),
    ("baca_dari_nol", dict(arah="kanan", sudut=0)), ("baca_dari_nol", dict(arah="kanan", sudut=175)),
    ("baca_dari_nol", dict(arah="kanan", sudut=180)), ("baca_dari_nol", dict(arah="kanan", sudut=72)),
    ("baca_dari_nol", dict(arah="kanan", sudut=True)), ("baca_dari_nol", dict(arah="kanan", sudut=70.0)),
    ("baca_dari_nol", dict(arah="kanan", sudut="70")), ("baca_dari_nol", dict(arah="kanan", sudut=None)),
    ("baca_dari_nol", dict(arah="atas", sudut=70)), ("baca_dari_nol", dict(arah=None, sudut=70)),
    ("baca_dari_nol", dict(arah=True, sudut=70)), ("baca_dari_nol", dict(sudut=70)),
    ("baca_dari_nol", dict(arah="kanan")), ("baca_dari_nol", dict(arah="kanan", sudut=70, a=10)),
    ("baca_geser", dict(a=30, b=30)), ("baca_geser", dict(a=0, b=30)), ("baca_geser", dict(a=30, b=180)),
    ("baca_geser", dict(a=35, b=110)), ("baca_geser", dict(a=30, b=True)), ("baca_geser", dict(a=30)),
    ("baca_geser", dict(a=30, b=110, arah="kanan")), ("baca_geser", dict(a="30", b=110)),
    ("jenis_sudut", dict(arah="kanan", sudut=5)), ("jenis_sudut", dict(arah="kanan", sudut=175)),
    ("jenis_sudut", dict(arah="kiri", sudut=92)), ("jenis_sudut", dict(arah="tengah", sudut=90)),
    ("jenis_sudut", dict(arah="kanan", sudut=90, b=10)),
    ("banding", dict(arah="kanan", b=40, c=40)), ("banding", dict(arah="kanan", b=45, c=100)),
    ("banding", dict(arah="kiri", b=40, c=180)), ("banding", dict(arah="atas", b=40, c=100)),
    ("banding", dict(arah="kanan", b=40)), ("banding", dict(arah="kanan", b=40, c=100, a=10)),
    ("banding", dict(b=40, c=100)), ("banding", dict(arah="kanan", b=True, c=100)),
    ("selisih_dua", dict(arah="kanan", b=70, c=70)), ("selisih_dua", dict(arah="kanan", b=0, c=70)),
    ("selisih_dua", dict(arah="kiri", b=75, c=70)), ("selisih_dua", dict(arah="kanan", b=70, c=None)),
])
def test_parameter_tidak_sah_ditolak(varian, isi):
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.ukur_sudut_awal(varian, **isi)


def test_contoh_sah_dari_tabel_penolakan_memang_diterima():
    assert _soal({"varian": "baca_dari_nol", "arah": "kiri", "sudut": 170}).kunci == "170"
    assert _soal({"varian": "baca_dari_nol", "arah": "kanan", "sudut": 10}).kunci == "10"
    assert _soal({"varian": "baca_geser", "a": 170, "b": 10}).kunci == "160"
    assert _soal({"varian": "jenis_sudut", "arah": "kanan", "sudut": 90}).kunci == "siku"
    assert _soal({"varian": "banding", "arah": "kanan", "b": 170, "c": 160}).kunci == "B"
    assert _soal({"varian": "selisih_dua", "arah": "kiri", "b": 10, "c": 170}).kunci == "160"


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_ukur_sudut_awal as jenis
hasil = []
for seed in range(200):
    p = jenis.parameter(random.Random(seed), "P5")
    s = jenis.ukur_sudut_awal(**p)
    hasil.append([p, s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                  [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    import templates
    jalur = [str(Path(jenis.__file__).resolve().parent),
             str(Path(templates.__file__).resolve().parent)]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE, json.dumps(jalur)],
                           env=env, capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c and len(a) == len(SEED)

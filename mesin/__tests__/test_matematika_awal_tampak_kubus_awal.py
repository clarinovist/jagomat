"""Matematika Awal, jenis tampak_kubus_awal (P6): domain, solver teks, malrule, PG, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (tanpa gambar), lihat
`tampak_solver_helpers`: tinggi tiap tumpukan dibaca lewat regex dan banyak kubus serta persegi tiap
tampak dihitung dengan rumus sendiri. Domain dicek oleh enumerator brute-force sendiri (seluruh tinggi
0..3 per alas, lalu disaring dengan syarat yang ditulis ulang di sini), dan SETIAP puncak tumpukan di
domain dibuktikan terlihat dari sudut pandang depan-kanan-atas lewat penelusuran sinar tiga dimensi
yang tidak memakai renderer. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru; yang dijaga:
bukan kunci, tidak kembar, selalu ada jalur K.
"""
from __future__ import annotations

from collections import Counter
import itertools
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

import pytest

import awal_tampak_kubus_awal as jenis
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
from tampak_solver_helpers import (TANYA_ATAS, TANYA_DEPAN, TANYA_KUBUS, TANYA_SAMPING,
                                   lajur_dari_teks, solver_dari_teks)
from templates import REGISTRI

TOPIK = "matematika-awal"
TID = "tampak_kubus_awal"
LEVEL = ("P6",)
VARIAN = ("banyak_kubus", "banyak_persegi_atas", "banyak_persegi_depan", "banyak_persegi_samping")
SEED = range(200)
AKAR_MESIN = Path(__file__).resolve().parents[1]
UKURAN_DOMAIN = {"banyak_kubus": 1242, "banyak_persegi_atas": 711, "banyak_persegi_depan": 722,
                 "banyak_persegi_samping": 722}
TOTAL_DOMAIN = 3397
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)
ALAS = ((2, 2), (2, 3), (3, 2), (3, 3))
TINGGI_NAMA = {"banyak_kubus": "kubus", "banyak_persegi_atas": "atas",
               "banyak_persegi_depan": "depan", "banyak_persegi_samping": "samping"}


def _soal(p: dict):
    return jenis.tampak_kubus_awal(**p)


def _domain() -> tuple:
    return jenis.domain_parameter("P6")


def _varian(*nama) -> list:
    return [p for p in _domain() if p["varian"] in nama]


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


def _p(varian, baris, kolom, tinggi) -> dict:
    return {"varian": varian, "baris": baris, "kolom": kolom, "tinggi": list(tinggi)}


# ── enumerator dan penghitung mandiri (brute force, tanpa kode jenis) ─────

def _lajur(baris, kolom, tinggi):
    return [tinggi[y * kolom:(y + 1) * kolom] for y in range(baris)]


def _hitungan(baris, kolom, tinggi) -> dict:
    lajur = _lajur(baris, kolom, tinggi)
    kolom_maks = [max(lajur[y][x] for y in range(baris)) for x in range(kolom)]
    baris_maks = [max(isi) for isi in lajur]
    return {"kubus": sum(tinggi), "atas": len([h for h in tinggi if h > 0]),
            "depan": sum(kolom_maks), "samping": sum(baris_maks)}


def _tangga(baris, kolom, tinggi) -> bool:
    """Tinggi tidak naik ke kanan dan tidak naik ke depan (baris belakang tidak lebih rendah)."""
    lajur = _lajur(baris, kolom, tinggi)
    for y in range(baris):
        for x in range(kolom):
            if x + 1 < kolom and lajur[y][x] < lajur[y][x + 1]:
                return False
            if y + 1 < baris and lajur[y][x] > lajur[y + 1][x]:
                return False
    return True


def _anggota_mandiri(varian: str) -> set:
    hasil = set()
    for baris, kolom in ALAS:
        for tinggi in itertools.product(range(4), repeat=baris * kolom):
            terisi = len([h for h in tinggi if h])
            if terisi < 3 or max(tinggi) < 2 or not _tangga(baris, kolom, tinggi):
                continue
            if terisi == baris * kolom and len(set(tinggi)) == 1:
                continue
            h = _hitungan(baris, kolom, tinggi)
            nama = TINGGI_NAMA[varian]
            if all(h[nama] != v for k, v in h.items() if k != nama):
                hasil.add((baris, kolom, tinggi))
    return hasil


def _kanon(p: dict) -> tuple:
    return (p["varian"], p["baris"], p["kolom"], tuple(p["tinggi"]))


def puncak_terlihat(baris, kolom, tinggi) -> bool:
    """Penelusuran sinar 3D: tiap puncak tumpukan terlihat dari depan-kanan-atas.

    Penonton berada ke arah (+kolom, -baris, +tinggi) dari susunan. Dari beberapa titik pada muka atas
    puncak tiap tumpukan, sinar menuju penonton (x + t, y - t, z + t) tidak boleh menembus kubus lain.
    """
    isi = {(x, y): tinggi[y * kolom + x] for y in range(baris) for x in range(kolom)}

    def ada_kubus(px, py, pz) -> bool:
        sel = (int(px // 1), int(py // 1))
        return sel in isi and 0 <= int(pz // 1) < isi[sel]

    for (x, y), h in isi.items():
        if not h:
            continue
        for gx, gy in ((0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)):
            for langkah in range(1, 61):
                t = langkah * 0.05
                if ada_kubus(x + gx + t, y + gy - t, h + t - 1e-9):
                    return False
    return True


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == jenis.tampak_kubus_awal.__name__
    assert jenis.LEVEL == LEVEL and jenis.VARIAN == VARIAN
    for level in ("P1", "P2", "P4", "P5", "", None):
        with pytest.raises(ValueError):
            jenis.domain_parameter(level)
        with pytest.raises(ValueError):
            jenis.parameter(random.Random(0), level)


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat():
    domain = _domain()
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN
    kanon = {_kanon(p) for p in domain}
    assert len(kanon) == len(domain) == TOTAL_DOMAIN
    assert len({_soal(p).tanda_tangan for p in domain}) == len(domain)


@pytest.mark.parametrize("varian", VARIAN)
def test_domain_sama_dengan_enumerator_brute_force_mandiri(varian):
    harapan = {(varian, b, k, t) for b, k, t in _anggota_mandiri(varian)}
    assert {_kanon(p) for p in _varian(varian)} == harapan
    assert len(harapan) == UKURAN_DOMAIN[varian]


def test_domain_dibangun_cepat_dan_urut_per_varian_lalu_alas_lalu_tinggi():
    awal = time.monotonic()
    domain = _domain()
    assert time.monotonic() - awal < 5
    urutan = [p["varian"] for p in domain]
    assert urutan == sorted(urutan, key=VARIAN.index), "domain harus urut menurut VARIAN"
    for varian in VARIAN:
        kunci = [(ALAS.index((p["baris"], p["kolom"])), tuple(p["tinggi"])) for p in _varian(varian)]
        assert kunci == sorted(kunci), "dalam satu varian: alas lalu tinggi urut leksikografis"


def test_domain_dict_dan_daftar_baru_setiap_panggilan_dan_sampler_murni():
    a = _domain()
    a[-1]["tinggi"][0] = 9
    a[-1]["varian"] = "rusak"
    b = _domain()
    assert b[-1]["varian"] == "banyak_persegi_samping" and b[-1]["tinggi"][0] != 9
    p = jenis.parameter(random.Random(0), "P6")
    q = jenis.parameter(random.Random(0), "P6")
    assert p == q and p is not q and p["tinggi"] is not q["tinggi"]
    p["tinggi"][0] = 9
    assert jenis.parameter(random.Random(0), "P6")["tinggi"][0] != 9


def test_domain_bentuk_parameter_dan_syarat_susunan():
    for p in _domain():
        assert set(p) == {"varian", "baris", "kolom", "tinggi"}
        assert (p["baris"], p["kolom"]) in ALAS
        tinggi = p["tinggi"]
        assert type(tinggi) is list and len(tinggi) == p["baris"] * p["kolom"]
        assert all(type(h) is int and 0 <= h <= 3 for h in tinggi)
        assert sum(1 for h in tinggi if h) >= 3 and max(tinggi) >= 2
        assert _tangga(p["baris"], p["kolom"], tuple(tinggi)), "tinggi naik ke kanan atau ke depan"
        seluruh_rata = all(h == tinggi[0] for h in tinggi) and tinggi[0] > 0
        assert not seluruh_rata, "seluruh petak terisi dengan tinggi yang sama"


def test_domain_nilai_yang_ditanya_berbeda_dari_tiga_nilai_lain():
    for p in _domain():
        h = _hitungan(p["baris"], p["kolom"], tuple(p["tinggi"]))
        nama = TINGGI_NAMA[p["varian"]]
        assert all(h[nama] != v for k, v in h.items() if k != nama), p
        assert 1 <= h[nama] <= 27


def test_domain_mencakup_keempat_alas_dan_semua_tinggi_nol_sampai_tiga():
    assert {(p["baris"], p["kolom"]) for p in _domain()} == set(ALAS)
    for varian in VARIAN:
        assert {(p["baris"], p["kolom"]) for p in _varian(varian)} == set(ALAS), varian
    assert {h for p in _domain() for h in p["tinggi"]} == {0, 1, 2, 3}
    kunci = {int(_soal(p).kunci) for p in _domain()}
    assert min(kunci) >= 2 and max(kunci) <= 27


def test_domain_memuat_kubus_tertutup_dan_depan_samping_berbeda():
    """Ada tumpukan tertinggi >= 2 di tiap susunan, jadi ada kubus yang tertutup; tampak tak simetris."""
    beda = 0
    for p in _varian("banyak_kubus"):
        h = _hitungan(p["baris"], p["kolom"], tuple(p["tinggi"]))
        assert h["kubus"] > h["atas"] and h["kubus"] > h["depan"] and h["kubus"] > h["samping"]
        beda += h["depan"] != h["samping"]
    assert beda > 0


def test_domain_alas_satu_baris_atau_kolom_tidak_masuk_dan_parameter_ditolak():
    for p in _domain():
        assert p["baris"] >= 2 and p["kolom"] >= 2
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.tampak_kubus_awal("banyak_kubus", baris=1, kolom=3, tinggi=[1, 2, 3])


def test_setiap_puncak_tumpukan_terlihat_dari_depan_kanan_atas_di_seluruh_domain():
    """Penelusuran sinar 3D mandiri: tak ada tumpukan yang hilang dari gambar (susunan unik diuji sekali)."""
    unik = {(p["baris"], p["kolom"], tuple(p["tinggi"])) for p in _domain()}
    assert 1000 < len(unik) < 1400
    for baris, kolom, tinggi in sorted(unik):
        assert puncak_terlihat(baris, kolom, tinggi), (baris, kolom, tinggi)


def test_penelusur_sinar_mengenali_tumpukan_yang_hilang_di_susunan_tanpa_syarat_tangga():
    """Contoh dari kajian: baris depan [1, 2], baris belakang [1, 0]; tumpukan belakang-kiri tertutup."""
    assert not puncak_terlihat(2, 2, (1, 2, 1, 0))
    assert puncak_terlihat(2, 2, (1, 0, 2, 1))
    assert not _tangga(2, 2, (1, 2, 1, 0))
    assert not any(tuple(p["tinggi"]) == (1, 2, 1, 0) for p in _domain())


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian_dan_alas():
    kanon = {_kanon(p) for p in _domain()}
    varian, alas = set(), set()
    for seed in range(600):
        p = jenis.parameter(random.Random(seed), "P6")
        assert _kanon(p) in kanon, (seed, p)
        varian.add(p["varian"])
        alas.add((p["baris"], p["kolom"]))
    assert varian == set(VARIAN) and alas == set(ALAS)


def test_sebaran_varian_pada_sampel_2000_hampir_seragam():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(2000):
        hitung[jenis.parameter(random.Random(seed), "P6")["varian"]] += 1
    assert all(440 <= n <= 560 for n in hitung.values()), hitung


# ── kunci lawan solver teks (seluruh domain) ─────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID


def test_kunci_berbentuk_bilangan_bulat_positif_sampai_27():
    for p in _domain():
        kunci = _soal(p).kunci
        assert re.fullmatch(r"[1-9]\d?", kunci) and 1 <= int(kunci) <= 27, (p, kunci)


def test_sampel_seed_kunci_sama_dengan_solver_teks():
    for seed in SEED:
        soal = _soal(jenis.parameter(random.Random(seed), "P6"))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_solver_tidak_meloloskan_teks_ambigu_atau_tidak_konsisten():
    pengantar = ("Kubus-kubus satuan disusun pada alas 2 baris dan 2 kolom. "
                 "Tinggi tumpukan dari kiri ke kanan, baris depan: 1, 0; baris belakang: 3, 2 "
                 "(0 artinya kosong). Tiap tumpukan berdiri di lantai.")
    assert solver_dari_teks(f"{pengantar}\n{TANYA_KUBUS}") == "6"
    for rusak in (
        pengantar.replace("2 baris", "3 baris"),  # banyak baris tidak cocok dengan isi
        pengantar.replace("baris belakang", "baris tengah"),
        pengantar.replace("baris depan: 1, 0", "baris depan: 1, 0, 1"),
        pengantar.replace("3, 2", "4, 2"),
        pengantar.replace(" Tiap tumpukan berdiri di lantai.", ""),
        pengantar + " Catatan.",
    ):
        with pytest.raises(AssertionError):
            solver_dari_teks(f"{rusak}\n{TANYA_KUBUS}")
    with pytest.raises(AssertionError):  # pertanyaan tak dikenal
        solver_dari_teks(f"{pengantar}\nBerapa kubusnya?")
    with pytest.raises(AssertionError):
        solver_dari_teks(f"{pengantar}\n{TANYA_KUBUS}\nTambahan.")


def test_teks_contoh_tangan_tiap_varian():
    f = jenis.tampak_kubus_awal
    pengantar_dua = ("Kubus-kubus satuan disusun pada alas 2 baris dan 3 kolom. Tinggi tumpukan dari kiri "
                     "ke kanan, baris depan: 1, 1, 0; baris belakang: 3, 2, 2 (0 artinya kosong). "
                     "Tiap tumpukan berdiri di lantai.")
    kubus = f("banyak_kubus", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
    assert kubus.teks == (f"{pengantar_dua}\nBerapa banyak kubus satuan seluruhnya, termasuk yang tertutup? "
                          "Tulis angkanya saja.")
    assert kubus.kunci == "9"
    atas = f("banyak_persegi_atas", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
    assert atas.teks.endswith("\nBerapa banyak persegi pada tampak atas (dilihat dari atas)? Tulis angkanya saja.")
    assert atas.kunci == "5"
    depan = f("banyak_persegi_depan", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
    assert depan.teks.endswith("\nBerapa banyak persegi pada tampak depan (dilihat dari depan)? Tulis angkanya saja.")
    assert depan.kunci == "7"
    samping = f("banyak_persegi_samping", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
    assert samping.teks.endswith(
        "\nBerapa banyak persegi pada tampak samping (dilihat dari sisi kanan)? Tulis angkanya saja.")
    assert samping.kunci == "4"
    tiga = f("banyak_kubus", baris=3, kolom=3, tinggi=[0, 0, 0, 1, 1, 0, 3, 2, 1])
    assert ("baris depan: 0, 0, 0; baris tengah: 1, 1, 0; baris belakang: 3, 2, 1 (0 artinya kosong)"
            in tiga.teks) and tiga.kunci == "8"


def test_pertanyaan_di_baris_terakhir_tanpa_digit_dan_pengantar_memuat_tinggi():
    for p in _domain()[::5]:
        soal = _soal(p)
        pengantar, tanya = soal.teks.split("\n")
        assert tanya in (TANYA_KUBUS, TANYA_ATAS, TANYA_DEPAN, TANYA_SAMPING)
        assert not re.search(r"\d", tanya), tanya
        assert "Perhatikan gambar" not in soal.teks and soal.teks.count("?") == 1
        assert lajur_dari_teks(pengantar) == [p["tinggi"][y * p["kolom"]:(y + 1) * p["kolom"]]
                                              for y in range(p["baris"])]


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


def test_malrule_jawaban_bilangan_bulat_positif_dan_jalur_k_hitungan_tampak_lain():
    for p in _domain():
        h = _hitungan(p["baris"], p["kolom"], tuple(p["tinggi"]))
        nama = TINGGI_NAMA[p["varian"]]
        lain = {str(v) for k, v in h.items() if k != nama}
        for m in _soal(p).malrule:
            assert re.fullmatch(r"[1-9]\d?", m.jawaban), (p, m.jawaban)
            if m.kode == "K":
                assert m.jawaban in lain, (p, m.id, m.jawaban)
            else:
                assert abs(int(m.jawaban) - h[nama]) == 1


def test_malrule_banyak_kubus_hanya_tampak_dan_meleset():
    m = _malrule(_p("banyak_kubus", 2, 3, [1, 1, 0, 3, 2, 2]))
    assert (m["hanya_tampak_atas"].jawaban, m["hanya_tampak_atas"].kode) == ("5", "K")
    assert (m["hanya_tampak_depan"].jawaban, m["hanya_tampak_depan"].kode) == ("7", "K")
    assert (m["hanya_tampak_samping"].jawaban, m["hanya_tampak_samping"].kode) == ("4", "K")
    assert (m["lebih_satu"].jawaban, m["lebih_satu"].kode) == ("10", "H")
    assert m["kurang_satu"].jawaban == "8"


def test_malrule_tampak_atas_depan_samping_semua_kubus_dan_tertukar():
    atas = _malrule(_p("banyak_persegi_atas", 2, 3, [1, 1, 0, 3, 2, 2]))
    assert (atas["hitung_semua_kubus"].jawaban, atas["hitung_semua_kubus"].kode) == ("9", "K")
    assert atas["tertukar_tampak_depan"].jawaban == "7" and atas["tertukar_tampak_samping"].jawaban == "4"
    assert atas["lebih_satu"].jawaban == "6" and atas["lebih_satu"].kode == "H"
    assert "kurang_satu" not in atas, "4 sudah dipakai jalur K tampak samping; saring_malrule membuang kembaran"
    depan = _malrule(_p("banyak_persegi_depan", 2, 3, [1, 1, 0, 3, 2, 2]))
    assert depan["hitung_semua_kubus"].jawaban == "9" and depan["tertukar_tampak_atas"].jawaban == "5"
    assert depan["tertukar_tampak_samping"].jawaban == "4"
    assert depan["lebih_satu"].jawaban == "8" and depan["kurang_satu"].jawaban == "6"
    samping = _malrule(_p("banyak_persegi_samping", 2, 3, [1, 1, 0, 3, 2, 2]))
    assert samping["hitung_semua_kubus"].jawaban == "9" and samping["tertukar_tampak_atas"].jawaban == "5"
    assert samping["tertukar_tampak_depan"].jawaban == "7"


def test_malrule_h_nol_tidak_pernah_jadi_jawaban():
    for p in _domain():
        assert all(int(m.jawaban) >= 1 for m in _soal(p).malrule)


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_langkah():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan, (p, soal.pembahasan)
        assert len(soal.pembahasan) > 60 and soal.pembahasan.strip() != soal.kunci
        assert " + " in soal.pembahasan and f"= {soal.kunci}" in soal.pembahasan


def test_pembahasan_contoh_per_varian():
    f = jenis.tampak_kubus_awal
    assert "1 + 1 + 3 + 2 + 2 = 9" in f("banyak_kubus", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2]).pembahasan
    assert "Kubus yang tertutup tetap dihitung" in f(
        "banyak_kubus", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2]).pembahasan
    atas = f("banyak_persegi_atas", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2]).pembahasan
    assert "baris depan 2, baris belakang 3" in atas and "2 + 3 = 5 persegi pada tampak atas" in atas
    depan = f("banyak_persegi_depan", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2]).pembahasan
    assert "Dari kiri ke kanan: 3, 2, 2" in depan and "3 + 2 + 2 = 7" in depan
    samping = f("banyak_persegi_samping", baris=3, kolom=3, tinggi=[0, 0, 0, 1, 1, 0, 3, 2, 1]).pembahasan
    assert "baris depan 0, baris tengah 1, baris belakang 3" in samping and "0 + 1 + 3 = 4" in samping


# ── kartu rumus, label, katalog, pancingan, sakelar ──────────────────────

def test_kartu_rumus_label_katalog_dan_cp_terdaftar():
    kartu = rumus.kartu_untuk(TID)
    assert kartu is not None and kartu.judul.startswith("Menghitung kubus satuan")
    for kata in ("tertutup", "tampak atas", "tampak depan", "tampak samping", "tertinggi", "sisi kanan"):
        assert kata in kartu.inti.lower()
    assert kartu.contoh.strip() and not TERLARANG.search(kartu.inti + kartu.contoh)
    assert TID in template_labels.NAMA_TIPE_SOAL
    grup = [g for entri in kurikulum_katalog.KATALOG if entri.topik_id == TOPIK for g in entri.grup]
    assert (TID, "Kubus satuan dan tampak depan, atas, samping", (TID,)) in [tuple(g) for g in grup]
    assert kurikulum_cp.CP_PER_GRUP[(TOPIK, TID)] == (("C.geometri.2", "sebagian"),)


def test_pancingan_dan_template_baru_terdaftar():
    berkas = AKAR_MESIN / "konten" / "pancingan" / "matematika-awal.json"
    isi = json.loads(berkas.read_text(encoding="utf-8"))["template"][TID]
    assert len(isi["pertanyaan"]) == 3 and isi["tindak_lanjut"].strip()
    assert TID in versi.TEMPLATE_BARU
    assert TID in topics.ambil(TOPIK).templates and TID in REGISTRI
    assert topics.pemilik_template(TID) == TOPIK


def test_komposisi_topik_memuat_jenis_di_p6_saja_dan_hanya_manual():
    paket = topics.ambil(TOPIK)
    assert TID in paket.komposisi["P6"]
    for level in ("P1", "P2", "P3", "P4", "P5"):
        assert TID not in paket.komposisi[level]
        with pytest.raises(ValueError, match="tidak tersedia untuk level"):
            generator.buat_soal(TID, 0, level, TOPIK)
    assert paket.hanya_manual is True


def test_jenis_ini_tidak_masuk_keluarga_geometri_ruang_dan_tidak_mengubahnya():
    assert TID not in topics.ambil("geometri-ruang").templates
    assert topics.pemilik_template(TID) == TOPIK
    assert set(topics.ambil("geometri-ruang").templates) >= {"jaring_jaring", "kubus_dicat", "volume_kubus_balok"}


# ── pilihan ganda ────────────────────────────────────────────────────────

def test_pilihan_ganda_seluruh_domain_tiga_opsi_pengecoh_cukup_dan_berbeda():
    hanya_dua = 0
    for p in _domain():
        soal = _soal(p)
        kebijakan, jenis_kunci, pengecoh = kandidat(soal)
        assert (kebijakan, jenis_kunci) == ("tiga-v1", "angka"), p
        assert len(pengecoh) == 2 and soal.kunci not in pengecoh, p
        semantik = {nilai_semantis(x, jenis_kunci) for x in pengecoh} | {nilai_semantis(soal.kunci, jenis_kunci)}
        assert len(semantik) == 3, p
        assert kebijakan_soal(soal) == (kebijakan, jenis_kunci)
        hanya_dua += len({m.jawaban for m in soal.malrule}) == 2
    assert hanya_dua > 0, "tiga-v1 dipakai karena ada susunan dengan tepat dua pengecoh berbeda"


def test_jawaban_tertulis_dibandingkan_dengan_kunci():
    soal = jenis.tampak_kubus_awal("banyak_kubus", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
    assert diagnosis.setara("9", soal.kunci, soal=soal) and diagnosis.setara(" 9 ", soal.kunci, soal=soal)
    assert not diagnosis.setara("7", soal.kunci, soal=soal)


# ── lembar cetak memakai bentuk TEKS yang bisa dijawab ───────────────────

def test_lembar_cetak_memakai_teks_lengkap_walau_flag_visual_menyala(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    lihat = set()
    for seed in range(60):
        lembar = generator.buat_lembar(seed, level="P6", topik=TOPIK)
        html = render.lembar_soal(list(lembar.soal), topik_paket=topics.ambil(TOPIK))
        assert "<svg" not in html
        for soal in lembar.soal:
            if soal.template_id != TID:
                continue
            lihat.add(soal.parameter["varian"])
            assert soal.penyajian is None
            assert solver_dari_teks(soal.teks) == soal.kunci
            pengantar = soal.teks.split("\n")[0]
            assert pengantar.split(". ")[0] in html and "baris depan:" in html
            assert "Perhatikan gambar kubus" not in html
    assert lihat == set(VARIAN)


def test_lembar_p6_memuat_empat_jenis_tanpa_kembar_dan_tampak_muncul_beberapa_kali():
    # P6 kini empat jenis (peluang, pecahan-desimal, pecahan campur, tampak kubus):
    # komposisi 3 + 3 + 2 + 2 (dikunci supaya perubahan komposisi tidak lolos diam-diam).
    for seed in range(40):
        lembar = generator.buat_lembar(seed, level="P6", topik=TOPIK)
        hitung = Counter(s.template_id for s in lembar.soal)
        assert hitung == {"peluang_dasar": 3, "pecahan_bilangan_asli_desimal": 3,
                          "pecahan_campur_awal": 2, TID: 2}, (seed, hitung)
        tanda = [s.tanda_tangan for s in lembar.soal]
        assert len(set(tanda)) == len(tanda), (seed, "soal kembar dalam lembar")


# ── penolakan parameter di luar domain ───────────────────────────────────

SAH = dict(baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])


@pytest.mark.parametrize("varian, isi", [
    ("tidak_ada", SAH), (None, SAH), (["banyak_kubus"], SAH), ("banyak_kubus ", SAH),
    ("banyak_kubus", {**SAH, "baris": 3}),  # banyak baris tidak cocok dengan daftar
    ("banyak_kubus", {**SAH, "baris": 2.0}), ("banyak_kubus", {**SAH, "baris": True}),
    ("banyak_kubus", {**SAH, "kolom": "3"}), ("banyak_kubus", {**SAH, "baris": None}),
    ("banyak_kubus", {**SAH, "tinggi": (1, 1, 0, 3, 2, 2)}),  # tuple bukan daftar
    ("banyak_kubus", {**SAH, "tinggi": "110322"}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2]}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2, 2, 0]}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2, 4]}),  # tinggi 4
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2, -1]}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2, 2.0]}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2, True]}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 1, 0, 3, 2, None]}),
    ("banyak_kubus", {**SAH, "tinggi": [1, 2, 0, 3, 2, 2]}),  # naik ke kanan (1 -> 2)
    ("banyak_kubus", {**SAH, "tinggi": [3, 2, 2, 1, 1, 0]}),  # turun ke belakang
    ("banyak_kubus", {**SAH, "tinggi": [0, 0, 0, 0, 3, 2]}),  # hanya dua petak terisi
    ("banyak_kubus", {**SAH, "tinggi": [0, 0, 0, 1, 1, 1]}),  # tanpa tumpukan setinggi 2
    ("banyak_kubus", dict(baris=2, kolom=2, tinggi=[2, 2, 2, 2])),  # seluruhnya rata
    ("banyak_kubus", {k: v for k, v in SAH.items() if k != "tinggi"}),
    ("banyak_kubus", {**SAH, "kunci": "9"}),
    ("banyak_kubus", {**SAH, "arah": "kanan"}),
    ("banyak_kubus", {}),
    ("banyak_kubus", dict(baris=1, kolom=3, tinggi=[3, 2, 1])),
    ("banyak_kubus", dict(baris=4, kolom=2, tinggi=[3, 2, 2, 1, 1, 1, 1, 0])),
])
def test_parameter_tidak_sah_ditolak(varian, isi):
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.tampak_kubus_awal(varian, **isi)


def test_varian_yang_nilainya_sama_dengan_nilai_lain_ditolak_untuk_varian_itu_saja():
    """Susunan 2x2 [1, 0 / 3, 2]: kubus 6, atas 3, depan 5, samping 4; semua berbeda, sah di keempat varian."""
    for varian in VARIAN:
        assert _soal(_p(varian, 2, 2, [1, 0, 3, 2])).kunci == {"banyak_kubus": "6", "banyak_persegi_atas": "3",
                                                              "banyak_persegi_depan": "5",
                                                              "banyak_persegi_samping": "4"}[varian]
    # [0,1,0 / 3,2,2 -> tidak tangga]; pakai susunan yang depan sama dengan samping untuk melihat penolakan
    tinggi = [1, 1, 0, 2, 2, 0]  # 2x3: depan 2+2+0 = 4, samping 1+2 = 3, atas 4, kubus 6
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.tampak_kubus_awal("banyak_persegi_atas", baris=2, kolom=3, tinggi=tinggi)  # atas 4 = depan 4
    assert _soal(_p("banyak_kubus", 2, 3, tinggi)).kunci == "6"


def test_contoh_sah_dari_tabel_penolakan_memang_diterima():
    assert _soal(_p("banyak_kubus", 2, 3, [1, 1, 0, 3, 2, 2])).kunci == "9"
    assert _soal(_p("banyak_persegi_depan", 3, 3, [1, 0, 0, 2, 2, 1, 3, 3, 2])).kunci == "8"
    assert _soal(_p("banyak_persegi_samping", 3, 2, [0, 0, 1, 0, 3, 2])).kunci == "4"


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_tampak_kubus_awal as jenis
hasil = []
for seed in range(200):
    p = jenis.parameter(random.Random(seed), "P6")
    s = jenis.tampak_kubus_awal(**p)
    hasil.append([p, s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                  [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
dom = jenis.domain_parameter("P6")
hasil.append([len(dom), dom[0], dom[-1], dom[len(dom) // 2]])
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
    assert a == b == c and len(a) == len(SEED) + 1

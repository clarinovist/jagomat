"""Matematika Awal, jenis piktogram_lima_awal (P5): domain, solver teks, malrule, PG, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal tanpa flag (titik hitam per baris), lihat
`piktogram_solver_helpers`. Domain dicek oleh enumerator mandiri yang menulis ulang aturannya dengan
`itertools.product` (bukan `permutations` seperti modul jenis), dan daftar tema ditulis ulang di sini
sebagai kunci APPEND-ONLY. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru; yang dijaga:
bukan kunci, tidak kembar, selalu ada jalur K, minimal dua jawaban berbeda.
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

import pytest

import awal_piktogram_lima_awal as jenis
import diagnosis
import generator
import kurikulum_cp
import kurikulum_katalog
import matematika_awal_versions as versi
import render
import rumus
import template_labels
import topics
from choice_generation import kandidat, kebijakan_soal
from multiple_choice import nilai_semantis
from piktogram_solver_helpers import SIMBOL, solver_dari_teks
from templates import REGISTRI

TOPIK = "matematika-awal"
TID = "piktogram_lima_awal"
LEVEL = ("P5",)
VARIAN = ("baca_nilai", "terbanyak_selisih", "total", "rata_rata", "berapa_ikon")
SKALA = (2, 5, 10, 20)
SEED = range(200)
AKAR_MESIN = Path(__file__).resolve().parents[1]
UKURAN_DOMAIN = {"baca_nilai": 2352, "terbanyak_selisih": 624, "total": 624, "rata_rata": 624,
                 "berapa_ikon": 1488}
TOTAL_DOMAIN = 5712
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)
# Tema ditulis ulang (append-only): nama -> (kata satuan, nama kategori urut).
TEMA_TES = {
    "mainan": ("mainan", ("Bola", "Mobil", "Boneka", "Balok", "Kelereng")),
    "jajanan": ("jajanan", ("Kue", "Roti", "Pizza", "Permen", "Pisang")),
    "barang": ("barang", ("Meja", "Lemari", "Karpet", "Sapu", "Payung")),
    "alat_tulis": ("perlengkapan", ("Buku", "Pensil", "Klip", "Stiker")),
    "hewan": ("ekor", ("Ayam", "Bebek", "Kelinci")),
    "buah": ("buah", ("Apel", "Jeruk", "Pisang")),
}
ANGGOTA_PER_KELOMPOK = 12


def _soal(p: dict):
    return jenis.piktogram_lima_awal(**p)


def _domain() -> tuple:
    return jenis.domain_parameter("P5")


def _varian(*nama) -> list:
    return [p for p in _domain() if p["varian"] in nama]


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


def _kanon(p: dict) -> tuple:
    return (p["varian"], p["tema"], p["skala"], tuple(p["jumlah"]), p.get("tanya"))


def _kunci_mandiri(varian, jumlah, skala, tanya) -> int:
    if varian == "baca_nilai":
        return jumlah[tanya] * skala
    if varian == "terbanyak_selisih":
        return (max(jumlah) - min(jumlah)) * skala
    if varian == "total":
        return sum(jumlah) * skala
    if varian == "rata_rata":
        return sum(jumlah) // len(jumlah) * skala
    return jumlah[tanya]


# ── enumerator mandiri (product + filter + selang tetap) ──────────────────

def _anggota_mandiri(varian: str) -> list:
    hasil, indeks = [], 0
    for tema, (_, nama) in TEMA_TES.items():
        for k in range(3, len(nama) + 1):
            if varian == "berapa_ikon" and k < 4:
                continue
            kolam = [t for t in itertools.product(range(1, 11), repeat=k) if len(set(t)) == k]
            if varian == "rata_rata":
                kolam = [t for t in kolam if sum(t) % k == 0]
            for skala in SKALA:
                langkah = max(1, len(kolam) // ANGGOTA_PER_KELOMPOK)
                for jumlah in kolam[indeks % langkah::langkah]:
                    tanya = range(k) if varian in ("baca_nilai", "berapa_ikon") else (None,)
                    hasil.extend((varian, tema, skala, jumlah, t) for t in tanya)
                indeks += 1
    return hasil


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == jenis.piktogram_lima_awal.__name__
    assert jenis.LEVEL == LEVEL and jenis.VARIAN == VARIAN and jenis.SKALA == SKALA
    for level in ("P1", "P2", "P3", "P4", "P6", "", None):
        with pytest.raises(ValueError):
            jenis.domain_parameter(level)
        with pytest.raises(ValueError):
            jenis.parameter(random.Random(0), level)


def test_tema_ditulis_ulang_sama_dengan_modul_append_only():
    assert tuple(jenis.TEMA) == tuple(TEMA_TES)
    for nama, (kata, kategori) in TEMA_TES.items():
        tema = jenis.TEMA[nama]
        assert tema.kata == kata and tuple(n for n, _ in tema.kategori) == kategori
        assert all(ikon == n.lower() for n, ikon in tema.kategori)


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat():
    domain = _domain()
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN
    assert len({_kanon(p) for p in domain}) == len(domain) == TOTAL_DOMAIN
    assert len({_soal(p).tanda_tangan for p in domain}) == len(domain)


@pytest.mark.parametrize("varian", VARIAN)
def test_domain_sama_dengan_enumerator_mandiri_termasuk_urutan(varian):
    harapan = _anggota_mandiri(varian)
    ada = [_kanon(p) for p in _varian(varian)]
    assert ada == harapan, "isi dan urutan enumerasi harus sama"
    assert len(harapan) == UKURAN_DOMAIN[varian]


def test_domain_urut_per_varian_dan_dibangun_cepat():
    import time
    jenis._domain_varian.cache_clear()
    jenis._kolam.cache_clear()
    awal = time.monotonic()
    domain = _domain()
    assert time.monotonic() - awal < 5
    urutan = [p["varian"] for p in domain]
    assert urutan == sorted(urutan, key=VARIAN.index), "domain harus urut menurut VARIAN"


def test_domain_dict_dan_daftar_baru_setiap_panggilan_dan_sampler_murni():
    a = _domain()
    a[-1]["jumlah"][0] = 99
    a[-1]["varian"] = "rusak"
    b = _domain()
    assert b[-1]["varian"] == "berapa_ikon" and b[-1]["jumlah"][0] != 99
    p = jenis.parameter(random.Random(0), "P5")
    q = jenis.parameter(random.Random(0), "P5")
    assert p == q and p is not q and p["jumlah"] is not q["jumlah"]
    p["jumlah"][0] = 99
    assert jenis.parameter(random.Random(0), "P5")["jumlah"][0] != 99


def test_domain_bentuk_parameter_dan_syarat_per_varian():
    for p in _domain():
        bertanya = p["varian"] in ("baca_nilai", "berapa_ikon")
        assert set(p) == {"varian", "tema", "skala", "jumlah"} | ({"tanya"} if bertanya else set())
        jumlah = p["jumlah"]
        nama = TEMA_TES[p["tema"]][1]
        assert type(jumlah) is list and 3 <= len(jumlah) <= len(nama)
        assert all(type(n) is int and 1 <= n <= 10 for n in jumlah)
        assert len(set(jumlah)) == len(jumlah), "jumlah gambar tiap kategori harus berbeda"
        assert type(p["skala"]) is int and p["skala"] in SKALA
        if bertanya:
            assert type(p["tanya"]) is int and 0 <= p["tanya"] < len(jumlah)
        if p["varian"] == "berapa_ikon":
            assert len(jumlah) >= 4, "tiga baris tertampil paling sedikit"
        if p["varian"] == "rata_rata":
            assert sum(jumlah) % len(jumlah) == 0


def test_domain_mencakup_semua_tema_skala_banyak_kategori_dan_jumlah_satu_sampai_sepuluh():
    domain = _domain()
    assert {p["tema"] for p in domain} == set(TEMA_TES)
    assert {p["skala"] for p in domain} == set(SKALA)
    assert {len(p["jumlah"]) for p in domain} == {3, 4, 5}
    assert {n for p in domain for n in p["jumlah"]} == set(range(1, 11))
    for varian in VARIAN:
        anggota = _varian(varian)
        assert {p["skala"] for p in anggota} == set(SKALA), varian
        assert {len(p["jumlah"]) for p in anggota} == ({4, 5} if varian == "berapa_ikon" else {3, 4, 5})
        assert any(10 in p["jumlah"] for p in anggota), varian
    assert {p["tema"] for p in _varian("berapa_ikon")} == {"mainan", "jajanan", "barang", "alat_tulis"}


def test_domain_memuat_baris_sepuluh_gambar_dan_lima_kategori_dengan_skala_besar():
    sepuluh = [p for p in _domain() if 10 in p["jumlah"] and len(p["jumlah"]) == 5]
    assert sepuluh
    assert {p["skala"] for p in sepuluh} == set(SKALA)


def test_domain_setiap_kategori_ditanya_dan_semua_indeks_dipakai():
    for varian in ("baca_nilai", "berapa_ikon"):
        per_banyak = {}
        for p in _varian(varian):
            per_banyak.setdefault(len(p["jumlah"]), set()).add(p["tanya"])
        assert {k: v for k, v in per_banyak.items()} == {k: set(range(k)) for k in per_banyak}


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian_skala_dan_tema():
    kanon = {_kanon(p) for p in _domain()}
    varian, skala, tema = set(), set(), set()
    for seed in range(800):
        p = jenis.parameter(random.Random(seed), "P5")
        assert _kanon(p) in kanon, (seed, p)
        varian.add(p["varian"])
        skala.add(p["skala"])
        tema.add(p["tema"])
    assert varian == set(VARIAN) and skala == set(SKALA) and tema == set(TEMA_TES)


def test_sebaran_varian_pada_sampel_2000_hampir_seragam():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(2000):
        hitung[jenis.parameter(random.Random(seed), "P5")["varian"]] += 1
    assert all(340 <= n <= 460 for n in hitung.values()), hitung


# ── kunci lawan solver teks (seluruh domain) ─────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID


def test_seluruh_domain_kunci_sama_dengan_rumus_mandiri_dan_bilangan_bulat_positif_sampai_999():
    for p in _domain():
        kunci = _soal(p).kunci
        assert kunci == str(_kunci_mandiri(p["varian"], p["jumlah"], p["skala"], p.get("tanya"))), p
        assert re.fullmatch(r"[1-9]\d{0,2}", kunci) and 1 <= int(kunci) <= 999, (p, kunci)


def test_sampel_seed_kunci_sama_dengan_solver_teks():
    for seed in SEED:
        soal = _soal(jenis.parameter(random.Random(seed), "P5"))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_solver_tidak_meloloskan_teks_ambigu_atau_tidak_konsisten():
    dasar = ("Piktogram mainan terjual di toko. Satu titik hitam mewakili 5 mainan.\n"
             "Bola: ●●●●\nMobil: ●●●●●●●\nBoneka: ●●\n")
    assert solver_dari_teks(dasar + "Berapa banyak mobil?") == "35"
    assert solver_dari_teks(dasar + "Berapa jumlah semua mainan?") == "65"
    for rusak in (
        dasar.replace("5 mainan", "3 mainan") + "Berapa banyak mobil?",  # skala di luar himpunan
        dasar.replace("Mobil: ●●●●●●●", "Mobil: ●●●●") + "Berapa banyak mobil?",  # jumlah kembar
        dasar.replace("Boneka: ●●\n", "") + "Berapa banyak mobil?",  # kurang dari tiga baris
        dasar.replace("●●●●●●●", "●●●●●●●●●●●") + "Berapa banyak mobil?",  # sebelas gambar
        dasar + "Berapa banyak truk?",  # kategori tidak ada
        dasar + "Berapa banyak mobil? ●",  # simbol di pertanyaan
        dasar + "Berapa rata-rata banyak mainan untuk tiap jenis?",  # 13 tidak habis dibagi 3
        dasar + "Berapa kali?",
        dasar.replace("Satu titik hitam", "Satu gambar") + "Berapa banyak mobil?",
    ):
        with pytest.raises(AssertionError):
            solver_dari_teks(rusak)


def test_teks_contoh_tangan_tiap_varian():
    def ambil(varian, tema, skala, banyak, **ciri):
        return next(p for p in _varian(varian) if p["tema"] == tema and p["skala"] == skala
                    and len(p["jumlah"]) == banyak and all(p.get(k) == v for k, v in ciri.items()))

    p = ambil("baca_nilai", "mainan", 5, 5, tanya=1)
    soal = _soal(p)
    baris = "\n".join(f"{nama}: {SIMBOL * n}" for (nama, _), n in zip(jenis.TEMA["mainan"].kategori, p["jumlah"]))
    assert soal.teks == ("Piktogram mainan terjual di toko. Satu titik hitam mewakili 5 mainan.\n"
                         f"{baris}\nBerapa banyak mobil?")
    assert soal.kunci == str(p["jumlah"][1] * 5)
    p = ambil("terbanyak_selisih", "jajanan", 10, 4)
    assert _soal(p).teks.endswith(
        "\nKategori yang paling banyak lebih banyak berapa jajanan daripada kategori yang paling sedikit?")
    p = ambil("total", "hewan", 20, 3)
    assert _soal(p).teks.split("\n")[0] == "Piktogram hewan di peternakan. Satu titik hitam mewakili 20 ekor."
    assert _soal(p).teks.endswith("\nBerapa jumlah semua ekor?")
    p = ambil("rata_rata", "barang", 2, 5)
    assert _soal(p).teks.endswith("\nBerapa rata-rata banyak barang untuk tiap jenis?")
    p = ambil("berapa_ikon", "alat_tulis", 20, 4, tanya=3)
    soal = _soal(p)
    assert soal.teks.endswith(f"\nStiker ada {p['jumlah'][3] * 20} perlengkapan, tetapi barisnya belum digambar. "
                              "Berapa titik hitam yang harus digambar pada baris stiker?")
    assert "Stiker:" not in soal.teks and soal.teks.count("\n") == 4


def test_pertanyaan_berapa_ikon_menyebut_nilai_tanpa_baris_yang_ditanya():
    for p in _varian("berapa_ikon")[::37]:
        soal = _soal(p)
        nama = TEMA_TES[p["tema"]][1][p["tanya"]]
        baris = soal.teks.split("\n")
        assert len(baris) == 1 + (len(p["jumlah"]) - 1) + 1
        assert not any(isi.startswith(nama + ":") for isi in baris[1:-1])
        assert baris[-1].startswith(f"{nama} ada {p['jumlah'][p['tanya']] * p['skala']} ")
        assert soal.teks.count(SIMBOL) == sum(p["jumlah"]) - p["jumlah"][p["tanya"]]
        assert soal.kunci == str(p["jumlah"][p["tanya"]])


def test_simbol_hanya_pada_baris_data_dan_pertanyaan_satu_baris_terakhir():
    for p in _domain()[::11]:
        baris = _soal(p).teks.split("\n")
        assert SIMBOL not in baris[0] and SIMBOL not in baris[-1]
        assert all(re.fullmatch(r"[A-Z][a-z]+: ●{1,10}", isi) for isi in baris[1:-1])
        assert baris[-1].count("?") == 1 and baris[0].count(".") >= 2


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
        assert len(soal.malrule) >= 2, p
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)
        assert not any(TERLARANG.search(m.alasan) for m in soal.malrule), p


def test_malrule_jawaban_bilangan_bulat_positif_paling_besar_999():
    for p in _domain():
        for m in _soal(p).malrule:
            assert re.fullmatch(r"[1-9]\d{0,2}", m.jawaban), (p, m.id, m.jawaban)


def test_malrule_baca_nilai_lupa_kali_baris_lain_dan_meleset_skala():
    p = next(p for p in _varian("baca_nilai") if p["skala"] == 10 and len(p["jumlah"]) == 4
             and len(_soal(p).malrule) == 5)  # tidak ada jawaban yang saling bertabrakan
    n, k = p["jumlah"], p["tanya"]
    m = _malrule(p)
    assert (m["lupa_kali_skala"].jawaban, m["lupa_kali_skala"].kode) == (str(n[k]), "K")
    assert m["baris_lain_1"].jawaban == str(n[(k + 1) % 4] * 10) and m["baris_lain_1"].kode == "K"
    assert m["baris_lain_2"].jawaban == str(n[(k + 2) % 4] * 10)
    assert (m["terhitung_dobel"].jawaban, m["terhitung_dobel"].kode) == (str(n[k] * 10 + 10), "H")
    assert m["terlewat"].jawaban == str(n[k] * 10 - 10)


def test_malrule_selisih_total_rata_dan_berapa_ikon_sesuai_hipotesis():
    p = next(p for p in _varian("terbanyak_selisih") if p["skala"] == 5 and len(p["jumlah"]) == 4)
    n = sorted(p["jumlah"])
    m = _malrule(p)
    assert m["lupa_kali_skala"].jawaban == str(n[-1] - n[0])
    assert m["jumlah_bukan_selisih"].jawaban == str((n[-1] + n[0]) * 5)
    assert m["hanya_terbanyak"].jawaban == str(n[-1] * 5)
    assert m["dua_terbanyak"].jawaban == str((n[-1] - n[-2]) * 5)
    p = next(p for p in _varian("total") if p["skala"] == 20 and len(p["jumlah"]) == 3)
    m = _malrule(p)
    assert m["lupa_kali_skala"].jawaban == str(sum(p["jumlah"]))
    assert m["lupa_baris_terakhir"].jawaban == str((sum(p["jumlah"]) - p["jumlah"][-1]) * 20)
    assert m["lupa_baris_pertama"].jawaban == str((sum(p["jumlah"]) - p["jumlah"][0]) * 20)
    p = next(p for p in _varian("rata_rata") if p["skala"] == 10 and len(p["jumlah"]) == 4)
    m = _malrule(p)
    rata = sum(p["jumlah"]) // 4
    assert m["lupa_kali_skala"].jawaban == str(rata) and m["tidak_dibagi"].jawaban == str(sum(p["jumlah"]) * 10)
    if "nilai_tengah" in m:  # saring_malrule membuang jawaban kembar dengan jalur sebelumnya
        assert m["nilai_tengah"].jawaban == str(sorted(p["jumlah"])[2] * 10) and m["nilai_tengah"].kode == "K"
    p = next(p for p in _varian("berapa_ikon") if p["skala"] == 5 and p["jumlah"][p["tanya"]] >= 3)
    m = _malrule(p)
    n, v = p["jumlah"][p["tanya"]], p["jumlah"][p["tanya"]] * 5
    assert m["tidak_dibagi"].jawaban == str(v) and m["dikurang_bukan_dibagi"].jawaban == str(v - 5)
    assert m["dikali_bukan_dibagi"].jawaban == str(v * 5) and m["lebih_satu"].jawaban == str(n + 1)


def test_malrule_jawaban_h_bergeser_satu_skala_atau_satu_gambar():
    for p in _domain()[::7]:
        soal = _soal(p)
        langkah = 1 if p["varian"] == "berapa_ikon" else p["skala"]
        for m in soal.malrule:
            if m.kode == "H":
                assert abs(int(m.jawaban) - int(soal.kunci)) == langkah, (p, m.id)


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_langkah():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan, (p, soal.pembahasan)
        assert len(soal.pembahasan) > 60 and soal.pembahasan.strip() != soal.kunci
        assert f"mewakili {p['skala']} " in soal.pembahasan
        assert (" × " in soal.pembahasan) or (" ÷ " in soal.pembahasan)


def test_pembahasan_contoh_per_varian():
    p = next(p for p in _varian("total") if p["skala"] == 20 and len(p["jumlah"]) == 3)
    soal = _soal(p)
    n = p["jumlah"]
    assert f"{n[0]} + {n[1]} + {n[2]} = {sum(n)} gambar" in soal.pembahasan
    assert f"{sum(n)} × 20 = {soal.kunci}" in soal.pembahasan
    p = next(p for p in _varian("rata_rata") if len(p["jumlah"]) == 3)
    soal = _soal(p)
    assert f"{sum(p['jumlah'])} ÷ 3 = {sum(p['jumlah']) // 3}" in soal.pembahasan
    p = next(p for p in _varian("berapa_ikon") if p["skala"] == 10)
    soal = _soal(p)
    nilai = int(soal.kunci) * 10
    assert f"{nilai} ÷ 10 = {soal.kunci}" in soal.pembahasan
    p = next(p for p in _varian("baca_nilai") if p["skala"] == 2)
    assert f"{p['jumlah'][p['tanya']]} × 2 = {_soal(p).kunci}" in _soal(p).pembahasan
    p = next(p for p in _varian("terbanyak_selisih") if p["skala"] == 5)
    assert "dicari dengan mengurangi" in _soal(p).pembahasan


# ── kartu rumus, label, katalog, pancingan, sakelar ──────────────────────

def test_kartu_rumus_label_katalog_dan_cp_terdaftar():
    kartu = rumus.kartu_untuk(TID)
    assert kartu is not None and kartu.judul.startswith("Membaca piktogram")
    for kata in ("satu gambar mewakili", "dikali n", "selisih", "jumlah semua", "rata-rata", "bagi nilai itu dengan n"):
        assert kata in kartu.inti.lower(), kata
    assert kartu.contoh.strip() and not TERLARANG.search(kartu.inti + kartu.contoh)
    assert TID in template_labels.NAMA_TIPE_SOAL
    grup = [g for entri in kurikulum_katalog.KATALOG if entri.topik_id == TOPIK for g in entri.grup]
    assert (TID, "Piktogram berskala besar", (TID,)) in [tuple(g) for g in grup]
    assert kurikulum_cp.CP_PER_GRUP[(TOPIK, TID)] == (("C.data.1", "sebagian"),)


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


def test_jenis_ini_tidak_mengubah_statistika_dan_tidak_masuk_keluarganya():
    assert TID not in topics.ambil("statistika").templates
    assert topics.pemilik_template(TID) == TOPIK
    assert {"piktogram", "diagram_batang_garis", "rata_rata", "median_modus"} <= set(
        topics.ambil("statistika").templates)


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
    assert hanya_dua > 0, "tiga-v1 dipakai karena ada soal dengan tepat dua pengecoh berbeda"


def test_jawaban_tertulis_dibandingkan_dengan_kunci():
    p = _varian("total")[0]
    soal = _soal(p)
    assert diagnosis.setara(soal.kunci, soal.kunci, soal=soal)
    assert diagnosis.setara(f" {soal.kunci} ", soal.kunci, soal=soal)
    assert not diagnosis.setara(str(int(soal.kunci) + int(p["skala"])), soal.kunci, soal=soal)


# ── lembar cetak memakai bentuk TEKS yang bisa dijawab ───────────────────

def test_lembar_cetak_memakai_teks_titik_hitam_walau_flag_visual_menyala(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    lihat = set()
    for seed in range(60):
        lembar = generator.buat_lembar(seed, level="P5", topik=TOPIK)
        html = render.lembar_soal(list(lembar.soal), topik_paket=topics.ambil(TOPIK))
        for soal in lembar.soal:
            if soal.template_id != TID:
                continue
            lihat.add(soal.parameter["varian"])
            assert soal.penyajian is None
            assert solver_dari_teks(soal.teks) == soal.kunci
            assert SIMBOL in soal.teks and "Satu titik hitam mewakili" in html
            assert "Perhatikan gambar. Satu gambar mewakili" not in html
    assert lihat == set(VARIAN)


def test_lembar_p5_memuat_empat_jenis_tanpa_kembar():
    for seed in range(40):
        lembar = generator.buat_lembar(seed, level="P5", topik=TOPIK)
        assert {s.template_id for s in lembar.soal} == {
            "bandingkan_ciri_bangun", "keliling_gabungan", "ukur_sudut_awal", TID}
        tanda = [s.tanda_tangan for s in lembar.soal]
        assert len(set(tanda)) == len(tanda), (seed, "soal kembar dalam lembar")
        assert Counter(s.template_id for s in lembar.soal)[TID] >= 2


# ── penolakan parameter di luar domain ───────────────────────────────────

def _sah() -> dict:
    return dict(next(p for p in _varian("baca_nilai")))


def _ubah(**kw) -> dict:
    isi = {k: v for k, v in _sah().items() if k != "varian"}
    isi.update(kw)
    return isi


def test_parameter_di_luar_domain_ditolak_dengan_pesan_jelas():
    sah = _sah()
    tanpa = {k: v for k, v in sah.items() if k != "varian"}
    assert _soal(sah).kunci
    kasus = [
        ("tidak_ada", tanpa), (None, tanpa), (["baca_nilai"], tanpa), ("baca_nilai ", tanpa),
        ("baca_nilai", _ubah(skala=3)), ("baca_nilai", _ubah(skala=True)), ("baca_nilai", _ubah(skala=5.0)),
        ("baca_nilai", _ubah(skala="5")), ("baca_nilai", _ubah(skala=None)), ("baca_nilai", _ubah(skala=40)),
        ("baca_nilai", _ubah(tema="tidak_ada")), ("baca_nilai", _ubah(tema=None)), ("baca_nilai", _ubah(tema=3)),
        ("baca_nilai", _ubah(jumlah=tuple(sah["jumlah"]))), ("baca_nilai", _ubah(jumlah="123")),
        ("baca_nilai", _ubah(jumlah=sah["jumlah"][:2])),  # dua kategori
        ("baca_nilai", _ubah(jumlah=[*sah["jumlah"], 4, 5, 6])),  # enam kategori
        ("baca_nilai", _ubah(jumlah=[1, 1, 2])),  # kembar
        ("baca_nilai", _ubah(jumlah=[0, 2, 3])), ("baca_nilai", _ubah(jumlah=[1, 2, 11])),
        ("baca_nilai", _ubah(jumlah=[1, 2, 3.0])), ("baca_nilai", _ubah(jumlah=[1, 2, True])),
        ("baca_nilai", _ubah(jumlah=[1, 2, None])), ("baca_nilai", _ubah(jumlah=[1, 2, "3"])),
        ("baca_nilai", _ubah(tanya=9)), ("baca_nilai", _ubah(tanya=True)), ("baca_nilai", _ubah(tanya=-1)),
        ("baca_nilai", _ubah(tanya="0")), ("baca_nilai", {k: v for k, v in tanpa.items() if k != "tanya"}),
        ("baca_nilai", {**tanpa, "kunci": "20"}), ("baca_nilai", {**tanpa, "tinggi": 1}),
        ("total", {**tanpa, "tanya": 0}),  # total tidak punya `tanya`
        ("baca_nilai", {}),
    ]
    for varian, isi in kasus:
        with pytest.raises(ValueError, match="di luar domain"):
            jenis.piktogram_lima_awal(varian, **isi)


def test_anggota_yang_sah_secara_umum_tetapi_di_luar_selang_domain_ditolak():
    """Tuple sah menurut aturan umum (berbeda, 1..10) tetapi tidak dipilih selang kelompok ditolak."""
    ada = {_kanon(p) for p in _varian("baca_nilai")}
    tema, skala = "mainan", 5
    ditolak = 0
    for jumlah in ((1, 2, 3), (10, 9, 8), (2, 3, 4), (3, 1, 2), (5, 6, 7)):
        for tanya in range(3):
            kunci = ("baca_nilai", tema, skala, jumlah, tanya)
            if kunci in ada:
                continue
            ditolak += 1
            with pytest.raises(ValueError, match="di luar domain"):
                jenis.piktogram_lima_awal("baca_nilai", tema=tema, skala=skala, jumlah=list(jumlah), tanya=tanya)
    assert ditolak > 0


def test_float_dan_bool_yang_nilainya_sama_dengan_anggota_domain_ditolak():
    """(1.0, 2.0, 3.0) == (1, 2, 3) dan True == 1: validator wajib memeriksa tipe sebelum keanggotaan."""
    ada = 0
    for p in _domain()[::5]:
        isi = {k: v for k, v in p.items() if k != "varian"}
        rusak = [{**isi, "jumlah": [float(n) for n in p["jumlah"]]}, {**isi, "skala": float(p["skala"])}]
        if 1 in p["jumlah"]:
            rusak.append({**isi, "jumlah": [True if n == 1 else n for n in p["jumlah"]]})
        if "tanya" in isi:
            rusak.append({**isi, "tanya": float(p["tanya"])})
            if p["tanya"] in (0, 1):
                rusak.append({**isi, "tanya": bool(p["tanya"])})
        for kasus in rusak:
            ada += 1
            with pytest.raises(ValueError, match="di luar domain"):
                jenis.piktogram_lima_awal(p["varian"], **kasus)
    assert ada > 2000


def test_rata_rata_tidak_habis_dibagi_dan_berapa_ikon_tiga_kategori_ditolak():
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.piktogram_lima_awal("rata_rata", tema="mainan", skala=5, jumlah=[1, 2, 4])
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.piktogram_lima_awal("berapa_ikon", tema="hewan", skala=5, jumlah=[1, 2, 4], tanya=0)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_piktogram_lima_awal as jenis
hasil = []
for seed in range(200):
    p = jenis.parameter(random.Random(seed), "P5")
    s = jenis.piktogram_lima_awal(**p)
    hasil.append([p, s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                  [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
dom = jenis.domain_parameter("P5")
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

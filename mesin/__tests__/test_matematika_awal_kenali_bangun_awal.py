"""Matematika Awal, jenis kenali_bangun_awal (P1/P2): domain, solver teks, malrule, PG, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (tanpa gambar): fakta bangun
dan benda ditulis ulang di tes ini (bukan diimpor dari modul jenis), kalimat ciri dibaca lewat
predikat regex dan harus cocok dengan TEPAT SATU bangun pada himpunan level; daftar bangun
`hitung_bentuk` dihitung ulang. Domain jenis lama `kenali_bentuk` dikunci byte-identik lewat
sidik jari yang dihitung SEBELUM jenis baru ditulis. Malrule hanya HIPOTESIS kesalahan umum
untuk ditinjau guru; yang dijaga: bukan kunci, tidak kembar, selalu ada jalur K.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

import pytest

import awal_kenali_bangun_awal as jenis
import awal_kenali_bentuk as jenis_lama
import bentuk_katalog as katalog
import diagnosis
import generator
import matematika_awal_versions as versi
import render
import rumus
import template_labels
import topics
from choice_generation import kandidat, kebijakan_soal
from bentuk_solver_helpers import BENDA_TES, DATAR_TES, RUANG_TES, _cocok_datar, _cocok_ruang, _tunggal, solver_dari_teks
from templates import REGISTRI

TOPIK = "matematika-awal"
TID = "kenali_bangun_awal"
LEVEL = ("P1", "P2")
VARIAN = ("datar_gambar", "ruang_gambar", "benda_ruang", "hitung_bentuk")
SEED = range(200)
AKAR_MESIN = Path(__file__).resolve().parents[1]
UKURAN_DOMAIN = {
    "P1": {"datar_gambar": 84, "ruang_gambar": 30, "benda_ruang": 12, "hitung_bentuk": 1143},
    "P2": {"datar_gambar": 96, "ruang_gambar": 36, "benda_ruang": 15, "hitung_bentuk": 2424},
}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)
# Dugaan tertukar yang harus ada (kunci, jawaban keliru) pada himpunan level.
PASANGAN_RAWAN = (("persegi", "persegi panjang"), ("kubus", "balok"), ("tabung", "kerucut"))
# Sidik jari domain, 200 undian seed tetap, dan isi soal `kenali_bentuk` (dihitung sebelum perubahan).
SIDIK_KENALI_BENTUK = "4626461dc9a9624ce618eaf0a3105ed8975dad2434378874c261d6c6842d6b2a"


def _soal(p: dict):
    return getattr(jenis, "kenali_bangun_awal")(**p)


def _domain(level: str) -> tuple:
    return jenis.domain_parameter(level)


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == jenis.kenali_bangun_awal.__name__
    assert jenis.LEVEL == LEVEL and jenis.VARIAN == VARIAN
    with pytest.raises(ValueError):
        jenis.domain_parameter("P3")
    with pytest.raises(ValueError):
        jenis.parameter(random.Random(0), "P6")


def test_jenis_lama_kenali_bentuk_byte_identik():
    """Domain P1 (19) dan P2 (26), 200 undian seed tetap, dan isi soal tidak berubah."""
    def ringkas(s):
        return [s.template_id, s.parameter, s.teks, s.kunci, s.pembahasan, s.bagian,
                [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]]
    h = hashlib.sha256()
    for lv in LEVEL:
        for p in jenis_lama.domain_parameter(lv):
            h.update(json.dumps([lv, p, ringkas(jenis_lama.kenali_bentuk(**p))],
                                sort_keys=True, ensure_ascii=False).encode())
    for lv in LEVEL:
        for seed in SEED:
            p = jenis_lama.parameter(random.Random(seed), lv)
            h.update(json.dumps([lv, seed, p, ringkas(jenis_lama.kenali_bentuk(**p))],
                                sort_keys=True, ensure_ascii=False).encode())
    assert len(jenis_lama.domain_parameter("P1")) == 19 and len(jenis_lama.domain_parameter("P2")) == 26
    assert h.hexdigest() == SIDIK_KENALI_BENTUK


# ── domain dan sampler ───────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat(level):
    domain = _domain(level)
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN[level]
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain) <= 6000, "domain berisi duplikat atau terlalu besar"
    assert len({_soal(p).tanda_tangan for p in domain[::7]}) == len(domain[::7])


@pytest.mark.parametrize("level", LEVEL)
def test_domain_dibangun_cepat_dan_urut_per_varian(level):
    awal = time.monotonic()
    domain = _domain(level)
    assert time.monotonic() - awal < 5
    urutan = [p["varian"] for p in domain]
    assert urutan == sorted(urutan, key=VARIAN.index), "domain harus urut menurut VARIAN"


def test_domain_dict_dan_list_baru_setiap_panggilan():
    a = _domain("P1")
    a[-1]["banyak"][0] = 99
    a[-1]["varian"] = "rusak"
    b = _domain("P1")
    assert b[-1]["varian"] == "hitung_bentuk" and b[-1]["banyak"][0] != 99
    assert isinstance(b[-1]["banyak"], list)
    p = jenis.parameter(random.Random(0), "P1")
    q = jenis.parameter(random.Random(0), "P1")
    assert p == q and p is not q


def test_domain_himpunan_level_dan_bangun_lengkap():
    for level, himpunan in (("P1", "dasar"), ("P2", "lengkap")):
        domain = _domain(level)
        assert {p["himpunan"] for p in domain} == {himpunan}
        datar = {p["bangun"] for p in domain if p["varian"] == "datar_gambar"}
        ruang = {p["bangun"] for p in domain if p["varian"] == "ruang_gambar"}
        benda = {p["bangun"] for p in domain if p["varian"] == "benda_ruang"}
        assert datar == set(DATAR_TES[level]) and ruang == benda == set(RUANG_TES[level])
    assert {"persegi panjang", "kerucut"}.isdisjoint(
        {p.get("bangun") for p in _domain("P1")})


@pytest.mark.parametrize("level", LEVEL)
def test_domain_ragam_orientasi_ukuran_dan_warna_tercakup(level):
    domain = [p for p in _domain(level) if p["varian"] in ("datar_gambar", "ruang_gambar")]
    assert {p["ukuran"] for p in domain} == {"kecil", "besar"}
    assert {p["warna"] for p in domain} == {"biru", "kuning", "hijau"}
    segitiga = [p for p in domain if p["bangun"] == "segitiga"]
    assert {(p["ragam"], p["putar"]) for p in segitiga} == {
        (r, v) for r in ("samasisi", "siku", "sembarang") for v in (0, 90, 180, 270)}
    assert {p["putar"] for p in domain if p["bangun"] != "segitiga"} == {0}, "persegi miring dilarang"
    assert {p["ragam"] for p in domain if p["bangun"] == "balok"} == {"mendatar", "tegak"}


@pytest.mark.parametrize("level", LEVEL)
def test_domain_hitung_aturan_jumlah_jenis_dan_ditanya_unik(level):
    himpunan = DATAR_TES[level]
    for p in (q for q in _domain(level) if q["varian"] == "hitung_bentuk"):
        banyak, tanya = p["banyak"], p["tanya"]
        assert len(banyak) == len(himpunan) and 4 <= sum(banyak) <= 10
        assert sum(1 for n in banyak if n) >= 2 and banyak[tanya] >= 1
        assert [n for i, n in enumerate(banyak) if i != tanya].count(banyak[tanya]) == 0
        assert p["tata"] in (0, 1, 2)


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian():
    for level in LEVEL:
        kanon = {json.dumps(p, sort_keys=True) for p in _domain(level)}
        varian = set()
        for seed in SEED:
            p = jenis.parameter(random.Random(seed), level)
            assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
            varian.add(p["varian"])
        assert varian == set(VARIAN)


def test_sebaran_varian_pada_sampel_2000_hampir_seragam():
    for level in LEVEL:
        hitung = {v: 0 for v in VARIAN}
        for seed in range(2000):
            hitung[jenis.parameter(random.Random(seed), level)["varian"]] += 1
        assert all(400 <= n <= 600 for n in hitung.values()), (level, hitung)


def test_sampler_murni_dari_rng_seed_sama_hasil_sama():
    for level in LEVEL:
        for seed in SEED:
            assert (jenis.parameter(random.Random(seed), level)
                    == jenis.parameter(random.Random(seed), level))


# ── kunci lawan solver teks (seluruh domain) ─────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_seluruh_domain_kunci_sama_dengan_solver_teks(level):
    for p in _domain(level):
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks, level), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID
        assert soal.kunci == soal.kunci.strip().lower()


def test_sampel_seed_kunci_sama_dengan_solver_teks():
    for level in LEVEL:
        for seed in SEED:
            soal = _soal(jenis.parameter(random.Random(seed), level))
            assert soal.kunci == solver_dari_teks(soal.teks, level), (seed, soal.teks)


def test_solver_tidak_meloloskan_ciri_yang_ambigu():
    """Mutasi ciri: persegi tanpa 'sama panjang' atau segitiga tanpa angka harus gagal diselesaikan."""
    with pytest.raises(AssertionError):
        solver_dari_teks("Bangun ini punya 4 sisi lurus.\nBangun datar apa ini?", "P2")
    with pytest.raises(AssertionError):
        solver_dari_teks("Bangun ruang ini punya 6 sisi.\nBangun ruang apa ini?", "P2")
    with pytest.raises(AssertionError):
        solver_dari_teks("Bu Rina menggambar: segitiga, segitiga, persegi, persegi.\n"
                         "Berapa banyak segitiga?", "P1")


def test_ciri_unik_pada_himpunan_dasar_dan_lengkap_untuk_semua_tiga_kalimat():
    for himpunan_datar, himpunan_ruang in ((DATAR_TES["P1"], RUANG_TES["P1"]),
                                           (DATAR_TES["P2"], RUANG_TES["P2"])):
        for bangun in himpunan_datar:
            for ciri in katalog.CIRI[bangun]:
                assert _tunggal(himpunan_datar, _cocok_datar, ciri) == bangun
        for bangun in himpunan_ruang:
            for ciri in katalog.CIRI[bangun]:
                assert _tunggal(himpunan_ruang, _cocok_ruang, ciri) == bangun


def test_benda_menunjuk_tepat_satu_bangun_dan_tabel_cocok_fakta_tes():
    semua = {b: n for n, daftar in katalog.BENDA.items() for b in daftar}
    assert semua == BENDA_TES
    assert len(semua) == sum(len(v) for v in katalog.BENDA.values()), "benda ganda di dua bangun"
    assert not any(re.search(r"\bkotak\b$", b) or b == "kotak" for b in semua), "benda ambigu dilarang"


def test_teks_contoh_tangan():
    f = jenis.kenali_bangun_awal
    datar = f("datar_gambar", "dasar", bangun="segitiga", ragam="siku", putar=90,
              ukuran="besar", warna="biru")
    assert datar.teks == "Bangun ini punya 3 sisi lurus dan 3 sudut.\nBangun datar apa ini?"
    assert datar.kunci == "segitiga"
    assert f("ruang_gambar", "lengkap", bangun="kerucut", ragam="tegak", putar=0,
             ukuran="kecil", warna="hijau").teks == (
        "Bangun ruang ini punya 1 sisi datar yang bulat dan 1 sisi lengkung yang meruncing ke atas."
        "\nBangun ruang apa ini?")
    assert f("benda_ruang", "dasar", bangun="bola", benda=0).teks == (
        "Bola sepak berbentuk seperti bangun ruang apa?")
    hitung = f("hitung_bentuk", "dasar", banyak=[2, 1, 1], tanya=0, tata=0)
    assert hitung.teks == ("Bu Rina menggambar: segitiga, segitiga, persegi, lingkaran.\n"
                           "Berapa banyak segitiga?")
    assert hitung.kunci == "2"
    campur = f("hitung_bentuk", "dasar", banyak=[3, 1, 2], tanya=0, tata=1)
    assert campur.teks.startswith("Pak Dedi menggambar: segitiga, persegi, lingkaran, segitiga, lingkaran, segitiga.")


def test_urutan_bangun_tiga_tata():
    f = jenis.urutan_bangun
    assert f([3, 1, 2], 0) == (0, 0, 0, 1, 2, 2)
    assert f([3, 1, 2], 1) == (0, 1, 2, 0, 2, 0)
    assert f([3, 1, 2], 2) == (2, 1, 0, 2, 0, 0)
    for banyak in ([1, 2, 3], [4, 0, 2], [2, 3, 5]):
        for tata in (0, 1, 2):
            urutan = f(banyak, tata)
            assert sorted(urutan) == sorted(i for i, n in enumerate(banyak) for _ in range(n))


def test_teks_tanpa_gambar_pertanyaan_di_baris_terakhir_dan_satu_kunci():
    for level in LEVEL:
        for p in _domain(level)[::29]:
            soal = _soal(p)
            assert soal.teks.split("\n")[-1].endswith("?")
            assert soal.teks.count("?") == 1
            assert not re.search(r"Perhatikan gambar", soal.teks)


# ── malrule ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k(level):
    for p in _domain(level):
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
        assert len(soal.malrule) >= 2, p


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


@pytest.mark.parametrize("level", LEVEL)
def test_nama_bangun_pengecoh_ada_di_himpunan_level_atau_bangun_datar_keliru(level):
    for p in _domain(level):
        if p["varian"] == "hitung_bentuk":
            continue
        himpunan = RUANG_TES[level] if p["varian"] != "datar_gambar" else DATAR_TES[level]
        jawaban = {m.jawaban for m in _soal(p).malrule}
        luar = jawaban - set(himpunan) - set(DATAR_TES[level])
        assert not luar, (p, luar)
        if p["varian"] == "datar_gambar":
            assert jawaban == set(himpunan) - {p["bangun"]}, p
        else:
            assert set(himpunan) - {p["bangun"]} <= jawaban, p
            assert len(jawaban & set(DATAR_TES[level])) == 1, "tepat satu bangun datar keliru"


def test_pasangan_rawan_tertukar_ada_di_malrule_semua_varian_nama():
    for level in LEVEL:
        himpunan = set(DATAR_TES[level]) | set(RUANG_TES[level])
        for p in _domain(level):
            if p["varian"] == "hitung_bentuk":
                continue
            jawaban = {m.jawaban for m in _soal(p).malrule}
            for kunci, lain in PASANGAN_RAWAN:
                if p["bangun"] == kunci and lain in himpunan:
                    assert lain in jawaban, (p, lain)


def test_bangun_datar_untuk_ruang_adalah_hipotesis_k_per_himpunan():
    f = jenis.kenali_bangun_awal
    p1 = {m.id.split(".", 1)[1]: m for m in f("benda_ruang", "dasar", bangun="balok", benda=1).malrule}
    p2 = {m.id.split(".", 1)[1]: m for m in f("benda_ruang", "lengkap", bangun="balok", benda=1).malrule}
    assert p1["datar_untuk_ruang"].jawaban == "persegi" and p1["datar_untuk_ruang"].kode == "K"
    assert p2["datar_untuk_ruang"].jawaban == "persegi panjang"
    for himpunan, bangun, datar in (("dasar", "kubus", "persegi"), ("lengkap", "kubus", "persegi"),
                                    ("dasar", "tabung", "lingkaran"), ("lengkap", "tabung", "lingkaran"),
                                    ("dasar", "bola", "lingkaran")):
        m = {x.id.split(".", 1)[1]: x for x in f("benda_ruang", himpunan, bangun=bangun, benda=0).malrule}
        assert m["datar_untuk_ruang"].jawaban == datar and m["datar_untuk_ruang"].kode == "K"
    kerucut = {m.id.split(".", 1)[1]: m for m in f("benda_ruang", "lengkap", bangun="kerucut", benda=0).malrule}
    assert kerucut["datar_untuk_ruang"].jawaban == "segitiga"
    bola = f("ruang_gambar", "dasar", bangun="bola", ragam="biasa", putar=0, ukuran="besar", warna="biru")
    assert "lingkaran" in {m.jawaban for m in bola.malrule}


def test_alasan_tertukar_khusus_menyebut_ciri_pembeda():
    f = jenis.kenali_bangun_awal
    kubus = _malrule(dict(varian="ruang_gambar", himpunan="dasar", bangun="kubus", ragam="biasa",
                          putar=0, ukuran="besar", warna="biru"))
    assert "balok" == kubus["ruang_tertukar_balok"].jawaban
    assert "persegi yang sama besar" in kubus["ruang_tertukar_balok"].alasan
    tabung = _malrule(dict(varian="benda_ruang", himpunan="lengkap", bangun="tabung", benda=0))
    assert "2 sisi datar" in tabung["ruang_tertukar_kerucut"].alasan
    persegi = _malrule(dict(varian="datar_gambar", himpunan="lengkap", bangun="persegi", ragam="biasa",
                            putar=0, ukuran="besar", warna="biru"))
    assert "semua sisinya sama panjang" in persegi["bangun_tertukar_persegi_panjang"].alasan
    assert f is jenis.kenali_bangun_awal


def test_hitung_malrule_jenis_lain_semua_dan_lebih_kurang_satu():
    m = _malrule(dict(varian="hitung_bentuk", himpunan="dasar", banyak=[3, 1, 4], tanya=0, tata=0))
    assert m["hitung_persegi"].jawaban == "1" and m["hitung_persegi"].kode == "K"
    assert m["hitung_lingkaran"].jawaban == "4" and m["hitung_lingkaran"].kode == "K"
    assert m["hitung_semua"].jawaban == "8" and m["hitung_semua"].kode == "K"
    assert "hitung_dobel" not in m, "lebih satu (4) kembar jawaban jenis lain, dibuang saringan"
    assert m["hitung_terlewat"].jawaban == "2" and m["hitung_terlewat"].kode == "H"
    satu = _malrule(dict(varian="hitung_bentuk", himpunan="dasar", banyak=[1, 2, 3], tanya=0, tata=1))
    assert "hitung_terlewat" not in satu, "kurang satu tidak boleh menjadi pengecoh 0"
    assert "hitung_dobel" not in satu and {x.jawaban for x in satu.values()} == {"2", "3", "6"}
    dobel = _malrule(dict(varian="hitung_bentuk", himpunan="dasar", banyak=[2, 1, 5], tanya=0, tata=0))
    assert dobel["hitung_dobel"].jawaban == "3" and dobel["hitung_dobel"].kode == "H"


def test_hitung_malrule_jenis_yang_tak_ada_tidak_jadi_pengecoh():
    m = _malrule(dict(varian="hitung_bentuk", himpunan="dasar", banyak=[3, 0, 2], tanya=0, tata=0))
    assert "hitung_persegi" not in m and m["hitung_lingkaran"].jawaban == "2"


# ── pembahasan ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_bahasa_anak_memuat_kunci_dan_fakta(level):
    for p in _domain(level):
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40 and soal.pembahasan.strip() != soal.kunci
        if p["varian"] != "hitung_bentuk":
            assert katalog.FAKTA[p["bangun"]] in soal.pembahasan


def test_fakta_bangun_benar_dan_lengkap_untuk_ulasan():
    fakta = katalog.FAKTA
    assert "3 sisi lurus dan 3 sudut" in fakta["segitiga"]
    assert "semuanya sama panjang" in fakta["persegi"]
    assert "sisi yang berhadapan sama panjang" in fakta["persegi panjang"]
    assert "tidak punya sisi lurus dan tidak punya sudut" in fakta["lingkaran"]
    assert "6 sisi" in fakta["kubus"] and "persegi" in fakta["kubus"]
    assert "6 sisi" in fakta["balok"] and "persegi panjang" in fakta["balok"]
    assert "tidak punya sisi datar" in fakta["bola"]
    assert "2 sisi datar" in fakta["tabung"] and "1 sisi lengkung" in fakta["tabung"]
    assert "1 sisi datar" in fakta["kerucut"] and "titik puncak" in fakta["kerucut"]


# ── kartu rumus, label, katalog, pancingan, sakelar ──────────────────────

def test_kartu_rumus_label_dan_pemetaan_terdaftar():
    kartu = rumus.kartu_untuk(TID)
    assert kartu is not None and kartu.judul == "Mengenal bangun datar dan bangun ruang"
    for kata in ("segitiga", "persegi panjang", "lingkaran", "kubus", "balok", "bola", "tabung", "kerucut"):
        assert kata in kartu.inti
    assert kartu.contoh.strip() and not TERLARANG.search(kartu.inti + kartu.contoh)
    assert template_labels.LABEL[TID] if hasattr(template_labels, "LABEL") else True


def test_pancingan_dan_template_baru_terdaftar():
    berkas = AKAR_MESIN / "konten" / "pancingan" / "matematika-awal.json"
    isi = json.loads(berkas.read_text(encoding="utf-8"))["template"][TID]
    assert len(isi["pertanyaan"]) == 3 and isi["tindak_lanjut"].strip()
    assert TID in versi.TEMPLATE_BARU
    assert TID in topics.ambil(TOPIK).templates and TID in REGISTRI
    assert topics.pemilik_template(TID) == TOPIK


def test_komposisi_topik_memuat_jenis_di_p1_dan_p2_saja_dan_hanya_manual():
    paket = topics.ambil(TOPIK)
    for level in LEVEL:
        assert TID in paket.komposisi[level]
    for level in ("P3", "P4", "P5", "P6"):
        assert TID not in paket.komposisi[level]
        with pytest.raises(ValueError, match="tidak tersedia untuk level"):
            generator.buat_soal(TID, 0, level, TOPIK)
    assert paket.hanya_manual is True


# ── pilihan ganda ────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_pilihan_ganda_seluruh_domain_tiga_opsi_pengecoh_cukup_dan_berbeda(level):
    for p in _domain(level):
        soal = _soal(p)
        kebijakan, jenis_kunci, pengecoh = kandidat(soal)
        assert kebijakan == "tiga-v1" and len(pengecoh) == 2, p
        assert jenis_kunci == ("angka" if p["varian"] == "hitung_bentuk" else "kategori"), p
        assert len({_norm(x) for x in pengecoh} | {_norm(soal.kunci)}) == 3, p
        assert kebijakan_soal(soal) == (kebijakan, jenis_kunci)


# ── lembar cetak memakai bentuk TEKS yang bisa dijawab ───────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_lembar_cetak_memakai_teks_lengkap_walau_flag_visual_menyala(level, monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    lihat = set()
    for seed in range(40):
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK)
        html = render.lembar_soal(list(lembar.soal), topik_paket=topics.ambil(TOPIK))
        for soal in lembar.soal:
            if soal.template_id != TID:
                continue
            lihat.add(soal.parameter["varian"])
            assert soal.penyajian is None
            assert solver_dari_teks(soal.teks, level) == soal.kunci
            assert "Perhatikan gambar" not in html or soal.template_id != TID
            assert "<svg" not in html
            assert soal.teks.split("\n")[0].split(" menggambar")[0][:3] in html or soal.teks.split("\n")[0][:12] in html
    assert lihat == set(VARIAN)


# ── penolakan parameter di luar domain ───────────────────────────────────

DATAR_OK = dict(himpunan="dasar", bangun="segitiga", ragam="siku", putar=90, ukuran="besar", warna="biru")
RUANG_OK = dict(himpunan="lengkap", bangun="kerucut", ragam="tegak", putar=0, ukuran="kecil", warna="hijau")
HITUNG_OK = dict(himpunan="dasar", banyak=[3, 1, 2], tanya=0, tata=2)


@pytest.mark.parametrize("varian, isi", [
    ("tidak_ada", DATAR_OK), (None, DATAR_OK), (["datar_gambar"], DATAR_OK),
    ("datar_gambar", {**DATAR_OK, "himpunan": "luas"}),
    ("datar_gambar", {**DATAR_OK, "bangun": "kubus"}),          # ruang pada varian datar
    ("datar_gambar", {**DATAR_OK, "bangun": "persegi panjang"}),  # belum ada di himpunan dasar
    ("datar_gambar", {**DATAR_OK, "ragam": "tegak"}),
    ("datar_gambar", {**DATAR_OK, "putar": 45}),
    ("datar_gambar", {**DATAR_OK, "putar": True}),
    ("datar_gambar", {**DATAR_OK, "putar": "90"}),
    ("datar_gambar", {**DATAR_OK, "ukuran": "sedang"}),
    ("datar_gambar", {**DATAR_OK, "warna": "merah"}),
    ("datar_gambar", {**DATAR_OK, "benda": 0}),
    ("datar_gambar", {**DATAR_OK, "banyak": [3, 1, 2]}),
    ("datar_gambar", {k: v for k, v in DATAR_OK.items() if k != "warna"}),
    ("datar_gambar", {**DATAR_OK, "bangun": "persegi", "putar": 90}),  # persegi miring dilarang
    ("ruang_gambar", {**DATAR_OK}),                              # datar pada varian ruang
    ("ruang_gambar", {**RUANG_OK, "himpunan": "dasar"}),         # kerucut belum ada di dasar
    ("ruang_gambar", {**RUANG_OK, "ragam": "mendatar"}),
    ("ruang_gambar", {**RUANG_OK, "putar": 90}),
    ("benda_ruang", dict(himpunan="dasar", bangun="kerucut", benda=0)),
    ("benda_ruang", dict(himpunan="dasar", bangun="bola", benda=3)),
    ("benda_ruang", dict(himpunan="dasar", bangun="bola", benda=-1)),
    ("benda_ruang", dict(himpunan="dasar", bangun="bola", benda=True)),
    ("benda_ruang", dict(himpunan="dasar", bangun="bola")),
    ("benda_ruang", dict(himpunan="dasar", bangun="bola", benda=0, warna="biru")),
    ("benda_ruang", dict(himpunan="dasar", bangun="persegi", benda=0)),
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [3, 3, 2]}),       # ditanya kembar jenis lain
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [3, 1]}),
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [3, 1, 2, 1]}),    # empat jenis pada himpunan dasar
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [7, 1, 2]}),       # di atas batas per jenis
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [1, 1, 1]}),       # total di bawah 4
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [6, 3, 2]}),       # total di atas 10
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [4, 0, 0]}),       # kurang dari dua jenis
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [3.0, 1, 2]}),
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [True, 1, 2]}),
    ("hitung_bentuk", {**HITUNG_OK, "banyak": "312"}),
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [-1, 3, 4]}),
    ("hitung_bentuk", {**HITUNG_OK, "tanya": 3}),
    ("hitung_bentuk", {**HITUNG_OK, "tanya": -1}),
    ("hitung_bentuk", {**HITUNG_OK, "tanya": "0"}),
    ("hitung_bentuk", {**HITUNG_OK, "banyak": [0, 3, 2], "tanya": 0}),   # yang ditanya tak ada
    ("hitung_bentuk", {**HITUNG_OK, "tata": 3}),
    ("hitung_bentuk", {**HITUNG_OK, "tata": None}),
    ("hitung_bentuk", {**HITUNG_OK, "warna": "biru"}),
    ("hitung_bentuk", {**HITUNG_OK, "bangun": "segitiga"}),
    ("hitung_bentuk", {**HITUNG_OK, "himpunan": "lengkap"}),     # empat jenis wajib pada himpunan lengkap
])
def test_parameter_tidak_sah_ditolak(varian, isi):
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.kenali_bangun_awal(varian, **isi)


def test_contoh_sah_dari_tabel_penolakan_memang_diterima():
    assert _soal({"varian": "datar_gambar", **DATAR_OK}).kunci == "segitiga"
    assert _soal({"varian": "ruang_gambar", **RUANG_OK}).kunci == "kerucut"
    assert _soal({"varian": "hitung_bentuk", **HITUNG_OK}).kunci == "3"
    assert _soal({"varian": "hitung_bentuk", **{**HITUNG_OK, "banyak": (3, 1, 2)}}).parameter["banyak"] == [3, 1, 2]


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_kenali_bangun_awal as jenis
hasil = []
for level in ("P1", "P2"):
    for seed in range(200):
        p = jenis.parameter(random.Random(seed), level)
        s = jenis.kenali_bangun_awal(**p)
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
    assert a == b == c and len(a) == 2 * len(SEED)

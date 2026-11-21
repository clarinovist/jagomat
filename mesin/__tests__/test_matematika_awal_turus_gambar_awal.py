"""Matematika Awal, jenis turus_gambar_awal (P2): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal: ia menghitung karakter
"|" pada tiap baris kategori, memeriksa sendiri format kelompok lima dan batas domain
(tiga kategori, 1..12 garis, jumlah garis berbeda semua), lalu menghitung ulang kunci.
Modul jenis diimpor langsung; tes ini tidak bergantung pada registrasi topik. Malrule
hanya HIPOTESIS kesalahan umum untuk ditinjau guru: yang dijaga di sini bukan kunci,
tidak kembar, dan selalu ada jalur K.
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

import awal_turus_gambar_awal as jenis
import templates
from templates import Soal

TID = "turus_gambar_awal"
LEVEL = "P2"
SEED = range(200)
VARIAN = ("baca", "terbanyak", "selisih", "jumlah")
TRIPLE = 220  # himpunan tiga angka berbeda dari 1..12, satu susunan tetap per himpunan
TEMA = 2
UKURAN_DOMAIN = {"baca": TEMA * TRIPLE * 3, "terbanyak": TEMA * TRIPLE,
                 "selisih": TEMA * TRIPLE * 3, "jumlah": TEMA * TRIPLE}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)
POLA_TURUS = re.compile(r"(?:\|{5} )*(?:\|{5}|\|{1,4})")  # kelompok lima, sisa di ujung


# ── solver terpisah: hanya membaca teks ──────────────────────────────────

def baca_data(teks: str) -> tuple:
    """(satuan, urutan nama, {nama huruf kecil: jumlah garis}, baris pertanyaan)."""
    baris = teks.split("\n")
    assert len(baris) == 5, ("harus pengantar + 3 baris kategori + pertanyaan", teks)
    cocok = re.fullmatch(
        r"[A-Z][a-z]+ menghitung ([a-z ]+) dengan turus\. Satu garis \(\|\) berarti satu "
        r"([a-z]+), dan tiap lima garis dikelompokkan\.", baris[0])
    assert cocok, ("pengantar tidak dikenal", baris[0])
    data, urutan = {}, []
    for b in baris[1:4]:
        c = re.fullmatch(r"([A-Z][a-z]+): ([| ]+)", b)
        assert c, ("baris kategori tidak dikenal", b)
        assert POLA_TURUS.fullmatch(c.group(2)), ("kelompok lima salah", b)
        nama = c.group(1).lower()
        assert nama not in data
        data[nama] = c.group(2).count("|")
        urutan.append(nama)
    assert all(1 <= n <= 12 for n in data.values()), ("jumlah garis di luar 1..12", teks)
    assert len(set(data.values())) == 3, ("jumlah garis harus berbeda semua", teks)
    return cocok.group(2), urutan, data, baris[4]


def solver_dari_teks(teks: str) -> str:
    satuan, _, data, tanya = baca_data(teks)
    cocok = re.fullmatch(r"Berapa (\w+) lebih banyak (\w+) daripada (\w+)\?", tanya)
    if cocok:
        assert cocok.group(1) == satuan
        besar, kecil = data[cocok.group(2)], data[cocok.group(3)]
        assert besar > kecil, ("yang ditanya harus lebih banyak", teks)
        return str(besar - kecil)
    cocok = re.fullmatch(r"Berapa (\w+) semuanya\?", tanya)
    if cocok:
        assert cocok.group(1) == satuan
        return str(sum(data.values()))
    cocok = re.fullmatch(r"([A-Z][a-z]+) apa yang paling banyak\?", tanya)
    if cocok:
        puncak = max(data.values())
        (nama,) = [n for n, v in data.items() if v == puncak]
        return nama
    cocok = re.fullmatch(r"Berapa (\w+) (\w+)\?", tanya)
    if cocok:
        assert cocok.group(1) == satuan and cocok.group(2) in data
        return str(data[cocok.group(2)])
    raise AssertionError("bentuk pertanyaan tidak dikenal: " + tanya)


def _soal(p: dict) -> Soal:
    return getattr(jenis, TID)(**p)


def _domain() -> tuple:
    return jenis.domain_parameter(LEVEL)


def _norm(teks: str) -> str:
    return re.sub(r"\s+", "", teks.strip().lower())


def _skor(n: int) -> int:
    """Banyak garis bila tiap kelompok lima dihitung satu garis."""
    return n // 5 + n % 5


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == getattr(jenis, TID).__name__
    assert jenis.LEVEL == ("P2",)
    with pytest.raises(ValueError):
        jenis.domain_parameter("P1")
    with pytest.raises(ValueError):
        jenis.parameter(random.Random(0), "P3")


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat():
    domain = _domain()
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN
    assert len(domain) == sum(UKURAN_DOMAIN.values())
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"


def test_domain_satu_susunan_per_himpunan_dan_kategori_terbanyak_bergantian():
    domain = _domain()
    for tema in (0, 1):
        triple = [tuple(p["jumlah"]) for p in domain
                  if p["varian"] == "jumlah" and p["tema"] == tema]
        assert len(triple) == TRIPLE == len({frozenset(t) for t in triple})
        puncak = {t.index(max(t)) for t in triple}
        assert puncak == {0, 1, 2}, "kategori terbanyak harus bergantian"
        kunci = {_soal(p).kunci for p in domain if p["varian"] == "terbanyak" and p["tema"] == tema}
        assert kunci == {n.lower() for n in jenis.TEMA[tema].nama}


def test_domain_dict_dan_list_baru_setiap_panggilan():
    a = _domain()
    a[0]["varian"] = "rusak"
    a[0]["jumlah"][0] = 99
    b = _domain()
    assert b[0]["varian"] == "baca" and b[0]["jumlah"][0] != 99
    assert isinstance(b[0]["jumlah"], list)


def test_domain_mencakup_batas_dan_semua_kategori_tanya():
    domain = _domain()
    semua = {n for p in domain for n in p["jumlah"]}
    assert semua == set(range(1, 13))
    assert {p["tanya"] for p in domain if p["varian"] == "baca"} == {0, 1, 2}
    assert {p["tema"] for p in domain} == {0, 1}
    assert all(len(set(p["jumlah"])) == 3 for p in domain)


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian = set()
    for seed in SEED:
        p = jenis.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
    assert varian == set(VARIAN)


def test_sampler_murni_dari_rng_seed_sama_hasil_sama():
    for seed in SEED:
        assert (jenis.parameter(random.Random(seed), LEVEL)
                == jenis.parameter(random.Random(seed), LEVEL))


# ── kunci lawan solver teks ──────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID
        assert soal.kunci == soal.kunci.strip().lower() and " " not in soal.kunci


def test_sampel_seed_kunci_sama_dengan_solver():
    for seed in SEED:
        soal = _soal(jenis.parameter(random.Random(seed), LEVEL))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_kunci_dan_teks_contoh_tangan():
    f = getattr(jenis, TID)
    baca = f("baca", tema=0, jumlah=[7, 3, 4], tanya=0)
    assert baca.teks == (
        "Rina menghitung buah di keranjang dengan turus. Satu garis (|) berarti satu buah, "
        "dan tiap lima garis dikelompokkan.\n"
        "Apel: ||||| ||\nJeruk: |||\nPisang: ||||\nBerapa buah apel?")
    assert baca.kunci == "7"
    assert f("baca", tema=0, jumlah=[7, 3, 12], tanya=2).teks.splitlines()[3] == "Pisang: ||||| ||||| ||"
    assert f("baca", tema=1, jumlah=[10, 3, 4], tanya=1).teks.endswith("Berapa ekor ayam?")
    terbanyak = f("terbanyak", tema=0, jumlah=[7, 3, 9])
    assert terbanyak.kunci == "pisang" and terbanyak.teks.endswith("Buah apa yang paling banyak?")
    assert f("terbanyak", tema=1, jumlah=[2, 11, 9]).kunci == "ayam"
    selisih = f("selisih", tema=0, jumlah=[7, 3, 4], besar=0, kecil=1)
    assert selisih.teks.endswith("Berapa buah lebih banyak apel daripada jeruk?")
    assert selisih.kunci == "4"
    assert f("jumlah", tema=1, jumlah=[7, 3, 4]).kunci == "14"
    assert f("jumlah", tema=1, jumlah=[7, 3, 4]).teks.endswith("Berapa ekor semuanya?")


def test_teks_tanpa_gambar_dan_pertanyaan_di_baris_terakhir():
    for p in _domain()[:: 37]:
        soal = _soal(p)
        assert soal.teks.split("\n")[-1].endswith("?")
        assert "?" not in "".join(soal.teks.split("\n")[:-1])


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


def test_setiap_parameter_punya_dua_pengecoh_berbeda_untuk_pilihan_ganda():
    for p in _domain():
        assert len(_soal(p).malrule) >= 2, p


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


def test_baca_kelompok_lima_dihitung_satu_dan_baris_lain_dan_kurang_satu():
    m = _malrule(dict(varian="baca", tema=0, jumlah=[7, 3, 12], tanya=0))
    assert m["kelompok_dihitung_satu"].jawaban == str(_skor(7)) == "3"
    assert m["kelompok_dihitung_satu"].kode == "K"
    assert {x.jawaban for x in m.values() if x.kode == "K"} >= {"3", "12"}
    assert m["terlewat_satu"].jawaban == "6" and m["terlewat_satu"].kode == "H"
    # pada jumlah kecil (<5) kelompok lima tak ada, jadi malrule itu tak kembar kunci dibuang
    kecil = _malrule(dict(varian="baca", tema=0, jumlah=[4, 3, 12], tanya=0))
    assert "kelompok_dihitung_satu" not in kecil
    assert any(x.kode == "K" for x in kecil.values())
    # terlewat satu tidak jadi pengecoh 0
    satu = _malrule(dict(varian="baca", tema=0, jumlah=[1, 3, 12], tanya=0))
    assert "terlewat_satu" not in satu


def test_baca_semua_n_di_domain_malrule_kelompok_muncul_bila_berbeda():
    for p in _domain():
        if p["varian"] != "baca":
            continue
        n = p["jumlah"][p["tanya"]]
        ada = "kelompok_dihitung_satu" in _malrule(p)
        # Bisa hilang oleh saringan bila angkanya kembar malrule lain, tapi tak pernah bila
        # n < 5 (sama dengan kunci).
        if n < 5:
            assert not ada, p


def test_terbanyak_pengecoh_adalah_dua_kategori_lain():
    for p in _domain():
        if p["varian"] != "terbanyak":
            continue
        soal = _soal(p)
        nama = {n.lower() for n in jenis.TEMA[p["tema"]].nama}
        assert {m.jawaban for m in soal.malrule} == nama - {soal.kunci}, p
        assert all(m.kode == "K" for m in soal.malrule)


def test_selisih_dijumlah_lawan_dikurang_dan_kurang_satu():
    m = _malrule(dict(varian="selisih", tema=0, jumlah=[9, 4, 6], besar=0, kecil=1))
    assert m["dijumlah"].jawaban == "13" and m["dijumlah"].kode == "K"
    assert m["satu_baris_saja"].jawaban == "9" and m["satu_baris_saja"].kode == "K"
    assert m["terlewat_satu"].jawaban == "4" and m["terlewat_satu"].kode == "H"


def test_jumlah_lupa_satu_baris_dan_kelompok_dan_kurang_satu():
    m = _malrule(dict(varian="jumlah", tema=0, jumlah=[7, 3, 12]))
    assert m["lupa_baris_1"].jawaban == "15" and m["lupa_baris_1"].kode == "K"
    assert m["kelompok_dihitung_satu"].jawaban == str(_skor(7) + _skor(3) + _skor(12)) == "10"
    assert m["terlewat_satu"].jawaban == "21" and m["terlewat_satu"].kode == "H"


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40
        assert soal.pembahasan.strip() != soal.kunci
        assert not re.search(r"\bx\b|×|dikali|kali", soal.pembahasan), soal.pembahasan  # tahap awal: tanpa perkalian


def test_cara_menghitung_baris_memakai_penjumlahan_berulang():
    f = getattr(jenis, TID)
    assert "5 + 5 + 2 = 12" in f("baca", tema=0, jumlah=[12, 3, 4], tanya=0).pembahasan
    assert "5 + 2 = 7" in f("baca", tema=0, jumlah=[7, 3, 4], tanya=0).pembahasan
    assert "5 + 5 = 10" in f("baca", tema=0, jumlah=[10, 3, 4], tanya=0).pembahasan
    assert "1 kelompok lima, jadi 5" in f("baca", tema=0, jumlah=[5, 3, 4], tanya=0).pembahasan
    assert "3 garis" in f("baca", tema=0, jumlah=[3, 6, 4], tanya=0).pembahasan


def test_tanpa_nama_anak_nyata_hanya_nama_sintetis_umum():
    assert {t.tokoh for t in jenis.TEMA} == {"Rina", "Budi"}
    for t in jenis.TEMA:
        assert all(re.fullmatch(r"[A-Z][a-z]+", n) for n in t.nama)


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("varian, isi", [
    ("tidak_ada", dict(tema=0, jumlah=[7, 3, 4])),
    (None, dict(tema=0, jumlah=[7, 3, 4])),
    ("baca", dict(tema=0, jumlah=[7, 3, 4])),                       # tanpa tanya
    ("baca", dict(tema=0, jumlah=[7, 3, 4], tanya=3)),
    ("baca", dict(tema=0, jumlah=[7, 3, 4], tanya=-1)),
    ("baca", dict(tema=0, jumlah=[7, 3, 4], tanya="0")),
    ("baca", dict(tema=2, jumlah=[7, 3, 4], tanya=0)),
    ("baca", dict(tema=-1, jumlah=[7, 3, 4], tanya=0)),
    ("baca", dict(tema=0, jumlah=[7, 3, 13], tanya=0)),             # 13 garis
    ("baca", dict(tema=0, jumlah=[0, 3, 4], tanya=0)),              # 0 garis
    ("baca", dict(tema=0, jumlah=[7, 3], tanya=0)),                 # dua kategori
    ("baca", dict(tema=0, jumlah=[7, 3, 4, 5], tanya=0)),           # empat kategori
    ("baca", dict(tema=0, jumlah=[7, 7, 4], tanya=0)),              # jumlah kembar
    ("baca", dict(tema=0, jumlah=[7.0, 3, 4], tanya=0)),
    ("baca", dict(tema=0, jumlah=[True, 3, 4], tanya=0)),
    ("baca", dict(tema=0, jumlah="734", tanya=0)),
    ("baca", dict(tema=0, jumlah=[7, 3, 4], tanya=0, besar=0)),
    ("terbanyak", dict(tema=0, jumlah=[7, 3, 4], tanya=0)),
    ("terbanyak", dict(tema=0, jumlah=[7, 3, 7])),
    ("terbanyak", dict(tema=0)),
    ("selisih", dict(tema=0, jumlah=[7, 3, 4], besar=1, kecil=0)),  # yang ditanya lebih sedikit
    ("selisih", dict(tema=0, jumlah=[7, 3, 4], besar=0, kecil=0)),
    ("selisih", dict(tema=0, jumlah=[7, 3, 4], besar=0, kecil=3)),
    ("selisih", dict(tema=0, jumlah=[7, 3, 4], besar=0)),
    ("jumlah", dict(tema=0, jumlah=[7, 3, 14])),
    ("jumlah", dict(tema=0, jumlah=None)),
    ("jumlah", dict(jumlah=[7, 3, 4])),
])
def test_parameter_tidak_sah_ditolak(varian, isi):
    with pytest.raises(ValueError, match="di luar domain"):
        getattr(jenis, TID)(varian, **isi)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_turus_gambar_awal as jenis
hasil = []
for seed in range(200):
    p = jenis.parameter(random.Random(seed), "P2")
    s = getattr(jenis, "turus_gambar_awal")(**p)
    hasil.append([p, s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                  [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
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
    assert a == b == c
    assert len(a) == len(SEED)

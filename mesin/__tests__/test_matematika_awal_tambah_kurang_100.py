"""Matematika Awal, jenis tambah_kurang_100 (P2): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang
hanya membaca TEKS soal. Malrule hanya HIPOTESIS kesalahan umum; yang dijaga: bukan
kunci, tidak kembar, selalu ada jalur K, dan cukup pengecoh angka.
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

import awal_tambah_kurang_100 as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "tambah_kurang_100"
LEVEL = "P2"
SEED = range(200)
VARIAN = ("tambah", "kurang", "lengkapi", "cerita")
BENTUK = ("cari_tambahan", "cari_awal_tambah", "cari_pengurang", "cari_awal_kurang")
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # mesin/, juga untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)
MINUS = "−"


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _simpan(a: int, b: int) -> bool:
    return a % 10 + b % 10 >= 10


def _pinjam(a: int, b: int) -> bool:
    return a % 10 < b % 10


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    cocok = re.fullmatch(r"(\d+) \+ (\d+) = \.\.\.", teks)
    if cocok:
        jumlah = int(cocok.group(1)) + int(cocok.group(2))
        assert jumlah <= 100, ("hasil lebih dari 100", teks)
        return str(jumlah)
    cocok = re.fullmatch(rf"(\d+) {MINUS} (\d+) = \.\.\.", teks)
    if cocok:
        selisih = int(cocok.group(1)) - int(cocok.group(2))
        assert selisih >= 1, ("hasil kurang dari 1", teks)
        return str(selisih)
    cocok = re.fullmatch(r"(\d+) \+ \.\.\. = (\d+)", teks)
    if cocok:
        return _hilang(int(cocok.group(2)) - int(cocok.group(1)), teks)
    cocok = re.fullmatch(r"\.\.\. \+ (\d+) = (\d+)", teks)
    if cocok:
        return _hilang(int(cocok.group(2)) - int(cocok.group(1)), teks)
    cocok = re.fullmatch(rf"(\d+) {MINUS} \.\.\. = (\d+)", teks)
    if cocok:
        return _hilang(int(cocok.group(1)) - int(cocok.group(2)), teks)
    cocok = re.fullmatch(rf"\.\.\. {MINUS} (\d+) = (\d+)", teks)
    if cocok:
        return _hilang(int(cocok.group(1)) + int(cocok.group(2)), teks)
    return _cerita(teks)


def _hilang(nilai: int, teks: str) -> str:
    assert 1 <= nilai <= 100, ("bilangan hilang di luar 1..100", teks)
    return str(nilai)


def _cerita(teks: str) -> str:
    angka = [int(n) for n in re.findall(r"\d+", teks)]
    assert len(angka) == 2, ("cerita harus memuat tepat dua bilangan", teks)
    assert teks.count("?") == 1 and teks.endswith("?"), teks
    kurang = re.search(r"tersisa|masih", teks) is not None
    if kurang:
        assert angka[0] > angka[1], teks
        return str(angka[0] - angka[1])
    assert angka[0] + angka[1] <= 100, teks
    return str(angka[0] + angka[1])


def _pengecoh_angka(soal) -> set:
    benar = nilai_semantis(soal.kunci, "angka")
    hasil = set()
    for m in soal.malrule:
        n = nilai_semantis(m.jawaban, "angka")
        if n >= 0 and n != benar:
            hasil.add(n)
    return hasil


def _operan(teks: str) -> list:
    return [int(n) for n in re.findall(r"\d+", teks)]


# ── kontrak modul dan domain ─────────────────────────────────────────────

def test_kontrak_modul_nama_dan_level():
    assert modul.TEMPLATE_ID == TID
    assert tuple(modul.LEVEL) == (LEVEL,)
    assert callable(getattr(modul, TID))
    assert modul.TEMPLATE_ID == getattr(modul, TID).__name__


def test_domain_cukup_besar_tanpa_duplikat_dan_semua_varian_bentuk_ada():
    domain = _domain()
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    assert len(domain) >= 40
    assert {p["varian"] for p in domain} == set(VARIAN)
    assert {p["bentuk"] for p in domain if p["varian"] == "lengkapi"} == set(BENTUK)
    assert {p["op"] for p in domain if p["varian"] == "cerita"} == {"tambah", "kurang"}
    assert {p["pola"] for p in domain if p["varian"] == "cerita"} == {0, 1, 2}


def test_domain_dict_baru_tiap_panggilan_dan_tuple_beku():
    domain = _domain()
    assert isinstance(domain, tuple)
    domain[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"


def test_domain_tiap_varian_punya_kedua_kelas_simpan_pinjam():
    for varian in VARIAN:
        kelas = set()
        for p in _domain():
            if p["varian"] != varian:
                continue
            soal = _soal(p)
            kelas.add(modul._kelas(varian, p))
            assert soal.parameter == p
        assert kelas == {"tanpa", "dengan"}, varian


def test_operan_tampil_bukan_kelipatan_sepuluh_dan_dalam_kelas_dua():
    for p in _domain():
        if p["varian"] in ("tambah", "kurang"):
            a, b = p["a"], p["b"]
            assert 11 <= a <= 99 and 2 <= b <= 99, p
            assert a % 10 != 0 and b % 10 != 0, p
        elif p["varian"] == "cerita":
            assert 11 <= p["a"] <= 99 and 2 <= p["b"] <= 99, p
        else:
            assert 11 <= p["x"] <= 99 and 1 <= p["c"] <= 100, p


def test_tambah_kurang_lengkapi_cerita_separuh_domain_tanpa_simpan_pinjam_kira_kira():
    domain = _domain()
    for varian in ("tambah", "kurang"):
        isi = [p for p in domain if p["varian"] == varian]
        dengan = sum(1 for p in isi if modul._kelas(varian, p) == "dengan")
        assert 0.35 < dengan / len(isi) < 0.65, (varian, dengan, len(isi))


def test_sampel_selalu_di_dalam_domain_dan_menyentuh_semua_varian_dan_kelas():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian, kelas = set(), set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
        kelas.add((p["varian"], modul._kelas(p["varian"], p)))
    assert varian == set(VARIAN)
    assert len(kelas) == 8


def test_sampler_murni_dari_rng_seed_sama_hasil_sama_dan_beragam():
    a = [modul.parameter(random.Random(s), LEVEL) for s in SEED]
    b = [modul.parameter(random.Random(s), LEVEL) for s in SEED]
    assert a == b
    assert len({json.dumps(p, sort_keys=True) for p in a}) > 150


def test_sampler_membagi_varian_hampir_seragam():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(800):
        hitung[modul.parameter(random.Random(seed), LEVEL)["varian"]] += 1
    assert all(150 < n < 250 for n in hitung.values()), hitung


def test_level_selain_p2_ditolak():
    for level in ("P1", "P3", "P4", "P5", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.template_id == TID and soal.bagian == "A"
        assert re.fullmatch(r"[1-9]\d{0,2}", soal.kunci), ("kunci angka polos", soal.kunci)
        assert 1 <= int(soal.kunci) <= 100


def test_kunci_dan_teks_contoh_tangan():
    f = modul.tambah_kurang_100
    assert f(varian="tambah", a=38, b=27).teks == "38 + 27 = ..."
    assert f(varian="tambah", a=38, b=27).kunci == "65"
    assert f(varian="tambah", a=21, b=36).kunci == "57"
    assert f(varian="kurang", a=52, b=28).teks == f"52 {MINUS} 28 = ..."
    assert f(varian="kurang", a=52, b=28).kunci == "24"
    assert f(varian="kurang", a=77, b=54).kunci == "23"
    assert f(varian="lengkapi", bentuk="cari_tambahan", x=11, c=26).teks == "11 + ... = 26"
    assert f(varian="lengkapi", bentuk="cari_tambahan", x=11, c=26).kunci == "15"
    assert f(varian="lengkapi", bentuk="cari_awal_tambah", x=15, c=26).teks == "... + 15 = 26"
    assert f(varian="lengkapi", bentuk="cari_awal_tambah", x=15, c=26).kunci == "11"
    assert f(varian="lengkapi", bentuk="cari_pengurang", x=13, c=1).teks == f"13 {MINUS} ... = 1"
    assert f(varian="lengkapi", bentuk="cari_pengurang", x=13, c=1).kunci == "12"
    assert f(varian="lengkapi", bentuk="cari_awal_kurang", x=12, c=1).teks == f"... {MINUS} 12 = 1"
    assert f(varian="lengkapi", bentuk="cari_awal_kurang", x=12, c=1).kunci == "13"


def test_lengkapi_seluruh_domain_cocok_bila_diisi_kembali_ke_teks():
    for p in _domain():
        if p["varian"] != "lengkapi":
            continue
        soal = _soal(p)
        isi = soal.teks.replace("...", soal.kunci)
        kiri, kanan = isi.split(" = ")
        u, tanda, v = re.fullmatch(rf"(\d+) ([+{MINUS}]) (\d+)", kiri).groups()
        nilai = int(u) + int(v) if tanda == "+" else int(u) - int(v)
        assert nilai == int(kanan), (soal.teks, soal.kunci)


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        kunci = normalisasi(soal.kunci)
        jawaban = [normalisasi(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)


def test_tiap_parameter_punya_cukup_pengecoh_angka_untuk_pilihan_ganda():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh_angka(soal)) >= 3, (p, [m.jawaban for m in soal.malrule])


def test_tambah_dengan_simpan_malrule_contoh_tangan():
    jawaban = {m.jawaban: m.kode for m in modul.tambah_kurang_100(
        varian="tambah", a=38, b=27).malrule}
    assert jawaban["55"] == "K"   # lupa menyimpan
    assert jawaban["515"] == "K"  # hasil satuan ditulis utuh
    assert jawaban["11"] == "K"   # dikurangkan
    assert jawaban["75"] == "H" and jawaban["66"] == "H"
    assert "65" not in jawaban


def test_tambah_tanpa_simpan_tidak_punya_malrule_lupa_menyimpan():
    for p in _domain():
        if p["varian"] != "tambah" or _simpan(p["a"], p["b"]):
            continue
        ids = {m.id.split(".")[-1] for m in _soal(p).malrule}
        assert "lupa_menyimpan" not in ids and "satuan_ditulis_utuh" not in ids, p


def test_kurang_dengan_pinjam_malrule_contoh_tangan():
    jawaban = {m.jawaban: m.kode for m in modul.tambah_kurang_100(
        varian="kurang", a=52, b=28).malrule}
    assert jawaban["36"] == "K"   # per kolom besar dikurangi kecil
    assert jawaban["34"] == "K"   # puluhan yang dipinjam tidak dikurangi
    assert jawaban["80"] == "K"   # operasi dibalik (ditambah)
    assert jawaban["14"] == "H"   # kurang 10
    assert "24" not in jawaban


def test_kurang_tanpa_pinjam_tidak_punya_malrule_kolom_tertukar():
    for p in _domain():
        if p["varian"] != "kurang" or _pinjam(p["a"], p["b"]):
            continue
        ids = {m.id.split(".")[-1] for m in _soal(p).malrule}
        assert "kolom_tertukar" not in ids and "lupa_kurangi_pinjaman" not in ids, p


def test_malrule_kolom_tertukar_selalu_lebih_kecil_dari_kunci_dan_tidak_negatif():
    for p in _domain():
        if p["varian"] != "kurang" or not _pinjam(p["a"], p["b"]):
            continue
        soal = _soal(p)
        tertukar = [m for m in soal.malrule if m.id.endswith("kolom_tertukar")]
        assert len(tertukar) == 1 and int(tertukar[0].jawaban) > int(soal.kunci), p
        assert int(tertukar[0].jawaban) >= 0


def test_lengkapi_malrule_mengikuti_operasi_yang_dihitung_anak():
    f = modul.tambah_kurang_100
    cari_tambahan = {m.jawaban: m.kode for m in f(
        varian="lengkapi", bentuk="cari_tambahan", x=11, c=26).malrule}
    assert cari_tambahan["37"] == "K"   # dijumlahkan (26 + 11), bukan dikurangkan
    akhir_kurang = {m.jawaban: m.kode for m in f(
        varian="lengkapi", bentuk="cari_awal_kurang", x=12, c=1).malrule}
    assert akhir_kurang["11"] == "K"    # dikurangkan (12 - 1), bukan ditambah


def test_malrule_h_selalu_dalam_rentang_wajar():
    for p in _domain():
        for m in _soal(p).malrule:
            if m.kode == "H":
                assert 1 <= int(m.jawaban) <= 100, (p, m.jawaban)


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        assert soal.kunci in set(re.findall(r"\d+", teks)), ("kunci tidak muncul", teks)


def test_pembahasan_menyebut_simpan_hanya_bila_ada_simpan_dan_pinjam_hanya_bila_ada_pinjam():
    for p in _domain():
        if p["varian"] not in ("tambah", "kurang"):
            continue
        teks = _soal(p).pembahasan
        if p["varian"] == "tambah":
            assert ("simpan" in teks) == _simpan(p["a"], p["b"]), (p, teks)
        else:
            assert ("pinjam" in teks) == _pinjam(p["a"], p["b"]), (p, teks)


def test_pembahasan_aritmetika_tiap_langkah_benar():
    # Setiap "x + y = z" dan "x - y = z" yang ditulis pembahasan harus benar.
    pola = re.compile(rf"(?<!\d [+{MINUS}] )(?<!\d)(\d+) ([+{MINUS}]) (\d+) = (\d+)(?!\d)(?! [+{MINUS}] )")
    for p in _domain():
        teks = _soal(p).pembahasan
        for kiri, tanda, kanan, hasil in pola.findall(teks):
            hitung = int(kiri) + int(kanan) if tanda == "+" else int(kiri) - int(kanan)
            assert hitung == int(hasil), (p, teks, kiri, tanda, kanan, hasil)


def test_teks_satu_pertanyaan_tanpa_gambar_dan_cerita_hanya_dua_bilangan():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        if p["varian"] == "cerita":
            assert len(_operan(teks)) == 2 and teks.endswith("?")
        else:
            assert teks.count("...") == 1


def test_cerita_tambah_dan_kurang_tidak_tertukar_kata_penanda():
    for p in _domain():
        if p["varian"] != "cerita":
            continue
        teks = _soal(p).teks
        ada_kurang = re.search(r"tersisa|masih", teks) is not None
        assert ada_kurang == (p["op"] == "kurang"), teks


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", a=38, b=27),
    dict(varian="tambah"),
    dict(varian="tambah", a=38),
    dict(varian="tambah", a=38, b=27, x=1),
    dict(varian="tambah", a=40, b=27),      # kelipatan 10
    dict(varian="tambah", a=38, b=70),      # kelipatan 10
    dict(varian="tambah", a=88, b=27),      # hasil > 100
    dict(varian="tambah", a=9, b=27),       # a satu angka
    dict(varian="tambah", a=38, b=1),       # b di bawah batas
    dict(varian="tambah", a=100, b=2),
    dict(varian="tambah", a=True, b=27),
    dict(varian="tambah", a="38", b=27),
    dict(varian="tambah", a=38.0, b=27),
    dict(varian="kurang", a=28, b=52),      # hasil negatif
    dict(varian="kurang", a=38, b=38),      # hasil nol
    dict(varian="kurang", a=50, b=28),
    dict(varian="kurang", a=52, b=-3),
    dict(varian="lengkapi", bentuk="tidak_ada", x=11, c=26),
    dict(varian="lengkapi", bentuk="cari_tambahan", x=11),
    dict(varian="lengkapi", bentuk="cari_tambahan", x=11, c=500),
    dict(varian="lengkapi", bentuk="cari_tambahan", x=11, c=26.0),
    dict(varian="lengkapi", bentuk=["cari_tambahan"], x=11, c=26),
    dict(varian="lengkapi", bentuk="cari_tambahan", a=11, b=15),
    dict(varian="lengkapi", bentuk="cari_tambahan", x=11, c=27),  # sah bentuk, di luar domain jarang
    dict(varian="cerita", op="kali", a=38, b=27, pola=0),
    dict(varian="cerita", op="tambah", a=38, b=27, pola=3),
    dict(varian="cerita", op="tambah", a=38, b=27, pola=-1),
    dict(varian="cerita", op="tambah", a=38, b=27),
    dict(varian=["tambah"], a=38, b=27),
    dict(varian=None, a=38, b=27),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.tambah_kurang_100(**parameter)


def test_pasangan_sah_tetapi_tidak_di_domain_ditolak_konsisten():
    domain = {json.dumps(p, sort_keys=True) for p in _domain()}
    ditolak = 0
    for a in range(11, 60):
        for b in range(11, 40):
            p = dict(varian="lengkapi", bentuk="cari_tambahan", x=a, c=a + b)
            try:
                modul.tambah_kurang_100(**p)
                diterima = True
            except ValueError:
                diterima = False
            assert diterima == (json.dumps(p, sort_keys=True) in domain), p
            ditolak += not diterima
    assert ditolak > 0


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_tambah_kurang_100 as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P2")
    s = m.tambah_kurang_100(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan,
                  [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    kode = _KODE % {"akar": str(AKAR_MESIN), "dir": str(DIR_MODUL)}
    hasil = subprocess.run([sys.executable, "-c", kode], env=env,
                           capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 150

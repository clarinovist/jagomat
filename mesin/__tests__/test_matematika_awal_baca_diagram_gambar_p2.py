"""Matematika Awal, baca_diagram_gambar level P2 (skala): domain, solver teks, malrule, P1 utuh.

Solver MANDIRI: hanya membaca TEKS soal (menghitung "●" per baris dan mengambil skala dari
kalimat kepala), tidak memakai fungsi kunci produksi. Daftar kategori per tema ditulis ulang
di sini. P1 dijaga byte-identik lewat tiga sidik yang dihitung dari main SEBELUM kode diubah
(domain, 200 undian seed tetap, dan seluruh isi soal domain P1).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import json
import os
import random
import re
import subprocess
import sys

import pytest

import awal_baca_diagram_gambar as modul
import diagnosis
from templates import Soal

TID = "baca_diagram_gambar"
VARIAN = ("baca", "terbanyak", "selisih", "jumlah")
SIMBOL = "●"
KATEGORI_TES = {
    "mainan": ("bola", "mobil", "boneka"),
    "buah": ("apel", "jeruk", "pisang"),
    "hewan": ("ayam", "bebek", "kelinci"),
}
BATAS_SKALA = {1: (5, 12), 2: (1, 8)}  # skala -> (minimum, maksimum) jumlah titik
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis|intervensi", re.I)

# Sidik P1 dihitung dari kode SEBELUM P2 ditambahkan (repr tuple immutable, sha256).
SIDIK_DOMAIN_P1 = "13390dc99a85121599c050d72032daa8efed14e82c38c972ebdb8467479dd6f4"
SIDIK_UNDIAN_P1 = "a02792aaa9f836e85045969af9c2e70c1a76309c21d287daf1d003bcb5db3678"
SIDIK_SOAL_P1 = "96017c731eefa16865988a5d1cf8ec339eb986b2b208447997f3e45b19f94c67"
SEED_UNDIAN_P1 = 20261121
JUMLAH_UNDIAN_P1 = 200


def _sidik(nilai) -> str:
    return hashlib.sha256(repr(nilai).encode()).hexdigest()


def _soal(parameter: dict) -> Soal:
    return replace(modul.baca_diagram_gambar(**parameter), level="P2")


def _domain() -> tuple:
    return modul.domain_parameter("P2")


# ── solver terpisah: hanya membaca teks ──────────────────────────────────

POLA_KEPALA = re.compile(
    r"Diagram gambar ([a-z]+) di ([a-z]+)\. Satu titik hitam mewakili ([12]) ([a-z]+)\.")
POLA_BARIS = re.compile(rf"([A-Z][a-z]+): ({SIMBOL}+)")


def _baca(teks: str):
    baris = teks.split("\n")
    assert len(baris) == 5, teks
    kepala = POLA_KEPALA.fullmatch(baris[0])
    assert kepala, ("kepala tidak dikenal", baris[0])
    skala = int(kepala.group(3))
    banyak = {}
    for isi in baris[1:4]:
        cocok = POLA_BARIS.fullmatch(isi)
        assert cocok, ("baris data tidak dikenal", isi)
        banyak[cocok.group(1).lower()] = len(cocok.group(2))
    assert teks.count(SIMBOL) == sum(banyak.values())
    assert SIMBOL not in baris[0] and SIMBOL not in baris[4]
    assert not re.search(r"\d", "\n".join(baris[1:]))  # angka skala hanya di kalimat kepala
    assert tuple(banyak) == KATEGORI_TES[kepala.group(1)]
    assert len(set(banyak.values())) == 3
    assert all(BATAS_SKALA[skala][0] <= n <= BATAS_SKALA[skala][1] for n in banyak.values()), (skala, banyak)
    return banyak, skala, baris[4]


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja: nilai benda = jumlah titik x skala dari kalimat kepala."""
    titik, skala, tanya = _baca(teks)
    nilai = {nama: n * skala for nama, n in titik.items()}
    cocok = re.fullmatch(r"Berapa banyak ([a-z]+)\?", tanya)
    if cocok:
        return str(nilai[cocok.group(1)])
    if tanya == "Mana yang paling banyak?":
        terbesar = max(titik.values())
        pemenang = [k for k, n in titik.items() if n == terbesar]
        assert len(pemenang) == 1, teks
        return pemenang[0]
    cocok = re.fullmatch(r"([A-Z][a-z]+) lebih banyak berapa daripada ([a-z]+)\?", tanya)
    if cocok:
        atas, bawah = cocok.group(1).lower(), cocok.group(2)
        assert titik[atas] > titik[bawah], teks
        return str(nilai[atas] - nilai[bawah])
    cocok = re.fullmatch(r"Berapa jumlah ([a-z]+) dan ([a-z]+)\?", tanya)
    assert cocok, ("pertanyaan tidak dikenal", teks)
    assert cocok.group(1) != cocok.group(2)
    return str(nilai[cocok.group(1)] + nilai[cocok.group(2)])


def _titik_tanpa_skala(teks: str, varian: str) -> int:
    """Jawaban angka bila skala dilupakan (jumlah titik saja), dari teks."""
    titik, _, tanya = _baca(teks)
    if varian == "baca":
        return titik[re.fullmatch(r"Berapa banyak ([a-z]+)\?", tanya).group(1)]
    if varian == "selisih":
        cocok = re.fullmatch(r"([A-Z][a-z]+) lebih banyak berapa daripada ([a-z]+)\?", tanya)
        return titik[cocok.group(1).lower()] - titik[cocok.group(2)]
    cocok = re.fullmatch(r"Berapa jumlah ([a-z]+) dan ([a-z]+)\?", tanya)
    return titik[cocok.group(1)] + titik[cocok.group(2)]


# ── P1 tidak berubah sama sekali ─────────────────────────────────────────

def _isi_soal_p1() -> tuple:
    hasil = []
    for p in modul.domain_parameter("P1"):
        s = modul.baca_diagram_gambar(**p)
        hasil.append((tuple(s.parameter.items()), s.teks, s.kunci,
                      tuple((r.id, r.jawaban, r.kode, r.alasan) for r in s.malrule),
                      s.pembahasan, s.bagian, s.template_id))
    return tuple(hasil)


def test_domain_p1_byte_identik_dengan_sebelum_p2_ada():
    domain = modul.domain_parameter("P1")
    assert len(domain) == 10080
    assert _sidik(tuple(tuple(p.items()) for p in domain)) == SIDIK_DOMAIN_P1


def test_urutan_undian_p1_identik_dengan_sebelum_p2_ada():
    rng = random.Random(SEED_UNDIAN_P1)
    undian = tuple(tuple(modul.parameter(rng, "P1").items()) for _ in range(JUMLAH_UNDIAN_P1))
    assert _sidik(undian) == SIDIK_UNDIAN_P1


def test_isi_soal_p1_identik_kunci_malrule_pembahasan_teks_parameter():
    assert _sidik(_isi_soal_p1()) == SIDIK_SOAL_P1


def test_soal_p1_tanpa_field_skala_dan_batas_delapan_tetap():
    assert all("skala" not in p for p in modul.domain_parameter("P1"))
    for jumlah in (9, 12):
        with pytest.raises(ValueError, match="di luar domain"):
            modul.baca_diagram_gambar("terbanyak", "mainan", 1, 2, jumlah)


# ── domain P2 ────────────────────────────────────────────────────────────

def _ukuran_harapan(varian: str, skala: int) -> int:
    """3 tema x banyak permutasi jumlah berbeda x pilihan tambahan (ditulis ulang di tes)."""
    terkecil, terbesar = BATAS_SKALA[skala]
    n = terbesar - terkecil + 1
    permutasi = n * (n - 1) * (n - 2)
    pilihan = {"baca": 3, "terbanyak": 1, "selisih": 3, "jumlah": 3}[varian]
    return 3 * permutasi * pilihan


def test_level_p2_sah_dan_level_lain_ditolak():
    assert modul.LEVEL == ("P1", "P2")
    for level in ("P3", "P6", "", "p2", None):
        with pytest.raises(ValueError, match="harus P1 atau P2"):
            modul.domain_parameter(level)
        with pytest.raises(ValueError, match="harus P1 atau P2"):
            modul.parameter(random.Random(0), level)


def test_domain_p2_tanpa_duplikat_ukuran_per_varian_dan_skala_dan_dict_baru():
    domain = _domain()
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain)
    hitung = Counter((p["varian"], p["skala"]) for p in domain)
    assert hitung == {(v, s): _ukuran_harapan(v, s) for v in VARIAN for s in BATAS_SKALA}
    assert len(domain) == sum(hitung.values()) == 20160 == 2 * len(modul.domain_parameter("P1"))
    assert {p["tema"] for p in domain} == set(KATEGORI_TES)
    _domain()[0]["tema"] = "rusak"
    assert _domain()[0]["tema"] != "rusak"


def test_urutan_enumerasi_p2_tetap_varian_tema_skala_lalu_jumlah():
    domain = _domain()
    varian = [p["varian"] for p in domain]
    assert [v for i, v in enumerate(varian) if i == 0 or v != varian[i - 1]] == list(VARIAN)
    baca = [p for p in domain if p["varian"] == "baca"]
    assert baca[0] == {"varian": "baca", "tema": "mainan", "n1": 5, "n2": 6, "n3": 7,
                       "skala": 1, "tanya": 0}
    kunci_urut = [(p["tema"], p["skala"]) for p in baca]
    dilihat = [k for i, k in enumerate(kunci_urut) if i == 0 or k != kunci_urut[i - 1]]
    assert dilihat == [(t, s) for t in KATEGORI_TES for s in (1, 2)]


def test_setiap_anggota_domain_p2_batas_jumlah_per_skala_dan_berbeda():
    for p in _domain():
        n = (p["n1"], p["n2"], p["n3"])
        assert p["skala"] in BATAS_SKALA and type(p["skala"]) is int
        terkecil, terbesar = BATAS_SKALA[p["skala"]]
        assert all(type(x) is int and terkecil <= x <= terbesar for x in n), p
        assert len(set(n)) == 3, p
    assert max(p["n1"] for p in _domain() if p["skala"] == 1) == 12
    assert min(min(p["n1"], p["n2"], p["n3"]) for p in _domain() if p["skala"] == 1) == 5
    assert min(min(p["n1"], p["n2"], p["n3"]) for p in _domain() if p["skala"] == 2) == 1
    assert max(max(p["n1"], p["n2"], p["n3"]) for p in _domain() if p["skala"] == 2) == 8


def test_semua_anggota_domain_p2_membentuk_soal_sah_dengan_parameter_sama():
    for p in _domain():
        soal = _soal(p)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert soal.kunci == soal.kunci.strip().lower() and " " not in soal.kunci


def test_kunci_angka_p2_bilangan_bulat_positif_paling_besar_tiga_puluh():
    angka = []
    for p in _domain():
        if p["varian"] == "terbanyak":
            continue
        kunci = _soal(p).kunci
        assert kunci.isdigit() and 1 <= int(kunci) <= 100, p
        angka.append(int(kunci))
    assert max(angka) == 30  # skala 2, jumlah (8 + 7) x 2


def test_sampler_p2_hanya_anggota_domain_dan_semua_skala_varian_muncul_pada_2000_sampel():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    skala, varian, tema = Counter(), Counter(), Counter()
    for seed in range(2000):
        p = modul.parameter(random.Random(seed), "P2")
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        skala[p["skala"]] += 1
        varian[p["varian"]] += 1
        tema[p["tema"]] += 1
    assert set(skala) == {1, 2} and set(varian) == set(VARIAN) and set(tema) == set(KATEGORI_TES)
    assert skala[1] >= 800 and skala[2] >= 800  # tiap skala setengah anggota domain (sekitar 50%)
    assert min(varian.values()) >= 400


def test_sampler_p2_satu_rng_berurutan_deterministik_dan_p1_bukan_p2():
    a = [modul.parameter(random.Random(7), "P2") for _ in range(3)]
    assert a[0] == a[1] == a[2]
    assert all("skala" in modul.parameter(random.Random(s), "P2") for s in range(50))
    assert all("skala" not in modul.parameter(random.Random(s), "P1") for s in range(50))


# ── kunci dan solver ─────────────────────────────────────────────────────

def test_seluruh_domain_p2_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)


def test_sapuan_seed_p2_kunci_sama_dengan_solver_teks():
    for seed in range(300):
        soal = _soal(modul.parameter(random.Random(seed), "P2"))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_kalimat_kepala_skala_dan_simbol_hanya_di_baris_data():
    skala_dua = _soal({"varian": "baca", "tema": "buah", "n1": 4, "n2": 1, "n3": 6,
                       "skala": 2, "tanya": 0})
    kepala = skala_dua.teks.split("\n")[0]
    assert kepala == "Diagram gambar buah di keranjang. Satu titik hitam mewakili 2 buah."
    skala_satu = _soal({"varian": "baca", "tema": "buah", "n1": 6, "n2": 5, "n3": 10,
                        "skala": 1, "tanya": 2})
    assert skala_satu.teks.split("\n")[0] == (
        "Diagram gambar buah di keranjang. Satu titik hitam mewakili 1 buah.")
    assert skala_satu.kunci == "10"


def test_kunci_contoh_tangan_skala_dua():
    f = modul.baca_diagram_gambar
    baca = f(varian="baca", tema="mainan", n1=3, n2=5, n3=2, tanya=1, skala=2)
    assert baca.kunci == "10"
    assert f(varian="terbanyak", tema="buah", n1=2, n2=7, n3=4, skala=2).kunci == "jeruk"
    selisih = f(varian="selisih", tema="hewan", n1=6, n2=1, n3=4, x=0, y=2, skala=2)
    assert selisih.kunci == "4" and selisih.teks.endswith("Ayam lebih banyak berapa daripada kelinci?")
    assert f(varian="jumlah", tema="mainan", n1=3, n2=5, n3=2, x=0, y=1, skala=2).kunci == "16"
    assert f(varian="jumlah", tema="mainan", n1=12, n2=11, n3=5, x=0, y=1, skala=1).kunci == "23"


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_p2_bukan_kunci_tidak_kembar_selalu_ada_jalur_k_dan_minimal_dua():
    for p in _domain():
        soal = _soal(p)
        kunci = diagnosis.normalisasi(soal.kunci)
        jawaban = [diagnosis.normalisasi(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert len(soal.malrule) >= 2, p
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert not any(TERLARANG.search(m.alasan) for m in soal.malrule)


def test_lupa_kali_skala_dua_sama_dengan_jumlah_titik_dan_bukan_kunci():
    jumlah_diperiksa = 0
    for p in _domain():
        if p["skala"] != 2 or p["varian"] == "terbanyak":
            continue
        soal = _soal(p)
        lupa = [m for m in soal.malrule if m.id == f"{TID}.lupa_kali_skala"]
        assert len(lupa) == 1, p
        assert lupa[0].kode == "K"
        assert lupa[0].jawaban == str(_titik_tanpa_skala(soal.teks, p["varian"])), p
        assert lupa[0].jawaban != soal.kunci
        jumlah_diperiksa += 1
    assert jumlah_diperiksa == 3 * 3024  # baca, selisih, jumlah pada skala 2


def test_lupa_kali_tidak_ada_pada_skala_satu_terbanyak_dan_p1():
    for p in _domain():
        if p["skala"] == 1 or p["varian"] == "terbanyak":
            ada = any(m.id.endswith("lupa_kali_skala") for m in _soal(p).malrule)
            assert not ada, p
    for p in modul.domain_parameter("P1")[::53]:
        assert not any(m.id.endswith("lupa_kali_skala")
                       for m in modul.baca_diagram_gambar(**p).malrule)


def test_salah_hitung_satu_titik_h_bergeser_sebesar_skala():
    for p in _domain():
        if p["varian"] == "terbanyak":
            continue
        soal = _soal(p)
        kunci = int(soal.kunci)
        h = {int(m.jawaban) for m in soal.malrule if m.kode == "H"}
        assert h <= {kunci - p["skala"], kunci + p["skala"]}, p
        assert all(x >= 1 for x in h), p


def _ada_atau_bentrok(k: dict, nama: str, nilai: str, lupa: str, p: dict) -> None:
    if nama in k:
        assert k[nama] == nilai, p
    else:
        assert nilai == lupa, (p, "malrule hilang tanpa bentrok")


def test_malrule_baris_lain_dan_operasi_terbalik_memakai_nilai_benda_p2():
    """Nilai benda (titik x 2); bila bentrok dengan lupa_kali, yang pertama (lupa_kali) menang."""
    for p in _domain():
        if p["skala"] != 2 or p["varian"] == "terbanyak":
            continue
        soal = _soal(p)
        titik = (p["n1"], p["n2"], p["n3"])
        k = {m.id.split(".")[1]: m.jawaban for m in soal.malrule if m.kode == "K"}
        lupa = k["lupa_kali_skala"]
        if p["varian"] == "baca":
            for urut, i in enumerate([i for i in range(3) if i != p["tanya"]], 1):
                nilai = str(titik[i] * 2)
                _ada_atau_bentrok(k, f"baris_lain_{urut}", nilai, lupa, p)
        else:
            a, b = titik[p["x"]], titik[p["y"]]
            nama, nilai = (("jumlah_bukan_selisih", (a + b) * 2) if p["varian"] == "selisih"
                           else ("selisih_bukan_jumlah", abs(a - b) * 2))
            _ada_atau_bentrok(k, nama, str(nilai), lupa, p)


def test_terbanyak_p2_malrule_sama_dengan_p1_hanya_k_dua_kategori_lain():
    for p in _domain():
        if p["varian"] != "terbanyak":
            continue
        soal = _soal(p)
        assert {m.kode for m in soal.malrule} == {"K"}
        assert {m.jawaban for m in soal.malrule} == set(KATEGORI_TES[p["tema"]]) - {soal.kunci}


def test_pembahasan_p2_bahasa_anak_memuat_kunci_dan_cara_kali_dua_pada_skala_dua():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40
        if p["skala"] == 2 and p["varian"] != "terbanyak":
            assert "× 2" in soal.pembahasan and "mewakili 2" in soal.pembahasan, soal.pembahasan
        if p["skala"] == 1:
            assert "×" not in soal.pembahasan


def test_pembahasan_skala_satu_p2_sama_dengan_p1_untuk_teks_yang_sama():
    p1 = modul.baca_diagram_gambar("selisih", "mainan", 8, 5, 6, x=0, y=1)
    p2 = modul.baca_diagram_gambar("selisih", "mainan", 8, 5, 6, x=0, y=1, skala=1)
    assert (p1.teks, p1.kunci, p1.pembahasan, p1.malrule) == (
        p2.teks, p2.kunci, p2.pembahasan, p2.malrule)
    assert "skala" in p2.parameter and "skala" not in p1.parameter


# ── penolakan parameter di luar domain ───────────────────────────────────

P2_BAIK = dict(varian="baca", tema="mainan", n1=3, n2=5, n3=2, tanya=1, skala=2)


@pytest.mark.parametrize("ubah", [
    dict(skala=0), dict(skala=3), dict(skala=-1), dict(skala=True), dict(skala=2.0),
    dict(skala="2"), dict(skala=[2]),
    dict(skala=2, n1=9), dict(skala=2, n2=12), dict(skala=1, n1=13), dict(skala=1, n3=0),
    dict(skala=1), dict(skala=1, n1=4, n2=6, n3=7), dict(skala=1, n1=1, n2=6, n3=7),
    dict(skala=1, n1=True), dict(skala=2, n2=5.0), dict(n1=5), dict(skala=1, n1=5),
    dict(varian="jumlah", x=1, y=0), dict(varian="selisih", x=0, y=1),
    dict(varian="terbanyak", tanya=1), dict(tanya=3),
])
def test_parameter_p2_tidak_sah_ditolak(ubah):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.baca_diagram_gambar(**{**P2_BAIK, **ubah})


def test_parameter_p2_sah_pembanding_diterima():
    for ubah in (dict(), dict(skala=1, n1=5, n2=6, n3=7), dict(skala=1, n1=12, n2=5, n3=7),
                 dict(skala=2, n1=8, n2=1, n3=2)):
        assert modul.baca_diagram_gambar(**{**P2_BAIK, **ubah}).kunci


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, sys
sys.path[:0] = json.loads(sys.argv[1])
import random
import awal_baca_diagram_gambar as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P2")
    s = m.baca_diagram_gambar(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan,
                  [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
d = m.domain_parameter("P2")
hasil.append([len(d), d[::131]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONHASHSEED"}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE, json.dumps(sys.path)],
                           env=env, capture_output=True, text=True, timeout=180)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_p2_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 151 and a[-1][0] == 20160

"""Matematika Awal, jenis pola_posisi (P2): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal: daftar kata (warna,
buah, nama anak, benda) ditulis ulang di tes ini, bukan diimpor dari modul. Solver
juga memeriksa ulang aturan domain dari teks (panjang barisan pola minimal dua
putaran penuh, nama yang disebut punya tetangga di dua sisi, dua kalimat letak
harus menentukan SATU urutan), jadi domain yang dilebarkan ke nilai tak sah merah.
Malrule hanya HIPOTESIS kesalahan umum yang ditinjau guru; yang dijaga di sini:
bukan kunci, tidak kembar, selalu ada jalur K, dan pengecoh pilihan ganda cukup.
Tes ini tidak bergantung pada pendaftaran topik: modul diimpor langsung.
"""
from __future__ import annotations

from itertools import permutations
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

AKAR_MESIN = Path(__file__).resolve().parents[1]
if str(AKAR_MESIN) not in sys.path:
    sys.path.insert(0, str(AKAR_MESIN))

import awal_pola_posisi as modul  # noqa: E402
import diagnosis  # noqa: E402
from templates import Soal  # noqa: E402

TID = "pola_posisi"
LEVEL = "P2"
SEED = range(200)
VARIAN = ("pola", "urutan", "kiri_kanan", "atas_bawah")
UKURAN_DOMAIN = {"P2": 124}
UKURAN_PER_VARIAN = {"pola": 40, "urutan": 24, "kiri_kanan": 36, "atas_bawah": 24}
MINIMAL_DOMAIN = 15
TERLARANG = re.compile(r"malrule|diagnosis|kode|template|kunci|hipotesis|guru", re.I)

# ── fakta ditulis ulang di tes (sumber independen) ───────────────────────

ITEM_POLA_TES = {
    "warna": {"merah", "biru", "kuning", "hijau", "putih", "ungu"},
    "buah": {"apel", "jeruk", "pisang", "mangga", "jambu", "semangka"},
}
NAMA_TES = {"rina", "budi", "dita", "eko", "sari", "tono", "wati", "andi",
            "maya", "joko", "lina", "rafi"}
BENDA_LETAK_TES = {
    "sebelah": {"bola", "kotak", "buku", "pensil", "penghapus", "penggaris",
                "apel", "jeruk", "pisang"},
    "tumpuk": {"topi", "kotak", "meja", "apel", "piring", "nampan"},
}
ANGKA_KATA = {"Empat": 4}
BENTUK_POLA_TES = {(0, 1): "AB", (0, 1, 2): "ABC", (0, 0, 1): "AAB"}


def _bentuk(unit: list) -> tuple:
    """Isyarat bentuk satu putaran: nomor kemunculan pertama tiap benda."""
    pertama = []
    for x in unit:
        if x not in pertama:
            pertama.append(x)
    return tuple(pertama.index(x) for x in unit)


def _periode_terkecil(daftar: list) -> int:
    for p in range(1, len(daftar)):
        if all(daftar[i] == daftar[i - p] for i in range(p, len(daftar))):
            return p
    return len(daftar)


def _solver_pola(teks: str) -> str:
    cocok = re.fullmatch(r"Perhatikan pola (\w+) berikut: (.+), \.\.\. (\w+) berikutnya apa\?", teks)
    assert cocok, ("bentuk teks pola tidak dikenal", teks)
    kategori, daftar = cocok.group(1), cocok.group(2).split(", ")
    assert cocok.group(3).lower() == kategori, ("kata tanya tak sama dengan kategori", teks)
    assert kategori in ITEM_POLA_TES and set(daftar) <= ITEM_POLA_TES[kategori], teks
    p = _periode_terkecil(daftar)
    assert p in (2, 3), ("periode harus 2 atau 3", teks, p)
    assert 5 <= len(daftar) <= 8, ("jumlah suku tampil di luar 5..8", teks)
    assert len(daftar) >= 2 * p, ("minimal dua putaran penuh agar tak ambigu", teks)
    assert _bentuk(daftar[:p]) in BENTUK_POLA_TES, ("bentuk putaran tak dikenal", teks)
    return daftar[len(daftar) - p]


def _solver_urutan(teks: str) -> str:
    cocok = re.fullmatch(
        r"(\w+) anak berbaris dalam satu barisan, dari depan ke belakang: (.+)\. (Siapa .+)\?", teks)
    assert cocok, ("bentuk teks urutan tidak dikenal", teks)
    nama = [x.lower() for x in cocok.group(2).split(", ")]
    assert ANGKA_KATA[cocok.group(1)] == len(nama) == 4, teks
    assert len(set(nama)) == len(nama) and set(nama) <= NAMA_TES, teks
    tanya = cocok.group(3)
    for pola, geser in ((r"Siapa yang berdiri tepat di belakang (\w+)", 1),
                        (r"Siapa yang berdiri tepat di depan (\w+)", -1)):
        c = re.fullmatch(pola, tanya)
        if c:
            idx = nama.index(c.group(1).lower())
            assert 0 < idx < len(nama) - 1, ("sasaran harus punya tetangga dua sisi", teks)
            return nama[idx + geser]
    c = re.fullmatch(r"Siapa yang berdiri di urutan ke-(\d) dari depan", tanya)
    assert c, ("pertanyaan urutan tak dikenal", teks)
    n = int(c.group(1))
    assert 1 <= n <= len(nama), teks
    return nama[n - 1]


def _solver_letak(teks: str) -> str:
    kalimat = re.findall(r"([A-Z]\w+) ada di (?:sebelah )?(kiri|kanan|atas|bawah) (\w+)\.", teks)
    assert len(kalimat) == 2, ("harus tepat dua kalimat letak", teks)
    tanya = re.search(r"(Benda apa yang (?:paling (kiri|kanan|atas|bawah)|ada di tengah)\?)$", teks)
    assert tanya, ("pertanyaan letak tak dikenal", teks)
    sumbu = "sebelah" if any(k[1] in ("kiri", "kanan") for k in kalimat) else "tumpuk"
    awal, akhir = ("kiri", "kanan") if sumbu == "sebelah" else ("atas", "bawah")
    assert all(k[1] in (awal, akhir) for k in kalimat), ("dua sumbu bercampur", teks)
    assert tanya.group(2) in (None, awal, akhir), ("sumbu pertanyaan beda dari kalimat", teks)
    # "sebelah" hanya dipakai untuk kiri/kanan, tidak untuk atas/bawah.
    assert ("sebelah" in teks) == (sumbu == "sebelah"), teks
    benda = sorted({a.lower() for a, _, _ in kalimat} | {c for _, _, c in kalimat})
    assert len(benda) == 3 and set(benda) <= BENDA_LETAK_TES[sumbu], (teks, benda)
    sebelum = {(a.lower(), c) if b == awal else (c, a.lower()) for a, b, c in kalimat}
    urutan = [p for p in permutations(benda)
              if all(p.index(x) < p.index(y) for x, y in sebelum)]
    assert len(urutan) == 1, ("dua kalimat harus menentukan SATU urutan", teks, urutan)
    tepat = urutan[0]
    kata = tanya.group(2)
    if kata is None:
        return tepat[1]
    return tepat[0] if kata == awal else tepat[2]


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; sengaja tidak memakai parameter atau tabel modul."""
    if teks.startswith("Perhatikan pola"):
        return _solver_pola(teks)
    if " anak berbaris" in teks:
        return _solver_urutan(teks)
    return _solver_letak(teks)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(p: dict) -> Soal:
    return modul.pola_posisi(**p)


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


def _per_varian(varian: str) -> list:
    return [p for p in _domain() if p["varian"] == varian]


# ── modul, domain, sampler ───────────────────────────────────────────────

def test_kontrak_modul():
    assert modul.TEMPLATE_ID == TID
    assert modul.LEVEL == ("P2",)
    assert callable(modul.pola_posisi) and callable(modul.parameter)
    assert callable(modul.domain_parameter) and callable(modul.pengecoh_tambahan)


def test_domain_eksplisit_unik_skalar_dan_cukup_besar():
    domain = _domain()
    assert len(domain) == UKURAN_DOMAIN[LEVEL]
    assert len(domain) >= MINIMAL_DOMAIN
    assert len({json.dumps(p, sort_keys=True) for p in domain}) == len(domain), "domain berisi duplikat"
    for p in domain:
        assert all(type(v) in (str, int) for v in p.values()), p
        assert json.loads(json.dumps(p)) == p
    assert {p["varian"] for p in domain} == set(VARIAN)
    for varian, ukuran in UKURAN_PER_VARIAN.items():
        assert len(_per_varian(varian)) == ukuran, varian
    # dict baru tiap panggilan: pemanggil tidak boleh bisa menodai domain
    _domain()[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"


def test_domain_mencakup_semua_cabang():
    ragam = {(p["ragam"], p["tampil"]) for p in _per_varian("pola")}
    assert {r for r, _ in ragam} == {"AB", "ABC", "AAB"}
    assert {t for r, t in ragam if r == "AB"} == {5, 6, 7, 8}
    assert {t for r, t in ragam if r != "AB"} == {6, 7, 8}
    tanya = {p["tanya"] for p in _per_varian("urutan")}
    assert tanya == {"belakang", "depan", "ke_n"}
    assert {p["n"] for p in _per_varian("urutan") if p["tanya"] == "ke_n"} == {1, 2, 3, 4}
    assert {p["orang"] for p in _per_varian("urutan") if p["tanya"] != "ke_n"} == {1, 2}
    assert {p["tanya"] for p in _per_varian("kiri_kanan")} == {"paling_kiri", "paling_kanan", "tengah"}
    assert {p["tanya"] for p in _per_varian("atas_bawah")} == {"paling_atas", "paling_bawah", "tengah"}
    for varian in ("kiri_kanan", "atas_bawah"):
        assert {p["bentuk"] for p in _per_varian(varian)} == {0, 1, 2, 3}


def test_domain_hanya_level_p2():
    for level in ("P1", "P3", "P6", "", None, "p2"):
        with pytest.raises(ValueError, match="level"):
            modul.domain_parameter(level)
        with pytest.raises(ValueError, match="level"):
            modul.parameter(random.Random(0), level)


def test_sampel_seed_selalu_di_domain_dan_menutup_domain():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    terambil = set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        terambil.add(json.dumps(p, sort_keys=True))
    for seed in range(200, 1500):
        terambil.add(json.dumps(modul.parameter(random.Random(seed), LEVEL), sort_keys=True))
    assert len(terambil) >= 0.95 * len(kanon), (len(terambil), len(kanon))


def test_sampler_sama_untuk_seed_sama_dan_tidak_menodai_domain():
    a = modul.parameter(random.Random(7), LEVEL)
    b = modul.parameter(random.Random(7), LEVEL)
    assert a == b
    a["varian"] = "rusak"
    assert modul.parameter(random.Random(7), LEVEL)["varian"] != "rusak"


# ── kunci, solver ────────────────────────────────────────────────────────

def test_seluruh_domain_menghasilkan_soal_sah_dengan_kunci_solver():
    for p in _domain():
        soal = _soal(p)
        assert isinstance(soal, Soal) and soal.template_id == TID and soal.bagian == "A"
        assert soal.parameter == p
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.kunci == soal.kunci.strip().lower() and " " not in soal.kunci
        assert re.fullmatch(r"[a-z]+", soal.kunci)
        assert "\n" not in soal.teks and soal.teks.endswith("?")


def test_tanda_tangan_unik_di_seluruh_domain():
    tanda = [_soal(p).teks + "|" + json.dumps(p, sort_keys=True) for p in _domain()]
    assert len(set(tanda)) == len(tanda)
    teks = [_soal(p).teks for p in _domain()]
    assert len(set(teks)) == len(teks), "dua parameter berbeda menghasilkan teks yang sama"


def test_kunci_contoh_tangan():
    f = modul.pola_posisi
    soal = f(varian="pola", kategori="warna", isi=0, ragam="AB", tampil=5)
    assert soal.teks == "Perhatikan pola warna berikut: merah, biru, merah, biru, merah, ... Warna berikutnya apa?"
    assert soal.kunci == "biru"
    soal = f(varian="pola", kategori="buah", isi=0, ragam="ABC", tampil=7)
    assert soal.teks == ("Perhatikan pola buah berikut: apel, jeruk, pisang, apel, jeruk, pisang, apel, ... "
                         "Buah berikutnya apa?")
    assert soal.kunci == "jeruk"
    soal = f(varian="pola", kategori="warna", isi=1, ragam="AAB", tampil=6)
    assert soal.kunci == "hijau" and soal.teks.count("hijau") == 4
    soal = f(varian="urutan", antrean=0, tanya="belakang", orang=1)
    assert soal.teks == ("Empat anak berbaris dalam satu barisan, dari depan ke belakang: "
                         "Rina, Budi, Dita, Eko. Siapa yang berdiri tepat di belakang Budi?")
    assert soal.kunci == "dita"
    assert f(varian="urutan", antrean=0, tanya="depan", orang=2).kunci == "budi"
    assert f(varian="urutan", antrean=1, tanya="ke_n", n=4).kunci == "andi"
    soal = f(varian="kiri_kanan", himpunan=0, bentuk=0, tanya="paling_kiri")
    assert soal.teks == ("Bola ada di sebelah kiri kotak. Kotak ada di sebelah kiri buku. "
                         "Benda apa yang paling kiri?")
    assert soal.kunci == "bola"
    assert f(varian="kiri_kanan", himpunan=0, bentuk=2, tanya="paling_kanan").kunci == "buku"
    assert f(varian="atas_bawah", himpunan=0, bentuk=1, tanya="tengah").kunci == "kotak"
    assert f(varian="atas_bawah", himpunan=1, bentuk=3, tanya="paling_bawah").kunci == "nampan"


def test_kalimat_letak_bentuk_berbeda_menghasilkan_urutan_sama():
    kunci = {_soal(dict(varian="kiri_kanan", himpunan=1, bentuk=b, tanya="paling_kiri")).kunci
             for b in range(4)}
    assert kunci == {"pensil"}
    teks = {_soal(dict(varian="kiri_kanan", himpunan=1, bentuk=b, tanya="tengah")).teks
            for b in range(4)}
    assert len(teks) == 4


# ── malrule dan pilihan ganda ────────────────────────────────────────────

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
        assert all(m.alasan.endswith(".") for m in soal.malrule)


def test_pengecoh_pilihan_ganda_cukup_dan_bukan_kunci():
    for p in _domain():
        soal = _soal(p)
        nilai = [m.jawaban for m in soal.malrule] + list(modul.pengecoh_tambahan(p))
        bersih = []
        for x in nilai:
            if _norm(x) != _norm(soal.kunci) and _norm(x) not in map(_norm, bersih):
                bersih.append(x)
        assert len(bersih) >= 2, (p, bersih)
        assert all(re.fullmatch(r"[a-z]+", x) for x in bersih), (p, bersih)


def test_pengecoh_tambahan_adalah_benda_yang_nyata():
    for p in _domain():
        tambahan = modul.pengecoh_tambahan(p)
        assert isinstance(tambahan, tuple) and len(set(tambahan)) == len(tambahan)
        teks = _soal(p).teks.lower()
        if p["varian"] == "pola":
            assert set(tambahan) <= ITEM_POLA_TES[p["kategori"]]
            assert len(tambahan) == 3
        else:
            assert all(x in teks for x in tambahan), (p, tambahan)


def test_malrule_urutan_menyebut_tetangga_yang_salah_arah():
    for p in _per_varian("urutan"):
        soal = _soal(p)
        antrean = [x.lower() for x in re.search(r"belakang: (.+)\. Siapa", soal.teks).group(1).split(", ")]
        jawaban = {m.jawaban: m for m in soal.malrule}
        if p["tanya"] == "belakang":
            assert antrean[p["orang"] - 1] in jawaban and jawaban[antrean[p["orang"] - 1]].kode == "K"
        elif p["tanya"] == "depan":
            assert antrean[p["orang"] + 1] in jawaban and jawaban[antrean[p["orang"] + 1]].kode == "K"
        else:
            dari_belakang = antrean[len(antrean) - p["n"]]
            assert dari_belakang in jawaban and jawaban[dari_belakang].kode == "K"


def test_malrule_letak_menukar_kiri_kanan_atau_menyebut_benda_lain():
    for varian, ujung in (("kiri_kanan", ("paling_kiri", "paling_kanan")),
                          ("atas_bawah", ("paling_atas", "paling_bawah"))):
        for p in _per_varian(varian):
            soal = _soal(p)
            lawan = {ujung[0]: _soal({**p, "tanya": ujung[1]}).kunci,
                     ujung[1]: _soal({**p, "tanya": ujung[0]}).kunci}
            jawaban = {m.jawaban: m for m in soal.malrule}
            if p["tanya"] in lawan:
                assert lawan[p["tanya"]] in jawaban, p
                assert jawaban[lawan[p["tanya"]]].kode == "K"
            else:
                assert {_soal({**p, "tanya": u}).kunci for u in ujung} <= set(jawaban), p
            assert {m.kode for m in soal.malrule} == {"K"}


def test_malrule_pola_mencakup_mengulang_suku_terakhir_bila_berbeda():
    for p in _per_varian("pola"):
        soal = _soal(p)
        terakhir = re.search(r", (\w+), \.\.\.", soal.teks).group(1)
        jawaban = {m.jawaban for m in soal.malrule}
        if terakhir != soal.kunci:
            assert terakhir in jawaban, (p, soal.teks)
        assert jawaban <= ITEM_POLA_TES[p["kategori"]]


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_tanpa_istilah_guru_dan_memuat_jawaban():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert re.search(r"\b%s\b" % soal.kunci, soal.pembahasan.lower()), (p, soal.pembahasan)
        assert soal.pembahasan.strip().lower() != soal.kunci
        assert len(soal.pembahasan) > 40
        assert "Cocokkan dengan caramu" not in soal.pembahasan


def test_pembahasan_membedakan_soal_dan_tidak_menyebut_nama_anak_nyata():
    teks = {_soal(p).pembahasan for p in _domain()}
    assert len(teks) > 60
    kata = set(re.findall(r"[A-Z][a-z]+", " ".join(_soal(p).teks for p in _domain())))
    kata -= {"Perhatikan", "Warna", "Buah", "Empat", "Siapa", "Benda", "Bola", "Kotak", "Buku",
             "Pensil", "Penghapus", "Penggaris", "Apel", "Jeruk", "Pisang", "Topi", "Meja",
             "Piring", "Nampan"}
    assert {x.lower() for x in kata} <= NAMA_TES


# ── penolakan parameter di luar domain ───────────────────────────────────

_POLA = dict(varian="pola", kategori="warna", isi=0, ragam="AB", tampil=5)
_URUT = dict(varian="urutan", antrean=0, tanya="belakang", orang=1)
_KEN = dict(varian="urutan", antrean=0, tanya="ke_n", n=2)
_LKK = dict(varian="kiri_kanan", himpunan=0, bentuk=0, tanya="paling_kiri")
_LAB = dict(varian="atas_bawah", himpunan=0, bentuk=0, tanya="paling_atas")


def _ubah(dasar: dict, **perubahan) -> dict:
    hasil = {**dasar, **perubahan}
    return {k: v for k, v in hasil.items() if v is not ...}


@pytest.mark.parametrize("parameter", [
    _ubah(_POLA, tampil=4), _ubah(_POLA, tampil=9),
    _ubah(_POLA, ragam="ABC", tampil=5),          # kurang dari dua putaran penuh
    _ubah(_POLA, ragam="AAB", tampil=5),
    _ubah(_POLA, ragam="ABB"), _ubah(_POLA, ragam="A"), _ubah(_POLA, ragam=None),
    _ubah(_POLA, kategori="hewan"), _ubah(_POLA, kategori=["warna"]),
    _ubah(_POLA, isi=2), _ubah(_POLA, isi=-1), _ubah(_POLA, isi="0"), _ubah(_POLA, isi=True),
    _ubah(_POLA, tampil="5"), _ubah(_POLA, tampil=5.0), _ubah(_POLA, tampil=True),
    _ubah(_POLA, tampil=...), _ubah(_POLA, kategori=...), _ubah(_POLA, extra=1),
    _ubah(_URUT, orang=0), _ubah(_URUT, orang=3), _ubah(_URUT, orang=-1), _ubah(_URUT, orang=1.0),
    _ubah(_URUT, antrean=3), _ubah(_URUT, antrean=-1), _ubah(_URUT, tanya="samping"),
    _ubah(_URUT, orang=...), _ubah(_URUT, n=1), _ubah(_URUT, tanya="depan", orang=3),
    _ubah(_KEN, n=0), _ubah(_KEN, n=5), _ubah(_KEN, n="2"), _ubah(_KEN, n=...),
    _ubah(_KEN, orang=1), _ubah(_KEN, antrean=9),
    _ubah(_LKK, bentuk=4), _ubah(_LKK, bentuk=-1), _ubah(_LKK, bentuk="0"),
    _ubah(_LKK, himpunan=3), _ubah(_LKK, himpunan=-1),
    _ubah(_LKK, tanya="paling_atas"), _ubah(_LKK, tanya="tengah "), _ubah(_LKK, tanya=...),
    _ubah(_LAB, himpunan=2), _ubah(_LAB, tanya="paling_kiri"), _ubah(_LAB, bentuk=7),
    dict(varian="tidak_ada"), dict(varian=None), dict(varian=["pola"]),
])
def test_parameter_tidak_sah_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pola_posisi(**parameter)


def test_parameter_sah_tidak_ditolak():
    for dasar in (_POLA, _URUT, _KEN, _LKK, _LAB):
        assert isinstance(modul.pola_posisi(**dasar), Soal)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
import awal_pola_posisi as m
def ringkas(p):
    s = m.pola_posisi(**p)
    return [p, s.teks, s.kunci, s.pembahasan,
            [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule],
            list(m.pengecoh_tambahan(p))]
hasil = [ringkas(m.parameter(random.Random(seed), "P2")) for seed in range(80)]
hasil += [ringkas(p) for p in m.domain_parameter("P2")]
print(json.dumps(hasil))
"""


def _proses(hash_seed: str):
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    hasil = subprocess.run([sys.executable, "-c", _KODE % {"akar": str(AKAR_MESIN)}],
                           env=env, capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 80 + UKURAN_DOMAIN[LEVEL]
    # hasil proses lain sama dengan hasil proses ini
    domain_ini = [[p, _soal(p).teks, _soal(p).kunci] for p in _domain()]
    assert [x[:3] for x in a[80:]] == json.loads(json.dumps(domain_ini))

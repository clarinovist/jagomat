"""Tes mesin cetakan soal berpola (C1): skema, evaluator AST terbatas, bangkitan, kelayakan.

Semua data sintetis. Kunci jawaban dicek dengan hitungan independen di tes (bukan memakai
evaluator yang diuji).
"""
from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path
import subprocess
import sys

import pytest

MESIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MESIN))

import cetakan_pola as cp  # noqa: E402


def dasar(**ubah):
    """Cetakan sah (kelas 2 bab 2); `ubah` menimpa, nilai `...` menghapus bidang."""
    isi = {
        "kelas": 2, "bab": 2, "judul": "Penjumlahan dua angka dalam soal cerita",
        "teks": "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa kelereng {nama} sekarang?",
        "variabel": {"a": [10, 50], "b": [1, 40]}, "nama": True,
        "syarat": ["a + b <= 99"], "kunci": "a + b", "pembahasan": "{a} + {b} = {kunci}",
    }
    for kunci, nilai in ubah.items():
        if nilai is ...:
            del isi[kunci]
        else:
            isi[kunci] = nilai
    return isi


def sederhana(kunci="a + b", syarat=(), variabel=None, teks="{a} dan {b}", **lain):
    """Cetakan ringkas tanpa nama untuk uji evaluator."""
    return cp.validasi(dasar(
        kunci=kunci, syarat=list(syarat), teks=teks, nama=False, pembahasan="",
        variabel=variabel or {"a": [1, 50], "b": [1, 40]}, **lain))


# --- skema -------------------------------------------------------------------

def test_cetakan_sah_dinormalkan_dan_variabel_terurut():
    c = cp.validasi(dasar(judul="  Judul  ", variabel={"b": [1, 40], "a": [10, 50]}))
    assert c.judul == "Judul"
    assert c.variabel == (("a", 10, 50), ("b", 1, 40))
    assert c.syarat == ("a + b <= 99",) and c.nama is True


def test_bidang_opsional_punya_bawaan():
    c = cp.validasi(dasar(nama=..., syarat=..., pembahasan=..., teks="{a} {b}"))
    assert c.nama is False and c.syarat == () and c.pembahasan == ""


def test_urutan_kunci_json_tidak_mengubah_cetakan():
    a = dasar()
    b = dict(reversed(list(a.items())))
    b["variabel"] = dict(reversed(list(a["variabel"].items())))
    assert cp.validasi(a) == cp.validasi(b)
    assert cp.validasi(a) == cp.validasi(a)


def test_ke_dict_dan_json_pulang_pergi_sama():
    c = cp.validasi(dasar())
    assert cp.validasi(cp.ke_dict(c)) == c
    assert cp.dari_json(cp.ke_json(c)) == c
    assert cp.ke_json(c) == cp.ke_json(cp.dari_json(cp.ke_json(c)))


def test_cetakan_beku_dan_bisa_di_hash():
    c = cp.validasi(dasar())
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.kelas = 3
    assert isinstance(hash(c), int)


@pytest.mark.parametrize("bidang", ["kelas", "bab", "judul", "teks", "variabel", "kunci"])
def test_bidang_wajib_kurang_ditolak_dan_disebut(bidang):
    with pytest.raises(ValueError, match=bidang):
        cp.validasi(dasar(**{bidang: ...}))


def test_bidang_asing_ditolak():
    with pytest.raises(ValueError, match="kode"):
        cp.validasi(dasar(kode="x"))


@pytest.mark.parametrize("nilai", [None, [], "teks", 5])
def test_bukan_objek_ditolak(nilai):
    with pytest.raises(ValueError, match="objek"):
        cp.validasi(nilai)


@pytest.mark.parametrize("kelas", [0, 7, "2", True, 2.0, None, -1])
def test_kelas_tak_sah(kelas):
    with pytest.raises(ValueError, match="kelas"):
        cp.validasi(dasar(kelas=kelas))


@pytest.mark.parametrize("kelas,bab", [(2, 99), (2, 0), (1, "2"), (2, True), (2, 2.0)])
def test_bab_tak_ada_di_kelas_ditolak(kelas, bab):
    with pytest.raises(ValueError, match="bab"):
        cp.validasi(dasar(kelas=kelas, bab=bab))


@pytest.mark.parametrize("judul", ["", "   ", "x" * 81, "a<b", "a>b", 5, None, "satu\ndua", "a\x00b"])
def test_judul_tak_sah(judul):
    with pytest.raises(ValueError, match="judul"):
        cp.validasi(dasar(judul=judul))


@pytest.mark.parametrize("teks", ["", "  ", "x" * 301, "{a} {b} <b>", "{a} {b} >", 5, None, "{a}\n{b}"])
def test_teks_tak_sah(teks):
    with pytest.raises(ValueError, match="teks"):
        cp.validasi(dasar(teks=teks))


@pytest.mark.parametrize("pembahasan", ["x" * 301, "<i>", 5, None])
def test_pembahasan_tak_sah(pembahasan):
    with pytest.raises(ValueError, match="pembahasan"):
        cp.validasi(dasar(pembahasan=pembahasan))


def test_batas_panjang_tepat_masih_sah():
    cp.validasi(dasar(judul="x" * 80, teks="{nama} {a} {b} " + "x" * 285,
                      pembahasan="y" * 300))
    with pytest.raises(ValueError, match="teks"):
        cp.validasi(dasar(teks="{nama} {a} {b} " + "x" * 286))


@pytest.mark.parametrize("variabel", [
    {}, [], None, "a",
    {c: [1, 2] for c in "abcde"},          # lima variabel
    {"A": [1, 2]}, {"ab": [1, 2]}, {"1": [1, 2]}, {"": [1, 2]}, {1: [1, 2]},
    {"a": [1]}, {"a": [1, 2, 3]}, {"a": "12"}, {"a": [1.0, 2]}, {"a": [True, 2]},
    {"a": [5, 4]}, {"a": [-1, 4]}, {"a": [0, 1_000_001]}, {"a": None},
])
def test_variabel_tak_sah(variabel):
    with pytest.raises(ValueError, match="variabel"):
        cp.validasi(dasar(variabel=variabel, teks="{a}", syarat=[], kunci="a"))


def test_variabel_batas_sah():
    c = cp.validasi(dasar(variabel={"a": [0, 0], "b": [0, 1_000_000], "c": [5, 5], "d": [1, 2]},
                          teks="{a}{b}{c}{d}", kunci="a", syarat=[]))
    assert len(c.variabel) == 4


@pytest.mark.parametrize("nama", [1, "true", None, 0])
def test_nama_harus_bool(nama):
    with pytest.raises(ValueError, match="nama"):
        cp.validasi(dasar(nama=nama))


@pytest.mark.parametrize("syarat", ["a < b", None, 5, ["a < b"] * 6, [5], [None]])
def test_syarat_tak_sah(syarat):
    with pytest.raises(ValueError, match="syarat"):
        cp.validasi(dasar(syarat=syarat))


def test_lima_syarat_masih_sah():
    assert len(cp.validasi(dasar(syarat=["a < 100"] * 5)).syarat) == 5


@pytest.mark.parametrize("kunci", [5, None, "", "   ", ["a"]])
def test_kunci_harus_teks_tak_kosong(kunci):
    with pytest.raises(ValueError, match="kunci"):
        cp.validasi(dasar(kunci=kunci))


# --- placeholder -------------------------------------------------------------

@pytest.mark.parametrize("teks", [
    "{a} {b} {z}", "{a} {b} {kunci}", "{a} {b} {A}", "{a} {b} {}", "{a} {b} {",
    "{a} {b} }", "{a} {b} {a.__class__}", "{a} {b} {a[0]}", "{a} {b} {a!r}",
    "{a} {b} {a:>99}", "{a} {b} {{a}}", "{a} {b} {nama}x{ nama}",
])
def test_placeholder_tak_terdaftar_atau_rusak_ditolak(teks):
    with pytest.raises(ValueError, match="teks"):
        cp.validasi(dasar(teks=teks, nama=False))


def test_nama_di_teks_hanya_bila_nama_true():
    with pytest.raises(ValueError, match="teks"):
        cp.validasi(dasar(nama=False))
    cp.validasi(dasar(nama=True))


def test_variabel_harus_muncul_di_teks():
    with pytest.raises(ValueError, match="variabel b"):
        cp.validasi(dasar(teks="{nama} punya {a} kelereng."))


@pytest.mark.parametrize("pembahasan", ["{z}", "{a.__class__}", "{", "}", "{b!r}", "{nama} {nama2}"])
def test_pembahasan_placeholder_tak_sah(pembahasan):
    with pytest.raises(ValueError, match="pembahasan"):
        cp.validasi(dasar(pembahasan=pembahasan))


def test_pembahasan_nama_ditolak_bila_nama_false():
    with pytest.raises(ValueError, match="pembahasan"):
        cp.validasi(dasar(nama=False, teks="{a} {b}", pembahasan="{nama}"))


# --- evaluator: daftar serangan ----------------------------------------------

SERANGAN = [
    "__import__('os')", "a.__class__", "(lambda: 1)()", "a**99999", "9**9**9", "a/b",
    "'x'*9", "[a]", "a if a else b", "abs(a)", "True", "False", "None", "1.5", "a[0]",
    "f'{a}'", "zz", "c", "a < b", "a == b", "a and b", "a or b", "not a", "~a", "+a", "a << 2",
    "a & b", "a | b", "a ^ b", "a @ b", "(a, b)", "{a}", "{a: b}", "[a for a in b]",
    "a.b", "b'x'", "1_000_001", "10**2", "-1.0", "a if True else 2", "(a := 1)", "a,", "...",
    "min(a, b)", "a.real", "(a)(b)", "a[1:2]", "-(a < b)", "a + (b < a)",
]


@pytest.mark.parametrize("ekspresi", SERANGAN)
def test_serangan_ditolak_sebagai_kunci(ekspresi):
    with pytest.raises(ValueError):
        cp.validasi(dasar(kunci=ekspresi, syarat=[], nama=False, teks="{a} {b}", pembahasan=""))


@pytest.mark.parametrize("ekspresi", SERANGAN)
def test_serangan_ditolak_sebagai_syarat(ekspresi):
    with pytest.raises(ValueError):
        cp.validasi(dasar(syarat=[f"({ekspresi}) > 0"], nama=False, teks="{a} {b}", pembahasan=""))
    if ekspresi in ("a < b", "a == b"):
        return  # perbandingan murni memang syarat yang sah
    with pytest.raises(ValueError):
        cp.validasi(dasar(syarat=[ekspresi], nama=False, teks="{a} {b}", pembahasan=""))


@pytest.mark.parametrize("syarat", ["a", "a + b", "1", "1 < 2 and a", "a < b or b", "not a < b",
                                    "(a < b) < c", "a < (b == 1)", "a + b > c"])
def test_syarat_harus_boolean_bertipe(syarat):
    with pytest.raises(ValueError):
        cp.validasi(dasar(syarat=[syarat], nama=False, teks="{a} {b}", pembahasan="",
                          variabel={"a": [1, 5], "b": [1, 5]}))


def test_compare_dan_boolop_hanya_di_syarat():
    cp.validasi(dasar(syarat=["a < b < 50", "a >= 1 and b != 3 or a == 7"]))
    for kunci in ("a < b", "a and b", "a + (b < 3)"):
        with pytest.raises(ValueError, match="kunci"):
            cp.validasi(dasar(kunci=kunci))


@pytest.mark.parametrize("ekspresi", ["a +", "(", "a b", "", "  ", "a\n+\nb", "#", "a;b", "1 +* 2", "\x00"])
def test_ekspresi_bukan_sintaks_sah_ditolak(ekspresi):
    with pytest.raises(ValueError):
        cp.validasi(dasar(kunci=ekspresi))


def test_batas_panjang_ekspresi_120_sah_121_ditolak():
    sah = "a" + " " * 116 + "+ b"
    assert len(sah) == 120
    cp.validasi(dasar(kunci=sah))
    lewat = "a" + " " * 117 + "+ b"
    assert len(lewat) == 121
    with pytest.raises(ValueError, match="maksimal 120"):
        cp.validasi(dasar(kunci=lewat))


def test_batas_jumlah_node_40_sah_41_ditolak():
    sah = "-a" + "+1" * 19   # Name + USub + 19 konstanta + 19 BinOp = 40 node
    lewat = "a" + "+1" * 20  # Name + 20 konstanta + 20 BinOp = 41 node, hanya 41 karakter
    assert len(sah) <= 120 and len(lewat) <= 120
    cp.validasi(dasar(kunci=sah))
    with pytest.raises(ValueError, match="maksimal 40 node"):
        cp.validasi(dasar(kunci=lewat))
    with pytest.raises(ValueError, match="maksimal 40 node"):
        cp.validasi(dasar(syarat=["a" + "+1" * 20 + " > 0"]))


def test_konstanta_batas_1_juta():
    cp.validasi(dasar(kunci="a + 1000000"))
    with pytest.raises(ValueError, match="kunci"):
        cp.validasi(dasar(kunci="a + 1000001"))


def test_kurung_tak_seimbang_sangat_dalam_ditolak_tanpa_crash():
    with pytest.raises(ValueError):
        cp.validasi(dasar(kunci="(" * 119))


def test_tanpa_eval_exec_compile_atau_format_di_modul():
    pohon = ast.parse((MESIN / "cetakan_pola.py").read_text(encoding="utf-8"))
    terlarang = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(pohon):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in terlarang
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr != "format"


# --- bangkitan ---------------------------------------------------------------

def test_kunci_sama_dengan_rumus_untuk_parameter_tercatat():
    c = cp.validasi(dasar())
    for seed in range(1, 80):
        soal = cp.buat_soal(c, seed)
        a, b = soal.parameter["a"], soal.parameter["b"]
        assert 10 <= a <= 50 and 1 <= b <= 40
        assert a + b <= 99                      # syarat terpenuhi
        assert soal.kunci == str(a + b)         # hitungan independen
        assert soal.pembahasan == f"{a} + {b} = {a + b}"
        assert f"{a} kelereng" in soal.teks and "{" not in soal.teks


def test_semua_operator_cocok_dengan_python_biasa():
    kasus = {
        "a * b + 3": lambda p: p["a"] * p["b"] + 3,
        "a - b": lambda p: p["a"] - p["b"],
        "(a + b) * 2 - 1": lambda p: (p["a"] + p["b"]) * 2 - 1,
        "a % b": lambda p: p["a"] % p["b"],
        "-b + a + 5": lambda p: -p["b"] + p["a"] + 5,
    }
    for ekspresi, rumus in kasus.items():
        c = sederhana(kunci=ekspresi, syarat=["a >= b + 5"] if "-" in ekspresi else [])
        for seed in range(1, 40):
            soal = cp.buat_soal(c, seed)
            assert soal.kunci == str(rumus(soal.parameter)), ekspresi


def test_pembagian_selalu_habis_dan_kunci_bulat_tepat():
    c = sederhana(kunci="a // b", variabel={"a": [1, 100], "b": [1, 10]})
    habis_dari_sampel_tak_habis = 0
    for seed in range(1, 150):
        soal = cp.buat_soal(c, seed)
        a, b = soal.parameter["a"], soal.parameter["b"]
        assert int(soal.kunci) * b == a          # tepat, bukan hasil pembulatan
        habis_dari_sampel_tak_habis += 1
    assert habis_dari_sampel_tak_habis == 149


def test_pembagian_tak_habis_diundi_ulang_bukan_dibulatkan():
    # Hampir semua pasangan (a, b) di sini tak habis; semuanya harus terundi ulang.
    c = sederhana(kunci="a // b", variabel={"a": [1, 97], "b": [2, 11]})
    sisa = {cp.buat_soal(c, seed).parameter["a"] % cp.buat_soal(c, seed).parameter["b"]
            for seed in range(1, 100)}
    assert sisa == {0}


def test_pembagi_nol_tak_pernah_menjadi_soal():
    for kunci in ("a // b", "a % b"):
        c = sederhana(kunci=kunci, variabel={"a": [1, 50], "b": [0, 2]})
        for seed in range(1, 60):
            soal = cp.buat_soal(c, seed)
            assert soal.parameter["b"] != 0


def test_operan_negatif_pada_bagi_dan_sisa_diundi_ulang():
    for kunci in ("(a - b) % 5", "(a - b) // 2"):
        c = sederhana(kunci=kunci, variabel={"a": [1, 50], "b": [1, 50]})
        for seed in range(1, 80):
            soal = cp.buat_soal(c, seed)
            assert soal.parameter["a"] >= soal.parameter["b"], kunci   # tak ada operan negatif
            assert int(soal.kunci) >= 0


def test_pembagi_selalu_nol_menjadi_syarat_terlalu_ketat():
    c = sederhana(kunci="a // b", variabel={"a": [1, 50], "b": [0, 0]})
    with pytest.raises(ValueError, match="syarat terlalu ketat"):
        cp.buat_soal(c, 1)


def test_nilai_antara_di_atas_10_pangkat_12_ditolak():
    selalu = sederhana(kunci="a * b * 2", variabel={"a": [1_000_000, 1_000_000], "b": [1_000_000, 1_000_000]})
    with pytest.raises(ValueError, match="syarat terlalu ketat"):
        cp.buat_soal(selalu, 1)
    batas = sederhana(kunci="a * b", variabel={"a": [1_000_000, 1_000_000], "b": [1_000_000, 1_000_000]})
    assert cp.buat_soal(batas, 1).kunci == str(10 ** 12)
    lewat = sederhana(kunci="a * b + 1", variabel={"a": [1_000_000, 1_000_000], "b": [1_000_000, 1_000_000]})
    with pytest.raises(ValueError, match="syarat terlalu ketat"):
        cp.buat_soal(lewat, 1)


def test_syarat_mustahil_menjadi_syarat_terlalu_ketat():
    c = sederhana(syarat=["a > 100"])
    with pytest.raises(ValueError, match="syarat terlalu ketat"):
        cp.buat_soal(c, 1)


def test_syarat_berantai_dan_boolop_dipatuhi():
    c = sederhana(syarat=["a < b < 30", "a % 2 == 0 or b == 7"])
    for seed in range(1, 60):
        p = cp.buat_soal(c, seed).parameter
        assert p["a"] < p["b"] < 30 and (p["a"] % 2 == 0 or p["b"] == 7)


def test_kunci_negatif_ditandai_bukan_dibulatkan():
    c = sederhana(kunci="a - b", variabel={"a": [1, 5], "b": [30, 40]})
    with pytest.raises(cp.KunciNegatif):
        cp.buat_soal(c, 1)


def test_determinisme_seed_sama_soal_sama_seed_beda_berbeda():
    c = cp.validasi(dasar())
    assert cp.buat_soal(c, 7) == cp.buat_soal(c, 7)
    assert cp.buat_soal(c, 7) != cp.buat_soal(c, 8)
    teks = {cp.buat_soal(c, s).teks for s in range(1, 40)}
    assert len(teks) > 20


def test_determinisme_lintas_proses():
    kode = (
        "import sys, json; sys.path.insert(0, %r); import cetakan_pola as cp; "
        "c = cp.validasi(json.loads(sys.stdin.read())); "
        "print(cp.buat_soal(c, 13).tanda_tangan, cp.buat_soal(c, 13).teks)" % str(MESIN))
    keluar = {subprocess.run([sys.executable, "-c", kode, ], input=json.dumps(dasar()), text=True,
                             capture_output=True, check=True,
                             env={"PYTHONHASHSEED": str(n), "PATH": ""}).stdout
              for n in (1, 2, 3)}
    assert len(keluar) == 1


def test_urutan_kunci_variabel_tidak_mengubah_soal():
    a = cp.validasi(dasar(variabel={"a": [10, 50], "b": [1, 40]}))
    b = cp.validasi(dasar(variabel={"b": [1, 40], "a": [10, 50]}))
    assert cp.buat_soal(a, 5) == cp.buat_soal(b, 5)


def test_seed_harus_int_bukan_bool():
    c = cp.validasi(dasar())
    for seed in (True, "1", 1.0, None):
        with pytest.raises(ValueError, match="Seed"):
            cp.buat_soal(c, seed)


def test_nama_dari_daftar_sintetis_dan_sama_dengan_topik_inti():
    c = cp.validasi(dasar())
    nama = set()
    for seed in range(1, 80):
        soal = cp.buat_soal(c, seed)
        pertama = soal.teks.split(" ")[0]
        assert pertama in cp.NAMA_SINTETIS
        nama.add(pertama)
    assert nama == set(cp.NAMA_SINTETIS)
    import topic_school_basics
    assert cp.NAMA_SINTETIS == topic_school_basics._NAMA_ANAK


def test_angka_di_teks_berformat_ribuan_indonesia_kunci_polos():
    c = sederhana(kunci="a * 2", variabel={"a": [5000, 9000], "b": [1, 2]})
    soal = cp.buat_soal(c, 3)
    a = soal.parameter["a"]
    assert soal.teks.startswith(f"{a:,}".replace(",", ".") + " dan ")
    assert soal.kunci == str(a * 2) and "." not in soal.kunci
    from school_numbers_common import ribuan
    assert cp.ribuan(123456789) == ribuan(123456789) == "123.456.789"


def test_tanda_tangan_bergantung_parameter_dan_bukan_nama():
    c = cp.validasi(dasar())
    ttd = {cp.buat_soal(c, s).tanda_tangan for s in range(1, 50)}
    assert len(ttd) > 20 and all(len(t) == 64 for t in ttd)
    lain_bab = cp.validasi(dasar(kelas=3, bab=2))
    assert cp.buat_soal(c, 1).tanda_tangan != cp.buat_soal(lain_bab, 1).tanda_tangan
    # Nama tidak ikut: dua soal berparameter sama memiliki tanda tangan sama.
    sama = [s for s in (cp.buat_soal(c, x) for x in range(1, 400))]
    per_param = {}
    for s in sama:
        per_param.setdefault(tuple(sorted(s.parameter.items())), set()).add(s.tanda_tangan)
    assert all(len(v) == 1 for v in per_param.values())


# --- kelayakan ---------------------------------------------------------------

def test_uji_kelayakan_cetakan_baik_lolos_dengan_sepuluh_contoh():
    hasil = cp.uji_kelayakan(cp.validasi(dasar()))
    assert hasil.lolos and hasil.alasan == ()
    assert hasil.jumlah_unik >= cp.MIN_UNIK and len(hasil.contoh) == 10
    assert hasil.contoh == cp.contoh(cp.validasi(dasar()), 10)


def test_uji_kelayakan_domain_kecil_gagal_walau_nama_menggandakan_teks():
    c = cp.validasi(dasar(variabel={"a": [1, 5]}, teks="{nama} punya {a} apel", syarat=[],
                          kunci="a", pembahasan=""))
    hasil = cp.uji_kelayakan(c)
    assert not hasil.lolos and hasil.jumlah_unik == 5
    assert any("unik" in a for a in hasil.alasan)
    assert len({s.teks for s in cp.contoh(c, 200)}) > 5     # teks lebih beragam dari tanda tangan


def test_uji_kelayakan_syarat_mustahil_gagal():
    hasil = cp.uji_kelayakan(sederhana(syarat=["a > 100"]))
    assert not hasil.lolos and hasil.jumlah_unik == 0 and hasil.contoh == ()


def test_uji_kelayakan_kunci_negatif_gagal():
    c = sederhana(kunci="a - b", variabel={"a": [1, 100], "b": [1, 100]})
    hasil = cp.uji_kelayakan(c)
    assert not hasil.lolos and any("negatif" in a for a in hasil.alasan)
    benar = sederhana(kunci="a - b", variabel={"a": [1, 100], "b": [1, 100]}, syarat=["a >= b"])
    assert cp.uji_kelayakan(benar).lolos


def test_uji_kelayakan_placeholder_sisa_gagal():
    c = dataclasses.replace(cp.validasi(dasar()), teks="{nama} punya {a} dan {b} dan {z}")
    hasil = cp.uji_kelayakan(c)
    assert not hasil.lolos and any("placeholder" in a for a in hasil.alasan)


def test_contoh_menghormati_n_dan_seed_awal():
    c = cp.validasi(dasar())
    assert len(cp.contoh(c, 3)) == 3
    assert cp.contoh(c, 2, seed_awal=5) == (cp.buat_soal(c, 5), cp.buat_soal(c, 6))
    for n in (0, -1, True, "3"):
        with pytest.raises(ValueError):
            cp.contoh(c, n)


# --- penutupan impor ---------------------------------------------------------

def _modul_mesin_terimpor(impor: str) -> set:
    kode = (
        "import sys; sys.path.insert(0, %r); %s; "
        "print(sorted(n for n, m in sys.modules.items() "
        "if getattr(m, '__file__', None) and m.__file__.startswith(%r)))"
        % (str(MESIN), impor, str(MESIN) + "/"))
    keluar = subprocess.run([sys.executable, "-c", kode], capture_output=True, text=True, check=True).stdout
    return set(ast.literal_eval(keluar.strip()))


def test_cetakan_pola_hanya_menarik_kurikulum_kelas_dari_mesin():
    assert _modul_mesin_terimpor("import cetakan_pola") <= {"cetakan_pola", "kurikulum_kelas"}


def test_generator_tidak_menarik_cetakan():
    terimpor = _modul_mesin_terimpor("import generator")
    assert "cetakan_pola" not in terimpor and "cetakan_store" not in terimpor


def test_cetakan_pola_hanya_mengimpor_stdlib_dan_kurikulum_kelas():
    pohon = ast.parse((MESIN / "cetakan_pola.py").read_text(encoding="utf-8"))
    modul = set()
    for node in pohon.body:
        if isinstance(node, ast.Import):
            modul.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modul.add(node.module)
    assert modul == {"__future__", "ast", "dataclasses", "functools", "hashlib", "json", "random",
                     "re", "typing", "unicodedata", "kurikulum_kelas"}

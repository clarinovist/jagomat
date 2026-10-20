"""Fase 3: kontrak paket topik kelima — teori-bilangan (P4/P5/P6).

8 template menutup cakupan bilangan & teori bilangan OSN SD: keterbagian,
faktorisasi prima, KPK/FPB, sisa pembagian, paritas, digit satuan pangkat,
dan jumlah deret (Gauss). Level P4/P5/P6.
"""

from __future__ import annotations

import math  # noqa: E402
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
from generator import buat_lembar, buat_soal  # noqa: E402


def _paket():
    return topics.ambil("teori-bilangan")


# ── Identitas & registrasi ─────────────────────────────────────────────


def test_teori_bilangan_terdaftar_dengan_identitas():
    paket = _paket()
    assert paket.id == "teori-bilangan"
    assert paket.nama == "Teori Bilangan"
    assert paket.judul_lembar == "Latihan Teori Bilangan"
    assert paket.judul_penilaian == "Penilaian — Teori Bilangan"


def test_teori_bilangan_memulai_dengan_template_awal():
    """Task 3.1 (kerangka): paket valid sejak template #1 #2 terisi."""
    paket = _paket()
    assert "keterbagian" in paket.templates
    assert "prima_faktorisasi" in paket.templates


# ── Komposisi per level (tabel plan Fase 3) ────────────────────────────


def test_komposisi_p4_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P4")
    assert komposisi == (
        "keterbagian", "sisa_pembagian", "paritas",
        "banyak_kelipatan", "sisa_operasi", "banyak_prima", "jumlah_kelipatan",
        "keterbagian", "sisa_pembagian", "paritas",
    )


def test_komposisi_p5_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P5")
    assert komposisi == (
        "keterbagian", "prima_faktorisasi", "kpk_dua_bilangan",
        "sisa_pembagian", "paritas", "gauss_deret",
        "banyak_kelipatan", "sisa_operasi", "banyak_prima", "jumlah_kelipatan",
    )


def test_komposisi_p6_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P6")
    assert komposisi == (
        "keterbagian", "prima_faktorisasi", "kpk_dua_bilangan",
        "fpb_kpk_hubungan", "sisa_pembagian", "angka_satuan_pangkat",
        "gauss_deret", "keterbagian", "fpb_kpk_hubungan",
        "angka_satuan_pangkat",
    )


def test_teori_bilangan_menolak_level_di_luar_scope():
    """Paket P4-P6 tidak boleh diam-diam membuat sesi untuk anak P3."""
    with pytest.raises(ValueError, match="teori-bilangan"):
        buat_lembar(7, level="P3", topik="teori-bilangan")
    with pytest.raises(ValueError, match="teori-bilangan"):
        buat_soal("keterbagian", 7, level="P3", topik="teori-bilangan")


def test_teori_bilangan_level_teks_aneh_jatuh_ke_p4():
    """Data tingkat lama yang aneh memakai level pertama paket (P4)."""
    aneh = buat_lembar(7, level="tingkat-lama", topik="teori-bilangan")
    p4 = buat_lembar(7, level="P4", topik="teori-bilangan")
    assert aneh.level == "P4"
    assert aneh.tanda_tangan == p4.tanda_tangan


def test_teori_bilangan_memuat_template_lama_dan_empat_jenis_terpilih():
    """Registry tetap superset: jenis lama tidak hilang ketika batch ditambahkan."""
    paket = _paket()
    assert len(paket.templates) >= 12
    assert {"banyak_kelipatan", "sisa_operasi", "banyak_prima", "jumlah_kelipatan"} <= paket.templates.keys()
    for nama in (
        "keterbagian",
        "prima_faktorisasi",
        "kpk_dua_bilangan",
        "fpb_kpk_hubungan",
        "sisa_pembagian",
        "paritas",
        "angka_satuan_pangkat",
        "gauss_deret",
    ):
        assert nama in paket.templates, nama


# ── Judul bagian ───────────────────────────────────────────────────────


def test_judul_bagian_teori_bilangan():
    paket = _paket()
    assert paket.judul_bagian == {
        "A": "Bagian A — Keterbagian",
        "B": "Bagian B — KPK & FPB",
        "C": "Bagian C — Sisa & paritas",
        "D": "Bagian D — Pola bilangan",
    }


# ── Template #1 keterbagian — Task 3.2 ─────────────────────────────────


def test_keterbagian_kunci_adalah_bilangan_yang_habis():
    """#1: tepat satu dari tiga bilangan habis dibagi d."""
    for seed in range(1, 120):
        s = buat_soal("keterbagian", seed, level="P4", topik="teori-bilangan")
        p = s.parameter
        pilihan = (p["a"], p["b"], p["c"])
        habis = [x for x in pilihan if x % p["d"] == 0]
        assert len(habis) == 1, f"{p=} tidak punya tepat satu kelipatan"
        assert s.kunci == str(habis[0]), f"{p=}, kunci={s.kunci}"
        # malrule tak boleh menebak kunci
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_keterbagian_trap_divisor():
    """#1: K = bilangan yang habis dibagi trap tapi tidak habis dibagi d."""
    from topic_number_theory import _TRAP

    for seed in range(1, 120):
        s = buat_soal("keterbagian", seed, level="P5", topik="teori-bilangan")
        p = s.parameter
        trap = _TRAP[p["d"]]
        jawaban = {m.id: m.jawaban for m in s.malrule}
        if "keterbagian.trap_divisor" in jawaban:
            num = int(jawaban["keterbagian.trap_divisor"])
            assert num % trap == 0, f"{p=}: {num} tidak habis dibagi {trap}"
            assert num % p["d"] != 0, f"{p=}: {num} habis dibagi {p['d']}"


def test_keterbagian_level_membedakan_pool_divisor():
    """d pool P4 tanpa 8/9/11; P5 ada 8,9; P6 ada 11."""
    terlihat = {"P4": set(), "P5": set(), "P6": set()}
    for level in ("P4", "P5", "P6"):
        for seed in range(1, 200):
            s = buat_soal("keterbagian", seed, level=level, topik="teori-bilangan")
            terlihat[level].add(s.parameter["d"])
    assert terlihat["P4"] <= {2, 3, 4, 5, 6}
    assert 8 in terlihat["P5"] and 9 in terlihat["P5"]
    assert 11 in terlihat["P6"]


def test_keterbagian_sweep_tanpa_malrule_kosong():
    for level in ("P4", "P5", "P6"):
        for seed in range(1, 120):
            s = buat_soal("keterbagian", seed, level=level, topik="teori-bilangan")
            assert s.malrule, f"keterbagian@{level}/{seed} kosong"
            assert {"K", "H"} <= {m.kode for m in s.malrule}


# ── Template #3-#4 KPK & FPB — Task 3.3 ───────────────────────────────

KELOMPOK_KPK = ("kpk_dua_bilangan", "fpb_kpk_hubungan")


def test_kpk_dua_bilangan_kunci():
    """#3: KPK dari a dan b = lcm(a,b)."""
    s = buat_soal("kpk_dua_bilangan", 7, level="P5", topik="teori-bilangan")
    p = s.parameter
    expected = p["a"] * p["b"] // math.gcd(p["a"], p["b"])
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_kpk_malrule_konsep():
    """#3: a×b (K), gcd (K), kurang_satu (H)."""
    s = buat_soal("kpk_dua_bilangan", 11, level="P5", topik="teori-bilangan")
    p = s.parameter
    jawaban = {m.id: m.jawaban for m in s.malrule}
    assert jawaban["kpk.dikali"] == str(p["a"] * p["b"])
    assert jawaban["kpk.tertukar_fpb"] == str(math.gcd(p["a"], p["b"]))
    assert jawaban["kpk.kurang_satu"] == str(p["a"] * p["b"] // math.gcd(p["a"], p["b"]) - 1)


def test_fpb_kpk_hubungan():
    """#4: FPB × KPK dari a dan b = a×b."""
    s = buat_soal("fpb_kpk_hubungan", 7, level="P6", topik="teori-bilangan")
    p = s.parameter
    expected = p["a"] * p["b"]
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_fpb_kpk_malrule_konsep():
    """#4: hanya_fpb (K), hanya_kpk (K), kurang_satu (H)."""
    s = buat_soal("fpb_kpk_hubungan", 11, level="P6", topik="teori-bilangan")
    p = s.parameter
    jawaban = {m.id: m.jawaban for m in s.malrule}
    assert jawaban["hubungan.hanya_fpb"] == str(math.gcd(p["a"], p["b"]))
    assert jawaban["hubungan.hanya_kpk"] == str(p["a"] * p["b"] // math.gcd(p["a"], p["b"]))
    assert jawaban["hubungan.kurang_satu"] == str(p["a"] * p["b"] - 1)


@pytest.mark.parametrize("template_id", KELOMPOK_KPK)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_kpk_sweep(template_id, level):
    """Tiap soal KPK/FPB punya K dan H."""
    if template_id == "fpb_kpk_hubungan" and level == "P5":
        return  # #4 hanya P6
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="teori-bilangan")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}


# ── Template #5-#6 sisa & paritas — Task 3.4 ──────────────────────────

KELOMPOK_SISA = ("sisa_pembagian", "paritas")


def test_sisa_pembagian_kunci():
    """#5: N dibagi d bersisa sisa = N % d, sisa >= 1."""
    s = buat_soal("sisa_pembagian", 7, level="P4", topik="teori-bilangan")
    p = s.parameter
    expected = p["N"] % p["d"]
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_sisa_malrule_konsep():
    """#5: quotient (K), complement (K), kurang_satu (H)."""
    s = buat_soal("sisa_pembagian", 11, level="P4", topik="teori-bilangan")
    p = s.parameter
    jawaban = {m.id: m.jawaban for m in s.malrule}
    assert jawaban["sisa.quotient"] == str(p["N"] // p["d"])
    assert jawaban["sisa.kurang_satu"] == str(p["N"] % p["d"] - 1)


def test_paritas_kunci():
    """#6: jumlah n bilangan ganjil mulai a = n·(a+n−1); a=1 → n²."""
    s = buat_soal("paritas", 7, level="P4", topik="teori-bilangan")
    p = s.parameter
    expected = p["n"] * (p["a"] + p["n"] - 1)
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_paritas_malrule_konsep():
    """#6: jumlah_natural (K), hanya_suku_pertama (K), kurang_satu (H)."""
    s = buat_soal("paritas", 11, level="P4", topik="teori-bilangan")
    p = s.parameter
    jawaban = {m.id: m.jawaban for m in s.malrule}
    assert jawaban["paritas.jumlah_natural"] == str(p["n"] * (p["n"] + 1) // 2)
    assert jawaban["paritas.hanya_suku_pertama"] == str(p["n"] * p["a"])
    assert jawaban["paritas.kurang_satu"] == str(
        p["n"] * (p["a"] + p["n"] - 1) - 1
    )


@pytest.mark.parametrize("template_id", KELOMPOK_SISA)
@pytest.mark.parametrize("level", ("P4", "P5", "P6"))
def test_kelompok_sisa_sweep(template_id, level):
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="teori-bilangan")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}


# ── Template #7-#8 pola bilangan — Task 3.5 ───────────────────────────

KELOMPOK_POLA = ("angka_satuan_pangkat", "gauss_deret")


def test_angka_satuan_pangkat_kunci():
    """#7: digit satuan a^b lewat siklus (a, a², a³, ... berulang)."""
    s = buat_soal("angka_satuan_pangkat", 7, level="P6", topik="teori-bilangan")
    p = s.parameter
    # brute force: kalikan berulang, ambil digit satuan
    satuan = 1
    for _ in range(p["b"]):
        satuan = (satuan * p["a"]) % 10
    assert s.kunci == str(satuan), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_angka_satuan_malrule_konsep():
    """#7: jawab_a (K), siklus_meleset (K), kurang_satu (H)."""
    s = buat_soal("angka_satuan_pangkat", 11, level="P6", topik="teori-bilangan")
    p = s.parameter
    jawaban = {m.id: m.jawaban for m in s.malrule}
    assert jawaban["satuan.jawab_a"] == str(p["a"] % 10)
    assert "satuan.siklus_meleset" in jawaban
    assert "satuan.kurang_satu" in jawaban


def test_gauss_deret_kunci():
    """#8: 1+2+...+n = n(n+1)/2."""
    s = buat_soal("gauss_deret", 7, level="P5", topik="teori-bilangan")
    p = s.parameter
    expected = p["n"] * (p["n"] + 1) // 2
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_gauss_deret_malrule_konsep():
    """#8: dikira_ganjil (K), lupa_bagi_2 (K), kurang_satu (H)."""
    s = buat_soal("gauss_deret", 11, level="P5", topik="teori-bilangan")
    p = s.parameter
    jawaban = {m.id: m.jawaban for m in s.malrule}
    assert jawaban["gauss.dikira_ganjil"] == str(p["n"] ** 2)
    assert jawaban["gauss.lupa_bagi_2"] == str(p["n"] * (p["n"] + 1))
    assert jawaban["gauss.kurang_satu"] == str(p["n"] * (p["n"] + 1) // 2 - 1)


@pytest.mark.parametrize("template_id", KELOMPOK_POLA)
def test_kelompok_pola_sweep(template_id):
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level="P6", topik="teori-bilangan")
        assert s.malrule, f"{template_id}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}

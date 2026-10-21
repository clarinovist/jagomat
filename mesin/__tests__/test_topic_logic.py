"""Fase 7: kontrak paket topik kesembilan — logika (P3/P5/P6).

Enam template menutup cakupan penalaran & logika OSN SD: penalaran
(bagian A), besaran & umur (B). P3 dibuka tanpa template baru — cukup
filter parameter per level (batas ringan selaras SASMO Primary 1–4,
non-routine: logic problems); P4 tetap di luar scope.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
from generator import buat_lembar, buat_soal  # noqa: E402


def _paket():
    return topics.ambil("logika")


# ── Identitas & registrasi ─────────────────────────────────────────────


def test_logika_terdaftar_dengan_identitas():
    paket = _paket()
    assert paket.id == "logika"
    assert paket.nama == "Logika & Penalaran"
    assert paket.judul_lembar == "Latihan Logika & Penalaran"
    assert paket.judul_penilaian == "Penilaian — Logika & Penalaran"


def test_logika_memulai_dengan_template_awal():
    """Task 7.1 (kerangka): paket valid sejak template #1 #2 terisi."""
    paket = _paket()
    assert "benar_salah_pengandaian" in paket.templates
    assert "tabel_penalaran" in paket.templates


# ── Komposisi per level (tabel plan Fase 7) ────────────────────────────


def test_komposisi_p3_sepuluh_soal():
    """P3 (selaras SASMO Primary 1–4, non-routine): 4 template penalaran,
    disusun mudah → sulit (pengandaian & tabel dulu, umur paling akhir)."""
    komposisi = _paket().komposisi_untuk("P3")
    assert komposisi == (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "soal_uang",
        "soal_umur",
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "soal_uang",
        "soal_umur",
    )


def test_komposisi_p5_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P5")
    assert komposisi == (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_uang",
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_uang",
        "benar_salah_pengandaian",
        "tabel_penalaran",
    )


def test_komposisi_p6_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P6")
    assert komposisi == (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_umur",
        "soal_uang",
        "dua_besaran_selisih",
        "jumlah_selisih",
        "soal_umur",
        "soal_uang",
        "dua_besaran_selisih",
    )


def test_logika_menolak_level_di_luar_scope():
    """Paket P3/P5/P6 tidak boleh diam-diam membuat sesi untuk anak P4.

    P3 dulu ikut ditolak; sekarang didukung lewat filter parameter per
    level, jadi penolakan tersisa untuk P4 saja.
    """
    with pytest.raises(ValueError, match="logika"):
        buat_lembar(7, level="P4", topik="logika")
    with pytest.raises(ValueError, match="logika"):
        buat_soal("jumlah_selisih", 7, level="P4", topik="logika")


def test_logika_level_teks_aneh_jatuh_ke_p3():
    """Data tingkat lama yang aneh memakai level pertama paket.

    Dulu asersinya P5: fallback next(iter(KOMPOSISI)) jatuh ke kunci
    pertama yang saat itu P5. Sejak P3 dibuka dan dijadikan kunci
    pertama KOMPOSISI (P3, P5, P6), fallback yang sama bergeser ke P3.
    """
    aneh = buat_lembar(7, level="tingkat-lama", topik="logika")
    p3 = buat_lembar(7, level="P3", topik="logika")
    assert aneh.level == "P3"
    assert aneh.tanda_tangan == p3.tanda_tangan


def test_logika_memuat_enam_template():
    """Task 7.3: seluruh 6 template sudah terimplementasi."""
    paket = _paket()
    assert len(paket.templates) == 6
    for nama in (
        "benar_salah_pengandaian",
        "tabel_penalaran",
        "jumlah_selisih",
        "soal_umur",
        "soal_uang",
        "dua_besaran_selisih",
    ):
        assert nama in paket.templates, nama


# ── Judul bagian ───────────────────────────────────────────────────────


def test_judul_bagian_logika():
    paket = _paket()
    assert paket.judul_bagian == {
        "A": "Bagian A — Penalaran",
        "B": "Bagian B — Besaran & umur",
    }


# ── Template #1-#2 penalaran ───────────────────────────────────────────


def test_benar_salah_pengandaian_kunci():
    """#1: kunci = huruf A-E (posisi pernyataan benar)."""
    for seed in range(1, 60):
        s = buat_soal("benar_salah_pengandaian", seed, level="P5", topik="logika")
        p = s.parameter
        assert s.kunci in ("A", "B", "C", "D", "E"), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        # harus ada B, K, H (4 malrule: B, K, K, H)
        assert {"B", "K", "H"} <= {m.kode for m in s.malrule}, p


def test_tabel_penalaran_kunci():
    """#2: kunci = nama orang (tertinggi/terendah/posisi)."""
    for seed in range(1, 60):
        s = buat_soal("tabel_penalaran", seed, level="P5", topik="logika")
        p = s.parameter
        assert s.kunci in p["urutan"], f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Template #3-#6 besaran & umur ──────────────────────────────────────


def test_jumlah_selisih_kunci():
    """#3: (j+s)/2 dan (j-s)/2."""
    for seed in range(1, 120):
        s = buat_soal("jumlah_selisih", seed, level="P5", topik="logika")
        p = s.parameter
        if p["tanya"] == "besar":
            expected = (p["jumlah"] + p["selisih"]) // 2
        else:
            expected = (p["jumlah"] - p["selisih"]) // 2
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_soal_umur_kunci(monkeypatch):
    """Writer diperbaiki memenuhi fakta umur pada waktu yang sama."""
    monkeypatch.setenv("OSN_KATALOG_VERSI", "2")
    for seed in range(1, 120):
        s = buat_soal("soal_umur", seed, level="P6", topik="logika")
        p = s.parameter
        jawaban = int(s.kunci)
        if p["tanya"] == "n_tahun":
            assert p["a"] + jawaban == (p["b"] + jawaban) * p["k"]
        else:
            assert (p["b"] + p["n"]) * jawaban == p["a"] + p["n"]
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_soal_uang_kunci():
    """#5: B = total/(k+1), A = k·B."""
    for seed in range(1, 120):
        s = buat_soal("soal_uang", seed, level="P5", topik="logika")
        p = s.parameter
        kecil = p["total"] // (p["k"] + 1)
        if p["tanya"] == "uang_kecil":
            expected = kecil
        else:
            expected = p["k"] * kecil
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_dua_besaran_selisih_kunci():
    """#6: b = s/(k−1), a = k·b."""
    for seed in range(1, 120):
        s = buat_soal("dua_besaran_selisih", seed, level="P6", topik="logika")
        p = s.parameter
        kecil = p["selisih"] // (p["k"] - 1)
        if p["tanya"] == "besar":
            expected = p["k"] * kecil
        else:
            expected = kecil
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Level P3 — filter parameter, bukan template baru ───────────────────

TEMPLATE_P3 = (
    "benar_salah_pengandaian",
    "tabel_penalaran",
    "soal_umur",
    "soal_uang",
)


@pytest.mark.parametrize("template_id", TEMPLATE_P3)
def test_parameter_p3_batas(template_id):
    """P3: batas parameter ringan selaras SASMO Primary 1–4 (non-routine)."""
    for seed in range(1, 121):
        p = buat_soal(template_id, seed, level="P3", topik="logika").parameter
        if template_id == "benar_salah_pengandaian":
            assert p["kelas"] == 3, p
        elif template_id == "tabel_penalaran":
            # selalu 3 nama; tanpa posisi_tiga (butuh minimal 4 nama)
            assert len(p["urutan"]) == 3, p
            assert p["tanya"] in ("tertinggi", "terendah", "posisi_dua"), p
        elif template_id == "soal_umur":
            assert p["k"] in (2, 3) and 2 <= p["b"] <= 8 and 1 <= p["n"] <= 8, p
            assert p["a"] == p["k"] * p["b"] + (p["k"] - 1) * p["n"], p
        else:  # soal_uang
            kecil = p["total"] // (p["k"] + 1)
            assert 10 <= kecil <= 40, p
            assert p["k"] in (2, 3, 4, 5), p


@pytest.mark.parametrize("template_id", TEMPLATE_P3)
def test_kunci_malrule_p3(template_id):
    """P3: kunci tidak bocor ke malrule; jalur diagnosis K & H selamat.

    benar_salah_pengandaian punya 4 malrule (B/K/K/H) — B ikut diasersi;
    tiga template lainnya 3 malrule (K/K/H).
    """
    for seed in range(1, 121):
        s = buat_soal(template_id, seed, level="P3", topik="logika")
        assert s.level == "P3", (template_id, seed)
        p = s.parameter
        assert s.kunci not in [m.jawaban for m in s.malrule], (template_id, seed, p)
        kode = {m.kode for m in s.malrule}
        assert {"K", "H"} <= kode, (template_id, seed, p)
        if template_id == "benar_salah_pengandaian":
            assert "B" in kode, (template_id, seed, p)


# ── Sweep per kelompok template ────────────────────────────────────────

KELOMPOK_A = ("benar_salah_pengandaian", "tabel_penalaran")
KELOMPOK_B = ("jumlah_selisih", "soal_umur", "soal_uang", "dua_besaran_selisih")


@pytest.mark.parametrize("template_id", KELOMPOK_A)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_a_sweep(template_id, level):
    for seed in range(1, 60):
        s = buat_soal(template_id, seed, level=level, topik="logika")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        # benar_salah_pengandaian punya B/K/H; tabel_penalaran punya K/H
        if template_id == "benar_salah_pengandaian":
            assert {"B", "K", "H"} <= {m.kode for m in s.malrule}, f"{template_id}@{level}/{seed}"
        else:
            assert {"K", "H"} <= {m.kode for m in s.malrule}, f"{template_id}@{level}/{seed}"


@pytest.mark.parametrize("template_id", KELOMPOK_B)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_b_sweep(template_id, level):
    if template_id in ("soal_umur", "dua_besaran_selisih") and level == "P5":
        return  # #4 #6 hanya P6
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="logika")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}, f"{template_id}@{level}/{seed}"
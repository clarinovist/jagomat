"""Fase 4: kontrak paket topik keenam — aritmatika-lanjut (P5/P6).

11 template menutup cakupan aritmatika terapan OSN SD: konversi satuan,
kecepatan/jarak/waktu, berpapasan, menyusul, debit, perbandingan senilai
& berbalik, kerja bersama, dan persen (diskon/untung-rugi/bertingkat).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
from generator import buat_lembar, buat_soal  # noqa: E402


def _paket():
    return topics.ambil("aritmatika-lanjut")


# ── Identitas & registrasi ─────────────────────────────────────────────


def test_aritmatika_lanjut_terdaftar_dengan_identitas():
    paket = _paket()
    assert paket.id == "aritmatika-lanjut"
    assert paket.nama == "Aritmatika Lanjut"
    assert paket.judul_lembar == "Latihan Aritmatika Lanjut"
    assert paket.judul_penilaian == "Penilaian — Aritmatika Lanjut"


def test_aritmatika_lanjut_memulai_dengan_template_awal():
    """Task 4.1 (kerangka): paket valid sejak template #1 #2 terisi."""
    paket = _paket()
    assert "satuan_konversi" in paket.templates
    assert "kecepatan_jarak_waktu" in paket.templates


# ── Komposisi per level (tabel plan Fase 4) ────────────────────────────


def test_komposisi_p5_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P5")
    assert komposisi == (
        "satuan_konversi", "kecepatan_jarak_waktu",
        "debit", "perbandingan_senilai", "perbandingan_berbalik",
        "kerja_bersama", "persen_diskon",
        "satuan_konversi", "kecepatan_jarak_waktu", "persen_diskon",
    )


def test_komposisi_p6_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P6")
    assert komposisi == (
        "berpapasan", "menyusul",
        "perbandingan_senilai", "perbandingan_berbalik",
        "kerja_bersama", "persen_untung_rugi", "persen_bertingkat",
        "satuan_konversi", "kecepatan_jarak_waktu", "debit",
    )


def test_aritmatika_lanjut_menolak_level_di_luar_scope():
    """Paket P5/P6 tidak boleh diam-diam membuat sesi untuk anak P3/P4."""
    for level in ("P3", "P4"):
        with pytest.raises(ValueError, match="aritmatika-lanjut"):
            buat_lembar(7, level=level, topik="aritmatika-lanjut")
        with pytest.raises(ValueError, match="aritmatika-lanjut"):
            buat_soal("satuan_konversi", 7, level=level, topik="aritmatika-lanjut")


def test_aritmatika_lanjut_level_teks_aneh_jatuh_ke_p5():
    """Data tingkat lama yang aneh memakai level pertama paket (P5)."""
    aneh = buat_lembar(7, level="tingkat-lama", topik="aritmatika-lanjut")
    p5 = buat_lembar(7, level="P5", topik="aritmatika-lanjut")
    assert aneh.level == "P5"
    assert aneh.tanda_tangan == p5.tanda_tangan


def test_aritmatika_lanjut_memuat_sebelas_template():
    """Task 4.5: seluruh 11 template sudah terimplementasi."""
    paket = _paket()
    assert len(paket.templates) == 11
    for nama in (
        "satuan_konversi",
        "kecepatan_jarak_waktu",
        "berpapasan",
        "menyusul",
        "debit",
        "perbandingan_senilai",
        "perbandingan_berbalik",
        "kerja_bersama",
        "persen_diskon",
        "persen_untung_rugi",
        "persen_bertingkat",
    ):
        assert nama in paket.templates, nama


# ── Judul bagian ───────────────────────────────────────────────────────


def test_judul_bagian_aritmatika_lanjut():
    paket = _paket()
    assert paket.judul_bagian == {
        "A": "Bagian A — Konversi & kecepatan",
        "B": "Bagian B — Perbandingan",
        "C": "Bagian C — Kerja sama",
        "D": "Bagian D — Persen",
    }


# ── Template #1-#2 konversi & kecepatan — Task 4.2 ────────────────────

KELOMPOK_KONVERSI = ("satuan_konversi", "kecepatan_jarak_waktu")


def test_satuan_konversi_kunci():
    """#1: konversi sesuai arah (× atau ÷ faktor)."""
    from topic_advanced_arithmetic import satuan_konversi as fn

    for seed in range(1, 120):
        s = buat_soal("satuan_konversi", seed, level="P5", topik="aritmatika-lanjut")
        p = s.parameter
        faktor = {
            "km_ke_m": 1000, "m_ke_km": 1000,
            "jam_ke_menit": 60, "menit_ke_jam": 60,
            "kg_ke_g": 1000, "g_ke_kg": 1000,
            "liter_ke_ml": 1000, "ml_ke_liter": 1000,
        }[p["varian"]]
        kiri = p["varian"].endswith(("_m", "_menit", "_g", "_ml"))
        expected = p["nilai"] * faktor if kiri else p["nilai"] // faktor
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_kecepatan_kunci():
    """#2: v=s/t, s=v·t, t=s/v — tiga arah."""
    for seed in range(1, 120):
        s = buat_soal("kecepatan_jarak_waktu", seed, level="P5", topik="aritmatika-lanjut")
        p = s.parameter
        if p["varian"] == "cari_v":
            expected = p["s"] // p["t"]
        elif p["varian"] == "cari_s":
            expected = p["v"] * p["t"]
        else:
            expected = p["s"] // p["v"]
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


@pytest.mark.parametrize("template_id", KELOMPOK_KONVERSI)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_konversi_sweep(template_id, level):
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="aritmatika-lanjut")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}


# ── Template #3-#5 gerak & debit — Task 4.3 ───────────────────────────

KELOMPOK_GERAK = ("berpapasan", "menyusul", "debit")


def test_berpapasan_kunci():
    """#3: waktu bertemu = jarak/(v₁+v₂)."""
    s = buat_soal("berpapasan", 7, level="P6", topik="aritmatika-lanjut")
    p = s.parameter
    expected = p["jarak"] // (p["v1"] + p["v2"])
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_menyusul_kunci():
    """#4: waktu menyusul = jarak_awal/(v₂−v₁)."""
    s = buat_soal("menyusul", 7, level="P6", topik="aritmatika-lanjut")
    p = s.parameter
    expected = p["jarak"] // (p["v2"] - p["v1"])
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_debit_kunci():
    """#5: debit = volume/waktu (dua arah)."""
    s = buat_soal("debit", 7, level="P5", topik="aritmatika-lanjut")
    p = s.parameter
    if p["varian"] == "cari_debit":
        expected = p["volume"] // p["waktu"]
    elif p["varian"] == "cari_volume":
        expected = p["debit"] * p["waktu"]
    else:
        expected = p["volume"] // p["debit"]
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


@pytest.mark.parametrize("template_id", KELOMPOK_GERAK)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_gerak_sweep(template_id, level):
    if template_id in ("berpapasan", "menyusul") and level == "P5":
        return  # #3 #4 hanya P6
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="aritmatika-lanjut")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}


# ── Template #6-#8 perbandingan & kerja — Task 4.4 ────────────────────

KELOMPOK_PERBANDINGAN = ("perbandingan_senilai", "perbandingan_berbalik", "kerja_bersama")


def test_perbandingan_senilai_kunci(monkeypatch):
    """#6: a₁/b₁ = a₂/b₂ → cari yang tak diketahui."""
    monkeypatch.setenv('OSN_KATALOG_VERSI', '2')
    s = buat_soal("perbandingan_senilai", 7, level="P5", topik="aritmatika-lanjut")
    p = s.parameter
    from fractions import Fraction
    assert Fraction(s.kunci.replace(',', '.')) / p['n'] == Fraction(p['q'], p['p'])
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_perbandingan_berbalik_kunci(monkeypatch):
    """#7: a₁×b₁ = a₂×b₂ → cari yang tak diketahui."""
    monkeypatch.setenv('OSN_KATALOG_VERSI', '2')
    s = buat_soal("perbandingan_berbalik", 7, level="P5", topik="aritmatika-lanjut")
    p = s.parameter
    from fractions import Fraction
    assert Fraction(s.kunci.replace(',', '.')) * p['a2'] == p['a1'] * p['b1']
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_kerja_bersama_kunci(monkeypatch):
    """#8: waktu bersama = a·b/(a+b)."""
    monkeypatch.setenv('OSN_KATALOG_VERSI', '2')
    s = buat_soal("kerja_bersama", 7, level="P5", topik="aritmatika-lanjut")
    p = s.parameter
    from fractions import Fraction
    waktu = Fraction(s.kunci.replace(',', '.'))
    assert waktu / p['a'] + waktu / p['b'] == 1
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


@pytest.mark.parametrize("template_id", KELOMPOK_PERBANDINGAN)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_perbandingan_sweep(template_id, level):
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="aritmatika-lanjut")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}


# ── Template #9-#11 persen — Task 4.5 ─────────────────────────────────

KELOMPOK_PERSEN = ("persen_diskon", "persen_untung_rugi", "persen_bertingkat")


def test_persen_diskon_kunci():
    """#9: harga setelah diskon = harga×(100−d)/100."""
    s = buat_soal("persen_diskon", 7, level="P5", topik="aritmatika-lanjut")
    p = s.parameter
    expected = p["harga"] * (100 - p["d"]) // 100
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_persen_untung_rugi_kunci():
    """#10: harga jual = modal×(100+%untung)/100."""
    s = buat_soal("persen_untung_rugi", 7, level="P6", topik="aritmatika-lanjut")
    p = s.parameter
    if p["jenis"] == "untung":
        expected = p["modal"] * (100 + p["persen"]) // 100
    else:
        expected = p["modal"] * (100 - p["persen"]) // 100
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_persen_bertingkat_kunci():
    """#11: harga×(1−d₁/100)×(1−d₂/100)."""
    s = buat_soal("persen_bertingkat", 7, level="P6", topik="aritmatika-lanjut")
    p = s.parameter
    expected = p["harga"] * (100 - p["d1"]) * (100 - p["d2"]) // 10000
    assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
    assert s.kunci not in [m.jawaban for m in s.malrule]
    assert {"K", "H"} <= {m.kode for m in s.malrule}, p


@pytest.mark.parametrize("template_id", KELOMPOK_PERSEN)
@pytest.mark.parametrize("level", ("P5", "P6"))
def test_kelompok_persen_sweep(template_id, level):
    if template_id in ("persen_untung_rugi", "persen_bertingkat") and level == "P5":
        return  # #10 #11 hanya P6
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="aritmatika-lanjut")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}

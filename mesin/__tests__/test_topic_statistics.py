"""Fase 6: kontrak paket topik kedelapan — statistika (P3-P6).

Lima template menutup cakupan statistika OSN SD: rata-rata (bagian A),
median & modus, diagram lingkaran dan batang/garis (B). P3 didukung
selaras band SASMO Primary 1-4 (statistics): hanya modus & diagram batang,
median menunggu P4.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
from generator import buat_lembar, buat_soal  # noqa: E402


def _paket():
    return topics.ambil("statistika")


# ── Identitas & registrasi ─────────────────────────────────────────────


def test_statistika_terdaftar_dengan_identitas():
    paket = _paket()
    assert paket.id == "statistika"
    assert paket.nama == "Statistika"
    assert paket.judul_lembar == "Latihan Statistika"
    assert paket.judul_penilaian == "Penilaian — Statistika"


def test_statistika_memulai_dengan_template_awal():
    """Task 6.1 (kerangka): paket valid sejak template #1 #2 terisi."""
    paket = _paket()
    assert "rata_rata" in paket.templates
    assert "rata_rata_gabungan" in paket.templates


# ── Komposisi per level (tabel plan Fase 6) ────────────────────────────


def test_komposisi_p3_sepuluh_soal():
    """P3: lima template — median & rata-rata tetap menunggu P4.

    Sebelum 2 Sep 2026 hanya dua template, dan itu membuat P3 level
    paling monoton di aplikasi (3000 soal → 6 bentuk kalimat saja).
    Jangkauan/turus/piktogram semuanya sesuai band SASMO Primary 1-4:
    membaca dan membandingkan data, tanpa perlu membagi.
    """
    komposisi = _paket().komposisi_untuk("P3")
    assert komposisi == (
        "jangkauan_data",
        "median_modus",
        "tabel_turus",
        "diagram_batang_garis",
        "piktogram",
        "median_modus",
        "jangkauan_data",
        "tabel_turus",
        "diagram_batang_garis",
        "piktogram",
    )
    assert "rata_rata" not in komposisi, "rata-rata masih menunggu P4"


def test_komposisi_p3_tanpa_median():
    """Median di atas kelas 3 — penambahan template tidak boleh
    menyelundupkannya lewat varian median_modus."""
    for seed in range(1, 60):
        lembar = buat_lembar(seed, level="P3", topik="statistika")
        for s in lembar.soal:
            assert s.parameter.get("varian") != "median", s.parameter


def test_komposisi_p4_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P4")
    assert komposisi == (
        "rata_rata",
        "median_modus",
        "diagram_batang_garis",
        "piktogram",
        "rata_rata",
        "tabel_turus",
        "median_modus",
        "diagram_batang_garis",
        "jangkauan_data",
        "rata_rata",
    )


def test_komposisi_p5_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P5")
    assert komposisi == (
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
    )


def test_komposisi_p6_sepuluh_soal():
    komposisi = _paket().komposisi_untuk("P6")
    assert komposisi == (
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "rata_rata",
    )


def test_statistika_p3_kini_didukung():
    """Dulu paket menolak P3; sejak P3 selaras band SASMO Primary 1-4,
    lembar P3 sah — pembukaan level tidak boleh melempar ValueError lagi."""
    lembar = buat_lembar(7, level="P3", topik="statistika")
    assert lembar.level == "P3"
    assert len(lembar.soal) == 10


def test_statistika_level_teks_aneh_jatuh_ke_p3():
    """Level teks aneh memakai level pertama paket.

    Dulu jatuh ke P4 — kunci pertama KOMPOSISI saat statistika belum
    mendukung P3. Kini "P3" kunci pertama KOMPOSISI, jadi teks aneh
    jatuh ke P3 (kontrak lama susun_lembar tetap dipertahankan).
    """
    aneh = buat_lembar(7, level="tingkat-lama", topik="statistika")
    p3 = buat_lembar(7, level="P3", topik="statistika")
    assert aneh.level == "P3"
    assert aneh.tanda_tangan == p3.tanda_tangan


def test_statistika_memuat_delapan_template():
    """Task 6.3 (5 template) + penambahan anti-monoton 2 Sep 2026 (3)."""
    paket = _paket()
    assert len(paket.templates) == 8
    for nama in (
        "rata_rata",
        "rata_rata_gabungan",
        "median_modus",
        "diagram_lingkaran",
        "diagram_batang_garis",
        "tabel_turus",
        "piktogram",
        "jangkauan_data",
    ):
        assert nama in paket.templates, nama


# ── Judul bagian ───────────────────────────────────────────────────────


def test_judul_bagian_statistika():
    paket = _paket()
    assert paket.judul_bagian == {
        "A": "Bagian A — Rata-rata",
        "B": "Bagian B — Median & modus, diagram",
    }


# ── Template #1 rata_rata ──────────────────────────────────────────────


def test_rata_rata_kunci():
    """#1: rata = jumlah/n; dua arah."""
    for seed in range(1, 120):
        s = buat_soal("rata_rata", seed, level="P4", topik="statistika")
        p = s.parameter
        if p["varian"] == "cari_rata":
            expected = sum(p["data"]) // len(p["data"])
        else:
            expected = p["rata"] * len(p["data"]) - sum(p["data"][:-1])
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Template #2 rata_rata_gabungan ─────────────────────────────────────


def test_rata_rata_gabungan_kunci():
    """#2: (n₁·x̄₁ + n₂·x̄₂)/(n₁+n₂)."""
    for seed in range(1, 120):
        s = buat_soal("rata_rata_gabungan", seed, level="P5", topik="statistika")
        p = s.parameter
        expected = (p["n1"] * p["x1"] + p["n2"] * p["x2"]) // (p["n1"] + p["n2"])
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Template #3 median_modus ───────────────────────────────────────────


def test_median_modus_kunci():
    """#3: median (urut) & modus (paling sering)."""
    for seed in range(1, 120):
        s = buat_soal("median_modus", seed, level="P4", topik="statistika")
        p = s.parameter
        data = p["data"]
        if p["varian"] == "median":
            urut = sorted(data)
            n = len(data)
            if n % 2 == 1:
                expected = str(urut[n // 2])
            else:
                jumlah_tengah = urut[n // 2 - 1] + urut[n // 2]
                if jumlah_tengah % 2 == 0:
                    expected = str(jumlah_tengah // 2)
                else:
                    expected = f"{jumlah_tengah // 2},5"
        else:
            from collections import Counter
            hitung = Counter(data)
            expected = str(max(hitung.items(), key=lambda kv: kv[1])[0])
        assert s.kunci == expected, f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_median_modus_p3_modus_saja():
    """P3: median tidak boleh lolos — selalu varian modus, data kecil.

    Median di atas kelas 3; band SASMO Primary 1-4 (statistics) memuat
    modus. P3: n 3-5, nilai 1-12, modus tunggal berulang tanpa posisi tetap.
    """
    from collections import Counter

    for seed in range(1, 120):
        s = buat_soal("median_modus", seed, level="P3", topik="statistika")
        p = s.parameter
        assert p["varian"] == "modus", p
        data = p["data"]
        assert 3 <= len(data) <= 5, p
        assert all(1 <= x <= 12 for x in data), p
        hitung = Counter(data)
        expected = max(hitung.items(), key=lambda kv: kv[1])[0]
        assert hitung[expected] >= 2, p
        assert sum(v == hitung[expected] for v in hitung.values()) == 1, p
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Template #4 diagram_lingkaran ──────────────────────────────────────


def test_diagram_lingkaran_kunci():
    """#4: nilai = s/360×total; balik arah cari sudut."""
    for seed in range(1, 120):
        s = buat_soal("diagram_lingkaran", seed, level="P5", topik="statistika")
        p = s.parameter
        if p["varian"] == "cari_nilai":
            expected = p["total"] * p["s"] // 360
        else:
            expected = p["nilai"] * 360 // p["total"]
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Template #5 diagram_batang_garis ───────────────────────────────────


def test_diagram_batang_garis_kunci():
    """#5: baca/jumlah/selisih dari diagram batang."""
    for seed in range(1, 120):
        s = buat_soal("diagram_batang_garis", seed, level="P4", topik="statistika")
        p = s.parameter
        data = p["data"]
        if p["varian"] == "baca":
            expected = data[p["i"]]
        elif p["varian"] == "jumlah":
            expected = sum(data)
        else:
            a, b = data[p["i"]], data[(p["i"] + 1) % len(data)]
            expected = abs(a - b)
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_diagram_batang_garis_p3_batas():
    """P3: empat batang, nilai 1-20; ketiga varian tetap boleh."""
    for seed in range(1, 120):
        s = buat_soal("diagram_batang_garis", seed, level="P3", topik="statistika")
        p = s.parameter
        assert p["varian"] in ("baca", "jumlah", "selisih"), p
        data = p["data"]
        assert len(data) == 4, p
        assert all(1 <= x <= 20 for x in data), p
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


# ── Sweep per kelompok template ────────────────────────────────────────

KELOMPOK_A = ("rata_rata", "rata_rata_gabungan")
KELOMPOK_B = ("median_modus", "diagram_lingkaran", "diagram_batang_garis")


@pytest.mark.parametrize("template_id", KELOMPOK_A)
@pytest.mark.parametrize("level", ("P4", "P5", "P6"))
def test_kelompok_a_sweep(template_id, level):
    if template_id == "rata_rata_gabungan" and level == "P4":
        return  # #2 hanya P5+
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="statistika")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}, f"{template_id}@{level}/{seed}"


@pytest.mark.parametrize("template_id", KELOMPOK_B)
@pytest.mark.parametrize("level", ("P4", "P5", "P6"))
def test_kelompok_b_sweep(template_id, level):
    if template_id == "diagram_lingkaran" and level == "P4":
        return  # #4 hanya P5+
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="statistika")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert {"K", "H"} <= {m.kode for m in s.malrule}, f"{template_id}@{level}/{seed}"

# ── Template #6-8: penambahan anti-monoton (2 Sep 2026) ────────────────
#
# Ketiganya lahir dari pengukuran, bukan selera: P3 statistika hanya
# punya 2 template, dan 3000 soal yang dibangkitkan cuma menghasilkan
# 6 bentuk kalimat berbeda. Menambah template menaikkan variasi jauh
# lebih besar daripada membungkus kalimat lewat LLM, dan tidak menambah
# biaya per soal sama sekali.


def test_tabel_turus_kunci():
    """#6: baca baris / cari terbanyak (jawaban NAMA) / jumlah."""
    for seed in range(1, 150):
        s = buat_soal("tabel_turus", seed, level="P3", topik="statistika")
        p = s.parameter
        data, nama = p["data"], p["nama"]
        if p["varian"] == "baca":
            expected = str(data[p["i"]])
        elif p["varian"] == "terbanyak":
            expected = nama[data.index(max(data))]
        else:
            expected = str(sum(data))
        assert s.kunci == expected, f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K"} <= {m.kode for m in s.malrule}, p


def test_tabel_turus_terbanyak_selalu_tunggal():
    """Kalau dua baris seri, soal tidak punya SATU jawaban benar dan
    malrule 'terbanyak kedua' justru menebak kunci."""
    for seed in range(1, 200):
        s = buat_soal("tabel_turus", seed, level="P3", topik="statistika")
        if s.parameter["varian"] != "terbanyak":
            continue
        data = s.parameter["data"]
        assert data.count(max(data)) == 1, s.parameter


def test_piktogram_kunci_memakai_skala():
    """#7: nilai = banyak gambar × nilai satu gambar.

    Miskonsepsi khasnya (menjawab banyaknya gambar, lupa dikali skala)
    tidak tersedia di template diagram batang — jadi template ini
    menambah jalur DIAGNOSIS baru, bukan sekadar kalimat baru.
    """
    for seed in range(1, 150):
        s = buat_soal("piktogram", seed, level="P4", topik="statistika")
        p = s.parameter
        g, satuan = p["gambar"], p["satuan"]
        if p["varian"] == "baca":
            expected = g[p["i"]] * satuan
        elif p["varian"] == "total":
            expected = sum(g) * satuan
        else:
            a, b = g[p["i"]], g[(p["i"] + 1) % len(g)]
            expected = abs(a - b) * satuan
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_piktogram_malrule_lupa_skala_selalu_ada():
    """Justifikasi template ini adalah malrule 'lupa dikali skala'.
    Kalau ia tersaring, template hanya menambah kalimat tanpa diagnosis."""
    for seed in range(1, 120):
        s = buat_soal("piktogram", seed, level="P3", topik="statistika")
        assert any(m.id == "pikto.lupa_skala" for m in s.malrule), s.parameter


def test_jangkauan_data_kunci():
    """#8: terbesar / terkecil / jangkauan = terbesar − terkecil."""
    for seed in range(1, 150):
        s = buat_soal("jangkauan_data", seed, level="P3", topik="statistika")
        p = s.parameter
        data = p["data"]
        if p["varian"] == "terbesar":
            expected = max(data)
        elif p["varian"] == "terkecil":
            expected = min(data)
        else:
            expected = max(data) - min(data)
        assert s.kunci == str(expected), f"{p=}, kunci={s.kunci}"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert {"K", "H"} <= {m.kode for m in s.malrule}, p


def test_jangkauan_data_ekstrem_tunggal():
    """Terbesar & terkecil wajib tunggal dan berbeda — kalau seri,
    malrule 'terbesar kedua' bertabrakan dengan kunci lalu terbuang."""
    for seed in range(1, 200):
        s = buat_soal("jangkauan_data", seed, level="P3", topik="statistika")
        data = s.parameter["data"]
        assert data.count(max(data)) == 1, s.parameter
        assert data.count(min(data)) == 1, s.parameter
        assert max(data) != min(data), s.parameter


def test_p3_angka_tetap_ramah_kelas_tiga():
    """Template baru tidak boleh menyelundupkan angka besar ke P3."""
    for seed in range(1, 120):
        for s in buat_lembar(seed, level="P3", topik="statistika").soal:
            p = s.parameter
            if s.template_id == "tabel_turus":
                assert all(1 <= x <= 9 for x in p["data"]), p
            elif s.template_id == "piktogram":
                assert p["satuan"] in (2, 5, 10), p
                assert all(1 <= x <= 6 for x in p["gambar"]), p
            elif s.template_id == "jangkauan_data":
                assert all(1 <= x <= 20 for x in p["data"]), p


def test_p3_variasi_kalimat_naik_tajam():
    """Pengunci alasan seluruh perubahan ini.

    Baseline sebelum penambahan (diukur 2 Sep 2026): 3000 soal P3
    statistika hanya melahirkan 6 bentuk kalimat berbeda — anak yang
    berlatih tiap hari membaca bunyi soal yang sama terus, cuma
    angkanya ganti. Yang diukur: kalimat soal dengan seluruh angka
    dinormalkan jadi 'N'.
    """
    import re

    bentuk = set()
    for seed in range(300):
        for s in buat_lembar(seed, level="P3", topik="statistika").soal:
            bentuk.add(re.sub(r"-?\d+(?:[.,]\d+)?", "N", s.teks))
    assert len(bentuk) >= 20, (
        f"P3 statistika cuma {len(bentuk)} bentuk kalimat (baseline lama 6) "
        "— penambahan template tidak memperbaiki monoton"
    )


@pytest.mark.parametrize(
    "template_id", ("tabel_turus", "piktogram", "jangkauan_data")
)
@pytest.mark.parametrize("level", ("P3", "P4", "P5", "P6"))
def test_template_baru_sweep(template_id, level):
    for seed in range(1, 120):
        s = buat_soal(template_id, seed, level=level, topik="statistika")
        assert s.malrule, f"{template_id}@{level}/{seed} kosong"
        assert s.kunci not in [m.jawaban for m in s.malrule]
        assert s.pembahasan.strip(), f"{template_id}@{level}/{seed}"

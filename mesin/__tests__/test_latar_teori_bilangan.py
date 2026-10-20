"""Kebijakan latar teori-bilangan — gelombang 2, Langkah 3.

Seluruh 8 template paket ini punya <= 2 bentuk kalimat, tapi HANYA SATU
yang diberi latar. Berkas ini mengunci keputusan itu beserta batasnya,
supaya "kenapa yang lain tidak" tidak perlu ditemukan ulang nanti.

Kebijakannya (keputusan pemilik produk 2 Sep 2026): latar cerita hanya
untuk template yang memang bercerita. "Berapa KPK dari 190 dan 108?"
adalah perintah hitung murni, dan begitu juga "Manakah dari bilangan 84,
85, dan 90 yang habis dibagi 3?" — membungkusnya jadi cerita mengaburkan
konsep yang sedang diuji tanpa menambah satu pun kemampuan yang dinilai.

KPK lolos karena ceritanya bukan bungkus: "lampu berkedip tiap N detik,
kapan berkedip bersamaan" adalah bentuk soal KPK yang sudah baku di buku
dan di naskah OSN — ia bagian dari konsepnya sendiri (kejadian berulang
yang bertemu).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator import buat_lembar, buat_soal  # noqa: E402

HITUNG_MURNI = (
    "keterbagian",
    "sisa_pembagian",
    "paritas",
    "prima_faktorisasi",
    "gauss_deret",
    "angka_satuan_pangkat",
    "fpb_kpk_hubungan",
    "banyak_kelipatan", "sisa_operasi", "banyak_prima", "jumlah_kelipatan",
)

LEVEL_UJI = {
    "angka_satuan_pangkat": "P6",
    "fpb_kpk_hubungan": "P6",
    "gauss_deret": "P5",
    "prima_faktorisasi": "P5",
}


def _soal(template_id: str, seed: int, level: str | None = None):
    return buat_soal(
        template_id,
        seed,
        level=level or LEVEL_UJI.get(template_id, "P4"),
        topik="teori-bilangan",
    )


def _pola(teks: str) -> str:
    return re.sub(r"-?\d+(?:[.,]\d+)?", "N", teks)


def test_kpk_punya_latar_berputar():
    """Satu-satunya template paket ini yang diberi latar."""
    bentuk = {
        _pola(_soal("kpk_dua_bilangan", seed, "P5").teks) for seed in range(1, 200)
    }
    assert len(bentuk) >= 4, f"kpk cuma {len(bentuk)} bentuk"


def test_kpk_tetap_punya_bentuk_perintah_murni():
    """Anak tetap harus pernah diminta menyebut KPK dengan namanya.

    Kalau semua soal jadi cerita, "KPK" tidak pernah lagi muncul sebagai
    istilah — anak bisa mengerjakan soalnya tapi tidak mengenali namanya
    saat guru menyebutnya di kelas.
    """
    ada_murni = any(
        _soal("kpk_dua_bilangan", seed, "P5").teks.startswith("Berapa KPK")
        for seed in range(1, 100)
    )
    assert ada_murni, "bentuk perintah murni hilang seluruhnya"


def test_kpk_latar_deterministik_atas_parameter():
    """Latar HARUS turunan parameter — kontrak cetak ulang bank soal."""
    from templates import REGISTRI

    fn = REGISTRI["kpk_dua_bilangan"]
    for seed in range(1, 60):
        asli = _soal("kpk_dua_bilangan", seed, "P5")
        ulang = fn(**asli.parameter)
        assert ulang.teks == asli.teks, asli.parameter
        assert ulang.kunci == asli.kunci
    for seed in range(1, 60):
        assert set(_soal("kpk_dua_bilangan", seed, "P5").parameter) == {"a", "b"}


def test_kpk_pembahasan_menyebut_kpk():
    """Soal versi cerita tidak menyebut kata "KPK", jadi pembahasannya
    yang harus menjelaskan dari mana KPK datang — kalau tidak, anak
    membaca rumus yang tidak ia tahu asalnya."""
    for seed in range(1, 100):
        s = _soal("kpk_dua_bilangan", seed, "P5")
        assert "KPK" in s.pembahasan, s.pembahasan


@pytest.mark.parametrize("template_id", HITUNG_MURNI)
def test_hitung_murni_tidak_dibungkus_cerita(template_id):
    """Pengunci KEPUTUSAN, bukan mekanisme.

    Ini test yang sengaja menolak "perbaikan": kalau nanti seseorang
    membungkus keterbagian atau sisa_pembagian dengan cerita demi
    menaikkan angka metrik, test ini gagal dan memaksa keputusan itu
    dibicarakan lagi. Angka metrik bukan tujuan; kejelasan soal iya.
    """
    penanda_cerita = (
        "Pak ", "Bu ", "sebuah toko", "berkedip", "berangkat",
        "membeli", "menjual", "sekolah", "kelas",
    )
    for seed in range(1, 80):
        teks = _soal(template_id, seed).teks
        for tanda in penanda_cerita:
            assert tanda not in teks, f"{template_id} dibungkus cerita: {teks}"


def test_batas_jujur_teori_bilangan_p4():
    """P4 kini tujuh jenis; jangan mengejar 25 kalimat dengan cerita buatan."""
    from topics import ambil
    assert len(set(ambil("teori-bilangan").komposisi["P4"])) >= 7
    bentuk = set()
    for seed in range(300):
        for s in buat_lembar(seed, level="P4", topik="teori-bilangan").soal:
            bentuk.add(_pola(s.teks))
    assert len(bentuk) >= 8, f"P4 turun jadi {len(bentuk)} bentuk"
    assert len(bentuk) < 25, (
        "P4 sudah melewati ambang — bagus, perbarui test ini dan README "
        "(batas yang diketahui) supaya catatannya tidak menyesatkan"
    )


@pytest.mark.parametrize("level,baseline", (("P5", 7), ("P6", 7)))
def test_bentuk_kalimat_p5_p6_naik(level, baseline):
    """P5/P6 memuat KPK, jadi keduanya ikut naik — meski tetap di bawah
    25 karena template lainnya memang hitung murni."""
    bentuk = set()
    for seed in range(300):
        for s in buat_lembar(seed, level=level, topik="teori-bilangan").soal:
            bentuk.add(_pola(s.teks))
    assert len(bentuk) > baseline, (
        f"teori-bilangan {level}: {len(bentuk)} bentuk, baseline {baseline}"
    )

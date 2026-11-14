"""Komposer Paket Tes Diagnostik Baku Berpasangan (Modul 1).

Menyusun baterai soal diagnostik terstruktur per jenjang (P1–P6) dengan dua
prinsip ketajaman:
1. Tahap triase prasyarat di butir-butir awal (fondasi berhitung sebelum soal inti).
2. Minimal 2 soal berpasangan per sub-konsep dengan tanda tangan (parameter/varian)
   berbeda sehingga salah konsep konsisten tidak tercampur dengan terpeleset 1 butir.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from generator import Lembar
from templates import LEVEL, Soal
import topics


@dataclass(frozen=True)
class SpesifikasiPasangan:
    template_id: str
    judul_ramah: str
    triase: bool = False
    domain_ramah: str = "Hitung Dasar"


BATERAI_JENJANG: dict[str, tuple[SpesifikasiPasangan, ...]] = {
    "P1": (
        SpesifikasiPasangan("tambah_dasar", "Penjumlahan sampai 10", True, "Hitung Dasar"),
        SpesifikasiPasangan("kurang_dasar", "Pengurangan sampai 10", True, "Hitung Dasar"),
        SpesifikasiPasangan("bilangan_hilang", "Bilangan yang hilang", False, "Pola Bilangan"),
        SpesifikasiPasangan("nilai_tempat", "Puluhan dan satuan", False, "Hitung Dasar"),
        SpesifikasiPasangan("bandingkan_bilangan", "Membandingkan bilangan", False, "Hitung Dasar"),
    ),
    "P2": (
        SpesifikasiPasangan("tambah_dasar", "Penjumlahan sampai 20", True, "Hitung Dasar"),
        SpesifikasiPasangan("kurang_dasar", "Pengurangan sampai 20", True, "Hitung Dasar"),
        SpesifikasiPasangan("bilangan_hilang", "Bilangan yang hilang", False, "Pola Bilangan"),
        SpesifikasiPasangan("nilai_tempat", "Puluhan dan satuan", False, "Hitung Dasar"),
        SpesifikasiPasangan("bandingkan_bilangan", "Membandingkan bilangan", False, "Hitung Dasar"),
    ),
    "P3": (
        SpesifikasiPasangan("perkalian_dasar", "Perkalian dasar kelas 3", True, "Hitung Dasar"),
        SpesifikasiPasangan("pembagian_dasar", "Pembagian sama rata", True, "Hitung Dasar"),
        SpesifikasiPasangan("nilai_tempat_ribuan", "Nilai tempat ratusan", True, "Hitung Dasar"),
        SpesifikasiPasangan("pecahan_bagian_dasar", "Pecahan sederhana", False, "Pecahan"),
        SpesifikasiPasangan("keliling_luas_datar", "Keliling persegi panjang", False, "Keliling & Luas"),
        SpesifikasiPasangan("luas_kotak_satuan", "Luas kotak satuan", False, "Keliling & Luas"),
        SpesifikasiPasangan("diagram_batang_garis", "Membaca diagram batang", False, "Tabel & Grafik"),
        SpesifikasiPasangan("piktogram", "Membaca piktogram berskala", False, "Tabel & Grafik"),
        SpesifikasiPasangan("deret_aritmetika", "Melanjutkan pola bilangan", False, "Pola Bilangan"),
        SpesifikasiPasangan("soal_uang", "Soal cerita uang & selisih", False, "Logika Cerita"),
    ),
    "P4": (
        SpesifikasiPasangan("perkalian_dasar", "Perkalian bersusun kelas 4", True, "Hitung Dasar"),
        SpesifikasiPasangan("pembagian_dasar", "Pembagian rata kelas 4", True, "Hitung Dasar"),
        SpesifikasiPasangan("pecahan_bagian_dasar", "Pecahan dasar kelas 4", True, "Pecahan"),
        SpesifikasiPasangan("nilai_tempat_ribuan", "Nilai tempat ribuan", False, "Hitung Dasar"),
        SpesifikasiPasangan("jam_selesai", "Menghitung waktu & jam selesai", False, "Satuan Waktu"),
        SpesifikasiPasangan("satuan_kuantitas", "Satuan lusin, kodi, rim", False, "Satuan Waktu"),
        SpesifikasiPasangan("keliling_luas_datar", "Keliling vs luas persegi panjang", False, "Keliling & Luas"),
        SpesifikasiPasangan("luas_segitiga_jajargenjang", "Luas segitiga & jajargenjang", False, "Keliling & Luas"),
        SpesifikasiPasangan("diagram_batang_garis", "Membaca diagram batang/garis", False, "Tabel & Grafik"),
        SpesifikasiPasangan("rata_rata", "Rata-rata sederhana", False, "Tabel & Grafik"),
        SpesifikasiPasangan("deret_aritmetika", "Pola barisan naik", False, "Pola Bilangan"),
        SpesifikasiPasangan("keterbagian", "Ciri habis dibagi", False, "Pola Bilangan"),
    ),
    "P5": (
        SpesifikasiPasangan("urutan_operasi_1", "Urutan operasi hitung", True, "Hitung Dasar"),
        SpesifikasiPasangan("pecahan_operasi_campuran", "Operasi pecahan beda penyebut", True, "Pecahan"),
        SpesifikasiPasangan("tangga_satuan_campuran", "Konversi satuan panjang/massa", True, "Satuan Waktu"),
        SpesifikasiPasangan("operasi_berkurung", "Operasi bertanda kurung", False, "Hitung Dasar"),
        SpesifikasiPasangan("urut_pecahan_desimal_persen", "Menyetarakan pecahan, desimal, persen", False, "Pecahan"),
        SpesifikasiPasangan("jam_selesai", "Durasi & waktu selesai", False, "Satuan Waktu"),
        SpesifikasiPasangan("keliling_luas_datar", "Keliling & balik luas segiempat", False, "Keliling & Luas"),
        SpesifikasiPasangan("lingkaran_keliling_luas", "Keliling & luas lingkaran", False, "Keliling & Luas"),
        SpesifikasiPasangan("rata_rata", "Rata-rata & nilai hilang", False, "Tabel & Grafik"),
        SpesifikasiPasangan("median_modus", "Median & modus data", False, "Tabel & Grafik"),
        SpesifikasiPasangan("kpk_dua_bilangan", "Kelipatan persekutuan terkecil", False, "Pola Bilangan"),
        SpesifikasiPasangan("persen_diskon", "Persen & potongan harga", False, "Pecahan"),
    ),
    "P6": (
        SpesifikasiPasangan("pecahan_kali_bagi", "Perkalian & pembagian pecahan", True, "Pecahan"),
        SpesifikasiPasangan("pembulatan_taksiran", "Pembulatan & penaksiran", True, "Hitung Dasar"),
        SpesifikasiPasangan("skala_peta", "Skala & jarak peta", True, "Satuan Waktu"),
        SpesifikasiPasangan("kecepatan_jarak_waktu", "Kecepatan, jarak, waktu", False, "Satuan Waktu"),
        SpesifikasiPasangan("perbandingan_senilai", "Perbandingan senilai", False, "Pecahan"),
        SpesifikasiPasangan("persen_untung_rugi", "Persentase untung & rugi", False, "Pecahan"),
        SpesifikasiPasangan("luas_arsiran", "Luas daerah arsiran", False, "Keliling & Luas"),
        SpesifikasiPasangan("volume_prisma_tabung", "Volume prisma & tabung", False, "Keliling & Luas"),
        SpesifikasiPasangan("rata_rata_gabungan", "Rata-rata gabungan", False, "Tabel & Grafik"),
        SpesifikasiPasangan("diagram_lingkaran", "Membaca diagram lingkaran", False, "Tabel & Grafik"),
        SpesifikasiPasangan("fpb_kpk_hubungan", "Hubungan FPB dan KPK", False, "Pola Bilangan"),
        SpesifikasiPasangan("kombinasi_pilih", "Memilih kelompok kemungkinan", False, "Pola Bilangan"),
    ),
}


def daftar_spesifikasi(level: str) -> tuple[SpesifikasiPasangan, ...]:
    """Kembalikan daftar pasangan probe untuk jenjang P1–P6."""
    if level not in LEVEL:
        raise ValueError(f"jenjang diagnostik tidak dikenal: {level!r}")
    return BATERAI_JENJANG[level]


def _varian_untuk(soal: Soal):
    return soal.parameter.get("varian") or soal.parameter.get("bentuk")


def _ambil_butir_unik(
    paket: topics.Topik,
    template_id: str,
    level: str,
    rng: random.Random,
    tanda_terpakai: set[str],
    hindari_varian=None,
) -> Soal:
    """Undi 1 butir yang tanda tangannya belum ada di lembar, usahakan beda varian bila kedua."""
    fn = paket.templates[template_id]
    param_fn = paket.parameter_untuk
    cadangan: Soal | None = None
    for _ in range(48):
        param = param_fn(template_id, rng, level) if param_fn else {}
        soal = replace(fn(**param), level=level)
        if soal.tanda_tangan in tanda_terpakai:
            continue
        if hindari_varian is not None and _varian_untuk(soal) == hindari_varian:
            if cadangan is None:
                cadangan = soal
            continue
        return soal
    if cadangan is not None:
        return cadangan
    # Terakhir: tetap hasilkan butir sah dari template tersebut
    param = param_fn(template_id, rng, level) if param_fn else {}
    return replace(fn(**param), level=level)


def bangun_lembar_diagnostik(seed: int, level: str) -> tuple[topics.Topik, Lembar, tuple[str, ...]]:
    """Susun lembar Tes Diagnostik Baku berpasangan (triase awal + 2 probe per konsep)."""
    specs = daftar_spesifikasi(level)
    urutan = tuple(tid for spec in specs for tid in (spec.template_id, spec.template_id))
    paket = topics.paket_untuk_template(urutan)
    tanda_terpakai: set[str] = set()
    butir: list[Soal] = []

    for idx, spec in enumerate(specs):
        rng1 = random.Random(seed * 131 + idx * 17 + 1)
        s1 = _ambil_butir_unik(paket, spec.template_id, level, rng1, tanda_terpakai)
        tanda_terpakai.add(s1.tanda_tangan)
        butir.append(s1)

        rng2 = random.Random(seed * 131 + idx * 17 + 9)
        s2 = _ambil_butir_unik(
            paket,
            spec.template_id,
            level,
            rng2,
            tanda_terpakai,
            hindari_varian=_varian_untuk(s1),
        )
        tanda_terpakai.add(s2.tanda_tangan)
        butir.append(s2)

    return paket, Lembar(seed=seed, soal=tuple(butir), level=level), urutan

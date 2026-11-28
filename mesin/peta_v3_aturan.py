"""Aturan deterministik laporan Peta versi 3 (F6): status per materi dan status perilaku belajar.

Murni: tanpa DB, tanpa token, tanpa jam. Ambang bernama di sini dan dipakai langsung oleh renderer.
Status materi memakai ambang yang sama dengan `cek_gratis_skor`: rasio benar >= `AMBANG_KUAT` berarti Dikuasai,
rasio <= `AMBANG_PERLU` berarti Belum dikuasai, dan di antaranya Perlu diperkuat. Rasio dihitung sebagai pecahan
tepat (bukan persen dibulatkan), jadi 4/5 tepat di batas Dikuasai dan 2/4 tepat di batas Belum dikuasai.
Status perilaku berupa pasangan (label, nada): nada "baik" atau "perhatian" menentukan warna, label tetap berteks.
"""
from __future__ import annotations

from fractions import Fraction

import cek_gratis_skor as skor
import peta_laporan_snapshot as snap

STATUS_DIKUASAI = "Dikuasai"
STATUS_PERLU = "Perlu diperkuat"
STATUS_BELUM = "Belum dikuasai"
URUTAN_STATUS = (STATUS_DIKUASAI, STATUS_PERLU, STATUS_BELUM)

NADA_BAIK = "baik"
NADA_PERHATIAN = "perhatian"

JENDELA_AKHIR_SOAL = 5  # jumlah soal terakhir yang dibaca untuk "fokus sampai akhir"
AMBANG_FOKUS_AKHIR = 3  # benar di jendela akhir >= nilai ini (atau semua bila jendela lebih kecil) -> Stabil
AMBANG_TEBAK_CEPAT = 2  # jawaban salah yang dijawab di bawah ambang detik >= nilai ini -> Cenderung menebak
AMBANG_PERIKSA_ULANG = 3  # total jawaban yang diganti >= nilai ini -> Sering memeriksa


def status_materi(benar: int, total: int) -> str:
    """Status satu materi dari rasio benar; `total` wajib >= 1 (dijamin `periksa_isi`)."""
    rasio = Fraction(benar, total)
    if rasio >= skor.AMBANG_KUAT:
        return STATUS_DIKUASAI
    if rasio <= skor.AMBANG_PERLU:
        return STATUS_BELUM
    return STATUS_PERLU


def _urut_materi_kunci(butir: dict) -> tuple:
    """Urut dari yang paling perlu dilatih (rasio naik), lalu nama; sama dengan urutan `perlu_dilatih`."""
    return (Fraction(butir["benar"], butir["total"]), butir["materi"])


def daftar_materi_berstatus(per_materi) -> list:
    """Salinan per materi dengan kunci `status`, diurut dari yang paling perlu dilatih."""
    return [{**m, "status": status_materi(m["benar"], m["total"])}
            for m in sorted(per_materi, key=_urut_materi_kunci)]


def status_ketekunan(dilewati: int) -> tuple:
    """Ketekunan: tidak ada soal yang dilewati berarti kuat."""
    if dilewati == 0:
        return ("Kuat", NADA_BAIK)
    return ("Perlu perhatian", NADA_PERHATIAN)


def benar_di_akhir(soal) -> tuple:
    """(benar, jendela): jumlah benar pada `JENDELA_AKHIR_SOAL` soal terakhir dan ukuran jendelanya."""
    jendela = soal[-JENDELA_AKHIR_SOAL:]
    return sum(1 for butir in jendela if butir["benar"] == 1), len(jendela)


def status_fokus_akhir(benar: int, jendela: int) -> tuple:
    """Fokus sampai akhir: jendela kecil (kurang dari ambang) harus benar semua agar dianggap stabil."""
    if jendela and benar >= min(AMBANG_FOKUS_AKHIR, jendela):
        return ("Stabil", NADA_BAIK)
    return ("Perlu perhatian", NADA_PERHATIAN)


def status_saat_sulit(jumlah_cepat: int) -> tuple:
    """Saat soal sulit: hitungan jawaban salah yang dijawab terlalu cepat (lihat `snap.AMBANG_CEPAT_DETIK`)."""
    if jumlah_cepat >= AMBANG_TEBAK_CEPAT:
        return ("Cenderung menebak", NADA_PERHATIAN)
    if jumlah_cepat == 0:
        return ("Tenang", NADA_BAIK)
    return ("Perlu perhatian", NADA_PERHATIAN)


def status_periksa_ulang(total_ganti: int) -> tuple:
    """Memeriksa ulang: sering bila jawaban yang diganti cukup banyak; selain itu jarang."""
    if total_ganti >= AMBANG_PERIKSA_ULANG:
        return ("Sering memeriksa", NADA_BAIK)
    return ("Jarang", NADA_PERHATIAN)


def terlalu_cepat(butir: dict) -> bool:
    """Jawaban salah yang diisi kurang dari `snap.AMBANG_CEPAT_DETIK` detik (predikat yang sama dengan snapshot)."""
    return bool(butir["dijawab"] and butir["benar"] == 0 and butir["detik"] is not None
                and butir["detik"] < snap.AMBANG_CEPAT_DETIK)


def soal_cepat_di_materi_lemah(soal, daftar_berstatus) -> tuple:
    """(lemah, semua_dikenal): jumlah soal terlalu cepat di materi Belum dikuasai, dan apakah semua punya nama materi.

    Nama materi soal dan `per_materi` berasal dari sumber yang sama (`topik_awam.nama`), jadi cocok dengan status.
    """
    status_per_nama = {m["materi"]: m["status"] for m in daftar_berstatus}
    cepat = [butir for butir in soal if terlalu_cepat(butir)]
    lemah = sum(1 for butir in cepat if status_per_nama.get(butir["materi"]) == STATUS_BELUM)
    semua_dikenal = all(butir["materi"] in status_per_nama for butir in cepat)
    return lemah, semua_dikenal

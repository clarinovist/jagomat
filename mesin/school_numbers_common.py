"""Alat bersama jenis soal Bilangan Sekolah (teks angka saja, tanpa gambar).

Hanya fungsi murni: pemformat titik ribuan, nama tempat, dan perangkai daftar
kalimat. Tidak ada aturan soal di sini; tiap jenis punya modul sendiri.
"""
from __future__ import annotations

KALI = "×"
BAGI = "÷"
KURANG = "−"
NAMA_TEMPAT = ("satuan", "puluhan", "ratusan", "ribuan", "puluhan ribu", "ratusan ribu")
BATAS_UNDI = 400  # percobaan sampler; rng yang sama, jadi penolakan tetap deterministik


def ribuan(n: int) -> str:
    """Titik ribuan gaya Indonesia untuk teks; kunci dan malrule tetap angka polos."""
    return f"{n:,}".replace(",", ".")


def digit(bilangan: int, posisi: int) -> int:
    """Angka pada pangkat sepuluh `posisi` (0 = satuan)."""
    return bilangan // 10 ** posisi % 10


def kolom(bilangan: int) -> list:
    """Angka-angka bilangan dari satuan ke tempat tertinggi."""
    return [int(c) for c in reversed(str(bilangan))]


def dari_kolom(isi: list) -> int:
    """Kebalikan `kolom`: angka dari satuan ke tertinggi menjadi satu bilangan."""
    return int("".join(str(d) for d in reversed(isi)))


def gabung(daftar) -> str:
    """'a dan b' atau 'a, b, dan c' untuk kalimat Indonesia."""
    daftar = [str(x) for x in daftar]
    if len(daftar) <= 2:
        return " dan ".join(daftar)
    return ", ".join(daftar[:-1]) + ", dan " + daftar[-1]


def bilangan_bulat(nilai) -> bool:
    """True hanya untuk int murni (bool, float, dan teks ditolak)."""
    return type(nilai) is int

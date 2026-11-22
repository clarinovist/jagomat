"""Potongan HTML bersama halaman anak Latihan Lomba: tautan beranda, maskot, hitung mundur, target harian.

Dipakai halaman awal, konfirmasi, hasil, dan kartu beranda murid. Murni render (tanpa DB, tanpa skrip);
semua teks yang berasal dari luar di-escape. CSS-nya ada di `contest_style` (GAYA_LOMBA/GAYA_AWAL/GAYA_BERANDA).
"""
from __future__ import annotations

import html

import brand

ALAMAT_BERANDA = "/murid"
UKURAN_MASKOT = 96
_PERSEN_PENUH = 100


def bilah_beranda() -> str:
    """Bilah atas dengan satu tautan kembali ke beranda murid."""
    return (f'<header class="bilah-atas"><a class="tautan-beranda" href="{ALAMAT_BERANDA}">'
            '<span aria-hidden="true">←</span>&nbsp;Beranda</a></header>')


def maskot_kartu(pose: str) -> str:
    """Maskot hiasan (alt kosong) untuk kepala kartu."""
    return brand.maskot(pose, UKURAN_MASKOT, kelas="maskot-kartu")


def blok_hitung_mundur(teks: str) -> str:
    """Kalimat hitung mundur; kosong bila tidak perlu tampil."""
    return f'<p class="hitung-mundur">{html.escape(teks)}</p>' if teks else ""


def persen_target(selesai: int, target: int) -> int:
    """Persen bar target, dibatasi 0-100; 0 bila target 0."""
    if target <= 0:
        return 0
    return max(0, min(_PERSEN_PENUH, selesai * _PERSEN_PENUH // target))


def blok_target(selesai: int, target: int) -> str:
    """"Latihan hari ini: 1 dari 2" + bar progres (div berlebar persen, tanpa JS); kosong bila target 0."""
    if target <= 0:
        return ""
    capai = ('<p class="target-capai">Target hari ini tercapai!</p>' if selesai >= target else "")
    return (f'<div class="target"><p class="target-teks">Latihan hari ini: {int(selesai)} dari {int(target)}</p>'
            f'<div class="bar-target" role="progressbar" aria-label="Latihan hari ini" aria-valuemin="0" '
            f'aria-valuemax="{int(target)}" aria-valuenow="{min(int(selesai), int(target))}">'
            f'<div class="bar-target-isi" style="width:{persen_target(selesai, target)}%"></div></div>{capai}</div>')

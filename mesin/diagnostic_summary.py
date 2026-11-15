"""Ringkasan Analisis Pasangan Diagnostik untuk halaman tinjauan guru.

Konsumen read-only dari `diagnosis.evaluasi_pasangan_diagnostik`: hanya sesi
dengan komposisi Tes Diagnostik Baku yang exact dan hanya peran guru/admin.
Tidak menulis bukti, tidak mengubah diagnosis, dan tidak merender kode,
malrule, skor, level, atau alasan internal ke permukaan lain.
"""
from __future__ import annotations

import html

import diagnosis
import diagnostic_battery
from templates import LEVEL

# Label awam untuk guru; kode B/K/H/E/T/N dan malrule_id sengaja tidak tampil.
LABEL_STATUS = {
    "kuat": "Sudah kuat",
    "konsisten_k": "Perlu pendalaman konsep",
    "konsep_awal": "Konsep mulai terbentuk, perlu dicek lagi",
    "teliti": "Perlu ketelitian",
    "tebak": "Perlu ditanya lisan",
    "belum_diajari": "Materi belum dikenalkan",
    "belum_dinilai": "Belum dinilai",
}

CATATAN_TRIASE = (
    "Triase prasyarat belum kuat. Turunkan fokus ke fondasi berhitung sebelum "
    "melanjutkan ke konsep berikutnya."
)


def _kolom(baris, nama, bawaan=None):
    if isinstance(baris, dict):
        return baris.get(nama, bawaan)
    try:
        return baris[nama]
    except (IndexError, KeyError):
        return bawaan


def _peran_diizinkan(peran: str) -> bool:
    """Guard palang murid: ringkasan ini hanya untuk guru/admin."""
    return peran in ("guru", "admin")


def urutan_baterai(level: str):
    """Komposisi exact sesi Tes Diagnostik Baku untuk satu jenjang."""
    if level not in LEVEL:
        return None
    return tuple(
        spec.template_id
        for spec in diagnostic_battery.daftar_spesifikasi(level)
        for _ in range(2)
    )


def sesi_baterai(butir, level: str) -> bool:
    """Guard: hanya ringkas sesi berpasangan exact, bukan sesi biasa/remedial."""
    harapan = urutan_baterai(level)
    if harapan is None:
        return False
    return tuple(_kolom(b, "template_id", "") for b in butir) == harapan


def ringkasan(butir, level: str, peran: str) -> str:
    """HTML ringkasan per sub-konsep; string kosong bila tidak berlaku."""
    if not _peran_diizinkan(peran) or not sesi_baterai(butir, level):
        return ""
    hasil = diagnosis.evaluasi_pasangan_diagnostik(butir, level)
    baris = []
    for entri in hasil["ringkasan"]:
        label = LABEL_STATUS.get(entri.status, LABEL_STATUS["belum_dinilai"])
        awalan = " · Prasyarat" if entri.triase else ""
        baris.append(
            '<li><b>' + html.escape(str(entri.judul_ramah)) + awalan + '</b><br>'
            + html.escape(str(label)) + '</li>'
        )
    catatan = (
        '<p class="koreksi-catatan-st">' + html.escape(CATATAN_TRIASE) + '</p>'
        if hasil["triase_macet"] else ""
    )
    return (
        '<section class="koreksi-misi-st" data-ringkasan-diagnostik>'
        '<h2>Ringkasan Tes Diagnostik Baku</h2>'
        '<p class="koreksi-catatan-st">Dua butir berpasangan per sub-konsep; '
        'satu kebetulan salah tidak langsung berarti salah konsep.</p>'
        '<ul>' + "".join(baris) + '</ul>' + catatan + '</section>'
    )

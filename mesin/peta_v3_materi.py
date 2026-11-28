"""Bagian per materi laporan Peta versi 3 (F6): peta pulau, detail penguasaan, temuan utama, dan urutan belajar.

Masukan: daftar per materi berstatus (`peta_v3_aturan.daftar_materi_berstatus`), sudah diurut dari yang paling perlu
dilatih. Semua kalimat memakai nama materi dan angka dari data; tidak ada sebab atau prasyarat yang dikarang.
Bagian ini murni: tanpa DB, tanpa token, tanpa atribut style.
"""
from __future__ import annotations

import peta_ikon
import peta_laporan_ortu_pages as v1
import peta_laporan_snapshot as snap
import peta_v3_aturan as aturan
from peta_laporan_ortu_v2 import COPY_URUTAN
from peta_v3_html import e, kartu

COPY_PETA_JUDUL = "Peta Kemampuan Matematika"
COPY_PETA_URUT = "Diurutkan dari yang paling perlu dilatih dulu."
COPY_TARGET_JUDUL = "Target berikutnya"
COPY_TARGET_ISI = "Siap materi Kelas %d"
COPY_DETAIL_JUDUL = "Detail penguasaan per materi"
COPY_TEMUAN_JUDUL = "Temuan utama"
COPY_TEMUAN_SOAL = "%d dari %d soal benar."
COPY_URUTAN_JUDUL = "Urutan belajar yang disarankan"
IKON_BAWAAN = "bintang"
IKON_TARGET = "bintang"
UKURAN_IKON_PULAU = 34
TEBAL_IKON = "2.2"

# Kelas CSS per status (warna dan tepi), kata status tetap ditampilkan sebagai teks.
KELAS_STATUS = {
    aturan.STATUS_DIKUASAI: "dikuasai",
    aturan.STATUS_PERLU: "perlu",
    aturan.STATUS_BELUM: "belum",
}
FRASA_TEMUAN = {
    aturan.STATUS_DIKUASAI: "sudah cukup baik",
    aturan.STATUS_PERLU: "perlu diperkuat",
    aturan.STATUS_BELUM: "belum dikuasai",
}
SIMBOL_TEMUAN = {
    aturan.STATUS_DIKUASAI: "✓",
    aturan.STATUS_PERLU: "!",
    aturan.STATUS_BELUM: "!",
}
# Ikon peta_ikon per nama materi (nama dari `topik_awam`); materi lain jatuh ke ikon bawaan.
IKON_MATERI = {
    "Aritmetika dasar": "tambah",
    "Aritmetika lanjut": "kali",
    "Berhitung": "bagi",
    "Bilangan dasar": "buku",
    "Geometri datar": "peta",
    "Pengukuran": "cari",
    "Pola bilangan": "bintang",
    "Statistika": "lembar",
}


def _ikon(nama: str) -> str:
    return peta_ikon.ikon(IKON_MATERI.get(nama, IKON_BAWAAN), UKURAN_IKON_PULAU, TEBAL_IKON)


def _pulau(indeks: int, materi: dict) -> str:
    kelas = KELAS_STATUS[materi["status"]]
    return (f'<li class="ortu-peta-v3-pulau-st ortu-peta-v3-{kelas}-st">'
            f'<span class="ortu-peta-v3-urut-st" aria-hidden="true">{indeks}</span>'
            f'<span class="ortu-peta-v3-ikon-st">{_ikon(materi["materi"])}</span>'
            f'<span class="ortu-peta-v3-teks-st"><b>{e(materi["materi"])}</b>'
            f'<span class="ortu-peta-v3-nilai-st">{e(v1.COPY_BENAR % (materi["benar"], materi["total"]))}</span>'
            f'<span class="ortu-peta-v3-label-st">{e(materi["status"])}</span></span></li>')


def _ujung(kelas) -> str:
    """Bendera target di ujung jalur; tanpa kelas (None) tidak ada target."""
    if kelas is None:
        return ""
    return (f'<li class="ortu-peta-v3-ujung-st"><span class="ortu-peta-v3-ikon-st">'
            f'{peta_ikon.ikon(IKON_TARGET, UKURAN_IKON_PULAU, TEBAL_IKON)}</span>'
            f'<span class="ortu-peta-v3-teks-st"><b>{e(COPY_TARGET_JUDUL)}</b>'
            f'<span>{e(COPY_TARGET_ISI % kelas)}</span></span></li>')


def bagian_peta(daftar: list, kelas) -> str:
    """Peta pulau: satu pulau per materi, urut dari yang paling perlu dilatih, lalu bendera target."""
    pulau = "".join(_pulau(indeks, materi) for indeks, materi in enumerate(daftar, start=1))
    isi = (f'<p class="ortu-peta-v3-urut-teks-st">{e(COPY_PETA_URUT)}</p>'
           f'<ol class="ortu-peta-v3-jalur-st">{pulau}{_ujung(kelas)}</ol>')
    return kartu("ortu-peta-v3-h-peta", COPY_PETA_JUDUL, isi, "ortu-peta-v3-peta-st")


def _baris_detail(materi: dict) -> str:
    kelas = KELAS_STATUS[materi["status"]]
    benar, total, nama = materi["benar"], materi["total"], materi["materi"]
    meter = f'<meter class="ortu-peta-v3-meter-st" min="0" max="{total}" value="{benar}" aria-hidden="true"></meter>'
    return (f'<li class="ortu-peta-v3-baris-st ortu-peta-v3-{kelas}-st">'
            f'<span class="ortu-peta-v3-nama-st"><b>{e(nama)}</b>'
            f'<span class="ortu-peta-v3-label-st">{e(materi["status"])}</span></span>'
            f'{meter}<span class="ortu-peta-v3-angka-st">{e(v1.COPY_BENAR % (benar, total))}</span></li>')


def bagian_detail(daftar: list) -> str:
    """Penguasaan per materi: nama, status, batang `meter`, dan angka benar dari total (tanpa pola salah)."""
    baris = "".join(_baris_detail(materi) for materi in daftar)
    return kartu("ortu-peta-v3-h-detail", COPY_DETAIL_JUDUL, f'<ul class="ortu-peta-v3-detail-st">{baris}</ul>')


def _temuan(materi: dict) -> str:
    status = materi["status"]
    kelas = KELAS_STATUS[status]
    return (f'<li><span class="ortu-peta-v3-tanda-st ortu-peta-v3-tanda-{kelas}-st" aria-hidden="true">'
            f'{SIMBOL_TEMUAN[status]}</span><span><b>{e(materi["materi"])} {FRASA_TEMUAN[status]}.</b> '
            f'{e(COPY_TEMUAN_SOAL % (materi["benar"], materi["total"]))}</span></li>')


def _urut_temuan(daftar: list) -> list:
    """Dikuasai dulu, lalu Perlu diperkuat, lalu Belum dikuasai; di dalam setiap status tetap urut dari daftar."""
    return sorted(daftar, key=lambda m: aturan.URUTAN_STATUS.index(m["status"]))


def bagian_temuan(daftar: list) -> str:
    """Temuan utama: satu butir per materi (tanda berbentuk simbol, bukan warna saja)."""
    butir = "".join(_temuan(materi) for materi in _urut_temuan(daftar))
    return kartu("ortu-peta-v3-h-temuan", COPY_TEMUAN_JUDUL,
                 f'<ul class="ortu-peta-v3-temuan-st">{butir}</ul>')


def _langkah(indeks: int, materi: dict) -> str:
    kelas = KELAS_STATUS[materi["status"]]
    return (f'<li class="ortu-peta-v3-langkah-st ortu-peta-v3-{kelas}-st">'
            f'<span class="ortu-peta-v3-no-langkah-st" aria-hidden="true">{indeks}</span>'
            f'<b>{e(materi["materi"])}</b></li>')


def bagian_urutan(daftar: list) -> str:
    """Tiga langkah dari materi paling perlu dilatih (yang belum Dikuasai); kosong bila semua sudah Dikuasai."""
    langkah = [materi for materi in daftar if materi["status"] != aturan.STATUS_DIKUASAI][:snap.MAKS_DILATIH]
    if not langkah:
        return ""
    butir = "".join(_langkah(indeks, materi) for indeks, materi in enumerate(langkah, start=1))
    return kartu("ortu-peta-v3-h-urutan", COPY_URUTAN_JUDUL,
                 f'<p>{e(COPY_URUTAN)}</p><ol class="ortu-peta-v3-urutan-st">{butir}</ol>')

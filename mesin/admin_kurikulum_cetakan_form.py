"""Konversi form admin cetakan soal berpola <-> dict isi cetakan (format `cetakan_pola.validasi`). Murni, tanpa I/O.

Field form tetap: `judul`, `teks`, `pembahasan`, `kunci`, `nama` (select `ya`/`tidak`, bukan checkbox: checkbox
kosong tidak terkirim dan merusak himpunan field persis), `var_N_nama`/`var_N_min`/`var_N_max` (N = 1..4; baris
kosong semua = tidak dipakai, baris setengah terisi = galat), dan `syarat_N` (N = 1..5; kosong = tidak ada).
`kelas` dan `bab` TIDAK ada di form: pemanggil mengisinya dari tinjauan (buat) atau dari baris tersimpan (ubah).

Bilangan diurai ketat (digit ASCII saja). Galat berupa `ValueError` berbahasa Indonesia untuk Guru; pemanggil
meng-escape sebelum menampilkannya.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List

import cetakan_pola as pola

NAMA_YA = "ya"
NAMA_TIDAK = "tidak"
PILIHAN_NAMA = (NAMA_YA, NAMA_TIDAK)
BANYAK_VARIABEL = pola.MAKS_VARIABEL
BANYAK_SYARAT = pola.MAKS_SYARAT
MAKS_DIGIT = len(str(pola.BATAS_KONSTANTA))
_BIDANG_VARIABEL = ("nama", "min", "max")
_BIDANG_TETAP = ("judul", "teks", "pembahasan", "kunci", "nama")

FIELD_ISI: FrozenSet[str] = frozenset(
    _BIDANG_TETAP
    + tuple("var_%d_%s" % (no, b) for no in range(1, BANYAK_VARIABEL + 1) for b in _BIDANG_VARIABEL)
    + tuple("syarat_%d" % no for no in range(1, BANYAK_SYARAT + 1)))


def kosong() -> Dict[str, str]:
    """Nilai awal form baru: semua kosong, `nama` = tidak."""
    nilai = {nama: "" for nama in FIELD_ISI}
    nilai["nama"] = NAMA_TIDAK
    return nilai


def dari_cetakan(cetakan: pola.Cetakan) -> Dict[str, str]:
    """Nilai form terisi dari cetakan tersimpan (kebalikan `ke_isi`)."""
    nilai = kosong()
    nilai.update(judul=cetakan.judul, teks=cetakan.teks, pembahasan=cetakan.pembahasan, kunci=cetakan.kunci,
                 nama=NAMA_YA if cetakan.nama else NAMA_TIDAK)
    for no, (nama, kecil, besar) in enumerate(cetakan.variabel, start=1):
        nilai["var_%d_nama" % no], nilai["var_%d_min" % no], nilai["var_%d_max" % no] = nama, str(kecil), str(besar)
    for no, syarat in enumerate(cetakan.syarat, start=1):
        nilai["syarat_%d" % no] = syarat
    return nilai


def _satu_baris(teks: str) -> str:
    """Textarea mengirim CRLF; cetakan satu baris, jadi pindah baris menjadi spasi."""
    return teks.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _bilangan(teks: str, label: str) -> int:
    if not teks.isascii() or not teks.isdigit() or len(teks) > MAKS_DIGIT:
        raise ValueError("%s harus bilangan bulat 0 sampai %d, hanya angka (tanpa titik, koma, atau tanda)."
                         % (label, pola.BATAS_KONSTANTA))
    return int(teks)


def _variabel(data: Dict[str, str]) -> Dict[str, List[int]]:
    hasil: Dict[str, List[int]] = {}
    for no in range(1, BANYAK_VARIABEL + 1):
        nama, kecil, besar = (data["var_%d_%s" % (no, b)].strip() for b in _BIDANG_VARIABEL)
        if not (nama or kecil or besar):
            continue
        if not (nama and kecil and besar):
            raise ValueError("Variabel baris %d belum lengkap: isi nama, nilai terkecil, dan nilai terbesar, "
                             "atau kosongkan ketiganya." % no)
        if nama in hasil:
            raise ValueError("Nama variabel '%s' dipakai lebih dari satu baris." % nama)
        hasil[nama] = [_bilangan(kecil, "Nilai terkecil variabel baris %d" % no),
                       _bilangan(besar, "Nilai terbesar variabel baris %d" % no)]
    return hasil


def _nama_anak(nilai: str) -> bool:
    if nilai not in PILIHAN_NAMA:
        raise ValueError("Pilihan nama anak harus ya atau tidak.")
    return nilai == NAMA_YA


def ke_isi(data: Dict[str, str], kelas: int, bab: int) -> dict:
    """Dict isi cetakan untuk `cetakan_pola.validasi` dari nilai form; ValueError bila bentuk form tak sah.

    Hanya bentuk form yang dicek di sini (baris variabel, bilangan, pilihan nama); aturan isi cetakan
    ditegakkan `cetakan_pola.validasi` oleh store."""
    return {
        "kelas": kelas, "bab": bab,
        "judul": data["judul"], "teks": _satu_baris(data["teks"]), "pembahasan": _satu_baris(data["pembahasan"]),
        "variabel": _variabel(data), "nama": _nama_anak(data["nama"]),
        "syarat": [s for s in (data["syarat_%d" % no].strip() for no in range(1, BANYAK_SYARAT + 1)) if s],
        "kunci": data["kunci"],
    }

"""Snapshot isi laporan Peta Kemampuan untuk orang tua (D1-1): pembangun MURNI dan pemeriksa isi.

`bangun` mengubah hasil pembaca allowlist `cek_ringkasan_admin.ringkasan_untuk_order` (dipakai ulang, bukan
diduplikasi) menjadi isi laporan versi 1. Hanya bahan `ada` dengan data per materi yang diterima; selain itu
ValueError (tidak ada penebakan). Isi TANPA nama anak, kontak, teks soal, jawaban, kunci, kode diagnosis/malrule/
alasan, id sesi/soal, nama Guru, peringkat, Tantangan/Resep/Lencana, status/bahan/hari_tersisa, atau jam selesai.

`periksa_isi` adalah gerbang tunggal bentuk isi: dipakai store saat menulis dan saat membaca, dan oleh renderer
halaman orang tua kelak. Kunci harus PERSIS `KUNCI_ISI`; tipe dan batas panjang ditegakkan; hasilnya salinan baru.
"""
from __future__ import annotations

from datetime import date
from fractions import Fraction
from typing import Optional

import topik_awam
from cek_gratis_skor import waktu_baku
from cek_ringkasan_admin import BAHAN_ADA, KUNCI_HASIL

VERSI_ISI = 1
MAKS_DILATIH = 3
MAKS_MATERI = 40
MAKS_NAMA = 80
MAKS_SOAL = 200
KELAS_MIN, KELAS_MAKS = 1, 12
KUNCI_ISI = (
    "versi", "kelas", "tanggal_cek", "skor", "kategori", "jumlah_soal", "per_materi", "kuat",
    "perlu_dilatih", "ringkasan_perlu",
)
KUNCI_MATERI = ("materi", "benar", "total")
_PESAN_BAHAN = "bahan tidak tersedia"


def _nama_awam(daftar) -> list:
    """Nama topik tersimpan (bisa nama resmi lama) menjadi label awam efektif; salinan baru."""
    return [topik_awam.dari_nama_lama(nama) for nama in daftar]


def _perlu_dilatih(per_materi) -> list:
    """Maks `MAKS_DILATIH` nama materi: rasio benar terendah dulu, lalu nama; hanya yang belum penuh benar."""
    kandidat = [m for m in per_materi if m["total"] >= 1 and m["benar"] < m["total"]]
    urut = sorted(kandidat, key=lambda m: (Fraction(m["benar"], m["total"]), m["materi"]))
    return [m["materi"] for m in urut[:MAKS_DILATIH]]


def bangun(ringkasan) -> dict:
    """Isi laporan versi 1 dari hasil `ringkasan_untuk_order`; ValueError("bahan tidak tersedia") bila belum layak."""
    if not isinstance(ringkasan, dict) or set(ringkasan) != set(KUNCI_HASIL):
        raise ValueError(_PESAN_BAHAN)
    if ringkasan["bahan"] != BAHAN_ADA or not ringkasan["per_materi"] or ringkasan["skor"] is None:
        raise ValueError(_PESAN_BAHAN)
    per_materi = [{"materi": m["materi"], "benar": m["benar"], "total": m["total"]}
                  for m in ringkasan["per_materi"]]
    isi = {
        "versi": VERSI_ISI,
        "kelas": ringkasan["kelas"],
        "tanggal_cek": waktu_baku(ringkasan["selesai_pada"]).date().isoformat(),
        "skor": ringkasan["skor"],
        "kategori": ringkasan["kategori"],
        "jumlah_soal": ringkasan["jumlah_soal"],
        "per_materi": per_materi,
        "kuat": _nama_awam(ringkasan["ringkasan_kuat"]),
        "perlu_dilatih": _perlu_dilatih(per_materi),
        "ringkasan_perlu": _nama_awam(ringkasan["ringkasan_perlu"]),
    }
    return periksa_isi(isi)


def _int(nilai, kecil: int, besar: int, nama: str) -> int:
    if type(nilai) is not int or not kecil <= nilai <= besar:
        raise ValueError("%s tidak sah" % nama)
    return nilai


def _teks(nilai, nama: str) -> str:
    if type(nilai) is not str or not 1 <= len(nilai) <= MAKS_NAMA or not nilai.isprintable():
        raise ValueError("%s tidak sah" % nama)
    return nilai


def _daftar_teks(nilai, maks: int, nama: str) -> list:
    if type(nilai) is not list or len(nilai) > maks:
        raise ValueError("%s tidak sah" % nama)
    return [_teks(butir, nama) for butir in nilai]


def _materi(butir) -> dict:
    if type(butir) is not dict or set(butir) != set(KUNCI_MATERI):
        raise ValueError("per_materi tidak sah")
    total = _int(butir["total"], 1, MAKS_SOAL, "total")
    return {"materi": _teks(butir["materi"], "materi"),
            "benar": _int(butir["benar"], 0, total, "benar"), "total": total}


def _tanggal(nilai) -> str:
    if type(nilai) is not str or len(nilai) != 10:
        raise ValueError("tanggal_cek tidak sah")
    try:
        return date.fromisoformat(nilai).isoformat()
    except ValueError:
        raise ValueError("tanggal_cek tidak sah") from None


def _kelas(nilai) -> Optional[int]:
    return None if nilai is None else _int(nilai, KELAS_MIN, KELAS_MAKS, "kelas")


def periksa_isi(isi) -> dict:
    """Isi bersih (salinan baru) atau ValueError: kunci persis, tipe, batas panjang, benar <= total."""
    if type(isi) is not dict or set(isi) != set(KUNCI_ISI):
        raise ValueError("kunci isi laporan tidak sah")
    if type(isi["versi"]) is not int or isi["versi"] != VERSI_ISI:
        raise ValueError("versi isi laporan tidak dikenal")
    per_materi = isi["per_materi"]
    if type(per_materi) is not list or not 1 <= len(per_materi) <= MAKS_MATERI:
        raise ValueError("per_materi tidak sah")
    return {
        "versi": VERSI_ISI,
        "kelas": _kelas(isi["kelas"]),
        "tanggal_cek": _tanggal(isi["tanggal_cek"]),
        "skor": _int(isi["skor"], 0, 100, "skor"),
        "kategori": _teks(isi["kategori"], "kategori"),
        "jumlah_soal": _int(isi["jumlah_soal"], 1, MAKS_SOAL, "jumlah_soal"),
        "per_materi": [_materi(butir) for butir in per_materi],
        "kuat": _daftar_teks(isi["kuat"], MAKS_MATERI, "kuat"),
        "perlu_dilatih": _daftar_teks(isi["perlu_dilatih"], MAKS_DILATIH, "perlu_dilatih"),
        "ringkasan_perlu": _daftar_teks(isi["ringkasan_perlu"], MAKS_MATERI, "ringkasan_perlu"),
    }

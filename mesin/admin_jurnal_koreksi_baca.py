"""Pembacaan untuk koreksi admin atas kehadiran dan jurnal pertemuan (2b): SELECT saja, tanpa tulis, tanpa berkas.

Pertemuan diambil berdasar id TANPA filter guru (permukaan admin). Anggota dihitung seperti sisi guru: order aktif
pada `kini` dan penempatannya sudah ada pada `mulai` (`anggota_masuk_form`). Tidak ada pengunci 7 hari di sini: admin
boleh mengoreksi kapan pun setelah pertemuan mulai (keputusan Pemilik 27 Nov 2026). `susun_riwayat` adalah fungsi murni.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Dict, List, Mapping, Optional, Tuple

import guru_jadwal_baca as gjb
import guru_pertemuan_aturan as aturan
import jadwal_store as js
import kelas_dasar as dasar

_log = logging.getLogger(__name__)

JENIS_MINI = "mini"
JENIS_PRIVATE = "private"
PERTEMUAN_ID_MIN = 1
PERTEMUAN_ID_MAKS = 2 ** 63 - 1  # batas INTEGER SQLite; id di luar rentang tidak pernah sampai ke SQL
PELAKU_ADMIN = "Admin"
PELAKU_GURU_BAWAAN = "Guru"
ANAK_LAIN = "Anak lain"
LABEL_STATUS = {"hadir": "Hadir", "izin": "Izin", "tidak_hadir": "Tidak hadir"}
_PERAN_ADMIN = "admin"
_SQL_NAMA_KELOMPOK = "SELECT nama FROM jadwal_kelompok WHERE id=?"


def _id_sah(pertemuan_id) -> bool:
    return type(pertemuan_id) is int and PERTEMUAN_ID_MIN <= pertemuan_id <= PERTEMUAN_ID_MAKS


def _keterangan(mulai: str, dibatalkan: bool, waktu: str) -> Optional[str]:
    """Alasan tidak bisa dikoreksi, atau None. Dibatalkan didahulukan, lalu belum mulai. Tanpa pengunci 7 hari.

    Kedua waktu berformat baku UTC, jadi pembandingan teks sah.
    """
    if dibatalkan:
        return aturan.ALASAN_DIBATALKAN
    if mulai > waktu:
        return aturan.ALASAN_BELUM_MULAI
    return None


def _nama_kelas(kon, kelompok_id: Optional[str]) -> Optional[str]:
    if kelompok_id is None:
        return None
    baris = kon.execute(_SQL_NAMA_KELOMPOK, (kelompok_id,)).fetchone()
    return None if baris is None else baris[0]


def _anggota(kon, baris: dict, waktu: str) -> List[dict]:
    """Anggota pertemuan: `order_id` dan `siswa_id` saja, urut order_id. Memakai aturan anggota sisi guru."""
    if baris["kelompok_id"] is not None:
        daftar = gjb.anggota_kelompok_pertemuan(kon, baris["kelompok_id"], baris["mulai"], waktu)
    else:
        daftar = gjb.anggota_order_pertemuan(kon, baris["order_id"], baris["mulai"], waktu)
    return [{"order_id": a["order_id"], "siswa_id": a["siswa_id"]}
            for a in sorted(daftar, key=lambda a: a["order_id"])]


def _id_awal(baris: dict) -> str:
    return baris["kelompok_id"] if baris["kelompok_id"] is not None else baris["order_id"]


def _bentuk_pertemuan(kon, baris: dict, waktu: str) -> dict:
    kelompok_id = baris["kelompok_id"]
    return {
        "id": baris["id"],
        "jenis": JENIS_MINI if kelompok_id is not None else JENIS_PRIVATE,
        "kelompok_id": kelompok_id,
        "order_id": baris["order_id"] if kelompok_id is None else None,
        "nama_kelas": _nama_kelas(kon, kelompok_id),
        "ke": baris["ke"],
        "mulai": baris["mulai"],
        "menit": baris["menit"],
        "kunci": aturan.kunci_pertemuan(_id_awal(baris), baris["ke"]),
        "keterangan": _keterangan(baris["mulai"], bool(baris["dibatalkan"]), waktu),
        "anggota": _anggota(kon, baris, waktu),
    }


def pertemuan_untuk_koreksi(kon_jadwal, pertemuan_id, kini) -> Optional[dict]:
    """Pertemuan Mini atau Private berdasar id untuk halaman koreksi admin, atau None.

    Id di luar bilangan bulat sah (termasuk bool) dan id yang tidak ada sama-sama None, tanpa SQL. Kunci dan jenis
    sama dengan sisi guru. Hanya SELECT; `kon_jadwal` dibuka pemanggil (`jadwal_store.buka`).
    """
    if not _id_sah(pertemuan_id):
        return None
    baris = js.pertemuan_dari(kon_jadwal, pertemuan_id)
    if baris is None:
        return None
    return _bentuk_pertemuan(kon_jadwal, baris, dasar.ke_baku(kini))


def nama_anggota(kon_belajar, anggota) -> Dict[str, str]:
    """`{order_id: nama anak}` dari latihan.db (koneksi dari pemanggil, baca-saja).

    Id tak dikenal dan galat baca memakai placeholder yang sama dengan sisi guru (`guru_jadwal_baca.PLACEHOLDER_NAMA`).
    """
    try:
        nama_siswa = gjb.nama_siswa(kon_belajar, [a["siswa_id"] for a in anggota])
    except (sqlite3.Error, ValueError) as galat:
        _log.warning("nama anak tidak terbaca: %s", type(galat).__name__)
        nama_siswa = {}
    return {a["order_id"]: nama_siswa.get(a["siswa_id"], gjb.PLACEHOLDER_NAMA) for a in anggota}


# --- riwayat (fungsi murni) ---------------------------------------------------------------------

def _kunci_catatan(baris: dict) -> Tuple[str, str, str]:
    return (baris["pada"], baris["oleh"], baris["peran"])


def _kelompokkan(riwayat: Mapping) -> List[dict]:
    """Baris jurnal dan hadir yang berbagi (pada, oleh, peran) menjadi satu grup, urut (pada, oleh, peran)."""
    jurnal, hadir = riwayat["jurnal"], riwayat["hadir"]
    kunci_unik = sorted({_kunci_catatan(b) for b in jurnal + hadir})
    return [{"kunci": k,
             "jurnal": [b for b in jurnal if _kunci_catatan(b) == k],
             "hadir": [b for b in hadir if _kunci_catatan(b) == k]}
            for k in kunci_unik]


def _label_status(status: str) -> str:
    if status not in LABEL_STATUS:
        raise ValueError("Status kehadiran tidak dikenal.")
    return LABEL_STATUS[status]


def _perubahan(grup: dict, nama_order: Mapping[str, str]) -> List[str]:
    topik = [f"Topik: {aturan.label_topik(b['topik'])}" for b in grup["jurnal"]]
    anak = [(nama_order.get(b["order_id"], ANAK_LAIN), _label_status(b["status"])) for b in grup["hadir"]]
    anak_urut = sorted(anak, key=lambda pasangan: pasangan[0].casefold())
    return topik + [f"{nama}: {label}" for nama, label in anak_urut]


def _pelaku(peran: str, oleh: str, nama_guru: Mapping[str, str]) -> str:
    if peran == _PERAN_ADMIN:
        return PELAKU_ADMIN
    return nama_guru.get(oleh) or PELAKU_GURU_BAWAAN


def _entri(grup: dict, nama_order: Mapping[str, str], nama_guru: Mapping[str, str]) -> dict:
    pada, oleh, peran = grup["kunci"]
    return {"pada": pada, "peran": peran, "pelaku": _pelaku(peran, oleh, nama_guru),
            "perubahan": _perubahan(grup, nama_order)}


def susun_riwayat(riwayat: Mapping, nama_order: Mapping[str, str], nama_guru: Mapping[str, str]) -> List[dict]:
    """Riwayat untuk halaman admin: satu entri per (pada, oleh, peran), urut kronologis naik. Fungsi murni.

    `riwayat` adalah hasil `guru_pertemuan_dasar.riwayat`. Keluaran tidak memuat order_id, oleh, kunci, atau id apa pun:
    pelaku diberi nama, anak diberi nama dari `nama_order` (order tak dikenal = "Anak lain"). Masukan tidak diubah.
    """
    return [_entri(grup, nama_order, nama_guru) for grup in _kelompokkan(riwayat)]

"""Pembaca "Sesi berikutnya" untuk beranda anak: hanya SELECT, tanpa lokasi, tautan, atau id di hasil.

Pemilihan order meniru `jadwal_store.jadwal_terbaru_murid` (order AKTIF terbaru milik (akun, anak) yang punya
penempatan); kode di jadwal_store sengaja tidak diubah. Guru Mini diambil dari kelompok, guru Private dari
penempatan. Nama guru TIDAK dibaca di sini: itu tugas kartu (`jadwal_anak_kartu`).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import jadwal_dasar as jd
import kelas_dasar as dasar
import kelas_status as ks
import pesanan_dasar as d


def _tambah_menit(waktu: str, menit: int) -> str:
    return (datetime.strptime(waktu, jd.FORMAT_BAKU) + timedelta(minutes=menit)).strftime(jd.FORMAT_BAKU)


def _penempatan_order(kon, order_id: str) -> Optional[dict]:
    """Guru dan kelompok penempatan satu order, atau None bila order belum berpenempatan."""
    baris = kon.execute(
        """SELECT p.kelompok_id,p.guru_id AS guru_privat,k.guru_id AS guru_kelompok
             FROM jadwal_penempatan p LEFT JOIN jadwal_kelompok k ON k.id=p.kelompok_id
            WHERE p.order_id=?""", (order_id,)).fetchone()
    if baris is None:
        return None
    guru = baris["guru_kelompok"] if baris["kelompok_id"] is not None else baris["guru_privat"]
    return {"order_id": order_id, "kelompok_id": baris["kelompok_id"], "guru_id": guru}


def _penempatan_terbaru(kon, akun_id: str, siswa_id: int, kini: str) -> Optional[dict]:
    """Penempatan order AKTIF terbaru milik (akun, anak) ini; order aktif tanpa penempatan dilewati."""
    orders = kon.execute("SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? "
                         "ORDER BY dibuat DESC,id DESC" % ks.KOLOM_ORDER, (akun_id, siswa_id)).fetchall()
    for order in orders:
        if ks.status_dari(order, ks.fakta_order(kon, order["id"]), kini) != dasar.STATUS_AKTIF:
            continue
        penempatan = _penempatan_order(kon, order["id"])
        if penempatan is not None:
            return penempatan
    return None


def _pertemuan_penempatan(kon, penempatan: dict) -> list:
    """Semua pertemuan kelompok atau order penempatan, urut mulai lalu id (termasuk yang dibatalkan)."""
    return kon.execute("SELECT id,ke,mulai,menit,dibatalkan FROM jadwal_pertemuan "
                       "WHERE kelompok_id=? OR order_id=? ORDER BY mulai,id",
                       (penempatan["kelompok_id"], penempatan["order_id"])).fetchall()


def _sesi_mendatang(pertemuan: list, kini: str) -> Optional[sqlite3.Row]:
    """Pertemuan pertama yang tidak dibatalkan dan belum selesai (selesai = mulai + menit > kini)."""
    for sesi in pertemuan:
        if sesi["dibatalkan"]:
            continue
        if _tambah_menit(sesi["mulai"], sesi["menit"]) > kini:
            return sesi
    return None


def order_penempatan_murid(kon, akun_id, siswa_id, kini) -> Optional[str]:
    """order_id penempatan order AKTIF terbaru milik (akun, anak) ini, atau None (pemilihan sama dengan `jadwal_terbaru_murid`).

    Dipakai pembuat berkas kalender sebagai kunci UID stabil per order. Hanya SELECT.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    dasar.periksa_siswa_id(siswa_id)
    penempatan = _penempatan_terbaru(kon, akun_id, siswa_id, dasar.ke_baku(kini))
    return None if penempatan is None else penempatan["order_id"]


def sesi_berikutnya_murid(kon, akun_id, siswa_id, kini) -> Optional[dict]:
    """`{"guru_id", "ke", "mulai", "menit", "berlangsung"}` untuk sesi berikutnya anak ini, atau None.

    `akun_id` dan `siswa_id` harus dari sesi murid; order akun/anak lain tidak pernah terbaca. `berlangsung`
    True bila pertemuan sudah mulai (mulai <= kini) tetapi belum selesai.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    dasar.periksa_siswa_id(siswa_id)
    waktu = dasar.ke_baku(kini)
    penempatan = _penempatan_terbaru(kon, akun_id, siswa_id, waktu)
    if penempatan is None:
        return None
    sesi = _sesi_mendatang(_pertemuan_penempatan(kon, penempatan), waktu)
    if sesi is None:
        return None
    return {"guru_id": penempatan["guru_id"], "ke": sesi["ke"], "mulai": sesi["mulai"],
            "menit": sesi["menit"], "berlangsung": sesi["mulai"] <= waktu}

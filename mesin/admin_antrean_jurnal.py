"""Antrean admin "N pertemuan lewat tanpa jurnal" dan data halaman `/admin/jadwal/jurnal` (SELECT saja).

Hitungan mengikuti R6 (guru_pertemuan_aturan): pertemuan tidak dibatalkan, punya >= 1 anggota (R4), berada di jendela
24 jam s.d. 7 hari sesudah selesai, belum punya keadaan terkini jurnal, dan mulai >= PERTEMUAN_WAJIB_SEJAK. Riwayat
(lebih dari 7 hari) hanya tampil di halaman, tidak dihitung di antrean.

Galat: cutoff kosong = butir mati dan DB admin tidak dibuka. `jumlah` menelan galat baca DB admin (= 0); `daftar`
membiarkannya naik agar halaman menjawab 503. Galat baca catatan = daftar kosong dengan `catatan_terbaca` False.
Keluaran tanpa nama atau id anak, dan tanpa order_id (kunci Private memuat order_id).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import admin_store
import guru_jadwal_baca as gb
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as catatan
import jadwal_store as js
import kelas_dasar as dasar

_log = logging.getLogger(__name__)

GALAT_BACA = (admin_store.StoreBelumSiap, sqlite3.Error, ValueError, OSError)
BATAS_KANDIDAT = 500  # baris terbaru per kueri; lebih dari ini = riwayat_terpotong
BATAS_TAMPIL = 50
JENIS_KELOMPOK = "kelompok"
JENIS_PRIVAT = "privat"
NAMA_PRIVAT = "Private"
_STATUS_ANTREAN = (aturan.ANTREAN_AKSI, aturan.ANTREAN_RIWAYAT)

# Kandidat: pertemuan yang sudah mulai cukup lama (<= kini - 24 jam) dan tidak lebih lama dari cutoff.
# `guru_id` hanya kolom keluaran; tidak ada filter guru (antrean admin melihat semua guru).
_SQL_KANDIDAT_MINI = (
    "SELECT s.id, s.ke, s.mulai, s.menit, s.dibatalkan, k.id AS id_awal, k.nama AS nama, k.guru_id AS guru_id "
    "FROM jadwal_pertemuan s JOIN jadwal_kelompok k ON k.id=s.kelompok_id "
    "WHERE s.mulai>=? AND s.mulai<=? ORDER BY s.mulai DESC, s.id DESC LIMIT ?"
)
_SQL_KANDIDAT_PRIVAT = (
    "SELECT s.id, s.ke, s.mulai, s.menit, s.dibatalkan, s.order_id AS id_awal, p.guru_id AS guru_id "
    "FROM jadwal_pertemuan s JOIN jadwal_penempatan p ON p.order_id=s.order_id "
    "WHERE p.kelompok_id IS NULL AND s.kelompok_id IS NULL AND s.mulai>=? AND s.mulai<=? "
    "ORDER BY s.mulai DESC, s.id DESC LIMIT ?"
)


def _mundur(baku: str, durasi: timedelta) -> str:
    return (datetime.strptime(baku, aturan.FORMAT_WAKTU) - durasi).strftime(aturan.FORMAT_WAKTU)


def _ambil_kandidat(kon, sql: str, cutoff: str, batas_atas: str) -> List[dict]:
    baris = kon.execute(sql, (cutoff, batas_atas, BATAS_KANDIDAT)).fetchall()
    return [dict(b) for b in baris]


def _kandidat(kon, batas_bawah: str, kini: str) -> Tuple[List[dict], bool]:
    """Kandidat Mini dan Private (keduanya dibatasi BATAS_KANDIDAT) dan apakah salah satu kueri mencapai batas."""
    batas_atas = _mundur(kini, aturan.JEDA_TERLAMBAT)
    mini = _ambil_kandidat(kon, _SQL_KANDIDAT_MINI, batas_bawah, batas_atas)
    privat = _ambil_kandidat(kon, _SQL_KANDIDAT_PRIVAT, batas_bawah, batas_atas)
    terpotong = len(mini) >= BATAS_KANDIDAT or len(privat) >= BATAS_KANDIDAT
    gabungan = [dict(b, jenis=JENIS_KELOMPOK) for b in mini] + [
        dict(b, jenis=JENIS_PRIVAT, nama=NAMA_PRIVAT) for b in privat]
    return gabungan, terpotong


def _status_baris(baris: dict, kini: str) -> str:
    return aturan.status_antrean(baris["mulai"], int(baris["menit"]), bool(baris["dibatalkan"]), kini)


def _kunci_baris(baris: dict) -> Optional[str]:
    try:
        return aturan.kunci_pertemuan(baris["id_awal"], int(baris["ke"]))
    except ValueError:
        _log.warning("kunci pertemuan tidak sah pada data jadwal; dilewati")
        return None


def _mengantre(kandidat: List[dict], kini: str, statuses) -> List[Tuple[str, dict, str]]:
    """(kunci, baris, status) untuk kandidat ber-status `statuses` dan mulai >= cutoff. Tanpa I/O."""
    hasil = []
    for baris in kandidat:
        status = _status_baris(baris, kini)
        if status not in statuses or not aturan.wajib_aktif(baris["mulai"]):
            continue
        kunci = _kunci_baris(baris)
        if kunci is not None:
            hasil.append((kunci, baris, status))
    return hasil


def _ada_anggota(kon, baris: dict, kini: str) -> bool:
    if baris["jenis"] == JENIS_KELOMPOK:
        anggota = gb.anggota_kelompok_pertemuan(kon, baris["id_awal"], baris["mulai"], kini)
    else:
        anggota = gb.anggota_order_pertemuan(kon, baris["id_awal"], baris["mulai"], kini)
    return bool(anggota)


def _item(baris: dict) -> dict:
    """Bentuk keluaran yang aman: tanpa kunci, id order, atau id anak."""
    return {"jenis": baris["jenis"], "nama": baris["nama"], "ke": int(baris["ke"]), "mulai": baris["mulai"],
            "guru_id": baris["guru_id"]}


def _terbaru(items: List[dict]) -> List[dict]:
    return sorted(items, key=lambda item: item["mulai"], reverse=True)


def _bentuk(*, aktif: bool, sejak: Optional[str] = None, catatan_terbaca: bool = True,
            perlu=(), riwayat=(), terpotong: bool = False) -> dict:
    urut_perlu = _terbaru(list(perlu))
    urut_riwayat = _terbaru(list(riwayat))
    return {
        "aktif": aktif,
        "sejak": sejak,
        "catatan_terbaca": catatan_terbaca,
        "perlu_diisi": urut_perlu[:BATAS_TAMPIL],
        "total_perlu_diisi": len(urut_perlu),
        "riwayat": urut_riwayat[:BATAS_TAMPIL],
        "total_riwayat": len(urut_riwayat),
        "riwayat_terpotong": terpotong,
    }


def _susun(kon, kandidat: List[dict], terpotong: bool, cutoff: str, kini: str, statuses) -> dict:
    """Saringan urut: status/cutoff, lalu SATU pembacaan catatan, lalu R4 hanya untuk yang belum dicatat."""
    mengantre = _mengantre(kandidat, kini, statuses)
    try:
        sudah = catatan.punya_jurnal([(kunci, baris["mulai"]) for kunci, baris, _status in mengantre])
    except (catatan.GalatCatatan, OSError):
        return _bentuk(aktif=True, sejak=cutoff, catatan_terbaca=False, terpotong=terpotong)
    belum = [(baris, status) for kunci, baris, status in mengantre if (kunci, baris["mulai"]) not in sudah]
    beranggota = [(baris, status) for baris, status in belum if _ada_anggota(kon, baris, kini)]
    return _bentuk(
        aktif=True, sejak=cutoff, terpotong=terpotong,
        perlu=[_item(b) for b, s in beranggota if s == aturan.ANTREAN_AKSI],
        riwayat=[_item(b) for b, s in beranggota if s == aturan.ANTREAN_RIWAYAT],
    )


def _batas_bawah(cutoff: str, kini: str, hanya_perlu_diisi: bool) -> str:
    """Awal kueri. Mode ringkas (antrean) cukup jendela aksi: kini - (jendela koreksi + durasi maksimum), tidak lebih lama dari cutoff."""
    if not hanya_perlu_diisi:
        return cutoff
    jendela = aturan.JENDELA_KOREKSI + timedelta(minutes=gb.DURASI_MAKS_MENIT)
    return max(cutoff, _mundur(kini, jendela))


def daftar(path_admin, sekarang: float, *, hanya_perlu_diisi: bool = False) -> dict:
    """Pertemuan lewat tanpa jurnal untuk halaman admin. Cutoff kosong = tidak aktif, DB admin tidak dibuka.

    Kunci: `aktif`, `sejak` (baku atau None), `perlu_diisi` dan `riwayat` (maks BATAS_TAMPIL, terbaru dulu),
    `total_perlu_diisi`, `total_riwayat`, `riwayat_terpotong`, `catatan_terbaca`. Item: jenis, nama, ke, mulai, guru_id.
    `hanya_perlu_diisi` (dipakai `jumlah` di setiap render sinyal admin): hanya jendela aksi yang dibaca dan diperiksa,
    riwayat lama tidak disentuh sehingga `riwayat` kosong. Galat baca DB admin dibiarkan naik (`GALAT_BACA`).
    """
    cutoff = aturan.PERTEMUAN_WAJIB_SEJAK
    if cutoff is None:
        return _bentuk(aktif=False)
    kini = dasar.ke_baku(sekarang)
    statuses = (aturan.ANTREAN_AKSI,) if hanya_perlu_diisi else _STATUS_ANTREAN
    with js.buka(path_admin) as kon:
        kandidat, terpotong = _kandidat(kon, _batas_bawah(cutoff, kini, hanya_perlu_diisi), kini)
        return _susun(kon, kandidat, terpotong, cutoff, kini, statuses)


def jumlah(path_admin, sekarang: float) -> int:
    """Total "perlu diisi" untuk butir antrean. Cutoff kosong, DB admin belum/rusak = 0 tanpa galat."""
    if aturan.PERTEMUAN_WAJIB_SEJAK is None:
        return 0
    try:
        return daftar(path_admin, sekarang, hanya_perlu_diisi=True)["total_perlu_diisi"]
    except GALAT_BACA:
        return 0

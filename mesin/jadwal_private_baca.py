"""Pembacaan jadwal private (hanya SELECT): slot terbuka untuk order, antrean admin, status pengajuan, dan daftar slot.

Dua sumber: DB private (slot dan pengajuan, lewat `dasar.dengan_baca`) dan admin-control.db (order, akses, penempatan).
Penentu basi dan terbuka ada di `dasar.alasan_basi`; modul ini hanya mengumpulkan faktanya.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

import jadwal_pilih as jp
import jadwal_private_dasar as dsr
import jadwal_store as js
import kelas_dasar as kd
import kelas_status as ks
import kelas_store
import pesanan_dasar as d

MAKS_TAMPIL_BAWAAN = 20
STATUS_SLOT_DIBATALKAN = "dibatalkan"
STATUS_SLOT_TERISI = "terisi"
STATUS_SLOT_DIAJUKAN = "diajukan"
STATUS_SLOT_LEWAT = "lewat"
STATUS_SLOT_TERBUKA = "terbuka"
_KOLOM_SLOT = "id,guru_id,mulai,menit,dibatalkan"


@dataclass(frozen=True)
class SlotTerbuka:
    """Slot yang boleh diajukan orang tua. Sengaja TANPA guru_id (nama guru tidak tampil ke orang tua)."""

    slot_id: int
    mulai: str
    menit: int


@dataclass(frozen=True)
class EntriAntrean:
    pengajuan_id: int
    order_id: str
    slot_id: int
    mulai: str
    guru_id: str
    dibuat: str
    basi: bool
    alasan_basi: Optional[str]


@dataclass(frozen=True)
class SlotAdmin:
    slot_id: int
    guru_id: str
    mulai: str
    menit: int
    status: str
    guru_aktif: bool


@dataclass(frozen=True)
class StatusPengajuan:
    pengajuan_id: int
    status: str
    slot_id: int
    mulai: str


def fakta_order(kon, order_id: str, kini: str) -> dsr.FaktaOrder:
    baris = ks.baris_order(kon, order_id)
    if baris is None:
        return dsr.FaktaOrder(False, None, False, False)
    lunas = ks.status_dari(baris, ks.fakta_order(kon, order_id), kini) == kd.STATUS_AKTIF
    aktif = lunas and baris["paket"] == dsr.PAKET
    return dsr.FaktaOrder(aktif, js._batas_akses_order(kon, order_id), _berjadwal(kon, order_id),
                          jp._penempatan_lain_menghalangi(kon, order_id, kini))


def _berjadwal(kon, order_id: str) -> bool:
    penempatan = kon.execute("SELECT 1 FROM jadwal_penempatan WHERE order_id=?", (order_id,)).fetchone()
    return penempatan is not None or js._punya_sesi(kon, order_id)


def terisi_penempatan(kon) -> FrozenSet[Tuple[str, str]]:
    """(guru, mulai) semua penempatan Private yang pertemuan ke-1-nya aktif: slot yang sudah terisi."""
    baris = kon.execute(
        "SELECT p.guru_id AS guru, s.mulai AS mulai FROM jadwal_penempatan p "
        "JOIN jadwal_pertemuan s ON s.order_id=p.order_id AND s.ke=1 AND s.dibatalkan=0 "
        "WHERE p.guru_id IS NOT NULL").fetchall()
    return frozenset((b["guru"], b["mulai"]) for b in baris)


def keadaan_penempatan(kon, order_id: str, slot: dsr.BarisSlot) -> str:
    """'kosong' bila order belum punya penempatan; 'sama' bila penempatan Private identik slot; selain itu 'lain'."""
    baris = kon.execute(
        "SELECT p.guru_id, p.kelompok_id, s.mulai FROM jadwal_penempatan p "
        "LEFT JOIN jadwal_pertemuan s ON s.order_id=p.order_id AND s.ke=1 AND s.dibatalkan=0 "
        "WHERE p.order_id=?", (order_id,)).fetchone()
    if baris is None:
        return "kosong"
    if baris["guru_id"] == slot.guru_id and baris["kelompok_id"] is None and baris["mulai"] == slot.mulai:
        return "sama"
    return "lain"


def _basi_pengajuan(kon_admin, order_id: str, slot: dsr.BarisSlot, kini: str, guru_sah, terisi) -> Optional[str]:
    if keadaan_penempatan(kon_admin, order_id, slot) == "sama":
        return None
    return dsr.alasan_basi(fakta_order(kon_admin, order_id, kini), slot, kini, guru_sah, terisi)


def ada_penahan_aktif(kon_admin, kon_p, slot: dsr.BarisSlot, kini: str, guru_sah, terisi) -> bool:
    """True bila ada pengajuan 'diajukan' pada slot ini yang MASIH HIDUP (tidak basi)."""
    for baris in kon_p.execute("SELECT order_id FROM private_pengajuan WHERE slot_id=? AND status=?",
                               (slot.id, dsr.STATUS_DIAJUKAN)):
        if _basi_pengajuan(kon_admin, baris["order_id"], slot, kini, guru_sah, terisi) is None:
            return True
    return False


def alasan_tak_terbuka(kon_admin, kon_p, fakta: dsr.FaktaOrder, slot: dsr.BarisSlot, kini: str, guru_sah,
                       terisi) -> Optional[str]:
    """Alasan slot tidak boleh diajukan sekarang (24 jam, aturan basi, pengajuan lain menahan), atau None."""
    if slot.mulai < dsr.batas_pesan(kini):
        return dsr.ALASAN_TERLALU_DEKAT
    alasan = dsr.alasan_basi(fakta, slot, kini, guru_sah, terisi)
    if alasan is not None:
        return alasan
    if ada_penahan_aktif(kon_admin, kon_p, slot, kini, guru_sah, terisi):
        return "slot sedang diajukan"
    return None


def _order_privat_terbaru(kon, akun_id: str, siswa_id: int, kini: str) -> Optional[str]:
    """Order Private AKTIF terbaru milik (akun, anak), atau None (pola sama dengan _order_mini_tanpa_jadwal)."""
    for baris in kon.execute(
            "SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC"
            % ks.KOLOM_ORDER, (akun_id, siswa_id, dsr.PAKET)).fetchall():
        if fakta_order(kon, baris["id"], kini).aktif:
            return baris["id"]
    return None


def order_milik_anak(kon, akun_id: str, siswa_id: int) -> FrozenSet[str]:
    return frozenset(b["id"] for b in kon.execute(
        "SELECT id FROM kelas_order WHERE akun_id=? AND siswa_id=?", (akun_id, siswa_id)))


def order_boleh_mengajukan(kon_admin, akun_id, siswa_id, sekarang) -> Optional[str]:
    """Order Private aktif terbaru milik (akun, anak) yang BELUM punya penempatan/sesi dan tidak terhalang penempatan lama."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kini = kd.ke_baku(sekarang)
    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)
    oid = _order_privat_terbaru(kon_admin, akun, siswa, kini)
    if oid is None:
        return None
    fakta = fakta_order(kon_admin, oid, kini)
    if fakta.berjadwal or fakta.terhalang:
        return None
    return oid


def _slot_terbuka(kon_admin, kon_p, oid: str, kini: str, guru_sah, maks: int) -> Tuple[SlotTerbuka, ...]:
    fakta = fakta_order(kon_admin, oid, kini)
    terisi = terisi_penempatan(kon_admin)
    hasil = []
    for baris in kon_p.execute(
            "SELECT %s FROM private_slot WHERE dibatalkan=0 AND mulai>=? ORDER BY mulai,id" % _KOLOM_SLOT,
            (dsr.batas_pesan(kini),)):
        slot = dsr.BarisSlot.dari(baris)
        if alasan_tak_terbuka(kon_admin, kon_p, fakta, slot, kini, guru_sah, terisi) is None:
            hasil.append(SlotTerbuka(slot.id, slot.mulai, slot.menit))
            if len(hasil) >= maks:
                break
    return tuple(hasil)


def slot_terbuka_untuk(kon_admin, order_id, sekarang, guru_sah, path=None, maks=MAKS_TAMPIL_BAWAAN):
    """Slot yang boleh diajukan order ini sekarang (tanpa guru_id). Order tidak eligible -> kosong."""
    oid = kd.periksa_order_id(order_id)
    kini = kd.ke_baku(sekarang)
    sah = dsr.periksa_himpunan_guru(guru_sah)
    dsr.periksa_id(maks, "batas tampil")
    return dsr.dengan_baca(path, lambda kon_p: _slot_terbuka(kon_admin, kon_p, oid, kini, sah, maks), ())


def _entri_antrean(kon_admin, baris, kini: str, guru_sah, terisi) -> EntriAntrean:
    slot = dsr.BarisSlot(int(baris["id_slot"]), baris["guru_id"], baris["mulai"], int(baris["menit"]),
                         bool(baris["dibatalkan"]))
    alasan = _basi_pengajuan(kon_admin, baris["order_id"], slot, kini, guru_sah, terisi)
    return EntriAntrean(baris["id"], baris["order_id"], slot.id, slot.mulai, slot.guru_id, baris["dibuat"],
                        alasan is not None, alasan)


def _antrean(kon_admin, kon_p, kini: str, guru_sah) -> Tuple[EntriAntrean, ...]:
    terisi = terisi_penempatan(kon_admin)
    baris = kon_p.execute(
        "SELECT p.id, p.order_id, p.dibuat, s.id AS id_slot, s.guru_id, s.mulai, s.menit, s.dibatalkan "
        "FROM private_pengajuan p JOIN private_slot s ON s.id=p.slot_id WHERE p.status=? ORDER BY p.dibuat,p.id",
        (dsr.STATUS_DIAJUKAN,)).fetchall()
    return tuple(_entri_antrean(kon_admin, b, kini, guru_sah, terisi) for b in baris)


def antrean_admin(kon_admin, sekarang, guru_sah, path=None) -> Tuple[EntriAntrean, ...]:
    """Semua pengajuan 'diajukan' (hidup dan basi) untuk antrean admin, terlama dulu."""
    kini = kd.ke_baku(sekarang)
    sah = dsr.periksa_himpunan_guru(guru_sah)
    return dsr.dengan_baca(path, lambda kon_p: _antrean(kon_admin, kon_p, kini, sah), ())


def jumlah_menunggu(kon_admin, sekarang, guru_sah, path=None) -> int:
    """Jumlah pengajuan yang masih hidup (tidak basi): angka untuk butir 'Perlu ditangani'."""
    return sum(1 for entri in antrean_admin(kon_admin, sekarang, guru_sah, path) if not entri.basi)


def _status_slot(kon_admin, kon_p, slot: dsr.BarisSlot, kini: str, guru_sah, terisi) -> str:
    if slot.dibatalkan:
        return STATUS_SLOT_DIBATALKAN
    if (slot.guru_id, slot.mulai) in terisi:
        return STATUS_SLOT_TERISI
    if ada_penahan_aktif(kon_admin, kon_p, slot, kini, guru_sah, terisi):
        return STATUS_SLOT_DIAJUKAN
    if slot.mulai < kini:
        return STATUS_SLOT_LEWAT
    return STATUS_SLOT_TERBUKA


BATAS_DAFTAR_SLOT = 300  # halaman admin menampilkan slot terbaru saja; jumlah sebenarnya kecil (admin membuat satu per satu)


def _daftar_slot(kon_admin, kon_p, kini: str, guru_sah) -> Tuple[SlotAdmin, ...]:
    terisi = terisi_penempatan(kon_admin)
    hasil = []
    for baris in kon_p.execute("SELECT %s FROM private_slot ORDER BY mulai DESC,id DESC LIMIT %d" % (_KOLOM_SLOT, BATAS_DAFTAR_SLOT)):
        slot = dsr.BarisSlot.dari(baris)
        status = _status_slot(kon_admin, kon_p, slot, kini, guru_sah, terisi)
        hasil.append(SlotAdmin(slot.id, slot.guru_id, slot.mulai, slot.menit, status, slot.guru_id in guru_sah))
    return tuple(hasil)


def daftar_slot_admin(kon_admin, sekarang, guru_sah, path=None) -> Tuple[SlotAdmin, ...]:
    """Semua slot (mulai terbaru dulu) dengan status turunan untuk halaman admin."""
    kini = kd.ke_baku(sekarang)
    sah = dsr.periksa_himpunan_guru(guru_sah)
    return dsr.dengan_baca(path, lambda kon_p: _daftar_slot(kon_admin, kon_p, kini, sah), ())


STATUS_BASI = "basi"  # status virtual (tidak disimpan): pengajuan 'diajukan' yang sudah tidak bisa dijalankan


def _status_terakhir(kon_p, oid: str, kon_admin=None, kini: str = "", guru_sah=None) -> Optional[StatusPengajuan]:
    baris = kon_p.execute(
        "SELECT p.id, p.slot_id, p.status, s.mulai FROM private_pengajuan p "
        "JOIN private_slot s ON s.id=p.slot_id WHERE p.order_id=? ORDER BY p.id DESC LIMIT 1", (oid,)).fetchone()
    if baris is None:
        return None
    status = baris["status"]
    if status == dsr.STATUS_DIAJUKAN and guru_sah is not None and _pengajuan_basi(kon_admin, kon_p, oid, baris["slot_id"], kini, guru_sah):
        status = STATUS_BASI
    return StatusPengajuan(baris["id"], status, baris["slot_id"], baris["mulai"])


def _pengajuan_basi(kon_admin, kon_p, oid: str, slot_id: int, kini: str, guru_sah) -> bool:
    slot = dsr.ambil_slot(kon_p, slot_id)
    return dsr.alasan_basi(fakta_order(kon_admin, oid, kini), slot, kini, guru_sah, terisi_penempatan(kon_admin)) is not None


def status_pengajuan(kon_admin, akun_id, siswa_id, sekarang, path=None, guru_sah=None) -> Optional[StatusPengajuan]:
    """Pengajuan terakhir dari order Private aktif terbaru milik (akun, anak), atau None.

    Bila `guru_sah` diberikan, pengajuan 'diajukan' yang sudah basi dikembalikan dengan status virtual 'basi'.
    """
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kini = kd.ke_baku(sekarang)
    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)
    oid = _order_privat_terbaru(kon_admin, akun, siswa, kini)
    if oid is None:
        return None
    return dsr.dengan_baca(path, lambda kon_p: _status_terakhir(kon_p, oid, kon_admin, kini, guru_sah), None)

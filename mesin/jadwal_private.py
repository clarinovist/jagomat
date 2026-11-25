"""Tulis jadwal private: buat/batalkan slot (admin), ajukan/batalkan pengajuan (orang tua), setujui/tolak (admin).

Kunci selalu urut: DB private dulu (`BEGIN IMMEDIATE`), baru admin-control lewat `jadwal_store.tempatkan` (transaksinya
sendiri). Bila tempatkan gagal, DB private di-rollback dan tak ada yang berubah. Bila commit private gagal SESUDAH
tempatkan sukses, pengajuan tetap 'diajukan' dan setujui berikutnya mendeteksi penempatan identik (idempoten), tanpa
memanggil tempatkan dua kali. Pembacaan (slot terbuka, antrean, status) ada di `jadwal_private_baca`, dire-ekspor di sini.
"""
from __future__ import annotations

import sqlite3

import jadwal_dasar as jd
import jadwal_private_baca as bc
import jadwal_private_dasar as dsr
import jadwal_store as js
import kelas_dasar as kd
import kelas_store
import pesanan_dasar as d
from jadwal_private_baca import (  # noqa: F401  (re-ekspor: satu pintu untuk pemanggil)
    EntriAntrean,
    SlotAdmin,
    SlotTerbuka,
    StatusPengajuan,
    antrean_admin,
    daftar_slot_admin,
    jumlah_menunggu,
    order_boleh_mengajukan,
    slot_terbuka_untuk,
    status_pengajuan,
)


def buat_slot(admin_id, guru_id, tanggal, jam, sekarang, guru_sah, path=None) -> int:
    """Buat slot private (guru aktif, waktu WIB belum lewat). Hanya tindakan ini yang boleh membuat berkas DB."""
    aktor = d.periksa_pelaku(admin_id)
    kini = kd.ke_baku(sekarang)
    guru = dsr.periksa_guru_aktif(guru_id, guru_sah)
    mulai = jd.pertemuan_pertama(tanggal, jam, kini)
    with dsr.dengan_tulis(path, buat=True) as kon:
        try:
            cur = kon.execute(
                "INSERT INTO private_slot(guru_id,mulai,menit,dibuat,dibuat_oleh) VALUES(?,?,?,?,?)",
                (guru, mulai, dsr.MENIT_SESI, kini, aktor))
        except sqlite3.IntegrityError:
            raise jd.JadwalKonflik("slot dengan guru dan waktu yang sama sudah ada") from None
    return cur.lastrowid


def batalkan_slot(kon_admin, admin_id, slot_id, sekarang, guru_sah, path=None) -> None:
    """Batalkan slot bila tidak ada pengajuan yang masih hidup menahannya. Pengajuan basi tidak menghalangi."""
    d.periksa_pelaku(admin_id)
    sid = dsr.periksa_id(slot_id, "slot")
    kini = kd.ke_baku(sekarang)
    sah = dsr.periksa_himpunan_guru(guru_sah)
    with dsr.dengan_tulis(path) as kon_p:
        slot = dsr.ambil_slot(kon_p, sid)
        if slot.dibatalkan:
            return
        if bc.ada_penahan_aktif(kon_admin, kon_p, slot, kini, sah, bc.terisi_penempatan(kon_admin)):
            raise jd.JadwalKonflik("slot masih diajukan; tolak pengajuannya dulu")
        _ubah_slot_batal(kon_p, sid)


def _ubah_slot_batal(kon, slot_id: int) -> None:
    cur = kon.execute("UPDATE private_slot SET dibatalkan=1 WHERE id=? AND dibatalkan=0", (slot_id,))
    if cur.rowcount != 1:
        raise jd.JadwalKonflik("slot sudah dibatalkan")


def ajukan(kon_admin, akun_id, siswa_id, slot_id, sekarang, guru_sah, path=None) -> int:
    """Orang tua mengajukan slot untuk order Private aktif anak itu. Mengganti pengajuan 'diajukan' order yang sama."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    sid = dsr.periksa_id(slot_id, "slot")
    kini = kd.ke_baku(sekarang)
    sah = dsr.periksa_himpunan_guru(guru_sah)
    with dsr.dengan_tulis(path) as kon_p:
        order_id = bc.order_boleh_mengajukan(kon_admin, akun, siswa, kini)
        if order_id is None:
            raise jd.JadwalKonflik("tidak ada paket Private yang bisa diajukan")
        slot = dsr.ambil_slot(kon_p, sid)
        fakta = bc.fakta_order(kon_admin, order_id, kini)
        alasan = bc.alasan_tak_terbuka(kon_admin, kon_p, fakta, slot, kini, sah, bc.terisi_penempatan(kon_admin))
        if alasan is not None:
            raise jd.JadwalKonflik("slot tidak bisa diajukan: " + alasan)
        _batalkan_diajukan_order(kon_p, order_id, kini)
        return _tulis_pengajuan(kon_p, order_id, sid, kini)


def _batalkan_diajukan_order(kon, order_id: str, kini: str) -> None:
    for (pid,) in kon.execute("SELECT id FROM private_pengajuan WHERE order_id=? AND status=?",
                              (order_id, dsr.STATUS_DIAJUKAN)).fetchall():
        _ubah_status(kon, pid, dsr.STATUS_DIBATALKAN, dsr.PELAKU_SISTEM, kini)


def _tulis_pengajuan(kon, order_id: str, slot_id: int, kini: str) -> int:
    cur = kon.execute("INSERT INTO private_pengajuan(order_id,slot_id,status,dibuat) VALUES(?,?,?,?)",
                      (order_id, slot_id, dsr.STATUS_DIAJUKAN, kini))
    return cur.lastrowid


def _ubah_status(kon, pengajuan_id: int, status_baru: str, oleh: str, kini: str) -> None:
    """Transisi tunggal pengajuan: hanya dari 'diajukan'. Trigger skema juga menolak transisi lain."""
    cur = kon.execute(
        "UPDATE private_pengajuan SET status=?,diputuskan=?,diputuskan_oleh=? WHERE id=? AND status=?",
        (status_baru, kini, oleh, pengajuan_id, dsr.STATUS_DIAJUKAN))
    if cur.rowcount != 1:
        raise jd.JadwalKonflik("pengajuan sudah diputuskan")


def _pengajuan_dari(kon, pengajuan_id: int):
    baris = kon.execute("SELECT id,order_id,slot_id,status FROM private_pengajuan WHERE id=?",
                        (pengajuan_id,)).fetchone()
    if baris is None:
        raise jd.JadwalTidakDitemukan()
    return baris


def batalkan_pengajuan(kon_admin, akun_id, siswa_id, sekarang, path=None) -> None:
    """Orang tua membatalkan pengajuan 'diajukan' milik order anak itu. Pengajuan anak lain tidak tersentuh."""
    akun = d.periksa_akun_id(akun_id)
    siswa = kd.periksa_siswa_id(siswa_id)
    kini = kd.ke_baku(sekarang)
    kelas_store._wajib_anak_milik(kon_admin, akun, siswa)
    milik = bc.order_milik_anak(kon_admin, akun, siswa)
    with dsr.dengan_tulis(path) as kon_p:
        pid = _pengajuan_diajukan_milik(kon_p, milik)
        _ubah_status(kon_p, pid, dsr.STATUS_DIBATALKAN, dsr.PELAKU_ORANG_TUA, kini)


def _pengajuan_diajukan_milik(kon, milik) -> int:
    for baris in kon.execute("SELECT id,order_id FROM private_pengajuan WHERE status=?",
                             (dsr.STATUS_DIAJUKAN,)).fetchall():
        if baris["order_id"] in milik:
            return baris["id"]
    raise jd.JadwalTidakDitemukan()


def tolak(admin_id, pengajuan_id, sekarang, path=None) -> None:
    """Admin menolak pengajuan 'diajukan', basi atau tidak."""
    aktor = d.periksa_pelaku(admin_id)
    pid = dsr.periksa_id(pengajuan_id, "pengajuan")
    kini = kd.ke_baku(sekarang)
    with dsr.dengan_tulis(path) as kon_p:
        _pengajuan_dari(kon_p, pid)
        _ubah_status(kon_p, pid, dsr.STATUS_DITOLAK, aktor, kini)


def setujui(kon_admin, admin_id, pengajuan_id, sekarang, guru_sah, path=None) -> None:
    """Admin menyetujui pengajuan hidup: menempatkan order (8 pertemuan) lalu menandai 'disetujui'.

    Penempatan yang sudah identik dengan slot hanya ditandai (idempoten). Penempatan lain = konflik tanpa perubahan.
    """
    aktor = d.periksa_pelaku(admin_id)
    pid = dsr.periksa_id(pengajuan_id, "pengajuan")
    kini = kd.ke_baku(sekarang)
    sah = dsr.periksa_himpunan_guru(guru_sah)
    with dsr.dengan_tulis(path) as kon_p:
        pengajuan = _pengajuan_dari(kon_p, pid)
        if pengajuan["status"] != dsr.STATUS_DIAJUKAN:
            raise jd.JadwalKonflik("pengajuan sudah diputuskan")
        slot = dsr.ambil_slot(kon_p, pengajuan["slot_id"])
        keadaan = bc.keadaan_penempatan(kon_admin, pengajuan["order_id"], slot)
        if keadaan == "lain":
            raise jd.JadwalKonflik("paket sudah punya jadwal lain; lepas dulu")
        if keadaan == "kosong":
            _tempatkan_slot(kon_admin, aktor, pengajuan["order_id"], slot, kini, sah)
        _tandai_disetujui(kon_p, pid, aktor, kini)


def _tempatkan_slot(kon_admin, aktor: str, order_id: str, slot: dsr.BarisSlot, kini: str, guru_sah) -> None:
    alasan = dsr.alasan_basi(bc.fakta_order(kon_admin, order_id, kini), slot, kini, guru_sah,
                             bc.terisi_penempatan(kon_admin))
    if alasan is not None:
        raise jd.JadwalKonflik("pengajuan basi (%s); gunakan Tolak" % alasan)
    tanggal, jam = jd.tanggal_jam_wib(slot.mulai)
    js.tempatkan(kon_admin, aktor, order_id, guru_id=slot.guru_id, tanggal=tanggal, jam=jam, sekarang=kini)


def _tandai_disetujui(kon, pengajuan_id: int, aktor: str, kini: str) -> None:
    _ubah_status(kon, pengajuan_id, dsr.STATUS_DISETUJUI, aktor, kini)

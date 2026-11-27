"""Persetujuan pola Private oleh admin: 8 pertemuan di tanggal dan jam pola, lalu pola ditandai 'disetujui'.

Urutan sama dengan `jadwal_private.setujui`: transaksi DB private (`BEGIN IMMEDIATE`) dulu, lalu penempatan admin lewat API
publik `jadwal_store` (`tempatkan` lalu `ubah_pertemuan` untuk pertemuan ke-2..8). `d.tulis` menolak transaksi bersarang,
jadi setiap panggilan punya transaksinya sendiri. Atomisitas dijaga kompensasi: bila pemindahan pertemuan gagal,
penempatan yang baru dibuat dilepas lewat `lepas_penempatan` (belum ada pertemuan yang mulai), lalu galat naik dan DB
private di-rollback sehingga pola tetap 'diajukan'. Bila commit private gagal SESUDAH penempatan sukses, pola tetap
'diajukan' dan setujui berikutnya mengenali penempatan identik (idempoten) tanpa `tempatkan` kedua.
Tidak bisa dipulihkan: `tempatkan` dapat menghapus penempatan lama anak yang sudah berakhir aksesnya
(`_pensiunkan_penempatan_lama`); kompensasi tidak mengembalikannya. Bila kompensasi sendiri gagal, penempatan parsial
tetap ada dan harus dilepas admin lewat halaman paket sebelum pertemuan mulai.
"""
from __future__ import annotations

import jadwal_dasar as jd
import jadwal_private_baca as bc
import jadwal_private_dasar as dsr
import jadwal_private_pola as pola_db
import jadwal_private_pola_aturan as aturan
import jadwal_store as js
import kelas_dasar as kd
import pesanan_dasar as d


def setujui(kon_admin, admin_id, pola_id, guru_id, tanggal, sekarang, guru_sah, path=None) -> None:
    aktor = d.periksa_pelaku(admin_id)
    pid = dsr.periksa_id(pola_id, "pola")
    kini = kd.ke_baku(sekarang)
    guru = dsr.periksa_guru_aktif(guru_id, guru_sah)
    with dsr.dengan_tulis(path) as kon_p:
        pola = pola_db.baca_pola(kon_p, pid)
        if pola.status != pola_db.STATUS_DIAJUKAN:
            raise jd.JadwalKonflik(pola_db.PESAN_SUDAH_DIPUTUSKAN)
        rencana = aturan.rencana_pertemuan(tanggal, pola.jam, pola.hari_a, pola.hari_b, kini)
        _tempatkan(kon_admin, aktor, pola.order_id, guru, rencana, kini)
        pola_db.tandai_disetujui(kon_p, pid, aktor, kini)


def _tempatkan(kon_admin, aktor: str, order_id: str, guru: str, rencana, kini: str) -> None:
    """Tempatkan delapan pertemuan. Penempatan yang sudah identik dianggap sudah jadi (idempoten)."""
    ada = js.ringkas_order(kon_admin, order_id)
    if ada is not None:
        if _sama(ada, guru, rencana):
            return
        raise jd.JadwalKonflik("paket sudah punya jadwal lain; lepas dulu")
    _pastikan_bisa_ditempatkan(kon_admin, order_id, rencana, kini)
    tanggal, jam = jd.tanggal_jam_wib(rencana[0])
    js.tempatkan(kon_admin, aktor, order_id, guru_id=guru, tanggal=tanggal, jam=jam, sekarang=kini)
    try:
        _pindahkan_pertemuan(kon_admin, aktor, order_id, rencana, kini)
    except BaseException:
        _lepas_kompensasi(kon_admin, aktor, order_id, kini)
        raise


def _sama(ada: dict, guru: str, rencana) -> bool:
    """Penempatan private dengan guru dan delapan waktu yang sama persis dengan rencana."""
    if ada["kelompok_id"] is not None or ada["guru_id"] != guru:
        return False
    per_ke = {sesi["ke"]: sesi["mulai"] for sesi in ada["sesi"] if not sesi["dibatalkan"]}
    return per_ke == {ke: waktu for ke, waktu in enumerate(rencana, start=1)}


def _pastikan_bisa_ditempatkan(kon_admin, order_id: str, rencana, kini: str) -> None:
    """Semua syarat dicek SEBELUM tulisan pertama: aktif, masa akses mencakup pertemuan terakhir, jarak 24 jam."""
    if rencana[0] < dsr.batas_pesan(kini):
        raise jd.JadwalTidakSah(dsr.ALASAN_TERLALU_DEKAT)
    fakta = bc.fakta_order(kon_admin, order_id, kini)
    if not fakta.aktif:
        raise jd.JadwalKonflik("paket belum aktif; setujui bukti dulu")
    if fakta.batas is None or kini >= fakta.batas:
        raise jd.JadwalKonflik(pola_db.PESAN_MASA_AKSES)
    if rencana[-1] > fakta.batas:
        raise jd.JadwalTidakSah(js.PESAN_LEWAT_AKSES)
    if fakta.terhalang:
        raise jd.JadwalKonflik(dsr.ALASAN_TERHALANG)


def _pindahkan_pertemuan(kon_admin, aktor: str, order_id: str, rencana, kini: str) -> None:
    """Geser pertemuan yang belum sesuai rencana (tempatkan memakai offset Private lama, bukan offset pola)."""
    for sesi in js.ringkas_order(kon_admin, order_id)["sesi"]:
        target = rencana[sesi["ke"] - 1]
        if sesi["mulai"] == target:
            continue
        tanggal, jam = jd.tanggal_jam_wib(target)
        js.ubah_pertemuan(kon_admin, aktor, sesi["id"], tanggal=tanggal, jam=jam, sekarang=kini)


def _lepas_kompensasi(kon_admin, aktor: str, order_id: str, kini: str) -> None:
    ada = js.ringkas_order(kon_admin, order_id)
    if ada is not None:
        js.lepas_penempatan(kon_admin, aktor, order_id, versi=ada["dibuat"], sekarang=kini)

"""Blok guru di halaman orang tua (3c): kehadiran dan jurnal, serta tugas dari Guru. Baca-saja, per anak.

Dipanggil `orang_tua_http` HANYA setelah tirai PIN terbuka. Tiap blok fail-silent: galat di satu blok menghasilkan
daftar kosong untuk blok itu saja, dan log hanya memuat NAMA TIPE galat (tanpa id, tanpa isi).

- Gerbang rilis 3c (`GURU_TUGAS_AKTIF`) berlaku untuk KEDUA blok. Sakelar `PAKET_BELAJAR` saja tidak cukup:
  paket sudah aktif di produksi, jadi kehadiran dan jurnal harus tetap mati sampai commit rilis 3c menyalakan
  gerbang. Kedua gerbang dicek sebelum DB apa pun dibuka.
- Kehadiran: hanya bila `GURU_TUGAS_AKTIF` DAN `PAKET_BELAJAR` aktif; DB jadwal dibuka baca-saja di dalam fungsi ini.
- Tugas: hanya bila `GURU_TUGAS_AKTIF`. Skor dibaca dari `latihan.db` lewat koneksi pemanggil (hanya selesai,
  benar, dan total); tugas yang sesinya tidak ditemukan di skor dibuang.

Keluaran tidak memuat id, `guru_akun`, `sesi_id`, `order_id`, atau kunci apa pun.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import admin_store
import guru_pertemuan_aturan as aturan
import guru_pertemuan_ortu
import guru_tugas_aturan
import guru_tugas_baca
import guru_tugas_dasar
import jadwal_store
import paket_belajar_gate
import pesanan_transfer_pages

_log = logging.getLogger(__name__)
BATAS_TUGAS = 10


def hari_ini_wib(kini: str) -> date:
    """Tanggal WIB dari waktu baku UTC `kini`. Dipakai untuk status tenggat (tenggat sendiri sudah tanggal WIB)."""
    waktu = datetime.strptime(kini, aturan.FORMAT_WAKTU) + timedelta(hours=pesanan_transfer_pages.WIB_JAM)
    return waktu.date()


def _item_kehadiran(item: dict) -> dict:
    return {"mulai": item["mulai"], "hadir": item["hadir"], "topik": item["topik"]}


def _kehadiran_aktif() -> bool:
    """Kehadiran tampil hanya bila gerbang rilis 3c dan sakelar paket sama-sama menyala (tanpa membuka DB)."""
    return guru_tugas_aturan.guru_tugas_aktif() and paket_belajar_gate.aktif()


def _kehadiran(akun_id: str, siswa_id: int, kini: str, path_catatan) -> list:
    if not _kehadiran_aktif():
        return []
    with jadwal_store.buka(admin_store.BAWAAN) as kon_jadwal:
        riwayat = guru_pertemuan_ortu.riwayat_untuk_anak(kon_jadwal, akun_id, siswa_id, kini,
                                                         path_catatan=path_catatan)
    # Waktu rusak dibuang di sini (batas data): renderer tidak boleh gagal karenanya.
    return [_item_kehadiran(item) for item in riwayat if aturan.waktu_sah(item["mulai"])]


def _item_tugas(tugas: dict, skor: dict, hari_ini: date) -> dict:
    selesai = bool(skor["selesai"])
    return {
        "topik": aturan.label_topik(tugas["topik"]),
        "tenggat": tugas["tenggat"],
        "status_tenggat": guru_tugas_aturan.status_tenggat(tugas["tenggat"], hari_ini),
        "selesai": selesai,
        "benar": skor["benar"] if selesai else None,
        "total": skor["total"],
    }


def _tugas(kon_belajar, siswa_id: int, hari_ini: date, path_tugas) -> list:
    if not guru_tugas_aturan.guru_tugas_aktif():
        return []
    daftar = guru_tugas_dasar.daftar_siswa(siswa_id, path=path_tugas)
    if not daftar:
        return []
    skor = guru_tugas_baca.skor_ringkas(kon_belajar, [(t["sesi_id"], siswa_id) for t in daftar])
    tampil = [_item_tugas(t, skor[t["sesi_id"]], hari_ini) for t in daftar if t["sesi_id"] in skor]
    # Belum selesai dulu; urutan asal (terbaru dulu) dijaga oleh sort yang stabil.
    return sorted(tampil, key=lambda item: item["selesai"])[:BATAS_TUGAS]


def _aman(nama_blok: str, bacaan) -> list:
    """Jalankan satu blok. Galat apa pun menjadi daftar kosong untuk blok ini saja; log hanya nama tipe galat."""
    try:
        return bacaan()
    except Exception as galat:  # fitur tambahan: galat baca tidak boleh menjatuhkan halaman orang tua
        _log.warning("blok %s di halaman orang tua dilewati: %s", nama_blok, type(galat).__name__)
        return []


def kumpulkan_guru(kon_belajar, akun_id: str, siswa_id: int, kini: str, hari_ini: date, *,
                   path_catatan=None, path_tugas=None) -> dict:
    """`{"kehadiran": [...], "tugas": [...]}` untuk satu anak. `kini` = waktu baku UTC; `hari_ini` = tanggal WIB.

    Gerbang rilis 3c (`GURU_TUGAS_AKTIF`) mematikan kedua blok; `PAKET_BELAJAR` hanya menambah syarat kehadiran.
    """
    return {
        "kehadiran": _aman("kehadiran", lambda: _kehadiran(akun_id, siswa_id, kini, path_catatan)),
        "tugas": _aman("tugas", lambda: _tugas(kon_belajar, siswa_id, hari_ini, path_tugas)),
    }

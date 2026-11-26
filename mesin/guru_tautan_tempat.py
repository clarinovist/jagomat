"""Persetujuan orang tua atas permintaan guru: penempatan anak plus putusan, lapisan domain tanpa HTTP.

Dibangun di atas `guru_tautan_dasar` (ledger `guru-tautan.db`) dan `jadwal_pilih` (admin-control.db). Kunci selalu
urut: tautan dulu, lalu admin-control; tidak ada jalur sebaliknya (pola sama dengan `jadwal_private.setujui`).

Urutan `setujui_permintaan`:
1. Baca permintaan di luar transaksi. `guru_id` dan `kelompok_id` sebuah permintaan tidak pernah berubah (tabel
   append-only), jadi aman dibaca lebih dulu; status dan kepemilikan anak diverifikasi ulang di dalam transaksi.
2. `putusan_dengan_tempat`: BEGIN IMMEDIATE tautan, lalu callback di dalamnya:
   a. `anak_masih_ada` (gagal tertutup = tanpa efek);
   b. `penempatan_anak` (penempatan dari order Mini aktif terbaru, sama dengan yang dipakai `jadwal_pilih`):
      - sama dengan kelompok permintaan = idempoten (commit tautan yang gagal setelah penempatan sukses): hanya cek
        baca bahwa kelompok masih milik guru pemilik permintaan, lalu putusan ditulis tanpa menempatkan lagi;
      - kelompok lain = `anak_di_kelompok_lain`;
      - kosong = `jadwal_pilih.pilih_kelompok(..., guru_diharapkan=...)`, yang memeriksa guru di dalam transaksinya.
3. Putusan `setuju` disisipkan, lalu tautan di-commit. Galat di mana pun sebelum commit = tanpa putusan.

Penolakan (`tolak_permintaan`) hanya menulis putusan `tolak`: tidak menempatkan dan tidak memeriksa `anak_masih_ada`,
karena tidak menyentuh jadwal. Sesi murid tetap wajib di lapisan HTTP.
"""
from __future__ import annotations

import functools
from typing import Optional

import admin_store
import guru_tautan_anak as anak
import guru_tautan_aturan as aturan
import guru_tautan_dasar as tautan
import jadwal_dasar as jd
import jadwal_pilih as jp
import jadwal_store as js
import kelas_dasar as kd
import kelas_status as ks
import pesanan_dasar as d
import schema_jadwal

ALASAN_ANAK_TAK_ADA = "anak_tak_ada"
ALASAN_PERMINTAAN_TAK_BISA = "permintaan_tak_bisa"
ALASAN_KELOMPOK_TAK_BISA = "kelompok_tak_bisa"
ALASAN_KELOMPOK_PENUH = "kelompok_penuh"
ALASAN_BUKAN_MILIK_GURU = "bukan_milik_guru"
ALASAN_ANAK_DI_KELOMPOK_LAIN = "anak_di_kelompok_lain"
ALASAN_PAKET_TAK_AKTIF = "paket_tak_aktif"
ALASAN_SAH = (
    ALASAN_ANAK_TAK_ADA,
    ALASAN_PERMINTAAN_TAK_BISA,
    ALASAN_KELOMPOK_TAK_BISA,
    ALASAN_KELOMPOK_PENUH,
    ALASAN_BUKAN_MILIK_GURU,
    ALASAN_ANAK_DI_KELOMPOK_LAIN,
    ALASAN_PAKET_TAK_AKTIF,
)


class GagalPutusan(RuntimeError):
    """Persetujuan atau penolakan tidak bisa diproses; `alasan` salah satu ALASAN_* (konstanta, tanpa data privat)."""

    def __init__(self, alasan: str) -> None:
        if alasan not in ALASAN_SAH:
            raise ValueError("Alasan galat tidak dikenal.")
        super().__init__("Putusan tidak bisa diproses: " + alasan)
        self.alasan = alasan


# --- penempatan saat ini (baca saja) ----------------------------------------------------

def _order_mini_aktif_terbaru(kon, akun_id: str, siswa_id: int, kini: str):
    """Order Mini AKTIF terbaru milik (akun, anak). Urutan dan aturan status sama dengan `jadwal_pilih`."""
    for order in kon.execute(
            "SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? ORDER BY dibuat DESC,id DESC"
            % ks.KOLOM_ORDER, (akun_id, siswa_id, schema_jadwal.KODE_PAKET_MINI)).fetchall():
        if ks.status_dari(order, ks.fakta_order(kon, order["id"]), kini) == kd.STATUS_AKTIF:
            return order
    return None


def penempatan_anak(kon, akun_id: str, siswa_id: int, sekarang: str) -> Optional[str]:
    """Kelompok tempat anak ditempatkan lewat order Mini aktif terbaru, atau None. Hanya baca.

    Penempatan order lama yang sudah berakhir tidak dihitung: bila order terbaru belum ditempatkan, hasilnya None,
    sama dengan `jadwal_pilih`, yang lalu memensiunkan penempatan lama itu.
    """
    kini = kd.ke_baku(sekarang)
    order = _order_mini_aktif_terbaru(kon, akun_id, siswa_id, kini)
    if order is None:
        return None
    baris = kon.execute("SELECT kelompok_id FROM jadwal_penempatan WHERE order_id=?", (order["id"],)).fetchone()
    return None if baris is None else baris[0]


# --- callback penempatan (di dalam transaksi tautan) ------------------------------------

def _pastikan_guru_kelompok(kon, kelompok_id: str, guru_id: str) -> None:
    baris = kon.execute("SELECT guru_id FROM jadwal_kelompok WHERE id=?", (kelompok_id,)).fetchone()
    if baris is None or baris[0] != guru_id:
        raise GagalPutusan(ALASAN_BUKAN_MILIK_GURU)


def _tempatkan_ke_kelompok(kon, akun_id: str, siswa_id: int, kelompok_id: str, guru_id: str, pada: str) -> None:
    """Terjemahkan galat `pilih_kelompok` ke alasan tertutup. Urutan `except` dari yang paling spesifik."""
    try:
        jp.pilih_kelompok(kon, akun_id, siswa_id, kelompok_id, pada, guru_diharapkan=guru_id)
    except jp.KelompokBukanMilikGuru:
        raise GagalPutusan(ALASAN_BUKAN_MILIK_GURU) from None
    except jd.JadwalPenuh:
        raise GagalPutusan(ALASAN_KELOMPOK_PENUH) from None
    except jd.JadwalTidakDitemukan:
        raise GagalPutusan(ALASAN_KELOMPOK_TAK_BISA) from None
    except d.PesananTidakDitemukan:
        raise GagalPutusan(ALASAN_ANAK_TAK_ADA) from None
    except kd.KelasKonflik:
        raise GagalPutusan(ALASAN_PAKET_TAK_AKTIF) from None
    except jd.JadwalTidakSah:
        raise GagalPutusan(ALASAN_KELOMPOK_TAK_BISA) from None
    except d.PesananKonflik:
        raise GagalPutusan(ALASAN_KELOMPOK_TAK_BISA) from None


def _tujuan_admin(path_admin):
    return admin_store.BAWAAN if path_admin is None else path_admin


def _tempatkan_permintaan(*, path_auth, path_belajar, path_admin, akun_id: str, siswa_id: int, guru_id: str,
                          kelompok_id: str, pada: str) -> None:
    """Dipanggil tepat satu kali di dalam transaksi tautan. Galat apa pun di sini membatalkan putusan."""
    if not anak.anak_masih_ada(akun_id, siswa_id, path_auth=path_auth, path_belajar=path_belajar):
        raise GagalPutusan(ALASAN_ANAK_TAK_ADA)
    with js.buka(_tujuan_admin(path_admin), tulis_data=True) as kon:
        keadaan = penempatan_anak(kon, akun_id, siswa_id, pada)
        if keadaan == kelompok_id:
            _pastikan_guru_kelompok(kon, kelompok_id, guru_id)
        elif keadaan is not None:
            raise GagalPutusan(ALASAN_ANAK_DI_KELOMPOK_LAIN)
        else:
            _tempatkan_ke_kelompok(kon, akun_id, siswa_id, kelompok_id, guru_id, pada)


# --- API publik -------------------------------------------------------------------------

def setujui_permintaan(*, permintaan_id: int, akun_id: str, siswa_id: int, oleh: str, pada: str,
                       path_tautan=None, path_admin=None, path_auth=None, path_belajar=None) -> None:
    """Setujui permintaan milik anak: anak ditempatkan ke kelompok permintaan, lalu putusan `setuju` ditulis.

    Galat domain = `GagalPutusan` dengan alasan tertutup, tanpa putusan dan tanpa penempatan. Galat lain (berkas,
    skema admin) dilempar apa adanya. `akun_id` dan `siswa_id` WAJIB dari sesi murid di lapisan HTTP.
    """
    permintaan = tautan.permintaan_dengan_status(permintaan_id, pada, path=path_tautan)
    if permintaan is None:
        raise GagalPutusan(ALASAN_PERMINTAAN_TAK_BISA)
    tempatkan = functools.partial(
        _tempatkan_permintaan, path_auth=path_auth, path_belajar=path_belajar, path_admin=path_admin,
        akun_id=akun_id, siswa_id=siswa_id, guru_id=permintaan["guru_id"],
        kelompok_id=permintaan["kelompok_id"], pada=pada)
    try:
        tautan.putusan_dengan_tempat(
            permintaan_id=permintaan_id, akun_id=akun_id, siswa_id=siswa_id, oleh=oleh, pada=pada,
            tempatkan=tempatkan, path=path_tautan)
    except tautan.PutusanTakBisa:
        raise GagalPutusan(ALASAN_PERMINTAAN_TAK_BISA) from None


def tolak_permintaan(*, permintaan_id: int, akun_id: str, siswa_id: int, oleh: str, pada: str,
                     path_tautan=None) -> None:
    """Tolak permintaan milik anak: putusan `tolak` saja. Jeda tolak 7 hari berlaku untuk (guru, anak) itu."""
    try:
        tautan.putusan(permintaan_id=permintaan_id, akun_id=akun_id, siswa_id=siswa_id,
                       hasil=aturan.HASIL_TOLAK, oleh=oleh, pada=pada, path=path_tautan)
    except tautan.PutusanTakBisa:
        raise GagalPutusan(ALASAN_PERMINTAAN_TAK_BISA) from None

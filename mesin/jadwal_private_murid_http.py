"""Rute murid Jadwal Private (orang tua): kartu di /murid/paket, ajukan slot, dan batal pengajuan.

Dipanggil `kelas_murid_http` setelah gerbang sakelar PAKET_BELAJAR, sesi anak, rekening, dan PIN tirai. Order TIDAK
pernah dari form: domain menurunkannya dari (akun sesi, anak sesi). Galat domain dijawab pesan tetap tanpa data
internal dan tanpa efek; galat tak terduga = 503 tanpa detail. Baca gagal-diam: kartu hilang, halaman tetap utuh.
"""
from __future__ import annotations

import re
import sqlite3

import admin_store
import admin_store_core
import jadwal_private as jp
import jadwal_private_dasar as dsr
import jadwal_private_murid as pm
import jadwal_store as js
import kelas_pages as halaman
import kelas_private_pages as priv
import pesanan_alur as alur
import pesanan_dasar as d
import pesanan_http
from kontak_http import _alihkan, _baca_form

KUNCI_FORM_AJUKAN = frozenset({"token", "slot"})
KUNCI_FORM_BATAL = frozenset({"token"})
_POLA_SLOT = re.compile(r"[1-9][0-9]{0,17}")
COPY_GAGAL_AJUKAN = ("Waktu itu belum bisa dipilih. Mungkin baru saja diambil. Silakan pilih waktu lain, "
                     "atau hubungi tim bila masih perlu bantuan.")
COPY_GAGAL_BATAL = "Tidak ada pilihan waktu yang bisa dibatalkan. Muat ulang halaman, lalu coba lagi."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
JUDUL_GAGAL_AJUKAN = "Pilihan belum bisa dipakai"
JUDUL_GAGAL_BATAL = "Pilihan belum bisa dibatalkan"
JUDUL_BELUM_SIAP = "Belum bisa diproses"
KODE_BENTROK = 409
KODE_TIDAK_SIAP = 503
# Galat yang dibaca gagal-diam (kartu tidak tampil) atau dijawab 503 (tulis). Galat domain Jadwal* ikut sebagai PesananError.
GALAT_LAYANAN = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError, d.PesananError,
                 dsr.GalatJadwalPrivate)


def kartu_untuk(akun_id: str, siswa_id: int, kini: str, token_untuk) -> str:
    """Kartu Private untuk halaman paket, atau '' bila tidak ditawarkan atau baca gagal (gagal-diam)."""
    try:
        tawaran = pm.baca_tawaran(akun_id, siswa_id, kini)
    except GALAT_LAYANAN:
        return ""
    if tawaran is None:
        return ""
    return priv.kartu_private(tawaran.pengajuan, tawaran.slot, token_untuk)


def _form_ajukan(penangan, principal):
    """slot_id sah dari form `{token, slot}` bertoken (`AKSI_AJUKAN` + id), atau None (respons penolakan sudah dikirim)."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_AJUKAN or not _POLA_SLOT.fullmatch(data["slot"]):
        penangan._tolak_isian()
        return None
    slot_id = int(data["slot"])
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), priv.AKSI_AJUKAN + str(slot_id), data["token"]):
        penangan._tolak_isian(403)
        return None
    return slot_id


def _form_batal(penangan, principal) -> bool:
    """True bila form `{token}` bertoken batal sah; False bila respons penolakan sudah dikirim."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_BATAL:
        penangan._tolak_isian()
        return False
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), priv.AKSI_BATAL, data["token"]):
        penangan._tolak_isian(403)
        return False
    return True


def _info(penangan, judul: str, teks: str, kode: int) -> None:
    penangan._kirim_privat(halaman.halaman_info(judul, teks), kode)


def _balas_galat(penangan, galat: Exception, judul: str, teks_bentrok: str) -> None:
    """Galat domain pilihan (sudah diambil, tak ada pengajuan, syarat tak terpenuhi) = pesan tetap; sisanya 503 tanpa detail."""
    if isinstance(galat, (d.PesananKonflik, d.PesananTidakDitemukan)):
        _info(penangan, judul, teks_bentrok, KODE_BENTROK)
    else:
        _info(penangan, JUDUL_BELUM_SIAP, COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def _tulis_ajukan(akun_id: str, siswa_id: int, slot_id: int) -> None:
    with js.buka(admin_store.BAWAAN) as kon_admin:
        jp.ajukan(kon_admin, akun_id, siswa_id, slot_id, alur.waktu_sekarang(), pm.guru_sah())


def _tulis_batal(akun_id: str, siswa_id: int) -> None:
    with js.buka(admin_store.BAWAAN) as kon_admin:
        jp.batalkan_pengajuan(kon_admin, akun_id, siswa_id, alur.waktu_sekarang())


def post_ajukan(penangan, principal, siswa_id: int) -> None:
    """Orang tua mengajukan satu slot untuk order Private anak sesi; semua syarat dicek di domain."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    slot_id = _form_ajukan(penangan, principal)
    if slot_id is None:
        return
    try:
        _tulis_ajukan(principal.id_akun, siswa_id, slot_id)
    except GALAT_LAYANAN as galat:
        _balas_galat(penangan, galat, JUDUL_GAGAL_AJUKAN, COPY_GAGAL_AJUKAN)
        return
    _alihkan(penangan, halaman.RUTE)


def post_batal(penangan, principal, siswa_id: int) -> None:
    """Orang tua membatalkan pengajuan yang masih menunggu milik anak sesi."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    if not _form_batal(penangan, principal):
        return
    try:
        _tulis_batal(principal.id_akun, siswa_id)
    except GALAT_LAYANAN as galat:
        _balas_galat(penangan, galat, JUDUL_GAGAL_BATAL, COPY_GAGAL_BATAL)
        return
    _alihkan(penangan, halaman.RUTE)

"""Tambah anak dengan kode di detail kelas guru: `POST /guru/kelas/<klp_id>/tautan` (Fase 3b-2).

Identitas HANYA dari sesi: guru_id = `id_akun` principal peran guru. Kelompok milik guru lain, tak ada, atau id cacat
dijawab 404 identik dengan rute tak dikenal (`lembaga_http._tidak_ada`).

Urutan POST. Tiap langkah yang gagal berhenti di situ:
1. pemilik kelompok (404);
2. batas laju burst umum (`_batasi_laju`, 429);
3. bentuk form tepat `kode` + `token` (400);
4. token sah untuk aksi `tautan:<klp_id>` (403; tidak dihitung sebagai percobaan kode);
5. kelompok terbuka dan punya kursi (409, pesan spesifik untuk pemiliknya; tidak dihitung);
6. laju gagal per guru (DB) dan per IP (memori) (429 yang sama untuk kode valid maupun salah; tidak dihitung);
7. kode: normalisasi dan hash, cari kode aktif, anak masih ada, anak boleh masuk, lalu `ajukan`. Semua kegagalan di
   langkah ini menghasilkan `halaman_gagal` yang sama byte-identik, dan dicatat ke kedua penghitung.

Kode tidak pernah masuk URL, Location, atau log. Nama login anak hanya tampil pada respons sukses ini dan pada
status `setuju` di detail kelas. Penghitung 429 tidak ikut bertambah, sehingga blokir tidak memperpanjang dirinya.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Optional

import admin_store
import admin_store_core
import form_token
import guru_jadwal_baca as baca
import guru_tautan_aturan as aturan
import guru_tautan_anak as anak
import guru_tautan_dasar as dasar
import guru_tautan_laju as laju
import guru_tautan_masuk as masuk
import guru_tautan_pages as halaman
import ip_klien
import jadwal_store as js
import kelas_dasar as kd
import kontak_http
import lembaga_http
import pesanan_alur as alur
from learning_cycle_http import GalatForm, _batasi_laju

_log = logging.getLogger(__name__)

RUTE_PREFIX = "/guru/kelas/"
SUFIKS_TAUTAN = "/tautan"
POLA_KELOMPOK_TAUTAN = re.compile(r"/guru/kelas/(klp_[0-9a-f]{32})/tautan")
DOMAIN_TOKEN_TAUTAN = b"tautan-guru-form-v1:"
KUNCI_KODE = "kode"
KUNCI_TOKEN = "token"
NAMA_LAJU_IP = "tautan-guru-ip"
STATUS_GAGAL = 400
STATUS_LAJU = 429
STATUS_TUNGGU = 503
STATUS_TUTUP = 409
JUDUL_LAJU = "Terlalu banyak percobaan"
TEKS_LAJU = "Coba lagi nanti. Batas percobaan kode anak sedang tercapai."
JUDUL_TUNGGU = "Belum bisa diproses"
TEKS_TUNGGU = "Tautan kode anak belum bisa diproses sekarang. Coba lagi sebentar."
JUDUL_TUTUP = "Kelompok belum bisa menerima anak"
JUDUL_BURST = "Terlalu banyak permintaan"
TEKS_BURST = "Coba lagi sebentar."
_GALAT_BACA = (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError, dasar.GalatTautan)


# --- identitas, token, dan jalur --------------------------------------------------------------

def _principal_guru(penangan):
    """Principal sesi bila berperan guru; None untuk admin, murid, anonim, dan mode lokal."""
    principal = penangan._principal()
    if principal is None or principal.peran != "guru":
        return None
    return principal


def _kini() -> str:
    return kd.ke_baku(alur.waktu_sekarang())


def _ip(penangan) -> str:
    return ip_klien.ip_klien(penangan.headers, penangan.client_address)


def _aksi(kelompok_id: str) -> str:
    return f"tautan:{kelompok_id}"


def _buat_token(principal, sesi, kelompok_id: str) -> str:
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN_TAUTAN, aksi=_aksi(kelompok_id))


def _token_sah(principal, sesi, kelompok_id: str, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN_TAUTAN, aksi=_aksi(kelompok_id))


def _kelompok_dari_jalur(jalur: str) -> Optional[str]:
    cocok = POLA_KELOMPOK_TAUTAN.fullmatch(jalur)
    return cocok.group(1) if cocok else None


def _baca_admin(fungsi, bawaan):
    """Jalankan `fungsi(kon)` pada DB admin (baca). Galat baca -> `bawaan`."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            return fungsi(kon)
    except _GALAT_BACA as galat:
        _log.warning("data kelompok tidak terbaca: %s", type(galat).__name__)
        return bawaan


def _milik_guru(principal, kelompok_id: str, kini: str) -> bool:
    return _baca_admin(lambda kon: baca.detail_kelas(kon, principal.id_akun, kelompok_id, kini), None) is not None


# --- laju ------------------------------------------------------------------------------------

def _diblokir(penangan, guru_id: str, kini: str) -> bool:
    """Gagal per guru (DB) atau per IP (memori) sudah mencapai batas. Tidak pernah menulis."""
    if aturan.guru_diblokir(dasar.jumlah_gagal_guru(guru_id, kini)):
        return True
    return laju.diblokir(NAMA_LAJU_IP, _ip(penangan), jendela=aturan.JENDELA_IP_DETIK, batas=aturan.GAGAL_PER_IP)


def _catat_gagal(penangan, guru_id: str, kini: str) -> None:
    """Catat satu percobaan kode yang gagal ke kedua penghitung. Galat tulis DB hanya dicatat, jawaban tetap sama."""
    try:
        dasar.catat_gagal(guru_id=guru_id, pada=kini)
    except dasar.GalatTautan as galat:
        _log.warning("percobaan gagal tidak tercatat di DB: %s", type(galat).__name__)
    laju.catat_gagal(NAMA_LAJU_IP, _ip(penangan), jendela=aturan.JENDELA_IP_DETIK)


# --- kode (langkah 7) -------------------------------------------------------------------------

def _anak_bisa_masuk(akun_id: str, siswa_id: int, kelompok_id: str, kini: str) -> bool:
    with js.buka(admin_store.BAWAAN) as kon:
        return masuk.anak_bisa_masuk(kon, akun_id, siswa_id, kelompok_id, kini)


def _ajukan_kode(guru_id: str, kelompok_id: str, kode, kini: str) -> Optional[dict]:
    """Jalur sukses: {nama, kedaluwarsa}. Setiap syarat yang tidak terpenuhi berhenti sebagai None (tanpa tulis)."""
    kode_aktif = dasar.cari_kode_aktif(aturan.hash_kode(kode))
    if kode_aktif is None:
        return None
    akun_id, siswa_id = kode_aktif["akun_id"], kode_aktif["siswa_id"]
    if not anak.anak_masih_ada(akun_id, siswa_id):
        return None
    nama = anak.nama_login(akun_id)
    if nama is None or not _anak_bisa_masuk(akun_id, siswa_id, kelompok_id, kini):
        return None
    dasar.ajukan(guru_id=guru_id, kelompok_id=kelompok_id, kode_id=kode_aktif["id"], pada=kini)
    return {"nama": nama, "kedaluwarsa": aturan.hitung_kedaluwarsa(kini)}


def _coba_ajukan(guru_id: str, kelompok_id: str, kode, kini: str) -> Optional[dict]:
    """Semua kegagalan setelah pencarian kode dijadikan satu jawaban (None). Jenis galat hanya dicatat."""
    try:
        return _ajukan_kode(guru_id, kelompok_id, kode, kini)
    except Exception as galat:  # sengaja luas: 500 pada kode tertentu akan menjadi oracle
        _log.warning("permintaan kode anak tidak diproses: %s", type(galat).__name__)
        return None


# --- respons ----------------------------------------------------------------------------------

def _kirim_info(penangan, kode: int, judul: str, teks: str) -> None:
    penangan._kirim_privat(halaman.halaman_info(judul, teks), kode)


def _kirim_galat_burst(penangan, galat: GalatForm) -> None:
    if galat.status == STATUS_LAJU:
        _kirim_info(penangan, STATUS_LAJU, JUDUL_BURST, TEKS_BURST)
    else:
        penangan._tolak_isian(galat.status)


def _tolak_jika_tutup(penangan, kelompok_id: str, kini: str) -> bool:
    """True bila respons sudah dikirim: kelompok tidak menerima anak, atau keadaannya tak bisa dibaca."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            pesan = masuk.kelompok_pesan_tutup(kon, kelompok_id, kini)
    except _GALAT_BACA as galat:
        _log.warning("keadaan kelompok tidak terbaca: %s", type(galat).__name__)
        _kirim_info(penangan, STATUS_TUNGGU, JUDUL_TUNGGU, TEKS_TUNGGU)
        return True
    if pesan is None:
        return False
    _kirim_info(penangan, STATUS_TUTUP, JUDUL_TUTUP, pesan)
    return True


def _tolak_jika_laju(penangan, guru_id: str, kini: str) -> bool:
    """True bila respons sudah dikirim: laju tercapai (429) atau penghitung tak terbaca (503). Tanpa tulis."""
    try:
        diblokir = _diblokir(penangan, guru_id, kini)
    except dasar.GalatTautan as galat:
        _log.warning("penghitung laju tidak terbaca: %s", type(galat).__name__)
        _kirim_info(penangan, STATUS_TUNGGU, JUDUL_TUNGGU, TEKS_TUNGGU)
        return True
    if diblokir:
        _kirim_info(penangan, STATUS_LAJU, JUDUL_LAJU, TEKS_LAJU)
        return True
    return False


def _proses_kode(penangan, guru_id: str, kelompok_id: str, kode, kini: str) -> None:
    jawaban = _coba_ajukan(guru_id, kelompok_id, kode, kini)
    if jawaban is None:
        _catat_gagal(penangan, guru_id, kini)
        penangan._kirim_privat(halaman.halaman_gagal(), STATUS_GAGAL)
        return
    penangan._kirim_privat(halaman.halaman_berhasil(jawaban["nama"], jawaban["kedaluwarsa"], kelompok_id))


def _proses_post(penangan, principal, kelompok_id: str, kini: str) -> None:
    try:
        _batasi_laju(penangan, principal.pengguna)
    except GalatForm as galat:
        _kirim_galat_burst(penangan, galat)
        return
    data = kontak_http._baca_form(penangan)
    if data is None or set(data) != {KUNCI_KODE, KUNCI_TOKEN}:
        penangan._tolak_isian()
        return
    if not _token_sah(principal, penangan._ambil_token(), kelompok_id, data[KUNCI_TOKEN]):
        penangan._tolak_isian(403)
        return
    if _tolak_jika_tutup(penangan, kelompok_id, kini) or _tolak_jika_laju(penangan, principal.id_akun, kini):
        return
    _proses_kode(penangan, principal.id_akun, kelompok_id, data[KUNCI_KODE], kini)


# --- bagian detail kelas (dipanggil guru_jadwal_http untuk pemilik saja) ----------------------

def _tampilan_permintaan(bentuk: dict) -> dict:
    """Hanya teks dan status. Nama login hanya untuk `setuju`; akun_id dan siswa_id tidak ikut."""
    anak_login = None
    if bentuk["status"] == aturan.STATUS_SETUJU:
        anak_login = anak.nama_login(bentuk["akun_id"]) or baca.PLACEHOLDER_NAMA
    return {"dibuat": bentuk["dibuat"], "status": bentuk["status"], "anak": anak_login}


def _permintaan_kelompok(guru_id: str, kelompok_id: str, kini: str) -> list:
    return [_tampilan_permintaan(b) for b in dasar.daftar_untuk_guru(guru_id, kini)
            if b["kelompok_id"] == kelompok_id]


def bagian_detail(penangan, principal, kelompok_id: str, kini: str) -> str:
    """HTML bagian 'Tambah anak dengan kode' dan daftar permintaan. Galat baca = bagian kosong, bukan 404 atau 500."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            pesan_tutup = masuk.kelompok_pesan_tutup(kon, kelompok_id, kini)
        permintaan = _permintaan_kelompok(principal.id_akun, kelompok_id, kini)
    except _GALAT_BACA as galat:
        _log.warning("bagian tautan tidak terbaca: %s", type(galat).__name__)
        return ""
    token = None if pesan_tutup is not None else _buat_token(principal, penangan._ambil_token(), kelompok_id)
    return halaman.bagian_tautan(kelompok_id, token, pesan_tutup, permintaan)


# --- dispatcher -------------------------------------------------------------------------------

def tangani_post(penangan, jalur: str) -> bool:
    """POST `/guru/kelas/<klp_id>/tautan`. Dipanggil setelah palang sandi dan guard asal dispatcher."""
    if not (jalur.startswith(RUTE_PREFIX) and jalur.endswith(SUFIKS_TAUTAN)):
        return False
    principal = _principal_guru(penangan)
    kelompok_id = _kelompok_dari_jalur(jalur)
    kini = _kini()
    if principal is None or kelompok_id is None or not _milik_guru(principal, kelompok_id, kini):
        lembaga_http._tidak_ada(penangan)
        return True
    _proses_post(penangan, principal, kelompok_id, kini)
    return True

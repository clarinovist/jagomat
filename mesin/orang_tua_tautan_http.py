"""Kode anak untuk guru di halaman orang tua: kartu GET dan `POST /murid/orang-tua/kode` (Fase 3b-3B).

Gerbang ditegakkan SERVER pada POST, berurutan, dan berhenti di langkah pertama yang gagal:
1. sakelar DAFTAR_AKUN_ANAK dan PAKET_BELAJAR (mati = False, jatuh ke jalur murid tak dikenal);
2. principal berperan murid (401 bila tidak);
3. bentuk isian tepat sesuai tindakan (400);
4. token domain `kode-anak-form-v1:` untuk aksi `kode:<tindakan>` (403, tanpa efek);
5. siswa_id HANYA dari sesi murid (404);
6. PIN terpasang (403) dan tirai terbuka untuk sesi cookie (`tirai_aksi`, fail-closed);
7. aksi lewat `guru_tautan_kode` (409 untuk kode basi, sudah ada, atau anak tak ada; 503 untuk galat tulis).

Kode baru tampil sekali pada respons 200 (`no-store`, tanpa redirect). Kartu GET hanya memuat tanggal dan peran pembuat.
Kartu dirender hanya bila PIN terpasang dan tirai terbuka (dicek pemanggil `orang_tua_http`), tanpa koneksi DB baru.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Optional, Tuple

import daftar_anak_gate
import database
import form_token
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_kode as kode
import kelas_dasar as kd
import orang_tua_tautan_pages as halaman
import paket_belajar_gate
import pesanan_alur as alur
import pin_orang_tua_store as pin_store
import tirai_aksi
from support_pages import halaman_pesan_murid

_log = logging.getLogger(__name__)

DOMAIN_TOKEN_KODE = b"kode-anak-form-v1:"
KUNCI_TINDAKAN = "tindakan"
KUNCI_TOKEN = "token"
KUNCI_KODE_ID = "kode_id"
_KUNCI_BUAT = frozenset((KUNCI_TINDAKAN, KUNCI_TOKEN))
_KUNCI_UBAH = _KUNCI_BUAT | {KUNCI_KODE_ID}
_TINDAKAN_SAH = (halaman.TINDAKAN_BUAT, halaman.TINDAKAN_GANTI, halaman.TINDAKAN_CABUT)
MAKS_DIGIT_KODE_ID = 18
STATUS_TOKEN = 403
STATUS_TANPA_PIN = 403
STATUS_TIDAK_ADA = 404
STATUS_BASI = 409
STATUS_TUNGGU = 503
_BASI_ANAK = (dasar.KodeSudahAda, dasar.KodeBasi)
_GALAT_BACA = (dasar.GalatTautan, sqlite3.Error, ValueError)


# --- identitas, token, dan bentuk isian ------------------------------------------------------

def tersedia() -> bool:
    """Sakelar DAFTAR_AKUN_ANAK dan PAKET_BELAJAR keduanya hidup."""
    return daftar_anak_gate.aktif() and paket_belajar_gate.aktif()


def _aksi(tindakan: str) -> str:
    return "kode:" + tindakan


def token_untuk(principal, sesi, tindakan: str) -> str:
    """Token form untuk `tindakan`, terikat ke akun, sesi, domain, dan aksi."""
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN_KODE, aksi=_aksi(tindakan))


def _token_sah(principal, sesi, tindakan: str, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN_KODE, aksi=_aksi(tindakan))


def _kode_id(nilai) -> Optional[int]:
    """id kode positif dari isian form; None bila bukan angka desimal ASCII yang masuk akal."""
    if type(nilai) is not str or not nilai.isascii() or not nilai.isdigit() or len(nilai) > MAKS_DIGIT_KODE_ID:
        return None
    angka = int(nilai)
    return angka if angka >= 1 else None


def _bentuk_sah(data: Optional[dict]) -> bool:
    """Isian tepat sesuai tindakan: `buat` tanpa kode_id; `ganti` dan `cabut` dengan kode_id positif."""
    if data is None or data.get(KUNCI_TINDAKAN) not in _TINDAKAN_SAH:
        return False
    if data[KUNCI_TINDAKAN] == halaman.TINDAKAN_BUAT:
        return set(data) == _KUNCI_BUAT
    return set(data) == _KUNCI_UBAH and _kode_id(data[KUNCI_KODE_ID]) is not None


def _baca_form(penangan) -> Optional[dict]:
    from kontak_http import _baca_form as baca
    return baca(penangan)


# --- gerbang ----------------------------------------------------------------------------------

def _pin_terpasang(siswa_id: int) -> bool:
    """PIN anak terpasang. Fail-closed: DB tak terbaca dianggap tidak terpasang."""
    try:
        with database.buka() as kon:
            return pin_store.ada_pin(kon, siswa_id)
    except sqlite3.Error:
        return False


def _siswa_sesi(principal) -> Optional[int]:
    import students
    with database.buka() as kon:
        return students.siswa_dari_akun(kon, principal.pengguna)


def _gerbang_tirai(penangan, principal, siswa_id: int) -> bool:
    """True bila boleh lanjut. Bila tidak, respons 403 sudah dikirim (PIN belum dipasang, atau tirai tertutup)."""
    if not _pin_terpasang(siswa_id):
        penangan._kirim_privat(halaman.halaman_belum_pin(), STATUS_TANPA_PIN)
        return False
    if tirai_aksi.tertutup(penangan, principal, siswa_id):
        penangan._kirim_privat(halaman.halaman_info("Halaman ditutup dengan PIN", tirai_aksi.COPY_TERTUTUP),
                               tirai_aksi.KODE_TERTUTUP)
        return False
    return True


# --- aksi -------------------------------------------------------------------------------------

def _kini() -> str:
    return kd.ke_baku(alur.waktu_sekarang())


def _lakukan(principal, siswa_id: int, data: dict, kini: str) -> Tuple[int, bytes]:
    """Jalankan aksi lalu kembalikan (status, isi). Kode mentah hanya ada di isi `buat`/`ganti`, sekali."""
    pencatat = {"oleh": principal.id_akun, "peran": aturan.PERAN_ORANG_TUA, "pada": kini}
    tindakan = data[KUNCI_TINDAKAN]
    if tindakan == halaman.TINDAKAN_BUAT:
        mentah = kode.buat_kode_baru(principal.id_akun, siswa_id, **pencatat)
        return 200, halaman.halaman_kode_baru(aturan.tampilkan(mentah))
    kode_id = _kode_id(data[KUNCI_KODE_ID])
    if tindakan == halaman.TINDAKAN_GANTI:
        mentah = kode.ganti_kode(principal.id_akun, siswa_id, kode_id_diharapkan=kode_id, **pencatat)
        return 200, halaman.halaman_kode_baru(aturan.tampilkan(mentah))
    kode.cabut(principal.id_akun, siswa_id, kode_id_diharapkan=kode_id, **pencatat)
    return 200, halaman.halaman_cabut()


def _kirim_galat_aksi(penangan, galat: Exception) -> None:
    """Pesan generik per jenis galat. Nama jenis galat saja yang dicatat; kode tidak pernah ikut."""
    if isinstance(galat, kode.AnakTakAda):
        penangan._kirim_privat(halaman.halaman_info(halaman.JUDUL_ANAK, halaman.TEKS_ANAK), STATUS_BASI)
    elif isinstance(galat, _BASI_ANAK):
        penangan._kirim_privat(halaman.halaman_info(halaman.JUDUL_BASI, halaman.TEKS_BASI), STATUS_BASI)
    else:
        penangan._kirim_privat(halaman.halaman_info(halaman.JUDUL_TUNGGU, halaman.TEKS_TUNGGU), STATUS_TUNGGU)


def _jalankan(penangan, principal, siswa_id: int, data: dict) -> None:
    try:
        status, isi = _lakukan(principal, siswa_id, data, _kini())
    except dasar.GalatTautan as galat:
        _log.info("aksi kode anak tidak selesai: %s", type(galat).__name__)
        _kirim_galat_aksi(penangan, galat)
        return
    penangan._kirim_privat(isi, status)


# --- kartu (GET) ------------------------------------------------------------------------------

def kartu_kode(principal, sesi, siswa_id: int) -> str:
    """Kartu 'Kode anak untuk guru'. Pemanggil hanya memanggil bila PIN terpasang dan tirai terbuka untuk `sesi`.

    Tanpa kode mentah: hanya tanggal dan peran pembuat kode aktif. Tirai tidak terbuka = "" (tanpa token).
    """
    if not tersedia():
        return ""
    try:
        aktif = kode.kode_aktif(principal.id_akun, siswa_id)
    except _GALAT_BACA as galat:  # kartu gagal sendiri; halaman orang tua tetap tampil
        _log.warning("kode anak tidak terbaca untuk kartu: %s", type(galat).__name__)
        return halaman.kartu_tak_terbaca()
    tindakan = (halaman.TINDAKAN_BUAT,) if aktif is None else (halaman.TINDAKAN_GANTI, halaman.TINDAKAN_CABUT)
    tokens = {nama: token_untuk(principal, sesi, nama) for nama in tindakan}
    # TITIK SISIP 3b-3 persetujuan: jumlah permintaan menunggu untuk anak ini dirender di sini (langkah berikutnya).
    return halaman.kartu(aktif, tokens)


# --- dispatcher -------------------------------------------------------------------------------

def _tolak_tanpa_masuk(penangan) -> None:
    penangan._kirim(halaman_pesan_murid("Perlu masuk", "<h1>Halaman murid</h1>"), 401)


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/murid/orang-tua/kode`. False bila jalur bukan milik modul atau sakelar mati (jatuh ke jalur tak dikenal)."""
    if jalur != halaman.RUTE_KODE or not tersedia():
        return False
    principal = penangan._principal()
    if principal is None or principal.peran != "murid":
        _tolak_tanpa_masuk(penangan)
        return True
    data = _baca_form(penangan)
    if not _bentuk_sah(data):
        penangan._tolak_isian()
        return True
    if not _token_sah(principal, penangan._ambil_token(), data[KUNCI_TINDAKAN], data[KUNCI_TOKEN]):
        penangan._tolak_isian(STATUS_TOKEN)
        return True
    siswa_id = _siswa_sesi(principal)
    if siswa_id is None:
        penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), STATUS_TIDAK_ADA)
        return True
    if _gerbang_tirai(penangan, principal, siswa_id):
        _jalankan(penangan, principal, siswa_id, data)
    return True

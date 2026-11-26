"""Kode anak untuk guru dan persetujuan permintaan guru di halaman orang tua (Fase 3b-3B dan 3b-3).

Gerbang ditegakkan SERVER pada POST, berurutan, dan berhenti di langkah pertama yang gagal:
1. sakelar DAFTAR_AKUN_ANAK dan PAKET_BELAJAR (mati = False, jatuh ke jalur murid tak dikenal);
2. principal berperan murid (401 bila tidak);
3. bentuk isian tepat sesuai rute dan tindakan (400);
4. token untuk aksi (403, tanpa efek): domain `kode-anak-form-v1:` untuk `kode:<tindakan>`, dan domain
   `tautan-ortu-form-v1:` untuk `tautan:<permintaan_id>:<hasil>`;
5. siswa_id HANYA dari sesi murid (404);
6. PIN terpasang (403) dan tirai terbuka untuk sesi cookie (`tirai_aksi`, fail-closed);
7. aksi. Kode lewat `guru_tautan_kode` (409 untuk kode basi, sudah ada, atau anak tak ada; 503 untuk galat tulis).
   Putusan lewat `guru_tautan_tempat` (409 untuk galat domain dengan alasan tertutup; 503 untuk galat tulis).

Kode baru tampil sekali pada respons 200 (`no-store`, tanpa redirect). Kartu GET memuat tanggal dan peran pembuat
kode, serta permintaan guru yang menunggu (tanpa id akun, id anak, atau id kelompok). Kartu dirender hanya bila PIN
terpasang dan tirai terbuka (dicek pemanggil `orang_tua_http`).

Id permintaan milik anak lain sama dengan id yang tidak ada: pemeriksaan milik terjadi di dalam domain sebelum
penempatan, dan keduanya dijawab alasan `permintaan_tak_bisa` yang sama.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Optional, Tuple

import admin_store_core
import daftar_anak_gate
import database
import form_token
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_kode as kode
import guru_tautan_tempat as tempat
import kelas_dasar as kd
import orang_tua_putusan_daftar as daftar
import orang_tua_tautan_pages as halaman
import paket_belajar_gate
import pesanan_alur as alur
import pin_orang_tua_store as pin_store
import tirai_aksi
from support_pages import halaman_pesan_murid

_log = logging.getLogger(__name__)

DOMAIN_TOKEN_KODE = b"kode-anak-form-v1:"
DOMAIN_TOKEN_PUTUSAN = b"tautan-ortu-form-v1:"
KUNCI_TINDAKAN = "tindakan"
KUNCI_TOKEN = "token"
KUNCI_KODE_ID = "kode_id"
KUNCI_KONFIRMASI = "konfirmasi"
KUNCI_PERMINTAAN = "permintaan_id"
KUNCI_HASIL = "hasil"
_KUNCI_BUAT = frozenset((KUNCI_TINDAKAN, KUNCI_TOKEN))
_KUNCI_UBAH = _KUNCI_BUAT | {KUNCI_KODE_ID, KUNCI_KONFIRMASI}
_KUNCI_PUTUSAN = frozenset((KUNCI_PERMINTAAN, KUNCI_HASIL, KUNCI_TOKEN))
_RUTE_POST = (halaman.RUTE_KODE, halaman.RUTE_PUTUSAN)
_TINDAKAN_SAH = (halaman.TINDAKAN_BUAT, halaman.TINDAKAN_GANTI, halaman.TINDAKAN_CABUT)
NILAI_KONFIRMASI = "1"
MAKS_DIGIT_ID = 18
STATUS_TOKEN = 403
STATUS_TANPA_PIN = 403
STATUS_TIDAK_ADA = 404
STATUS_BASI = 409
STATUS_TUNGGU = 503
_BASI_ANAK = (dasar.KodeSudahAda, dasar.KodeBasi)
_GALAT_BACA = (dasar.GalatTautan, sqlite3.Error, ValueError)
_GALAT_MENUNGGU = _GALAT_BACA + (OSError,)
_GALAT_PUTUSAN = (dasar.GalatTautan, admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError)
_PESAN_PUTUSAN = {
    tempat.ALASAN_ANAK_TAK_ADA: (
        "Akun anak tidak aktif", "Akun anak ini sudah tidak aktif, jadi permintaan tidak bisa diproses."),
    tempat.ALASAN_PERMINTAAN_TAK_BISA: (
        "Permintaan tidak bisa diproses lagi",
        "Permintaan ini sudah diputuskan, kedaluwarsa, atau dibatalkan. Muat ulang halaman untuk melihat keadaannya."),
    tempat.ALASAN_KELOMPOK_TAK_BISA: (
        "Kelompok tidak bisa menerima anak", "Kelompok ini sudah tidak bisa menerima anak. Minta guru mengajukan lagi."),
    tempat.ALASAN_BUKAN_MILIK_GURU: (
        "Kelompok tidak bisa menerima anak", "Kelompok ini sudah tidak bisa menerima anak. Minta guru mengajukan lagi."),
    tempat.ALASAN_KELOMPOK_PENUH: (
        "Kelompok sudah penuh", "Kelompok ini sudah penuh, jadi anak belum bisa masuk. Permintaan tetap menunggu."),
    tempat.ALASAN_ANAK_DI_KELOMPOK_LAIN: (
        "Anak sudah punya kelompok", "Anak ini sudah masuk kelompok lain, jadi permintaan ini tidak bisa disetujui."),
    tempat.ALASAN_PAKET_TAK_AKTIF: (
        "Paket belum aktif", "Paket Mini anak ini tidak aktif sekarang, jadi anak belum bisa masuk kelompok."),
}


# --- identitas, token, dan bentuk isian ------------------------------------------------------------

def tersedia() -> bool:
    """Gerbang KODE_ANAK_AKTIF, sakelar DAFTAR_AKUN_ANAK, dan PAKET_BELAJAR, ketiganya hidup."""
    return aturan.kode_anak_aktif() and daftar_anak_gate.aktif() and paket_belajar_gate.aktif()


def _aksi(tindakan: str) -> str:
    return "kode:" + tindakan


def token_untuk(principal, sesi, tindakan: str) -> str:
    """Token form kode untuk `tindakan`, terikat ke akun, sesi, domain, dan aksi."""
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN_KODE, aksi=_aksi(tindakan))


def _token_sah(principal, sesi, tindakan: str, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN_KODE, aksi=_aksi(tindakan))


def _aksi_putusan(permintaan_id: int, hasil: str) -> str:
    return f"tautan:{permintaan_id}:{hasil}"


def token_putusan(principal, sesi, permintaan_id: int, hasil: str) -> str:
    """Token form setuju/tolak untuk satu permintaan, terikat ke akun, sesi, domain putusan, dan aksi."""
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN_PUTUSAN,
                                 aksi=_aksi_putusan(permintaan_id, hasil))


def _token_putusan_sah(principal, sesi, permintaan_id: int, hasil: str, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN_PUTUSAN,
                                aksi=_aksi_putusan(permintaan_id, hasil))


def _id_positif(nilai) -> Optional[int]:
    """Id positif dari isian form: angka desimal ASCII tanpa nol di depan dan panjang dibatasi; None bila tidak sah."""
    if type(nilai) is not str or not nilai.isascii() or not nilai.isdigit() or len(nilai) > MAKS_DIGIT_ID:
        return None
    angka = int(nilai)
    return angka if angka >= 1 and str(angka) == nilai else None


def _bentuk_sah(data: Optional[dict]) -> bool:
    """Isian tepat sesuai tindakan: `buat` tanpa kode_id; `ganti` dan `cabut` dengan kode_id positif dan centang."""
    if data is None or data.get(KUNCI_TINDAKAN) not in _TINDAKAN_SAH:
        return False
    if data[KUNCI_TINDAKAN] == halaman.TINDAKAN_BUAT:
        return set(data) == _KUNCI_BUAT
    return (set(data) == _KUNCI_UBAH and _id_positif(data[KUNCI_KODE_ID]) is not None
            and data[KUNCI_KONFIRMASI] == NILAI_KONFIRMASI)


def _bentuk_putusan_sah(data: Optional[dict]) -> bool:
    """Isian tepat `permintaan_id`, `hasil` (setuju atau tolak), dan `token`."""
    if data is None or set(data) != _KUNCI_PUTUSAN:
        return False
    return data[KUNCI_HASIL] in aturan.HASIL_SAH and _id_positif(data[KUNCI_PERMINTAAN]) is not None


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


def _siswa_terhubung(penangan, principal) -> Optional[int]:
    """siswa_id dari sesi; None bila tidak terhubung (404 sudah dikirim)."""
    siswa_id = _siswa_sesi(principal)
    if siswa_id is None:
        penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), STATUS_TIDAK_ADA)
    return siswa_id


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


# --- aksi kode --------------------------------------------------------------------------------

def _kini() -> str:
    return kd.ke_baku(alur.waktu_sekarang())


def _lakukan(principal, siswa_id: int, data: dict, kini: str) -> Tuple[int, bytes]:
    """Jalankan aksi lalu kembalikan (status, isi). Kode mentah hanya ada di isi `buat`/`ganti`, sekali."""
    pencatat = {"oleh": principal.id_akun, "peran": aturan.PERAN_ORANG_TUA, "pada": kini}
    tindakan = data[KUNCI_TINDAKAN]
    if tindakan == halaman.TINDAKAN_BUAT:
        mentah = kode.buat_kode_baru(principal.id_akun, siswa_id, **pencatat)
        return 200, halaman.halaman_kode_baru(aturan.tampilkan(mentah))
    kode_id = _id_positif(data[KUNCI_KODE_ID])
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


# --- putusan permintaan guru ------------------------------------------------------------------

def _kirim_galat_putusan(penangan, alasan: str) -> None:
    """Pesan ramah per alasan tertutup. Tidak memuat id, nama guru, atau nama anak."""
    judul, teks = _PESAN_PUTUSAN[alasan]
    penangan._kirim_privat(halaman.halaman_info(judul, teks), STATUS_BASI)


def _jalankan_putusan(principal, siswa_id: int, permintaan_id: int, hasil: str, kini: str) -> None:
    argumen = {"permintaan_id": permintaan_id, "akun_id": principal.id_akun, "siswa_id": siswa_id,
               "oleh": principal.id_akun, "pada": kini}
    if hasil == aturan.HASIL_SETUJU:
        tempat.setujui_permintaan(**argumen)
    else:
        tempat.tolak_permintaan(**argumen)


def _putuskan(penangan, principal, siswa_id: int, permintaan_id: int, hasil: str) -> None:
    try:
        _jalankan_putusan(principal, siswa_id, permintaan_id, hasil, _kini())
    except tempat.GagalPutusan as galat:
        _log.info("putusan orang tua tidak diproses: %s", galat.alasan)
        _kirim_galat_putusan(penangan, galat.alasan)
        return
    except _GALAT_PUTUSAN as galat:
        _log.warning("putusan orang tua tidak tersimpan: %s", type(galat).__name__)
        penangan._kirim_privat(halaman.halaman_info(halaman.JUDUL_TUNGGU, halaman.TEKS_TUNGGU), STATUS_TUNGGU)
        return
    penangan._kirim_privat(halaman.halaman_putusan(hasil), 200)


# --- kartu (GET) ------------------------------------------------------------------------------

def kartu_kode(principal, sesi, siswa_id: int) -> str:
    """Kartu 'Kode anak untuk guru' beserta permintaan menunggu. Pemanggil hanya memanggil bila PIN terpasang
    dan tirai terbuka untuk `sesi`. Tanpa kode mentah: hanya tanggal dan peran pembuat kode aktif.
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
    return halaman.kartu(aktif, tokens, menunggu_html=_bagian_menunggu(principal, sesi, siswa_id))


def _bagian_menunggu(principal, sesi, siswa_id: int) -> str:
    """Permintaan guru yang menunggu untuk anak ini. Galat baca hanya menggantikan bagian ini."""
    try:
        baris = daftar.baris_menunggu(principal.id_akun, siswa_id, _kini())
    except _GALAT_MENUNGGU as galat:
        _log.warning("permintaan menunggu untuk kartu tidak terbaca: %s", type(galat).__name__)
        return halaman.bagian_menunggu_tak_terbaca()
    return halaman.bagian_menunggu([_dengan_token(b, principal, sesi) for b in baris])


def _dengan_token(baris: dict, principal, sesi) -> dict:
    tokens = {hasil: token_putusan(principal, sesi, baris["id"], hasil) for hasil in aturan.HASIL_SAH}
    return {**baris, "tokens": tokens}


# --- dispatcher -------------------------------------------------------------------------------

def _tolak_tanpa_masuk(penangan) -> None:
    penangan._kirim(halaman_pesan_murid("Perlu masuk", "<h1>Halaman murid</h1>"), 401)


def _tangani_kode_post(penangan, principal, data: Optional[dict]) -> None:
    if not _bentuk_sah(data):
        penangan._tolak_isian()
        return
    if not _token_sah(principal, penangan._ambil_token(), data[KUNCI_TINDAKAN], data[KUNCI_TOKEN]):
        penangan._tolak_isian(STATUS_TOKEN)
        return
    siswa_id = _siswa_terhubung(penangan, principal)
    if siswa_id is not None and _gerbang_tirai(penangan, principal, siswa_id):
        _jalankan(penangan, principal, siswa_id, data)


def _tangani_putusan_post(penangan, principal, data: Optional[dict]) -> None:
    if not _bentuk_putusan_sah(data):
        penangan._tolak_isian()
        return
    permintaan_id = _id_positif(data[KUNCI_PERMINTAAN])
    hasil = data[KUNCI_HASIL]
    if not _token_putusan_sah(principal, penangan._ambil_token(), permintaan_id, hasil, data[KUNCI_TOKEN]):
        penangan._tolak_isian(STATUS_TOKEN)
        return
    siswa_id = _siswa_terhubung(penangan, principal)
    if siswa_id is not None and _gerbang_tirai(penangan, principal, siswa_id):
        _putuskan(penangan, principal, siswa_id, permintaan_id, hasil)


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/murid/orang-tua/kode` dan `/murid/orang-tua/tautan`. False bila jalur bukan milik modul atau sakelar mati."""
    if jalur not in _RUTE_POST or not tersedia():
        return False
    principal = penangan._principal()
    if principal is None or principal.peran != "murid":
        _tolak_tanpa_masuk(penangan)
        return True
    data = _baca_form(penangan)
    if jalur == halaman.RUTE_PUTUSAN:
        _tangani_putusan_post(penangan, principal, data)
    else:
        _tangani_kode_post(penangan, principal, data)
    return True

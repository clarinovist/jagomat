"""Kode anak untuk guru di detail order Paket Belajar admin (Fase 3b-5): blok GET dan `POST /admin/kelas/kode-anak`.

Identitas anak HANYA dari baris `kelas_order` di server (`akun_id` dan `siswa_id`), dicari dari `order_id` yang dikirim
form. Hanya order paket Mini yang punya blok dan menerima POST; order Private dan order tak ada sama-sama 404 identik.
Token domain `kode-anak-admin-form-v1:` dengan aksi `kode:<tindakan>:<order_id>` mengikat token ke satu order dan
satu tindakan, sehingga token order lain atau tindakan lain tidak berlaku.

Urutan POST. Tiap langkah yang gagal berhenti di situ:
1. admin berkuki (404 identik untuk peran lain, anonim, dan mode lokal);
2. bentuk isian tepat sesuai tindakan (400): `ganti` wajib `kode_id` positif, `buat` dan `cabut` tanpa `kode_id`;
3. sesi berkuki (403; tanpa kuki tidak ada token);
4. token sah untuk tindakan dan order itu (403, tanpa efek);
5. order Mini ada (404);
6. aksi lewat `guru_tautan_kode`: `buat` dan `ganti` memakai aturan anak (anak tak ada = 409); `cabut` memakai
   `cabut_semua` (idempoten, tanpa cek anak); kode basi atau sudah ada = 409; galat tulis = 503.

Kode mentah tampil sekali pada respons 200 buat/ganti (`no-store`, tanpa redirect). Cabut menjawab 200 yang sama
baik ada kode yang dicabut maupun tidak. Pencatat `oleh` = id akun admin sesi dan `peran` = admin. Blok GET tidak
memuat kode, akun, atau id siswa.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Dict, Optional, Tuple

import admin_http as h
import admin_kode_anak_pages as halaman
import admin_security
import admin_store
import form_token
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_kode as kode
import kelas_dasar as kd
import kelas_status as ks
import kelas_store as store
import paket_belajar_katalog as katalog
import pesanan
import pesanan_alur as alur

_log = logging.getLogger(__name__)

DOMAIN_TOKEN_ADMIN = b"kode-anak-admin-form-v1:"
KUNCI_TINDAKAN = "tindakan"
KUNCI_ORDER = "order_id"
KUNCI_KODE_ID = "kode_id"
KUNCI_TOKEN = "token"
_KUNCI_BUAT = frozenset((KUNCI_TINDAKAN, KUNCI_ORDER, KUNCI_TOKEN))
_KUNCI_UBAH = _KUNCI_BUAT | {KUNCI_KODE_ID}
_TINDAKAN_SAH = (halaman.TINDAKAN_BUAT, halaman.TINDAKAN_GANTI, halaman.TINDAKAN_CABUT)
MAKS_FIELD = 8
MAKS_DIGIT_KODE_ID = 18
SEKSI = "kelas_belajar"
JUDUL = "Paket Belajar 1 Bulan"
SUBJUDUL = "Kode anak untuk guru di detail order."
COPY_TOKEN = "Form kedaluwarsa atau tidak sah. Muat ulang halaman, lalu coba lagi."
COPY_ISIAN = "Isian kode anak tidak sah."
COPY_BASI = "Keadaan kode sudah berubah atau anak tidak lagi ada. Muat ulang halaman, lalu coba lagi."
COPY_LAYANAN = "Kode anak belum bisa diproses sekarang. Coba lagi sebentar."
_GALAT_BACA = (dasar.GalatTautan, sqlite3.Error, ValueError, OSError, admin_store.StoreBelumSiap)
_GALAT_BASI = (kode.AnakTakAda, dasar.KodeSudahAda, dasar.KodeBasi)
_GALAT_LAYANAN = (dasar.GalatTautan, sqlite3.Error, OSError, admin_store.StoreBelumSiap)
_ISIAN = (ValueError, KeyError, TypeError, pesanan.PesananDataTidakSah)


# --- identitas, token, dan isian --------------------------------------------------------------

def _aksi(tindakan: str, order_id: str) -> str:
    return f"kode:{tindakan}:{order_id}"


def _token(principal, sesi, tindakan: str, order_id: str) -> str:
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN_ADMIN, aksi=_aksi(tindakan, order_id))


def _token_sah(principal, sesi, tindakan: str, order_id: str, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN_ADMIN, aksi=_aksi(tindakan, order_id))


def _kode_id(nilai) -> Optional[int]:
    """id kode positif dari isian form; None bila bukan angka desimal ASCII yang masuk akal."""
    if type(nilai) is not str or not nilai.isascii() or not nilai.isdigit() or len(nilai) > MAKS_DIGIT_KODE_ID:
        return None
    angka = int(nilai)
    return angka if angka >= 1 else None


def _tindakan_isian(data: dict) -> Tuple[str, str, Optional[int]]:
    """(tindakan, order_id, kode_id) bila isian tepat sesuai tindakan; selain itu ValueError.

    `buat` dan `cabut` tanpa `kode_id`; `ganti` wajib `kode_id` positif (anti kirim-ulang M1).
    """
    tindakan = data.get(KUNCI_TINDAKAN)
    if tindakan not in _TINDAKAN_SAH:
        raise ValueError("tindakan tidak sah")
    harap = _KUNCI_UBAH if tindakan == halaman.TINDAKAN_GANTI else _KUNCI_BUAT
    if set(data) != harap:
        raise ValueError("isian tidak sah")
    order_id = kd.periksa_order_id(data[KUNCI_ORDER])
    if tindakan != halaman.TINDAKAN_GANTI:
        return tindakan, order_id, None
    kode_id = _kode_id(data[KUNCI_KODE_ID])
    if kode_id is None:
        raise ValueError("kode_id tidak sah")
    return tindakan, order_id, kode_id


# --- order dan kode ---------------------------------------------------------------------------

def _anak_mini_order(order_id: str) -> Optional[Tuple[str, int]]:
    """(akun_id, siswa_id) dari baris `kelas_order` Mini di admin-control.

    None bila order tak ada ATAU bukan paket Mini (Private tidak punya blok dan tidak menerima POST): keduanya
    dijawab sama oleh pemanggil.
    """
    with store.buka(h._path_admin()) as kon:
        baris = ks.baris_order(kon, order_id)
    if baris is None or baris["paket"] != katalog.KODE_MINI:
        return None
    return baris["akun_id"], baris["siswa_id"]


def _tokens(penangan, principal, order_id: str, aktif: Optional[dict]) -> Optional[Dict[str, str]]:
    """Token per tindakan yang tampil; None untuk sesi bukan kuki (tampilan baca-saja)."""
    if principal.metode != "cookie":
        return None
    sesi = h._wajib_cookie(penangan, principal)
    tindakan = (halaman.TINDAKAN_BUAT,) if aktif is None else (halaman.TINDAKAN_GANTI, halaman.TINDAKAN_CABUT)
    return {nama: _token(principal, sesi, nama, order_id) for nama in tindakan}


def blok_html(penangan, principal, order_id: str) -> str:
    """Blok 'Kode anak untuk guru' untuk detail order. Galat baca menjadi blok tak terbaca (halaman tetap 200)."""
    try:
        anak = _anak_mini_order(order_id)
        if anak is None:
            return ""
        aktif = kode.kode_aktif(anak[0], anak[1])
        tokens = _tokens(penangan, principal, order_id, aktif)
    except _GALAT_BACA as galat:
        _log.warning("kode anak tidak terbaca untuk detail order: %s", type(galat).__name__)
        return halaman.blok_tak_terbaca()
    return halaman.blok(order_id, aktif, tokens)


# --- aksi POST --------------------------------------------------------------------------------

def _kini() -> str:
    return kd.ke_baku(alur.waktu_sekarang())


def _laksanakan(principal, order_id: str, akun_id: str, siswa_id: int, tindakan: str,
                kode_id: Optional[int]) -> str:
    """Isi halaman hasil. Kode mentah hanya ada di isi buat/ganti. Galat domain dan tulis naik ke pemanggil."""
    pencatat = {"oleh": principal.id_akun, "peran": aturan.PERAN_ADMIN, "pada": _kini()}
    if tindakan == halaman.TINDAKAN_BUAT:
        mentah = kode.buat_kode_baru(akun_id, siswa_id, **pencatat)
        return halaman.halaman_kode_baru(order_id, aturan.tampilkan(mentah))
    if tindakan == halaman.TINDAKAN_GANTI:
        mentah = kode.ganti_kode(akun_id, siswa_id, kode_id_diharapkan=kode_id, **pencatat)
        return halaman.halaman_kode_baru(order_id, aturan.tampilkan(mentah))
    kode.cabut_semua(akun_id, siswa_id, **pencatat)
    return halaman.halaman_cabut(order_id)


def _kirim_isi(penangan, principal, isi: str) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SEKSI, isi, penangan=penangan, judul=JUDUL, subjudul=SUBJUDUL), 200)


def _jalankan(penangan, principal) -> None:
    data = admin_security.baca_form(penangan, maksimum_field=MAKS_FIELD)
    tindakan, order_id, kode_id = _tindakan_isian(data)
    sesi = h._wajib_cookie(penangan, principal)
    if not _token_sah(principal, sesi, tindakan, order_id, data[KUNCI_TOKEN]):
        raise PermissionError("token kode anak tidak sah")
    anak = _anak_mini_order(order_id)
    if anak is None:
        raise LookupError("order tidak ada atau bukan Mini")
    isi = _laksanakan(principal, order_id, anak[0], anak[1], tindakan, kode_id)
    _kirim_isi(penangan, principal, isi)


def tangani_post(penangan, jalur) -> bool:
    """POST `/admin/kelas/kode-anak`. False bila jalur bukan milik modul ini."""
    if jalur != halaman.RUTE_KODE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        _jalankan(penangan, principal)
    except PermissionError:
        h._galat(penangan, 403, COPY_TOKEN)
    except _ISIAN:
        h._galat(penangan, 400, COPY_ISIAN)
    except LookupError:
        h._tidak_ada(penangan)
    except _GALAT_BASI as galat:
        _log.info("kode anak admin tidak selesai: %s", type(galat).__name__)
        h._galat(penangan, 409, COPY_BASI)
    except _GALAT_LAYANAN as galat:
        _log.warning("kode anak admin gagal ditulis: %s", type(galat).__name__)
        h._galat(penangan, 503, COPY_LAYANAN)
    return True

"""Koreksi admin atas jadwal tetap guru (3d, WP3): `GET /admin/jadwal/tetap`, `GET` dan `POST` `/<guru_akun>`.

Hanya principal admin; selain itu 404 identik dengan rute tak dikenal (`admin_http._tidak_ada`). Gerbang
`guru_jadwal_tetap_aktif()` mati = 404 identik untuk semua, admin juga, tanpa membaca atau membuat DB. Hanya sesi
berkuki yang boleh menulis (Basic = 403). Tanpa sandi ulang (bukan aksi uang). `oleh` selalu id akun admin dari sesi,
tidak pernah dari form atau URL. Tanpa pembatasan laju: pengelola tidak dibatasi (plan §2b).

Urutan POST; tiap langkah yang gagal berhenti tanpa tulis:
1. principal admin dan gerbang menyala (selain itu 404); pola id guru di URL (cacat = 404);
2. sesi berkuki (Basic = 403);
3. isian terbaca dengan batas field dan ukuran (400, atau 403 bila asal/sesi ditolak);
4. token sah untuk aksi yang dibangun dari nilai mentah isian (403);
5. guru ada di peta guru aktif (404);
6. himpunan field persis dan format (400);
7. putus: usulan harus yang sedang menunggu milik guru di URL (409, tanpa tulis);
8. tulis: konflik = 409, galat lain = 503; sukses = PRG 303 ke `?pesan=tersimpan`.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from typing import Optional

import admin_http as h
import admin_jadwal_tetap_pages as halaman
import admin_security
import form_token
import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as tetap
import jadwal_admin_http as jah
import kelas_dasar as kd
import pesanan_alur as alur

_log = logging.getLogger(__name__)

SEKSI = "kelas_belajar"
RUTE_PREFIX = halaman.RUTE + "/"
DOMAIN_TOKEN = b"admin-jadwal-tetap-v1:"
POLA_GURU = re.compile(r"akun_[0-9a-f]{32}")
POLA_USULAN = re.compile(r"[1-9][0-9]{0,11}")  # 1 sampai 12 digit ASCII tanpa nol di depan
MAKS_FIELD = len(aturan.KUNCI_FORM) + 2  # 28 blok, token, dan aksi
KUNCI_TOKEN = "token"
KUNCI_AKSI = "aksi"
KUNCI_USULAN = "usulan_id"
KUNCI_PUTUSAN = "putusan"
KUNCI_PESAN = "pesan"
AKSI_TETAPKAN = "tetapkan"
AKSI_PUTUS = "putus"
KUNCI_PUTUS = frozenset({KUNCI_TOKEN, KUNCI_AKSI, KUNCI_USULAN, KUNCI_PUTUSAN})
KUNCI_TETAPKAN = aturan.KUNCI_FORM | frozenset({KUNCI_TOKEN, KUNCI_AKSI})
PESAN_TERSIMPAN = "tersimpan"
COPY_TOKEN = "Form kedaluwarsa atau tidak sah. Muat ulang halaman, lalu coba lagi."
COPY_ISIAN = "Isian jadwal tetap tidak sah. Muat ulang halaman, lalu coba lagi. Tidak ada yang diubah."
COPY_KONFLIK = "Usulan sudah berubah, muat ulang halaman. Tidak ada yang diubah."
COPY_LAYANAN = "Jadwal tetap belum bisa disimpan sekarang. Coba lagi sebentar. Tidak ada yang diubah."
_GALAT_BACA = (tetap.GalatTetap, sqlite3.Error, OSError, ValueError)


class _Tolak(Exception):
    """Langkah POST yang menolak. Kode 404 = rute tak dikenal (`_tidak_ada`); lainnya = halaman galat dengan `pesan`."""

    def __init__(self, kode: int, pesan: str = ""):
        super().__init__(pesan)
        self.kode = kode
        self.pesan = pesan


# --- jalur, gerbang, dan identitas --------------------------------------------------------------

def _kini() -> str:
    return kd.ke_baku(alur.waktu_sekarang())


def _gerbang_menyala() -> bool:
    return aturan.guru_jadwal_tetap_aktif()


def _cocok_jalur(jalur: str) -> bool:
    return jalur == halaman.RUTE or jalur.startswith(RUTE_PREFIX)


def _guru_dari_jalur(jalur: str) -> Optional[str]:
    """Id guru dari URL bila polanya sah; None untuk daftar, akhiran cacat, atau id berpola lain."""
    if not jalur.startswith(RUTE_PREFIX):
        return None
    sisa = jalur[len(RUTE_PREFIX):]
    return sisa if POLA_GURU.fullmatch(sisa) else None


def _nama_guru(guru: str) -> Optional[str]:
    """Nama pengguna guru aktif dari peta akun; None bila bukan guru aktif."""
    return jah.guru_map().get(guru)


# --- token --------------------------------------------------------------------------------------

def _aksi_tetapkan(guru: str) -> str:
    return f"{AKSI_TETAPKAN}:{guru}"


def _aksi_putus(usulan_id, putusan) -> str:
    return f"{AKSI_PUTUS}:{usulan_id}:{putusan}"


def _token(principal, sesi: str, aksi: str) -> str:
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN, aksi=aksi)


def _aksi_dari_isian(guru: str, data: dict) -> Optional[str]:
    """Aksi token yang harus cocok, dibangun dari nilai mentah isian. None bila isian belum lengkap."""
    aksi = data.get(KUNCI_AKSI)
    if aksi == AKSI_TETAPKAN:
        return _aksi_tetapkan(guru)
    if aksi == AKSI_PUTUS and KUNCI_USULAN in data and KUNCI_PUTUSAN in data:
        return _aksi_putus(data[KUNCI_USULAN], data[KUNCI_PUTUSAN])
    return None


def _token_sah(principal, sesi: str, guru: str, data: dict) -> bool:
    aksi = _aksi_dari_isian(guru, data)
    return aksi is not None and form_token.token_sah(
        principal, sesi, data.get(KUNCI_TOKEN), domain=DOMAIN_TOKEN, aksi=aksi)


# --- GET: daftar dan detail ---------------------------------------------------------------------

def _daftar_view(peta_guru: dict) -> list:
    aktif = tetap.aktif_semua()
    menunggu = tetap.menunggu_semua()
    urut = sorted(peta_guru.items(), key=lambda item: item[1].casefold())
    return [
        {
            "guru": guru,
            "nama": nama,
            "blok_aktif": aktif[guru]["blok"] if guru in aktif else None,
            "menunggu": guru in menunggu,
        }
        for guru, nama in urut
    ]


def _menunggu_view(menunggu: Optional[dict], principal, sesi: Optional[str]) -> Optional[dict]:
    if menunggu is None:
        return None
    token = None
    if sesi is not None:
        token = {putusan: _token(principal, sesi, _aksi_putus(menunggu["usulan_id"], putusan))
                 for putusan in tetap.PUTUSAN_SAH}
    return {"usulan_id": menunggu["usulan_id"], "blok": menunggu["blok"], "dibuat": menunggu["dibuat"],
            "token": token}


def _detail_view(principal, sesi: Optional[str], guru: str, nama: str, pesan: Optional[str]) -> dict:
    return {
        "guru": guru,
        "nama": nama,
        "pesan": pesan,
        "aktif": tetap.aktif(guru),
        "menunggu": _menunggu_view(tetap.menunggu(guru), principal, sesi),
        "riwayat": tetap.riwayat(guru, batas=tetap.BATAS_RIWAYAT_BAWAAN),
        "bisa_isi": sesi is not None,
        "token_tetapkan": _token(principal, sesi, _aksi_tetapkan(guru)) if sesi is not None else None,
    }


def _kueri_kosong(penangan) -> None:
    """Daftar tidak menerima parameter: `_query` melempar ValueError bila ada kueri apa pun."""
    h._query(penangan, diizinkan=frozenset())


def _pesan_detail(penangan) -> Optional[str]:
    """Banner hanya dari kode tetap `tersimpan`. Kueri lain atau nilai lain = ValueError (404 oleh pemanggil)."""
    kueri = h._query(penangan, diizinkan=frozenset({KUNCI_PESAN}))
    if not kueri:
        return None
    if kueri.get(KUNCI_PESAN) != PESAN_TERSIMPAN:
        raise ValueError("Parameter tidak dikenal.")
    return halaman.COPY_TERSIMPAN


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SEKSI, isi, penangan=penangan, judul=halaman.JUDUL, subjudul=halaman.SUBJUDUL), kode)


def _get_daftar(penangan, principal) -> None:
    try:
        _kueri_kosong(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        isi = halaman.halaman_daftar(_daftar_view(jah.guru_map()))
    except _GALAT_BACA as galat:
        _log.warning("daftar jadwal tetap tidak terbaca: %s", type(galat).__name__)
        return _kirim(penangan, principal, halaman.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, isi)


def _get_detail(penangan, principal, jalur: str) -> None:
    guru = _guru_dari_jalur(jalur)
    try:
        pesan = _pesan_detail(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    if guru is None:
        return h._tidak_ada(penangan)
    try:
        nama = _nama_guru(guru)
        if nama is None:
            return h._tidak_ada(penangan)
        view = _detail_view(principal, h._token_sesi(penangan, principal), guru, nama, pesan)
        isi = halaman.halaman_detail(view)
    except _GALAT_BACA as galat:
        _log.warning("jadwal tetap guru tidak terbaca: %s", type(galat).__name__)
        return _kirim(penangan, principal, halaman.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, isi)


def tangani_get(penangan, jalur) -> bool:
    """GET daftar dan detail. False untuk jalur di luar awalan; selain admin atau gerbang mati = 404 identik."""
    if not _cocok_jalur(jalur):
        return False
    principal = h._principal_admin(penangan)
    if principal is None or not _gerbang_menyala():
        h._tidak_ada(penangan)
        return True
    if jalur == halaman.RUTE:
        _get_daftar(penangan, principal)
    else:
        _get_detail(penangan, principal, jalur)
    return True


# --- POST: urutan wajib, tiap langkah gagal = berhenti tanpa tulis ------------------------------

def _sesi_berkuki(penangan, principal) -> str:
    try:
        return h._wajib_cookie(penangan, principal)
    except PermissionError:
        raise _Tolak(403, COPY_TOKEN) from None


def _baca_isian(penangan) -> dict:
    try:
        return admin_security.baca_form(penangan, maksimum_field=MAKS_FIELD)
    except PermissionError:
        raise _Tolak(403, COPY_TOKEN) from None
    except ValueError:
        raise _Tolak(400, COPY_ISIAN) from None


def _isian_putus(data: dict) -> tuple:
    if set(data) != KUNCI_PUTUS:
        raise _Tolak(400, COPY_ISIAN)
    if POLA_USULAN.fullmatch(data[KUNCI_USULAN]) is None or data[KUNCI_PUTUSAN] not in tetap.PUTUSAN_SAH:
        raise _Tolak(400, COPY_ISIAN)
    return int(data[KUNCI_USULAN]), data[KUNCI_PUTUSAN]


def _blok_dari_isian(data: dict) -> str:
    """Teks kanonik blok dari 28 field; token dan aksi tidak ikut. Field berlebih atau kurang = 400."""
    if set(data) != KUNCI_TETAPKAN:
        raise _Tolak(400, COPY_ISIAN)
    try:
        return aturan.kanonik(aturan.blok_dari_form({kunci: data[kunci] for kunci in aturan.KUNCI_FORM}))
    except ValueError:
        raise _Tolak(400, COPY_ISIAN) from None


def _pastikan_usulan_menunggu(guru: str, usulan_id: int) -> None:
    """Usulan yang diputus harus yang sedang menunggu milik guru di URL. Selain itu 409 tanpa tulis."""
    menunggu = tetap.menunggu(guru)
    if menunggu is None or menunggu["usulan_id"] != usulan_id:
        raise _Tolak(409, COPY_KONFLIK)


def _putus(principal, guru: str, data: dict) -> None:
    usulan_id, putusan = _isian_putus(data)
    _pastikan_usulan_menunggu(guru, usulan_id)
    tetap.putus(usulan_id=usulan_id, putusan=putusan, admin_akun=principal.id_akun, dibuat=_kini())


def _tetapkan(principal, guru: str, data: dict) -> None:
    blok = _blok_dari_isian(data)
    tetap.tetapkan_admin(guru_akun=guru, blok=blok, admin_akun=principal.id_akun, dibuat=_kini())


def _jalankan_post(penangan, principal, guru: str) -> None:
    sesi = _sesi_berkuki(penangan, principal)
    data = _baca_isian(penangan)
    if not _token_sah(principal, sesi, guru, data):
        raise _Tolak(403, COPY_TOKEN)
    if _nama_guru(guru) is None:
        raise _Tolak(404)
    if data[KUNCI_AKSI] == AKSI_PUTUS:
        _putus(principal, guru, data)
    else:
        _tetapkan(principal, guru, data)


def _kirim_tolak(penangan, tolak: _Tolak) -> None:
    if tolak.kode == 404:
        h._tidak_ada(penangan)
        return
    h._galat(penangan, tolak.kode, tolak.pesan)


def _kirim_galat_tulis(penangan, galat: tetap.GalatTetap) -> None:
    if galat.kind == tetap.KIND_KONFLIK:
        h._galat(penangan, 409, COPY_KONFLIK)
        return
    _log.warning("jadwal tetap guru gagal ditulis: %s", galat.kind)
    h._galat(penangan, 503, COPY_LAYANAN)


def _post(penangan, principal, guru: str) -> None:
    try:
        _jalankan_post(penangan, principal, guru)
    except _Tolak as tolak:
        _kirim_tolak(penangan, tolak)
    except tetap.GalatTetap as galat:
        _kirim_galat_tulis(penangan, galat)
    except _GALAT_BACA as galat:
        _log.warning("jadwal tetap guru tidak terbaca: %s", type(galat).__name__)
        h._galat(penangan, 503, COPY_LAYANAN)
    else:
        h._redirect(penangan, f"{halaman.tautan_guru(guru)}?{KUNCI_PESAN}={PESAN_TERSIMPAN}")


def tangani_post(penangan, jalur) -> bool:
    """POST koreksi per guru. False untuk jalur di luar awalan; selain admin, gerbang mati, atau id cacat = 404 identik."""
    if not _cocok_jalur(jalur):
        return False
    principal = h._principal_admin(penangan)
    guru = _guru_dari_jalur(jalur)
    if principal is None or guru is None or not _gerbang_menyala():
        h._tidak_ada(penangan)
        return True
    _post(penangan, principal, guru)
    return True

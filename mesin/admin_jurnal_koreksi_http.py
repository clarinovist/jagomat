"""Koreksi admin atas kehadiran dan jurnal pertemuan (2b): `GET` dan `POST /admin/jadwal/jurnal/<pertemuan_id>`.

Hanya principal admin; selain itu 404 identik dengan rute tak dikenal (`admin_http._tidak_ada`). Hanya sesi berkuki
yang boleh menulis (Basic = 403). Tidak ada pengunci 7 hari untuk admin (keputusan Pemilik 27 Nov 2026 d), tetapi
hanya pertemuan yang sudah mulai dan tidak dibatalkan yang bisa dikoreksi. Guru tetap terkunci di rute guru.

Tulis hanya lewat `guru_pertemuan_dasar.catat` dengan `peran='admin'` dan `oleh` = id akun admin sesi (tidak pernah
dari form). Urutan POST; tiap langkah yang gagal berhenti tanpa tulis:
1. principal admin (selain itu 404 identik);
2. sesi berkuki (Basic = 403);
3. laju per akun dan IP (429);
4. isian terbaca dengan batas field dan format (400, atau 403 untuk asal silang);
5. token sah untuk aksi `koreksi:<id>` (403);
6. pertemuan ada (404);
7. pertemuan sudah mulai dan tidak dibatalkan (409);
8. himpunan field persis `{token, topik}` ditambah `anak_<handle>` untuk setiap anggota (400);
9. topik dan status sah untuk SETIAP anggota (400);
10. catat: galat catatan atau layanan = 503; sukses = PRG 303 ke `?pesan=tersimpan`.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Tuple

import admin_http as h
import admin_jurnal_koreksi_baca as kb
import admin_jurnal_koreksi_pages as halaman
import admin_security
import admin_store
import auth
import database
import form_token
import guru_jadwal_baca as gjb
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as dasar
import jadwal_admin_http as jah
import jadwal_store as js
import kelas_dasar as kd
import pesanan_alur as alur
import schema_jadwal
from learning_cycle_http import GalatForm, _batasi_laju

_log = logging.getLogger(__name__)

RUTE_PREFIX = halaman.RUTE + "/"
SEKSI = "kelas_belajar"
DOMAIN_TOKEN = b"admin-jurnal-koreksi-v1:"
DOMAIN_HANDLE = b"admin-jurnal-handle-v1:"
PANJANG_HANDLE = 16
PERAN_ADMIN = halaman.PERAN_ADMIN
POLA_ID = re.compile(r"[1-9][0-9]{0,11}")  # 1 sampai 12 digit ASCII tanpa nol di depan; jauh di bawah batas INTEGER
MAKS_FIELD = schema_jadwal.KUOTA_MAKS + 2  # token, topik, dan paling banyak satu field status per anak
KUNCI_TOKEN = "token"
KUNCI_TOPIK = "topik"
KUNCI_PESAN = "pesan"
AWALAN_ANAK = "anak_"
PESAN_TERSIMPAN = "tersimpan"
COPY_TOKEN = "Form kedaluwarsa atau tidak sah. Muat ulang halaman, lalu coba lagi."
COPY_ISIAN = "Isian koreksi tidak sah. Muat ulang halaman, lalu coba lagi. Tidak ada yang diubah."
COPY_LAJU = "Terlalu banyak permintaan. Coba lagi sebentar."
COPY_LAYANAN = "Koreksi belum bisa disimpan sekarang. Coba lagi sebentar. Tidak ada yang diubah."
_GALAT_BACA = (admin_store.StoreBelumSiap, sqlite3.Error, OSError, ValueError)
_GALAT_LAYANAN = _GALAT_BACA + (dasar.GalatCatatan,)


class _Tolak(Exception):
    """Langkah POST yang menolak. Kode 404 = rute tak dikenal (`_tidak_ada`); lainnya = halaman galat dengan `pesan`."""

    def __init__(self, kode: int, pesan: str = ""):
        super().__init__(pesan)
        self.kode = kode
        self.pesan = pesan


# --- identitas, handle, dan token ---------------------------------------------------------------

def _kini() -> str:
    return kd.ke_baku(alur.waktu_sekarang())


def _id_dari_jalur(jalur: str) -> Optional[int]:
    cocok = POLA_ID.fullmatch(jalur[len(RUTE_PREFIX):])
    return int(cocok.group(0)) if cocok else None


def handle_anak(principal, kunci: str, order_id: str) -> str:
    """Handle buram satu anak di satu pertemuan untuk admin: HMAC kunci akun admin, domain terpisah dari guru."""
    akun = auth.cari_akun(principal.pengguna)
    if akun is None:
        raise ValueError("Akun pemegang sesi tidak ditemukan.")
    pesan = DOMAIN_HANDLE + kunci.encode() + b"|" + order_id.encode()
    return hmac.new(bytes.fromhex(akun["kunci"]), pesan, hashlib.sha256).hexdigest()[:PANJANG_HANDLE]


def _aksi(pertemuan_id: int) -> str:
    return f"koreksi:{pertemuan_id}"


def _buat_token(principal, sesi, pertemuan_id: int) -> str:
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN, aksi=_aksi(pertemuan_id))


def _token_sah(principal, sesi, pertemuan_id: int, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN, aksi=_aksi(pertemuan_id))


# --- baca: pertemuan, nama, dan riwayat ---------------------------------------------------------

def _muat_pertemuan(pertemuan_id: int, kini: str) -> Optional[dict]:
    """Pertemuan Mini atau Private berdasar id tanpa filter guru, atau None. Hanya SELECT pada DB jadwal."""
    with js.buka(admin_store.BAWAAN) as kon:
        return kb.pertemuan_untuk_koreksi(kon, pertemuan_id, kini)


@contextmanager
def _buka_latihan_baca():
    """latihan.db mode ro: tidak pernah membuat berkas atau menulis."""
    uri = Path(database.BAWAAN).resolve().as_uri() + "?mode=ro"
    kon = sqlite3.connect(uri, uri=True)
    try:
        yield kon
    finally:
        kon.close()


def _nama_anggota(anggota: list) -> Dict[str, str]:
    """{order_id: nama}; latihan.db tak terbuka = placeholder untuk semua anggota (halaman tetap tampil)."""
    if not anggota:
        return {}
    try:
        with _buka_latihan_baca() as kon:
            return kb.nama_anggota(kon, anggota)
    except sqlite3.Error:
        _log.warning("nama anak tidak terbaca untuk koreksi jurnal")
        return {a["order_id"]: gjb.PLACEHOLDER_NAMA for a in anggota}


def _keadaan_riwayat(pertemuan: dict) -> Tuple[dict, dict]:
    keadaan = dasar.terkini(pertemuan["kunci"], pertemuan["mulai"])
    riwayat = dasar.riwayat(pertemuan["kunci"], pertemuan["mulai"])
    return keadaan, riwayat


def _anggota_tampil(principal, pertemuan: dict, keadaan: dict, nama: dict) -> list:
    """Anggota untuk halaman: nama, handle, dan status terkini. Tanpa order_id maupun siswa_id."""
    daftar = [
        {
            "nama": nama.get(a["order_id"], gjb.PLACEHOLDER_NAMA),
            "handle": handle_anak(principal, pertemuan["kunci"], a["order_id"]),
            "status_terkini": keadaan["hadir"].get(a["order_id"]),
        }
        for a in pertemuan["anggota"]
    ]
    return sorted(daftar, key=lambda anak: anak["nama"].casefold())


def _judul(pertemuan: dict, nama: dict) -> str:
    if pertemuan["jenis"] == kb.JENIS_MINI:
        return "Mini Class: " + (pertemuan["nama_kelas"] or "")
    if not pertemuan["anggota"]:
        return "Private"
    return "Private: " + nama.get(pertemuan["anggota"][0]["order_id"], gjb.PLACEHOLDER_NAMA)


def _opsi_topik() -> list:
    return [(id_topik, aturan.label_topik(id_topik)) for id_topik in aturan.daftar_topik_jurnal()]


def _tampilan(penangan, principal, pertemuan: dict, pesan: Optional[str]) -> dict:
    """View-model halaman. Formulir dan token hanya untuk sesi berkuki dan pertemuan yang boleh dikoreksi."""
    keadaan, riwayat = _keadaan_riwayat(pertemuan)
    nama = _nama_anggota(pertemuan["anggota"])
    bisa_isi = pertemuan["keterangan"] is None and principal.metode == "cookie"
    return {
        "judul": _judul(pertemuan, nama),
        "ke": pertemuan["ke"],
        "mulai": pertemuan["mulai"],
        "menit": pertemuan["menit"],
        "keterangan": pertemuan["keterangan"],
        "anggota": _anggota_tampil(principal, pertemuan, keadaan, nama),
        "topik_terkini": keadaan["topik"],
        "opsi_topik": _opsi_topik(),
        "riwayat": kb.susun_riwayat(riwayat, nama, jah.guru_map()),
        "aksi_form": f"{RUTE_PREFIX}{pertemuan['id']}" if bisa_isi else None,
        "token": _buat_token(principal, penangan._ambil_token(), pertemuan["id"]) if bisa_isi else None,
        "pesan": pesan,
    }


# --- GET -----------------------------------------------------------------------------------------

def _pesan_get(penangan) -> Optional[str]:
    """Banner hanya dari kode tetap. Kueri lain atau nilai `pesan` lain = ValueError (404 oleh pemanggil)."""
    kueri = h._query(penangan, diizinkan=frozenset({KUNCI_PESAN}))
    if not kueri:
        return None
    if kueri.get(KUNCI_PESAN) != PESAN_TERSIMPAN:
        raise ValueError("Parameter tidak dikenal.")
    return halaman.COPY_TERSIMPAN


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SEKSI, isi, penangan=penangan, judul=halaman.JUDUL, subjudul=halaman.SUBJUDUL), kode)


def _get(penangan, principal, pertemuan_id: int) -> None:
    try:
        pesan = _pesan_get(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        pertemuan = _muat_pertemuan(pertemuan_id, _kini())
        if pertemuan is None:
            return h._tidak_ada(penangan)
        tampilan = _tampilan(penangan, principal, pertemuan, pesan)
    except _GALAT_LAYANAN as galat:
        _log.warning("koreksi jurnal tidak terbaca: %s", type(galat).__name__)
        return _kirim(penangan, principal, halaman.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, halaman.halaman(tampilan))


def tangani_get(penangan, jalur) -> bool:
    """GET `/admin/jadwal/jurnal/<id>`. False untuk jalur di luar awalan; selain admin = 404 identik."""
    if not jalur.startswith(RUTE_PREFIX):
        return False
    principal = h._principal_admin(penangan)
    pertemuan_id = _id_dari_jalur(jalur)
    if principal is None or pertemuan_id is None:
        h._tidak_ada(penangan)
        return True
    _get(penangan, principal, pertemuan_id)
    return True


# --- POST: urutan wajib, tiap langkah gagal = berhenti tanpa tulis -----------------------------

def _sesi_berkuki(penangan, principal) -> str:
    try:
        return h._wajib_cookie(penangan, principal)
    except PermissionError:
        raise _Tolak(403, COPY_TOKEN) from None


def _batasi(penangan, principal) -> None:
    try:
        _batasi_laju(penangan, principal.pengguna)
    except GalatForm:
        raise _Tolak(429, COPY_LAJU) from None


def _baca_isian(penangan) -> dict:
    try:
        return admin_security.baca_form(penangan, maksimum_field=MAKS_FIELD)
    except PermissionError:
        raise _Tolak(403, COPY_TOKEN) from None
    except ValueError:
        raise _Tolak(400, COPY_ISIAN) from None


def _peta_handle(principal, pertemuan: dict) -> Dict[str, str]:
    """Handle -> order_id untuk anggota yang dihitung ulang server. Tidak pernah diambil dari form."""
    return {handle_anak(principal, pertemuan["kunci"], a["order_id"]): a["order_id"]
            for a in pertemuan["anggota"]}


def _kunci_form(peta: Dict[str, str]) -> frozenset:
    return frozenset({KUNCI_TOKEN, KUNCI_TOPIK}) | frozenset(AWALAN_ANAK + handle for handle in peta)


def _hadir_dari_form(data: dict, peta: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Pemetaan order_id -> status; None bila ada status yang tidak sah. Semua anggota wajib ada."""
    hadir = {}
    for handle, order_id in peta.items():
        status = data[AWALAN_ANAK + handle]
        if not aturan.status_sah(status):
            return None
        hadir[order_id] = status
    return hadir


def _isian_sah(principal, pertemuan: dict, data: dict) -> Tuple[str, Dict[str, str]]:
    peta = _peta_handle(principal, pertemuan)
    if set(data) != _kunci_form(peta):
        raise _Tolak(400, COPY_ISIAN)
    topik = data[KUNCI_TOPIK]
    hadir = _hadir_dari_form(data, peta)
    if hadir is None or not aturan.topik_sah(topik):
        raise _Tolak(400, COPY_ISIAN)
    return topik, hadir


def _catat(principal, pertemuan: dict, topik: str, hadir: Dict[str, str], kini: str) -> None:
    try:
        dasar.catat(kunci=pertemuan["kunci"], pertemuan_id=pertemuan["id"], mulai=pertemuan["mulai"],
                    topik=topik, hadir=hadir, oleh=principal.id_akun, peran=PERAN_ADMIN, pada=kini)
    except ValueError:
        raise _Tolak(400, COPY_ISIAN) from None


def _jalankan_post(penangan, principal, pertemuan_id: int) -> None:
    sesi = _sesi_berkuki(penangan, principal)
    _batasi(penangan, principal)
    data = _baca_isian(penangan)
    if not _token_sah(principal, sesi, pertemuan_id, data.get(KUNCI_TOKEN)):
        raise _Tolak(403, COPY_TOKEN)
    kini = _kini()
    pertemuan = _muat_pertemuan(pertemuan_id, kini)
    if pertemuan is None:
        raise _Tolak(404)
    if pertemuan["keterangan"] is not None:
        raise _Tolak(409, halaman.COPY_KETERANGAN[pertemuan["keterangan"]])
    topik, hadir = _isian_sah(principal, pertemuan, data)
    _catat(principal, pertemuan, topik, hadir, kini)
    h._redirect(penangan, f"{RUTE_PREFIX}{pertemuan_id}?{KUNCI_PESAN}={PESAN_TERSIMPAN}")


def _kirim_tolak(penangan, tolak: _Tolak) -> None:
    if tolak.kode == 404:
        h._tidak_ada(penangan)
        return
    h._galat(penangan, tolak.kode, tolak.pesan)


def _post(penangan, principal, pertemuan_id: int) -> None:
    try:
        _jalankan_post(penangan, principal, pertemuan_id)
    except _Tolak as tolak:
        _kirim_tolak(penangan, tolak)
    except _GALAT_LAYANAN as galat:
        _log.warning("koreksi jurnal gagal ditulis: %s", type(galat).__name__)
        h._galat(penangan, 503, COPY_LAYANAN)


def tangani_post(penangan, jalur) -> bool:
    """POST `/admin/jadwal/jurnal/<id>`. False untuk jalur di luar awalan; selain admin = 404 identik."""
    if not jalur.startswith(RUTE_PREFIX):
        return False
    principal = h._principal_admin(penangan)
    pertemuan_id = _id_dari_jalur(jalur)
    if principal is None or pertemuan_id is None:
        h._tidak_ada(penangan)
        return True
    _post(penangan, principal, pertemuan_id)
    return True

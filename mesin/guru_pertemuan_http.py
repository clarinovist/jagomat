"""Rute guru `GET/POST /guru/pertemuan/<id>`: catat kehadiran dan jurnal satu pertemuan (Fase 2a-2).

Identitas HANYA dari sesi: `guru_id` = `id_akun` principal peran guru. `<id>` dari path dicocokkan dengan kepemilikan
di SQL (`guru_jadwal_baca.pertemuan_milik`). Selain pemilik (admin, murid, anonim, mode lokal, guru lain, id cacat
atau tak ada) jawaban 404 identik dengan rute tak dikenal (`lembaga_http._tidak_ada`).

Tulis hanya lewat `guru_pertemuan_dasar.catat`, dan hanya setelah urutan POST terpenuhi: token sah untuk aksi
`pertemuan:<id>`, jendela R1/R2 (`boleh_catat`), dan kelengkapan isian (R5). Anak diidentifikasi di form lewat
handle buram `anak_<handle>` yang dihitung ulang server; id mentah tidak pernah tampil.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import logging
import re
import urllib.parse
from typing import Dict, Optional

import auth
import form_token
import guru_jadwal_baca as baca
import guru_jadwal_http as jadwal_http  # helper peran guru dan jam; modulnya tidak diubah di Fase 2
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as dasar
import guru_pertemuan_pages as halaman
import kontak_http  # `_baca_form` dipakai ulang: urlencoded, kunci tunggal, batas ukuran dan kolom
import lembaga_http  # `_tidak_ada` dan `_alihkan`: jawaban 404 identik dan PRG
from learning_cycle_http import GalatForm, _batasi_laju
from support_pages import halaman_pesan

_log = logging.getLogger(__name__)
RUTE_PREFIX = "/guru/pertemuan/"
DOMAIN_TOKEN_PERTEMUAN = b"guru-pertemuan-form-v1:"
DOMAIN_HANDLE_ANAK = b"anak-handle-v1:"
PANJANG_HANDLE = 16
POLA_ID = re.compile(r"[1-9][0-9]{0,17}")  # 1 sampai 18 digit tanpa nol di depan; selalu di bawah batas INTEGER
KUNCI_TOKEN = "token"
KUNCI_TOPIK = "topik"
AWALAN_ANAK = "anak_"
PESAN_TERSIMPAN = "tersimpan"
TEKS_TERSIMPAN = "Catatan tersimpan."
JUDUL_TOLAK = "Pertemuan belum bisa dicatat"
JUDUL_GALAT_SIMPAN = "Catatan belum tersimpan"
TEKS_GALAT_SIMPAN = "Catatan pertemuan belum bisa disimpan sekarang. Coba lagi sebentar."
TEKS_TANPA_ANAK = "Belum ada anak di pertemuan ini."
KETERANGAN_ALASAN = {
    aturan.ALASAN_DIBATALKAN: "Pertemuan ini dibatalkan, jadi tidak ada yang bisa dicatat.",
    aturan.ALASAN_BELUM_MULAI: "Pertemuan belum dimulai. Kehadiran dan jurnal bisa dicatat setelah pertemuan mulai.",
    aturan.ALASAN_TERKUNCI: "Jendela pencatatan sudah ditutup, 7 hari sejak pertemuan selesai. Hubungi admin untuk koreksi.",
}


# --- handle dan token -----------------------------------------------------------------------------

def handle_anak(principal, kunci: str, order_id: str) -> str:
    """Handle buram satu anak di satu pertemuan: HMAC kunci akun dengan domain terpisah dari token.

    Tidak memuat order_id; beda per akun, kunci pertemuan, dan order. Dipakai sebagai bagian nama field `anak_<handle>`.
    """
    akun = auth.cari_akun(principal.pengguna)
    if akun is None:
        raise ValueError("Akun pemegang sesi tidak ditemukan.")
    pesan = DOMAIN_HANDLE_ANAK + kunci.encode() + b"|" + order_id.encode()
    return hmac.new(bytes.fromhex(akun["kunci"]), pesan, hashlib.sha256).hexdigest()[:PANJANG_HANDLE]


def _aksi_token(pertemuan_id: int) -> str:
    return f"pertemuan:{pertemuan_id}"


def _buat_token(principal, sesi, pertemuan_id: int) -> str:
    return form_token.buat_token(principal, sesi, domain=DOMAIN_TOKEN_PERTEMUAN, aksi=_aksi_token(pertemuan_id))


def _token_sah(principal, sesi, pertemuan_id: int, token) -> bool:
    return form_token.token_sah(principal, sesi, token, domain=DOMAIN_TOKEN_PERTEMUAN,
                                aksi=_aksi_token(pertemuan_id))


# --- muat pertemuan milik guru ------------------------------------------------------------------

def _id_dari_jalur(jalur: str) -> Optional[int]:
    cocok = POLA_ID.fullmatch(jalur[len(RUTE_PREFIX):])
    return int(cocok.group(0)) if cocok else None


def _lengkapi_kunci(milik: dict) -> Optional[dict]:
    """Tambahkan `kunci` pertemuan. Data jadwal yang tak bisa membentuk kunci dianggap tak ada (404)."""
    try:
        kunci = aturan.kunci_pertemuan(milik["id_awal"], milik["ke"])
    except ValueError:
        _log.warning("kunci pertemuan tidak sah pada data jadwal")
        return None
    return {**milik, "kunci": kunci}


def _muat_pertemuan(principal, jalur: str, kini: str) -> Optional[dict]:
    """Pertemuan milik guru sesi beserta `kunci`, atau None. Tanpa principal guru tidak ada yang dibaca."""
    pertemuan_id = _id_dari_jalur(jalur)
    if principal is None or pertemuan_id is None or auth.cari_akun(principal.pengguna) is None:
        return None
    milik = jadwal_http._baca_admin(
        lambda kon: baca.pertemuan_milik(kon, principal.id_akun, pertemuan_id, kini), None)
    if milik is None:
        return None
    return _lengkapi_kunci(milik)


# --- keadaan dan tampilan (GET) -----------------------------------------------------------------

def _keterangan(pertemuan: dict, kini: str) -> Optional[str]:
    """Alasan halaman hanya-baca; None bila form boleh tampil dan diisi."""
    alasan = aturan.boleh_catat(pertemuan["mulai"], pertemuan["menit"], pertemuan["dibatalkan"], kini)
    if alasan is not None:
        return KETERANGAN_ALASAN[alasan]
    if not pertemuan["anggota"]:
        return TEKS_TANPA_ANAK
    return None


def _keadaan_terkini(kunci: str, mulai: str) -> dict:
    try:
        return dasar.terkini(kunci, mulai)
    except dasar.GalatCatatan:
        _log.warning("catatan pertemuan tidak terbaca; form kosong ditampilkan")
        return {"topik": None, "hadir": {}}


def _opsi_topik() -> list:
    return [(id_topik, aturan.label_topik(id_topik)) for id_topik in aturan.daftar_topik_jurnal()]


def _anggota_tampilan(principal, pertemuan: dict, keadaan: dict, nama: dict) -> list:
    """Anggota untuk halaman: nama, handle, status terkini, dan akses habis. Tanpa order_id maupun siswa_id."""
    daftar = [
        {
            "nama": nama.get(a["siswa_id"], baca.PLACEHOLDER_NAMA),
            "handle": handle_anak(principal, pertemuan["kunci"], a["order_id"]),
            "status_terkini": keadaan["hadir"].get(a["order_id"]),
            "akses_habis": a["akses_habis"],
        }
        for a in pertemuan["anggota"]
    ]
    return sorted(daftar, key=lambda anak: anak["nama"].casefold())


def _judul(pertemuan: dict, nama: dict) -> str:
    if pertemuan["jenis"] == "kelompok":
        return "Mini Class: " + (pertemuan["nama_kelompok"] or "")
    siswa = pertemuan["anggota"][0]["siswa_id"] if pertemuan["anggota"] else None
    return "Private: " + nama.get(siswa, baca.PLACEHOLDER_NAMA)


def _tampilan_halaman(penangan, principal, pertemuan: dict, pesan: Optional[str], kini: str) -> dict:
    keterangan = _keterangan(pertemuan, kini)
    keadaan = _keadaan_terkini(pertemuan["kunci"], pertemuan["mulai"])
    nama = jadwal_http._nama_anak(a["siswa_id"] for a in pertemuan["anggota"])
    bisa_isi = keterangan is None
    return {
        "judul": _judul(pertemuan, nama),
        "ke": pertemuan["ke"],
        "mulai": pertemuan["mulai"],
        "menit": pertemuan["menit"],
        "anggota": _anggota_tampilan(principal, pertemuan, keadaan, nama),
        "topik_terkini": keadaan["topik"],
        "opsi_topik": _opsi_topik(),
        "aksi_form": f"{RUTE_PREFIX}{pertemuan['id']}" if bisa_isi else None,
        "token": _buat_token(principal, penangan._ambil_token(), pertemuan["id"]) if bisa_isi else None,
        "pesan": pesan,
        "keterangan": keterangan or "",
    }


def _pesan_get(jalur_penuh: str) -> Optional[str]:
    """Banner hanya dari kode tetap; nilai `pesan` lain diabaikan."""
    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    if (kueri.get("pesan") or [""])[0] == PESAN_TERSIMPAN:
        return TEKS_TERSIMPAN
    return None


def _kirim_halaman(penangan, principal, pertemuan: dict, pesan: Optional[str], kini: str) -> None:
    tampilan = _tampilan_halaman(penangan, principal, pertemuan, pesan, kini)
    penangan._kirim_privat(halaman.halaman_pertemuan(jadwal_http._ident(principal), tampilan))


# --- POST: urutan wajib, tiap langkah gagal = berhenti tanpa tulis -------------------------------

def _kirim_tolak(penangan, kode: int, judul: str, teks: str) -> None:
    isi = halaman_pesan(judul, f"<h1>{html.escape(judul)}</h1><p>{html.escape(teks)}</p>")
    penangan._kirim_privat(isi, kode)


def _kirim_galat_laju(penangan, galat: GalatForm) -> None:
    if galat.status == 429:
        _kirim_tolak(penangan, 429, "Terlalu banyak permintaan", "Coba lagi sebentar.")
    else:
        penangan._tolak_isian(galat.status)


def _peta_handle(principal, pertemuan: dict) -> Dict[str, str]:
    """Handle -> order_id untuk anggota yang dihitung ulang server. Tidak pernah diambil dari form."""
    return {handle_anak(principal, pertemuan["kunci"], a["order_id"]): a["order_id"]
            for a in pertemuan["anggota"]}


def _kunci_form_sah(peta: Dict[str, str]) -> frozenset:
    return frozenset({KUNCI_TOKEN, KUNCI_TOPIK}) | frozenset(AWALAN_ANAK + handle for handle in peta)


def _hadir_dari_form(data: dict, peta: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Pemetaan order_id -> status; None bila ada status yang tidak sah. Semua anggota wajib ada (R5)."""
    hadir = {}
    for handle, order_id in peta.items():
        status = data[AWALAN_ANAK + handle]
        if not aturan.status_sah(status):
            return None
        hadir[order_id] = status
    return hadir


def _jalur_tersimpan(pertemuan_id: int) -> str:
    return f"{RUTE_PREFIX}{pertemuan_id}?pesan={PESAN_TERSIMPAN}"


def _catat_isian(penangan, principal, pertemuan: dict, data: dict, kini: str) -> None:
    peta = _peta_handle(principal, pertemuan)
    if set(data) != _kunci_form_sah(peta):
        penangan._tolak_isian()
        return
    topik = data[KUNCI_TOPIK]
    hadir = _hadir_dari_form(data, peta)
    if hadir is None or not aturan.topik_sah(topik):
        penangan._tolak_isian()
        return
    try:
        dasar.catat(kunci=pertemuan["kunci"], pertemuan_id=pertemuan["id"], mulai=pertemuan["mulai"],
                    topik=topik, hadir=hadir, oleh=principal.id_akun, peran="guru", pada=kini)
    except ValueError:
        penangan._tolak_isian()
        return
    except dasar.GalatCatatan:
        _log.warning("catatan pertemuan gagal ditulis")
        _kirim_tolak(penangan, 503, JUDUL_GALAT_SIMPAN, TEKS_GALAT_SIMPAN)
        return
    lembaga_http._alihkan(penangan, _jalur_tersimpan(pertemuan["id"]))


def _proses_post(penangan, principal, pertemuan: dict, kini: str) -> None:
    try:
        _batasi_laju(penangan, principal.pengguna)
    except GalatForm as galat:
        _kirim_galat_laju(penangan, galat)
        return
    data = kontak_http._baca_form(penangan)
    if data is None:
        penangan._tolak_isian()
        return
    if not _token_sah(principal, penangan._ambil_token(), pertemuan["id"], data.get(KUNCI_TOKEN)):
        penangan._tolak_isian(403)
        return
    keterangan = _keterangan(pertemuan, kini)
    if keterangan is not None:
        _kirim_tolak(penangan, 409, JUDUL_TOLAK, keterangan)
        return
    _catat_isian(penangan, principal, pertemuan, data, kini)


# --- dispatcher ----------------------------------------------------------------------------------

def tangani_get(penangan, jalur: str) -> bool:
    """GET `/guru/pertemuan/<id>`. False untuk jalur di luar awalan; selain pemilik = 404 identik."""
    if not jalur.startswith(RUTE_PREFIX):
        return False
    principal = jadwal_http._principal_guru(penangan)
    kini = jadwal_http._kini()
    pertemuan = _muat_pertemuan(principal, jalur, kini)
    if pertemuan is None:
        lembaga_http._tidak_ada(penangan)
        return True
    _kirim_halaman(penangan, principal, pertemuan, _pesan_get(penangan.path), kini)
    return True


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/guru/pertemuan/<id>`. Dipanggil setelah palang sandi dan guard asal dispatcher."""
    if not jalur.startswith(RUTE_PREFIX):
        return False
    principal = jadwal_http._principal_guru(penangan)
    kini = jadwal_http._kini()
    pertemuan = _muat_pertemuan(principal, jalur, kini)
    if pertemuan is None:
        lembaga_http._tidak_ada(penangan)
        return True
    _proses_post(penangan, principal, pertemuan, kini)
    return True

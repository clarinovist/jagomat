"""Rute guru cek kemampuan gratis (funnel Fase 2b): mulai, hasil, tautan anak.

Dipanggil setelah palang sandi guru/admin di dispatcher (dekat `kontak_http`).
Aturan yang ditegakkan di sini, bukan di halaman:

- `id_akun` dan pemilik anak HANYA dari principal sesi server. Tidak ada id
  anak/sesi/cek di URL atau form, jadi tidak ada IDOR; field tak dikenal ditolak.
- Hanya peran guru. Admin menerima 404 byte-identik dengan rute tak dikenal
  (GET: halaman 404 GET; POST: halaman 404 POST). Murid/anonim sudah dihentikan
  palang sandi (401) sebelum modul ini.
- Sakelar `FUNNEL_AKTIF` mati: GET = halaman "belum dibuka" tanpa akses basis
  data; POST = tidak ditangani (jatuh ke 404 rute tak dikenal), tanpa efek.
- Token form HMAC (akun, revisi auth, sesi, aksi, waktu habis) dengan domain
  sendiri; token kontak atau token form lain tidak berlaku di sini.
- Mulai: persetujuan `setuju=1` wajib, gerbang `/persetujuan` (policy), pembatas
  laju 10 permulaan/IP/hari (in-memory, per proses), lalu `cek_gratis.mulai`.
- Tautan anak dibuat lewat `share_links` yang sudah ada dan hanya tampil pada
  respons POST pembuatnya (`_kirim_tautan`: no-store, tanpa referrer).
- Nama anak, skor, dan jawaban tidak masuk URL, log, atau pesan galat.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from datetime import datetime, timezone

import auth
import cek_gratis
import cek_pages
import database
import funnel_flag
import ip_klien
import share_links
from cek_gratis_skor import FORMAT_WAKTU
from kontak_http import _alihkan, _baca_form, _principal_guru
from support_pages import halaman_pesan

RUTE_MULAI = cek_pages.RUTE_MULAI
RUTE_HASIL = cek_pages.RUTE_HASIL
RUTE_TAUTAN = cek_pages.RUTE_TAUTAN
RUTE_GET = frozenset({RUTE_MULAI, RUTE_HASIL})
RUTE_POST = frozenset({RUTE_MULAI, RUTE_TAUTAN})
KUNCI_MULAI = frozenset({"token", "setuju"})
KUNCI_TAUTAN = frozenset({"token"})
UMUR_TOKEN_DETIK = 900
BATAS_PERMULAAN_PER_HARI = 10
JENDELA_LAJU_DETIK = 24 * 60 * 60
AKSI_MULAI = "cek-mulai"
AKSI_TAUTAN = "cek-tautan"
_DOMAIN_TOKEN = b"cek-form-v1:"
_BATAS_TOKEN = 256

_riwayat: dict = {}
_kunci_laju = threading.Lock()


def _tidak_ada(penangan, *, post: bool) -> None:
    """Jawaban sama persis dengan fallthrough rute tak dikenal (GET dan POST berbeda body)."""
    if post:
        penangan._kirim(halaman_pesan("404", "<h1>Tidak ada</h1>"), 404)
    else:
        penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def _mac(principal, sesi, aksi: str, kedaluwarsa: int):
    akun = auth.cari_akun(principal.pengguna)
    if akun is None:
        return None
    badan = json.dumps(
        [principal.id_akun, principal.revisi_auth,
         hashlib.sha256((sesi or "").encode()).hexdigest(), aksi, kedaluwarsa],
        separators=(",", ":"),
    ).encode()
    return hmac.new(bytes.fromhex(akun["kunci"]), _DOMAIN_TOKEN + badan, hashlib.sha256).hexdigest()


def buat_token(principal, sesi, aksi: str) -> str:
    """Token form berumur pendek, terikat ke akun, sesi, dan aksi formnya."""
    kedaluwarsa = int(time.time()) + UMUR_TOKEN_DETIK
    return f"{kedaluwarsa}.{_mac(principal, sesi, aksi, kedaluwarsa)}"


def token_sah(principal, sesi, aksi: str, token) -> bool:
    """True hanya untuk token utuh, belum kedaluwarsa, dan cocok dengan akun+sesi+aksi ini."""
    if type(token) is not str or not 0 < len(token) <= _BATAS_TOKEN:
        return False
    awal, titik, tanda = token.partition(".")
    if not titik or not awal.isascii() or not awal.isdigit():
        return False
    kedaluwarsa = int(awal)
    if int(time.time()) >= kedaluwarsa:
        return False
    harap = _mac(principal, sesi, aksi, kedaluwarsa)
    return harap is not None and hmac.compare_digest(tanda, harap)


def _izinkan_permulaan(penangan) -> bool:
    """Hitung satu permulaan untuk IP ini; False bila sudah 10 dalam 24 jam terakhir."""
    global _riwayat
    kini = time.monotonic()
    kunci = (penangan.server.server_address,
             ip_klien.ip_klien(penangan.headers, penangan.client_address))
    with _kunci_laju:
        aktif = {k: tuple(t for t in waktu if kini - t < JENDELA_LAJU_DETIK)
                 for k, waktu in _riwayat.items() if waktu and kini - waktu[-1] < JENDELA_LAJU_DETIK}
        waktu = aktif.get(kunci, ())
        if len(waktu) >= BATAS_PERMULAAN_PER_HARI:
            _riwayat = aktif
            return False
        _riwayat = {**aktif, kunci: (*waktu, kini)}
        return True


def _sekarang() -> str:
    return datetime.now(timezone.utc).strftime(FORMAT_WAKTU)


def _anak_akun(kon, pengguna: str):
    """Satu anak per akun: anak milik akun dengan id terkecil (atau None)."""
    return kon.execute(
        "SELECT id, nama FROM siswa WHERE pemilik = ? ORDER BY id LIMIT 1", (pengguna,)
    ).fetchone()


def _cek_akun(kon, id_akun: str):
    """Cek terbaru MILIK akun ini (kunci id_akun dari sesi server) beserta nama anak."""
    return kon.execute(
        """SELECT c.sesi_id, c.skor, w.nama FROM cek_gratis c
           JOIN siswa w ON w.id = c.siswa_id
           WHERE c.id_akun = ? ORDER BY c.id DESC LIMIT 1""",
        (id_akun,),
    ).fetchone()


def _kirim_mulai(penangan, principal, nama_anak: str, *, kode: int = 200, galat: str = "") -> None:
    token = buat_token(principal, penangan._ambil_token(), AKSI_MULAI)
    isi = cek_pages.halaman_mulai((principal.pengguna, principal.peran), token, nama_anak, galat=galat)
    penangan._kirim_privat(isi, kode)


def _kirim_info(penangan, principal, judul: str, teks: str, kode: int = 409) -> None:
    penangan._kirim_privat(
        cek_pages.halaman_info((principal.pengguna, principal.peran), judul, teks), kode)


def _belum_dibuka(penangan) -> None:
    import funnel_http
    import funnel_pages

    penangan._kirim(funnel_pages.halaman_belum_dibuka(funnel_http._dukungan()))


def _get_mulai(penangan, principal) -> None:
    with database.buka() as kon:
        status = cek_gratis.baca_hasil(kon, principal.id_akun)["status"]
        anak = None if status != "belum_mulai" else _anak_akun(kon, principal.pengguna)
    if status != "belum_mulai":
        _alihkan(penangan, RUTE_HASIL)
    elif anak is None:
        _kirim_info(penangan, principal, "Cek belum bisa dimulai", cek_pages.COPY_TANPA_ANAK, 200)
    else:
        _kirim_mulai(penangan, principal, anak["nama"])


def _get_hasil(penangan, principal) -> None:
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        cek_gratis.selesaikan_jika_siap(kon, principal.id_akun, _sekarang())
        hasil = cek_gratis.baca_hasil(kon, principal.id_akun)
        baris = _cek_akun(kon, principal.id_akun)
    if hasil["status"] == "belum_mulai" or baris is None:
        _alihkan(penangan, RUTE_MULAI)
        return
    token = buat_token(principal, penangan._ambil_token(), AKSI_TAUTAN)
    penangan._kirim_privat(
        cek_pages.halaman_hasil((principal.pengguna, principal.peran), hasil, baris["nama"], token))


def tangani_get(penangan, jalur: str) -> bool:
    """GET mulai/hasil: halaman milik akun sesi; sakelar mati = halaman belum dibuka."""
    if jalur not in RUTE_GET:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan, post=False)
        return True
    if not funnel_flag.funnel_aktif():
        _belum_dibuka(penangan)
        return True
    if jalur == RUTE_MULAI:
        _get_mulai(penangan, principal)
    else:
        _get_hasil(penangan, principal)
    return True


def _jalankan_mulai(principal, setuju: bool):
    """Satu transaksi: anak akun sesi, lalu `cek_gratis.mulai`. None bila akun tanpa anak."""
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        anak = _anak_akun(kon, principal.pengguna)
        if anak is None:
            return None
        cek_gratis.mulai(kon, principal.id_akun, anak["id"], principal.pengguna, setuju, _sekarang())
        return anak["nama"]


def _nama_anak(principal) -> str:
    with database.buka() as kon:
        anak = _anak_akun(kon, principal.pengguna)
    return "" if anak is None else anak["nama"]


def _galat_mulai(penangan, principal, galat: Exception) -> None:
    """Peta eksepsi domain ke pesan tetap; `str(galat)` tidak pernah dipantulkan."""
    if isinstance(galat, cek_gratis.CekPersetujuanDiperlukan):
        _kirim_mulai(penangan, principal, _nama_anak(principal), kode=400,
                     galat=cek_pages.COPY_WAJIB_CENTANG)
    else:
        _kirim_info(penangan, principal, "Cek belum bisa dimulai", cek_pages.COPY_BELUM_TERSEDIA)


def _tolak_laju(penangan) -> None:
    penangan._kirim(halaman_pesan(
        "Terlalu banyak permintaan",
        "<h1>Terlalu banyak permintaan</h1>"
        "<p>Hari ini terlalu banyak cek dimulai dari jaringan ini. Coba lagi besok.</p>"), 429)


def _gerbang_persetujuan(penangan, principal) -> bool:
    """True (dan 303 ke /persetujuan, tanpa efek) bila akun masih harus menyetujui kesepakatan."""
    import policy_http

    if not policy_http.perlu(principal):
        return False
    _alihkan(penangan, "/persetujuan")
    return True


def _post_mulai(penangan, principal) -> None:
    data = _baca_form(penangan)
    if (data is None or "token" not in data or not set(data) <= KUNCI_MULAI):
        penangan._tolak_isian()
        return
    if not token_sah(principal, penangan._ambil_token(), AKSI_MULAI, data["token"]):
        penangan._tolak_isian(403)
        return
    if _gerbang_persetujuan(penangan, principal):
        return
    setuju = data.get("setuju") == "1"
    if not setuju:
        _kirim_mulai(penangan, principal, _nama_anak(principal), kode=400,
                     galat=cek_pages.COPY_WAJIB_CENTANG)
        return
    if not _izinkan_permulaan(penangan):
        _tolak_laju(penangan)
        return
    try:
        nama = _jalankan_mulai(principal, setuju)
    except cek_gratis.CekTidakDitemukan:
        _tidak_ada(penangan, post=True)
        return
    except ValueError as galat:  # CekPersetujuanDiperlukan/CekBelumTersedia termasuk ValueError
        _galat_mulai(penangan, principal, galat)
        return
    if nama is None:
        _kirim_info(penangan, principal, "Cek belum bisa dimulai", cek_pages.COPY_TANPA_ANAK)
        return
    _alihkan(penangan, RUTE_HASIL)


def _buat_tautan(principal):
    """Tautan baru untuk sesi cek MILIK akun yang belum berskor; (token, nama) atau tujuan alihan."""
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        baris = _cek_akun(kon, principal.id_akun)
        if baris is None:
            return RUTE_MULAI
        if baris["skor"] is not None or baris["sesi_id"] is None:
            return RUTE_HASIL
        if not database.sesi_milik(kon, baris["sesi_id"], principal.pengguna):
            return RUTE_HASIL
        try:
            token = share_links.buat(kon, baris["sesi_id"])
        except ValueError:  # sesi sudah selesai/dibatalkan: hasil dinilai di halaman hasil
            return RUTE_HASIL
        kon.commit()
        return token, baris["nama"]


def _post_tautan(penangan, principal) -> None:
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_TAUTAN:
        penangan._tolak_isian()
        return
    if not token_sah(principal, penangan._ambil_token(), AKSI_TAUTAN, data["token"]):
        penangan._tolak_isian(403)
        return
    hasil = _buat_tautan(principal)
    if isinstance(hasil, str):
        _alihkan(penangan, hasil)
        return
    import share_http

    token, nama = hasil
    tautan = f"{share_http._situs_tautan(penangan)}/mulai/{token}"
    penangan._kirim_tautan(
        cek_pages.halaman_tautan((principal.pengguna, principal.peran), nama, tautan))


def tangani_post(penangan, jalur: str) -> bool:
    """POST mulai/tautan; sakelar mati = tidak ditangani (jatuh ke 404 rute tak dikenal)."""
    if jalur not in RUTE_POST:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan, post=True)
        return True
    if not funnel_flag.funnel_aktif():
        return False
    if jalur == RUTE_MULAI:
        _post_mulai(penangan, principal)
    else:
        _post_tautan(penangan, principal)
    return True

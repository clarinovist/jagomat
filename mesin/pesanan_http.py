"""Rute guru pesanan Paket Coba (funnel Fase 3c-3): pesan, status, QR, periksa, ulang, buat.

Dipanggil setelah palang sandi guru/admin di dispatcher (dekat `cek_http`). Aturan yang
ditegakkan di sini, bukan di halaman:

- `id_akun` HANYA dari principal sesi server; anak dan order diturunkan dari akun itu.
  Tidak ada id order, nominal, atau nama anak di URL atau form; form hanya `{token}`
  (field lain/ganda -> 400). Nominal selalu konstanta domain.
- Hanya peran guru. Admin/peran lain menerima 404 byte-identik dengan rute tak dikenal
  (`cek_http._tidak_ada`; GET dan POST berbeda body). Anonim/murid dihentikan palang sandi.
- Gerbang pembayaran = `pesanan.baca_gerbang` (FUNNEL_AKTIF + sakelar efektif + tahap
  checkout; kesiapan dari runtime server, bukan form). Tertutup: GET `/pesanan` dan
  GET `/paket-coba/pesan` = halaman status jujur tanpa pembacaan ledger, GET `/pesanan/qr`
  = 404; semua POST = tidak ditangani (jatuh ke 404 rute tak dikenal), tanpa efek.
  `FUNNEL_AKTIF` saja tidak membuka pembayaran. Terbuka: GET `/paket-coba/pesan` = 303
  ke `/pesanan` (tombol kembali setelah POST), bukan halaman yang membuat apa pun.
- Token form HMAC (akun, revisi auth, sesi, aksi, waktu habis) dengan domain
  `pesanan-form-v1:`; token cek/kontak atau aksi lain tidak berlaku.
- Pembatas laju per akun DAN per IP (in-memory, per proses) sebelum validasi form;
  periksa manual punya ember sendiri yang lebih ketat; lewat batas = 429 tanpa efek. GET `/pesanan` yang melewati batas tetap tampil dari ledger
  tanpa pemeriksaan provider.
- Efek uang hanya lewat ledger: "lunas" mustahil dari URL/redirect/POST klien; status
  provider diterapkan lewat domain (`pesanan_alur`). PRG: respons POST tidak memuat data.
- Tidak ada log dan tidak ada `str(galat)` di respons: pesan tetap saja.
- Jalur transfer rekening punya gerbang SENDIRI (`pesanan_transfer_gerbang`), tidak bergantung
  sakelar/tahap Midtrans. GET `/pesanan` dan GET `/paket-coba/pesan` melayani halaman bila SALAH
  SATU gerbang terbuka; transfer-only tidak pernah menghubungi provider dan `/pesanan/qr` tetap
  404. POST transfer (pesan transfer-only, tagihan, bukti) ada di `pesanan_transfer_http`;
  gerbang Midtrans/QRIS tidak berubah.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import hmac
import json
import sqlite3
import threading
import time

import admin_security
import admin_store
import admin_subscription
import auth
import cek_pages
import ip_klien
import pesanan
import pesanan_alur as alur
import pesanan_midtrans
import pesanan_pages as halaman
import pesanan_transfer
import pesanan_transfer_gerbang as gerbang_transfer
import pesanan_transfer_pages as halaman_transfer
import pesanan_transfer_tampil
from cek_http import _tidak_ada
from kontak_http import _alihkan, _baca_form, _principal_guru
from support_pages import halaman_pesan

RUTE_PESAN = cek_pages.RUTE_PESAN
RUTE_STATUS = halaman.RUTE_STATUS
RUTE_QR = halaman.RUTE_QR
RUTE_PERIKSA = halaman.RUTE_PERIKSA
RUTE_ULANG = halaman.RUTE_ULANG
RUTE_BUAT = halaman.RUTE_BUAT
RUTE_GET = frozenset({RUTE_STATUS, RUTE_QR, RUTE_PESAN})
RUTE_POST = frozenset({RUTE_PESAN, RUTE_PERIKSA, RUTE_ULANG, RUTE_BUAT})
AKSI_PESAN = "pesan"
AKSI_RUTE = {RUTE_PESAN: AKSI_PESAN, RUTE_PERIKSA: alur.AKSI_PERIKSA,
             RUTE_ULANG: alur.AKSI_ULANG, RUTE_BUAT: alur.AKSI_BUAT}
KUNCI_FORM = frozenset({"token"})
UMUR_TOKEN_DETIK = 900
BATAS_AKUN = 30
BATAS_IP = 60
BATAS_PERIKSA = 6
EMBER_PERIKSA = "periksa"
JENDELA_LAJU_DETIK = 60
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
_DOMAIN_TOKEN = b"pesanan-form-v1:"
_BATAS_TOKEN = 256

_laju: dict = {}
_kunci_laju = threading.Lock()


# --- gerbang & runtime -----------------------------------------------------

def _runtime(penangan):
    """Runtime produksi terpasang di server (bukan sandbox, transport bisa dipanggil) atau None."""
    runtime = admin_subscription.runtime_penangan(penangan)
    if runtime is None or getattr(runtime.config, "lingkungan", None) != "production":
        return None
    if not callable(runtime.transport):
        return None
    return runtime


def _runtime_bila_terbuka(penangan):
    """Runtime hanya bila ketiga syarat gerbang terpenuhi; selain itu None (fail-closed)."""
    runtime = _runtime(penangan)
    if runtime is None:
        return None
    if not pesanan.baca_gerbang(admin_store.BAWAAN, runtime.kesiapan):
        return None
    return runtime


def gerbang_terbuka(penangan) -> bool:
    """True hanya bila gerbang pembayaran (Midtrans/QRIS) terbuka."""
    return _runtime_bila_terbuka(penangan) is not None


def rekening_transfer(penangan):
    """Rekening publik bila gerbang transfer terbuka; selain itu None (fail-closed)."""
    if not gerbang_transfer.transfer_aktif():
        return None
    try:
        runtime = _runtime(penangan)
    except Exception:
        return None
    return gerbang_transfer.rekening_bila_terbuka(runtime)


def pesan_terbuka(penangan) -> bool:
    """True bila SALAH SATU gerbang terbuka (dipakai halaman hasil cek untuk CTA pesan)."""
    return gerbang_terbuka(penangan) or rekening_transfer(penangan) is not None


# --- token form ------------------------------------------------------------

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


# --- pembatas laju ---------------------------------------------------------

def _izinkan(penangan, principal, *, ketat: bool = False, ember: str = EMBER_PERIKSA) -> bool:
    """Hitung satu permintaan untuk akun DAN IP ini; False bila salah satu sudah di batas.

    `ketat` (periksa manual, unggah bukti) menambah ember per-akun bernama `ember` yang
    lebih kecil.
    """
    global _laju
    kini = time.monotonic()
    ip = ip_klien.ip_klien(penangan.headers, penangan.client_address)
    batas = {("akun", principal.id_akun): BATAS_AKUN, ("ip", ip): BATAS_IP}
    if ketat:
        batas[(ember, principal.id_akun)] = BATAS_PERIKSA
    with _kunci_laju:
        aktif = {k: tuple(t for t in waktu if kini - t < JENDELA_LAJU_DETIK)
                 for k, waktu in _laju.items()}
        aktif = {k: waktu for k, waktu in aktif.items() if waktu}
        if any(len(aktif.get(k, ())) >= maks for k, maks in batas.items()):
            _laju = aktif
            return False
        _laju = {**aktif, **{k: (*aktif.get(k, ()), kini) for k in batas}}
        return True


# --- respons ---------------------------------------------------------------

def _ident(principal):
    return (principal.pengguna, principal.peran)


def _info(penangan, principal, judul: str, teks: str, kode: int, tautan=None) -> None:
    penangan._kirim_privat(halaman.halaman_info(_ident(principal), judul, teks, tautan), kode)


def _tolak_laju(penangan) -> None:
    penangan._kirim(halaman_pesan(
        "Terlalu banyak permintaan",
        f"<h1>Terlalu banyak permintaan</h1><p>{halaman.COPY_TERLALU_BANYAK}</p>"), 429)


def _kirim_png(penangan, isi: bytes) -> None:
    penangan.send_response(200)
    for nama, nilai in admin_security.header_privat().items():
        penangan.send_header(nama, nilai)
    penangan.send_header("X-Content-Type-Options", "nosniff")
    penangan.send_header("Content-Type", "image/png")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.end_headers()
    penangan.wfile.write(isi)


def _masih_sah(penangan, principal) -> bool:
    """Sesi/akun tidak berubah selama panggilan provider (revisi auth, peran, pemilik)."""
    return _principal_guru(penangan) == principal


def _galat_domain(penangan, principal, galat: Exception, *, post: bool) -> None:
    """Peta eksepsi ke pesan tetap; `str(galat)` tidak pernah dipantulkan."""
    if isinstance(galat, alur.PesananTanpaAnak):
        _info(penangan, principal, "Belum ada anak", cek_pages.COPY_TANPA_ANAK, 409)
    elif isinstance(galat, alur.PesananCekBelumSelesai):
        _info(penangan, principal, "Cek belum selesai", halaman.COPY_CEK_BELUM_SELESAI, 409,
              halaman.tautan_hasil())
    elif isinstance(galat, pesanan.PesananButuhKontak):
        _info(penangan, principal, "Lengkapi kontak", halaman.COPY_BUTUH_KONTAK, 409,
              halaman.tautan_kontak())
    elif isinstance(galat, pesanan.PesananKuotaHabis):
        _info(penangan, principal, "Pendaftaran dihentikan sementara", halaman.COPY_KUOTA_HABIS, 409)
    elif isinstance(galat, pesanan.PesananBatasJendela):
        _info(penangan, principal, "Tidak bisa dibuat ulang", halaman.COPY_BATAS_ULANG, 409)
    elif isinstance(galat, pesanan.PesananTidakDitemukan):
        _tidak_ada(penangan, post=post)
    elif isinstance(galat, pesanan.PesananKonflik):
        _info(penangan, principal, "Pesanan perlu dicek", halaman.COPY_BENTROK, 409)
    else:
        _info(penangan, principal, "Belum bisa diproses", halaman.COPY_BELUM_SIAP, 503)


_GALAT_ALUR = (
    alur.PesananTanpaAnak, alur.PesananCekBelumSelesai, pesanan.PesananError,
    admin_store.StoreBelumSiap, sqlite3.Error, OSError, ValueError,
)


# --- GET -------------------------------------------------------------------

def _blok_transfer(penangan, principal, rekening, runtime) -> str:
    """Kartu transfer dari ledger (HTML); '' bila akun belum punya order.

    Tombol jendela bayar ulang transfer hanya bila gerbang Midtrans tertutup (`runtime` None).
    """
    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)
    if order_id is None:
        return ""
    with pesanan_transfer.buka(admin_store.BAWAAN) as kon:
        tampil = pesanan_transfer_tampil.baca(kon, order_id, principal.id_akun, alur.waktu_sekarang())
    tampil = replace(tampil, boleh_ulang=tampil.boleh_ulang and runtime is None)
    sesi = penangan._ambil_token()
    return halaman_transfer.blok_transfer(
        tampil, rekening, lambda aksi: buat_token(principal, sesi, aksi))


def _aksi_midtrans(tampil, runtime):
    """Aksi tombol Midtrans; tanpa runtime terbuka (transfer-only) tidak ada tombol Midtrans."""
    if runtime is None:
        return None
    return (alur.AKSI_ULANG if tampil.boleh_ulang else alur.AKSI_BUAT if tampil.boleh_buat
            else alur.AKSI_PERIKSA if tampil.boleh_periksa else None)


def _get_status(penangan, principal, runtime, rekening) -> None:
    anak = alur.ambil_anak(principal)
    if anak is None:
        _alihkan(penangan, cek_pages.RUTE_HASIL)
        return
    klien = None if runtime is None else pesanan_midtrans.dari_runtime(runtime)
    tampil = alur.tampilan(admin_store.BAWAAN, principal, anak, klien,
                           periksa_provider=_izinkan(penangan, principal))
    if not _masih_sah(penangan, principal):
        _tidak_ada(penangan, post=False)
        return
    if tampil is None:
        _alihkan(penangan, cek_pages.RUTE_HASIL)
        return
    aksi = _aksi_midtrans(tampil, runtime)
    token = None if aksi is None else buat_token(principal, penangan._ambil_token(), aksi)
    blok = "" if rekening is None else _blok_transfer(penangan, principal, rekening, runtime)
    penangan._kirim_privat(halaman.halaman_status(_ident(principal), {
        "status": tampil.status, "nama_anak": tampil.nama_anak, "qr": tampil.qr_url is not None,
        "aksi": aksi, "boleh_ulang": tampil.boleh_ulang,
        "belum_terperiksa": tampil.belum_terperiksa,
        "blok_transfer": blok, "qris": runtime is not None}, token))


def _get_qr(penangan, principal, runtime) -> None:
    if not _izinkan(penangan, principal):
        _tolak_laju(penangan)
        return
    anak = alur.ambil_anak(principal)
    klien = pesanan_midtrans.dari_runtime(runtime)
    tampil = None if anak is None else alur.tampilan(
        admin_store.BAWAAN, principal, anak, klien, periksa_provider=True)
    if tampil is None or tampil.qr_url is None:
        _tidak_ada(penangan, post=False)
        return
    gambar = klien.gambar(tampil.qr_url)
    if not _masih_sah(penangan, principal):
        _tidak_ada(penangan, post=False)
    elif type(gambar) is not bytes or not gambar.startswith(MAGIC_PNG):
        _info(penangan, principal, "Belum bisa diproses", halaman.COPY_BELUM_SIAP, 503)
    else:
        _kirim_png(penangan, gambar)


def tangani_get(penangan, jalur: str) -> bool:
    """GET status/QR milik akun sesi; gerbang tertutup = halaman jujur / 404."""
    if jalur not in RUTE_GET:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan, post=False)
        return True
    runtime = _runtime_bila_terbuka(penangan)
    rekening = rekening_transfer(penangan)
    if runtime is None and rekening is None:
        if jalur == RUTE_QR:
            _tidak_ada(penangan, post=False)
        else:
            penangan._kirim_privat(halaman.halaman_tertutup(_ident(principal)))
        return True
    if jalur == RUTE_PESAN:  # tombol kembali setelah POST: PRG ke status, tanpa efek
        _alihkan(penangan, RUTE_STATUS)
        return True
    if jalur == RUTE_QR and runtime is None:  # QRIS hanya bila gerbang Midtrans terbuka
        _tidak_ada(penangan, post=False)
        return True
    try:
        if jalur == RUTE_STATUS:
            _get_status(penangan, principal, runtime, rekening)
        else:
            _get_qr(penangan, principal, runtime)
    except _GALAT_ALUR as galat:
        _galat_domain(penangan, principal, galat, post=False)
    return True


# --- POST ------------------------------------------------------------------

def _jalankan(principal, klien, aksi: str, merchant: str) -> None:
    path = admin_store.BAWAAN
    if aksi == AKSI_PESAN:
        alur.pesan(path, principal, klien, merchant)
    elif aksi == alur.AKSI_BUAT:
        alur.buat(path, principal, klien)
    elif aksi == alur.AKSI_PERIKSA:
        alur.periksa(path, principal, klien)
    else:
        alur.ulang(path, principal, klien)


def _post_aksi(penangan, principal, runtime, aksi: str) -> None:
    klien = pesanan_midtrans.dari_runtime(runtime)
    _jalankan(principal, klien, aksi, runtime.config.merchant)
    if not _masih_sah(penangan, principal):
        _tidak_ada(penangan, post=True)
        return
    _alihkan(penangan, RUTE_STATUS)


def tangani_post(penangan, jalur: str) -> bool:
    """POST aksi pesanan; gerbang tertutup = tidak ditangani (404 rute tak dikenal), tanpa efek."""
    if jalur not in RUTE_POST:
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        _tidak_ada(penangan, post=True)
        return True
    runtime = _runtime_bila_terbuka(penangan)
    if runtime is None:
        return False
    if not _izinkan(penangan, principal, ketat=jalur == RUTE_PERIKSA):
        _tolak_laju(penangan)
        return True
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM:
        penangan._tolak_isian()
        return True
    aksi = AKSI_RUTE[jalur]
    if not token_sah(principal, penangan._ambil_token(), aksi, data["token"]):
        penangan._tolak_isian(403)
        return True
    try:
        _post_aksi(penangan, principal, runtime, aksi)
    except _GALAT_ALUR as galat:
        _galat_domain(penangan, principal, galat, post=True)
    return True

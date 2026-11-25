"""Rute murid langganan Latihan Harian (F5): orang tua memilih paket, membayar transfer, dan mengunggah bukti lewat akun anak.

Titik masuk GET `/murid/langganan`; POST `/murid/langganan/buat` (buat tagihan) dan `/murid/langganan/bukti`
(unggah bukti). Aturan yang ditegakkan di sini, bukan di halaman:

- Hidup HANYA bila sakelar `LATIHAN_HARIAN` aktif; mati = `False` (jatuh ke penangan murid biasa: jawaban sama
  dengan jalur `/murid` tak dikenal). Dijawab SEBELUM `_lolos_sandi` seperti permukaan murid lain.
- Anak = siswa yang tertaut ke akun murid sesi (`students.siswa_dari_akun`), BUKAN dari URL/form/kueri; kueri
  diabaikan. Anonim, guru, dan admin tidak ditangani (False: GET 303 /masuk, POST 401 seperti jalur murid lain).
- Form buat tagihan persis `{token, paket}`; paket hanya salah satu kode paket dan token terikat ke paket itu.
  Nominal selalu dari konstanta paket + kode unik server, tidak pernah dari form. Order bukti diturunkan dari
  anak sesi, tidak pernah dari form.
- Rekening belum diisi admin: GET = halaman jujur "belum dibuka", POST = 404 murid, tanpa efek.
- Unggah: laju ketat, body berbatas, multipart sempit, token, ukuran, magic bytes, lalu hambatan status; berkas
  ditulis atomik ke subfolder khusus (`harian_langganan_berkas`) dan dihapus bila catat gagal/duplikat.
- Nomor WhatsApp tidak pernah dirender; pesan galat tetap, tanpa `str(galat)`, id, atau jalur berkas.
"""
from __future__ import annotations

import hashlib
import sqlite3

import akses_harian
import bukti_berkas
import bukti_multipart
import database
import harian_langganan_berkas as berkas
import harian_langganan_dasar as h
import harian_langganan_pages as halaman
import harian_langganan_ringkas as ringkas
import harian_langganan_store as store
import paket_belajar_gate
import tirai_aksi
import pesanan_alur as alur
import pesanan_dasar as d
import pesanan_http
import pesanan_rekening
from bukti_berkas import mime_dari_isi
from kontak_http import _alihkan, _baca_form
from schema_transfer import BATAS_UKURAN_BUKTI

KUNCI_FORM_BUAT = frozenset({"token", "paket"})
OVERHEAD_MULTIPART = 64 * 1024
BATAS_BODY_UNGGAH = BATAS_UKURAN_BUKTI + OVERHEAD_MULTIPART
EMBER_BUKTI = "bukti_harian"
KODE_BENTROK = 409
KODE_BERKAS_KOSONG = 400
KODE_BERKAS_BESAR = 413
KODE_TIPE_TIDAK_DIDUKUNG = 415
KODE_TIDAK_SIAP = 503
_GET = frozenset({halaman.RUTE})
_POST = frozenset({halaman.RUTE_BUAT, halaman.RUTE_BUKTI})
_GALAT_LAYANAN = (d.PesananError, sqlite3.Error, OSError, bukti_berkas.BuktiBerkasError, ValueError)


def _pembeli(penangan):
    """(principal, siswa_id) murid yang siswanya tertaut, atau None (jatuh ke penangan murid biasa)."""
    import students
    principal = pesanan_http.principal_murid(penangan)
    if principal is None:
        return None
    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)
    return None if siswa_id is None else (principal, siswa_id)


def _rekening():
    """Rekening publik atau None (fail-closed bila penyimpanan rekening belum siap)."""
    try:
        return pesanan_rekening.baca_publik()
    except Exception:
        return None


def _info(penangan, judul: str, teks: str, kode: int) -> None:
    penangan._kirim_privat(halaman.halaman_info(judul, teks), kode)


def _token_untuk(penangan, principal):
    sesi = penangan._ambil_token()
    return lambda aksi: pesanan_http.buat_token(principal, sesi, aksi)


# --- GET ---------------------------------------------------------------------------------

def _get_halaman(penangan, principal, siswa_id: int) -> None:
    rekening = _rekening()
    kini = alur.waktu_sekarang()
    try:
        with database.buka() as kon:
            r = ringkas.ringkasan(kon, siswa_id, kini)
            tampil = store.tampilan_terbuka(kon, siswa_id, kini)
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", halaman.COPY_BELUM_SIAP, KODE_TIDAK_SIAP)
        return
    penangan._kirim_privat(halaman.halaman_langganan(r, tampil, rekening, _token_untuk(penangan, principal),
                                                     tautan_paket=paket_belajar_gate.aktif()))


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET `/murid/langganan`; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _GET or not akses_harian.aktif():
        return False
    pembeli = _pembeli(penangan)
    if pembeli is None:
        return False
    _get_halaman(penangan, *pembeli)
    return True


# --- POST: buat tagihan ----------------------------------------------------------------------

def _tidak_ada(penangan) -> None:
    from support_pages import halaman_pesan_murid
    penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), 404)


def _form_buat(penangan, principal):
    """Paket sah dari form `{token, paket}` bertoken, atau None (respons penolakan sudah dikirim)."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_BUAT or data["paket"] not in h.PAKET:
        penangan._tolak_isian()
        return None
    sesi = penangan._ambil_token()
    if not pesanan_http.token_sah(principal, sesi, halaman.AKSI_BUAT + data["paket"], data["token"]):
        penangan._tolak_isian(403)
        return None
    return data["paket"]


def _galat_buat(penangan, galat: Exception) -> None:
    if isinstance(galat, h.KodeUnikHabis):
        _info(penangan, "Tagihan belum bisa dibuat", halaman.COPY_KODE_HABIS, KODE_BENTROK)
    elif isinstance(galat, d.PesananTidakDitemukan):
        _tidak_ada(penangan)
    elif isinstance(galat, h.LanggananKonflik):
        _info(penangan, "Tagihan belum bisa dibuat", halaman.COPY_GAGAL_BUAT, KODE_BENTROK)
    else:
        _info(penangan, "Belum bisa diproses", halaman.COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def _post_buat(penangan, principal, siswa_id: int) -> None:
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    paket = _form_buat(penangan, principal)
    if paket is None:
        return
    try:
        with database.buka() as kon:
            store.buat_tagihan(kon, siswa_id, paket, alur.waktu_sekarang())
    except _GALAT_LAYANAN as galat:
        _galat_buat(penangan, galat)
        return
    _alihkan(penangan, halaman.RUTE)


# --- POST: unggah bukti ----------------------------------------------------------------------

def _periksa_isi(isi: bytes):
    """(kode, pesan, mime): kode/pesan terisi bila isi ditolak; mime dari MAGIC BYTES."""
    if not isi:
        return KODE_BERKAS_KOSONG, halaman.COPY_BERKAS["kosong"], None
    if len(isi) > BATAS_UKURAN_BUKTI:
        return KODE_BERKAS_BESAR, halaman.COPY_BERKAS["besar"], None
    mime = mime_dari_isi(isi)
    if mime is None:
        return KODE_TIPE_TIDAK_DIDUKUNG, halaman.COPY_BERKAS["tipe"], None
    return None, None, mime


def _baca_unggahan(penangan, principal):
    """BuktiForm sah dari body multipart, atau None (respons penolakan sudah dikirim)."""
    tubuh = penangan._baca_tubuh(BATAS_BODY_UNGGAH)
    if tubuh is None:
        penangan.close_connection = True
        penangan._tolak_isian(KODE_BERKAS_BESAR)
        return None
    form = bukti_multipart.parse(tubuh, penangan.headers.get("Content-Type", ""))
    if form is None:
        _info(penangan, "Berkas tidak terbaca", halaman.COPY_BERKAS["terbaca"], 400)
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_BUKTI, form.token):
        penangan._tolak_isian(403)
        return None
    return form


def _simpan_dan_catat(siswa_id: int, isi: bytes, mime: str) -> None:
    """Tulis berkas atomik lalu catat; gagal atau duplikat -> berkas dihapus."""
    nama = berkas.simpan(isi)
    try:
        with database.buka() as kon:
            hasil = store.catat_bukti(kon, siswa_id, mime, len(isi), hashlib.sha256(isi).hexdigest(), nama,
                                      alur.waktu_sekarang())
    except BaseException:
        berkas.hapus(nama)
        raise
    if not hasil["baru"]:
        berkas.hapus(nama)


def _hambatan(siswa_id: int):
    """Pesan ramah bila PASTI tidak ada tagihan yang menerima bukti sekarang; None bila boleh dicoba."""
    with database.buka() as kon:
        tampil = store.tampilan_terbuka(kon, siswa_id, alur.waktu_sekarang())
    if tampil is None or not tampil.boleh_unggah:
        return halaman.COPY_BATAS_BUKTI if tampil is not None and tampil.jumlah_bukti >= h.MAKS_BUKTI \
            else halaman.COPY_TIDAK_TERIMA
    return None


def _unggah_sah(penangan, siswa_id: int, form) -> None:
    kode, pesan, mime = _periksa_isi(form.isi)
    if kode is not None:
        _info(penangan, "Berkas belum bisa diterima", pesan, kode)
        return
    hambatan = _hambatan(siswa_id)
    if hambatan is not None:
        _info(penangan, "Bukti belum bisa diterima", hambatan, KODE_BENTROK)
        return
    _simpan_dan_catat(siswa_id, form.isi, mime)
    _alihkan(penangan, halaman.RUTE)


def _post_bukti(penangan, principal, siswa_id: int) -> None:
    if not pesanan_http._izinkan(penangan, principal, ketat=True, ember=EMBER_BUKTI):
        penangan.close_connection = True
        pesanan_http._tolak_laju(penangan)
        return
    form = _baca_unggahan(penangan, principal)
    if form is None:
        return
    try:
        _unggah_sah(penangan, siswa_id, form)
    except h.BatasBukti:
        _info(penangan, "Batas bukti tercapai", halaman.COPY_BATAS_BUKTI, KODE_BENTROK)
    except h.LanggananKonflik:
        _info(penangan, "Bukti belum bisa diterima", halaman.COPY_TIDAK_TERIMA, KODE_BENTROK)
    except _GALAT_LAYANAN:
        _info(penangan, "Belum bisa diproses", halaman.COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def tangani_post(penangan, jalur: str) -> bool:
    """POST buat tagihan / unggah bukti; False bila bukan milik modul, sakelar mati, atau bukan murid tertaut."""
    if jalur not in _POST or not akses_harian.aktif():
        return False
    pembeli = _pembeli(penangan)
    if pembeli is None:
        return False
    if _rekening() is None:  # gerbang pembayaran tertutup: 404 murid, tanpa efek
        _tidak_ada(penangan)
        return True
    if tirai_aksi.tertutup(penangan, *pembeli):  # PIN terpasang dan tirai tertutup: tanpa efek
        _info(penangan, "Untuk Ayah/Bunda", tirai_aksi.COPY_TERTUTUP, tirai_aksi.KODE_TERTUTUP)
        return True
    (_post_buat if jalur == halaman.RUTE_BUAT else _post_bukti)(penangan, *pembeli)
    return True

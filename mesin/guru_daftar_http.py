"""Pendaftaran guru mandiri: `GET/POST /daftar?peran=guru` (butir QA #5; gerbang env `DAFTAR_GURU`, bawaan mati).

Dipanggil `registration_http` hanya bila query persis `peran=guru` (selain itu `/daftar` berjalan seperti biasa, tidak ada eskalasi
peran dari form). Membuat akun guru TANPA profil anak lewat `admin_registration.daftar_publik` (guard registrasi, kunci DB
pemilik, dan receipt idempoten yang sudah ada). Akun baru tidak masuk lembaga mana pun: pemasukan oleh admin di /admin/lembaga.
Validasi server otoritatif sebelum menulis; form persis `{nama, sandi, setuju, token_form}`. Laju: lima percobaan pembuatan per IP dan 30 global per 15 menit
(`jatah_pendaftaran`, terpisah dari pembatas login). Sandi tidak pernah dikembalikan ke halaman, log, atau galat.
"""
from __future__ import annotations

import time
import urllib.parse

import auth
import database
import guru_daftar_gate as gerbang
import ip_klien
import jatah_pendaftaran
import laju_masuk
import sessions

PARAMETER = "peran"
NILAI = "guru"
KUNCI_FORM = frozenset({"nama", "sandi", "setuju", "token_form"})
PESAN_NAMA = "Nama pengguna wajib diisi."
PESAN_SANDI = "Kata sandi minimal 8 karakter."
PESAN_SETUJU = "Centang persetujuan Syarat Penggunaan dan Kebijakan Privasi dulu, ya."
PESAN_NAMA_TERPAKAI = "Nama sudah dipakai. Pakai nama lain, atau masuk bila memang akun Anda."
PESAN_NAMA_TIDAK_SAH = (
    "Nama pengguna hanya boleh huruf, angka, titik, garis bawah, atau tanda hubung, tanpa spasi, 3–40 karakter."
)
PESAN_DITUTUP = "Pendaftaran baru sedang ditutup. Akun yang sudah terdaftar tetap bisa masuk."
PESAN_TOKEN = "Form pendaftaran sudah tidak berlaku. Buka ulang halaman pendaftaran."
PESAN_BELUM_SELESAI = "Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama."
PESAN_BELUM_TERSEDIA = "Pendaftaran sementara belum tersedia. Akun yang sudah ada tetap bisa masuk."
PESAN_LAJU = "Terlalu banyak pendaftaran dari jaringan ini. Coba lagi 15 menit lagi."
PESAN_TIDAK_DAPAT_DIGUNAKAN = "Isian pendaftaran belum dapat digunakan."
PESAN_FORM_TIDAK_SAH = "Isian pendaftaran tidak sah."


def diminta(path: str) -> bool:
    """True hanya bila query persis `peran=guru` (satu nilai, tanpa parameter ganda)."""
    nilai = urllib.parse.parse_qs(urllib.parse.urlparse(path).query).get(PARAMETER, [])
    return nilai == [NILAI]


def _halaman(pesan: str = "", *, galat: bool = False, nama: str = "", token_form: str = "", dibuka: bool = True,
             belum_tersedia: bool = False) -> bytes:
    import landing
    return landing.halaman_daftar(
        pesan, galat=galat, nama=nama, token_form=token_form, mode_guru=True,
        pendaftaran_dibuka=dibuka, belum_tersedia=belum_tersedia)


def _kirim_belum_dibuka(penangan, status: int = 200) -> None:
    penangan._kirim(_halaman(gerbang.PESAN_BELUM_DIBUKA, galat=True, dibuka=False, belum_tersedia=True), status)


def tangani_get(penangan) -> None:
    """Form pendaftaran guru, atau penolakan jujur bila gerbang mati / pendaftaran ditutup / penyimpanan belum siap."""
    import admin_http
    import admin_registration
    import admin_store
    if not gerbang.aktif():
        _kirim_belum_dibuka(penangan)
        return
    try:
        status = admin_registration.status(admin_store.BAWAAN)
        token_form = admin_http.buat_token_pendaftaran() if status.dibuka else ""
    except admin_store.StoreBelumSiap:
        penangan._kirim(_halaman(PESAN_BELUM_TERSEDIA, galat=True, dibuka=False, belum_tersedia=True), 503)
        return
    penangan._kirim(_halaman(dibuka=status.dibuka, token_form=token_form))


def _baca_isian(penangan) -> dict:
    import admin_security
    data = admin_security.baca_form(penangan)
    if set(data) != KUNCI_FORM:
        raise ValueError(PESAN_FORM_TIDAK_SAH)
    return data


def _periksa(data: dict) -> str:
    """Pesan galat ramah pertama atau '' bila lolos (urutan = urutan tampil di form)."""
    if not data["nama"].strip():
        return PESAN_NAMA
    if len(data["sandi"]) < 8:
        return PESAN_SANDI
    if data["setuju"] != "1":
        return PESAN_SETUJU
    return ""


def _daftarkan(data: dict, tinjauan: dict):
    import admin_http
    import admin_registration
    import admin_store
    return admin_registration.daftar_publik(
        admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN,
        operasi_id=tinjauan["op"], alias=data["nama"].strip(), sandi=data["sandi"],
        token_form=admin_http.token_domain(data["token_form"]), sekarang=int(time.time()))


def _pesan_dari_galat(galat: Exception, nama: str, kunci_ip: str) -> tuple:
    """(pesan ramah, status HTTP); hanya pesan tetap, tidak pernah str(galat) mentah."""
    teks = str(galat)
    if "alias tidak tersedia" in teks:
        laju_masuk.catat_gagal(nama, kunci_ip)
        return PESAN_NAMA_TERPAKAI, 200
    if "alias tidak sah" in teks:
        return PESAN_NAMA_TIDAK_SAH, 200
    return PESAN_TIDAK_DAPAT_DIGUNAKAN, 400


def _selesai(penangan, akun_baru) -> None:
    """Sesi login lalu 303 ke /persetujuan (bila kesepakatan belum diterima) atau /guru."""
    import policy_http
    token = sessions.buat_dari_principal(akun_baru)
    if token is None:
        penangan._kirim(_halaman("Akun berubah saat pendaftaran. Silakan masuk lagi.", galat=True), 409)
        return
    tujuan = "/persetujuan" if policy_http.perlu(akun_baru) else "/guru"
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Set-Cookie", penangan._set_cookie(token))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def tangani_post(penangan) -> None:
    import admin_http
    import admin_registration
    import admin_store
    from admin_accounts import DomainAkunTidakSah
    from admin_contracts import KontrakTidakSah
    if not gerbang.aktif():
        _kirim_belum_dibuka(penangan, 403)
        return
    kunci_ip = ip_klien.ip_klien(penangan.headers, penangan.client_address)
    nama = ""
    data: dict = {}
    try:
        data = _baca_isian(penangan)
        nama = data["nama"].strip()
        token_baru = admin_http.buat_token_pendaftaran()
        if not admin_registration.status(admin_store.BAWAAN).dibuka:
            raise PermissionError("Pendaftaran ditutup.")
        pesan = _periksa(data)
        if pesan:
            penangan._kirim(_halaman(pesan, galat=True, nama=nama, token_form=token_baru))
            return
        tinjauan = admin_http.periksa_token_pendaftaran(data["token_form"])   # token palsu ditolak SEBELUM jatah terpakai
        if not jatah_pendaftaran.ambil(kunci_ip):              # satu percobaan pembuatan = satu jatah (per IP dan global)
            penangan._kirim(_halaman(PESAN_LAJU, galat=True, nama=nama, token_form=data["token_form"]), 429)
            return
        akun_baru = _daftarkan(data, tinjauan)
    except admin_registration.RegistrasiBelumSelesai:
        penangan._kirim(_halaman(PESAN_BELUM_SELESAI, galat=True, nama=nama, token_form=data.get("token_form", "")), 503)
        return
    except PermissionError as galat:
        ditutup = "ditutup" in str(galat)
        penangan._kirim(_halaman(
            PESAN_DITUTUP if ditutup else PESAN_TOKEN, galat=True, nama=nama, dibuka=not ditutup,
            token_form="" if ditutup else admin_http.buat_token_pendaftaran()), 403)
        return
    except (admin_store.StoreBelumSiap, OSError):          # setelah PermissionError: itu turunan OSError
        penangan._kirim(_halaman(PESAN_BELUM_SELESAI, galat=True, nama=nama, token_form=data.get("token_form", "")), 503)
        return
    except (ValueError, KontrakTidakSah, DomainAkunTidakSah) as galat:
        pesan, status = _pesan_dari_galat(galat, nama, kunci_ip)
        penangan._kirim(_halaman(
            pesan, galat=True, nama=nama,
            token_form=data.get("token_form") or admin_http.buat_token_pendaftaran()), status)
        return
    _selesai(penangan, akun_baru)

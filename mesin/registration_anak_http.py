"""Rute HTTP pendaftaran mode anak: `/daftar` membuat akun murid + anak milik koordinator lembaga antrean.

Dipanggil `registration_http` hanya bila `daftar_anak_gate.keadaan()` bukan `LAMA`. `BELUM_SIAP` (sakelar
hidup, antrean belum siap) menolak jujur tanpa menulis apa pun dan TIDAK jatuh ke alur akun guru. `ANAK`
memakai saga yang sama dengan mode guru (`admin_registration.daftar_dengan_profil` + `ModeAnak`) lewat
`subscription_registration.daftar_web`, lalu menerbitkan sesi murid dan mengalihkan ke `/murid`.

Validasi server otoritatif dan sebelum menulis apa pun. Hook khusus akun guru (kesepakatan kebijakan,
analitik KPI, sinkron langganan) sengaja tidak dipanggil untuk akun murid. Sandi dan PIN tidak pernah
dikembalikan ke halaman, log, atau galat; nomor WhatsApp hanya di-echo ke atribut value (di-escape).
"""
from __future__ import annotations

import time

import auth
import daftar_anak_gate
import database
import ip_klien
import laju_masuk
import sessions

TUJUAN_SETELAH_DAFTAR = "/murid"
KUNCI_FORM = frozenset({
    "nama", "sandi", "nama_lengkap", "kelas_sekolah", "wa", "setuju", "pin", "pin_ulang", "token_form", "jalur",
})
PESAN_FORM_TIDAK_SAH = "Isian pendaftaran tidak sah."
PESAN_NAMA_LOGIN = "Nama login anak wajib diisi."
PESAN_SANDI = "Sandi anak minimal 8 karakter."
PESAN_KELAS = "Pilih kelas anak dulu, ya."
PESAN_SETUJU = "Centang persetujuan orang tua/wali dulu, ya."
PESAN_PIN_BEDA = "PIN dan ulangannya belum sama."
PESAN_NAMA_TERPAKAI = "Nama login sudah dipakai. Pakai nama lain, ya."
PESAN_NAMA_LOGIN_TIDAK_SAH = (
    "Nama login hanya boleh huruf, angka, titik, garis bawah, atau tanda hubung, tanpa spasi, 3–40 karakter."
)
PESAN_NAMA_KEMBAR_HABIS = "Nama lengkap itu sudah terlalu banyak yang memakai. Tambahkan nama belakang atau inisial, ya."
PESAN_BELUM_SELESAI = "Pendaftaran belum selesai. Coba kirim lagi dengan isian yang sama."
PESAN_DITUTUP = "Pendaftaran baru sedang ditutup. Akun yang sudah terdaftar tetap bisa masuk."
PESAN_FORM_KEDALUWARSA = "Form pendaftaran sudah tidak berlaku. Buka ulang halaman pendaftaran."
PESAN_TIDAK_DAPAT_DIGUNAKAN = "Isian pendaftaran belum dapat digunakan."
PESAN_LAJU = "Terlalu banyak percobaan. Coba lagi 15 menit lagi."
# Pesan saga yang ramah pengguna dan aman ditampilkan apa adanya (selain itu: pesan umum 400).
_PESAN_SAGA_RAMAH = frozenset((
    "Nama lengkap anak wajib diisi, maksimal 80 karakter.",
    "Nama lengkap anak tidak sah.",
    "Isi nomor WhatsApp Indonesia yang valid, ya.",
    "Pilih kelas sekolah 1–6 atau Kelas belum diisi.",
    "Centang persetujuan Kebijakan Privasi dulu, ya.",
    "PIN harus 4 angka.",
    "Kata sandi minimal 8 karakter.",
))


def _halaman_belum_siap(penangan) -> None:
    import landing
    penangan._kirim(landing.halaman_daftar(
        daftar_anak_gate.PESAN_BELUM_DIBUKA, galat=True, pendaftaran_dibuka=False, belum_tersedia=True), 503)


def tangani_get(penangan, keadaan) -> None:
    """Form mode anak, atau penolakan jujur bila antrean belum siap / pendaftaran ditutup."""
    import admin_http
    import admin_registration
    import admin_store
    import landing
    import registration_contact
    if keadaan.mode == daftar_anak_gate.BELUM_SIAP:
        _halaman_belum_siap(penangan)
        return
    try:
        status = admin_registration.status(admin_store.BAWAAN)
        token_form = admin_http.buat_token_pendaftaran() if status.dibuka else ""
    except admin_store.StoreBelumSiap:
        penangan._kirim(landing.halaman_daftar(
            "Pendaftaran sementara belum tersedia. Akun yang sudah ada tetap bisa masuk.",
            galat=True, pendaftaran_dibuka=False, belum_tersedia=True), 503)
        return
    penangan._kirim(landing.halaman_daftar(
        pendaftaran_dibuka=status.dibuka, token_form=token_form, mode_anak=True,
        jalur_cek=registration_contact.jalur_funnel_di_query(penangan.path)))


class _Isian:
    """Isian form yang sudah divalidasi (tidak mengubah apa pun di luar objek ini)."""

    def __init__(self, data):
        import registration_contact
        self.data = data
        self.jalur_cek = data.get("jalur") == registration_contact.JALUR_FUNNEL
        self.nama = data["nama"].strip()
        self.sandi = data["sandi"]
        self.nama_lengkap = data.get("nama_lengkap", "").strip()
        self.kelas_mentah = data.get("kelas_sekolah", "")
        self.wa_echo = registration_contact.echo_wa(data)
        self.wa = registration_contact.normalisasi_dari_form(data)
        self.pin = data.get("pin", "")
        self.pin_ulang = data.get("pin_ulang", "")
        self.kelas = None


def _baca_isian(data) -> _Isian:
    """Whitelist per mode; field tak dikenal ditolak tanpa menulis apa pun."""
    import registration_contact
    if set(data) - KUNCI_FORM or not {"nama", "sandi"} <= set(data):
        raise ValueError(PESAN_FORM_TIDAK_SAH)
    if "jalur" in data and data["jalur"] != registration_contact.JALUR_FUNNEL:
        raise ValueError(PESAN_FORM_TIDAK_SAH)
    return _Isian(data)


def _periksa_isian(isian: _Isian, mode) -> str:
    """Pesan galat ramah pertama, atau "" bila lolos. Urutan = urutan tampil di form."""
    import admin_registration
    import learning_profile_ui
    import pin_orang_tua_store
    import registration_contact
    if not isian.nama:
        return PESAN_NAMA_LOGIN
    if len(isian.sandi) < 8:
        return PESAN_SANDI
    try:
        isian.nama_lengkap = admin_registration._nama_anak_sah(isian.nama_lengkap, mode)
    except ValueError as galat:
        return str(galat)
    isian.kelas = learning_profile_ui.baca_kelas_form(isian.kelas_mentah)
    if isian.kelas is None:
        return PESAN_KELAS
    if isian.wa is None:
        return registration_contact.PESAN_WA_WAJIB
    if isian.data.get("setuju") != "1":
        return PESAN_SETUJU
    if (isian.pin or isian.pin_ulang) and not pin_orang_tua_store.pin_sah(isian.pin):
        return pin_orang_tua_store.PESAN_PIN_TIDAK_SAH
    if isian.pin != isian.pin_ulang:
        return PESAN_PIN_BEDA
    return ""


def _kirim_form(penangan, isian, pesan, token_form, status=200, **kunci):
    import landing
    kelas = None
    if isian is not None and isian.kelas_mentah in ("1", "2", "3", "4", "5", "6"):
        kelas = int(isian.kelas_mentah)
    penangan._kirim(landing.halaman_daftar(
        pesan, galat=True, mode_anak=True, token_form=token_form,
        nama=isian.nama if isian else "", nama_lengkap=isian.nama_lengkap if isian else "",
        kelas_sekolah=kelas, wa=isian.wa_echo if isian else "",
        jalur_cek=bool(isian and isian.jalur_cek), **kunci), status)


def _pesan_dari_galat(galat, isian, kunci_ip) -> tuple:
    """(pesan ramah, status HTTP) dari ValueError saga; kegagalan nama login ikut dihitung laju."""
    import lembaga_store
    teks = str(galat)
    if isinstance(galat, lembaga_store.PenolakanNamaAnak):
        return PESAN_NAMA_KEMBAR_HABIS, 200
    if "alias tidak tersedia" in teks:
        if isian.nama:
            laju_masuk.catat_gagal(isian.nama, kunci_ip)
        return PESAN_NAMA_TERPAKAI, 200
    if "alias tidak sah" in teks:
        return PESAN_NAMA_LOGIN_TIDAK_SAH, 200
    if teks in _PESAN_SAGA_RAMAH:
        return teks, 200
    return PESAN_TIDAK_DAPAT_DIGUNAKAN, 400


def _daftarkan(isian, tinjauan, token_form_mentah, keadaan):
    """Saga mode anak lewat daftar_web (tanpa sinkron langganan); mengembalikan AkunBaru."""
    import admin_http
    import admin_registration
    import admin_store
    import subscription_registration
    return subscription_registration.daftar_web(
        admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN,
        operasi_id=tinjauan["op"], alias=isian.nama, sandi=isian.sandi,
        nama_anak=isian.nama_lengkap, kelas_sekolah=isian.kelas, profil_parameter=None,
        token_form=admin_http.token_domain(token_form_mentah), sekarang=int(time.time()),
        wa=isian.wa, mode_anak=admin_registration.ModeAnak(
            lembaga_id=keadaan.lembaga_id, setuju=True, pin=isian.pin or None),
    ).akun


def _selesai(penangan, akun_baru, isian, token_baru) -> None:
    """Terbitkan sesi murid lalu 303 ke /murid; sesi gagal (akun berubah) = 409 tanpa cookie."""
    token = sessions.buat_dari_principal(akun_baru)
    if token is None:
        _kirim_form(penangan, isian, "Akun berubah saat pendaftaran. Silakan masuk lagi.", token_baru, 409)
        return
    penangan.send_response(303)
    penangan.send_header("Location", TUJUAN_SETELAH_DAFTAR)
    penangan.send_header("Set-Cookie", penangan._set_cookie(token))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def tangani_post(penangan, keadaan) -> None:
    """Daftarkan anak secara idempoten (token form = operasi), lalu sesi murid dan redirect ke /murid."""
    import admin_http
    import admin_registration
    import admin_security
    import admin_store
    from admin_accounts import DomainAkunTidakSah
    from admin_contracts import KontrakTidakSah
    if keadaan.mode == daftar_anak_gate.BELUM_SIAP:
        _halaman_belum_siap(penangan)  # tanpa membaca form, tanpa menulis apa pun
        return
    kunci_ip = ip_klien.ip_klien(penangan.headers, penangan.client_address)
    isian = None
    data = {}
    try:
        data = admin_security.baca_form(penangan)
        isian = _baca_isian(data)
        token_baru = admin_http.buat_token_pendaftaran()
        if not admin_registration.status(admin_store.BAWAAN).dibuka:
            raise PermissionError("Pendaftaran ditutup.")
        mode = admin_registration.ModeAnak(lembaga_id=keadaan.lembaga_id, setuju=True)
        pesan = _periksa_isian(isian, mode)
        if pesan:
            _kirim_form(penangan, isian, pesan, token_baru)
            return
        if laju_masuk.sedang_diblokir(isian.nama, kunci_ip):
            _kirim_form(penangan, isian, PESAN_LAJU, data.get("token_form", token_baru), 429)
            return
        tinjauan = admin_http.periksa_token_pendaftaran(data.get("token_form", ""))
        akun_baru = _daftarkan(isian, tinjauan, data["token_form"], keadaan)
    except admin_registration.AntreanBelumSiap:
        _halaman_belum_siap(penangan)
    # PermissionError subclass OSError: harus lebih dulu dari klausa OSError.
    except PermissionError as galat:
        ditutup = "ditutup" in str(galat)
        _kirim_form(penangan, isian, PESAN_DITUTUP if ditutup else PESAN_FORM_KEDALUWARSA,
                    "" if ditutup else admin_http.buat_token_pendaftaran(), 403,
                    **({"pendaftaran_dibuka": False} if ditutup else {}))
    except (admin_registration.RegistrasiBelumSelesai, admin_store.StoreBelumSiap, OSError):
        _kirim_form(penangan, isian, PESAN_BELUM_SELESAI, data.get("token_form", ""), 503)
    except (ValueError, KontrakTidakSah, DomainAkunTidakSah) as galat:
        pesan, status = _pesan_dari_galat(galat, isian, kunci_ip) if isian else (PESAN_FORM_TIDAK_SAH, 400)
        _kirim_form(penangan, isian, pesan, data.get("token_form") or admin_http.buat_token_pendaftaran(), status)
    else:
        _selesai(penangan, akun_baru, isian, admin_http.buat_token_pendaftaran())

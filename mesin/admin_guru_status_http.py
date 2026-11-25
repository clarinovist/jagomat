"""Rute admin nonaktifkan / aktifkan kembali guru (/admin/guru/nonaktifkan, /admin/guru/aktifkan).

Non-admin = 404 identik rute tak dikenal sebelum data dibaca. GET menampilkan konfirmasi (query hanya `id`); POST memakai pola
uang admin (`aksi.terima_form`: CSRF, tinjauan terikat aksi dan sesi, sandi ulang). Target hanya dari tinjauan bertanda tangan
(field `id` di form harus sama). Perubahan = satu tulis atomik berkas akun (`guru_status`): `dinonaktifkan` + revisi_auth naik.
Koordinator lembaga ditolak. Sukses = PRG ke halaman guru. Tanpa kredensial di respons.
"""
from __future__ import annotations

import time
from typing import Optional

import admin_guru_akun as G
import admin_guru_akun_pages as P
import admin_guru_status_pages as ui
import admin_http as h
import admin_pesanan_aksi as aksi
import admin_security
import admin_store
import auth
import database
import guru_status

SECTION = "guru"
KUNCI_QUERY = frozenset({"id"})
FORM_ID = frozenset({ui.FIELD_ID})
RUTE_AKSI = {ui.RUTE_NONAKTIFKAN: (ui.AKSI_NONAKTIFKAN, True), ui.RUTE_AKTIFKAN: (ui.AKSI_AKTIFKAN, False)}


class _Tolak(ValueError):
    """Perintah ditolak dengan pesan Bahasa Indonesia tetap (400)."""


def _principal_pengelola(penangan):
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
    return principal


def _kirim(penangan, principal, isi: str) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SECTION, isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL), skrip=True)


def _guru(id_akun) -> Optional[G.GuruRingkas]:
    if not auth.id_akun_sah(id_akun):
        return None
    with database.buka() as kon:
        return G.satu_guru(kon, auth.muat_akun(), auth.muat_sandi(), id_akun)


def _periksa_keadaan(guru: Optional[G.GuruRingkas], nonaktifkan: bool) -> G.GuruRingkas:
    """Guru harus ada; nonaktifkan: guru aktif bukan koordinator; aktifkan: guru nonaktif-admin."""
    if guru is None:
        raise LookupError("guru tidak ada")
    if nonaktifkan and guru.nonaktif or not nonaktifkan and not guru.nonaktif:
        raise _Tolak(ui.COPY_TIDAK_BISA)
    if nonaktifkan and guru.peran_lembaga == G.PERAN_KOORDINATOR:
        raise _Tolak(ui.COPY_TAHAN_KOORDINATOR % guru.lembaga)
    return guru


def _alasan_tahan(guru: G.GuruRingkas, nonaktifkan: bool) -> Optional[str]:
    """Alasan tampilan tanpa form (koordinator); keadaan lain yang tidak cocok = _Tolak."""
    try:
        _periksa_keadaan(guru, nonaktifkan)
    except _Tolak as galat:
        if nonaktifkan and not guru.nonaktif and guru.peran_lembaga == G.PERAN_KOORDINATOR:
            return str(galat)
        raise
    return None


def _token(penangan, principal, guru: G.GuruRingkas, aksi_kode: str):
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    target = auth.cari_akun(guru.pengguna)
    if akun is None or target is None or target.get("id_akun") != guru.id_akun:
        raise LookupError("guru tidak ada")
    tinjauan = admin_security.buat_tinjauan(akun, sesi, aksi_kode, {
        "target_id": guru.id_akun, "target_revisi": auth.revisi_auth(target), "target_peran": "guru", "section": SECTION})
    return h._csrf(akun, sesi), tinjauan


def _get(penangan, principal, rute: str) -> None:
    aksi_kode, nonaktifkan = RUTE_AKSI[rute]
    try:
        query = h._query(penangan, diizinkan=KUNCI_QUERY)
        guru = _guru(query.get("id"))
        if guru is None:
            raise LookupError("guru tidak ada")
        tahan = _alasan_tahan(guru, nonaktifkan)
        token = None if tahan else _token(penangan, principal, guru, aksi_kode)
    except (ValueError, LookupError):
        return h._tidak_ada(penangan)
    except PermissionError:
        return h._galat(penangan, 403, ui.COPY_TANPA_SESI)
    _kirim(penangan, principal, ui.halaman_konfirmasi(guru, nonaktifkan=nonaktifkan, token=token, tahan=tahan))


def _terapkan(principal, guru: G.GuruRingkas, revisi: int, nonaktifkan: bool) -> None:
    try:
        if nonaktifkan:
            guru_status.nonaktifkan(guru.id_akun, revisi, principal.id_akun, int(time.time()))
        else:
            guru_status.aktifkan(guru.id_akun, revisi)
    except guru_status.StatusBerubah:
        raise admin_store.KonflikOperasi("akun berubah") from None
    except guru_status.StatusDitolak:
        raise _Tolak(ui.COPY_TIDAK_BISA) from None


def _simpan(penangan, principal, aksi_kode: str, nonaktifkan: bool) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, aksi_kode)
    aksi.wajib_field(data, FORM_ID)
    meta = tinjauan["data"]
    id_akun, revisi = meta.get("target_id"), meta.get("target_revisi")
    if data[ui.FIELD_ID] != id_akun or type(revisi) is not int:
        raise _Tolak(ui.COPY_TIDAK_BISA)
    guru = _periksa_keadaan(_guru(id_akun), nonaktifkan)
    _terapkan(principal, guru, revisi, nonaktifkan)
    h._redirect(penangan, P.alamat_guru(guru.id_akun))


def _jalankan(penangan, principal, rute: str) -> None:
    aksi_kode, nonaktifkan = RUTE_AKSI[rute]
    try:
        _simpan(penangan, principal, aksi_kode, nonaktifkan)
    except _Tolak as galat:
        h._galat(penangan, 400, str(galat))


def tangani_get(penangan, jalur) -> bool:
    if jalur not in RUTE_AKSI:
        return False
    principal = _principal_pengelola(penangan)
    if principal is not None:
        _get(penangan, principal, jalur)
    return True


def tangani_post(penangan, jalur) -> bool:
    if jalur not in RUTE_AKSI:
        return False
    principal = _principal_pengelola(penangan)
    if principal is not None:
        aksi.jalankan_aman(penangan, lambda: _jalankan(penangan, principal, jalur),
                           copy_konflik=ui.COPY_BERUBAH, copy_isian=ui.COPY_TIDAK_BISA, copy_layanan=ui.COPY_TIDAK_BISA)
    return True

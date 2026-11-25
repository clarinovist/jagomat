"""Rute admin `/admin?section=guru`: daftar akun guru, kelola satu guru, dan halaman tinjauan aksi akun untuk guru.

Hanya GET. Aksi tetap lewat `/admin/tinjau` dan `POST /admin/akun` milik `admin_http` (token tinjauan, CSRF, sandi ulang admin, jurnal);
modul ini hanya merender halaman tinjauan untuk target guru yang tampil di daftar (bukan orang tua alur lama, bukan akun lain).
"""
from __future__ import annotations

import time

import admin_guru_akun as G
import admin_guru_akun_pages as ui
import admin_http as h
import admin_pages
import admin_queries
import admin_security
import auth
import database
from admin_contracts import AKSI_HAPUS_LOGIN

SECTION = "guru"
AKSI_TINJAU = frozenset(("account_password_reset", "account_session_revoke", AKSI_HAPUS_LOGIN))


def _kirim(penangan, principal, isi: str) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SECTION, isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL), skrip=True)


def get(penangan, principal, query) -> None:
    """Daftar (dengan filter `status`) atau kelola satu guru (`id`)."""
    akun, mentah = auth.muat_akun(), auth.muat_sandi()
    with database.buka() as kon:
        if query.get("id"):
            guru = G.satu_guru(kon, akun, mentah, query["id"])
            if guru is None:
                return h._tidak_ada(penangan)
            return _kirim(penangan, principal, ui.render_detail(
                guru, tindakan=None if principal.metode == "cookie" else "", sekarang=time.time()))
        saring = query.get("status", "semua")
        daftar = G.daftar_guru(kon, akun, mentah, saring)
        hitungan = G.hitung_per_saring(kon, akun, mentah)
    _kirim(penangan, principal, ui.render_daftar(
        daftar, saring, hitungan, sekarang=time.time(), tampilkan_aksi=principal.metode == "cookie"))


def tinjau(penangan, principal, aksi: str, id_akun: str, akun_admin, token_sesi, csrf) -> None:
    """Halaman tinjauan aksi akun untuk guru (`dari=guru`); token baru hanya untuk guru yang tampil di daftar."""
    if aksi not in AKSI_TINJAU:
        return h._tidak_ada(penangan)
    target = h._target_akun(id_akun)
    with database.buka() as kon:
        guru = G.satu_guru(kon, auth.muat_akun(), auth.muat_sandi(), id_akun)
    if guru is None or target is None or target.get("peran") != "guru":
        return h._tidak_ada(penangan)
    if aksi == AKSI_HAPUS_LOGIN and guru.lembaga:
        tindakan = '<section class="admin-kartu admin-catatan"><p>%s</p></section>' % ui.e(ui.COPY_TAHAN_HAPUS % (
            "pemilik" if guru.peran_lembaga == G.PERAN_KOORDINATOR else "anggota", guru.lembaga))
    else:
        token = admin_security.buat_tinjauan(akun_admin, token_sesi, aksi, {
            "target_id": target["id_akun"], "target_revisi": auth.revisi_auth(target),
            "target_peran": "guru", "section": SECTION})
        tindakan = admin_pages.form_tindakan_akun(
            target["pengguna"], "guru", csrf, {aksi: token}, kembali=ui.alamat_guru(guru.id_akun),
            jumlah_siswa=guru.jumlah_siswa, jumlah_sesi=guru.jumlah_sesi)
    _kirim(penangan, principal, ui.render_detail(guru, tindakan=tindakan, sekarang=time.time()))

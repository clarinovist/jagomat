"""Rute admin langganan Latihan Harian: antrean `/admin/langganan`, detail `/verifikasi`, pratinjau `/bukti`, aksi
`/setujui` dan `/tolak`.

Dijawab `admin_http` sebelum palang guru, jadi anonim, murid, dan guru menerima 404 yang sama dengan rute admin tak
dikenal SEBELUM DB atau berkas disentuh. Semua rute hanya hidup bila sakelar `LATIHAN_HARIAN` aktif (mati = tidak
ditangani = 404 rute tak dikenal); konsekuensinya bukti yang sedang menunggu baru dapat diputuskan setelah sakelar
dinyalakan lagi. Aturan aksi (pola uang yang sama dengan verifikasi transfer):

- CSRF + tinjauan bertanda tangan terikat aksi dan sesi + sandi admin ulang (`h._token_final`), wajib sesi berkuki.
  `order_id` dan bukti terakhir yang dilihat admin HANYA dari tinjauan (`target_id`, `target_revisi`); `admin_id`
  dari principal sesi. Field lain (admin_id, order_id, nominal, paket) = 400. Keputusan hanya sah atas bukti terbaru
  yang dilihat admin (bukti baru = 409). Setujui tanpa field; Tolak hanya `alasan`.
- Setujui menulis verifikasi dan akses dalam satu transaksi (`harian_langganan_putusan`).
- Pratinjau memakai pembaca berkas dan header yang sama dengan bukti Paket Coba (tipe dari ledger dan magic bytes,
  `nosniff`, CSP ketat, nama unduhan generik); berkas dari subfolder khusus langganan.
- Tidak ada `str(galat)` di respons; PRG 303 dengan kode hasil dari enum tetap.
"""
from __future__ import annotations

import sqlite3

import admin_http as h
import admin_pesanan_aksi as aksi
import admin_pesanan_pages as daftar_ui
import admin_security
import admin_store
import admin_verifikasi_http as bukti_umum
import akses_harian
import bukti_berkas
import database
import harian_langganan_admin_pages as ui
import harian_langganan_berkas as berkas
import harian_langganan_dasar as dasar
import harian_langganan_putusan as putusan
import pesanan
import pesanan_alur as alur
from schema_transfer import BATAS_UKURAN_BUKTI, MIME_BUKTI

RUTE_GET = frozenset({ui.RUTE, ui.RUTE_VERIFIKASI, ui.RUTE_BUKTI})
_AKSI_POST = {ui.RUTE_SETUJUI: ui.AKSI_SETUJUI, ui.RUTE_TOLAK: ui.AKSI_TOLAK}
_GALAT_BACA = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, ui.SECTION, isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL,
    ), kode, skrip=True)


# --- antrean dan detail -----------------------------------------------------------------------

def _get_antrean(penangan, principal) -> None:
    try:
        query = h._query(penangan, diizinkan={"hasil"})
        hasil = query.get("hasil")
        if hasil is not None and hasil not in (ui.HASIL_SETUJU, ui.HASIL_TOLAK):
            raise ValueError("hasil tidak sah")
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        with database.buka() as kon:
            antrean = putusan.antrean(kon, alur.waktu_sekarang())
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, ui.halaman_antrean(antrean, hasil=hasil))


def _order_query(penangan) -> str:
    query = h._query(penangan, diizinkan={"order"})
    return dasar.periksa_order_id(query.get("order"))


def _forms(penangan, principal, detail):
    """{'setujui': (csrf, tinjauan), 'tolak': ...} hanya untuk order menunggu dan sesi berkuki."""
    if principal.metode != "cookie" or detail["status"] != dasar.STATUS_MENUNGGU:
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    isi = {"target_id": detail["order_id"], "target_revisi": detail["bukti_terakhir_id"]}
    return {nama: (csrf, admin_security.buat_tinjauan(akun, sesi, kode, isi))
            for nama, kode in (("setujui", ui.AKSI_SETUJUI), ("tolak", ui.AKSI_TOLAK))}


def _get_detail(penangan, principal) -> None:
    try:
        order_id = _order_query(penangan)
    except (ValueError, pesanan.PesananDataTidakSah):
        return h._tidak_ada(penangan)
    try:
        with database.buka() as kon:
            detail = putusan.detail(kon, order_id, alur.waktu_sekarang())
        forms = None if detail is None else _forms(penangan, principal, detail)
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    if detail is None:
        return h._tidak_ada(penangan)
    _kirim(penangan, principal, ui.halaman_detail(detail, forms, baca_saja=principal.metode != "cookie"))


# --- pratinjau bukti --------------------------------------------------------------------------

def _muat_bukti(bukti_id: int):
    """(mime, isi) atau None bila bukti tak ada atau berkas hilang; berkas rusak = BuktiBerkasError."""
    with database.buka() as kon:
        meta = putusan.bukti_meta(kon, bukti_id)
    if meta is None:
        return None
    try:
        with berkas.buka(meta["berkas"]) as f:
            isi = f.read(BATAS_UKURAN_BUKTI + 1)
    except FileNotFoundError:
        return None
    except OSError:
        raise bukti_berkas.BuktiBerkasError("berkas bukti tidak bisa dibuka") from None
    if (meta["mime"] not in MIME_BUKTI or len(isi) > BATAS_UKURAN_BUKTI
            or bukti_berkas.mime_dari_isi(isi) != meta["mime"]):
        raise bukti_berkas.BuktiBerkasError("berkas bukti tidak cocok dengan catatan")
    return meta["mime"], isi


def _get_bukti(penangan, principal) -> None:
    try:
        bukti_id, unduh = bukti_umum._query_bukti(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        muat = _muat_bukti(bukti_id)
    except bukti_berkas.BuktiBerkasError:
        return _kirim(penangan, principal, bukti_umum.ui.halaman_bukti_rusak(), 503)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    if muat is None:
        return _kirim(penangan, principal, bukti_umum.ui.halaman_bukti_tidak_tersedia(), 404)
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    bukti_umum._kirim_bukti(penangan, muat[0], muat[1], unduh)


def tangani_get(penangan, jalur) -> bool:
    if jalur not in RUTE_GET or not akses_harian.aktif():
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    {ui.RUTE: _get_antrean, ui.RUTE_VERIFIKASI: _get_detail, ui.RUTE_BUKTI: _get_bukti}[jalur](penangan, principal)
    return True


# --- keputusan --------------------------------------------------------------------------------

def _bukti_dilihat(tinjauan) -> int:
    nilai = tinjauan["data"].get("target_revisi")
    if type(nilai) is not int or nilai < 1:
        raise ValueError("bukti tidak sah")
    return nilai


def _order_dari_tinjauan(tinjauan) -> str:
    """`order_id` hanya dari tinjauan bertanda tangan (`target_id`), tidak pernah dari field form."""
    return dasar.periksa_order_id(tinjauan["data"].get("target_id"))


def _putuskan(penangan, principal, jalur: str) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, _AKSI_POST[jalur])
    setuju = jalur == ui.RUTE_SETUJUI
    aksi.wajib_field(data, frozenset() if setuju else frozenset({"alasan"}))
    order_id, dilihat = _order_dari_tinjauan(tinjauan), _bukti_dilihat(tinjauan)
    with database.buka() as kon:
        if setuju:
            putusan.setujui(kon, order_id, principal.id_akun, alur.waktu_sekarang(), bukti_dilihat=dilihat)
        else:
            putusan.tolak(kon, order_id, principal.id_akun, data["alasan"], alur.waktu_sekarang(),
                          bukti_dilihat=dilihat)
    h._redirect(penangan, "%s?hasil=%s" % (ui.RUTE, ui.HASIL_SETUJU if setuju else ui.HASIL_TOLAK))


def tangani_post(penangan, jalur) -> bool:
    if jalur not in _AKSI_POST or not akses_harian.aktif():
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(
        penangan, lambda: _putuskan(penangan, principal, jalur), copy_konflik=ui.COPY_GALAT_KONFLIK,
        copy_isian=ui.COPY_GALAT_ALASAN if jalur == ui.RUTE_TOLAK else daftar_ui.COPY_GALAT_ISIAN)
    return True

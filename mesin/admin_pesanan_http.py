"""Rute admin `/admin/pesanan` (daftar) dan aksi periksa/refund (Fase 3c-4).

Satu permukaan kecil di bawah `/admin/`: sudah dijawab `admin_http` sebelum palang guru, jadi
anonim, murid, dan guru menerima 404 yang sama dengan rute admin tak dikenal (`h._tidak_ada`)
SEBELUM ledger dibaca. Aturan yang ditegakkan di sini:

- Hanya peran admin (`h._principal_admin`). Aksi memakai pola uang yang sama dengan panel
  langganan: `h._token_final` (CSRF + tinjauan bertanda tangan terikat aksi dan sesi + sandi ulang)
  dan wajib sesi berkuki.
- `order_id` hanya dari tinjauan bertanda tangan (`target_id`), bukan field form. Form periksa harus
  kosong dan form refund hanya `catatan_kode`; field lain (termasuk `akun_id`) = 400.
- Periksa: `akun_id` dibaca dari ledger di server, bukan dari form; hanya bila gerbang pembayaran terbuka
  (`pesanan_http._runtime_bila_terbuka`); tertutup = pesan jujur tanpa panggilan provider dan tanpa efek.
- Refund: hanya CATATAN (`pesanan.catat_refund`), tanpa panggilan API refund dan tidak dibatasi gerbang.
  `catatan_kode` divalidasi enum di sini; galat domain tak terduga = 503 (bukan 400). `operasi_id`
  deterministik per order (idempoten, satu catatan per order); `dicatat_oleh` = id akun admin sesi.
- Jejak: catatan refund itu sendiri (pelaku, kode, waktu; tabel append-only). Aksi periksa tidak
  menulis jurnal admin (kontrak jurnal `operasi_admin` tidak diubah); efeknya tercatat sebagai pengamatan ledger.
- Tidak ada `str(galat)` di respons; PRG: pengalihan 303 ke daftar dengan kode hasil dari enum tetap.
- Jalur transfer rekening: daftar menerima `?status=menunggu` (tab verifikasi) dan menampilkan ringkasan transfer
  (`pesanan_admin_transfer`); rute detail/pratinjau/keputusan dan rekening didelegasikan ke
  `admin_verifikasi_http` dan `admin_rekening_http` (tidak bergantung pada gerbang transfer maupun Midtrans).
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

import admin_http as h
import admin_pesanan_pages as ui
import admin_rekening_http
import admin_security
import admin_store
import admin_verifikasi_http
import pesanan
import pesanan_admin_transfer
import pesanan_alur as alur
import pesanan_http
import pesanan_midtrans
import pesanan_status as st
from schema_pesanan import CATATAN_REFUND

RUTE = ui.RUTE
RUTE_PERIKSA = ui.RUTE_PERIKSA
RUTE_REFUND = ui.RUTE_REFUND
AKSI_PERIKSA = "periksa_pesanan"
AKSI_REFUND = "catat_refund_pesanan"
AKSI_RUTE = {RUTE_PERIKSA: AKSI_PERIKSA, RUTE_REFUND: AKSI_REFUND}
_AKSI_UI = {ui.AKSI_PERIKSA: AKSI_PERIKSA, ui.AKSI_REFUND: AKSI_REFUND}
MAKS_HALAMAN = 100000
_POLA_ORDER = re.compile(r"ord_[0-9a-f]{32}")
_PANJANG_OPERASI = 32
_GALAT_BACA = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)


def _admin(penangan):
    return h._principal_admin(penangan)


def _runtime_periksa(penangan):
    """Runtime pembayaran hanya bila ketiga syarat gerbang terpenuhi; selain itu None."""
    return pesanan_http._runtime_bila_terbuka(penangan)


# --- GET -------------------------------------------------------------------

def _halaman_query(penangan):
    query = h._query(penangan, diizinkan={"halaman", "hasil", "status"})
    halaman = h._angka(query.get("halaman"), 1)
    hasil, saring = query.get("hasil"), query.get("status")
    if halaman > MAKS_HALAMAN or (hasil is not None and hasil not in ui.KODE_HASIL):
        raise ValueError("query tidak sah")
    if saring is not None and saring != ui.SARING_MENUNGGU:
        raise ValueError("query tidak sah")
    return halaman, hasil, saring


def _token_baris(penangan, principal, daftar, gerbang_terbuka, halaman):
    """{order_id: {aksi: (csrf, tinjauan)}} hanya untuk aksi yang tampil; kosong bila bukan sesi berkuki."""
    if principal.metode != "cookie":
        return {}
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    return {
        item["order_id"]: {
            aksi: (csrf, admin_security.buat_tinjauan(
                akun, sesi, _AKSI_UI[aksi], {"target_id": item["order_id"], "halaman": halaman}))
            for aksi in ui.aksi_tersedia(item, gerbang_terbuka)}
        for item in daftar["items"]}


def _kirim(penangan, principal, isi, kode=200):
    if _admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "pesanan", isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL,
    ), kode, skrip=True)


def _baca_daftar(halaman, saring):
    """(daftar, ringkasan transfer per order) dalam satu koneksi baca."""
    with pesanan.buka(h._path_admin()) as kon:
        daftar = pesanan.daftar_admin(
            kon, halaman=halaman, per_halaman=ui.PER_HALAMAN, sekarang=alur._sekarang(),
            hanya_menunggu=saring == ui.SARING_MENUNGGU)
        return daftar, pesanan_admin_transfer.ringkasan(kon, [i["order_id"] for i in daftar["items"]])


def tangani_get(penangan, jalur) -> bool:
    if admin_verifikasi_http.tangani_get(penangan, jalur) or admin_rekening_http.tangani_get(penangan, jalur):
        return True
    if jalur != RUTE:
        return False
    principal = _admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        halaman, hasil, saring = _halaman_query(penangan)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    try:
        daftar, transfer = _baca_daftar(halaman, saring)
        gerbang = _runtime_periksa(penangan) is not None
        forms = _token_baris(penangan, principal, daftar, gerbang, halaman)
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_GALAT_FORM)
        return True
    except _GALAT_BACA:
        _kirim(penangan, principal, ui.halaman_tidak_siap(), 503)
        return True
    _kirim(penangan, principal, ui.halaman(
        daftar, halaman=halaman, gerbang_terbuka=gerbang, forms=forms, hasil=hasil,
        baca_saja=principal.metode != "cookie", transfer=transfer, saring=saring))
    return True


# --- POST ------------------------------------------------------------------

def operasi_refund(order_id: str) -> str:
    """Id operasi deterministik per order: replay identik idempoten, isi beda = konflik."""
    return "rfd_" + hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:_PANJANG_OPERASI]


def _order_dari_tinjauan(tinjauan) -> str:
    order_id = tinjauan["data"].get("target_id")
    if type(order_id) is not str or _POLA_ORDER.fullmatch(order_id) is None:
        raise ValueError("order tidak sah")
    return order_id


def _halaman_dari_tinjauan(tinjauan) -> int:
    halaman = tinjauan["data"].get("halaman", 1)
    return halaman if type(halaman) is int and 1 <= halaman <= MAKS_HALAMAN else 1


def _akun_ledger(order_id: str) -> str:
    """Pemilik order menurut ledger server; bukan dari form."""
    with pesanan.buka(h._path_admin()) as kon:
        baris = st.baris_order(kon, order_id)
    if baris is None:
        raise pesanan.PesananTidakDitemukan()
    return baris["akun_id"]


def _periksa(penangan, principal, order_id: str, data: dict) -> str:
    if data:
        raise ValueError("isian asing")
    runtime = _runtime_periksa(penangan)
    if runtime is None:
        return "gerbang_tertutup"
    akun_id = _akun_ledger(order_id)
    hasil = alur.periksa_status(h._path_admin(), order_id, akun_id, pesanan_midtrans.dari_runtime(runtime))
    if _admin(penangan) != principal:
        raise LookupError("sesi berubah")
    if not hasil.dicoba:
        return "periksa_dilewati"
    return "periksa_ok" if hasil.ok else "periksa_gagal"


def _refund(principal, order_id: str, data: dict) -> str:
    if set(data) != {"catatan_kode"}:
        raise ValueError("isian tidak sah")
    catatan = data["catatan_kode"]
    if catatan not in CATATAN_REFUND:
        raise ValueError("catatan_kode tidak sah")
    with pesanan.buka(h._path_admin(), tulis_data=True) as kon:
        hasil = pesanan.catat_refund(
            kon, order_id, operasi_refund(order_id), principal.id_akun, catatan, alur._sekarang())
    return "refund_dicatat" if hasil["baru"] else "refund_sudah_ada"


def _jalankan(penangan, principal, jalur: str, data: dict) -> None:
    aksi = AKSI_RUTE[jalur]
    _akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)
    order_id = _order_dari_tinjauan(tinjauan)
    halaman = _halaman_dari_tinjauan(tinjauan)
    if jalur == RUTE_PERIKSA:
        kode = _periksa(penangan, principal, order_id, data)
    else:
        kode = _refund(principal, order_id, data)
    h._redirect(penangan, "%s?halaman=%d&hasil=%s" % (RUTE, halaman, kode))


def tangani_post(penangan, jalur) -> bool:
    if admin_verifikasi_http.tangani_post(penangan, jalur) or admin_rekening_http.tangani_post(penangan, jalur):
        return True
    if jalur not in AKSI_RUTE:
        return False
    principal = _admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        data = admin_security.baca_form(penangan, maksimum_field=8)
        _jalankan(penangan, principal, jalur, data)
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_GALAT_FORM)
    except (LookupError, pesanan.PesananTidakDitemukan):
        h._tidak_ada(penangan)
    except pesanan.PesananKonflik:
        h._galat(penangan, 409, ui.COPY_GALAT_KONFLIK)
    except (pesanan.PesananError, admin_store.StoreBelumSiap, sqlite3.Error, OSError):
        h._galat(penangan, 503, ui.COPY_GALAT_LAYANAN)
    except (ValueError, KeyError, TypeError):
        h._galat(penangan, 400, ui.COPY_GALAT_ISIAN)
    return True

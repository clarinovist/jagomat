"""Rute admin `/admin/pesanan` (daftar), `/admin/pesanan/order` (detail order), dan aksi periksa/refund (Fase C).

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
- Voucher dan laporan (V3, domain `purna`): `/admin/pesanan/voucher` (aksi `catat_voucher_pakai`, form hanya `catatan_kode`
  dari `schema_purna.CATATAN_PAKAI`, `operasi_id` deterministik per order) dan `/admin/pesanan/terbit` (aksi
  `catat_laporan_terbit`, form harus kosong). Pola, token, galat, dan PRG sama dengan refund; skema purna belum
  terpasang = PesananKonflik dari domain = 409. Refund sesudah voucher dipakai ditolak domain, bukan hanya disembunyikan.
- Jejak: catatan refund itu sendiri (pelaku, kode, waktu; tabel append-only). Aksi periksa tidak
  menulis jurnal admin (kontrak jurnal `operasi_admin` tidak diubah); efeknya tercatat sebagai pengamatan ledger.
- Tidak ada `str(galat)` di respons; PRG: pengalihan 303 ke Detail order (`/admin/pesanan/order?id=&hasil=`)
  dengan kode hasil dari enum tetap. `order_id` di pengalihan berasal dari tinjauan bertanda tangan.
- Daftar tanpa form tindakan: form periksa dan refund hanya ada di Detail order (token per aksi dibuat di sana,
  hanya untuk sesi berkuki). Detail order: admin saja, id divalidasi persis, order tak ada = 404 identik rute tak dikenal.
- Daftar menerima `?status=` dari allowlist `ui.KODE_SARING` (menunggu, belum_bayar, dibayar, ditolak) dan
  menampilkan ringkasan transfer (`pesanan_admin_transfer`); rute detail/pratinjau/keputusan dan rekening didelegasikan ke
  `admin_verifikasi_http` dan `admin_rekening_http` (tidak bergantung pada gerbang transfer maupun Midtrans).
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3

import admin_http as h
import admin_pesanan_detail_pages as dui
import admin_pesanan_pages as ui
import admin_rekening_http
import admin_security
import admin_store
import admin_verifikasi_http
import cek_ringkasan_admin
import database
import pesanan
import pesanan_admin_transfer
import pesanan_alur as alur
import pesanan_http
import pesanan_midtrans
import pesanan_rekening
import pesanan_admin_order
import pesanan_status as st
import purna
from admin_pesanan_aksi import periksa_order
from schema_pesanan import CATATAN_REFUND
from schema_purna import CATATAN_PAKAI

RUTE = ui.RUTE
RUTE_PERIKSA = ui.RUTE_PERIKSA
RUTE_REFUND = ui.RUTE_REFUND
RUTE_VOUCHER = ui.RUTE_VOUCHER
RUTE_TERBIT = ui.RUTE_TERBIT
RUTE_ORDER = ui.RUTE_ORDER
AKSI_PERIKSA = "periksa_pesanan"
AKSI_REFUND = "catat_refund_pesanan"
AKSI_VOUCHER = "catat_voucher_pakai"
AKSI_TERBIT = "catat_laporan_terbit"
AKSI_RUTE = {RUTE_PERIKSA: AKSI_PERIKSA, RUTE_REFUND: AKSI_REFUND, RUTE_VOUCHER: AKSI_VOUCHER,
             RUTE_TERBIT: AKSI_TERBIT}
_AKSI_UI = {ui.AKSI_PERIKSA: AKSI_PERIKSA, ui.AKSI_REFUND: AKSI_REFUND, ui.AKSI_VOUCHER: AKSI_VOUCHER,
            ui.AKSI_TERBIT: AKSI_TERBIT}
MAKS_HALAMAN = 100000
_POLA_ORDER = re.compile(r"ord_[0-9a-f]{32}")
_PANJANG_OPERASI = 32
_GALAT_BACA = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)
# Galat baca kartu data cek (DB belajar): kartu menampilkan "tidak terbaca", halaman tetap utuh. ValueError/LookupError
# mencakup ringkasan tersimpan yang rusak dan id yang tak sah; hanya NAMA tipe yang dicatat di log.
_GALAT_CEK = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError, ValueError, LookupError)
_log = logging.getLogger(__name__)


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
    if saring is not None and saring not in ui.KODE_SARING:
        raise ValueError("query tidak sah")
    return halaman, hasil, saring


def _detail_query(penangan):
    """(order_id, hasil) dari query Detail order; id harus persis `ord_` + 32 hex, hasil dari allowlist detail."""
    query = h._query(penangan, diizinkan={"id", "hasil"})
    hasil = query.get("hasil")
    if hasil is not None and hasil not in ui.KODE_HASIL_DETAIL:
        raise ValueError("query tidak sah")
    return periksa_order(query.get("id")), hasil


def _token_detail(penangan, principal, detail, gerbang_terbuka):
    """{aksi: (csrf, tinjauan)} hanya untuk aksi yang tampil di Detail order; kosong bila bukan sesi berkuki."""
    if principal.metode != "cookie":
        return {}
    tersedia = ui.aksi_tersedia(detail, gerbang_terbuka)
    if not tersedia:
        return {}
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    return {
        nama: (csrf, admin_security.buat_tinjauan(akun, sesi, _AKSI_UI[nama], {"target_id": detail["order_id"]}))
        for nama in tersedia}


def _kirim(penangan, principal, isi, kode=200, *, judul=ui.JUDUL, subjudul=ui.SUBJUDUL):
    if _admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "pesanan", isi, penangan=penangan, skrip=True, judul=judul, subjudul=subjudul,
    ), kode, skrip=True)


def _baca_daftar(halaman, saring):
    """(daftar tersaring + hitungan, ringkasan transfer per order, ringkasan purna per order) dalam satu koneksi baca.

    Kolom Laporan memanggil `purna_ringkas` per baris halaman (N+1 sengaja: paling banyak `ui.PER_HALAMAN` = 25 baris,
    batas keras domain 100, tiap panggilan hanya SELECT kecil pada SQLite lokal), supaya turunan voucher/terlambat
    memakai satu sumber dengan Detail order dan tidak ada salinan logikanya di SQL daftar.
    """
    with pesanan.buka(h._path_admin()) as kon:
        kini = alur._sekarang()
        daftar = pesanan.daftar_tersaring(
            kon, halaman=halaman, per_halaman=ui.PER_HALAMAN, sekarang=kini, kelompok=saring)
        ids = [i["order_id"] for i in daftar["items"]]
        laporan = {oid: pesanan_admin_order.purna_ringkas(kon, oid, kini) for oid in ids}
        return daftar, pesanan_admin_transfer.ringkasan(kon, ids), laporan


def _rekening_terisi() -> bool:
    """True bila rekening transfer terisi; pembaca fail-closed (galat baca = False), tidak pernah memuat nomornya."""
    return pesanan_rekening.baca(h._path_admin()) is not None


def _baca_detail(order_id):
    with pesanan.buka(h._path_admin()) as kon:
        return pesanan.detail_order(kon, order_id, alur._sekarang())


def _baca_cek(order_id):
    """Ringkasan data cek untuk order lunas, atau None bila tidak terbaca (galat, atau tiga kunci tidak cocok).

    Tiga kunci (siswa, cek, akun) dibaca dari ledger admin di server, lalu dipakai membaca DB belajar lewat koneksi
    yang dibuka `database.buka()` (pola admin lain) dan dikunci `query_only`: tidak ada tulis ke DB belajar.
    """
    try:
        with pesanan.buka(h._path_admin()) as kon:
            kunci = pesanan_admin_order.kunci_cek(kon, order_id)
        if kunci is None:
            return None
        with database.buka() as kon:
            kon.execute("PRAGMA query_only = ON")
            return cek_ringkasan_admin.ringkasan_untuk_order(kon, *kunci, alur._sekarang())
    except _GALAT_CEK as galat:
        _log.warning("kartu data cek gagal dibaca: %s", type(galat).__name__)
        return None


def _dengan_cek(detail: dict) -> dict:
    """Detail + kunci `cek` bila order lunas (dict baru); selain itu detail apa adanya, tanpa membaca DB belajar."""
    if not pesanan_admin_order.kartu_cek_berlaku(detail["status"]):
        return detail
    return {**detail, "cek": _baca_cek(detail["order_id"])}


def _get_detail(penangan, principal) -> None:
    try:
        order_id, hasil = _detail_query(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        detail = _baca_detail(order_id)
        gerbang = _runtime_periksa(penangan) is not None
        forms = {} if detail is None else _token_detail(penangan, principal, detail, gerbang)
    except PermissionError:
        return h._galat(penangan, 403, ui.COPY_GALAT_FORM)
    except _GALAT_BACA:
        return _kirim(penangan, principal, ui.halaman_tidak_siap(), 503, judul=dui.JUDUL, subjudul=dui.SUBJUDUL)
    if detail is None:
        return h._tidak_ada(penangan)
    detail = _dengan_cek(detail)
    _kirim(penangan, principal, dui.halaman(
        detail, gerbang_terbuka=gerbang, forms=forms, hasil=hasil, baca_saja=principal.metode != "cookie"),
        judul=dui.JUDUL, subjudul=dui.SUBJUDUL)


def tangani_get(penangan, jalur) -> bool:
    if admin_verifikasi_http.tangani_get(penangan, jalur) or admin_rekening_http.tangani_get(penangan, jalur):
        return True
    if jalur not in (RUTE, RUTE_ORDER):
        return False
    principal = _admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    if jalur == RUTE_ORDER:
        _get_detail(penangan, principal)
        return True
    try:
        halaman, hasil, saring = _halaman_query(penangan)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    try:
        daftar, transfer, laporan = _baca_daftar(halaman, saring)
        gerbang = _runtime_periksa(penangan) is not None
        rekening = _rekening_terisi()
    except _GALAT_BACA:
        _kirim(penangan, principal, ui.halaman_tidak_siap(), 503)
        return True
    _kirim(penangan, principal, ui.halaman(
        daftar, halaman=halaman, gerbang_terbuka=gerbang, hasil=hasil, transfer=transfer, saring=saring,
        hitungan=daftar["hitungan"], rekening_terisi=rekening, laporan=laporan))
    return True


# --- POST ------------------------------------------------------------------

def operasi_refund(order_id: str) -> str:
    """Id operasi deterministik per order: replay identik idempoten, isi beda = konflik."""
    return "rfd_" + hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:_PANJANG_OPERASI]


def operasi_voucher(order_id: str) -> str:
    """Id operasi pemakaian voucher, deterministik per order (satu catatan per order; replay idempoten)."""
    return "vch_" + hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:_PANJANG_OPERASI]


def _order_dari_tinjauan(tinjauan) -> str:
    order_id = tinjauan["data"].get("target_id")
    if type(order_id) is not str or _POLA_ORDER.fullmatch(order_id) is None:
        raise ValueError("order tidak sah")
    return order_id


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


def _voucher(principal, order_id: str, data: dict) -> str:
    """Catat voucher dipakai: hanya field `catatan_kode` (enum `schema_purna.CATATAN_PAKAI`); order dari tinjauan."""
    if set(data) != {"catatan_kode"}:
        raise ValueError("isian voucher tidak sah")
    catatan = data["catatan_kode"]
    if catatan not in CATATAN_PAKAI:
        raise ValueError("catatan_kode voucher tidak sah")
    with pesanan.buka(h._path_admin(), tulis_data=True) as kon:
        hasil = purna.catat_pakai(
            kon, order_id, operasi_voucher(order_id), principal.id_akun, catatan, alur._sekarang())
    return "voucher_dicatat" if hasil["baru"] else "voucher_sudah_ada"


def _terbit(principal, order_id: str, data: dict) -> str:
    """Catat laporan terbit: tanpa field apa pun; waktu terbit = jam pencatatan server."""
    if data:
        raise ValueError("isian terbit asing")
    with pesanan.buka(h._path_admin(), tulis_data=True) as kon:
        hasil = purna.catat_terbit(kon, order_id, principal.id_akun, alur._sekarang())
    return "terbit_dicatat" if hasil["baru"] else "terbit_sudah_ada"


def _kode_hasil(penangan, principal, jalur: str, order_id: str, data: dict) -> str:
    """Jalankan aksi sesuai rute; tiap rute punya penangan sendiri (tidak ada jalur bawaan)."""
    if jalur == RUTE_PERIKSA:
        return _periksa(penangan, principal, order_id, data)
    if jalur == RUTE_REFUND:
        return _refund(principal, order_id, data)
    if jalur == RUTE_VOUCHER:
        return _voucher(principal, order_id, data)
    if jalur == RUTE_TERBIT:
        return _terbit(principal, order_id, data)
    raise LookupError("rute tidak dikenal")


def _jalankan(penangan, principal, jalur: str, data: dict) -> None:
    aksi = AKSI_RUTE[jalur]
    _akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)
    order_id = _order_dari_tinjauan(tinjauan)
    kode = _kode_hasil(penangan, principal, jalur, order_id, data)
    h._redirect(penangan, "%s?id=%s&hasil=%s" % (RUTE_ORDER, order_id, kode))


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

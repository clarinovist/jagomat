"""Rute admin verifikasi transfer: detail `/admin/pesanan/verifikasi`, pratinjau bukti `/admin/pesanan/bukti`,
dan aksi `/admin/pesanan/setujui` / `/admin/pesanan/tolak`.

Dijawab `admin_http` sebelum palang guru, jadi anonim, murid, dan guru menerima 404 yang sama dengan rute admin
tak dikenal (`h._tidak_ada`) SEBELUM ledger atau berkas disentuh. Tidak bergantung pada gerbang transfer:
admin tetap dapat memutuskan bukti yang menunggu setelah sakelar dimatikan. Aturan:

- Aksi memakai pola uang yang sama dengan aksi pesanan lain (`h._token_final`: CSRF + tinjauan terikat aksi dan
  sesi + sandi ulang, wajib sesi berkuki) dan same-origin (`baca_form`). `order_id` dan bukti terakhir yang dilihat
  admin HANYA dari tinjauan bertanda tangan; `admin_id` dari principal sesi. Field lain (admin_id, order_id,
  nominal) = 400. Keputusan hanya sah atas bukti terbaru yang dilihat admin (bukti baru = 409, bukan disetujui
  tanpa dilihat). Setujui tanpa field; Tolak hanya `alasan` (wajib, <= BATAS_ALASAN, tanpa karakter kontrol).
- Pratinjau: id bukti hanya digit ASCII, nama berkas dari ledger (tidak pernah dari input), dibuka lewat
  `bukti_berkas.buka_berkas` (nama divalidasi, symlink ditolak), tipe harus cocok dengan magic bytes dan tipe
  tersimpan. Respons: tipe dari ledger, `nosniff`, `no-store`, CSP `default-src 'none'; sandbox`, nama unduhan
  generik. Bukti terhapus/hilang = 404 ramah; berkas rusak = 503 tanpa isi.
- Tidak ada `str(galat)` di respons; PRG 303 dengan kode hasil dari enum tetap: ke detail transfer menunggu tertua
  berikutnya (`?order=&hasil=`), ke daftar menunggu bila habis, atau ke daftar lama bila pencarian berikutnya gagal.
"""
from __future__ import annotations

import sqlite3

import admin_http as h
import admin_pesanan_aksi as aksi
import admin_pesanan_pages as daftar_ui
import admin_security
import admin_store
import admin_transfer_menunggu as menunggu
import admin_verifikasi_pages as ui
import bukti_berkas
import pesanan
import pesanan_admin_transfer as pat
import pesanan_alur as alur
import pesanan_transfer
import peta_otomatis
from schema_transfer import BATAS_UKURAN_BUKTI, MIME_BUKTI

RUTE_VERIFIKASI = ui.RUTE_VERIFIKASI
RUTE_BUKTI = ui.RUTE_BUKTI
RUTE_SETUJUI = ui.RUTE_SETUJUI
RUTE_TOLAK = ui.RUTE_TOLAK
_AKSI_POST = {RUTE_SETUJUI: ui.AKSI_SETUJUI, RUTE_TOLAK: ui.AKSI_TOLAK}
HASIL_SETUJU = "verifikasi_setuju"
HASIL_TOLAK = "verifikasi_tolak"
MAKS_DIGIT_ID = 12
CSP_BUKTI = "default-src 'none'; sandbox"
_HASIL_DETAIL = frozenset({HASIL_SETUJU, HASIL_TOLAK})
_GALAT_BACA = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "pesanan", isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL,
    ), kode, skrip=True)


# --- detail ------------------------------------------------------------------

def _order_query(penangan):
    """(order_id, hasil) dari query; `hasil` hanya kode keputusan sah (banner lanjut) atau None."""
    query = h._query(penangan, diizinkan={"order", "hasil"})
    hasil = query.get("hasil")
    if hasil is not None and hasil not in _HASIL_DETAIL:
        raise ValueError("hasil tidak sah")
    return aksi.periksa_order(query.get("order")), hasil


def _forms(penangan, principal, detail):
    """{'setujui': (csrf, tinjauan), 'tolak': ...} hanya untuk order menunggu dan sesi berkuki."""
    if principal.metode != "cookie" or detail["status"] != ui.STATUS_MENUNGGU:
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    isi = {"target_id": detail["order_id"], "target_revisi": detail["bukti_terakhir_id"]}
    return {nama: (csrf, admin_security.buat_tinjauan(akun, sesi, kode, isi))
            for nama, kode in (("setujui", ui.AKSI_SETUJUI), ("tolak", ui.AKSI_TOLAK))}


def _baca_detail(order_id: str):
    with pesanan_transfer.buka(h._path_admin()) as kon:
        return pat.detail(kon, order_id, alur.waktu_sekarang())


def _get_detail(penangan, principal) -> None:
    try:
        order_id, hasil = _order_query(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        detail = _baca_detail(order_id)
        forms = None if detail is None else _forms(penangan, principal, detail)
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    if detail is None:
        return h._tidak_ada(penangan)
    _kirim(penangan, principal, ui.halaman(
        detail, forms, baca_saja=principal.metode != "cookie", lanjut=hasil))


# --- pratinjau bukti ---------------------------------------------------------

def _query_bukti(penangan):
    """(id_bukti, unduh) dari query; apa pun yang tidak persis sah = ValueError."""
    query = h._query(penangan, diizinkan={"id", "unduh"})
    nilai = query.get("id", "")
    if not nilai.isascii() or not nilai.isdigit() or len(nilai) > MAKS_DIGIT_ID or int(nilai) < 1:
        raise ValueError("id tidak sah")
    if query.get("unduh") not in (None, "1"):
        raise ValueError("unduh tidak sah")
    return int(nilai), query.get("unduh") == "1"


def _muat_bukti(bukti_id: int):
    """(mime, isi) atau None bila bukti tak ada, terhapus, atau berkas hilang; galat lain diteruskan."""
    with pesanan_transfer.buka(h._path_admin()) as kon:
        meta = pat.ambil_bukti(kon, bukti_id)
    if meta is None or meta["dihapus"]:
        return None
    try:
        with bukti_berkas.buka_berkas(meta["berkas"]) as f:
            isi = f.read(BATAS_UKURAN_BUKTI + 1)
    except FileNotFoundError:
        return None
    except OSError:
        raise bukti_berkas.BuktiBerkasError("berkas bukti tidak bisa dibuka") from None
    if meta["mime"] not in MIME_BUKTI or len(isi) > BATAS_UKURAN_BUKTI or bukti_berkas.mime_dari_isi(isi) != meta["mime"]:
        raise bukti_berkas.BuktiBerkasError("berkas bukti tidak cocok dengan catatan")
    return meta["mime"], isi


def _header_bukti(mime: str, panjang: int, unduh: bool) -> dict:
    disposisi = "attachment" if unduh else "inline"
    return {**admin_security.header_privat(), "Content-Security-Policy": CSP_BUKTI,
            "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin",
            "Content-Type": mime, "Content-Length": str(panjang), "Vary": "Cookie",
            "Content-Disposition": '%s; filename="%s"' % (disposisi, ui.nama_unduhan(mime))}


def _kirim_bukti(penangan, mime: str, isi: bytes, unduh: bool) -> None:
    penangan.send_response(200)
    for nama, nilai in _header_bukti(mime, len(isi), unduh).items():
        penangan.send_header(nama, nilai)
    penangan.end_headers()
    penangan.wfile.write(isi)


def _get_bukti(penangan, principal) -> None:
    try:
        bukti_id, unduh = _query_bukti(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        muat = _muat_bukti(bukti_id)
    except bukti_berkas.BuktiBerkasError:
        return _kirim(penangan, principal, ui.halaman_bukti_rusak(), 503)
    except _GALAT_BACA:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    if muat is None:
        return _kirim(penangan, principal, ui.halaman_bukti_tidak_tersedia(), 404)
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    _kirim_bukti(penangan, muat[0], muat[1], unduh)


def tangani_get(penangan, jalur) -> bool:
    if jalur not in (RUTE_VERIFIKASI, RUTE_BUKTI):
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    (_get_detail if jalur == RUTE_VERIFIKASI else _get_bukti)(penangan, principal)
    return True


# --- keputusan ---------------------------------------------------------------

def _bukti_dilihat(tinjauan) -> int:
    nilai = tinjauan["data"].get("target_revisi")
    if type(nilai) is not int or nilai < 1:
        raise ValueError("bukti tidak sah")
    return nilai


def _tujuan_setelah_putusan(order_id: str, hasil: str) -> str:
    """Transfer menunggu tertua berikutnya; habis = daftar menunggu; galat baca = daftar lama (keputusan sudah tersimpan)."""
    try:
        berikut = menunggu.berikutnya(h._path_admin(), alur.waktu_sekarang(), kecuali=order_id)
    except menunggu.GALAT_BACA:
        return "%s?halaman=1&hasil=%s" % (daftar_ui.RUTE, hasil)
    if berikut is None:
        return "%s?status=%s&halaman=1&hasil=%s" % (daftar_ui.RUTE, daftar_ui.SARING_MENUNGGU, hasil)
    return "%s?order=%s&hasil=%s" % (RUTE_VERIFIKASI, berikut, hasil)


def _putuskan(penangan, principal, jalur: str) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, _AKSI_POST[jalur])
    setuju = jalur == RUTE_SETUJUI
    aksi.wajib_field(data, frozenset() if setuju else frozenset({"alasan"}))
    order_id, dilihat = aksi.order_dari_tinjauan(tinjauan), _bukti_dilihat(tinjauan)
    with pesanan_transfer.buka(h._path_admin(), tulis_data=True) as kon:
        if setuju:
            pesanan_transfer.setujui(kon, order_id, principal.id_akun, alur.waktu_sekarang(),
                                     bukti_terakhir_id=dilihat)
        else:
            pesanan_transfer.tolak(kon, order_id, principal.id_akun, data["alasan"], alur.waktu_sekarang(),
                                   bukti_terakhir_id=dilihat)
    if setuju:
        peta_otomatis.setelah_lunas(order_id)  # ledger sudah commit; galat pemicu tidak menggagalkan persetujuan
    h._redirect(penangan, _tujuan_setelah_putusan(order_id, HASIL_SETUJU if setuju else HASIL_TOLAK))


def tangani_post(penangan, jalur) -> bool:
    if jalur not in _AKSI_POST:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(
        penangan, lambda: _putuskan(penangan, principal, jalur), copy_konflik=ui.COPY_GALAT_KONFLIK,
        copy_isian=ui.COPY_GALAT_ALASAN if jalur == RUTE_TOLAK else daftar_ui.COPY_GALAT_ISIAN)
    return True

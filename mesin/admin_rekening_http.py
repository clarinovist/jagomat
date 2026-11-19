"""Rute admin pengaturan rekening transfer: GET/POST `/admin/pesanan/rekening`.

Dijawab `admin_http` sebelum palang guru: anonim/murid/guru = 404 identik rute admin tak dikenal sebelum DB
dibaca. Tidak bergantung pada gerbang transfer (rekening diisi SEBELUM sakelar dinyalakan). Aturan:

- Aksi = pola uang admin (`h._token_final`: CSRF + tinjauan terikat aksi dan sesi + sandi ulang, sesi berkuki),
  same-origin, tepat tiga field isian. `revisi` dan `sidik` snapshot yang dilihat admin HANYA dari tinjauan
  bertanda tangan (bukan field form); `pesanan_rekening.ubah` menegakkan optimistic concurrency (konflik = 409
  ramah, bukan menimpa). `operasi` = id operasi tinjauan sehingga kirim ulang form yang sama idempoten.
- Nomor rekening tidak pernah tampil lengkap (hanya ter-mask), tidak dipantulkan di galat, dan audit hanya
  menyimpan sidik. Skema belum dipasang = kartu/pesan jujur dengan petunjuk migrasi, tanpa efek.
"""
from __future__ import annotations

import sqlite3
import time

import admin_http as h
import admin_pesanan_aksi as aksi
import admin_pesanan_pages as daftar_ui
import admin_rekening_pages as ui
import admin_security
import admin_store
import auth
import pesanan_rekening
import pesanan_transfer_gerbang as gerbang

RUTE = ui.RUTE_REKENING
_FIELD = frozenset({"nama_bank", "nomor_rekening", "atas_nama"})
HASIL_TERSIMPAN = "tersimpan"
_GALAT_BACA = (admin_store.StoreBelumSiap, sqlite3.Error, OSError, ValueError)


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "pesanan", isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL,
    ), kode, skrip=True)


def _skema_terpasang(path) -> bool:
    with admin_store.buka_baca(path) as kon:
        return bool(pesanan_rekening.validasi_schema(kon))


def _keadaan(path) -> dict:
    """Keadaan rekening untuk halaman; galat baca/skema rusak diteruskan (dijawab 503 jujur)."""
    if not _skema_terpasang(path):
        return {"status": ui.KEADAAN_BELUM_DIPASANG}
    cfg = pesanan_rekening.baca(path)
    if cfg is None:
        return {"status": ui.KEADAAN_KOSONG}
    return {"status": ui.KEADAAN_TERISI, "nama_bank": cfg.nama_bank, "atas_nama": cfg.atas_nama,
            "nomor": cfg.nomor_rekening, "revisi": cfg.revisi, "diperbarui": cfg.diperbarui,
            "actor": cfg.actor_id, "sidik": pesanan_rekening.sidik_konfigurasi(cfg)}


def _snapshot(keadaan: dict):
    """(revisi, sidik) dari pembacaan yang sama dengan halaman; belum diisi = (0, SIDIK_KOSONG)."""
    if keadaan["status"] != ui.KEADAAN_TERISI:
        return 0, pesanan_rekening.SIDIK_KOSONG
    return keadaan["revisi"], keadaan["sidik"]


def _token(penangan, principal, keadaan: dict):
    """(csrf, tinjauan) untuk form ubah; None bila bukan sesi berkuki."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    revisi, sidik = _snapshot(keadaan)
    return (h._csrf(akun, sesi),
            admin_security.buat_tinjauan(akun, sesi, ui.AKSI_UBAH, {"revisi": revisi, "sidik": sidik}))


def _hasil_query(penangan):
    hasil = h._query(penangan, diizinkan={"hasil"}).get("hasil")
    if hasil is not None and hasil not in ui.KODE_HASIL:
        raise ValueError("hasil tidak sah")
    return hasil


def _get(penangan, principal) -> None:
    try:
        hasil = _hasil_query(penangan)
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        keadaan = _keadaan(h._path_admin())
        if keadaan["status"] == ui.KEADAAN_BELUM_DIPASANG:
            return _kirim(penangan, principal, ui.halaman_tidak_siap(), 503)
        token = _token(penangan, principal, keadaan)
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_BACA:
        return _kirim(penangan, principal, ui.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, ui.halaman(
        keadaan, token, hasil=hasil, sakelar_aktif=gerbang.transfer_aktif()))


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    _get(penangan, principal)
    return True


def _snapshot_tinjauan(tinjauan):
    meta = tinjauan["data"]
    revisi, sidik = meta.get("revisi"), meta.get("sidik")
    if type(revisi) is not int or type(sidik) is not str:
        raise ValueError("snapshot tidak sah")
    return revisi, sidik


def _simpan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH)
    aksi.wajib_field(data, _FIELD)
    revisi, sidik = _snapshot_tinjauan(tinjauan)
    pesanan_rekening.ubah(
        h._path_admin(), auth.BERKAS_SANDI, principal, operasi=tinjauan["op"], revisi=revisi,
        sidik_awal=sidik, nama_bank=data["nama_bank"], nomor_rekening=data["nomor_rekening"],
        atas_nama=data["atas_nama"], sekarang=int(time.time()))
    h._redirect(penangan, "%s?hasil=%s" % (RUTE, HASIL_TERSIMPAN))


def tangani_post(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    aksi.jalankan_aman(penangan, lambda: _simpan(penangan, principal), copy_konflik=ui.COPY_GALAT_KONFLIK,
                       copy_isian=ui.COPY_GALAT_ISIAN, copy_layanan=ui.COPY_TIDAK_SIAP)
    return True

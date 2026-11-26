"""Rute guru baca-saja `/guru/jadwal`, `/guru/kelas`, dan `/guru/kelas/<klp_id>` (Jadwal dan Kelas saya, Fase 1).

Identitas HANYA dari sesi: `guru_id` = `id_akun` principal yang berperan guru. Tidak ada id dari URL, kueri, atau form.
Selain guru pemilik (admin, murid, anonim, mode lokal tanpa principal) jawaban 404 yang byte-identik dengan rute tak
dikenal (`lembaga_http._tidak_ada`). Galat baca DB admin: daftar kosong; detail 404. Nama anak dibaca dari latihan.db
mode ro; galat baca memakai placeholder. Tanpa tulis dan tanpa pembuatan berkas.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import admin_store
import admin_store_core
import database
import guru_jadwal_baca as baca
import guru_jadwal_pages as halaman
import jadwal_store as js
import kelas_dasar as dasar
import lembaga_http
import pesanan_alur as alur

_log = logging.getLogger(__name__)

RUTE_JADWAL = "/guru/jadwal"
RUTE_KELAS = "/guru/kelas"
PREFIX_KELAS = RUTE_KELAS + "/"
_GALAT_BACA = (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError)


def _principal_guru(penangan):
    """Principal sesi bila berperan guru; None untuk admin, murid, anonim, dan mode lokal."""
    principal = penangan._principal()
    if principal is None or principal.peran != "guru":
        return None
    return principal


def _ident(principal) -> tuple:
    return principal.pengguna, principal.peran


def _kini() -> str:
    return dasar.ke_baku(alur.waktu_sekarang())


def _baca_admin(fungsi, bawaan):
    """Jalankan `fungsi(kon)` pada DB admin (ro). Galat baca -> `bawaan` (daftar kosong, atau None untuk detail)."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            return fungsi(kon)
    except _GALAT_BACA as galat:
        _log.warning("jadwal guru tidak terbaca: %s", type(galat).__name__)
        return bawaan


@contextmanager
def _buka_belajar_baca():
    """latihan.db dibuka mode ro: tidak pernah membuat berkas atau menulis."""
    uri = Path(database.BAWAAN).resolve().as_uri() + "?mode=ro"
    kon = sqlite3.connect(uri, uri=True)
    try:
        yield kon
    finally:
        kon.close()


def _nama_anak(ids) -> dict:
    """Nama anak untuk id hasil kueri milik guru saja. Galat baca latihan.db -> placeholder untuk semua id."""
    unik = sorted(set(ids))
    if not unik:
        return {}
    try:
        with _buka_belajar_baca() as kon:
            return baca.nama_siswa(kon, unik)
    except (sqlite3.Error, ValueError) as galat:
        _log.warning("nama anak tidak terbaca: %s", type(galat).__name__)
        return {siswa_id: baca.PLACEHOLDER_NAMA for siswa_id in unik}


def _tampilan_pertemuan(pertemuan: dict, nama: dict) -> dict:
    """View-model tanpa siswa_id/order_id: hanya teks dan `kelas_id` (kelompok milik guru, untuk href)."""
    if pertemuan["jenis"] == "kelompok":
        judul = "Mini Class: " + (pertemuan["nama_kelompok"] or "")
    else:
        judul = "Private: " + nama.get(pertemuan["siswa_id"], baca.PLACEHOLDER_NAMA)
    return {"judul": judul, "ke": pertemuan["ke"], "mulai": pertemuan["mulai"],
            "dibatalkan": pertemuan["dibatalkan"], "kelas_id": pertemuan["kelompok_id"]}


def _halaman_jadwal(penangan, principal) -> None:
    kini = _kini()
    pertemuan = _baca_admin(lambda kon: baca.pertemuan_mendatang(kon, principal.id_akun, kini), [])
    nama = _nama_anak(p["siswa_id"] for p in pertemuan if p["siswa_id"] is not None)
    tampilan = [_tampilan_pertemuan(p, nama) for p in pertemuan]
    penangan._kirim_privat(halaman.halaman_jadwal(_ident(principal), tampilan))


def _halaman_kelas(penangan, principal) -> None:
    kini = _kini()
    kelas = _baca_admin(lambda kon: baca.daftar_kelas(kon, principal.id_akun, kini), [])
    penangan._kirim_privat(halaman.halaman_kelas(_ident(principal), kelas))


def _halaman_detail(penangan, principal, kelompok_id: str) -> None:
    kini = _kini()
    detail = _baca_admin(lambda kon: baca.detail_kelas(kon, principal.id_akun, kelompok_id, kini), None)
    if detail is None:
        lembaga_http._tidak_ada(penangan)
        return
    nama = _nama_anak(detail["anggota"])
    tampilan = {
        "nama": detail["nama"],
        "lokasi": detail["lokasi"],
        "kuota": detail["kuota"],
        "terisi": len(detail["anggota"]),
        "sesi": detail["sesi"],
        "anggota": sorted(nama.get(siswa_id, baca.PLACEHOLDER_NAMA) for siswa_id in detail["anggota"]),
    }
    penangan._kirim_privat(halaman.halaman_detail(_ident(principal), tampilan))


def tangani_get(penangan, jalur: str) -> bool:
    """Dipanggil setelah palang sandi guru/admin. False hanya untuk jalur di luar keluarga `/guru/jadwal|kelas`."""
    if jalur != RUTE_JADWAL and jalur != RUTE_KELAS and not jalur.startswith(PREFIX_KELAS):
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        lembaga_http._tidak_ada(penangan)
        return True
    if jalur == RUTE_JADWAL:
        _halaman_jadwal(penangan, principal)
    elif jalur == RUTE_KELAS:
        _halaman_kelas(penangan, principal)
    else:
        _halaman_detail(penangan, principal, jalur[len(PREFIX_KELAS):])
    return True

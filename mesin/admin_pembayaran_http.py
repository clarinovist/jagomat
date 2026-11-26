"""Rute admin `/admin/pembayaran` ("Semua pembayaran"): daftar baca-saja tiga jalur pembayaran.

Dijawab `admin_http` sebelum palang guru: anonim, murid, dan guru menerima 404 yang sama dengan rute admin tak dikenal
SEBELUM ledger disentuh. Hanya GET; query hanya `status` (allowlist kelompok). Tidak ada aksi tulis, tanpa
`str(galat)` di respons; jenis yang tidak terbaca dilaporkan di halaman, bukan diam-diam kosong.
"""
from __future__ import annotations

import admin_http as h
import admin_pembayaran_pages as ui
import admin_pembayaran_semua as semua
import admin_transfer_menunggu as menunggu
import auth
import pesanan_alur as alur

RUTE = ui.RUTE


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    if h._principal_admin(penangan) != principal:
        return h._tidak_ada(penangan)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "pembayaran", isi, penangan=penangan, judul=ui.JUDUL, subjudul=ui.SUBJUDUL), kode)


def _saring(penangan):
    nilai = h._query(penangan, diizinkan={"status"}).get("status")
    if nilai is not None and nilai not in ui.KODE_SARING:
        raise ValueError("status tidak sah")
    return nilai


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        saring = _saring(penangan)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    baris, gagal = semua.baca(h._path_admin(), alur.waktu_sekarang())
    if len(gagal) == 3:
        _kirim(penangan, principal, ui.halaman_tidak_siap(), 503)
        return True
    tampil = semua.lengkapi_anak_akun(semua.saring(baris, saring), auth.BERKAS_SANDI)
    _kirim(penangan, principal, ui.halaman(tampil, saring=saring, hitungan=semua.hitung(baris), gagal=gagal))
    return True

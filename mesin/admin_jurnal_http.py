"""Rute admin baca-saja `/admin/jadwal/jurnal`: daftar pertemuan yang belum dicatat guru (tanpa tulis).

Dijawab `admin_http` sebelum palang guru; anonim dan guru menerima 404 yang sama dengan rute tak dikenal. Tanpa form,
tanpa token, dan tanpa POST. DB admin yang belum siap dijawab 503 tertata, bukan 500. Pembacaan tidak membuat berkas.
"""
from __future__ import annotations

import time

import admin_antrean_jurnal as aj
import admin_http as h
import admin_jurnal_pages as ui
import jadwal_admin_http as jah

RUTE = ui.RUTE
SECTION = "kelas_belajar"


def _sekarang() -> float:
    return time.time()


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SECTION, isi, penangan=penangan, judul=ui.JUDUL, subjudul=ui.SUBJUDUL), kode)


def _get(penangan, principal) -> None:
    try:
        h._query(penangan, diizinkan=frozenset())
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        daftar = aj.daftar(h._path_admin(), _sekarang())
    except aj.GALAT_BACA:
        return _kirim(penangan, principal, ui.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, ui.halaman(daftar, jah.guru_map()))


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    _get(penangan, principal)
    return True

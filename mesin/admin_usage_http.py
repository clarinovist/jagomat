"""Rute admin baca-saja `/admin/pemakaian` (pemakaian guru)."""
from __future__ import annotations

import sqlite3

import admin_http as h
import admin_usage_pages as ui
import database
import teacher_usage

RUTE = "/admin/pemakaian"
JUDUL = "Pemakaian guru"
SUBJUDUL = "Apakah guru memakai Jagomat berulang dan berapa lama langkahnya. Tanpa nama anak."


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        h._query(penangan, diizinkan=set())
        with database.buka() as kon:
            daftar = teacher_usage.ambil_pemakaian(kon)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    except sqlite3.Error:
        h._galat(penangan, 503, "Layanan admin belum siap.")
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "pemakaian", ui.halaman(daftar), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL,
    ))
    return True

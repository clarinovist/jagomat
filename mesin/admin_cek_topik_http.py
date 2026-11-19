"""Rute admin baca-saja `/admin/cek-topik` (topik Cek Kemampuan gratis per kelas)."""
from __future__ import annotations

import admin_cek_topik_pages as ui
import admin_http as h
import question_context

RUTE = "/admin/cek-topik"
JUDUL = "Topik Cek Kemampuan"
SUBJUDUL = "Topik soal cek gratis per kelas. Diubah lewat kode dan rilis (keputusan pemilik 19 Nov 2026)."


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        h._query(penangan, diizinkan=set())
        dasar_aktif = question_context.materi_dasar_aktif()
    except ValueError:
        h._tidak_ada(penangan)
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "cek-topik", ui.halaman(dasar_aktif), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL,
    ))
    return True

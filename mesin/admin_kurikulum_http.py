"""Rute admin baca-saja `/admin/kurikulum` (peta kurikulum: topik, grup, dan butir CP Merdeka)."""
from __future__ import annotations

import admin_http as h
import admin_kurikulum_pages as ui

RUTE = "/admin/kurikulum"
JUDUL = "Peta kurikulum"
SUBJUDUL = "Topik, grup soal, dan Capaian Pembelajaran Merdeka. Diubah lewat kode dan rilis."


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        h._query(penangan, diizinkan=set())
    except ValueError:
        h._tidak_ada(penangan)
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", ui.halaman(), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL,
    ))
    return True

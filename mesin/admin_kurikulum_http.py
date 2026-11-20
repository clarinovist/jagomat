"""Rute admin `/admin/kurikulum/cp-detail` (Detail CP: topik, grup, dan butir CP Merdeka; baca-saja).

Pemetaan CP yang ditampilkan adalah nilai efektif (`kurikulum_override.daftar_cp()`); mengubahnya lewat
halaman per grup di `admin_kurikulum_cp_http`. Tampilan utama kurikulum (`/admin/kurikulum`) ada di
`admin_kurikulum_merdeka_http`.
"""
from __future__ import annotations

import admin_http as h
import admin_kurikulum_pages as ui
import kurikulum_override as override

RUTE = "/admin/kurikulum/cp-detail"
JUDUL = "Detail CP"
SUBJUDUL = "Topik, grup soal, dan Capaian Pembelajaran Merdeka. Pemetaan CP per grup bisa diubah admin."


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
        principal, "kurikulum", ui.halaman(override.daftar_cp()), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL,
    ))
    return True

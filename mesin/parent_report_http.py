"""Rute baca-saja `/laporan-ortu/<token>` untuk orang tua (tanpa login).

Seluruh keadaan tidak sah (token salah/kedaluwarsa/dicabut, laporan masih draf,
anak dihapus) menghasilkan satu halaman 404 identik. Query string diabaikan dan
rute ini tidak menulis apa pun ke basis data.
"""
from __future__ import annotations

import database
import parent_report_page as halaman
import parent_report_store as toko

AWALAN = "/laporan-ortu/"
POLOS = "/laporan-ortu"  # dispatcher dapat membuang garis miring akhir
CSP = ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
       "form-action 'none'; base-uri 'none'; frame-ancestors 'none'")


def _kirim_tidak_ada(penangan) -> None:
    penangan._kirim_tautan(halaman.render_tidak_dapat_dibuka(), 404, csp=CSP)


def tangani_get(penangan, jalur: str) -> bool:
    if jalur != POLOS and not jalur.startswith(AWALAN):
        return False
    token = jalur[len(AWALAN):]
    with database.buka() as kon:
        data = toko.ambil_dengan_token(kon, token)
    if data is None:
        _kirim_tidak_ada(penangan)
        return True
    penangan._kirim_tautan(halaman.render_laporan(**data), 200, csp=CSP)
    return True


def tangani_post(penangan, jalur: str) -> bool:
    """Halaman ini tidak punya formulir; POST apa pun tidak berefek."""
    if jalur != POLOS and not jalur.startswith(AWALAN):
        return False
    _kirim_tidak_ada(penangan)
    return True

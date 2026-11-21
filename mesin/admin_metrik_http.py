"""Rute admin baca-saja `/admin/metrik`: ringkasan metrik runtime sebagai JSON.

Dilindungi persis seperti rute admin lain: selain admin (anonim, guru, murid) mendapat
respons 404 admin generik yang sama, dan query string apa pun ditolak. Isinya hanya
agregat dari `metrik_runtime` (tanpa path mentah, token, atau data anak).
"""
from __future__ import annotations

import json

import admin_http as h
import admin_security
import metrik_runtime

RUTE = "/admin/metrik"


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    if h._principal_admin(penangan) is None:
        h._tidak_ada(penangan)
        return True
    try:
        h._query(penangan, diizinkan=set())
    except ValueError:
        h._tidak_ada(penangan)
        return True
    isi = json.dumps(
        metrik_runtime.ringkasan(), ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")
    penangan.send_response(200)
    penangan.send_header("Content-Type", "application/json; charset=utf-8")
    penangan.send_header("Content-Length", str(len(isi)))
    for nama, nilai in admin_security.header_privat().items():
        penangan.send_header(nama, nilai)
    penangan.send_header("Vary", "Cookie")
    penangan.end_headers()
    penangan.wfile.write(isi)
    return True

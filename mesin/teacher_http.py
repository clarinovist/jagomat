"""Permukaan HTTP beranda dan workspace guru.

Modul route menerima renderer dari façade ``web`` agar monkeypatch/caller lama
terus memakai simbol yang sama. Transport, identitas, cookie, dan primitive
respons tetap dimiliki ``web.Penangan``.
"""
from __future__ import annotations

import urllib.parse

import database


def tangani_beranda_get(
    penangan,
    jalur: str,
    jalur_penuh: str,
    *,
    halaman_utama,
) -> bool:
    """Tangani root terautentikasi dan alias beranda guru."""
    if jalur not in ("/", "/guru", "/ortu"):
        return False

    ident = penangan._identitas()
    if not penangan._lolos_sandi():
        return True
    if ident[1] == "admin":
        penangan.send_response(303)
        penangan.send_header("Location", "/admin")
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return True

    q = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    if jalur != "/guru":
        # Alias lama mempertahankan kabar, bukan tujuan bebas dari URL.
        qs = urllib.parse.urlencode({
            kunci: q[kunci][0]
            for kunci in ("pesan", "sorot")
            if kunci in q
        })
        penangan.send_response(303)
        penangan.send_header("Location", "/guru" + ("?" + qs if qs else ""))
        penangan.send_header("Content-Length", "0")
        penangan.end_headers()
        return True

    pesan = (q.get("pesan") or [""])[0][:200]
    try:
        sorot = int((q.get("sorot") or [""])[0])
    except ValueError:
        sorot = None
    with database.buka() as kon:
        isi = halaman_utama(
            kon,
            pesan=pesan,
            pemilik=ident[0],
            peran=ident[1],
            sorot=sorot,
        )
    import product_analytics_http as analitik
    survei = analitik.form_survei(penangan)
    if survei:
        isi = isi.replace(b"</main>", survei.encode() + b"</main>", 1)
        penangan._kirim_privat(isi)
    else:
        penangan._kirim(isi)
    return True

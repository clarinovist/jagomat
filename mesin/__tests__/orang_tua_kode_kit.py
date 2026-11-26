"""Bantuan HTTP bersama tes kode anak di halaman orang tua (`/murid/orang-tua/kode`). Data sintetis saja.

`req` mengembalikan (status, isi, header) tanpa mengikuti pengalihan. `login` memakai POST /masuk dan mengembalikan nilai
cookie sesi. `form_kode` membaca input tersembunyi form kode untuk satu tindakan dari HTML kartu.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

from http_test_kit import _basic

RUTE = "/murid/orang-tua"
RUTE_KODE = RUTE + "/kode"
PIN_TERTUTUP = RUTE + "/pin"
KODE_TAMPIL = re.compile(r"[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}")
POLA_FORM = re.compile(r'<form method="post" action="/murid/orang-tua/kode">(.*?)</form>', re.S)
POLA_INPUT = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)">')


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def req(server, jalur, *, data=None, cookie=None, basic=None, headers=None):
    isi = None if data is None else urllib.parse.urlencode(data).encode()
    permintaan = urllib.request.Request(server.alamat + jalur, data=isi,
                                        method=None if isi is None else "POST")
    if isi is not None:
        permintaan.add_header("Content-Type", "application/x-www-form-urlencoded")
    if cookie:
        permintaan.add_header("Cookie", "osn_sesi=" + cookie)
    if basic:
        permintaan.add_header("Authorization", _basic(*basic))
    for nama, nilai in (headers or {}).items():
        permintaan.add_header(nama, nilai)
    try:
        with urllib.request.build_opener(_TanpaIkut).open(permintaan, timeout=10) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as galat:
        return galat.code, galat.read().decode("utf-8", "replace"), dict(galat.headers)


def login(server, nama: str, sandi: str) -> str:
    kode, _, header = req(server, "/masuk", data={"nama": nama, "sandi": sandi})
    assert kode == 303, kode
    return header["Set-Cookie"].split(";")[0].split("=", 1)[1]


def form_kode(isi: str, tindakan: str) -> dict:
    """Input tersembunyi form kode untuk `tindakan` (token, kode_id). Kosong bila form itu tidak dirender."""
    for blok in POLA_FORM.findall(isi):
        masukan = dict(POLA_INPUT.findall(blok))
        if masukan.get("tindakan") == tindakan:
            return masukan
    return {}

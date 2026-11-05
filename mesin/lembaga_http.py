"""Rute guru `/lembaga` (ringkasan pemilik les) dan `/lembaga/pindah` (POST).

Kewenangan ditegakkan di sini dan diulang di ``lembaga_store.pindahkan`` dalam
transaksi yang sama. Selain pemilik lembaga (guru, bukan admin), semua jawaban
memakai 404 yang byte-identik dengan rute tak dikenal, termasuk POST yang
otorisasinya gagal (tanpa tulis apa pun). Penolakan bisnis dialihkan (PRG) ke
`/lembaga?pesan=<kode tetap>`.
"""
from __future__ import annotations

import re
import urllib.parse

import database
import lembaga_pages as halaman
import lembaga_store as toko
from learning_cycle_http import GalatForm, _batasi_laju
from support_pages import halaman_pesan

RUTE = "/lembaga"
RUTE_PINDAH = "/lembaga/pindah"
BATAS_FORM = 4096
_POLA_ID = re.compile(r"[1-9][0-9]{0,17}")
_BATAS_NAMA_GURU = 200


def _tidak_ada(penangan) -> None:
    """Jawaban sama persis dengan fallthrough GET rute tak dikenal."""
    penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _pemilik_guru(penangan):
    """(pengguna, peran) bila peran guru, selain itu None (admin tidak pernah pemilik)."""
    ident = penangan._identitas()
    return ident if ident and ident[1] == "guru" else None


def _baca_form(penangan):
    """Form urlencoded kecil dengan kunci tunggal; None bila tidak sah."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None or penangan.headers.get_content_type() != "application/x-www-form-urlencoded":
        return None
    try:
        pasangan = urllib.parse.parse_qs(
            tubuh.decode("utf-8", "strict"), keep_blank_values=True,
            strict_parsing=bool(tubuh), max_num_fields=8,
        )
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(v) != 1 for v in pasangan.values()):
        return None
    return {k: v[0] for k, v in pasangan.items()}


def _isian_pindah(data):
    """(siswa_id, ke) hanya bila tepat dua kolom sah; selain itu None."""
    if data is None or set(data) != {"siswa_id", "ke"}:
        return None
    ke = data["ke"]
    if not _POLA_ID.fullmatch(data["siswa_id"]) or not ke or len(ke) > _BATAS_NAMA_GURU:
        return None
    return int(data["siswa_id"]), ke


def _kode_pesan(jalur_penuh: str) -> str:
    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query)
    nilai = (kueri.get("pesan") or [""])[0]
    return nilai if nilai in halaman.PESAN else ""


def tangani_get(penangan, jalur: str) -> bool:
    """Dipanggil setelah palang sandi guru/admin."""
    if jalur not in (RUTE, RUTE_PINDAH):
        return False
    ident = _pemilik_guru(penangan) if jalur == RUTE else None
    if ident is None:
        _tidak_ada(penangan)
        return True
    with database.buka() as kon:
        lembaga = toko.lembaga_milik(kon, ident[0])
        if lembaga is None:
            _tidak_ada(penangan)
            return True
        isi = halaman.halaman(lembaga, toko.ringkasan(kon, lembaga),
                              _kode_pesan(penangan.path), ident)
    penangan._kirim_privat(isi)
    return True


def _galat_form(penangan, galat: GalatForm) -> None:
    if galat.status == 429:
        penangan._kirim(halaman_pesan("Terlalu banyak permintaan", "<h1>Terlalu banyak permintaan</h1>"
                                      "<p>Coba lagi sebentar.</p>"), 429)
    else:
        penangan._tolak_isian(galat.status)


def tangani_post(penangan, jalur: str) -> bool:
    """Dipanggil setelah `_asal_sama_post` dan palang sandi guru/admin."""
    if jalur != RUTE_PINDAH:
        return False
    ident = _pemilik_guru(penangan)
    if ident is None:
        _tidak_ada(penangan)
        return True
    with database.buka() as kon:
        if toko.lembaga_milik(kon, ident[0]) is None:
            _tidak_ada(penangan)
            return True
        try:
            _batasi_laju(penangan, ident[0])
        except GalatForm as galat:
            _galat_form(penangan, galat)
            return True
        isian = _isian_pindah(_baca_form(penangan))
        if isian is None:
            penangan._tolak_isian()
            return True
        kon.execute("BEGIN IMMEDIATE")
        hasil = toko.pindahkan(kon, oleh=ident[0], siswa_id=isian[0], ke=isian[1])
        if hasil.berhasil:
            kon.commit()
            return _selesai(penangan, "pindah_ok")
        kon.rollback()
    if hasil.status in toko.STATUS_PENOLAKAN_BISNIS:
        return _selesai(penangan, hasil.status)
    _tidak_ada(penangan)
    return True


def _selesai(penangan, kode: str) -> bool:
    _alihkan(penangan, "/lembaga?pesan=" + kode)
    return True

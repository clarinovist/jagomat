"""Rute admin `/admin/lembaga` (daftar) dan aksi buat/tambah/lepas dengan token CSRF."""
from __future__ import annotations

import re
import sqlite3

import admin_http as h
import admin_lembaga_pages as ui
import admin_security
import auth
import database
import lembaga_store as toko

RUTE = "/admin/lembaga"
JUDUL = "Lembaga les"
SUBJUDUL = "Pemilik les, guru anggota, dan batasnya. Tanpa nama anak."
_AKSI = {"/admin/lembaga/buat", "/admin/lembaga/anggota", "/admin/lembaga/lepas",
         "/admin/lembaga/bubarkan"}
_POLA_ID = re.compile(r"[1-9][0-9]{0,17}")


def _nama_guru_aktif() -> tuple:
    """Nama kanonis akun berperan guru dan tidak dinonaktifkan, urut abjad."""
    return tuple(sorted(
        a["pengguna"] for a in auth.muat_akun()
        if a.get("peran", "guru") == "guru" and not a.get("dinonaktifkan")
    ))


def _guru_sah(nama: str) -> str:
    """Nama kanonis akun guru aktif; selain itu ValueError (admin/murid ditolak)."""
    if not isinstance(nama, str) or not nama.strip():
        raise ValueError("guru tidak sah")
    akun = auth.cari_akun(nama)
    if akun is None or akun.get("peran", "guru") != "guru" or akun.get("dinonaktifkan"):
        raise ValueError("guru tidak sah")
    return akun["pengguna"]


def _id_lembaga(nilai: str) -> int:
    if not _POLA_ID.fullmatch(nilai or ""):
        raise ValueError("lembaga tidak sah")
    return int(nilai)


def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        h._query(penangan, diizinkan=set())
        csrf = ""
        if principal.metode == "cookie":
            csrf = h._csrf(h._akun_principal(principal), h._wajib_cookie(penangan, principal))
        with database.buka() as kon:
            lembaga = toko.daftar_lembaga(kon)
            terikat = toko.guru_terikat(kon)
        calon = tuple(g for g in _nama_guru_aktif() if g not in terikat)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    except sqlite3.Error:
        h._galat(penangan, 503, "Layanan admin belum siap.")
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "lembaga", ui.halaman(lembaga, calon, csrf), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL, skrip=True,
    ), skrip=True)
    return True


def _jalankan(jalur: str, data: dict) -> None:
    """Validasi isian lalu tulis dalam satu transaksi; isian asing ditolak."""
    if jalur == "/admin/lembaga/buat":
        if set(data) != {"nama", "pemilik"}:
            raise ValueError("isian tidak sah")
        nama = data["nama"].strip()
        if not 1 <= len(nama) <= ui.BATAS_NAMA:
            raise ValueError("nama lembaga tidak sah")
        pemilik = _guru_sah(data["pemilik"])
        aksi = lambda kon: toko.buat_lembaga(kon, nama=nama, pemilik=pemilik)  # noqa: E731
    elif jalur.endswith("/bubarkan"):
        if set(data) != {"lembaga_id"}:
            raise ValueError("isian tidak sah")
        lembaga_id = _id_lembaga(data["lembaga_id"])
        aksi = lambda kon: toko.bubarkan_lembaga(kon, lembaga_id=lembaga_id)  # noqa: E731
    else:
        if set(data) != {"lembaga_id", "guru"}:
            raise ValueError("isian tidak sah")
        lembaga_id = _id_lembaga(data["lembaga_id"])
        if jalur.endswith("/anggota"):
            guru = _guru_sah(data["guru"])
            aksi = lambda kon: toko.tambah_anggota(kon, lembaga_id=lembaga_id, guru=guru)  # noqa: E731
        else:
            guru = data["guru"]
            aksi = lambda kon: toko.lepas_anggota(kon, lembaga_id=lembaga_id, guru=guru)  # noqa: E731
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        aksi(kon)
        kon.commit()


def tangani_post(penangan, jalur) -> bool:
    if jalur not in _AKSI:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        data = admin_security.baca_form(penangan, maksimum_field=8)
        akun = h._akun_principal(principal)
        if akun is None:
            raise PermissionError("sesi berubah")
        h._cek_csrf(akun, h._wajib_cookie(penangan, principal), data.pop("csrf", None))
        _jalankan(jalur, data)
    except PermissionError:
        h._galat(penangan, 403, "Form kedaluwarsa atau tidak sah.")
    except toko.PenolakanLembaga:
        h._galat(penangan, 409, "Perubahan ditolak: guru sudah terikat pada lembaga, atau data berubah.")
    except ValueError:
        h._galat(penangan, 400, "Isian tidak sah.")
    except sqlite3.Error:
        h._galat(penangan, 503, "Layanan admin belum dapat menyelesaikan tindakan.")
    else:
        h._redirect(penangan, RUTE)
    return True

"""Rute admin `/admin/lembaga` (daftar) dan aksi buat/tambah/lepas/bubarkan.

Semua aksi tulis memakai pola yang sama dengan halaman admin lain (`h._token_final`): CSRF, tinjauan
bertanda tangan per aksi yang terikat sesi, dan sandi admin (`reauth`). Target (id lembaga, guru yang
dilepas) diikat di dalam tinjauan; isian form hanya boleh mengulang nilai itu. Galat sandi/tinjauan/CSRF
ditolak 403 sebelum isian dibaca, jadi tidak ada perubahan data.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Optional

import admin_http as h
import admin_lembaga_pages as ui
import admin_security
import auth
import database
import lembaga_store as toko

RUTE = "/admin/lembaga"
JUDUL = "Lembaga les"
SUBJUDUL = "Pemilik les, guru anggota, dan batasnya. Tanpa nama anak."
AKSI_POST = {
    "/admin/lembaga/buat": ui.AKSI_BUAT,
    "/admin/lembaga/anggota": ui.AKSI_TAMBAH,
    "/admin/lembaga/lepas": ui.AKSI_LEPAS,
    "/admin/lembaga/bubarkan": ui.AKSI_BUBARKAN,
}
_POLA_ID = re.compile(r"[1-9][0-9]{0,17}")


def nama_guru_aktif() -> tuple:
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


class NamaTidakCocok(ValueError):
    """Nama lembaga yang diketik admin tidak sama persis dengan nama tersimpan."""


def _token_form(penangan, principal, lembaga, anak_guru):
    """Token form hanya untuk sesi cookie; selain itu halaman hanya-baca."""
    if principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)

    def tinjauan(aksi, meta=None):
        return admin_security.buat_tinjauan(akun, sesi, aksi, meta or {})

    return ui.TokenLembaga(
        csrf=h._csrf(akun, sesi),
        buat=tinjauan(ui.AKSI_BUAT, {"section": "lembaga"}),
        tambah={int(b["id"]): tinjauan(ui.AKSI_TAMBAH, {"target_id": int(b["id"])})
                for b, _ in lembaga},
        lepas={(int(b["id"]), g): tinjauan(ui.AKSI_LEPAS, {"target_id": int(b["id"]), "akun": g})
               for b, anggota in lembaga for g in anggota},
        anak_guru=anak_guru,
        bubarkan={int(b["id"]): tinjauan(ui.AKSI_BUBARKAN, {"target_id": int(b["id"])})
                  for b, _ in lembaga},
    )


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
            lembaga = toko.daftar_lembaga(kon)
            terikat = toko.guru_terikat(kon)
            anak_guru = {g: toko.jumlah_anak_guru(kon, g) for _, anggota in lembaga for g in anggota}
        calon = tuple(g for g in nama_guru_aktif() if g not in terikat)
        token = _token_form(penangan, principal, lembaga, anak_guru)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    except sqlite3.Error:
        h._galat(penangan, 503, "Layanan admin belum siap.")
        return True
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "lembaga", ui.halaman(lembaga, calon, token), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL, skrip=True,
    ), skrip=True)
    return True


def _cocok_tinjauan(meta: dict, lembaga_id: int, guru: Optional[str] = None) -> None:
    """Isian form harus sama dengan target yang diikat tinjauan bertanda tangan."""
    if meta.get("target_id") != lembaga_id or (guru is not None and meta.get("akun") != guru):
        raise PermissionError("tinjauan tidak cocok dengan target")


def _nama_lembaga(kon, lembaga_id: int) -> Optional[str]:
    """Nama tersimpan lembaga (lewat `daftar_lembaga`; modul store tidak boleh bertambah SQL, sidik kontrak rilis)."""
    return next((b["nama"] for b, _ in toko.daftar_lembaga(kon) if int(b["id"]) == lembaga_id), None)


def _bubarkan(kon, lembaga_id: int, konfirmasi: str) -> None:
    nama = _nama_lembaga(kon, lembaga_id)
    if nama is None:
        raise toko.PenolakanLembaga("lembaga tidak ada")
    if konfirmasi != nama:
        raise NamaTidakCocok("nama lembaga tidak cocok")
    toko.bubarkan_lembaga(kon, lembaga_id=lembaga_id)


def _siapkan(jalur: str, meta: dict, data: dict, oleh: str):
    """Validasi isian dan target tinjauan; kembalikan `aksi(kon)` yang menulis. Isian asing ditolak.

    ``oleh`` = nama admin yang beraksi (dicatat di jejak pindah saat lepas anggota).
    """
    if jalur == "/admin/lembaga/buat":
        if set(data) != {"nama", "pemilik"}:
            raise ValueError("isian tidak sah")
        nama = data["nama"].strip()
        if not 1 <= len(nama) <= ui.BATAS_NAMA:
            raise ValueError("nama lembaga tidak sah")
        pemilik = _guru_sah(data["pemilik"])
        return lambda kon: toko.buat_lembaga(kon, nama=nama, pemilik=pemilik)
    if jalur.endswith("/bubarkan"):
        if set(data) != {"lembaga_id", "konfirmasi_nama"}:
            raise ValueError("isian tidak sah")
        lembaga_id = _id_lembaga(data["lembaga_id"])
        _cocok_tinjauan(meta, lembaga_id)
        return lambda kon: _bubarkan(kon, lembaga_id, data["konfirmasi_nama"])
    if set(data) != {"lembaga_id", "guru"}:
        raise ValueError("isian tidak sah")
    lembaga_id = _id_lembaga(data["lembaga_id"])
    if jalur.endswith("/anggota"):
        _cocok_tinjauan(meta, lembaga_id)
        guru = _guru_sah(data["guru"])
        return lambda kon: toko.tambah_anggota(kon, lembaga_id=lembaga_id, guru=guru)
    _cocok_tinjauan(meta, lembaga_id, data["guru"])
    return lambda kon: toko.lepas_anggota(
        kon, lembaga_id=lembaga_id, guru=data["guru"], oleh=oleh)


def _jalankan(jalur: str, meta: dict, data: dict, oleh: str) -> None:
    """Validasi lalu tulis dalam satu transaksi; penolakan tidak menulis apa pun."""
    aksi = _siapkan(jalur, meta, data, oleh)
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        aksi(kon)
        kon.commit()


def tangani_post(penangan, jalur) -> bool:
    aksi = AKSI_POST.get(jalur)
    if aksi is None:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        data = admin_security.baca_form(penangan, maksimum_field=8)
        akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)
        _jalankan(jalur, tinjauan["data"], data, akun["pengguna"])
    except PermissionError:
        h._galat(penangan, 403, "Form kedaluwarsa atau autentikasi ulang tidak sah.")
    except toko.PenolakanSesiBerjalan:
        h._galat(penangan, 409, ui.COPY_LEPAS_SESI_BERJALAN)
    except toko.PenolakanNamaAnak:
        h._galat(penangan, 409, ui.COPY_LEPAS_NAMA_HABIS)
    except toko.PenolakanLembaga:
        h._galat(penangan, 409, "Perubahan ditolak: lembaga atau guru sudah berubah (mis. lembaga sudah dibubarkan atau guru sudah terikat di lembaga lain). Muat ulang halaman, lalu coba lagi.")
    except NamaTidakCocok:
        h._galat(penangan, 400, ui.COPY_NAMA_TIDAK_COCOK)
    except ValueError:
        h._galat(penangan, 400, "Isian tidak sah.")
    except sqlite3.Error:
        h._galat(penangan, 503, "Layanan admin belum dapat menyelesaikan tindakan.")
    else:
        h._redirect(penangan, RUTE)
    return True

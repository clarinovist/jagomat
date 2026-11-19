"""Rute admin `/admin/profil-guru`: daftar + tambah/ubah/hapus profil guru peninjau.

Pola mengikuti `atur_dukungan`: CSRF, tinjauan bertanda tangan, reauth sandi,
revisi/sidik optimistic lock. Non-admin menerima 404 identik. Penyimpanan belum
disiapkan -> halaman menjelaskan dan semua POST ditolak tanpa menulis.
"""
from __future__ import annotations

import sqlite3
import time

import admin_http as h
import admin_profil_guru_pages as ui
import admin_security
import admin_store
import auth
import profil_guru_settings as pg

RUTE = "/admin/profil-guru"
JUDUL = "Profil guru peninjau"
SUBJUDUL = "Nama, latar pendidikan, dan lama mengajar guru yang tampil di halaman publik."
AKSI_POST = {
    ui.AKSI_TAMBAH: "tambah_profil_guru",
    ui.AKSI_UBAH: "ubah_profil_guru",
    ui.AKSI_HAPUS: "hapus_profil_guru",
}
FEEDBACK = {
    "tersimpan": "Profil guru tersimpan. Baris yang bertanda tampil langsung dipakai halaman publik.",
    "dihapus": "Profil guru dihapus dari daftar dan dari halaman publik.",
}
_ISIAN_WAJIB = frozenset(("nama", "latar", "lama_mengajar", "urutan"))
_ISIAN_BOLEH = _ISIAN_WAJIB | {"tampil"}


def _token_form(penangan, principal, profil):
    """Token form hanya untuk sesi cookie dan penyimpanan siap; selain itu halaman hanya-baca."""
    if profil is None or principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)

    def tinjauan(aksi, meta=None):
        return admin_security.buat_tinjauan(akun, sesi, AKSI_POST[aksi], meta or {})

    def meta(p):
        return {"target_id": p.id, "revisi": p.revisi, "sidik": pg.sidik_profil(p)}

    return ui.TokenForm(
        h._csrf(akun, sesi), tinjauan(ui.AKSI_TAMBAH),
        {p.id: tinjauan(ui.AKSI_UBAH, meta(p)) for p in profil},
        {p.id: tinjauan(ui.AKSI_HAPUS, meta(p)) for p in profil},
    )



def tangani_get(penangan, jalur) -> bool:
    if jalur != RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        kueri = h._query(penangan, diizinkan={"status"})
        profil = pg.baca(h._path_admin())
        token = _token_form(penangan, principal, profil)
    except ValueError:
        h._tidak_ada(penangan)
        return True
    isi = ui.halaman(profil, token, FEEDBACK.get(kueri.get("status", ""), ""))
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "profil_guru", isi, penangan=penangan, judul=JUDUL, subjudul=SUBJUDUL, skrip=True,
    ), skrip=True)
    return True


def _urutan(teks: str) -> int:
    if not teks.isascii() or not teks.isdigit():
        raise pg.ProfilTidakSah("Urutan harus bilangan bulat %d sampai %d." % (pg.URUTAN_MIN, pg.URUTAN_MAKS))
    return int(teks)


def _isian_form(data: dict) -> dict:
    """Allowlist isian tambah/ubah; kunci asing atau checkbox bernilai aneh ditolak."""
    if set(data) - _ISIAN_BOLEH or not _ISIAN_WAJIB <= set(data) or data.get("tampil", "1") != "1":
        raise ValueError("isian asing")
    return dict(
        nama=data["nama"], latar=data["latar"], lama_mengajar=data["lama_mengajar"],
        urutan=_urutan(data["urutan"]), tampil="tampil" in data,
    )


def _snapshot(meta: dict) -> dict:
    profil_id, revisi, sidik = meta.get("target_id"), meta.get("revisi"), meta.get("sidik")
    if type(profil_id) is not int or type(revisi) is not int or type(sidik) is not str:
        raise ValueError("snapshot profil guru tidak sah")
    return dict(profil_id=profil_id, revisi=revisi, sidik_awal=sidik)


def _jalankan(aksi: str, principal, tinjauan: dict, data: dict) -> str:
    """Panggil domain sesuai aksi; mengembalikan kode feedback untuk redirect."""
    umum = dict(operasi=tinjauan["op"], sekarang=int(time.time()))
    path = h._path_admin()
    if aksi == "hapus_profil_guru":
        if data:
            raise ValueError("isian asing")
        pg.hapus(path, auth.BERKAS_SANDI, principal, **umum, **_snapshot(tinjauan["data"]))
        return "dihapus"
    isian = _isian_form(data)
    if aksi == "tambah_profil_guru":
        pg.tambah(path, auth.BERKAS_SANDI, principal, **umum, **isian)
    else:
        pg.ubah(path, auth.BERKAS_SANDI, principal, **umum, **_snapshot(tinjauan["data"]), **isian)
    return "tersimpan"


def tangani_post(penangan, jalur) -> bool:
    aksi = AKSI_POST.get(jalur)
    if aksi is None:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    try:
        if pg.baca(h._path_admin()) is None:
            raise admin_store.StoreBelumSiap("profil guru belum siap")
        data = admin_security.baca_form(penangan, maksimum_field=12)
        _akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)
        status = _jalankan(aksi, principal, tinjauan, data)
    except LookupError:
        h._tidak_ada(penangan)
    except PermissionError:
        h._galat(penangan, 403, "Form kedaluwarsa atau autentikasi ulang tidak sah.")
    except admin_store.KonflikOperasi:
        h._galat(penangan, 409, "Data berubah. Buka ulang halaman profil guru sebelum mencoba lagi.")
    except admin_store.StoreBelumSiap:
        h._galat(penangan, 503, ui.PESAN_BELUM_SIAP)
    except pg.ProfilTidakSah as galat:
        h._galat(penangan, 400, str(galat))
    except (ValueError, KeyError, TypeError):
        h._galat(penangan, 400, "Isian profil guru tidak sah.")
    except (RuntimeError, sqlite3.Error, OSError):
        h._galat(penangan, 503, "Layanan admin belum dapat menyelesaikan tindakan.")
    else:
        h._redirect(penangan, "%s?status=%s" % (RUTE, status))
    return True

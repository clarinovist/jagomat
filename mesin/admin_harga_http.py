"""Rute admin Harga (/admin/harga): GET tampilan dan POST ubah harga Private dan Mini Class.

Non-admin = 404 identik rute tak dikenal sebelum DB dibaca. POST memakai pola uang admin
(`aksi.terima_form` -> `h._token_final`: CSRF, tinjauan terikat aksi dan sesi, sandi ulang). Produk hanya dari
tinjauan (field `kode` di form harus sama). Nilai harga di-parse ketat, divalidasi di handler, lalu
`harga.ubah_harga` memvalidasi ulang di dalam transaksi (harga lama berbeda = 409). Sukses = PRG ke
`/admin/harga?hasil=tersimpan`. Skema belum dipasang = 409, rusak = 503, tanpa path atau detail internal.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Mapping, Optional, Tuple

import admin_harga_baca as baca
import admin_harga_pages as ui
import admin_http as h
import admin_pesanan_aksi as aksi
import admin_security
import admin_store
import harga
import harga_aturan as a
import harga_validasi as hv
import schema_harga

SECTION = "operasional"  # butir Pengaturan layanan: halaman ini menyorot menu induk, tanpa butir menu baru
FORM_HARGA = frozenset({ui.FIELD_KODE, ui.FIELD_HARGA})
FORM_HARGA_KONFIRMASI = FORM_HARGA | {ui.FIELD_KONFIRMASI}
BATAS_RASIO = 2  # harga baru di luar [lama / 2, lama * 2] butuh konfirmasi eksplisit (jaga salah ketik)
POLA_HARGA = re.compile(ui.pola_isian_harga())
KUNCI_QUERY = frozenset({"hasil"})
Token = Tuple[str, str]


class _PesanTolak(ValueError):
    """Isian atau perintah ditolak; pesannya berbahasa Indonesia dan di-escape saat ditampilkan."""


class _BelumDipasang(Exception):
    """Skema harga_* belum dipasang: 409, tidak ada yang ditulis."""


class _SkemaRusak(Exception):
    """Skema harga_* ada tetapi rusak: 503 tanpa detail."""


def _sekarang() -> str:
    return datetime.now(timezone.utc).strftime(harga.FORMAT_WAKTU)


def _principal_pengelola(penangan):
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
    return principal


def _kirim_halaman(penangan, principal, isi: str, kode: int = 200) -> None:
    h._kirim_privat(
        penangan,
        h._halaman_admin(principal, SECTION, isi, penangan=penangan, skrip=True,
                         judul=ui.JUDUL, subjudul=ui.SUBJUDUL),
        kode, skrip=True)


def _hasil_query(penangan) -> Optional[str]:
    query = h._query(penangan, diizinkan=KUNCI_QUERY)
    if "hasil" not in query:
        return None
    if query["hasil"] not in ui.KODE_HASIL:
        raise ValueError("hasil tidak sah")
    return query["hasil"]


def _tinjauan(akun, sesi, baris: baca.BarisProduk) -> str:
    # target_revisi membawa harga lama yang ditampilkan (optimistic concurrency), bukan revisi baris.
    return admin_security.buat_tinjauan(
        akun, sesi, ui.AKSI_UBAH, {"target_id": baris.kode, "target_revisi": baris.rupiah})


def _tokens(penangan, principal, tampilan: baca.Tampilan) -> Optional[Mapping[str, Token]]:
    if not tampilan.terpasang or principal.metode != "cookie":
        return None
    akun = h._akun_principal(principal)
    sesi = h._wajib_cookie(penangan, principal)
    csrf = h._csrf(akun, sesi)
    return {b.kode: (csrf, _tinjauan(akun, sesi, b)) for b in tampilan.produk if b.bisa_diubah}


def _get(penangan, principal) -> None:
    try:
        hasil = _hasil_query(penangan)
    except ValueError:
        h._tidak_ada(penangan)
        return
    try:
        tampilan = baca.muat(h._path_admin())
        tokens = _tokens(penangan, principal, tampilan)
    except PermissionError:
        h._galat(penangan, 403, ui.COPY_TANPA_SESI)
        return
    except ValueError:
        _kirim_halaman(penangan, principal, ui.galat_skema_rusak(), 503)
        return
    except (admin_store.StoreBelumSiap, sqlite3.Error, OSError):
        _kirim_halaman(penangan, principal, ui.galat_layanan(), 503)
        return
    _kirim_halaman(penangan, principal, ui.halaman(tampilan, tokens, hasil))


def tangani_get(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = _principal_pengelola(penangan)
    if principal is not None:
        _get(penangan, principal)
    return True


def parse_rupiah(teks) -> int:
    """Digit ASCII saja, tanpa spasi, tanda, desimal, pemisah, atau notasi; batas panjang dari harga_aturan."""
    if type(teks) is not str or POLA_HARGA.fullmatch(teks) is None:
        raise _PesanTolak(ui.COPY_FORMAT)
    return int(teks)


def _perintah(tinjauan, data) -> Tuple[str, int]:
    """(kode, harga lama) dari tinjauan bertanda tangan; field kode di form hanya boleh menyamai tinjauan."""
    meta = tinjauan["data"]
    kode, lama = meta.get("target_id"), meta.get("target_revisi")
    if kode not in a.ALLOW_UBAH or type(lama) is not int:
        raise _PesanTolak("Perintah ubah harga tidak sah. Tidak ada yang diubah.")
    if data.get(ui.FIELD_KODE) != kode:
        raise _PesanTolak("Produk tidak cocok dengan tinjauan. Tidak ada yang diubah.")
    return kode, lama


def _harga_untuk_ubah(path) -> Mapping[str, int]:
    """Harga aktif semua produk; skema belum dipasang = _BelumDipasang, rusak = _SkemaRusak (tanpa detail)."""
    try:
        with admin_store.buka_baca(path) as kon:
            if not schema_harga.validasi(kon):
                raise _BelumDipasang()
            return harga.harga_semua(kon)
    except ValueError:
        raise _SkemaRusak() from None


def _periksa_selisih(data, rupiah: int, lama: int) -> None:
    """Selisih besar (lebih dari BATAS_RASIO kali atau kurang dari 1/BATAS_RASIO) butuh konfirmasi persis "ya"."""
    konfirmasi = data.get(ui.FIELD_KONFIRMASI)
    if konfirmasi is not None and konfirmasi != ui.NILAI_KONFIRMASI:
        raise _PesanTolak(ui.COPY_ISIAN)
    besar = rupiah * BATAS_RASIO < lama or rupiah > lama * BATAS_RASIO
    if besar and konfirmasi is None:
        raise _PesanTolak(ui.COPY_SELISIH_BESAR)


def _validasi_pra(kode: str, rupiah: int, lama: int, aktif: Mapping[str, int]) -> None:
    # Harga sama dengan yang aktif ditolak hanya bila halaman tidak basi; yang basi lewat ke cek konflik (409).
    if rupiah == lama == aktif[kode]:
        raise _PesanTolak(ui.COPY_HARGA_SAMA)
    lain = {p: v for p, v in aktif.items() if p != kode}
    try:
        hv.validasi_harga(kode, rupiah, lain)
    except ValueError as galat:
        raise _PesanTolak(str(galat)) from None


def _ubah(principal, kode: str, rupiah: int, lama: int) -> None:
    try:
        harga.ubah_harga(h._path_admin(), kode, rupiah, lama, principal.id_akun, _sekarang())
    except harga.KonflikHarga:
        raise admin_store.KonflikOperasi("harga aktif berubah") from None
    except harga.HargaBelumTerpasang:
        raise _BelumDipasang() from None
    except ValueError as galat:
        raise _PesanTolak(str(galat)) from None


def _simpan(penangan, principal) -> None:
    tinjauan, data = aksi.terima_form(penangan, principal, ui.AKSI_UBAH)
    aksi.wajib_field(data, FORM_HARGA_KONFIRMASI if ui.FIELD_KONFIRMASI in data else FORM_HARGA)
    kode, lama = _perintah(tinjauan, data)
    rupiah = parse_rupiah(data[ui.FIELD_HARGA])
    aktif = _harga_untuk_ubah(h._path_admin())
    _periksa_selisih(data, rupiah, lama)
    _validasi_pra(kode, rupiah, lama, aktif)
    _ubah(principal, kode, rupiah, lama)
    h._redirect(penangan, "%s?hasil=%s" % (ui.RUTE, ui.HASIL_TERSIMPAN))


def _jalankan(penangan, principal) -> None:
    try:
        _simpan(penangan, principal)
    except _PesanTolak as galat:
        _kirim_halaman(penangan, principal, ui.galat_isian(str(galat)), 400)
    except _BelumDipasang:
        _kirim_halaman(penangan, principal, ui.galat_belum_dipasang(), 409)
    except _SkemaRusak:
        _kirim_halaman(penangan, principal, ui.galat_skema_rusak(), 503)


def tangani_post(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = _principal_pengelola(penangan)
    if principal is not None:
        aksi.jalankan_aman(penangan, lambda: _jalankan(penangan, principal),
                           copy_konflik=ui.COPY_KONFLIK, copy_isian=ui.COPY_ISIAN, copy_layanan=ui.COPY_LAYANAN)
    return True

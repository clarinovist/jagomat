"""Rute guru baca-saja `/guru/jadwal`, `/guru/kelas`, dan `/guru/kelas/<klp_id>` (Jadwal dan Kelas saya, Fase 1).

Identitas HANYA dari sesi: `guru_id` = `id_akun` principal yang berperan guru. Tidak ada id dari URL, kueri, atau form.
Selain guru pemilik (admin, murid, anonim, mode lokal tanpa principal) jawaban 404 yang byte-identik dengan rute tak
dikenal (`lembaga_http._tidak_ada`). Galat baca DB admin: daftar kosong; detail 404. Nama anak dibaca dari latihan.db
mode ro; galat baca memakai placeholder. Tanpa tulis dan tanpa pembuatan berkas.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Set, Tuple

import admin_store
import admin_store_core
import database
import guru_jadwal_baca as baca
import guru_jadwal_pages as halaman
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as catatan
import jadwal_store as js
import kelas_dasar as dasar
import lembaga_http
import pesanan_alur as alur

_log = logging.getLogger(__name__)

RUTE_JADWAL = "/guru/jadwal"
RUTE_KELAS = "/guru/kelas"
PREFIX_KELAS = RUTE_KELAS + "/"
_GALAT_BACA = (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError)
_GALAT_CATATAN = (catatan.GalatCatatan, OSError, sqlite3.Error)


def _principal_guru(penangan):
    """Principal sesi bila berperan guru; None untuk admin, murid, anonim, dan mode lokal."""
    principal = penangan._principal()
    if principal is None or principal.peran != "guru":
        return None
    return principal


def _ident(principal) -> tuple:
    return principal.pengguna, principal.peran


def _kini() -> str:
    return dasar.ke_baku(alur.waktu_sekarang())


def _baca_admin(fungsi, bawaan):
    """Jalankan `fungsi(kon)` pada DB admin (ro). Galat baca -> `bawaan` (daftar kosong, atau None untuk detail)."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            return fungsi(kon)
    except _GALAT_BACA as galat:
        _log.warning("jadwal guru tidak terbaca: %s", type(galat).__name__)
        return bawaan


@contextmanager
def _buka_belajar_baca():
    """latihan.db dibuka mode ro: tidak pernah membuat berkas atau menulis."""
    uri = Path(database.BAWAAN).resolve().as_uri() + "?mode=ro"
    kon = sqlite3.connect(uri, uri=True)
    try:
        yield kon
    finally:
        kon.close()


def _nama_anak(ids) -> dict:
    """Nama anak untuk id hasil kueri milik guru saja. Galat baca latihan.db -> placeholder untuk semua id."""
    unik = sorted(set(ids))
    if not unik:
        return {}
    try:
        with _buka_belajar_baca() as kon:
            return baca.nama_siswa(kon, unik)
    except (sqlite3.Error, ValueError) as galat:
        _log.warning("nama anak tidak terbaca: %s", type(galat).__name__)
        return {siswa_id: baca.PLACEHOLDER_NAMA for siswa_id in unik}


def _judul(pertemuan: dict, nama: dict) -> str:
    if pertemuan["jenis"] == "kelompok":
        return "Mini Class: " + (pertemuan["nama_kelompok"] or "")
    return "Private: " + nama.get(pertemuan["siswa_id"], baca.PLACEHOLDER_NAMA)


def _tampilan_pertemuan(pertemuan: dict, nama: dict) -> dict:
    """View-model tanpa siswa_id/order_id: hanya teks dan `kelas_id` (kelompok milik guru, untuk href)."""
    return {"judul": _judul(pertemuan, nama), "ke": pertemuan["ke"], "mulai": pertemuan["mulai"],
            "dibatalkan": pertemuan["dibatalkan"], "kelas_id": pertemuan["kelompok_id"]}


def _sudah_dicatat(pasangan: List[Tuple[str, str]]) -> Set[Tuple[str, str]]:
    """Pasangan (kunci, mulai) yang sudah punya jurnal. Galat baca = belum ada catatan; log hanya memuat tipe galat."""
    if not pasangan:
        return set()
    try:
        return catatan.punya_jurnal(pasangan)
    except _GALAT_CATATAN as galat:
        _log.warning("catatan pertemuan tidak terbaca: %s", type(galat).__name__)
        return set()


def _tampilan_berlangsung(pertemuan: dict, nama: dict, sudah: Set[Tuple[str, str]]) -> dict:
    """View-model 'Sudah berlangsung': tanpa siswa_id, order_id, dan kunci."""
    return {"judul": _judul(pertemuan, nama), "ke": pertemuan["ke"], "mulai": pertemuan["mulai"],
            "tercatat": (pertemuan["kunci"], pertemuan["mulai"]) in sudah, "id_pertemuan": pertemuan["id"]}


def _halaman_jadwal(penangan, principal) -> None:
    kini = _kini()
    pertemuan = _baca_admin(lambda kon: baca.pertemuan_mendatang(kon, principal.id_akun, kini), [])
    berlangsung = _baca_admin(lambda kon: baca.pertemuan_dalam_jendela(kon, principal.id_akun, kini), [])
    nama = _nama_anak(p["siswa_id"] for p in pertemuan + berlangsung if p["siswa_id"] is not None)
    sudah = _sudah_dicatat([(p["kunci"], p["mulai"]) for p in berlangsung])
    tampilan = [_tampilan_pertemuan(p, nama) for p in pertemuan]
    tampilan_berlangsung = [_tampilan_berlangsung(p, nama, sudah) for p in berlangsung]
    penangan._kirim_privat(halaman.halaman_jadwal(_ident(principal), tampilan, tampilan_berlangsung))


def _halaman_kelas(penangan, principal) -> None:
    kini = _kini()
    kelas = _baca_admin(lambda kon: baca.daftar_kelas(kon, principal.id_akun, kini), [])
    penangan._kirim_privat(halaman.halaman_kelas(_ident(principal), kelas))


def _tampilan_anggota(anggota: list, nama: dict) -> list:
    """Anggota untuk view-model: `nama` dan `akses_habis` saja (tanpa siswa_id), terurut nama tanpa membedakan huruf."""
    daftar = [{"nama": nama.get(a["siswa_id"], baca.PLACEHOLDER_NAMA), "akses_habis": a["akses_habis"]}
              for a in anggota]
    return sorted(daftar, key=lambda anak: anak["nama"].casefold())


def _halaman_detail(penangan, principal, kelompok_id: str) -> None:
    kini = _kini()
    detail = _baca_admin(lambda kon: baca.detail_kelas(kon, principal.id_akun, kelompok_id, kini), None)
    if detail is None:
        lembaga_http._tidak_ada(penangan)
        return
    nama = _nama_anak(a["siswa_id"] for a in detail["anggota"])
    tampilan = {
        "nama": detail["nama"],
        "lokasi": detail["lokasi"],
        "kuota": detail["kuota"],
        "terisi": len(detail["anggota"]),
        "sesi": _sesi_tampilan(detail["sesi"], kini),
        "anggota": _tampilan_anggota(detail["anggota"], nama),
    }
    penangan._kirim_privat(halaman.halaman_detail(_ident(principal), tampilan))


def _boleh_isi(sesi: dict, kini: str) -> bool:
    """Sesi boleh dicatat bila masih dalam jendela (R1/R2) dan punya >= 1 anggota (R4), sama dengan form pertemuan."""
    jendela = aturan.boleh_catat(sesi["mulai"], sesi["menit"], sesi["dibatalkan"], kini) is None
    return jendela and sesi["anggota_n"] > 0


def _sesi_view(sesi: dict, boleh: bool, sudah: Set[Tuple[str, str]]) -> dict:
    aksi = None
    if boleh:
        aksi = {"id_pertemuan": sesi["id"], "tercatat": (sesi["kunci"], sesi["mulai"]) in sudah}
    return {"ke": sesi["ke"], "mulai": sesi["mulai"], "menit": sesi["menit"],
            "dibatalkan": sesi["dibatalkan"], "aksi": aksi}


def _sesi_tampilan(sesi: List[dict], kini: str) -> List[dict]:
    """View-model sesi: `aksi` None bila tak boleh dicatat, atau {id_pertemuan, tercatat}; tanpa kunci."""
    bisa = [_boleh_isi(s, kini) for s in sesi]
    sudah = _sudah_dicatat([(s["kunci"], s["mulai"]) for s, boleh in zip(sesi, bisa) if boleh])
    return [_sesi_view(s, boleh, sudah) for s, boleh in zip(sesi, bisa)]


def tangani_get(penangan, jalur: str) -> bool:
    """Dipanggil setelah palang sandi guru/admin. False hanya untuk jalur di luar keluarga `/guru/jadwal|kelas`."""
    if jalur != RUTE_JADWAL and jalur != RUTE_KELAS and not jalur.startswith(PREFIX_KELAS):
        return False
    principal = _principal_guru(penangan)
    if principal is None:
        lembaga_http._tidak_ada(penangan)
        return True
    if jalur == RUTE_JADWAL:
        _halaman_jadwal(penangan, principal)
    elif jalur == RUTE_KELAS:
        _halaman_kelas(penangan, principal)
    else:
        _halaman_detail(penangan, principal, jalur[len(PREFIX_KELAS):])
    return True

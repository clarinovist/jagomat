"""Rute admin jadwal Private: buat/batalkan slot, setujui/tolak pengajuan orang tua.

Dijawab `admin_http` sebelum palang guru; anonim dan guru menerima 404 yang sama sebelum data dibaca. Tidak bergantung
pada sakelar PAKET_BELAJAR (sama seperti `jadwal_admin_http`). Aksi memakai CSRF + tinjauan bertanda tangan tanpa sandi
ulang: `admin_id` dari principal sesi, id slot/pengajuan dari TINJAUAN (kunci `target_id`), dan field `id` di form harus
sama persis. Sukses = PRG 303 ke /admin/kelas/private. Galat domain dipetakan ke pesan tetap lewat `aksi.jalankan_aman`;
berkas private yang rusak menjadi 503. Tanpa data di respons.
"""
from __future__ import annotations

import logging
import sqlite3

import admin_http as h
import admin_pesanan_aksi as aksi
import admin_pesanan_pages as daftar_ui
import admin_store
import guru_jadwal_tetap_peringatan as tetap
import jadwal_admin_http as jah
import jadwal_private as jp
import jadwal_private_admin_pages as ui
import jadwal_private_dasar as dsr
import jadwal_private_pola as jpp
import jadwal_private_pola_setujui as jpps
import jadwal_store as js
import kelas_dasar as kd
import pesanan_alur as alur

_log = logging.getLogger(__name__)

SECTION = "kelas_belajar"
AKSI_SLOT_BUAT = "jadwal_private_slot_buat"
AKSI_SLOT_BATAL = "jadwal_private_slot_batal"
AKSI_SETUJUI = "jadwal_private_setujui"
AKSI_TOLAK = "jadwal_private_tolak"
AKSI_POLA_SETUJUI = "jadwal_private_pola_setujui"
AKSI_POLA_TOLAK = "jadwal_private_pola_tolak"
KUNCI_TINJAUAN_ID = "target_id"
FIELD_ID = "id"
FORM_BUAT = frozenset({"guru_id", "tanggal", "jam"})
FORM_ID = frozenset({FIELD_ID})
FORM_POLA_SETUJUI = frozenset({FIELD_ID, "guru_id", "tanggal"})
COPY_KONFLIK_BUAT = ("Slot tidak bisa dibuat: guru dan waktu mulai yang sama sudah ada. "
                     "Tidak ada yang diubah.")
COPY_KONFLIK_BATAL = ("Slot tidak bisa dibatalkan: masih ada pengajuan orang tua. Tolak pengajuannya dulu. "
                      "Tidak ada yang diubah.")
COPY_KONFLIK_SETUJUI = ("Pengajuan tidak bisa disetujui: sudah basi (waktu mulai lewat, slot dibatalkan, guru tidak "
                        "aktif, paket sudah berjadwal, atau slot sudah terisi) atau sudah diputuskan. "
                        "Pengajuan sudah basi: gunakan Tolak. Tidak ada yang diubah.")
COPY_KONFLIK_TOLAK = "Pengajuan sudah diputuskan sebelumnya. Muat ulang halaman. Tidak ada yang diubah."
COPY_KONFLIK_POLA_SETUJUI = ("Pola tidak bisa disetujui: sudah diputuskan, paket sudah berjadwal, masa akses tidak "
                             "cukup, atau pertemuan pertama kurang dari 24 jam lagi. Tidak ada yang diubah.")
COPY_KONFLIK_POLA_TOLAK = "Pola sudah diputuskan sebelumnya. Muat ulang halaman. Tidak ada yang diubah."
COPY_ISIAN = ("Isian jadwal private tidak sah: periksa guru, tanggal, dan jam (waktu mulai tidak boleh sudah lewat). "
              "Tidak ada yang diubah.")
COPY_LAYANAN = "Jadwal private belum siap di server. Coba lagi beberapa saat; tidak ada yang diubah."
_GALAT_LAYANAN = (admin_store.StoreBelumSiap, dsr.GalatJadwalPrivate, sqlite3.Error, OSError)


def _buka(*, tulis: bool = False):
    return js.buka(h._path_admin(), tulis_data=tulis)


def _guru_sah() -> frozenset:
    return frozenset(jah.guru_map())


def _target(tinjauan, data) -> int:
    """Id target dari tinjauan bertanda tangan; field `id` form harus sama persis (selain itu ValueError = 400)."""
    pid = dsr.periksa_id(tinjauan["data"].get(KUNCI_TINJAUAN_ID), "target")
    if data[FIELD_ID] != str(pid):
        raise ValueError("id tidak cocok dengan tinjauan")
    return pid


def _kirim(penangan, principal, isi: str, kode: int = 200) -> None:
    h._kirim_privat(penangan, h._halaman_admin(
        principal, SECTION, isi, penangan=penangan, skrip=True, judul=ui.JUDUL, subjudul=ui.SUBJUDUL),
        kode, skrip=True)


def _token(penangan, principal, slot, antrean, pola) -> dict:
    def bentuk(aksi_nama: str, isi: dict):
        return jah.bentuk_token(penangan, principal, aksi_nama, isi)

    return {
        "buat": bentuk(AKSI_SLOT_BUAT, {"section": SECTION}),
        "batal": {s.slot_id: bentuk(AKSI_SLOT_BATAL, {KUNCI_TINJAUAN_ID: s.slot_id})
                  for s in slot if s.status in ui.STATUS_BISA_BATAL},
        "setujui": {e.pengajuan_id: bentuk(AKSI_SETUJUI, {KUNCI_TINJAUAN_ID: e.pengajuan_id}) for e in antrean},
        "tolak": {e.pengajuan_id: bentuk(AKSI_TOLAK, {KUNCI_TINJAUAN_ID: e.pengajuan_id}) for e in antrean},
        "pola_setujui": {e.pola.id: bentuk(AKSI_POLA_SETUJUI, {KUNCI_TINJAUAN_ID: e.pola.id}) for e in pola},
        "pola_tolak": {e.pola.id: bentuk(AKSI_POLA_TOLAK, {KUNCI_TINJAUAN_ID: e.pola.id}) for e in pola},
    }


def _halaman(penangan, principal) -> str:
    guru = jah.guru_map()
    sah = frozenset(guru)
    sekarang = alur.waktu_sekarang()
    with _buka() as kon:
        slot = jp.daftar_slot_admin(kon, sekarang, sah)
        antrean = jp.antrean_admin(kon, sekarang, sah)
    pola = jpp.antrean_admin(kd.ke_baku(sekarang))
    return ui.halaman(slot, antrean, guru, _token(penangan, principal, slot, antrean, pola),
                      luar_jam=_slot_luar_jam(slot), pola=pola)


def _slot_luar_jam(slot) -> frozenset:
    """Id slot aktif (tidak dibatalkan) yang punya pertemuan di luar jam tetap guru.

    Jadwal tetap tiap guru dibaca sekali per permintaan.
    """
    blok_per_guru = {guru: tetap.blok_aktif(guru) for guru in {s.guru_id for s in slot}}
    return frozenset(s.slot_id for s in slot
                     if s.status != ui.STATUS_DIBATALKAN
                     and tetap.slot_luar_jam_dengan_blok(blok_per_guru[s.guru_id], s.mulai))


# --- GET ------------------------------------------------------------------------------------

def _get(penangan, principal) -> None:
    if principal.metode != "cookie":
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    try:
        h._query(penangan, diizinkan=frozenset())
    except ValueError:
        return h._tidak_ada(penangan)
    try:
        isi = _halaman(penangan, principal)
    except PermissionError:
        return h._galat(penangan, 403, daftar_ui.COPY_GALAT_FORM)
    except _GALAT_LAYANAN:
        return _kirim(penangan, principal, daftar_ui.halaman_tidak_siap(), 503)
    _kirim(penangan, principal, isi)


# --- POST -----------------------------------------------------------------------------------

def _buat_slot(penangan, principal) -> None:
    _tinjauan, data = jah._terima(penangan, principal, AKSI_SLOT_BUAT)
    aksi.wajib_field(data, FORM_BUAT)
    jp.buat_slot(principal.id_akun, data["guru_id"], data["tanggal"], data["jam"],
                 alur.waktu_sekarang(), _guru_sah())
    h._redirect(penangan, ui.RUTE)


def _batal_slot(penangan, principal) -> None:
    tinjauan, data = jah._terima(penangan, principal, AKSI_SLOT_BATAL)
    aksi.wajib_field(data, FORM_ID)
    sid = _target(tinjauan, data)
    with _buka() as kon:
        jp.batalkan_slot(kon, principal.id_akun, sid, alur.waktu_sekarang(), _guru_sah())
    h._redirect(penangan, ui.RUTE)


def _setujui(penangan, principal) -> None:
    tinjauan, data = jah._terima(penangan, principal, AKSI_SETUJUI)
    aksi.wajib_field(data, FORM_ID)
    pid = _target(tinjauan, data)
    with _buka(tulis=True) as kon:
        jp.setujui(kon, principal.id_akun, pid, alur.waktu_sekarang(), _guru_sah())
    h._redirect(penangan, ui.RUTE)


def _tolak(penangan, principal) -> None:
    tinjauan, data = jah._terima(penangan, principal, AKSI_TOLAK)
    aksi.wajib_field(data, FORM_ID)
    pid = _target(tinjauan, data)
    jp.tolak(principal.id_akun, pid, alur.waktu_sekarang())
    h._redirect(penangan, ui.RUTE)


def _setujui_pola(penangan, principal) -> None:
    """Pola disetujui: guru dan tanggal mulai dari form (diperiksa domain), id dari tinjauan."""
    tinjauan, data = jah._terima(penangan, principal, AKSI_POLA_SETUJUI)
    aksi.wajib_field(data, FORM_POLA_SETUJUI)
    pid = _target(tinjauan, data)
    with _buka(tulis=True) as kon:
        jpps.setujui(kon, principal.id_akun, pid, data["guru_id"], data["tanggal"], alur.waktu_sekarang(),
                     _guru_sah())
    h._redirect(penangan, ui.RUTE)


def _tolak_pola(penangan, principal) -> None:
    tinjauan, data = jah._terima(penangan, principal, AKSI_POLA_TOLAK)
    aksi.wajib_field(data, FORM_ID)
    pid = _target(tinjauan, data)
    jpp.tolak(principal.id_akun, pid, alur.waktu_sekarang())
    h._redirect(penangan, ui.RUTE)


def _dengan_galat_layanan(fungsi) -> None:
    """Berkas private rusak / skema tak dikenal menjadi galat layanan (503), dicatat hanya nama tipenya."""
    try:
        fungsi()
    except dsr.GalatJadwalPrivate as galat:
        _log.error("Jadwal private gagal: %s", type(galat.__cause__ or galat).__name__)
        raise admin_store.StoreBelumSiap("jadwal private belum siap") from galat


def _jalankan(penangan, fungsi, copy_konflik: str) -> None:
    aksi.jalankan_aman(penangan, lambda: _dengan_galat_layanan(fungsi), copy_konflik=copy_konflik,
                       copy_isian=COPY_ISIAN, copy_layanan=COPY_LAYANAN)


_AKSI_POST = {
    ui.RUTE_SLOT: (_buat_slot, COPY_KONFLIK_BUAT),
    ui.RUTE_SLOT_BATAL: (_batal_slot, COPY_KONFLIK_BATAL),
    ui.RUTE_SETUJUI: (_setujui, COPY_KONFLIK_SETUJUI),
    ui.RUTE_TOLAK: (_tolak, COPY_KONFLIK_TOLAK),
    ui.RUTE_POLA_SETUJUI: (_setujui_pola, COPY_KONFLIK_POLA_SETUJUI),
    ui.RUTE_POLA_TOLAK: (_tolak_pola, COPY_KONFLIK_POLA_TOLAK),
}


def tangani_get(penangan, jalur) -> bool:
    if jalur != ui.RUTE:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    _get(penangan, principal)
    return True


def tangani_post(penangan, jalur) -> bool:
    if jalur not in _AKSI_POST:
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    fungsi, copy_konflik = _AKSI_POST[jalur]
    _jalankan(penangan, lambda: fungsi(penangan, principal), copy_konflik)
    return True

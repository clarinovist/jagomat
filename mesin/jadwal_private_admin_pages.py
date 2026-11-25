"""Render admin jadwal Private: form slot, antrean pengajuan orang tua, dan daftar slot.

Murni render (tanpa DB/HTTP). Semua nilai dinamis di-escape. Tidak memuat nama anak, nama orang tua, atau kontak;
nama guru hanya dari peta guru aktif. Token CSRF/tinjauan disuntik pemanggil per aksi. Tanpa sandi ulang karena
ini penjadwalan, bukan aksi uang. Orang tua hanya melihat waktu, bukan nama guru (lihat jadwal_private_baca).
"""
from __future__ import annotations

import html
from typing import Mapping, Sequence

import admin_labels as L
import admin_verifikasi_pages as vp
from pesanan_transfer_pages import waktu_wib

RUTE = "/admin/kelas/private"
RUTE_SLOT = RUTE + "/slot"
RUTE_SLOT_BATAL = RUTE + "/slot/batal"
RUTE_SETUJUI = RUTE + "/setujui"
RUTE_TOLAK = RUTE + "/tolak"
RUTE_ORDER = "/admin/kelas/verifikasi"
JUDUL = "Jadwal Private"
SUBJUDUL = "Slot guru, pengajuan orang tua, dan daftar slot."
JUDUL_SLOT = "Slot Private"
JUDUL_ANTREAN = "Pengajuan orang tua"
JUDUL_DAFTAR = "Daftar slot"
COPY_PETUNJUK = ("Orang tua hanya melihat waktu, bukan nama guru. "
                 "Bentrok ditandai oleh tim di halaman kelas; tidak diblokir.")
COPY_TANPA_GURU = "Belum ada akun guru aktif. Tambah akun guru dulu sebelum membuat slot."
COPY_ANTREAN_KOSONG = "Belum ada pengajuan dari orang tua."
COPY_SLOT_KOSONG = "Belum ada slot Private."
COPY_BATAL = "Batalkan slot ini? Slot yang dibatalkan tidak bisa dipilih orang tua lagi."
COPY_TOLAK = "Tolak pengajuan ini? Orang tua bisa memilih slot lain."
GURU_TIDAK_AKTIF = "Guru tidak aktif"
STATUS_BISA_BATAL = frozenset({"terbuka"})  # slot yang sedang diajukan harus ditolak/diputuskan dulu (server menolak batal)
LABEL_STATUS = {
    "terbuka": "Terbuka",
    "diajukan": "Diajukan",
    "terisi": "Terisi",
    "dibatalkan": "Dibatalkan",
    "lewat": "Lewat",
}


def _e(nilai) -> str:
    return html.escape(str(nilai), quote=True)


def _hidden(token: Mapping) -> str:
    return vp._hidden(token["csrf"], token["tinjauan"])


def _nama_guru(guru: Mapping[str, str], akun_id: str) -> str:
    return guru.get(akun_id, GURU_TIDAK_AKTIF)


def _opsi_guru(guru: Mapping[str, str]) -> str:
    opsi = ['<option value="">Pilih guru</option>']
    for akun, nama in sorted(guru.items(), key=lambda x: x[1].casefold()):
        opsi.append('<option value="%s">%s</option>' % (_e(akun), _e(nama)))
    return "".join(opsi)


def _kartu_slot_baru(guru: Mapping[str, str], token: Mapping) -> str:
    if not guru:
        return ('<section class="admin-kartu"><h2>%s</h2><p class="admin-meta">%s</p></section>'
                % (JUDUL_SLOT, _e(COPY_TANPA_GURU)))
    return (
        '<section class="admin-kartu admin-form-pendek"><h2>%s</h2>'
        '<form method="post" action="%s">%s'
        '<label>Guru<select name="guru_id" required>%s</select></label>'
        '<label>Tanggal mulai<input type="date" name="tanggal" required></label>'
        '<label>Jam mulai (WIB)<input type="time" name="jam" required></label>'
        '<button class="admin-tombol" type="submit">Buat slot</button></form></section>'
        % (JUDUL_SLOT, RUTE_SLOT, _hidden(token), _opsi_guru(guru)))


def _tombol_setujui(entri, token: Mapping) -> str:
    """Tombol Setujui hanya untuk pengajuan yang masih hidup; pengajuan basi harus ditolak."""
    if entri.basi:
        return ""
    return ('<form method="post" action="%s">%s<input type="hidden" name="id" value="%d">'
            '<button class="admin-tombol" type="submit">Setujui</button></form>'
            % (RUTE_SETUJUI, _hidden(token["setujui"][entri.pengajuan_id]), entri.pengajuan_id))


def _tombol_tolak(entri, token: Mapping) -> str:
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s<input type="hidden" name="id" value="%d">'
            '<button class="admin-tombol admin-bahaya" type="submit">Tolak</button></form>'
            % (RUTE_TOLAK, _e(COPY_TOLAK), _hidden(token["tolak"][entri.pengajuan_id]), entri.pengajuan_id))


def _badge_basi(entri) -> str:
    if not entri.basi:
        return ""
    return '<span class="admin-badge">kedaluwarsa: %s</span>' % _e(entri.alasan_basi)


def _baris_antrean(entri, guru: Mapping[str, str], token: Mapping) -> str:
    return ('<tr><td><a class="admin-tautan" href="%s?order=%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td>'
            '<td>%s<div class="admin-aksi-sesi-baris">%s%s</div></td></tr>'
            % (RUTE_ORDER, _e(entri.order_id), L.referensi(entri.order_id),
               _e(_nama_guru(guru, entri.guru_id)), _e(waktu_wib(entri.mulai)), _e(waktu_wib(entri.dibuat)),
               _badge_basi(entri), _tombol_setujui(entri, token), _tombol_tolak(entri, token)))


def _kartu_antrean(antrean: Sequence, guru: Mapping[str, str], token: Mapping) -> str:
    baris = "".join(_baris_antrean(entri, guru, token) for entri in antrean)
    return vp._tabel(JUDUL_ANTREAN, ("Order", "Guru", "Mulai (WIB)", "Diajukan", "Aksi"), baris, COPY_ANTREAN_KOSONG)


def _tombol_batal(slot, token: Mapping) -> str:
    if slot.status not in STATUS_BISA_BATAL:
        return ""
    return ('<form method="post" action="%s" data-konfirmasi="%s">%s<input type="hidden" name="id" value="%d">'
            '<button class="admin-tombol admin-bahaya" type="submit">Batalkan slot</button></form>'
            % (RUTE_SLOT_BATAL, _e(COPY_BATAL), _hidden(token["batal"][slot.slot_id]), slot.slot_id))


def _baris_slot(slot, guru: Mapping[str, str], token: Mapping) -> str:
    return ('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (_e(_nama_guru(guru, slot.guru_id)), _e(waktu_wib(slot.mulai)),
               _e(LABEL_STATUS.get(slot.status, slot.status)), _tombol_batal(slot, token)))


def _kartu_daftar(slot: Sequence, guru: Mapping[str, str], token: Mapping) -> str:
    baris = "".join(_baris_slot(s, guru, token) for s in slot)
    return vp._tabel(JUDUL_DAFTAR, ("Guru", "Mulai (WIB)", "Status", "Aksi"), baris, COPY_SLOT_KOSONG)


def halaman(slot: Sequence, antrean: Sequence, guru: Mapping[str, str], token: Mapping) -> str:
    """Petunjuk, kartu slot baru, pengajuan orang tua, dan daftar slot (tanpa nama anak atau orang tua)."""
    petunjuk = '<p class="admin-meta">%s</p>' % _e(COPY_PETUNJUK)
    return (petunjuk + _kartu_slot_baru(guru, token["buat"])
            + _kartu_antrean(antrean, guru, token) + _kartu_daftar(slot, guru, token))

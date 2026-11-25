"""Halaman konfirmasi nonaktifkan / aktifkan kembali guru (admin); murni, tanpa I/O dan tanpa JavaScript.

Form: csrf, tinjauan (terikat aksi dan sesi), reauth (sandi admin), id (harus sama dengan tinjauan). Tanpa kredensial atau kontak.
"""
from __future__ import annotations

from typing import Optional, Tuple

import admin_guru_akun as G
import admin_guru_akun_pages as P
from admin_guru_tab import TAB_AKUN, tab_guru
from admin_komponen import e

RUTE_NONAKTIFKAN = P.RUTE_NONAKTIFKAN
RUTE_AKTIFKAN = P.RUTE_AKTIFKAN
AKSI_NONAKTIFKAN = "guru_nonaktifkan"
AKSI_AKTIFKAN = "guru_aktifkan"
FIELD_ID = "id"
JUDUL = "Akun guru"
SUBJUDUL = "Nonaktifkan atau aktifkan kembali akun guru."
COPY_NONAKTIF = (
    "Guru ini langsung keluar dari semua perangkat dan tidak bisa masuk lagi sampai diaktifkan kembali. "
    "Data anak, lembaga, dan jadwal tidak diubah, tetapi guru nonaktif tidak muncul di pilihan penempatan baru. "
    "Akun bisa diaktifkan kembali. Pengecualian: bila guru ini ikut koleksi sensor, episode dan chat sensornya dihapus "
    "permanen pada pemeliharaan berikutnya dan tidak kembali saat diaktifkan.")
COPY_AKTIF = "Guru ini bisa masuk lagi dengan sandinya yang lama. Perangkat yang sudah keluar tetap harus masuk ulang."
COPY_TAHAN_KOORDINATOR = (
    "Tidak bisa dinonaktifkan: akun ini masih pemilik lembaga %s. Pendaftaran publik membutuhkan koordinator yang aktif. "
    "Pindahkan atau bubarkan lembaganya dulu.")
COPY_TIDAK_BISA = "Akun ini tidak bisa diubah statusnya. Tidak ada yang diubah."
COPY_BERUBAH = "Akun berubah sejak halaman dibuka. Buka ulang halaman guru lalu coba lagi."
COPY_TANPA_SESI = "Aksi ini butuh sesi masuk pengelola (bukan Basic auth)."
Token = Tuple[str, str]


def alamat_konfirmasi(rute: str, id_akun: str) -> str:
    return "%s?id=%s" % (rute, id_akun)


def _hidden(nama: str, nilai: str) -> str:
    return '<input type="hidden" name="%s" value="%s">' % (nama, e(nilai))


def _form(rute: str, id_akun: str, token: Token, tombol: str, *, bahaya: bool) -> str:
    csrf, tinjauan = token
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s%s%s'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required autocomplete="current-password"></label>'
        '<button class="admin-tombol%s" type="submit">%s</button></form>'
        % (rute, _hidden("csrf", csrf), _hidden("tinjauan", tinjauan), _hidden(FIELD_ID, id_akun),
           " admin-bahaya" if bahaya else "", e(tombol)))


def halaman_konfirmasi(g: G.GuruRingkas, *, nonaktifkan: bool, token: Optional[Token], tahan: Optional[str] = None) -> str:
    """Kartu konfirmasi untuk satu guru. `tahan` = alasan aksi tidak tersedia (tanpa form); `token` None = tanpa sesi cookie."""
    rute, tombol, copy = ((RUTE_NONAKTIFKAN, "Nonaktifkan akun", COPY_NONAKTIF) if nonaktifkan
                          else (RUTE_AKTIFKAN, "Aktifkan kembali", COPY_AKTIF))
    if tahan or not token:
        isi = '<p class="admin-meta">%s</p>' % e(tahan or COPY_TANPA_SESI)
    else:
        isi = _form(rute, g.id_akun, token, tombol, bahaya=nonaktifkan)
    return (
        tab_guru(TAB_AKUN)
        + '<p class="admin-jejak"><a href="%s">← Kembali ke guru %s</a></p>' % (e(P.alamat_guru(g.id_akun)), e(g.pengguna))
        + '<section class="admin-kartu"><h2>%s guru %s</h2><p>%s</p><p class="admin-meta">Anak: %d. Meminta sandi admin. Jejaknya tampil di halaman guru, bukan di Riwayat admin.</p>%s</section>'
        % ("Nonaktifkan" if nonaktifkan else "Aktifkan kembali", e(g.pengguna), e(copy), g.jumlah_siswa, isi))

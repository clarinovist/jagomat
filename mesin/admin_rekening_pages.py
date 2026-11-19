"""Renderer murni halaman admin pengaturan rekening tujuan transfer (tanpa I/O, tanpa JS baru).

Nomor rekening hanya tampil ter-mask (empat digit terakhir) dan tidak pernah dipantulkan kembali di form:
admin mengetik ulang nomor setiap perubahan. Halaman menjelaskan bahwa transfer tetap tertutup bagi guru
sampai rekening diisi. Semua nilai dinamis di-escape; waktu ditampilkan dalam WIB.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple

import admin_labels as L
from admin_komponen import e
from admin_pesanan_pages import RUTE, RUTE_REKENING
from pesanan_rekening import BATAS_ATAS_NAMA, BATAS_NAMA_BANK, BATAS_NOMOR

JUDUL = "Rekening transfer"
SUBJUDUL = "Rekening tujuan transfer Paket Coba. Nomor tampil ter-mask; perubahan tercatat di audit hanya sebagai sidik."
AKSI_UBAH = "ubah_rekening"
KEADAAN_TERISI = "terisi"
KEADAAN_KOSONG = "kosong"
KEADAAN_BELUM_DIPASANG = "belum_dipasang"
DIGIT_TERAKHIR = 4
KARAKTER_TOPENG = "*"

COPY_HASIL = {"tersimpan": "Rekening tersimpan. Nomor lengkap tidak ditampilkan lagi di halaman ini."}
KODE_HASIL = frozenset(COPY_HASIL)
COPY_BELUM_DIISI = (
    "Rekening belum diisi. Transfer tetap tertutup bagi guru sampai rekening diisi di sini dan sakelar "
    "transfer dinyalakan operator."
)
COPY_TIDAK_SIAP = (
    "Skema rekening belum dipasang atau database belum siap di server ini. Operator memasangnya lebih dulu "
    "lewat mesin/pesanan_transfer_migrasi.py (lihat docs/production-release.md). Tidak ada yang diubah."
)
COPY_PETUNJUK_NOMOR = (
    "Ketik ulang nomor rekening setiap kali menyimpan: %d sampai %d digit, bukan satu angka berulang."
    % BATAS_NOMOR
)
COPY_TANPA_SESI = "Tampilan baca-saja. Masuk melalui formulir untuk mengubah rekening."
COPY_GALAT_ISIAN = (
    "Isian rekening tidak sah. Nama bank %d sampai %d karakter, atas nama %d sampai %d karakter, nomor %d sampai "
    "%d digit dan bukan satu angka berulang; tanpa spasi ganda atau di awal/akhir. Tidak ada yang diubah."
    % (BATAS_NAMA_BANK + BATAS_ATAS_NAMA + BATAS_NOMOR)
)
COPY_GALAT_KONFLIK = (
    "Rekening sudah diubah sejak halaman ini dibuka, atau permintaan ini bentrok dengan catatan yang ada. "
    "Buka ulang halaman rekening, periksa nilai terbaru, lalu coba lagi. Tidak ada yang diubah."
)


def topeng_nomor(nomor: str) -> str:
    """Nomor ter-mask: hanya `DIGIT_TERAKHIR` digit terakhir yang terlihat."""
    return KARAKTER_TOPENG * max(0, len(nomor) - DIGIT_TERAKHIR) + nomor[-DIGIT_TERAKHIR:]


def _hidden(csrf: str, tinjauan: str) -> str:
    return ('<input type="hidden" name="csrf" value="%s"><input type="hidden" name="tinjauan" value="%s">'
            % (e(csrf), e(tinjauan)))


def _form(keadaan: Mapping, token: Tuple[str, str]) -> str:
    return (
        '<form class="admin-form-bagian admin-form-pendek" method="post" action="%s">%s'
        '<label>Nama bank<input type="text" name="nama_bank" required minlength="%d" maxlength="%d" '
        'autocomplete="off" value="%s"></label>'
        '<label>Nomor rekening<input type="text" name="nomor_rekening" required inputmode="numeric" '
        'pattern="[0-9]*" minlength="%d" maxlength="%d" autocomplete="off"></label>'
        '<p class="admin-meta">%s</p>'
        '<label>Atas nama<input type="text" name="atas_nama" required minlength="%d" maxlength="%d" '
        'autocomplete="off" value="%s"></label>'
        '<label>Sandi admin saat ini<input type="password" name="reauth" required '
        'autocomplete="current-password"></label>'
        '<button class="admin-tombol" type="submit">Simpan rekening</button></form>'
        % (RUTE_REKENING, _hidden(*token), BATAS_NAMA_BANK[0], BATAS_NAMA_BANK[1],
           e(keadaan.get("nama_bank", "")), BATAS_NOMOR[0], BATAS_NOMOR[1], e(COPY_PETUNJUK_NOMOR),
           BATAS_ATAS_NAMA[0], BATAS_ATAS_NAMA[1], e(keadaan.get("atas_nama", ""))))


def _ringkasan(keadaan: Mapping) -> str:
    if keadaan["status"] != KEADAAN_TERISI:
        return '<p>%s</p>' % e(COPY_BELUM_DIISI)
    return ('<p>Rekening terisi: <strong>%s</strong>, atas nama <strong>%s</strong>, nomor '
            '<code class="admin-id">%s</code>.</p><p class="admin-meta">Revisi %d, diperbarui %s oleh '
            '<code class="admin-id">%s</code>.</p>'
            % (e(keadaan["nama_bank"]), e(keadaan["atas_nama"]), e(topeng_nomor(keadaan["nomor"])),
               keadaan["revisi"], e(L.tanggal(keadaan["diperbarui"])), e(keadaan["actor"][:13])))


def _umpan_balik(hasil: Optional[str]) -> str:
    if hasil not in COPY_HASIL:
        return ""
    return '<p class="admin-kartu admin-catatan" role="status" aria-atomic="true">%s</p>' % e(COPY_HASIL[hasil])


def _sakelar(aktif: bool) -> str:
    teks = ("Sakelar transfer: aktif (PESANAN_TRANSFER_AKTIF=1). Gerbang tetap menunggu funnel, runtime "
            "produksi, dan rekening terisi." if aktif else
            "Sakelar transfer: mati (PESANAN_TRANSFER_AKTIF bukan 1). Guru tidak melihat jalur transfer.")
    return '<p class="admin-meta">%s</p>' % e(teks)


def halaman(keadaan: Mapping, token: Optional[Tuple[str, str]], *, hasil: Optional[str] = None,
            sakelar_aktif: bool = False) -> str:
    """Isi section rekening. `token` = (csrf, tinjauan) atau None (baca-saja, tanpa form)."""
    form = _form(keadaan, token) if token else '<p class="admin-meta">%s</p>' % e(COPY_TANPA_SESI)
    return (_umpan_balik(hasil) + '<section class="admin-kartu"><h2>%s</h2>%s%s</section>'
            % (e(JUDUL), _ringkasan(keadaan), _sakelar(sakelar_aktif))
            + '<section class="admin-kartu admin-form-tindakan">%s</section>' % form
            + '<p class="admin-meta"><a class="admin-tautan" href="%s">Kembali ke pesanan</a></p>' % RUTE)


def halaman_tidak_siap() -> str:
    return ('<section class="admin-kartu admin-galat" role="alert"><h2>Belum siap</h2><p>%s</p></section>'
            % e(COPY_TIDAK_SIAP))

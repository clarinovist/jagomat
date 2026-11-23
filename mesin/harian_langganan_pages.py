"""Render halaman langganan Latihan Harian untuk murid (orang tua memakai akun anak) dan blok halaman orang tua.

Murni render: tanpa DB, tanpa token buatan sendiri (pemanggil menyuntik `token_untuk(aksi)`), tanpa JS baru.
Aturan isi:

- Nominal hanya dari tagihan ledger (harga paket + kode unik) dan disorot harus persis; harga paket dari
  konstanta domain, bukan dari form. Rekening hanya tampil bersama tagihan.
- Alasan penolakan admin tampil ter-escape. Nomor WhatsApp, nama berkas, dan id order tidak pernah dirender.
- Satu aksi satu tombol: status menentukan hanya satu form (pilih paket, atau unggah bukti).
"""
from __future__ import annotations

from typing import Callable, Optional

from cek_pages import _a, _e
from format_tanggal import tanggal_pendek
import harian_langganan_dasar as h
import harian_langganan_ringkas as ringkas
import pesanan_murid_pages
from pesanan_transfer_pages import (COPY_ATURAN, COPY_BERKAS_BESAR, COPY_BERKAS_KOSONG, COPY_BERKAS_TAK_TERBACA,
                                    COPY_LABEL_BERKAS, COPY_TIPE_TIDAK_DIDUKUNG, rupiah, waktu_wib)

RUTE = "/murid/langganan"
RUTE_BUAT = RUTE + "/buat"
RUTE_BUKTI = RUTE + "/bukti"
AKSI_BUAT = "harian_buat:"
AKSI_BUKTI = "harian_bukti"
ID_JUDUL = "judul-langganan"
COPY_JUDUL = "Langganan Latihan Harian"
COPY_JUDUL_STATUS = "Status langganan"
_ACCEPT_BUKTI = "image/jpeg,image/png,application/pdf"

COPY_AKTIF = "Latihan Harian tanpa batas aktif sampai %s."
COPY_LES = "Anak ini murid les, jadi Latihan Harian tanpa batas tanpa perlu berlangganan."
COPY_GRATIS = "Belum berlangganan. Anak tetap bisa 1 sesi Latihan Harian gratis setiap hari."
COPY_PENGANTAR = "Pilih paket, lalu transfer ke rekening kami dan unggah bukti transfernya. Tim akan memeriksa bukti Anda."
COPY_PENGANTAR_PERPANJANG = "Perpanjangan menyambung dari tanggal berakhir, jadi hari yang tersisa tidak hilang."
COPY_BELUM_DIBUKA = "Pembayaran langganan belum dibuka. Coba lagi nanti."
COPY_JUDUL_TAGIHAN = "Bayar lewat transfer"
COPY_MENUNGGU = "Bukti sudah kami terima. Tim akan memeriksanya; langganan aktif setelah bukti disetujui."
COPY_DITOLAK = "Bukti terakhir belum sesuai. Alasan dari tim:"
COPY_BATAS_BUKTI = "Batas bukti untuk tagihan ini sudah tercapai. Hubungi tim bila masih perlu bantuan."
COPY_TOMBOL_UNGGAH = "Unggah bukti"
COPY_TOMBOL_UNGGAH_ULANG = "Unggah ulang bukti"
COPY_REKENING_KOSONG = "Rekening tujuan belum tersedia. Hubungi tim sebelum mentransfer."
COPY_GAGAL_BUAT = "Tagihan belum bisa dibuat. Selesaikan tagihan yang sedang berjalan, atau coba lagi nanti."
COPY_KODE_HABIS = "Tagihan belum bisa dibuat sekarang. Coba lagi nanti atau hubungi tim."
COPY_TIDAK_TERIMA = "Tidak ada tagihan yang sedang menerima bukti. Buat tagihan dulu, atau waktu pembayaran sudah habis."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
COPY_ISIAN_TIDAK_SAH = "Isian tidak sah. Muat ulang halaman, lalu coba lagi."
COPY_BERKAS = {"kosong": COPY_BERKAS_KOSONG, "besar": COPY_BERKAS_BESAR, "tipe": COPY_TIPE_TIDAK_DIDUKUNG,
               "terbaca": COPY_BERKAS_TAK_TERBACA}

TokenUntuk = Callable[[str], str]


def _kartu(isi: str) -> str:
    return f'<div class="kartu-st">{isi}</div>'


def _catatan(teks: str) -> str:
    return f'<p class="funnel-catatan-st">{_e(teks)}</p>'


def _tombol(teks: str) -> str:
    return f'<p class="akun-aksi-sandi"><button type="submit" class="tombol-utama-akun">{_e(teks)}</button></p>'


def tanggal_berakhir(berakhir: str) -> str:
    return tanggal_pendek(h.tanggal_wib(berakhir))


def kalimat_status(r: ringkas.Ringkasan) -> str:
    """Satu kalimat status akses (dipakai halaman langganan dan kartu halaman orang tua)."""
    if r.langganan_aktif and r.berakhir:
        return COPY_AKTIF % tanggal_berakhir(r.berakhir)
    return COPY_LES if r.sumber == "les" else COPY_GRATIS


def _kartu_status(r: ringkas.Ringkasan) -> str:
    return _kartu(f"<h2>{_e(COPY_JUDUL_STATUS)}</h2><p>{_e(kalimat_status(r))}</p>")


def _form_paket(paket: h.Paket, token_untuk: TokenUntuk, perpanjang: bool) -> str:
    teks = "%s %s %s" % ("Perpanjang" if perpanjang else "Pilih", paket.nama, rupiah(paket.rupiah))
    return (f'<form method="post" action="{RUTE_BUAT}">'
            f'<input type="hidden" name="token" value="{_a(token_untuk(AKSI_BUAT + paket.kode))}">'
            f'<input type="hidden" name="paket" value="{_a(paket.kode)}">{_tombol(teks)}</form>')


def _kartu_pilih(r: ringkas.Ringkasan, token_untuk: TokenUntuk) -> str:
    pengantar = COPY_PENGANTAR + (" " + COPY_PENGANTAR_PERPANJANG if r.langganan_aktif else "")
    forms = "".join(_form_paket(p, token_untuk, r.langganan_aktif) for p in h.PAKET.values())
    return _kartu(f"<h2>{_e(COPY_JUDUL_TAGIHAN)}</h2><p>{_e(pengantar)}</p>{forms}")


def _rincian(tampil, rekening) -> str:
    if rekening is None:
        return _catatan(COPY_REKENING_KOSONG)
    return (
        f"<p>Paket: <strong>{_e(tampil.paket.nama)}</strong></p>"
        f"<p>Bank: <strong>{_e(rekening.nama_bank)}</strong></p>"
        f"<p>Nomor rekening: <strong>{_e(rekening.nomor_label)}</strong></p>"
        f"<p>Atas nama: <strong>{_e(rekening.atas_nama)}</strong></p>"
        f'<p class="funnel-catatan-st">Nominal yang harus Anda transfer: <strong>{_e(rupiah(tampil.nominal))}</strong>. '
        "Nominal harus persis sama sampai tiga digit terakhir; jangan dibulatkan.</p>"
        f"<p>Batas waktu: <strong>{_e(waktu_wib(tampil.kedaluwarsa))}</strong></p>")


def _form_unggah(token: str, ulang: bool) -> str:
    return (
        f'<form method="post" action="{RUTE_BUKTI}" enctype="multipart/form-data">'
        f'<input type="hidden" name="token" value="{_a(token)}">'
        f'<p><label>{_e(COPY_LABEL_BERKAS)}<br>'
        f'<input type="file" name="berkas" accept="{_ACCEPT_BUKTI}" required></label></p>'
        f'{_tombol(COPY_TOMBOL_UNGGAH_ULANG if ulang else COPY_TOMBOL_UNGGAH)}</form>')


def _kartu_tagihan(tampil, rekening, token_untuk: TokenUntuk) -> str:
    isi = f"<h2>{_e(COPY_JUDUL_TAGIHAN)}</h2>"
    if tampil.status == h.STATUS_DITOLAK and tampil.alasan_tolak:
        isi += f'<p class="funnel-catatan-st">{_e(COPY_DITOLAK)} <strong>{_e(tampil.alasan_tolak)}</strong></p>'
    if tampil.status == h.STATUS_MENUNGGU:
        isi += _catatan(COPY_MENUNGGU)
    isi += _rincian(tampil, rekening)
    if tampil.status != h.STATUS_MENUNGGU:
        isi += _catatan(COPY_ATURAN)
    if rekening is not None and tampil.boleh_unggah:
        isi += _form_unggah(token_untuk(AKSI_BUKTI), tampil.status == h.STATUS_DITOLAK)
    elif tampil.jumlah_bukti >= h.MAKS_BUKTI:
        isi += _catatan(COPY_BATAS_BUKTI)
    return _kartu(isi)


def _badan(r: ringkas.Ringkasan, tampil, rekening, token_untuk: TokenUntuk) -> str:
    isi = _kartu_status(r)
    if tampil is not None:
        return isi + _kartu_tagihan(tampil, rekening, token_untuk)
    if rekening is None:
        return isi + _kartu(f"<h2>{_e(COPY_JUDUL_TAGIHAN)}</h2><p>{_e(COPY_BELUM_DIBUKA)}</p>")
    return isi + _kartu_pilih(r, token_untuk)


def halaman_langganan(r: ringkas.Ringkasan, tampil, rekening, token_untuk: TokenUntuk) -> bytes:
    """Halaman /murid/langganan: status akses + (pilih paket | tagihan terbuka)."""
    return _bungkus(_badan(r, tampil, rekening, token_untuk))


def halaman_info(judul: str, teks: str) -> bytes:
    """Pesan tetap tanpa form, dengan tautan kembali ke halaman langganan."""
    isi = (_kartu(f"<h2>{_e(judul)}</h2><p>{_e(teks)}</p>")
           + f'<p class="akun-aksi-sandi"><a href="{RUTE}">Kembali ke langganan</a></p>')
    return _bungkus(isi)


def _bungkus(isi: str) -> bytes:
    return pesanan_murid_pages.halaman_murid(COPY_JUDUL, ID_JUDUL, f'<h1 id="{ID_JUDUL}">{_e(COPY_JUDUL)}</h1>' + isi,
                                             "/murid", "Beranda")


# --- halaman orang tua ----------------------------------------------------------------

def banner_orang_tua(r: Optional[ringkas.Ringkasan], nama_anak: str) -> str:
    """Banner 'berakhir N hari lagi' bila langganan aktif dan sisa <= HARI_PENGINGAT; selain itu ''."""
    if r is None or not r.perlu_pengingat:
        return ""
    teks = "Latihan Harian %s berakhir %d hari lagi." % (nama_anak or "anak", r.sisa_hari)
    return (f'<p class="ortu-kabar-st" id="ortu-langganan-banner" role="status">{_e(teks)} '
            f'<a href="{RUTE}">Perpanjang</a></p>')


def kartu_orang_tua(r: Optional[ringkas.Ringkasan]) -> str:
    """Kartu status langganan + satu tombol ke halaman langganan; '' bila fitur mati (r None)."""
    if r is None:
        return ""
    label = "Perpanjang" if r.langganan_aktif else "Berlangganan"
    tombol = "" if r.sumber == "les" else f'<a class="ortu-tombol-st" href="{RUTE}">{_e(label)}</a>'
    return (f'<section class="ortu-kartu-st" id="ortu-langganan"><h2>{_e(COPY_JUDUL)}</h2>'
            f'<p>{_e(kalimat_status(r))}</p>{tombol}</section>')

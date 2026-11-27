"""Render kartu 'Jadwal Private' di /murid/paket (sisi orang tua): slot yang boleh diajukan dan pengajuan menunggu.

Tanpa nama guru dan tanpa id guru: slot hanya tampil sebagai hari dan waktu WIB. Id slot ikut sebagai nilai form
bertoken. Semua nilai dinamis di-escape. Murni render (tanpa DB, HTTP, atau store).
"""
from __future__ import annotations

import html
from typing import Callable, Optional, Sequence

import jadwal_dasar as jd
import jadwal_private_dasar as dsr
import paket_belajar_katalog as katalog
from jadwal_private_baca import SlotTerbuka, StatusPengajuan
from jadwal_private_pola_aturan import NAMA_HARI, Pola, teks_pola
from kelas_pages import RUTE
from pesanan_transfer_pages import waktu_wib

RUTE_PRIVATE = RUTE + "/jadwal-private"
RUTE_AJUKAN = RUTE_PRIVATE + "/ajukan"
RUTE_BATAL = RUTE_PRIVATE + "/batal"
AKSI_AJUKAN = "jadwal_private_ajukan:"
AKSI_BATAL = "jadwal_private_batal"
RUTE_POLA = RUTE_PRIVATE + "/pola"
RUTE_POLA_BATAL = RUTE_PRIVATE + "/pola/batal"
AKSI_POLA = "jadwal_private_pola_ajukan"
AKSI_POLA_BATAL = "jadwal_private_pola_batal"
COPY_JUDUL = "Jadwal Private"
COPY_PENGANTAR = "Pilih satu waktu untuk anak. Tim memeriksa pilihan Ayah/Bunda sebelum jadwal dikunci."
COPY_MENUNGGU = "Waktu pilihanmu: {waktu} — menunggu persetujuan tim."
COPY_DITOLAK = "Pilihan sebelumnya tidak bisa dipakai. Silakan pilih waktu lain."
COPY_KOSONG = "Belum ada waktu yang dibuka. Tim akan menghubungimu."
COPY_AJUKAN = "Ajukan"
COPY_GANTI = "Ganti ke waktu ini"
COPY_BATAL = "Batalkan pilihan"
TokenUntuk = Callable[[str], str]


def _e(teks: object) -> str:
    return html.escape(str(teks), quote=True)


def _p(teks: str, kelas: str = "lg-ket") -> str:
    return f'<p class="{kelas}">{_e(teks)}</p>'


def _tombol(teks: str) -> str:
    return f'<button type="submit" class="ceria-tombol">{_e(teks)}</button>'


def _ritme() -> str:
    paket = katalog.ambil(dsr.PAKET)
    return f"{paket.pertemuan} pertemuan, 2x seminggu, {paket.menit} menit, Online"


def _waktu(mulai: str) -> str:
    """'Rabu, 25 November 2026 pukul 10.00 WIB'; hari dihitung dari tanggal WIB."""
    return f"{NAMA_HARI[jd.tanggal_wib(mulai).weekday()]}, {waktu_wib(mulai)}"


def _form_batal(token_untuk: TokenUntuk) -> str:
    return (f'<form method="post" action="{RUTE_BATAL}">'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_BATAL))}">'
            f"{_tombol(COPY_BATAL)}</form>")


def _form_ajukan(slot: SlotTerbuka, label: str, token_untuk: TokenUntuk) -> str:
    return (f'<form method="post" action="{RUTE_AJUKAN}">{_p(_waktu(slot.mulai))}'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_AJUKAN + str(slot.slot_id)))}">'
            f'<input type="hidden" name="slot" value="{_e(slot.slot_id)}">'
            f"{_tombol(label)}</form>")


def _menunggu(pengajuan: Optional[StatusPengajuan]) -> bool:
    return pengajuan is not None and pengajuan.status == dsr.STATUS_DIAJUKAN


def _kabar(pengajuan: Optional[StatusPengajuan], token_untuk: TokenUntuk) -> str:
    if _menunggu(pengajuan):
        return _p(COPY_MENUNGGU.format(waktu=_waktu(pengajuan.mulai)), "lg-kecil") + _form_batal(token_untuk)
    if pengajuan is not None and pengajuan.status in (dsr.STATUS_DITOLAK, "basi"):
        return _p(COPY_DITOLAK, "lg-kecil")
    return ""


def _daftar(pengajuan: Optional[StatusPengajuan], slot: Sequence[SlotTerbuka], token_untuk: TokenUntuk) -> str:
    if not slot:
        return _p(COPY_KOSONG, "lg-kecil")
    label = COPY_GANTI if _menunggu(pengajuan) else COPY_AJUKAN
    return "".join(_form_ajukan(s, label, token_untuk) for s in slot)


def kartu_private(pengajuan: Optional[StatusPengajuan], slot: Sequence[SlotTerbuka], token_untuk: TokenUntuk) -> str:
    """Kartu 'Jadwal Private' LAMA (pilih satu slot): tidak lagi dirender murid sejak pola 2 hari.

    Tindak lanjut (sesudah pola stabil di produksi): hapus kartu ini, rute `ajukan`/`batal` lama di
    jadwal_private_murid_http, dan `jadwal_private.ajukan`. Sampai itu, rute lama tetap menerima POST dan admin tetap
    bisa menyetujui pengajuan slot 'diajukan' yang sudah ada.
    """
    isi = (f"<h2>{_e(COPY_JUDUL)}</h2>{_p(_ritme())}{_p(COPY_PENGANTAR)}"
           f"{_kabar(pengajuan, token_untuk)}{_daftar(pengajuan, slot, token_untuk)}")
    return f'<section class="lg-kartu">{isi}</section>'


# --- kartu pola (2 hari + 1 jam, disetujui tim) ---------------------------------------------

COPY_POLA_PENGANTAR = "Pilih dua hari dan satu jam untuk anak. Tim memeriksa pilihan Ayah/Bunda sebelum jadwal dikunci."
COPY_POLA_MENUNGGU = "Pilihan Anda: {pola} — menunggu persetujuan tim."
COPY_POLA_DITOLAK = "Pilihan sebelumnya tidak bisa dipakai. Silakan pilih hari dan jam lain."
COPY_POLA_HARI = "Hari (pilih 2)"
COPY_POLA_JAM = "Jam"
COPY_POLA_AJUKAN = "Ajukan"
COPY_LAMA_MENUNGGU = ("Pilihan waktu sebelumnya: {waktu} — menunggu persetujuan tim. "
                      "Memilih hari dan jam baru akan membatalkannya.")


def _form_batal_pola(token_untuk: TokenUntuk) -> str:
    return (f'<form method="post" action="{RUTE_POLA_BATAL}">'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_POLA_BATAL))}">'
            f"{_tombol(COPY_BATAL)}</form>")


def _kabar_lama(lama: Optional[StatusPengajuan], token_untuk: TokenUntuk) -> str:
    """Pengajuan slot lama yang masih menunggu (dari sebelum pola): tetap terlihat dan bisa dibatalkan."""
    if not _menunggu(lama):
        return ""
    return _p(COPY_LAMA_MENUNGGU.format(waktu=_waktu(lama.mulai)), "lg-kecil") + _form_batal(token_untuk)


def _kabar_pola(terakhir: Optional[Pola], token_untuk: TokenUntuk) -> str:
    if terakhir is None:
        return ""
    if terakhir.status == dsr.STATUS_DIAJUKAN:
        teks = teks_pola(terakhir.hari_a, terakhir.hari_b, terakhir.jam)
        return _p(COPY_POLA_MENUNGGU.format(pola=teks), "lg-kecil") + _form_batal_pola(token_untuk)
    if terakhir.status == dsr.STATUS_DITOLAK:
        return _p(COPY_POLA_DITOLAK, "lg-kecil")
    return ""


def _pilihan(nama: str, nilai: str, label: str, tipe: str, wajib: bool = False) -> str:
    atribut = " required" if wajib else ""
    return (f'<label class="lg-pilihan"><input type="{tipe}" name="{nama}" value="{_e(nilai)}"{atribut}> '
            f"{_e(label)}</label>")


def _form_pola(token_untuk: TokenUntuk) -> str:
    hari = "".join(_pilihan(f"hari_{nomor}", "1", NAMA_HARI[nomor], "checkbox") for nomor in sorted(dsr.HARI_BOLEH))
    jam = "".join(_pilihan("jam", waktu, waktu.replace(":", ".") + " WIB", "radio", wajib=True)
                  for waktu in dsr.JAM_BOLEH)
    return (f'<form method="post" action="{RUTE_POLA}">'
            f'<input type="hidden" name="token" value="{_e(token_untuk(AKSI_POLA))}">'
            f'<fieldset class="lg-pilihan-grup"><legend>{_e(COPY_POLA_HARI)}</legend>{hari}</fieldset>'
            f'<fieldset class="lg-pilihan-grup"><legend>{_e(COPY_POLA_JAM)}</legend>{jam}</fieldset>'
            f"{_tombol(COPY_POLA_AJUKAN)}</form>")


def kartu_pola(terakhir: Optional[Pola], token_untuk: TokenUntuk,
               lama: Optional[StatusPengajuan] = None) -> str:
    """Kartu 'Jadwal Private' pola: pengantar, kabar pilihan (pola dan slot lama), lalu form (tanpa JS)."""
    isi = (f"<h2>{_e(COPY_JUDUL)}</h2>{_p(_ritme())}{_p(COPY_POLA_PENGANTAR)}"
           f"{_kabar_lama(lama, token_untuk)}{_kabar_pola(terakhir, token_untuk)}{_form_pola(token_untuk)}")
    return f'<section class="lg-kartu">{isi}</section>'

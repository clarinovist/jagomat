"""Peta rute pesanan Peta Kemampuan per permukaan pembeli (guru dan murid).

Mesin pesanan/transfer SATU saja; yang berbeda per permukaan hanya alamat. `Rute` adalah
peta alamat beku yang dipakai renderer (form, tautan, gambar QR) dan penangan (pengalihan).
Permukaan ditentukan oleh PERAN principal dari sesi server (`rute_untuk`), tidak pernah
oleh input klien. Guru memakai alamat lama persis seperti sebelumnya; murid (orang tua
yang memakai akun anak) memakai awalan `/murid/pesanan`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

PERAN_MURID = "murid"


@dataclass(frozen=True)
class Rute:
    status: str
    qr: str
    pesan: str
    periksa: str
    ulang: str
    buat: str
    tagihan: str
    bukti: str
    ulang_transfer: str
    beranda: str
    label_beranda: str
    hasil: str
    label_hasil: str
    kontak: Optional[str]
    label_kontak: str
    # Pilihan pembeli saat laporan terlambat (V4a): hanya permukaan murid; None (guru lama) = tanpa tombol dan tanpa rute.
    pilih: Optional[str] = None


RUTE_GURU = Rute(
    status="/pesanan", qr="/pesanan/qr", pesan="/paket-coba/pesan", periksa="/pesanan/periksa",
    ulang="/pesanan/ulang", buat="/pesanan/buat", tagihan="/pesanan/tagihan",
    bukti="/pesanan/bukti", ulang_transfer="/pesanan/tagihan/ulang",
    beranda="/guru", label_beranda="Beranda",
    hasil="/cek-kemampuan/hasil", label_hasil="Kembali ke hasil cek",
    kontak="/akun/kontak", label_kontak="Lengkapi nomor WhatsApp",
)

# Murid: titik masuk GET = `/murid/pesanan`. Tidak ada rute kontak (nomor diubah lewat admin).
RUTE_MURID = Rute(
    status="/murid/pesanan", qr="/murid/pesanan/qr", pesan="/murid/pesanan/pesan",
    periksa="/murid/pesanan/periksa", ulang="/murid/pesanan/ulang", buat="/murid/pesanan/buat",
    tagihan="/murid/pesanan/tagihan", bukti="/murid/pesanan/bukti",
    ulang_transfer="/murid/pesanan/tagihan/ulang",
    beranda="/murid", label_beranda="Beranda",
    hasil="/murid", label_hasil="Kembali ke beranda",
    kontak=None, label_kontak="",
    pilih="/murid/pesanan/pilih",
)

_KANONIK_KE_MURID = tuple(
    (getattr(RUTE_GURU, nama), getattr(RUTE_MURID, nama))
    for nama in ("status", "qr", "pesan", "periksa", "ulang", "buat", "tagihan", "bukti", "ulang_transfer", "pilih")
)
# Alamat murid -> alamat guru yang setara (kunci tabel aksi/gerbang di penangan bersama). `pilih` tidak punya
# padanan guru (None): penangan murid melayaninya sendiri SEBELUM mencari padanan ini (`pesanan_pilih_http`).
MURID_KE_KANONIK = {murid: guru for guru, murid in _KANONIK_KE_MURID}


def rute_untuk_peran(peran) -> Rute:
    """Peta rute untuk satu peran; selain murid memakai alamat guru (perilaku lama)."""
    return RUTE_MURID if peran == PERAN_MURID else RUTE_GURU


def rute_untuk(principal) -> Rute:
    """Peta rute untuk principal sesi (peran dari server)."""
    return rute_untuk_peran(principal.peran)

"""Masa berlaku Paket Belajar per anak untuk banner perpanjang di halaman orang tua (BACA-SAJA, tanpa tulis).

Keputusan Pemilik 25 Nov 2026: perpanjangan paket kelas bulanan (Private/Mini) hanya memakai tagihan dan notifikasi
di dalam aplikasi. Masa diturunkan dari `kelas_akses` (sumber masa aktif); tidak ada baris yang ditulis di sini.

Aturan:

- Masa paket = `MAX(berakhir)` akses milik akun pembeli untuk (anak, paket). Perpanjangan yang sudah disetujui tetapi
  belum mulai ikut terhitung lewat MAX, sehingga tidak memicu banner (perilaku yang diinginkan).
- Akun SELALU ikut di kueri: akses atau order milik akun lain tidak pernah terbaca (sama seperti tidak ada).
- Paket dengan order TERBUKA (belum bayar, menunggu, atau ditolak) untuk anak itu DILEWATI: pembeli sedang
  memperpanjang, jadi tidak ada entri dan tidak ada banner untuk paket tersebut.
- Paket yang berakhir lebih awal daripada paket lain milik anak yang sama dilewati (anak yang pindah paket tidak
  mendapat banner "berakhir" untuk paket lamanya).
- Paket tanpa akses dilewati. Urutan hasil mengikuti katalog.
- `sisa_hari` dibulatkan ke atas (0 bila sudah berakhir). Status: `habis` bila sisa 0, `segera` bila sisa
  1..HARI_PENGINGAT, selain itu `aktif`.
- Modul ini tidak mengimpor domain harian; alat waktu dan validasi dari `kelas_dasar` dan `pesanan_dasar`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

import kelas_dasar as k
import kelas_status as ks
import paket_belajar_katalog as katalog
import pesanan_dasar as d

HARI_PENGINGAT = 3
DETIK_PER_HARI = 86_400
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
STATUS_AKTIF = "aktif"
STATUS_SEGERA = "segera"
STATUS_HABIS = "habis"

_SQL_BERAKHIR = ("SELECT MAX(a.berakhir) FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
                 "WHERE o.akun_id=? AND a.siswa_id=? AND o.paket=?")
_SQL_BERAKHIR_SEMUA_PAKET = ("SELECT MAX(a.berakhir) FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
                             "WHERE o.akun_id=? AND a.siswa_id=?")


@dataclass(frozen=True)
class TagihanBelumBayar:
    """Tagihan paket yang masih menunggu pembayaran atau unggah ulang bukti (butir QA #3, notifikasi gantung)."""
    kode_paket: str
    nama: str
    kedaluwarsa: str
    status: str


@dataclass(frozen=True)
class MasaPaket:
    kode_paket: str
    nama: str
    berakhir: str
    sisa_hari: int
    status: str


def _sisa_hari(berakhir: str, kini: str) -> int:
    """Hari tersisa dibulatkan ke atas; 0 bila `berakhir` sudah lewat atau tepat `kini`."""
    selisih = (datetime.strptime(berakhir, FORMAT_WAKTU) - datetime.strptime(kini, FORMAT_WAKTU)).total_seconds()
    if selisih <= 0:
        return 0
    return math.ceil(selisih / DETIK_PER_HARI)


def _status(sisa: int) -> str:
    if sisa == 0:
        return STATUS_HABIS
    return STATUS_SEGERA if sisa <= HARI_PENGINGAT else STATUS_AKTIF


def _berakhir_terakhir(kon, akun_id: str, siswa_id: int, kode_paket: str) -> Optional[str]:
    baris = kon.execute(_SQL_BERAKHIR, (akun_id, siswa_id, kode_paket)).fetchone()
    return baris[0]


def _masa_paket(kon, akun_id: str, siswa_id: int, paket: katalog.PaketBelajar, kini: str,
                akhir_semua_paket: Optional[str]) -> Optional[MasaPaket]:
    """Masa satu paket, atau None bila tak ada akses, ada order terbuka, atau anak punya paket lain yang lebih akhir."""
    if ks.order_terbuka(kon, akun_id, siswa_id, paket.kode, kini) is not None:
        return None
    berakhir = _berakhir_terakhir(kon, akun_id, siswa_id, paket.kode)
    if berakhir is None or berakhir < akhir_semua_paket:
        return None
    sisa = _sisa_hari(berakhir, kini)
    return MasaPaket(paket.kode, paket.nama, berakhir, sisa, _status(sisa))


def tagihan_belum_dibayar(kon, akun_id: str, siswa_id: int, sekarang) -> Tuple[TagihanBelumBayar, ...]:
    """Tagihan TERBARU milik akun untuk anak ini bila belum ada bukti menunggu: belum_bayar atau ditolak (boleh unggah ulang).

    Satu elemen paling banyak: setelah ganti paket, tagihan lama masih terbuka sampai habis tetapi tidak diingatkan.

    Jendela bayar yang sudah lewat tidak terbuka, jadi tidak ikut. Tanpa tulis; akun selalu ikut di kueri.
    """
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    kini = k.ke_baku(sekarang)
    for o, _fakta, status in ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini):     # terbaru dulu
        if status in (k.STATUS_BELUM_BAYAR, k.STATUS_DITOLAK):
            return (TagihanBelumBayar(o["paket"], katalog.ambil(o["paket"]).nama, o["kedaluwarsa"], status),)
        return ()      # tagihan terbaru sudah punya bukti menunggu: tagihan lama (setelah ganti paket) tidak diingatkan
    return ()


def masa_paket_anak(kon, akun_id: str, siswa_id: int, sekarang) -> Tuple[MasaPaket, ...]:
    """Masa tiap paket katalog yang punya akses milik `akun_id` untuk `siswa_id` dan tidak sedang diperpanjang."""
    d.periksa_koneksi(kon)
    d.periksa_akun_id(akun_id)
    k.periksa_siswa_id(siswa_id)
    kini = k.ke_baku(sekarang)
    akhir_semua = kon.execute(_SQL_BERAKHIR_SEMUA_PAKET, (akun_id, siswa_id)).fetchone()[0]
    masa = (_masa_paket(kon, akun_id, siswa_id, paket, kini, akhir_semua) for paket in katalog.DAFTAR_PAKET)
    return tuple(m for m in masa if m is not None)

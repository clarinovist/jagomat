"""Harga admin produk kelas (Private, Mini Class) dan Peta: nilai aktif, ubah harga, dan riwayat.

Akses data tanpa tampilan. Tabel `harga_*` (schema_harga) opt-in: selama belum dipasang, nilai aktif = HARGA_AWAL
(gagal aman, tidak melempar); skema yang ada tetapi rusak melempar ValueError (tidak menagih dari data tak jelas).
Fungsi baca menerima koneksi dan hanya SELECT. Tidak menyentuh tabel kelas_*. Harga Latihan Harian bukan di sini.
Irisan ini belum dipakai alur katalog atau tagihan.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

import admin_store_core
import pesanan_dasar
import schema_harga
from harga_aturan import (  # noqa: F401  (konstanta dan aturan turunan, diekspor untuk pemanggil)
    ALLOW_UBAH, BATAS_OLEH, HARGA_MAKS, HARGA_MIN, KELIPATAN, KODE_PRODUK, PERTEMUAN_PER_BULAN,
    SISA_PERTEMUAN_MIN, nominal_proporsional,
)
from harga_validasi import periksa_kode_produk, validasi_harga

# Nilai awal sebelum admin pernah mengubah harga (baris tak ada di harga_produk = nilai ini).
HARGA_AWAL = MappingProxyType({
    "private": 640_000,
    "mini": 300_000,
    "peta": pesanan_dasar.RUPIAH_PAKET,
})
BATAS_RIWAYAT_BAWAAN = 50
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"


@dataclass(frozen=True)
class HasilUbahHarga:
    kode: str
    lama: int
    baru: int


@dataclass(frozen=True)
class RiwayatHarga:
    id: int
    kode: str
    lama: Optional[int]
    baru: int
    oleh: str
    waktu: str


class HargaBelumTerpasang(admin_store_core.StoreBelumSiap):
    """Skema harga_* belum dipasang; ubah harga ditolak tanpa menulis apa pun."""


class KonflikHarga(RuntimeError):
    """Harga aktif sudah berubah sejak admin melihatnya; tidak ada yang ditulis."""


def periksa_oleh(oleh):
    if type(oleh) is not str or not oleh.strip() or len(oleh) > BATAS_OLEH or not oleh.isprintable():
        raise ValueError("oleh harus teks terlihat 1 sampai %d karakter" % BATAS_OLEH)
    return oleh


def periksa_waktu(sekarang):
    try:
        datetime.strptime(sekarang, FORMAT_WAKTU)
    except (TypeError, ValueError):
        raise ValueError("waktu harus format UTC YYYY-MM-DDTHH:MM:SS") from None
    return sekarang


def _baris_tersimpan(kon) -> dict:
    if not schema_harga.validasi(kon):
        return {}
    return {baris[0]: int(baris[1]) for baris in kon.execute("SELECT kode, rupiah FROM harga_produk")}


def harga_semua(kon) -> Mapping[str, int]:
    """Harga aktif ketiga produk (tak-berubah); baris yang tak ada memakai HARGA_AWAL."""
    tersimpan = _baris_tersimpan(kon)
    return MappingProxyType({kode: tersimpan.get(kode, HARGA_AWAL[kode]) for kode in KODE_PRODUK})


def harga_aktif(kon, kode) -> int:
    periksa_kode_produk(kode)
    return harga_semua(kon)[kode]


def _ubah_dalam_transaksi(kon, kode, rupiah_baru, diharapkan, oleh, waktu) -> HasilUbahHarga:
    if not schema_harga.validasi(kon):
        raise HargaBelumTerpasang("harga admin belum dipasang")
    aktif = harga_semua(kon)
    validasi_harga(kode, rupiah_baru, {p: v for p, v in aktif.items() if p != kode})
    lama_aktif = aktif[kode]
    if lama_aktif != diharapkan:
        raise KonflikHarga("harga aktif %d tidak sama dengan yang diharapkan %d" % (lama_aktif, diharapkan))
    # Lama di riwayat = baris tersimpan sebelumnya (None bila belum pernah diubah), bukan nilai awal.
    baris_sebelumnya = _baris_tersimpan(kon).get(kode)
    kon.execute(
        "INSERT INTO harga_produk(kode, rupiah, diubah, diubah_oleh) VALUES(?,?,?,?) "
        "ON CONFLICT(kode) DO UPDATE SET rupiah=excluded.rupiah, diubah=excluded.diubah, "
        "diubah_oleh=excluded.diubah_oleh",
        (kode, rupiah_baru, waktu, oleh))
    kon.execute(
        "INSERT INTO harga_riwayat(kode, lama, baru, oleh, waktu) VALUES(?,?,?,?,?)",
        (kode, baris_sebelumnya, rupiah_baru, oleh, waktu))
    return HasilUbahHarga(kode, lama_aktif, rupiah_baru)


def ubah_harga(path, kode, rupiah_baru, rupiah_lama_diharapkan, oleh, sekarang) -> HasilUbahHarga:
    """Ubah harga satu produk dalam satu transaksi admin; `sekarang` UTC disuntik agar tes deterministik."""
    import admin_store  # diimpor di sini agar jalur baca (harga_aktif, riwayat) tetap ringan

    pelaku = periksa_oleh(oleh)
    waktu = periksa_waktu(sekarang)
    with admin_store._transaksi(path) as kon:
        return _ubah_dalam_transaksi(kon, kode, rupiah_baru, rupiah_lama_diharapkan, pelaku, waktu)


def riwayat(kon, batas=BATAS_RIWAYAT_BAWAAN) -> Tuple[RiwayatHarga, ...]:
    """Catatan perubahan terbaru dulu; kosong bila skema belum dipasang."""
    if type(batas) is not int or batas < 1:
        raise ValueError("batas riwayat harus bilangan bulat positif")
    if not schema_harga.validasi(kon):
        return ()
    baris = kon.execute(
        "SELECT id, kode, lama, baru, oleh, waktu FROM harga_riwayat ORDER BY id DESC LIMIT ?", (batas,))
    return tuple(RiwayatHarga(*tuple(r)) for r in baris.fetchall())

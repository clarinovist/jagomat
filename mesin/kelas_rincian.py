"""Rincian nominal tagihan kelas untuk satu pembeli: deposit Peta aktif (SELECT saja).

Nominal HANYA dihitung di server dari katalog (`paket_belajar_katalog.hitung_rincian`) dan deposit yang dibaca di
sini; tidak ada angka dari form.

Deposit aktif = order Peta MILIK akun pembeli untuk anak ini (`pesanan_order` UNIQUE per anak; `akun_id` wajib sama)
yang keadaan purna-nya `aktif` (lunas, tidak direfund, tidak ditahan, belum dipakai, belum 90 hari). Purna belum
terpasang = tidak ada deposit. Deposit yang sudah dipegang tagihan LAIN anak ini yang masih terbuka tidak dipotongkan
dua kali (pemakaian ledger tetap sekali, dicatat saat lunas).

Diskon anak kedua sudah dihapus (25 Nov 2026): tidak ada lagi penanda keluarga yang memengaruhi harga.
"""
from __future__ import annotations

from typing import Optional, Tuple

import harga
import kelas_status as ks
import paket_belajar_katalog as katalog
import purna


def _peta_milik(kon, akun_id: str, siswa_id: int) -> Optional[str]:
    baris = kon.execute("SELECT order_id FROM pesanan_order WHERE siswa_id=? AND akun_id=?",
                        (siswa_id, akun_id)).fetchone()
    return None if baris is None else baris["order_id"]


def deposit_aktif(kon, akun_id: str, siswa_id: int, kini: str) -> Optional[str]:
    """order_id Peta yang deposit-nya aktif untuk akun dan anak ini pada `kini`, atau None."""
    if not purna.terpasang(kon):
        return None
    order_id = _peta_milik(kon, akun_id, siswa_id)
    if order_id is None:
        return None
    return order_id if purna.keadaan(kon, order_id, kini).voucher == purna.VOUCHER_AKTIF else None


def _deposit_dipegang_lain(kon, akun_id: str, siswa_id: int, kode_paket: str, deposit_order: str, kini: str) -> bool:
    for order, _, _ in ks.order_terbuka_siswa(kon, akun_id, siswa_id, kini):
        if order["paket"] == kode_paket:
            continue
        if ks.baris_tagihan(kon, order["id"])["deposit_order_id"] == deposit_order:
            return True
    return False


def rincian_untuk(kon, akun_id: str, siswa_id: int, kode_paket: str, kini: str) -> Tuple[katalog.Rincian, Optional[str]]:
    """(rincian, order_id Peta yang dipotongkan atau None) untuk tagihan BARU paket ini pada `kini`.

    Harga bulanan dibaca dari harga aktif admin (`harga.harga_aktif`, koneksi yang sama). Galat skema harga
    dibiarkan naik: tagihan baru gagal tertutup, tidak memakai harga katalog diam-diam.
    """
    deposit = deposit_aktif(kon, akun_id, siswa_id, kini)
    if deposit is not None and _deposit_dipegang_lain(kon, akun_id, siswa_id, kode_paket, deposit, kini):
        deposit = None
    harga_paket = harga.harga_aktif(kon, kode_paket)
    rincian = katalog.hitung_rincian(kode_paket, deposit_aktif=deposit is not None, harga_paket=harga_paket)
    return rincian, (deposit if rincian.potongan_deposit > 0 else None)

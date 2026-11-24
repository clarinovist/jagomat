"""Rincian nominal tagihan kelas untuk satu pembeli: deposit Peta aktif dan status anak kedua (SELECT saja).

Nominal HANYA dihitung di server dari katalog (`paket_belajar_katalog.hitung_rincian`) dan dua fakta yang dibaca di sini;
tidak ada angka dari form.

Deposit aktif = order Peta MILIK akun pembeli untuk anak ini (`pesanan_order` UNIQUE per anak; `akun_id` wajib sama)
yang keadaan purna-nya `aktif` (lunas, tidak direfund, tidak ditahan, belum dipakai, belum 90 hari). Purna belum
terpasang = tidak ada deposit. Deposit yang sudah dipegang tagihan LAIN anak ini yang masih terbuka tidak dipotongkan
dua kali (pemakaian ledger tetap sekali, dicatat saat lunas).

Anak kedua = anak tertaut keluarga (`kelas_keluarga`, oleh admin) yang punya anggota lain dengan akses kelas yang
MULAI lebih dulu, DAN anak ini tidak membayar Peta sendiri (order Peta lunas dan tidak direfund, walau deposit sudah
dipakai atau kedaluwarsa; keputusan Pemilik 24 Nov 2026: anak kedua tidak membayar Peta). Deposit menang atas
diskon bila keduanya berlaku (`hitung_rincian`); keduanya tidak pernah menumpuk.
"""
from __future__ import annotations

from typing import Optional, Tuple

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


def membayar_peta_sendiri(kon, siswa_id: int, kini: str) -> bool:
    """True bila anak ini punya order Peta lunas yang tidak direfund (akun mana pun; deposit boleh sudah terpakai)."""
    baris = kon.execute("SELECT order_id FROM pesanan_order WHERE siswa_id=?", (siswa_id,)).fetchone()
    if baris is None:
        return False
    keadaan = purna.keadaan(kon, baris["order_id"], kini)
    return keadaan.lunas and not keadaan.direfund


def _mulai_pertama(kon, sql: str, params: tuple) -> Optional[str]:
    return kon.execute(sql, params).fetchone()[0]


def anggota_lain_mulai_lebih_dulu(kon, siswa_id: int) -> bool:
    """True bila anak tertaut keluarga dan ada anggota lain yang akses kelasnya mulai lebih awal dari akses pertama anak ini.

    Anak ini belum punya akses = mulai 'sekarang', jadi akses anggota lain mana pun yang sudah ada lebih dulu.
    Mulai yang persis sama tidak dihitung lebih dulu (tidak ada yang menjadi anak kedua).
    """
    keluarga = kon.execute("SELECT keluarga_id FROM kelas_keluarga WHERE siswa_id=?", (siswa_id,)).fetchone()
    if keluarga is None:
        return False
    lain = _mulai_pertama(
        kon, "SELECT MIN(a.mulai) FROM kelas_akses a JOIN kelas_keluarga f ON f.siswa_id=a.siswa_id "
             "WHERE f.keluarga_id=? AND a.siswa_id<>?", (keluarga["keluarga_id"], siswa_id))
    if lain is None:
        return False
    sendiri = _mulai_pertama(kon, "SELECT MIN(mulai) FROM kelas_akses WHERE siswa_id=?", (siswa_id,))
    return sendiri is None or lain < sendiri


def anak_kedua(kon, siswa_id: int, kini: str) -> bool:
    """Anak kedua: anggota lain keluarga mulai lebih dulu DAN anak ini tidak membayar Peta sendiri."""
    return anggota_lain_mulai_lebih_dulu(kon, siswa_id) and not membayar_peta_sendiri(kon, siswa_id, kini)


def rincian_untuk(kon, akun_id: str, siswa_id: int, kode_paket: str, kini: str) -> Tuple[katalog.Rincian, Optional[str]]:
    """(rincian, order_id Peta yang dipotongkan atau None) untuk tagihan BARU paket ini pada `kini`."""
    deposit = deposit_aktif(kon, akun_id, siswa_id, kini)
    if deposit is not None and _deposit_dipegang_lain(kon, akun_id, siswa_id, kode_paket, deposit, kini):
        deposit = None
    rincian = katalog.hitung_rincian(kode_paket, deposit_aktif=deposit is not None,
                                     anak_kedua=anak_kedua(kon, siswa_id, kini))
    return rincian, (deposit if rincian.potongan_deposit > 0 else None)

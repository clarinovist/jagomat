"""Katalog dan kalkulasi paket v2 murni; bukan checkout atau pemberian hak akses.

Input billing/promo berasal snapshot service terverifikasi, bukan browser. Tidak
membaca DB/env/clock, tidak mengubah tarif v1, dan tidak mengaktifkan kampanye.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

VERSI = "paket-jago-v2"
WIB = timezone(timedelta(hours=7))
DURASI_COBA = 30 * 24 * 60 * 60
DURASI_REFUND = 7 * 24 * 60 * 60
BATAS_RUPIAH = 10_000_000
BATAS_WAKTU = 253_370_739_599  # datetime maksimum dalam WIB.
TAMBAHAN_BULANAN = 10_000
TAMBAHAN_TAHUNAN = 100_000


@dataclass(frozen=True)
class Kuota:
    balasan: int
    foto: int


KUOTA_COBA = Kuota(10, 2)


@dataclass(frozen=True)
class Paket:
    kode: str
    nama: str
    bulanan: int
    bulanan_promo: int
    tahunan: int
    tahunan_promo: int
    kuota: Kuota


PAKET: Tuple[Paket, ...] = (
    Paket("jago", "Jago", 29_000, 25_000, 290_000, 250_000, Kuota(0, 0)),
    Paket("jago_pro", "Jago Pro", 59_000, 49_000, 590_000, 490_000, Kuota(50, 5)),
)


def _bilangan(nilai, minimum=0, maksimum=BATAS_RUPIAH):
    if type(nilai) is not int or not minimum <= nilai <= maksimum:
        raise ValueError("bilangan paket tidak sah")
    return nilai


def _waktu(nilai):
    return _bilangan(nilai, maksimum=BATAS_WAKTU)


def _versi(versi):
    if versi != VERSI:
        raise ValueError("versi paket tidak dikenal")


def ambil_paket(kode, *, versi=VERSI):
    _versi(versi)
    for paket in PAKET:
        if type(kode) is str and paket.kode == kode:
            return paket
    raise ValueError("paket tidak dikenal")


def jumlah_bulan(penagihan):
    if type(penagihan) is not str or penagihan not in ("bulanan", "tahunan"):
        raise ValueError("periode penagihan tidak dikenal")
    return 1 if penagihan == "bulanan" else 12


@dataclass(frozen=True)
class Penawaran:
    """Hasil kalkulasi, belum invoice/bukti eligibility/grant."""
    versi: str
    paket: str
    penagihan: str
    jumlah_profil: int
    promo: bool
    rupiah: int
    normal: int


def penawaran(kode, penagihan, jumlah_profil, *, peserta_promo,
              periode_dibayar, versi=VERSI):
    """Promo tiga bulanan atau satu tahunan; tambahan profil tidak didiskon lagi.

    periode_dibayar menghitung periode yang sudah dibayar pada pilihan penagihan
    tetap. Peralihan bulanan/tahunan perlu kebijakan service; fungsi ini bukan
    pemberi eligibility dan tidak boleh dipakai untuk mereset jatah promo akun.
    """
    paket = ambil_paket(kode, versi=versi)
    bulan = jumlah_bulan(penagihan)
    _bilangan(jumlah_profil, 1)
    _bilangan(periode_dibayar)
    if type(peserta_promo) is not bool:
        raise ValueError("eligibility promo tidak sah")
    promo = peserta_promo and periode_dibayar < (3 if bulan == 1 else 1)
    normal = paket.bulanan if bulan == 1 else paket.tahunan
    khusus = paket.bulanan_promo if bulan == 1 else paket.tahunan_promo
    tambahan = (jumlah_profil - 1) * (TAMBAHAN_BULANAN if bulan == 1 else TAMBAHAN_TAHUNAN)
    total_normal = _bilangan(normal + tambahan, 1)
    rupiah = _bilangan((khusus if promo else normal) + tambahan, 1)
    return Penawaran(VERSI, paket.kode, penagihan, jumlah_profil, promo, rupiah, total_normal)


def batas_bulan(jangkar_mulai, urutan_bulan):
    """Geser dari jangkar asli WIB, bukan menambah 30/365 hari atau tanggal terjepit."""
    _waktu(jangkar_mulai)
    _bilangan(urutan_bulan, 0, 120_000)
    awal = datetime.fromtimestamp(jangkar_mulai, WIB)
    indeks = awal.year * 12 + awal.month - 1 + urutan_bulan
    tahun, bulan0 = divmod(indeks, 12)
    if not 1 <= tahun <= 9999:
        raise ValueError("batas kalender di luar jangkauan")
    hari = min(awal.day, monthrange(tahun, bulan0 + 1)[1])
    akhir = awal.replace(year=tahun, month=bulan0 + 1, day=hari)
    return _waktu(int(akhir.timestamp()))


def akhir_periode(jangkar_mulai, penagihan, *, urutan=1):
    """Akhir periode ke-n dari jangkar awal yang sama, termasuk perpanjangan tahunan."""
    bulan = jumlah_bulan(penagihan)
    _bilangan(urutan, 1, 10_000)
    return batas_bulan(jangkar_mulai, urutan * bulan)


def akhir_coba(mulai):
    return _waktu(_waktu(mulai) + DURASI_COBA)


@dataclass(frozen=True)
class JendelaKuota:
    mulai: int
    akhir: int
    kuota: Kuota


def jendela_kuota(kode, penagihan, jangkar_mulai, *, sekarang, urutan=1,
                  versi=VERSI) -> Optional[JendelaKuota]:
    """Jendela satu grant; bukan cek kepemilikan, sisa pemakaian, atau reserve AI.

    Penagihan tahunan tetap memakai 12 jendela satu bulan. Urutan grant dari
    jangkar asli menjaga tanggal setelah bulan pendek/tahun kabisat. Clock di luar
    grant tidak memperoleh kuota. Caller memvalidasi grant dan pencabutannya.
    """
    paket = ambil_paket(kode, versi=versi)
    bulan = jumlah_bulan(penagihan)
    _waktu(sekarang)
    _bilangan(urutan, 1, 10_000)
    awal_indeks = (urutan - 1) * bulan
    mulai = batas_bulan(jangkar_mulai, awal_indeks)
    akhir = akhir_periode(jangkar_mulai, penagihan, urutan=urutan)
    if not mulai <= sekarang < akhir:
        return None
    for indeks in range(awal_indeks, awal_indeks + bulan):
        kiri, kanan = batas_bulan(jangkar_mulai, indeks), batas_bulan(jangkar_mulai, indeks + 1)
        if kiri <= sekarang < kanan:
            return JendelaKuota(kiri, kanan, paket.kuota)
    raise ValueError("jendela kuota tidak ditemukan")


def jendela_coba(mulai, *, sekarang) -> Optional[JendelaKuota]:
    _waktu(sekarang)
    akhir = akhir_coba(mulai)
    return JendelaKuota(mulai, akhir, KUOTA_COBA) if mulai <= sekarang < akhir else None


def status_refund(penagihan, dibayar_pada, *, diajukan_pada):
    """Nilai jendela pengajuan saja, bukan transfer dana/pencabutan akses.

    dibayar_pada harus timestamp settlement terverifikasi. Bukti waktu belum ada
    atau clock pengajuan mendahului settlement harus ditinjau, bukan ditolak otomatis.
    """
    bulan = jumlah_bulan(penagihan)
    _waktu(diajukan_pada)
    if dibayar_pada is not None:
        _waktu(dibayar_pada)
    if bulan != 12:
        return "bukan_tahunan"
    if dibayar_pada is None or diajukan_pada < dibayar_pada:
        return "perlu_diperiksa"
    akhir = _waktu(dibayar_pada + DURASI_REFUND)
    return "dalam_jendela" if diajukan_pada < akhir else "di_luar_jendela"

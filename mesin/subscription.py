"""Domain langganan murni; belum terhubung ke registrasi, router, atau paywall.

Waktu epoch UTC diinjeksi caller. Bulan kalender memakai WIB dan tanggal jangkar
asli; tidak membaca clock sistem, akun, consent, credential atau data belajar.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Optional, Tuple

WIB = timezone(timedelta(hours=7))
DURASI_TRIAL = 30 * 24 * 60 * 60
DURASI_KAMPANYE = 8 * 7 * 24 * 60 * 60
VERSI_ATURAN = "langganan-v1"
BATAS_RUPIAH = 10_000_000


class FiturNonaktif(RuntimeError):
    """Permukaan belum diaktifkan; jangan melakukan efek samping."""


@dataclass(frozen=True)
class Sakelar:
    fondasi: bool = False
    buat_pembayaran: bool = False
    rekonsiliasi: bool = False
    penegakan: bool = False

    def wajib(self, nama):
        if nama not in ("fondasi", "buat_pembayaran", "rekonsiliasi", "penegakan"):
            raise ValueError("sakelar tidak dikenal")
        if getattr(self, nama) is not True:
            raise FiturNonaktif("fitur langganan nonaktif")


SAKELAR = Sakelar()


def bilangan(nilai, minimum=0, maksimum=BATAS_RUPIAH):
    if type(nilai) is not int or not minimum <= nilai <= maksimum:
        raise ValueError("bilangan langganan tidak sah")
    return nilai


def waktu(nilai):
    # Batas datetime tetap sama di Python 3.9/3.12 dan lintas platform.
    return bilangan(nilai, 0, 253_370_739_599)


def identitas(nilai, jenis):
    pola = {"akun": r"akun_[0-9a-f]{32}", "invoice": r"inv_[0-9a-f]{32}",
            "operasi": r"[A-Za-z0-9_-]{8,46}"}
    if type(nilai) is not str or re.fullmatch(pola[jenis], nilai) is None:
        raise ValueError("identitas langganan tidak sah")
    return nilai


def profil_kanonis(profil):
    if type(profil) is not tuple:
        raise ValueError("cakupan harus tuple profil")
    for item in profil:
        bilangan(item, 1, 2**63 - 1)
    if len(set(profil)) != len(profil):
        raise ValueError("profil duplikat")
    return tuple(sorted(profil))


def harga(jumlah_profil, *, peserta_promo, periode_dibayar):
    """Nol profil tidak boleh membuat charge, termasuk biaya dasar orang tua."""
    bilangan(jumlah_profil, 1)
    bilangan(periode_dibayar)
    if type(peserta_promo) is not bool:
        raise ValueError("eligibility tidak sah")
    promo = peserta_promo and periode_dibayar < 3
    dasar, per_anak = (10_000, 5_000) if promo else (25_000, 10_000)
    total = dasar + jumlah_profil * per_anak
    bilangan(total, 1)
    return total


@dataclass(frozen=True)
class Enrollment:
    akun_id: str
    mulai: int
    peserta_promo: bool
    versi: str = VERSI_ATURAN

    def __post_init__(self):
        identitas(self.akun_id, "akun")
        waktu(self.mulai)
        waktu(self.mulai + DURASI_TRIAL)
        if type(self.peserta_promo) is not bool or self.versi != VERSI_ATURAN:
            raise ValueError("enrollment tidak sah")

    @property
    def akhir_trial(self):
        return self.mulai + DURASI_TRIAL


@dataclass(frozen=True)
class Periode:
    mulai: int
    akhir: int
    jangkar: int

    def __post_init__(self):
        waktu(self.mulai)
        waktu(self.akhir)
        bilangan(self.jangkar, 1, 31)
        if self.akhir <= self.mulai:
            raise ValueError("periode tidak sah")


def bulan_berikutnya(mulai, jangkar):
    waktu(mulai)
    bilangan(jangkar, 1, 31)
    tanggal = datetime.fromtimestamp(mulai, WIB)
    tahun, bulan = tanggal.year + (tanggal.month == 12), tanggal.month % 12 + 1
    hari = min(jangkar, monthrange(tahun, bulan)[1])
    return waktu(int(tanggal.replace(year=tahun, month=bulan, day=hari).timestamp()))


def periode_baru(*, sekarang, enrollment, sebelumnya=None):
    """Bayar awal memperpanjang; jeda memulai jangkar baru tanpa reset promo."""
    waktu(sekarang)
    if sekarang < enrollment.mulai:
        raise ValueError("clock mendahului enrollment")
    batas = sebelumnya.akhir if sebelumnya else enrollment.akhir_trial
    mulai = max(sekarang, batas)
    jangkar = (sebelumnya.jangkar if sebelumnya and sekarang <= batas
               else datetime.fromtimestamp(mulai, WIB).day)
    return Periode(mulai, bulan_berikutnya(mulai, jangkar), jangkar)


@dataclass(frozen=True)
class Grant:
    akun_id: str
    invoice_id: str
    urutan: int
    periode: Periode
    profil: Tuple[int, ...]
    promo: bool

    def __post_init__(self):
        identitas(self.akun_id, "akun")
        identitas(self.invoice_id, "invoice")
        bilangan(self.urutan, 1)
        if not self.profil or profil_kanonis(self.profil) != self.profil:
            raise ValueError("cakupan grant tidak sah")
        if type(self.promo) is not bool or not isinstance(self.periode, Periode):
            raise ValueError("promo/periode grant tidak sah")


@dataclass(frozen=True)
class Akses:
    status: str
    akhir: Optional[int] = None
    profil: Tuple[int, ...] = ()


def akses(enrollment, grants=(), *, sekarang, terverifikasi=True):
    """Proyeksi, bukan enforcement. Invoice pending tidak menjadi input akses."""
    if terverifikasi is not True or not isinstance(enrollment, Enrollment):
        return Akses("belum_terverifikasi")
    try:
        waktu(sekarang)
        if sekarang < enrollment.mulai:
            return Akses("belum_terverifikasi")
        urut = sorted(grants, key=lambda g: g.urutan)
        for i, grant in enumerate(urut, 1):
            if (grant.akun_id != enrollment.akun_id or grant.urutan != i
                    or grant.promo != (enrollment.peserta_promo and i <= 3)
                    or grant.periode.mulai < enrollment.akhir_trial
                    or grant.periode.akhir != bulan_berikutnya(grant.periode.mulai, grant.periode.jangkar)
                    or (i > 1 and grant.periode.mulai < urut[i-2].periode.akhir)):
                return Akses("belum_terverifikasi")
        for grant in urut:
            if grant.periode.mulai <= sekarang < grant.periode.akhir:
                return Akses("promo" if grant.promo else "paid", grant.periode.akhir, grant.profil)
        if sekarang < enrollment.akhir_trial:
            return Akses("trial", enrollment.akhir_trial)
        return Akses("expired")
    except (ValueError, TypeError, AttributeError, OverflowError):
        return Akses("belum_terverifikasi")


@dataclass(frozen=True)
class Pembayaran:
    """Bukti minimum dari adapter tepercaya, bukan DTO callback/browser mentah."""
    provider: str
    transaksi_id: str
    invoice_id: str
    akun_id: str
    rupiah: int
    currency: str
    channel: str
    merchant: str
    status: str
    terverifikasi: bool


def pembayaran_cocok(bukti, invoice, akun_id):
    """Owner berasal principal/service terjaga, bukan hidden input pengguna."""
    return (
        bukti.terverifikasi is True and bukti.status == "settlement"
        and bukti.invoice_id == invoice["invoice_id"]
        and bukti.akun_id == akun_id == invoice["akun_id"]
        and type(bukti.rupiah) is int and bukti.rupiah == invoice["rupiah"]
        and bukti.currency == "IDR" and bukti.channel == invoice["channel"]
        and bukti.provider == invoice["provider"] and bukti.merchant == invoice["merchant"]
    )

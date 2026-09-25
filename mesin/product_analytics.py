"""Metrik uji coba murni: populasi matang dan ketidakpastian tetap terlihat."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Tuple

HARI = 86400
WIB = timezone(timedelta(hours=7))
VERSI = 'kpi-v1'
CONSENT = 'analitik-keluarga-v1'
SURVEI = 'manfaat-v1'
KODE = ('latihan_dikirim', 'lembar_soal_disajikan', 'panduan_hasil_disajikan')
SUMBER = ('rekomendasi', 'pencarian', 'komunitas', 'iklan', 'lainnya', 'tidak_diketahui')


@dataclass(frozen=True)
class Peserta:
    """DTO sementara reducer tanpa nama/akun/anak atau jawaban bebas."""
    t0: int
    terlambat: bool
    aktivitas: Tuple[Tuple[str, str, int], ...]
    ditawari: bool = False
    jawaban: str = ''
    sumber: str = 'tidak_diketahui'


@dataclass(frozen=True)
class Metrik:
    kode: str
    pembilang: int
    penyebut: int
    target: int
    status: str
    kecil: bool
    respons: int = 0
    penawaran: int = 0


@dataclass(frozen=True)
class Laporan:
    metrik: Tuple[Metrik, ...]
    peserta: int
    matang: int
    menunggu: int
    terlambat: int
    minggu: Tuple[Tuple[int, int, int, int], ...]
    kualitas: bool


def waktu(nilai):
    if type(nilai) is not int or not 0 <= nilai <= 253370739599:
        raise ValueError('waktu analitik tidak sah')
    return nilai


def jendela(t0, kini):
    umur = waktu(kini) - waktu(t0)
    if not 0 <= umur < 30 * HARI:
        return None
    return 1 if umur < 7 * HARI else 2 if umur < 14 * HARI else 3


def akhir_retensi_agregat(epoch):
    """Dua belas bulan kalender WIB; tahun kabisat tidak memperpanjang TTL."""
    tanggal = datetime.fromtimestamp(waktu(epoch), WIB)
    tahun = tanggal.year + 1
    tujuan = tanggal.replace(year=tahun, day=min(tanggal.day, monthrange(tahun,tanggal.month)[1]))
    return int(tujuan.timestamp())


def hari_wib(kini):
    return datetime.fromtimestamp(waktu(kini), WIB).date().isoformat()


def _aktif(p, minggu):
    return any(j == minggu and (minggu != 1 or k != 'panduan_hasil_disajikan')
               for _, k, j in p.aktivitas)


def hitung(peserta, *, mulai, sekarang, lengkap):
    """Retensi utama memakai semua peserta matang, bukan hanya yang aktivasi."""
    waktu(mulai)
    waktu(sekarang)
    sah = tuple(p for p in peserta if mulai <= p.t0 < mulai + 56 * HARI
                and p.t0 <= sekarang)
    matang = tuple(p for p in sah if not p.terlambat and sekarang >= p.t0 + 14 * HARI)
    aktivasi = sum(_aktif(p, 1) for p in matang)
    kembali = sum(_aktif(p, 1) and _aktif(p, 2) for p in matang)
    ditawari = sum(p.ditawari for p in matang)
    jawab = sum(bool(p.jawaban) for p in matang)
    ya = sum(p.jawaban == 'ya' for p in matang)
    organik = tuple(p for p in matang if p.t0 >= mulai + 28 * HARI and _aktif(p, 1))
    angka_organik = sum(p.sumber in ('rekomendasi', 'pencarian') for p in organik)
    def kartu(kode, n, den, target, *, survei=False):
        if not lengkap:
            status = 'Data belum lengkap'
        elif not den:
            status = 'Belum matang' if any(not p.terlambat for p in sah) and not matang else 'Belum ada data'
        elif survei and (not ditawari or jawab * 100 < ditawari * 40):
            status = 'Respons belum cukup'
        else:
            status = 'Target tercapai' if n * 100 >= den * target else 'Di bawah target'
        return Metrik(kode, n, den, target, status, 0 < den < 5,
                      jawab if survei else 0, ditawari if survei else 0)
    minggu = []
    for i in range(8):
        grup = tuple(p for p in matang if mulai + i*7*HARI <= p.t0 < mulai + (i+1)*7*HARI)
        # Tidak ada drill-down atau pecahan kelompok kecil pada DTO dashboard.
        if len(grup) >= 5:
            minggu.append((i+1, len(grup), sum(_aktif(p,1) for p in grup),
                           sum(_aktif(p,1) and _aktif(p,2) for p in grup)))
    return Laporan((kartu('aktivasi',aktivasi,len(matang),60),
                    kartu('retensi',kembali,len(matang),25),
                    kartu('manfaat',ya,jawab,70,survei=True),
                    kartu('organik',angka_organik,len(organik),20)),
                   len(sah),len(matang),sum(not p.terlambat for p in sah)-len(matang),
                   sum(p.terlambat for p in sah),tuple(minggu),bool(lengkap))

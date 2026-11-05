"""Pemakaian guru: agregat per akun guru per minggu ISO (WIB), baca-saja.

Mengukur apakah guru memakai Jagomat berulang di minggu berbeda dan berapa lama
langkah-langkahnya, tanpa nama anak. Waktu di DB adalah jam dinding WIB naif
(`datetime('now', '+7 hours')`); nilai ber-zona dikonversi ke WIB dulu.

Modul ini hanya membaca (SELECT). SQL-nya sengaja di modul tersendiri agar sidik
jari kontrak persistensi rilis tidak berubah.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Dict, List, Optional, Sequence, Tuple

ZONA_WIB = timezone(timedelta(hours=7))
JUMLAH_MINGGU = 8
BATAS_WAJAR_MENIT = 24 * 60
URUTAN_SUMBER = ("tautan", "foto", "akun", "tanpa")

_SQL_SESI = """
SELECT sw.pemilik, s.dibuat, s.mulai, s.selesai, s.direview,
       s.dikonfirmasi_guru, ps.sumber
  FROM sesi s
  JOIN siswa sw ON sw.id = s.siswa_id
  LEFT JOIN pengiriman_sesi ps ON ps.sesi_id = s.id
 WHERE s.dibatalkan IS NULL
   AND sw.pemilik IS NOT NULL AND sw.pemilik <> ''
"""
_SQL_LAPORAN = """
SELECT sw.pemilik, l.diterbitkan
  FROM laporan_ortu l
  JOIN siswa sw ON sw.id = l.siswa_id
 WHERE l.diterbitkan IS NOT NULL
   AND sw.pemilik IS NOT NULL AND sw.pemilik <> ''
"""


@dataclass(frozen=True)
class MingguGuru:
    senin: date
    sesi_dibuat: int
    sesi_selesai: int
    sesi_dikonfirmasi: int


@dataclass(frozen=True)
class PemakaianGuru:
    pengguna: str
    minggu: Tuple[MingguGuru, ...]
    sesi_dibuat: int
    sesi_selesai: int
    sesi_dikonfirmasi: int
    minggu_aktif: int
    median_kerja_menit: Optional[float]
    median_jeda_konfirmasi_menit: Optional[float]
    median_tinjau_menit: Optional[float]
    sumber: Tuple[Tuple[str, int], ...]
    laporan_terbit: int


def waktu_wib(nilai) -> Optional[datetime]:
    """Parse teks waktu menjadi datetime WIB naif; None bila kosong/rusak."""
    if not isinstance(nilai, str) or not nilai.strip():
        return None
    teks = nilai.strip()
    if teks.endswith(("Z", "z")):
        teks = teks[:-1] + "+00:00"
    try:
        hasil = datetime.fromisoformat(teks)
    except ValueError:
        return None
    if hasil.tzinfo is not None:
        hasil = hasil.astimezone(ZONA_WIB).replace(tzinfo=None)
    return hasil


def _senin(waktu: datetime) -> date:
    hari = waktu.date()
    return hari - timedelta(days=hari.weekday())


def minggu_senin(nilai) -> Optional[date]:
    """Senin minggu ISO (WIB) dari teks waktu; None bila tidak terbaca."""
    waktu = waktu_wib(nilai)
    return None if waktu is None else _senin(waktu)


def _menit(awal, akhir, *, batas: Optional[int]) -> Optional[float]:
    a, b = waktu_wib(awal), waktu_wib(akhir)
    if a is None or b is None:
        return None
    menit = (b - a).total_seconds() / 60
    if menit < 0 or (batas is not None and menit > batas):
        return None
    return menit


def _median(nilai: Sequence[Optional[float]]) -> Optional[float]:
    ada = [x for x in nilai if x is not None]
    return float(median(ada)) if ada else None


def _jendela(sekarang: datetime, jumlah: int) -> Tuple[date, ...]:
    akhir = _senin(sekarang)
    return tuple(akhir - timedelta(weeks=jumlah - 1 - i) for i in range(jumlah))


def _hitung_guru(pengguna, baris, laporan, jendela) -> PemakaianGuru:
    awal = set(jendela)
    di_jendela = [r for r in baris if minggu_senin(r["dibuat"]) in awal]
    per_minggu: List[MingguGuru] = []
    for senin in jendela:
        sesi = [r for r in di_jendela if minggu_senin(r["dibuat"]) == senin]
        per_minggu.append(MingguGuru(
            senin, len(sesi),
            sum(1 for r in sesi if waktu_wib(r["selesai"])),
            sum(1 for r in sesi if waktu_wib(r["dikonfirmasi_guru"])),
        ))
    sumber: Dict[str, int] = {k: 0 for k in URUTAN_SUMBER}
    for r in di_jendela:
        kunci = r["sumber"] if r["sumber"] in sumber else "tanpa"
        sumber[kunci] += 1
    return PemakaianGuru(
        pengguna=pengguna,
        minggu=tuple(per_minggu),
        sesi_dibuat=sum(m.sesi_dibuat for m in per_minggu),
        sesi_selesai=sum(m.sesi_selesai for m in per_minggu),
        sesi_dikonfirmasi=sum(m.sesi_dikonfirmasi for m in per_minggu),
        minggu_aktif=sum(1 for m in per_minggu if m.sesi_dibuat),
        median_kerja_menit=_median([
            _menit(r["mulai"], r["selesai"], batas=BATAS_WAJAR_MENIT) for r in di_jendela]),
        median_jeda_konfirmasi_menit=_median([
            _menit(r["selesai"], r["dikonfirmasi_guru"], batas=None) for r in di_jendela]),
        median_tinjau_menit=_median([
            _menit(r["direview"], r["dikonfirmasi_guru"], batas=BATAS_WAJAR_MENIT)
            for r in di_jendela]),
        sumber=tuple((k, sumber[k]) for k in URUTAN_SUMBER),
        laporan_terbit=sum(1 for d in laporan if minggu_senin(d) in awal),
    )


def ambil_pemakaian(kon, *, sekarang: Optional[datetime] = None,
                    jumlah_minggu: int = JUMLAH_MINGGU) -> List[PemakaianGuru]:
    """Pemakaian per guru pemilik anak, urut nama; hanya membaca."""
    sekarang = sekarang or datetime.now(ZONA_WIB).replace(tzinfo=None)
    jendela = _jendela(sekarang, jumlah_minggu)
    sesi: Dict[str, list] = {}
    for baris in kon.execute(_SQL_SESI):
        sesi.setdefault(baris["pemilik"], []).append(baris)
    laporan: Dict[str, list] = {}
    for baris in kon.execute(_SQL_LAPORAN):
        laporan.setdefault(baris["pemilik"], []).append(baris["diterbitkan"])
    pemilik = sorted(set(sesi) | set(laporan), key=str.casefold)
    return [
        _hitung_guru(p, sesi.get(p, []), laporan.get(p, []), jendela)
        for p in pemilik
    ]

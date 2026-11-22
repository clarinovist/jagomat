"""Paket Latihan Lomba sebagai konfigurasi (kode, bukan DB) dan fungsi murni seputar waktu paket.

Satu paket aktif (`PAKET_AKTIF`). Nilai paket mengatur durasi, jumlah soal, target harian, dan hitung mundur;
`lomba_sesi.paket_id` menyimpan `id`-nya (paket lama tetap terbaca). Tanpa akses DB; waktu selalu parameter.
WIB dipakai sebagai UTC+7 tetap, sama seperti `contest_format`.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from contest_format import OFFSET_WIB_DETIK

JUMLAH_SOAL_WAJIB = 10            # batas CHECK(nomor BETWEEN 1 AND 10) di skema lomba_soal
MAKS_TARGET_HARIAN = 5
DETIK_PER_HARI = 24 * 3600
DETIK_PER_MENIT = 60
BATAS_DETIK_ASAL_KUMPUL = 120     # sesi lebih singkat dari ini dianggap asal kumpul
BATAS_TERISI_ASAL_KUMPUL = 3      # atau terisi kurang dari ini
_NOL_UTC = datetime.datetime(1970, 1, 1)
_TEKS_HARI_H = "Hari ini lombanya. Semangat!"


@dataclass(frozen=True)
class PaketLomba:
    id: str
    nama: str
    nama_pendek: str
    tanggal_lomba: datetime.date
    durasi_detik: int
    jumlah_soal: int
    jumlah_isian: int
    target_harian: int
    tampil_hitung_mundur: bool

    def __post_init__(self) -> None:
        if not self.id or not self.nama or not self.nama_pendek:
            raise ValueError("id, nama, dan nama pendek paket wajib diisi")
        if self.jumlah_soal != JUMLAH_SOAL_WAJIB:
            raise ValueError(f"jumlah soal paket harus {JUMLAH_SOAL_WAJIB} (batas skema DB)")
        if not 0 <= self.jumlah_isian < self.jumlah_soal:
            raise ValueError("jumlah isian harus 0 sampai kurang dari jumlah soal")
        if self.durasi_detik <= 0:
            raise ValueError("durasi paket harus lebih dari nol")
        if not 0 <= self.target_harian <= MAKS_TARGET_HARIAN:
            raise ValueError(f"target harian harus 0 sampai {MAKS_TARGET_HARIAN}")

    @property
    def jumlah_pg(self) -> int:
        return self.jumlah_soal - self.jumlah_isian

    @property
    def durasi_menit(self) -> int:
        return self.durasi_detik // DETIK_PER_MENIT


COREXIS_2026_L1 = PaketLomba(
    id="corexis_l1_matematika",
    nama="Grand Final Corexis 2026 · Matematika Level 1",
    nama_pendek="Grand Final Corexis",
    tanggal_lomba=datetime.date(2026, 12, 12),
    durasi_detik=900,
    jumlah_soal=10,
    jumlah_isian=2,
    target_harian=2,
    tampil_hitung_mundur=True,
)
PAKET_AKTIF = COREXIS_2026_L1


def awal_hari_wib(epoch: int) -> int:
    """Epoch detik awal hari kalender WIB (00:00 WIB) yang memuat `epoch`."""
    lokal = int(epoch) + OFFSET_WIB_DETIK
    return lokal - lokal % DETIK_PER_HARI - OFFSET_WIB_DETIK


def _tanggal_wib(epoch: int) -> datetime.date:
    return (_NOL_UTC + datetime.timedelta(seconds=int(epoch) + OFFSET_WIB_DETIK)).date()


def hari_menuju_lomba(paket: PaketLomba, sekarang_epoch: int) -> int:
    """Selisih hari kalender WIB sampai tanggal lomba; negatif bila sudah lewat."""
    return (paket.tanggal_lomba - _tanggal_wib(sekarang_epoch)).days


JUDUL_ANAK = "Mode Lomba"   # judul di sisi anak: umum, nama acara (nama_pendek) tidak ditampilkan ke anak


def teks_hitung_mundur(paket: PaketLomba, sekarang: int) -> str:
    """Kalimat hitung mundur; kosong bila dimatikan atau tanggal lomba sudah lewat."""
    if not paket.tampil_hitung_mundur:
        return ""
    hari = hari_menuju_lomba(paket, sekarang)
    if hari < 0:
        return ""
    if hari == 0:
        return _TEKS_HARI_H
    return f"Lomba tinggal {hari} hari lagi"


def asal_kumpul(waktu_terpakai_detik: int, terisi: int) -> bool:
    """Sesi selesai yang terlalu singkat atau hampir kosong; tidak ikut nilai terbaik, banding, dan target."""
    return waktu_terpakai_detik < BATAS_DETIK_ASAL_KUMPUL or terisi < BATAS_TERISI_ASAL_KUMPUL

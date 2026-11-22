"""Paket Latihan Lomba sebagai konfigurasi (kode, bukan DB) dan fungsi murni seputar waktu paket.

Satu paket aktif (`PAKET_AKTIF`). Nilai paket mengatur durasi, jumlah soal, target harian, dan hitung mundur;
dua mode sesi: Latihan (10 soal) dan Simulasi Lomba (35 soal, format lomba asli); `format_mode` merangkum satu mode;
`lomba_sesi.paket_id` menyimpan `id`-nya (paket lama tetap terbaca). Tanpa akses DB; waktu selalu parameter.
WIB dipakai sebagai UTC+7 tetap, sama seperti `contest_format`.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from contest_format import OFFSET_WIB_DETIK

JUMLAH_SOAL_WAJIB = 10            # Latihan: perakit 10 soal (contest_session) dirancang untuk angka ini
JUMLAH_SOAL_SIMULASI_WAJIB = 35   # Simulasi: sebaran topik tetap 9/9/8/9 (contest_session.SEBARAN_SIMULASI)
MAKS_NOMOR_SOAL = 35              # batas CHECK(nomor BETWEEN 1 AND 35) di skema lomba_soal
MAKS_TARGET_HARIAN = 5
DETIK_PER_HARI = 24 * 3600
DETIK_PER_MENIT = 60
BATAS_DETIK_ASAL_KUMPUL = 120     # sesi lebih singkat dari ini dianggap asal kumpul
BATAS_TERISI_ASAL_KUMPUL = 3      # atau terisi kurang dari ini
BATAS_DETIK_ASAL_KUMPUL_SIMULASI = 10 * 60   # Simulasi: kurang dari 10 menit (kecuali waktunya memang habis)
BATAS_TERISI_ASAL_KUMPUL_SIMULASI = 12       # atau terisi kurang dari 12 dari 35 soal
DURASI_MIN_MENIT, DURASI_MAKS_MENIT = 5, 180  # durasi per anak yang boleh diatur Guru (bilangan bulat menit)
MODE_LATIHAN, MODE_SIMULASI = "latihan", "simulasi"
MODE_SAH = (MODE_LATIHAN, MODE_SIMULASI)
LABEL_MODE = {MODE_LATIHAN: "Latihan", MODE_SIMULASI: "Simulasi Lomba"}
LABEL_MODE_PENDEK = {MODE_LATIHAN: "Latihan", MODE_SIMULASI: "Simulasi"}
LABEL_BERJALAN = {MODE_LATIHAN: "Latihanmu", MODE_SIMULASI: "Simulasi lombamu"}   # "... masih berjalan" (anak)
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
    durasi_simulasi_detik: int = 3600
    jumlah_soal_simulasi: int = JUMLAH_SOAL_SIMULASI_WAJIB
    jumlah_isian_simulasi: int = 5

    def __post_init__(self) -> None:
        if not self.id or not self.nama or not self.nama_pendek:
            raise ValueError("id, nama, dan nama pendek paket wajib diisi")
        if self.jumlah_soal != JUMLAH_SOAL_WAJIB:
            raise ValueError(f"jumlah soal paket harus {JUMLAH_SOAL_WAJIB} (batas skema DB)")
        if not 0 <= self.jumlah_isian < self.jumlah_soal:
            raise ValueError("jumlah isian harus 0 sampai kurang dari jumlah soal")
        if self.jumlah_soal_simulasi != JUMLAH_SOAL_SIMULASI_WAJIB:
            raise ValueError(f"jumlah soal simulasi harus {JUMLAH_SOAL_SIMULASI_WAJIB}")
        if not 0 <= self.jumlah_isian_simulasi < self.jumlah_soal_simulasi:
            raise ValueError("jumlah isian simulasi harus 0 sampai kurang dari jumlah soal simulasi")
        if self.durasi_detik <= 0 or self.durasi_simulasi_detik <= 0:
            raise ValueError("durasi paket harus lebih dari nol")
        if not 0 <= self.target_harian <= MAKS_TARGET_HARIAN:
            raise ValueError(f"target harian harus 0 sampai {MAKS_TARGET_HARIAN}")

    @property
    def jumlah_pg(self) -> int:
        return self.jumlah_soal - self.jumlah_isian

    @property
    def durasi_menit(self) -> int:
        return self.durasi_detik // DETIK_PER_MENIT

    def format_mode(self, mode: str) -> "FormatMode":
        """Ringkasan satu mode sesi (jumlah soal, isian, durasi) dari nilai paket ini."""
        if mode == MODE_LATIHAN:
            return FormatMode(MODE_LATIHAN, self.jumlah_soal, self.jumlah_isian, self.durasi_detik)
        if mode == MODE_SIMULASI:
            return FormatMode(MODE_SIMULASI, self.jumlah_soal_simulasi, self.jumlah_isian_simulasi,
                              self.durasi_simulasi_detik)
        raise ValueError(f"mode tidak dikenal: {mode!r}")


@dataclass(frozen=True)
class FormatMode:
    mode: str
    jumlah_soal: int
    jumlah_isian: int
    durasi_detik: int

    @property
    def label(self) -> str:
        return LABEL_MODE[self.mode]

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


def asal_kumpul(waktu_terpakai_detik: int, terisi: int, mode: str = MODE_LATIHAN,
                durasi_sesi_detik: Optional[int] = None) -> bool:
    """Sesi selesai yang terlalu singkat atau hampir kosong; tidak ikut nilai terbaik, banding, dan target.

    Latihan: < 120 detik ATAU terisi < 3. Simulasi: < 10 menit ATAU terisi < 12; batas menit tidak pernah melebihi
    durasi sesi itu sendiri (`durasi_sesi_detik`), jadi simulasi yang memakai seluruh waktunya tidak dianggap cepat.
    """
    if mode == MODE_SIMULASI:
        batas_detik = BATAS_DETIK_ASAL_KUMPUL_SIMULASI
        if durasi_sesi_detik is not None:
            batas_detik = min(batas_detik, durasi_sesi_detik)
        return waktu_terpakai_detik < batas_detik or terisi < BATAS_TERISI_ASAL_KUMPUL_SIMULASI
    return waktu_terpakai_detik < BATAS_DETIK_ASAL_KUMPUL or terisi < BATAS_TERISI_ASAL_KUMPUL


def menit_sah(menit: int) -> bool:
    """Durasi per anak yang boleh diatur Guru: bilangan bulat DURASI_MIN_MENIT..DURASI_MAKS_MENIT."""
    return (not isinstance(menit, bool) and isinstance(menit, int)
            and DURASI_MIN_MENIT <= menit <= DURASI_MAKS_MENIT)

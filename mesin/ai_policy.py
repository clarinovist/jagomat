"""Kebijakan murni untuk pengendalian seluruh panggilan AI."""

from __future__ import annotations

from dataclasses import dataclass
import os

FITUR = ("pendamping", "cerita", "lampiran", "uji_sintetis")
LABEL_FITUR = {
    "pendamping": "Pendamping",
    "cerita": "Cerita soal",
    "lampiran": "Lampiran",
    "uji_sintetis": "Tes sintetis",
}

# Nilai uang selalu micro-USD. Ini nilai awal yang disetujui, bukan tagihan provider.
DEFAULT_LIMIT = {
    "global": (1_000_000, 20_000_000),
    "pendamping": (500_000, 10_000_000),
    "cerita": (300_000, 6_000_000),
    "lampiran": (150_000, 3_000_000),
    "uji_sintetis": (50_000, 1_000_000),
}
DEFAULT_REQUEST_AKUN_HARIAN = 20
DEFAULT_UJI_HARIAN = 3
DEFAULT_UJI_COOLDOWN_DETIK = 600

# Reservasi konservatif per request. Rekonsiliasi usage menggunakan tarif profil.
RESERVASI_MICRO_USD = {
    "pendamping": 15_000,
    "cerita": 5_000,
    "lampiran": 50_000,
    "uji_sintetis": 5_000,
}
HARD_CEILING_DEFAULT = 100_000_000  # USD 100 per bulan, dapat diperkecil operator.


@dataclass(frozen=True)
class Profil:
    fitur: str
    model: str
    max_output: int
    timeout: int
    reservasi_micro_usd: int


def profil(fitur: str) -> Profil:
    if fitur not in FITUR:
        raise ValueError("Fitur AI tidak dikenal.")
    model = os.environ.get(
        "DEEPSEEK_VISION_MODEL" if fitur == "lampiran" else "DEEPSEEK_MODEL",
        "deepseek-flash",
    ).strip()
    output = {"pendamping": 1200, "cerita": 2000, "lampiran": 8000,
              "uji_sintetis": 32}[fitur]
    timeout = {"pendamping": 25, "cerita": 20, "lampiran": 80,
               "uji_sintetis": 10}[fitur]
    return Profil(fitur, model, output, timeout, RESERVASI_MICRO_USD[fitur])


def hard_ceiling_micro_usd() -> int:
    mentah = os.environ.get("AI_HARD_CEILING_BULANAN_USD", "100")
    try:
        nilai = round(float(mentah) * 1_000_000)
    except ValueError:
        return 0
    return max(0, min(nilai, HARD_CEILING_DEFAULT))


def deployment_mengizinkan(fitur: str) -> bool:
    if os.environ.get("AI_NONAKTIF", "0") == "1":
        return False
    if fitur == "pendamping":
        return os.environ.get("PENDAMPING_AKTIF", "0") == "1"
    return True

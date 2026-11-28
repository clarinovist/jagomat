"""Waktu mengerjakan per soal pada layar soal anak cek gratis (F1).

Stateless, tanpa skema baru: layar soal menaruh jam render server (epoch detik) di hidden
field `t0`. Saat simpan, selisih `sekarang - t0` menjadi detik mengerjakan. Nilai ini metrik
self-report, bukan otorisasi, jadi tidak diberi HMAC. Bila `t0` hilang, rusak, di masa depan,
atau terlalu lama, hasilnya None dan kiriman anak tetap tersimpan.
"""
from __future__ import annotations

import re
import time

NAMA_FIELD = "t0"
BATAS_DETIK_SOAL = 600
JENDELA_DETIK = 3600
POLA_T0 = re.compile(r"[0-9]{1,12}")


def sekarang() -> int:
    """Jam server dalam epoch detik bulat. Dibungkus fungsi supaya tes bisa menyuntik waktu."""
    return int(time.time())


def hitung_detik(t0, kini: int) -> int | None:
    """Detik sejak `t0` sampai `kini`, dibatasi `BATAS_DETIK_SOAL`; None bila `t0` tidak sah."""
    if not isinstance(t0, str) or not POLA_T0.fullmatch(t0):
        return None
    awal = int(t0)
    if not kini - JENDELA_DETIK <= awal <= kini:
        return None
    return min(kini - awal, BATAS_DETIK_SOAL)

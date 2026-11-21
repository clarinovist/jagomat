"""Gerbang fitur Latihan Lomba.

Sementara memakai env `OSN_LOMBA` (bawaan mati; hanya nilai persis "1" menyalakan). Pada Tahap 3
diganti sakelar admin `OSN_LOMBA` (`feature_switch`, migrasi `sakelar.db` v1 -> v2). Saat mati, semua
rute `/murid/lomba/...` tidak dikenali (404 yang identik dengan jalur murid lain yang tidak ada).
"""
from __future__ import annotations

import os

ENV_LOMBA = "OSN_LOMBA"


def aktif() -> bool:
    return os.environ.get(ENV_LOMBA, "0").strip() == "1"

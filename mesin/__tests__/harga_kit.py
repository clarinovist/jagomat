"""Pembantu bersama tes harga: DB admin sintetis (store admin + tabel harga_*). Data sintetis saja."""
from __future__ import annotations

from pathlib import Path

import admin_store
import schema_harga

ADMIN = "admin_sintetis_a"
SEKARANG = "2026-11-25T08:00:00"
SESUDAH = "2026-11-25T09:00:00"


def siapkan_db_harga(tmp_path):
    """DB admin sintetis: store admin standar + migrasi harga eksplisit (tanpa pesanan; harga tanpa kunci asing)."""
    path = Path(tmp_path) / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    schema_harga.migrasikan(path)
    return path


def siapkan_db_admin_saja(tmp_path):
    """DB admin sintetis tanpa tabel harga_*: untuk menguji perilaku skema belum terpasang."""
    path = Path(tmp_path) / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    return path

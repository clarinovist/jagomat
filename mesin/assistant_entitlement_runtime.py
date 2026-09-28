"""Adapter read-only entitlement Pendamping; enforcement default mati."""
from __future__ import annotations

from dataclasses import dataclass
import os
import sqlite3
import time
from typing import Optional

import admin_store


@dataclass(frozen=True)
class StatusRuntime:
    status: str
    paket: Optional[str] = None
    limit: int = 0
    digunakan: int = 0
    direservasi: int = 0
    tersisa: int = 0
    isi_ulang: Optional[int] = None
    enforcement_aktif: bool = False
    domain: object = None


def enforcement_aktif() -> bool:
    """Hanya nilai exact 1 mengaktifkan guard; default dan nilai asing OFF."""
    return os.environ.get("PENDAMPING_ENTITLEMENT_AKTIF", "0") == "1"


def _gagal(aktif: bool) -> StatusRuntime:
    return StatusRuntime("storage_tidak_terverifikasi", enforcement_aktif=aktif)


def status(account_id: str, *, sekarang: int, fitur: str = "balasan_pendamping") -> StatusRuntime:
    """Baca status tanpa membuat/migrasi DB, trial, window, atau ledger."""
    aktif = enforcement_aktif()
    path = admin_store.BAWAAN
    if not path.is_file():
        return _gagal(aktif)
    try:
        import assistant_entitlement
        snapshot = assistant_entitlement.baca_status(
            path, account_id, fitur=fitur, sekarang=sekarang, penegakan=aktif,
        )
        return StatusRuntime(
            snapshot.status, paket=getattr(snapshot, "paket", None),
            limit=int(getattr(snapshot, "limit", 0)),
            digunakan=int(getattr(snapshot, "digunakan", 0)),
            direservasi=int(getattr(snapshot, "direservasi", 0)),
            tersisa=int(getattr(snapshot, "tersisa", 0)),
            isi_ulang=getattr(snapshot, "isi_ulang", None),
            enforcement_aktif=aktif, domain=snapshot,
        )
    except (ImportError, OSError, sqlite3.Error, RuntimeError, ValueError, LookupError):
        return _gagal(aktif)


def status_pengguna(pengguna: str, *, sekarang: Optional[int] = None):
    """Proyeksi ikon generik; tidak membaca profil/konteks saat enforcement OFF."""
    if not enforcement_aktif():
        return None
    import auth

    akun = auth.cari_akun(pengguna)
    if akun is None or akun.get("peran") != "guru":
        return _gagal(True)
    kini = int(time.time()) if sekarang is None else int(sekarang)
    return status(akun.get("id_akun", ""), sekarang=kini)


def boleh_outbound(account_id: str, *, sekarang: int,
                    fitur: str = "balasan_pendamping") -> bool:
    """Default OFF mempertahankan runtime lama; ON hanya state berhak."""
    if not enforcement_aktif():
        return True
    return status(account_id, sekarang=sekarang, fitur=fitur).status in {
        "trial_aktif", "pro_aktif",
    }

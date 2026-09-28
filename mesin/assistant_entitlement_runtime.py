"""Adapter read-only entitlement Pendamping; enforcement default mati."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
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
    """Aktif hanya bila opt-in server dan tahap audit penegakan sama-sama sah."""
    if os.environ.get("PENDAMPING_ENTITLEMENT_AKTIF", "0") != "1":
        return False
    try:
        import admin_subscription
        return admin_subscription.sakelar_runtime(admin_store.BAWAAN).penegakan is True
    except (OSError, RuntimeError, sqlite3.Error, ValueError):
        return False


def _gagal(aktif: bool) -> StatusRuntime:
    return StatusRuntime("storage_tidak_terverifikasi", enforcement_aktif=aktif)


def status(account_id: str, *, sekarang: int, fitur: str = "balasan_pendamping") -> StatusRuntime:
    """Baca status tanpa membuat/migrasi DB, trial, window, atau ledger."""
    aktif = enforcement_aktif()
    if not aktif:
        # Rollout OFF tidak membaca billing dan tidak mengubah jalur lama.
        return _gagal(False)
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


class GalatKuotaRuntime(RuntimeError):
    """Admission/finalisasi kuota gagal tertutup tanpa detail storage."""


def operasi_id(account_id: str, fitur: str, identitas: str) -> str:
    """ID durable bounded; teks/prompt/resource tidak disimpan pada ledger."""
    if not account_id or not fitur or not identitas:
        raise ValueError("identitas kuota tidak lengkap")
    sidik = hashlib.sha256(
        (account_id + "\0" + fitur + "\0" + identitas).encode("utf-8")
    ).hexdigest()[:32]
    return "kuota_" + sidik


def reservasi(account_id: str, *, fitur: str, identitas: str, sekarang: int):
    """Reserve sebelum outbound; OFF benar-benar tanpa I/O billing."""
    if not enforcement_aktif():
        return None
    try:
        import assistant_quota_store
        hasil = assistant_quota_store.reservasi(
            admin_store.BAWAAN, account_id,
            operasi_id=operasi_id(account_id, fitur, identitas), fitur=fitur,
            sekarang=sekarang, penegakan=True,
        )
    except Exception as galat:
        raise GalatKuotaRuntime("kuota tidak tersedia") from galat
    if hasil is None or not hasil.boleh_outbound:
        raise GalatKuotaRuntime("permintaan kuota bukan reservasi baru")
    return hasil.ikatan


def _ubah(nama: str, ikatan, *, sekarang: int, **kwargs) -> None:
    if ikatan is None:
        return
    try:
        import assistant_quota_store
        getattr(assistant_quota_store, nama)(
            admin_store.BAWAAN, ikatan, sekarang=sekarang, **kwargs
        )
    except Exception as galat:
        raise GalatKuotaRuntime("status kuota tidak dapat diperbarui") from galat


def tandai_unknown(ikatan, *, sekarang: int) -> None:
    _ubah("tandai_unknown", ikatan, sekarang=sekarang)


def lepaskan(ikatan, *, sekarang: int, rekonsiliasi: bool = False) -> None:
    _ubah(
        "lepaskan", ikatan, sekarang=sekarang,
        tanpa_output_terbukti=True, rekonsiliasi=rekonsiliasi,
    )


def finalisasi(ikatan, *, sekarang: int, rekonsiliasi: bool = False) -> None:
    _ubah(
        "finalisasi", ikatan, sekarang=sekarang,
        hasil_valid_tersimpan=True, rekonsiliasi=rekonsiliasi,
    )


def finalisasi_replay(account_id: str, *, fitur: str, identitas: str,
                       sekarang: int) -> None:
    """Pulihkan crash sesudah output tersimpan; tidak pernah outbound ulang."""
    if not enforcement_aktif():
        return
    try:
        import assistant_quota_store
        hasil = assistant_quota_store.baca_operasi(
            admin_store.BAWAAN, account_id,
            operasi_id(account_id, fitur, identitas), fitur=fitur,
        )
        if hasil is None or hasil.status == "completed":
            return
        finalisasi(hasil.ikatan, sekarang=sekarang, rekonsiliasi=True)
    except Exception as galat:
        raise GalatKuotaRuntime("rekonsiliasi kuota gagal") from galat

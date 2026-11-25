"""Pembacaan sisi orang tua untuk jadwal Private: guru aktif dan tawaran slot untuk satu anak (tanpa nama guru).

Hanya membaca. Penulisan (ajukan, batal) ada di `jadwal_private` dan dipanggil dari `jadwal_private_murid_http`.
Tidak mengimpor `admin_http` atau `jadwal_admin_http`: jalur murid tidak menarik permukaan admin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import admin_store
import auth
import jadwal_private as jp
import jadwal_store as js
from jadwal_private_baca import SlotTerbuka, StatusPengajuan


@dataclass(frozen=True)
class Tawaran:
    """Isi kartu Private untuk satu anak: pengajuan terakhir (atau None) dan slot yang boleh diajukan sekarang."""

    pengajuan: Optional[StatusPengajuan]
    slot: Tuple[SlotTerbuka, ...]


def guru_sah() -> frozenset:
    """Id akun guru aktif (peran guru, tidak dinonaktifkan). Predikat sama dengan `jadwal_admin_http.guru_map`."""
    return frozenset(a["id_akun"] for a in auth.muat_akun()
                     if a.get("peran") == "guru" and not a.get("dinonaktifkan") and a.get("id_akun"))


def baca_tawaran(akun_id: str, siswa_id: int, kini: str) -> Optional[Tawaran]:
    """Tawaran untuk order Private aktif anak yang belum berjadwal, atau None bila tidak ditawarkan."""
    with js.buka(admin_store.BAWAAN) as kon:
        oid = jp.order_boleh_mengajukan(kon, akun_id, siswa_id, kini)
        if oid is None:
            return None
        sah = guru_sah()
        pengajuan = jp.status_pengajuan(kon, akun_id, siswa_id, kini, guru_sah=sah)
        return Tawaran(pengajuan, jp.slot_terbuka_untuk(kon, oid, kini, sah))

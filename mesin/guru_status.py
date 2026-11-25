"""Nonaktifkan / aktifkan kembali akun guru oleh admin (satu tulis atomik ke berkas akun).

Penguncian memakai sinyal yang sudah dihormati kode lama: `dinonaktifkan: True` (login Basic dan cookie ditolak)
dan `revisi_auth` naik di tulis yang sama (semua cookie lama mati). Penanda `nonaktif_admin` membedakan
nonaktif-admin (boleh diaktifkan kembali) dari tombstone penghapusan keluarga (pseudonim, kredensial dibuang;
tidak pernah boleh diaktifkan). Data anak, lembaga, dan jadwal tidak disentuh.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import auth
from json_storage import transaksi_json

KUNCI_MARKA = "nonaktif_admin"
AWALAN_TOMBSTONE = "keluarga_dihapus_"  # pseudonim tombstone family_deletion; tidak pernah boleh diaktifkan
PERAN_GURU = "guru"


class StatusDitolak(ValueError):
    """Target bukan guru yang sah untuk perintah ini (admin, murid, tombstone, atau keadaan tidak cocok)."""


class StatusBerubah(Exception):
    """Revisi akun berbeda dari tinjauan (akun berubah sejak halaman dibuka): tidak ada yang ditulis."""


def nonaktif_admin(akun) -> bool:
    """True hanya untuk guru yang dinonaktifkan admin (bukan tombstone): dinonaktifkan dan bermarka sah."""
    marka = akun.get(KUNCI_MARKA)
    pengguna = akun.get("pengguna")
    return (akun.get("peran", PERAN_GURU) == PERAN_GURU and akun.get("dinonaktifkan") is True
            and not (type(pengguna) is str and pengguna.startswith(AWALAN_TOMBSTONE))
            and isinstance(marka, dict) and type(marka.get("oleh")) is str and type(marka.get("pada")) is int)


def _cari_guru(akun: list, id_akun: str) -> dict:
    target = next((a for a in akun if a.get("id_akun") == id_akun), None)
    if target is None or target.get("peran", PERAN_GURU) != PERAN_GURU:
        raise StatusDitolak("akun bukan guru")
    return target


def _ubah(id_akun: str, revisi_diharap: int, terapkan, path: Optional[Path]) -> int:
    if not auth.id_akun_sah(id_akun) or type(revisi_diharap) is not int:
        raise StatusDitolak("perintah tidak sah")
    p = path or auth.BERKAS_SANDI
    with transaksi_json(p) as tujuan:
        mentah, akun, _multi = auth._baca_akun_untuk_tulis(tujuan)
        target = _cari_guru(akun, id_akun)
        if auth.revisi_auth(target) != revisi_diharap:
            raise StatusBerubah()
        terapkan(target)
        target["revisi_auth"] = revisi_diharap + 1  # cookie lama mati, juga di image recovery
        auth._tulis_akun_atomik(auth._bungkus_akun(mentah, akun), tujuan)
        return target["revisi_auth"]


def nonaktifkan(id_akun: str, revisi_diharap: int, admin_id: str, sekarang: int, path: Optional[Path] = None) -> int:
    """Kunci guru aktif. Mengembalikan revisi_auth baru."""
    if type(admin_id) is not str or not admin_id or type(sekarang) is not int:
        raise StatusDitolak("perintah tidak sah")

    def terapkan(target: dict) -> None:
        if target.get("dinonaktifkan") is True:
            raise StatusDitolak("guru sudah nonaktif")
        target["dinonaktifkan"] = True
        target[KUNCI_MARKA] = {"oleh": admin_id, "pada": sekarang}

    return _ubah(id_akun, revisi_diharap, terapkan, path)


def aktifkan(id_akun: str, revisi_diharap: int, path: Optional[Path] = None) -> int:
    """Buka kunci guru yang dinonaktifkan admin. Tombstone dan guru aktif ditolak. Mengembalikan revisi_auth baru."""

    def terapkan(target: dict) -> None:
        if not nonaktif_admin(target):
            raise StatusDitolak("guru tidak dinonaktifkan oleh admin")
        del target["dinonaktifkan"]
        del target[KUNCI_MARKA]

    return _ubah(id_akun, revisi_diharap, terapkan, path)

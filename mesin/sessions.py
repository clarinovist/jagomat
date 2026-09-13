"""Sesi login: token acak -> (pengguna, peran, kedaluarsa), disimpan JSON.

Kenapa berkas, bukan tabel basis data: sesi adalah state AUTENTIKASI, bukan
data pendidikan — mencampurnya ke latihan.db membuat cadangan data anak ikut
membawa kuki sesi. Polanya mengikuti sandi.json: chmod 600, tulis atomik.
"""
from __future__ import annotations

import hashlib
import os
import math
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from json_storage import (
    GalatPenyimpananJSON,
    baca_json_ketat,
    transaksi_json,
    tulis_json_atomik,
)

BERKAS_SESI = Path(
    os.environ.get("OSN_BERKAS_SESI", Path(__file__).resolve().parent / "sesi.json")
)
TTL_DETIK = 14 * 24 * 3600  # dua minggu; iPhone anak dipakai bergantian

_jalur_dari_kunci_ip: dict[tuple[str, str], list[float]] = {}

# Umpan waktu-tetap untuk akun tak dikenal (B3): PBKDF2 satu kali ini agar
# jalur nama-salah memakan waktu serupa jalur nama-benar+sandi-salah.
# Iterasinya mengikuti OSN_PBKDF2_ITERASI — lihat komentar _ITERASI di
# auth.py; test menyetelnya rendah lewat __tests__/conftest.py.
_ITERASI = int(os.environ.get("OSN_PBKDF2_ITERASI", "600000"))
_garam_dummy = hashlib.pbkdf2_hmac(
    "sha256", b"dummy", b"aaaaaaaaaaaaaaaa", _ITERASI, dklen=32
)  # dihitung saat import — tidak di hot path; nilai tidak dipakai selain untuk waktu

_BATAS_JENDELA = 15 * 60  # hitung gagal dalam 15 menit
_BATAS_GAGAL = 5  # gagal ke-5 menutup keran
_BATAS_TUNGGU = 15 * 60


# ── sesi token ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Principal:
    """Identitas kanonik yang diverifikasi terhadap akun mutakhir."""

    pengguna: str
    peran: str
    id_akun: str
    revisi_auth: int
    metode: str


@dataclass(frozen=True)
class PrincipalPendamping:
    """Identitas guru terverifikasi untuk storage privat Pendamping."""

    pengguna: str
    peran: str
    id_akun: str


def _data_sesi_sah(data) -> bool:
    import auth

    if not isinstance(data, dict):
        return False
    for token, entri in data.items():
        if not isinstance(token, str) or not isinstance(entri, dict):
            return False
        kedaluarsa = entri.get("kedaluarsa")
        id_akun = entri.get("id_akun")
        revisi = entri.get("revisi_auth")
        punya_id = "id_akun" in entri
        punya_revisi = "revisi_auth" in entri
        legacy = not punya_id and not punya_revisi
        if (
            not token
            or not isinstance(entri.get("pengguna"), str)
            or not entri.get("pengguna")
            or entri.get("peran") not in auth.PERAN
            or isinstance(kedaluarsa, bool)
            or not isinstance(kedaluarsa, (int, float))
            or not math.isfinite(kedaluarsa)
            or not (
                legacy
                or (
                    punya_id
                    and punya_revisi
                    and auth.id_akun_sah(id_akun)
                    and type(revisi) is int
                    and revisi >= 0
                )
            )
        ):
            return False
    return True


def muat(path: Path | None = None) -> dict:
    p = path or BERKAS_SESI
    try:
        data = baca_json_ketat(p, bawaan={})
    except GalatPenyimpananJSON:
        # Reader autentikasi tetap fail-closed tanpa membuka detail storage.
        return {}
    return data if _data_sesi_sah(data) else {}


def _muat_untuk_tulis(path: Path) -> dict:
    """Writer membedakan state kosong dari state rusak agar tidak overwrite."""
    try:
        data = baca_json_ketat(path, bawaan={})
    except GalatPenyimpananJSON as galat:
        raise ValueError("berkas sesi tidak sah") from galat
    if not _data_sesi_sah(data):
        raise ValueError("berkas sesi tidak sah")
    return data


def _tulis(data: dict, path: Path | None = None) -> None:
    """Tulis sesi privat; aman dipanggil di dalam transaksi yang sama."""
    tulis_json_atomik(data, path or BERKAS_SESI)


def buat(pengguna: str, peran: str, path: Path | None = None,
         sekarang: float | None = None, id_akun: str | None = None,
         revisi_auth: int | None = None) -> str:
    import auth

    if peran not in auth.PERAN:
        raise ValueError("peran sesi tidak sah")
    if not auth.id_akun_sah(id_akun):
        raise ValueError("id_akun sesi tidak sah")
    if type(revisi_auth) is not int or revisi_auth < 0:
        raise ValueError("revisi_auth sesi tidak sah")
    entri = {
        "pengguna": pengguna,
        "peran": peran,
        "id_akun": id_akun,
        "revisi_auth": revisi_auth,
        "kedaluarsa": (sekarang if sekarang is not None else time.time()) + TTL_DETIK,
    }
    p = path or BERKAS_SESI
    with transaksi_json(p) as tujuan:
        data = _muat_untuk_tulis(tujuan)
        token = secrets.token_urlsafe(32)
        while token in data:
            token = secrets.token_urlsafe(32)
        data[token] = entri
        _tulis(data, tujuan)
        return token


def _cocok_principal_akun(entri: dict, akun: dict) -> bool:
    """Semua dimensi cookie harus cocok record akun mutakhir."""
    import auth

    revisi_sesi = entri.get("revisi_auth")
    try:
        revisi_akun = auth.revisi_auth(akun)
    except ValueError:
        return False
    return (
        type(entri.get("pengguna")) is str
        and entri["pengguna"] == akun.get("pengguna")
        and entri.get("peran") in auth.PERAN
        and entri.get("peran") == akun.get("peran", "guru")
        and auth.id_akun_sah(entri.get("id_akun"))
        and entri.get("id_akun") == akun.get("id_akun")
        and type(revisi_sesi) is int
        and revisi_sesi >= 0
        and revisi_sesi == revisi_akun
    )


def ambil_principal(
    token: str | None, path: Path | None = None,
    sekarang: float | None = None, path_akun: Path | None = None,
) -> Principal | None:
    """Validasi cookie terhadap akun mutakhir tanpa menulis atau migrasi."""
    if not token:
        return None
    kini = sekarang if sekarang is not None else time.time()
    entri = muat(path).get(token)
    if not isinstance(entri, dict) or entri.get("kedaluarsa", 0) <= kini:
        return None

    import auth

    akun = auth.cari_akun(entri.get("pengguna", ""), path_akun)
    if akun is None or not _cocok_principal_akun(entri, akun):
        return None
    return Principal(
        pengguna=akun["pengguna"],
        peran=akun.get("peran", "guru"),
        id_akun=akun["id_akun"],
        revisi_auth=auth.revisi_auth(akun),
        metode="cookie",
    )


def principal_basic(
    pengguna: str, sandi: str, path_akun: Path | None = None
) -> Principal | None:
    """Verifikasi Basic setiap request dan kembalikan nama record kanonik."""
    import auth

    akun = auth.autentikasi(pengguna, sandi, path_akun)
    if akun is None:
        return None
    return Principal(
        pengguna=akun.pengguna,
        peran=akun.peran,
        id_akun=akun.id_akun,
        revisi_auth=akun.revisi_auth,
        metode="basic",
    )


def buat_dari_principal(
    principal_akun, path: Path | None = None, sekarang: float | None = None,
    path_akun: Path | None = None,
) -> str | None:
    """Terbitkan sesi jika snapshot credential tetap mutakhir saat commit.

    Urutan lock selalu akun lalu sesi. Reset yang menunggu lock akun akan
    menaikkan revisi setelah sesi ditulis, sehingga sesi itu langsung stale.
    """
    import auth

    tujuan_akun = path_akun or auth.BERKAS_SANDI
    with transaksi_json(tujuan_akun) as path_akun_terkunci:
        try:
            _mentah, daftar, _multi = auth._baca_akun_untuk_tulis(
                path_akun_terkunci
            )
            akun = next(
                (
                    item for item in daftar
                    if item.get("id_akun") == principal_akun.id_akun
                ),
                None,
            )
            cocok = (
                akun is not None
                and akun.get("pengguna") == principal_akun.pengguna
                and akun.get("peran", "guru") == principal_akun.peran
                and auth.revisi_auth(akun) == principal_akun.revisi_auth
            )
        except (AttributeError, ValueError):
            return None
        if not cocok:
            return None
        return buat(
            principal_akun.pengguna, principal_akun.peran, path=path,
            sekarang=sekarang, id_akun=principal_akun.id_akun,
            revisi_auth=principal_akun.revisi_auth,
        )


def ambil(token: str | None, path: Path | None = None,
          sekarang: float | None = None,
          path_akun: Path | None = None) -> tuple[str, str] | None:
    """Adapter tuple lama; cookie legacy kini sengaja fail-closed."""
    principal = ambil_principal(token, path, sekarang, path_akun)
    if principal is None:
        return None
    return principal.pengguna, principal.peran


def ambil_principal_pendamping(
    token: str | None,
    path: Path | None = None,
    sekarang: float | None = None,
    path_akun: Path | None = None,
) -> PrincipalPendamping | None:
    """Adapter guru-only untuk storage privat Pendamping."""
    principal = ambil_principal(token, path, sekarang, path_akun)
    if principal is None or principal.peran != "guru":
        return None
    return PrincipalPendamping(
        pengguna=principal.pengguna,
        peran=principal.peran,
        id_akun=principal.id_akun,
    )


def cabut_akun(id_akun: str, path_akun: Path | None = None) -> int | None:
    """Cabut seluruh cookie akun secara logis lewat kenaikan revisi.

    Fungsi tidak mengambil lock sesi; validasi cookie membaca revisi akun setiap
    request, sehingga commit auth menjadi titik pencabutan untuk semua token.
    """
    import auth

    return auth.naikkan_revisi_auth(id_akun, path_akun)


def hapus(token: str, path: Path | None = None) -> bool:
    p = path or BERKAS_SESI
    with transaksi_json(p) as tujuan:
        data = _muat_untuk_tulis(tujuan)
        if token not in data:
            return False
        del data[token]
        _tulis(data, tujuan)
        return True


def bersihkan(path: Path | None = None) -> int:
    p = path or BERKAS_SESI
    with transaksi_json(p) as tujuan:
        kini = time.time()
        data = _muat_untuk_tulis(tujuan)
        sisa = {t: e for t, e in data.items() if e.get("kedaluarsa", 0) > kini}
        dihapus = len(data) - len(sisa)
        if dihapus:
            _tulis(sisa, tujuan)
        return dihapus


# ── rate limit percobaan masuk ──────────────────────────────────────────────
def _pangkas(kunci: tuple[str, str], kini: float) -> list[float]:
    lst = _jalur_dari_kunci_ip.get(kunci, [])
    lst = [t for t in lst if kini - t < _BATAS_JENDELA]
    _jalur_dari_kunci_ip[kunci] = lst
    return lst


def sedang_diblokir(nama: str, kunci_ip: str, sekarang: float | None = None) -> bool:
    kini = sekarang if sekarang is not None else time.time()
    kunci = (nama.strip().lower(), kunci_ip)
    lst = _pangkas(kunci, kini)
    return len(lst) >= _BATAS_GAGAL


def catat_gagal(nama: str, kunci_ip: str, sekarang: float | None = None) -> None:
    kini = sekarang if sekarang is not None else time.time()
    kunci = (nama.strip().lower(), kunci_ip)
    lst = _pangkas(kunci, kini)
    lst.append(kini)
    _jalur_dari_kunci_ip[kunci] = lst


def catat_berhasil(nama: str, kunci_ip: str) -> None:
    _jalur_dari_kunci_ip.pop((nama.strip().lower(), kunci_ip), None)


def _reset_rate_limit() -> None:  # khusus test
    _jalur_dari_kunci_ip.clear()

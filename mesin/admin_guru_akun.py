"""Daftar akun guru untuk admin (baca-saja): asal akun, lembaga, dan jumlah anak.

Akun peran guru bercampur dengan akun orang tua alur lama (pendaftaran lama membuat akun peran guru + profil anak). Penanda alur lama =
receipt pendaftaran (`operasi_registrasi`, teacher_created) yang operasinya punya entri `registrasi_profil`; akun itu tetap di menu
Keluarga dan tidak masuk daftar ini. Asal akun sisanya: "mandiri" (receipt tanpa profil, jalur guru daftar sendiri) atau "admin" (tanpa
receipt: dibuat admin atau akun lama). Jumlah anak, sesi, dan aktivitas dari query keluarga yang sama dengan menu Keluarga. Tanpa kredensial,
hash, atau kontak. Akun yang dinonaktifkan admin hanya tampil di chip "Nonaktif" (bisa diaktifkan kembali); tombstone
penghapusan keluarga tidak pernah ditampilkan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

import admin_antrean_guru as antrean_guru
import admin_queries as Q
import guru_status
import lembaga_store

ASAL_MANDIRI = "mandiri"
ASAL_ADMIN = "admin"
LABEL_ASAL = {ASAL_MANDIRI: "Daftar sendiri", ASAL_ADMIN: "Dibuat admin atau akun lama"}
PERAN_KOORDINATOR = "Koordinator"
PERAN_ANGGOTA = "Anggota"
SARING = ("semua", "belum_lembaga", "mandiri", "di_lembaga", "nonaktif")
BATAS_BARIS = 500


@dataclass(frozen=True)
class GuruRingkas:
    id_akun: str
    pengguna: str
    asal: str
    lembaga: Optional[str]
    peran_lembaga: Optional[str]
    jumlah_siswa: int
    jumlah_sesi: int
    aktivitas_terakhir: Optional[str]
    nonaktif: bool = False
    nonaktif_oleh: Optional[str] = None
    nonaktif_pada: Optional[int] = None


def id_orang_tua_lama(mentah) -> frozenset:
    """Id akun peran guru hasil pendaftaran alur lama (receipt teacher_created yang punya profil anak)."""
    if not isinstance(mentah, Mapping):
        return frozenset()
    receipts, profil = mentah.get("operasi_registrasi"), mentah.get("registrasi_profil", {})
    if not isinstance(receipts, Mapping) or not isinstance(profil, Mapping):
        return frozenset()
    return frozenset(
        r["hasil_id"] for op, r in receipts.items()
        if isinstance(r, Mapping) and r.get("hasil_kode") == antrean_guru.KODE_GURU and op in profil
        and isinstance(r.get("hasil_id"), str))


def _peta_lembaga(kon) -> dict:
    peta = {}
    for baris, anggota in lembaga_store.daftar_lembaga(kon):
        peta[baris["pemilik"]] = (baris["nama"], PERAN_KOORDINATOR)
        for nama in anggota:
            peta.setdefault(nama, (baris["nama"], PERAN_ANGGOTA))
    return peta


def _semua_guru(kon, akun_mentah: Iterable[Mapping], mentah) -> Tuple[GuruRingkas, ...]:
    """Semua guru bukan orang tua alur lama, urut nama (tanpa pemotongan). Nonaktif-admin ikut (bertanda), tombstone tidak."""
    akun_mentah = [a for a in akun_mentah if not a.get("dinonaktifkan") or guru_status.nonaktif_admin(a)]
    nama_akun = {a.get("id_akun"): a.get("pengguna") for a in akun_mentah}
    konteks = Q.buat_konteks(kon, akun_mentah)
    mandiri, lama = antrean_guru.id_guru_mandiri(mentah), id_orang_tua_lama(mentah)
    marka_nonaktif = {a.get("id_akun"): (a[guru_status.KUNCI_MARKA]["oleh"], a[guru_status.KUNCI_MARKA]["pada"])
                      for a in akun_mentah if guru_status.nonaktif_admin(a)}
    keluarga = {k.id_akun: k for k in Q._keluarga_semua(kon, konteks) if k.id_akun}
    lembaga = _peta_lembaga(kon)
    hasil = []
    for akun in konteks.akun:
        if akun.peran != "guru" or akun.id_akun is None or akun.id_akun in lama:
            continue
        nama_lembaga, peran = lembaga.get(akun.pengguna, (None, None))
        ringkas = keluarga.get(akun.id_akun)
        marka = marka_nonaktif.get(akun.id_akun)
        hasil.append(GuruRingkas(
            akun.id_akun, akun.pengguna, ASAL_MANDIRI if akun.id_akun in mandiri else ASAL_ADMIN,
            nama_lembaga, peran, ringkas.jumlah_siswa if ringkas else 0, ringkas.jumlah_sesi if ringkas else 0,
            ringkas.aktivitas_terakhir if ringkas else None,
            marka is not None, nama_akun.get(marka[0], marka[0]) if marka else None, marka[1] if marka else None))
    hasil.sort(key=lambda g: (g.pengguna.casefold(), g.pengguna))
    return tuple(hasil)


def _lolos(g: GuruRingkas, saring: str) -> bool:
    if saring == "nonaktif":
        return g.nonaktif
    if g.nonaktif:
        return False
    if saring == "belum_lembaga":
        return g.lembaga is None
    if saring == "di_lembaga":
        return g.lembaga is not None
    if saring == "mandiri":
        return g.asal == ASAL_MANDIRI
    return True


def daftar_guru(kon, akun_mentah: Iterable[Mapping], mentah, saring: str = "semua") -> Tuple[GuruRingkas, ...]:
    """Guru untuk tabel, dipotong `BATAS_BARIS`. `saring` di luar `SARING` = InputQueryTidakSah."""
    if saring not in SARING:
        raise Q.InputQueryTidakSah("filter guru tidak sah")
    return tuple(g for g in _semua_guru(kon, akun_mentah, mentah) if _lolos(g, saring))[:BATAS_BARIS]


def hitung_per_saring(kon, akun_mentah: Iterable[Mapping], mentah) -> dict:
    """Jumlah guru per chip filter (dari seluruh guru, tanpa pemotongan; satu kali baca)."""
    semua = _semua_guru(kon, akun_mentah, mentah)
    return {s: sum(1 for g in semua if _lolos(g, s)) for s in SARING}


def satu_guru(kon, akun_mentah: Iterable[Mapping], mentah, id_akun: str) -> Optional[GuruRingkas]:
    """Ringkasan satu guru menurut id akun (dari seluruh guru, bukan tabel terpotong), atau None."""
    return next((g for g in _semua_guru(kon, akun_mentah, mentah) if g.id_akun == id_akun), None)

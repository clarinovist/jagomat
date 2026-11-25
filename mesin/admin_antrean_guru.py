"""Guru yang mendaftar sendiri dan belum dimasukkan ke lembaga, untuk antrean admin (read-only, hanya angka).

Penanda guru mandiri = receipt pendaftaran publik di berkas akun (`operasi_registrasi`, kode teacher_created) yang operasinya TIDAK
punya entri `registrasi_profil`: alur orang tua lama (`daftar_dengan_profil`) selalu menulis profil anak, sedangkan
`admin_registration.daftar_publik` (jalur guru mandiri) tidak. Receipt itu sudah ada sejak akun dibuat, jadi tidak butuh kolom,
skema, atau kode hasil baru (kode baru akan ditolak pembaca receipt di image lama). Akun yang sudah punya anak (pemilik siswa),
sudah terikat lembaga, dinonaktifkan, atau bukan peran guru tidak dihitung. Galat baca berarti 0: antrean tidak boleh menjatuhkan
halaman admin. Tanpa nama akun di keluaran.
"""
from __future__ import annotations

from typing import Iterable, Mapping

import auth
import database
import lembaga_store

KODE_GURU = "teacher_created"


def id_guru_mandiri(mentah) -> frozenset:
    """Id akun guru hasil pendaftaran publik tanpa profil anak, dari isi berkas akun mentah."""
    if not isinstance(mentah, Mapping):
        return frozenset()
    receipts, profil = mentah.get("operasi_registrasi"), mentah.get("registrasi_profil", {})
    if not isinstance(receipts, Mapping) or not isinstance(profil, Mapping):
        return frozenset()
    return frozenset(
        r["hasil_id"] for op, r in receipts.items()
        if isinstance(r, Mapping) and r.get("hasil_kode") == KODE_GURU and op not in profil
        and isinstance(r.get("hasil_id"), str))


def hitung(mentah, akun: Iterable[Mapping], *, terikat, pemilik_siswa) -> int:
    """Guru mandiri aktif yang belum terikat lembaga dan belum memegang anak. `pemilik_siswa` huruf kecil."""
    mandiri = id_guru_mandiri(mentah)
    return sum(
        1 for a in akun
        if a.get("id_akun") in mandiri and a.get("peran", "guru") == "guru" and not a.get("dinonaktifkan")
        and a.get("pengguna") not in terikat and str(a.get("pengguna", "")).casefold() not in pemilik_siswa)


def jumlah() -> int:
    """Hitungan untuk antrean admin; galat baca apa pun = 0."""
    try:
        mentah = auth.muat_sandi()
        akun = auth.muat_akun()
        with database.buka() as kon:
            terikat = lembaga_store.guru_terikat(kon)
            pemilik = frozenset(str(b[0]).casefold() for b in kon.execute("SELECT DISTINCT pemilik FROM siswa"))
        return hitung(mentah, akun, terikat=terikat, pemilik_siswa=pemilik)
    except Exception:           # noqa: BLE001 - penanda antrean tidak boleh menjatuhkan halaman admin
        return 0

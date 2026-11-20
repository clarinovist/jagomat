"""Rute admin baca-saja `/admin/kurikulum` (tabel materi Kurikulum Merdeka per kelas) dan `/admin/kurikulum/buat`.

Keduanya hanya membaca: tabel memakai agregat COUNT tabel `soal` (DB tak terbaca = kolom "–", halaman tetap 200),
sedangkan Buat soal membangkitkan contoh dari generator tanpa menulis apa pun. Non-admin mendapat 404 identik.
Query di luar kunci yang dikenal atau bernilai tak sah = 404.
"""
from __future__ import annotations

import random
from typing import Dict, Optional, Tuple

import admin_http as h
import admin_kurikulum_buat_pages as buat_ui
import admin_kurikulum_merdeka_pages as ui
import kurikulum_buat_soal as buat
import kurikulum_kelas as kk
import kurikulum_kelas_hitung as hitung

RUTE = ui.RUTE
RUTE_BUAT = buat_ui.RUTE
JUDUL = "Kurikulum Merdeka"
SUBJUDUL = "Materi per kelas sesuai buku siswa Kurikulum Merdeka, dan jenis soal Jagomat yang melatihnya."
JUDUL_BUAT = "Buat soal"
SUBJUDUL_BUAT = "Contoh soal dari satu bab, hanya untuk dilihat. Tidak disimpan."
KUNCI_QUERY_BUAT = frozenset({"kelas", "bab", "jumlah", "seed"})
MAKS_DIGIT = 10
PESAN_GAGAL_BUAT = "Soal belum dapat dibuat untuk bab ini."


def _angka_ketat(nilai: Optional[str]) -> int:
    """Bilangan bulat desimal kanonik (tanpa nol di depan, tanda, atau spasi); selain itu ValueError."""
    if nilai is None or not nilai.isascii() or not nilai.isdigit() or len(nilai) > MAKS_DIGIT or str(int(nilai)) != nilai:
        raise ValueError("angka tidak sah")
    return int(nilai)


def _parameter_buat(query: Dict[str, str]) -> Tuple[kk.Kelas, kk.Bab, int, Optional[int]]:
    """(kelas, bab, jumlah, seed|None) tervalidasi ketat; apa pun yang tak sah = ValueError (404)."""
    kelas, nomor = _angka_ketat(query.get("kelas")), _angka_ketat(query.get("bab"))
    ditemukan = hitung.cari_bab(kelas, nomor)
    if ditemukan is None:
        raise ValueError("bab tidak ada")
    jumlah = _angka_ketat(query["jumlah"]) if "jumlah" in query else buat.JUMLAH_BAWAAN
    if jumlah not in buat.JUMLAH_PILIHAN:
        raise ValueError("jumlah tidak sah")
    seed = None
    if "seed" in query:
        seed = _angka_ketat(query["seed"])
        if not buat.SEED_MIN <= seed <= buat.SEED_MAKS:
            raise ValueError("seed tidak sah")
    return ditemukan[0], ditemukan[1], jumlah, seed


def _tabel(penangan, principal) -> None:
    pemakaian = hitung.pemakaian_per_template_level()
    per_kelas = tuple((k.kelas, hitung.ringkasan_kelas(k, pemakaian)) for k in kk.KELAS)
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", ui.halaman(per_kelas, pemakaian is not None), penangan=penangan,
        judul=JUDUL, subjudul=SUBJUDUL))


def _halaman_buat(penangan, principal) -> None:
    try:
        kelas, bab, jumlah, seed = _parameter_buat(h._query(penangan, diizinkan=KUNCI_QUERY_BUAT))
    except ValueError:
        h._tidak_ada(penangan)
        return
    if seed is None:
        seed = random.SystemRandom().randint(buat.SEED_MIN, buat.SEED_MAKS)
    try:
        hasil = buat.buat_soal_bab(kelas.kelas, bab, jumlah, seed)
        isi = buat_ui.halaman(kelas.kelas, bab, hasil, jumlah, seed)
    except (RuntimeError, ValueError, KeyError):
        h._galat(penangan, 500, PESAN_GAGAL_BUAT)
        return
    h._kirim_privat(penangan, h._halaman_admin(
        principal, "kurikulum", isi, penangan=penangan, judul=JUDUL_BUAT, subjudul=SUBJUDUL_BUAT))


def tangani_get(penangan, jalur) -> bool:
    if jalur not in (RUTE, RUTE_BUAT):
        return False
    principal = h._principal_admin(penangan)
    if principal is None:
        h._tidak_ada(penangan)
        return True
    if jalur == RUTE_BUAT:
        _halaman_buat(penangan, principal)
        return True
    try:
        h._query(penangan, diizinkan=set())
    except ValueError:
        h._tidak_ada(penangan)
        return True
    _tabel(penangan, principal)
    return True

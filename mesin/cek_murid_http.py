"""Rute murid `POST /murid/cek/mulai` (F2b): mulai/lanjutkan cek kemampuan dari sesi anak.

Pola `contest_http`: gerbang mati -> False, sehingga rantai lama menjawab persis seperti jalur murid tak dikenal.
Diletakkan di rantai POST `web.py` setelah guard asal dan sebelum `student_http` (sebelum `_lolos_sandi`).

Cara kerja (memakai ulang alur anak yang ada, tanpa menyalin mesin soal/penilaian): satu transaksi
`BEGIN IMMEDIATE` -> `siswa_dari_akun` -> `cek_murid.mulai` -> `share_links.buat` -> commit, lalu 303 ke
`/mulai/<token>` (layar cek anak `cek_anak_http`). Sesi login anak TIDAK dihapus (beda dengan `hp_ini` guru) dan
memakai `?di=akun` (layar akhir: tautan kembali ke /murid), bukan `?di=hp-ini` (CTA layar akhir varian itu menuju rute guru). Token bearer ada di `Location`, jadi respons
no-store dan tanpa referrer.

`siswa_id` dan `id_akun` HANYA dari principal sesi server. Body POST harus kosong (field apa pun = 400 tanpa
menulis); query string tidak dibaca. Pesan galat tetap, `str(galat)` tidak pernah dipantulkan.
"""
from __future__ import annotations

from datetime import datetime, timezone

import cek_gratis
import cek_murid
import database
import share_links
from cek_gratis_skor import FORMAT_WAKTU
from support_pages import halaman_pesan as _halaman
from support_pages import halaman_pesan_murid as _halaman_murid

BATAS_TUBUH = 1024
TUJUAN_BERANDA = "/murid"
PESAN_BELUM_TERSEDIA = (
    "<h1>Cek belum bisa dimulai</h1><p>Cek untuk kelasmu belum tersedia. "
    "Bilang ke Ayah atau Bunda, ya.</p>"'<p><a href="/murid">Kembali ke ruang belajar</a></p>'
)


def _sekarang() -> str:
    return datetime.now(timezone.utc).strftime(FORMAT_WAKTU)


def _tidak_ada(penangan) -> None:
    penangan._kirim(_halaman_murid("404", "<h1>Halaman tidak ada</h1>"), 404)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("Referrer-Policy", "no-referrer")
    penangan.send_header("X-Robots-Tag", "noindex, nofollow")
    penangan.end_headers()


def _body_kosong(penangan) -> bool:
    """True bila body ada (sah) dan kosong; selain itu respons penolakan sudah dikirim."""
    tubuh = penangan._baca_tubuh(BATAS_TUBUH)
    if tubuh is None:
        penangan._tolak_isian()
        return False
    if tubuh.strip():
        penangan._tolak_isian()
        return False
    return True


def _jalankan(principal):
    """Satu transaksi; mengembalikan tujuan 303 (tautan anak, atau beranda bila cek sudah selesai)."""
    import students

    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)
        if siswa_id is None:
            raise cek_gratis.CekTidakDitemukan("Cek tidak ditemukan.")
        hasil = cek_murid.mulai(kon, principal.id_akun, siswa_id, _sekarang())
        try:
            token = share_links.buat(kon, hasil["sesi_id"])
        except ValueError:  # sesi sudah dikumpulkan/dibatalkan: tidak ada yang perlu dilanjutkan
            return TUJUAN_BERANDA
        return "/mulai/" + token + "?di=akun"


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/murid/cek/mulai`; False bila bukan milik modul, gerbang mati, atau pemanggil bukan murid."""
    if jalur != cek_murid.RUTE_MULAI or not cek_murid.gerbang_aktif():
        return False
    principal = penangan._principal()
    if principal is None:
        penangan._kirim(_halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401)
        return True
    if principal.peran != "murid":
        return False  # guru/admin: rantai lama (identik jalur tak dikenal)
    if not _body_kosong(penangan):
        return True
    try:
        tujuan = _jalankan(principal)
    except (cek_gratis.CekTidakDitemukan, cek_gratis.CekPersetujuanDiperlukan):
        _tidak_ada(penangan)
        return True
    except ValueError:  # CekBelumTersedia dan id_akun tak sah; pesan tetap
        penangan._kirim(_halaman_murid("Cek belum bisa dimulai", PESAN_BELUM_TERSEDIA), 409)
        return True
    _alihkan(penangan, tujuan)
    return True

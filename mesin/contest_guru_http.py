"""Rute HTTP guru/admin untuk Latihan Lomba satu anak: riwayat (GET, hanya-lihat) dan pengaturan Mode Lomba (POST).

Kontrak dengan `web.py`: `tangani_get(penangan, jalur, jalur_penuh)` dipanggil setelah `_lolos_sandi` dan sebelum
penangkap `/anak/...`; True bila jalur milik modul ini dan sudah dijawab, False bila bukan atau gerbang mati
(sehingga jawabannya identik dengan jalur `/anak/...` lain yang tidak dikenal). `tangani_post(penangan, jalur)`
dipasang setelah `_lolos_sandi` dan `_asal_sama_post`, di samping `parent_report_http.tangani_guru_post`.

Rute: ``/anak/<siswa_id>/lomba`` (kartu Mode Lomba + progress), ``/anak/<siswa_id>/lomba/<sesi_id>`` (detail sesi
selesai), dan POST ``/anak/<siswa_id>/lomba/pengaturan`` (aktifkan/matikan Mode Lomba, target harian, hitung mundur).
Id hanya angka ASCII 1-12 digit. Anak tidak ada, bukan milik pemanggil (`_bisa_lihat_siswa`), sesi bukan
milik anak itu, sesi masih berjalan, id tidak sah, dan sakelar induk mati semuanya dijawab 404 yang sama dengan
`parent_report_http` (tubuh dan header identik); POST dengan 404 tidak menulis apa pun. Isian POST dibaca SETELAH
kepemilikan terbukti, jadi bukan pemilik tidak bisa membedakan 404 dari 400. Satu-satunya tulisan DB di GET adalah
penutupan malas sesi yang batas waktunya sudah lewat (lewat `contest_results`).
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import contest_assignment_store as AS
import contest_gate
import contest_guru_pages as H
import contest_paket as PK
import contest_results as R
import contest_store as K
import database
from support_pages import halaman_pesan

MAKS_DIGIT_ID = 12
BATAS_FORM = 2048
_POLA_RUTE = re.compile(r"/anak/([^/]+)/lomba(?:/([^/]+))?")
_POLA_PENGATURAN = re.compile(r"/anak/([^/]+)/lomba/pengaturan")
_POLA_ID = re.compile(rf"[0-9]{{1,{MAKS_DIGIT_ID}}}")
_KOLOM_PENGATURAN = frozenset({"aktif", "target", "hitung_mundur"})
_NILAI_AKTIF = {"1": True, "0": False}
_NILAI_CENTANG = "1"


class _TidakAda(Exception):
    """Rute dikenal tetapi sasarannya tidak boleh dilihat; dijawab 404 yang sama untuk semua sebabnya."""


@dataclass(frozen=True)
class _Pengaturan:
    aktif: bool
    target_harian: Optional[int]
    tampil_hitung_mundur: Optional[bool]


def _sekarang() -> int:
    return int(time.time())


def _kenali(jalur: str) -> Optional[Tuple[str, Optional[str]]]:
    cocok = _POLA_RUTE.fullmatch(jalur)
    return None if cocok is None else (cocok.group(1), cocok.group(2))


def _angka_id(mentah: str) -> int:
    if _POLA_ID.fullmatch(mentah) is None:
        raise _TidakAda(mentah)
    return int(mentah)


def _kirim_tidak_ada(penangan) -> None:
    penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def _tersimpan(jalur_penuh: str) -> bool:
    pasangan = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query, keep_blank_values=True)
    return pasangan.get("tersimpan") == ["1"]


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET ``/anak/<id>/lomba[/<sesi_id>]``; False bila bukan milik modul atau gerbang mati."""
    rute = _kenali(jalur)
    if rute is None or not contest_gate.aktif():
        return False
    try:
        isi = _bangun(penangan, *rute, tersimpan=_tersimpan(jalur_penuh))
    except (_TidakAda, K.SesiTidakDitemukan, K.SesiBerjalan):
        _kirim_tidak_ada(penangan)
        return True
    penangan._kirim_tautan(isi)
    return True


def _bangun(penangan, siswa_mentah: str, sesi_mentah: Optional[str], tersimpan: bool = False) -> bytes:
    siswa_id = _angka_id(siswa_mentah)
    sesi_id = None if sesi_mentah is None else _angka_id(sesi_mentah)
    ident = penangan._identitas()
    with database.buka() as kon:
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
        if siswa is None or not penangan._bisa_lihat_siswa(kon, siswa_id):
            raise _TidakAda(siswa_id)
        if sesi_id is None:
            return _progres(kon, siswa, ident, tersimpan)
        return H.halaman_detail(siswa, R.hasil_rinci(kon, siswa_id, sesi_id, _sekarang()), ident)


def _progres(kon, siswa, ident, tersimpan: bool) -> bytes:
    sekarang = _sekarang()
    siswa_id = int(siswa["id"])
    return H.halaman_progres(
        siswa, R.progres(kon, siswa_id, sekarang), R.jenis_sering_salah(kon, siswa_id, sekarang), ident,
        penugasan=AS.ambil(kon, siswa_id), tersimpan=tersimpan)


# --- POST pengaturan Mode Lomba -------------------------------------------------------------------

def _baca_isian(penangan) -> Optional[Dict[str, str]]:
    """Isian form satu-nilai per kolom dengan kolom yang dikenal saja; None bila tidak sah."""
    tubuh = penangan._baca_tubuh(BATAS_FORM)
    if tubuh is None:
        return None
    try:
        pasangan = urllib.parse.parse_qs(tubuh.decode("utf-8", "strict"), keep_blank_values=True, max_num_fields=16)
    except (UnicodeDecodeError, ValueError):
        return None
    if any(len(nilai) != 1 for nilai in pasangan.values()) or not set(pasangan) <= _KOLOM_PENGATURAN:
        return None
    return {nama: nilai[0] for nama, nilai in pasangan.items()}


def _target_dari_isian(mentah: Optional[str]) -> Tuple[bool, Optional[int]]:
    """(sah, target): "paket" -> None (ikut paket); angka harus salah satu pilihan Guru."""
    if mentah == H.NILAI_IKUT_PAKET:
        return True, None
    pilihan = {str(n): n for n in H.PILIHAN_TARGET}
    if mentah in pilihan:
        return True, pilihan[mentah]
    return False, None


def _baca_pengaturan(penangan) -> Optional[_Pengaturan]:
    """Pengaturan tervalidasi dari isian; None bila isian tidak sah. Hitung mundur sama dengan paket -> None."""
    isian = _baca_isian(penangan)
    if isian is None or isian.get("aktif") not in _NILAI_AKTIF:
        return None
    sah, target = _target_dari_isian(isian.get("target"))
    centang = isian.get("hitung_mundur")
    if not sah or centang not in (None, _NILAI_CENTANG):
        return None
    tampil = centang is not None
    return _Pengaturan(
        aktif=_NILAI_AKTIF[isian["aktif"]], target_harian=target,
        tampil_hitung_mundur=None if tampil == PK.PAKET_AKTIF.tampil_hitung_mundur else tampil)


def _pastikan_boleh(penangan, kon, siswa_id: int) -> None:
    ada = kon.execute("SELECT 1 FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    if ada is None or not penangan._bisa_lihat_siswa(kon, siswa_id):
        raise _TidakAda(siswa_id)


def _simpan(penangan, kon, siswa_id: int) -> bool:
    """Validasi lalu tulis dalam satu transaksi; False bila isian tidak sah (jawaban 400 sudah dikirim)."""
    _pastikan_boleh(penangan, kon, siswa_id)
    pengaturan = _baca_pengaturan(penangan)
    if pengaturan is None:
        penangan._tolak_isian()
        return False
    kon.execute("BEGIN IMMEDIATE")
    _pastikan_boleh(penangan, kon, siswa_id)
    AS.atur(kon, siswa_id, aktif=pengaturan.aktif, target_harian=pengaturan.target_harian,
            tampil_hitung_mundur=pengaturan.tampil_hitung_mundur, sekarang=_sekarang(),
            oleh=penangan._identitas()[0][:AS.MAKS_PANJANG_OLEH])
    return True


def _alihkan_tersimpan(penangan, siswa_id: int) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", f"{H.alamat_progres(siswa_id)}?tersimpan=1")
    penangan.send_header("Content-Length", "0")
    penangan.send_header("Cache-Control", "no-store")
    penangan.end_headers()


def tangani_post(penangan, jalur: str) -> bool:
    """POST ``/anak/<id>/lomba/pengaturan``; False bila bukan milik modul. Sakelar induk mati -> 404 tanpa tulis."""
    cocok = _POLA_PENGATURAN.fullmatch(jalur)
    if cocok is None:
        return False
    try:
        if not contest_gate.aktif():
            raise _TidakAda(jalur)
        siswa_id = _angka_id(cocok.group(1))
        with database.buka() as kon:
            tersimpan = _simpan(penangan, kon, siswa_id)
    except _TidakAda:
        _kirim_tidak_ada(penangan)
        return True
    if tersimpan:
        _alihkan_tersimpan(penangan, siswa_id)
    return True

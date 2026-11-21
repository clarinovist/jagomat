"""Rute HTTP murid untuk Latihan Lomba (``/murid/lomba/...``).

Kontrak dengan `web.py`: `tangani_get(penangan, jalur, jalur_penuh)` dan `tangani_post(penangan, jalur)`
mengembalikan True bila jalur milik modul ini dan sudah dijawab, False bila bukan (atau gerbang mati)
sehingga `student_http` yang menjawab seperti biasa (404 yang sama dengan jalur murid tak dikenal).

Palang: hanya murid yang masuk; sesi/hasil milik anak lain, id tak ada, id bukan angka, dan nomor soal
di luar 1-10 semuanya dijawab 404 yang byte-identik dengan jalur tak dikenal. Waktu selalu dari jam
server lewat `_sekarang()`; jam klien tidak pernah dipercaya (lihat `contest_store`).
"""
from __future__ import annotations

import html
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Optional

import contest_gate
import contest_pages as P
import contest_session
import contest_store as K
import database
from support_pages import halaman_pesan as _halaman

BATAS_TUBUH = 2048
MAKS_DIGIT_ID = 12
_POLA_ID = re.compile(rf"[0-9]{{1,{MAKS_DIGIT_ID}}}")
_POLA_NOMOR = re.compile(r"[0-9]{1,2}")
_GET_AWAL, _GET_SESI, _GET_SELESAI, _GET_HASIL = "awal", "sesi", "selesai", "hasil"
_POST_MULAI, _POST_JAWAB, _POST_KUMPUL = "mulai", "jawab", "kumpul"
_PESAN_SESI_HABIS = ("Sesi kamu sudah habis atau akun lain masuk di perangkat ini. "
                     "Masuk lagi dengan nama & sandimu, ya.")


class _TidakAda(Exception):
    """Bentuk rute dikenal tetapi id/nomor tidak sah; dijawab 404 yang sama dengan jalur tak dikenal."""


def _sekarang() -> int:
    return int(time.time())


def _kenali(jalur: str, method: str) -> Optional[tuple]:
    """(nama rute, id sesi mentah atau None) bila jalur milik modul ini, selain itu None."""
    bagian = jalur.split("/")
    if bagian[:3] != ["", "murid", "lomba"]:
        return None
    sisa = bagian[3:]
    if method == "GET":
        if sisa == []:
            return _GET_AWAL, None
        if len(sisa) == 2 and sisa[0] == "sesi":
            return _GET_SESI, sisa[1]
        if len(sisa) == 3 and sisa[0] == "sesi" and sisa[2] == "selesai":
            return _GET_SELESAI, sisa[1]
        if len(sisa) == 2 and sisa[0] == "hasil":
            return _GET_HASIL, sisa[1]
        return None
    if sisa == ["mulai"]:
        return _POST_MULAI, None
    if len(sisa) == 3 and sisa[0] == "sesi" and sisa[2] in (_POST_JAWAB, _POST_KUMPUL):
        return sisa[2], sisa[1]
    return None


def _angka_id(mentah: Optional[str]) -> int:
    if mentah is None or _POLA_ID.fullmatch(mentah) is None:
        raise _TidakAda(mentah)
    return int(mentah)


def _nomor_soal(mentah: Optional[str]) -> int:
    if mentah is None or _POLA_NOMOR.fullmatch(mentah) is None:
        raise _TidakAda(mentah)
    nomor = int(mentah)
    if not K.NOMOR_PERTAMA <= nomor <= K.NOMOR_TERAKHIR:
        raise _TidakAda(mentah)
    return nomor


@dataclass(frozen=True)
class _Respons:
    """Keputusan respons; dikirim SETELAH transaksi commit supaya GET susulan klien melihat data baru."""

    kode: int = 200
    isi: bytes = b""
    tujuan: Optional[str] = None
    tautan: bool = True


def _alihkan(tujuan: str) -> _Respons:
    return _Respons(kode=303, tujuan=tujuan)


def _halaman_tautan(isi: bytes, kode: int = 200) -> _Respons:
    return _Respons(kode=kode, isi=isi)


def _halaman_biasa(isi: bytes, kode: int = 200) -> _Respons:
    return _Respons(kode=kode, isi=isi, tautan=False)


def _respons_tidak_ada() -> _Respons:
    return _halaman_biasa(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)


def _kirim(penangan, respons: _Respons) -> None:
    if respons.tujuan is not None:
        penangan.send_response(respons.kode)
        penangan.send_header("Location", respons.tujuan)
        penangan.send_header("Content-Length", "0")
        penangan.send_header("Cache-Control", "no-store")
        penangan.end_headers()
    elif respons.tautan:
        penangan._kirim_tautan(respons.isi, respons.kode)
    else:
        penangan._kirim(respons.isi, respons.kode)


def _query(jalur_penuh: str) -> Dict[str, list]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query, keep_blank_values=True)


def _tunggal(pasangan: Dict[str, list], nama: str) -> Optional[str]:
    """Nilai satu-satunya untuk `nama`; None bila tidak ada; nilai ganda dianggap tidak sah."""
    nilai = pasangan.get(nama)
    if nilai is None:
        return None
    if len(nilai) != 1:
        raise _TidakAda(nama)
    return nilai[0]


def _tolak_masuk(penangan) -> None:
    """Murid belum masuk: 303 ke /masuk, pesan sama dengan student_http."""
    penangan.send_response(303)
    penangan.send_header("Location", "/masuk?" + urllib.parse.urlencode({"galat": _PESAN_SESI_HABIS}))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _belum_terhubung(pengguna: str) -> _Respons:
    return _halaman_biasa(_halaman(
        "Belum terhubung",
        f"<h1>Halo, {html.escape(pengguna)}</h1>"
        "<p>Akunmu belum dihubungkan ke daftar siswa. Minta gurumu menyiapkannya.</p>"))


def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET ``/murid/lomba...``; False bila bukan milik modul atau gerbang mati."""
    rute = _kenali(jalur, "GET")
    if rute is None or not contest_gate.aktif():
        return False
    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        _tolak_masuk(penangan)
        return True
    try:
        respons = _jalankan_get(kredensial[0], rute, jalur_penuh)
    except (_TidakAda, K.SesiTidakDitemukan):
        respons = _respons_tidak_ada()
    _kirim(penangan, respons)
    return True


def _jalankan_get(pengguna: str, rute: tuple, jalur_penuh: str) -> _Respons:
    import students

    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, pengguna)
        if siswa_id is None:
            return _belum_terhubung(pengguna)
        return _layani_get(kon, siswa_id, rute, jalur_penuh)


def _layani_get(kon, siswa_id: int, rute: tuple, jalur_penuh: str) -> _Respons:
    nama, id_mentah = rute
    sekarang = _sekarang()
    if nama == _GET_AWAL:
        berjalan = K.sesi_berjalan(kon, siswa_id, sekarang)
        return _halaman_tautan(P.halaman_awal(berjalan, berjalan.sisa_detik(sekarang) if berjalan else 0))
    pasangan = _query(jalur_penuh)
    nomor = K.NOMOR_PERTAMA
    if nama == _GET_SESI and "no" in pasangan:
        nomor = _nomor_soal(_tunggal(pasangan, "no"))
    sesi = K.ambil_sesi(kon, siswa_id, _angka_id(id_mentah), sekarang)
    if nama == _GET_HASIL:
        return _layani_hasil(kon, siswa_id, sesi, sekarang)
    if sesi.status != K.BERJALAN:
        return _alihkan(P.alamat_hasil(sesi.id))
    sisa = sesi.sisa_detik(sekarang)
    terjawab = K.nomor_terjawab(kon, siswa_id, sesi.id)
    if nama == _GET_SELESAI:
        return _halaman_tautan(P.halaman_selesai(sesi.id, K.NOMOR_TERAKHIR - len(terjawab), sisa))
    soal = K.soal_untuk_anak(kon, siswa_id, sesi.id, nomor)
    galat = _tunggal(pasangan, "galat") == "angka"
    return _halaman_tautan(P.halaman_soal(sesi.id, soal, terjawab, sisa, galat))


def _layani_hasil(kon, siswa_id: int, sesi: K.SesiRingkas, sekarang: int) -> _Respons:
    if sesi.status == K.BERJALAN:
        return _alihkan(P.alamat_sesi(sesi.id))
    return _halaman_tautan(P.halaman_hasil(K.hasil_ringkas(kon, siswa_id, sesi.id, sekarang)))


def _baca_isian(penangan) -> Optional[Dict[str, str]]:
    """Isian form satu-nilai per kolom; None bila penolakan sudah dikirim."""
    tubuh = penangan._baca_tubuh(BATAS_TUBUH)
    if tubuh is None:
        _tolak_ukuran(penangan)
        return None
    try:
        pasangan = urllib.parse.parse_qs(tubuh.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError:
        penangan._tolak_isian()
        return None
    if any(len(nilai) != 1 for nilai in pasangan.values()):
        penangan._tolak_isian()
        return None
    return {nama: nilai[0] for nama, nilai in pasangan.items()}


def _tolak_ukuran(penangan) -> None:
    """413 bila Content-Length jelas melampaui batas; selain itu 400 generik."""
    teks = (penangan.headers.get("Content-Length") or "").strip()
    terlalu_besar = teks.isascii() and teks.isdigit() and int(teks) > BATAS_TUBUH
    penangan._tolak_isian(413 if terlalu_besar else 400)


def tangani_post(penangan, jalur: str) -> bool:
    """POST ``/murid/lomba...``; False bila bukan milik modul atau gerbang mati."""
    rute = _kenali(jalur, "POST")
    if rute is None or not contest_gate.aktif():
        return False
    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        penangan._kirim(_halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401)
        return True
    isian = _baca_isian(penangan)
    if isian is None:
        return True
    try:
        respons = _jalankan_post(kredensial[0], rute, isian)
    except (_TidakAda, K.SesiTidakDitemukan):
        respons = _respons_tidak_ada()
    _kirim(penangan, respons)
    return True


def _jalankan_post(pengguna: str, rute: tuple, isian: Dict[str, str]) -> _Respons:
    import students

    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        siswa_id = students.siswa_dari_akun(kon, pengguna)
        if siswa_id is None:
            raise _TidakAda(pengguna)
        return _layani_post(kon, siswa_id, rute, isian)


def _layani_post(kon, siswa_id: int, rute: tuple, isian: Dict[str, str]) -> _Respons:
    nama, id_mentah = rute
    sekarang = _sekarang()
    if nama == _POST_MULAI:
        return _mulai(kon, siswa_id, sekarang)
    sesi_id = _angka_id(id_mentah)
    if nama == _POST_KUMPUL:
        K.kumpulkan(kon, siswa_id, sesi_id, sekarang)
        return _alihkan(P.alamat_hasil(sesi_id))
    return _jawab(kon, siswa_id, sesi_id, isian, sekarang)


def _mulai(kon, siswa_id: int, sekarang: int) -> _Respons:
    try:
        sesi = K.mulai_atau_lanjut(kon, siswa_id, sekarang)
    except contest_session.GagalMerakitSesi:
        return _halaman_biasa(P.halaman_gagal_siapkan(), 503)
    return _alihkan(P.alamat_sesi(sesi.id))


def _jawab(kon, siswa_id: int, sesi_id: int, isian: Dict[str, str], sekarang: int) -> _Respons:
    nomor = _nomor_soal(isian.get("no"))
    pindah = _nomor_soal(isian["pindah"]) if "pindah" in isian else None
    sesi = K.ambil_sesi(kon, siswa_id, sesi_id, sekarang)
    if sesi.status != K.BERJALAN:
        return _alihkan(P.alamat_hasil(sesi_id))
    pengganti = _simpan_bila_perlu(kon, siswa_id, sesi_id, nomor, pindah, isian, sekarang)
    if pengganti is None and isian.get("aksi") == "selesai":
        pengganti = P.alamat_selesai(sesi_id)       # isian terketik sudah tersimpan di atas
    return _alihkan(pengganti or P.alamat_sesi(sesi_id, pindah or nomor))


def _simpan_bila_perlu(kon, siswa_id: int, sesi_id: int, nomor: int, pindah: Optional[int],
                       isian: Dict[str, str], sekarang: int) -> Optional[str]:
    """Simpan `jawaban` bila ada; kembalikan alamat pengganti bila perlu mengalihkan, selain itu None.

    Isian kosong hanya menghapus jawaban lewat tombol Simpan (`aksi=simpan`) tanpa `pindah`; kosong
    yang ikut klik nomor/Sebelumnya/Berikutnya diabaikan supaya pindah soal tidak menghapus apa pun.
    """
    if "jawaban" not in isian:
        return None
    nilai = isian["jawaban"]
    menghapus = isian.get("aksi") == "simpan" and pindah is None
    if not nilai.strip() and not menghapus:
        return None
    try:
        K.simpan_jawaban(kon, siswa_id, sesi_id, nomor, nilai, sekarang)
    except K.SesiSelesai:
        return P.alamat_hasil(sesi_id)
    except K.JawabanTidakSah:
        return P.alamat_sesi(sesi_id, nomor, galat=True)
    return None

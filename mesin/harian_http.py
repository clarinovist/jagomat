"""Rute HTTP murid Latihan Harian (`/murid/latihan-harian...`).

Kontrak dengan `web.py` (pola `contest_http`/`pesanan_murid_http`): `tangani_get(penangan, jalur, jalur_penuh)` dan
`tangani_post(penangan, jalur)` mengembalikan True bila jalur milik modul ini dan sudah dijawab, False bila bukan atau
sakelar `LATIHAN_HARIAN` mati (`akses_harian.aktif()`), sehingga `student_http` menjawab seperti jalur murid tak
dikenal (404 identik). Dipanggil sebelum `_lolos_sandi`; POST sesudah `_asal_sama_post` di dispatcher.

Rute:
- GET  `/murid/latihan-harian`                  beranda tingkat (saran, lanjutkan sesi, atau jatah habis)
- POST `/murid/latihan-harian/mulai`            form `tingkat`; mulai/lanjutkan -> 303 ke soal
- GET  `/murid/latihan-harian/sesi/<id>?no=<n>` soal ke-n (tanpa kunci/pembahasan bila belum dijawab)
- POST `/murid/latihan-harian/sesi/<id>/jawab`  form `no`, `pilihan`; mengunci jawaban -> 303 ke soal yang sama
- GET  `/murid/latihan-harian/sesi/<id>/ringkasan` hasil (jumlah benar dari 10, tanpa peringkat)

Palang: `siswa_id` HANYA dari sesi server (`students.siswa_dari_akun`); id sesi/nomor dari URL hanya dipakai bersama
`siswa_id` itu. Sesi anak lain, id tak ada, id bukan angka, nomor di luar sesi, dan soal yang belum gilirannya
semuanya = 404 byte-identik dengan jalur tak dikenal, tanpa efek samping. Waktu dari jam server (`_sekarang`).
Jawab kedua untuk soal yang sama tidak mengubah apa pun dan dialihkan kembali ke soal itu (aman untuk klik ganda).
Jatah gratis habis saat mulai = 303 ke beranda tanpa menulis; beranda menampilkan pesan ramah.
Tanpa token form tambahan: pola murid yang ada (cookie SameSite + `_asal_sama_post`), seperti `contest_http`.
"""
from __future__ import annotations

import html
import re
import time
import urllib.parse
from typing import Dict, Optional

import akses_harian
import daftar_anak_gate
import database
import harian_beruntun
import harian_latihan_store as hs
import harian_pages as P
import harian_rakit
import harian_tingkat as ht
import harian_waktu
from support_pages import halaman_pesan_murid as _halaman

DASAR = P.DASAR
MAKS_DIGIT_ID = 12
_POLA_ID = re.compile(r"[0-9]{1,%d}" % MAKS_DIGIT_ID)
_POLA_NOMOR = re.compile(r"[0-9]{1,2}")
_GET_AWAL, _GET_SESI, _GET_RINGKASAN = "awal", "sesi", "ringkasan"
_POST_MULAI, _POST_JAWAB = "mulai", "jawab"
KOLOM_MULAI = frozenset({"tingkat"})
KOLOM_JAWAB = frozenset({"no", "pilihan"})


class _TidakAda(Exception):
    """Bentuk rute dikenal tetapi id/nomor tak sah; dijawab 404 yang sama dengan jalur tak dikenal."""


def _sekarang() -> int:
    return int(time.time())


def _kenali(jalur: str, method: str) -> Optional[tuple]:
    """(nama rute, id sesi mentah atau None) bila jalur milik modul ini, selain itu None."""
    bagian = jalur.split("/")
    if bagian[:3] != ["", "murid", "latihan-harian"]:
        return None
    sisa = bagian[3:]
    if method == "GET":
        if sisa == []:
            return _GET_AWAL, None
        if len(sisa) == 2 and sisa[0] == "sesi":
            return _GET_SESI, sisa[1]
        if len(sisa) == 3 and sisa[0] == "sesi" and sisa[2] == "ringkasan":
            return _GET_RINGKASAN, sisa[1]
        return None
    if sisa == ["mulai"]:
        return _POST_MULAI, None
    if len(sisa) == 3 and sisa[0] == "sesi" and sisa[2] == "jawab":
        return _POST_JAWAB, sisa[1]
    return None


def _angka(pola: re.Pattern, mentah) -> int:
    if not isinstance(mentah, str) or pola.fullmatch(mentah) is None:
        raise _TidakAda(mentah)
    return int(mentah)


def _alihkan(penangan, tujuan: str) -> None:
    penangan.send_response(303)
    penangan.send_header("Location", tujuan)
    penangan.send_header("Content-Length", "0")
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("Referrer-Policy", "no-referrer")
    penangan.end_headers()


def _tidak_ada(penangan) -> None:
    penangan._kirim(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)


def _tolak_masuk(penangan) -> None:
    from student_http import alamat_masuk_murid
    penangan.send_response(303)
    penangan.send_header("Location", alamat_masuk_murid(penangan))
    penangan.send_header("Content-Length", "0")
    penangan.end_headers()


def _belum_terhubung(penangan, pengguna: str) -> None:
    penangan._kirim(_halaman(
        "Belum terhubung",
        f"<h1>Halo, {html.escape(pengguna)}</h1>"
        "<p>Akunmu belum dihubungkan ke daftar siswa. Minta gurumu menyiapkannya.</p>"))


# --- GET -----------------------------------------------------------------------------------------

def tangani_get(penangan, jalur: str, jalur_penuh: str = "") -> bool:
    """GET `/murid/latihan-harian...`; False bila bukan milik modul atau sakelar mati."""
    rute = _kenali(jalur, "GET")
    if rute is None or not akses_harian.aktif():
        return False
    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        _tolak_masuk(penangan)
        return True
    try:
        _jalankan_get(penangan, kredensial[0], rute, jalur_penuh)
    except (_TidakAda, hs.HarianTidakDitemukan):
        _tidak_ada(penangan)
    return True


def _jalankan_get(penangan, pengguna: str, rute: tuple, jalur_penuh: str) -> None:
    import students

    with database.buka() as kon:
        siswa_id = students.siswa_dari_akun(kon, pengguna)
        if siswa_id is None:
            return _belum_terhubung(penangan, pengguna)
        nama, id_mentah = rute
        if nama == _GET_AWAL:
            return _get_awal(penangan, kon, siswa_id)
        sesi = hs.ambil_sesi(kon, siswa_id, _angka(_POLA_ID, id_mentah))
        if nama == _GET_RINGKASAN:
            return _get_ringkasan(penangan, kon, siswa_id, sesi)
        return _get_soal(penangan, kon, siswa_id, sesi, jalur_penuh)


def _ada_halaman_ortu() -> bool:
    """Bendera tampilan: halaman orang tua hanya ada bila sakelar DAFTAR_AKUN_ANAK hidup (sama dengan
    `orang_tua_http.tersedia()`, dibaca langsung dari gerbangnya agar tak ada impor melingkar). Bukan gerbang akses."""
    return daftar_anak_gate.aktif()


def _get_awal(penangan, kon, siswa_id: int) -> None:
    sekarang = _sekarang()
    berjalan = hs.sesi_berjalan(kon, siswa_id)
    habis = hs.kuota(kon, siswa_id, sekarang).habis
    penangan._kirim_privat(P.halaman_beranda(berjalan, habis, ht.saran_tingkat(kon, siswa_id),
                                             hs.tingkat_terakhir(kon, siswa_id), ada_ortu=_ada_halaman_ortu()))


def _nomor_dari_query(jalur_penuh: str) -> Optional[int]:
    pasangan = urllib.parse.parse_qs(urllib.parse.urlparse(jalur_penuh).query, keep_blank_values=True)
    if "no" not in pasangan:
        return None
    if len(pasangan["no"]) != 1:
        raise _TidakAda("no")
    return _angka(_POLA_NOMOR, pasangan["no"][0])


def _get_soal(penangan, kon, siswa_id: int, sesi: hs.SesiRingkas, jalur_penuh: str) -> None:
    nomor = _nomor_dari_query(jalur_penuh)
    if nomor is None:
        if not sesi.berjalan:
            return _alihkan(penangan, P.alamat_ringkasan(sesi.id))
        nomor = sesi.nomor_berikut
    soal, umpan = hs.muat_soal(kon, siswa_id, sesi.id, nomor)
    beruntun = harian_beruntun.hitung(kon, sesi.id, nomor, umpan.benar) if umpan is not None else 1
    penangan._kirim_privat(P.halaman_soal(sesi.id, sesi.tingkat, soal, umpan, sesi.terjawab, beruntun))


def _get_ringkasan(penangan, kon, siswa_id: int, sesi: hs.SesiRingkas) -> None:
    ringkas = hs.ringkasan_sesi(kon, siswa_id, sesi.id)
    if ringkas is None:
        return _alihkan(penangan, P.alamat_sesi(sesi.id, sesi.nomor_berikut))
    tanpa_batas = hs.kuota(kon, siswa_id, _sekarang()).akses.tanpa_batas
    penangan._kirim_privat(P.halaman_ringkasan(ringkas, tampil_ajakan_ortu=_ada_halaman_ortu() and not tanpa_batas))


# --- permukaan lain: kartu beranda murid dan ringkasan halaman orang tua --------------------------

def kartu_beranda_untuk(kon, siswa_id: int) -> str:
    """Kartu "Latihan Harian" untuk beranda murid; "" (tanpa kartu) bila sakelar mati. Hanya membaca."""
    if not akses_harian.aktif():
        return ""
    sekarang = _sekarang()
    return P.kartu_beranda(hs.sesi_berjalan(kon, siswa_id), hs.tingkat_terakhir(kon, siswa_id),
                           hs.kuota(kon, siswa_id, sekarang).habis,
                           hs.hari_latihan(kon, siswa_id, harian_waktu.pekan_wib(sekarang), sekarang))


def ringkasan_untuk_orang_tua(kon, siswa_id: int) -> Optional[hs.RingkasanHarian]:
    """Angka aktivitas 7 hari untuk halaman orang tua; None (tanpa kartu) bila sakelar mati. Hanya membaca."""
    if not akses_harian.aktif():
        return None
    return hs.ringkasan_harian(kon, siswa_id, _sekarang())


# --- POST ----------------------------------------------------------------------------------------

def _baca_isian(penangan, kolom_sah: frozenset) -> Optional[Dict[str, str]]:
    """Form urlencoded kecil dengan tepat kolom `kolom_sah`; None bila penolakan sudah dikirim."""
    from kontak_http import _baca_form
    isian = _baca_form(penangan)
    if isian is None or set(isian) != kolom_sah:
        penangan._tolak_isian()
        return None
    return isian


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/murid/latihan-harian/{mulai,sesi/<id>/jawab}`; False bila bukan milik modul atau sakelar mati."""
    rute = _kenali(jalur, "POST")
    if rute is None or not akses_harian.aktif():
        return False
    kredensial = penangan._sesi_atau_basic(peran_wajib="murid")
    if not kredensial:
        penangan._kirim(_halaman("Perlu masuk", "<h1>Halaman murid</h1>"), 401)
        return True
    nama, id_mentah = rute
    isian = _baca_isian(penangan, KOLOM_MULAI if nama == _POST_MULAI else KOLOM_JAWAB)
    if isian is None:
        return True
    try:
        if nama == _POST_MULAI:
            _post_mulai(penangan, kredensial[0], isian)
        else:
            _post_jawab(penangan, kredensial[0], _angka(_POLA_ID, id_mentah), isian)
    except (_TidakAda, hs.HarianTidakDitemukan):
        _tidak_ada(penangan)
    return True


def _post_mulai(penangan, pengguna: str, isian: Dict[str, str]) -> None:
    import students

    tujuan = None
    try:
        with database.buka() as kon:
            kon.execute("BEGIN IMMEDIATE")
            siswa_id = students.siswa_dari_akun(kon, pengguna)
            if siswa_id is None:
                raise _TidakAda(pengguna)
            sesi, _baru = hs.mulai(kon, siswa_id, isian["tingkat"], _sekarang())
            tujuan = P.alamat_sesi(sesi.id, sesi.nomor_berikut)
    except hs.TingkatTidakSah:
        return penangan._tolak_isian()
    except hs.BatasGratisHabis:
        return _alihkan(penangan, P.ALAMAT_AWAL)
    except harian_rakit.TingkatKosong:
        return penangan._kirim_privat(P.halaman_gagal_siapkan(), 503)
    _alihkan(penangan, tujuan)


def _post_jawab(penangan, pengguna: str, sesi_id: int, isian: Dict[str, str]) -> None:
    import students

    nomor = _angka(_POLA_NOMOR, isian["no"])
    with database.buka() as kon:
        kon.execute("BEGIN IMMEDIATE")
        siswa_id = students.siswa_dari_akun(kon, pengguna)
        if siswa_id is None:
            raise _TidakAda(pengguna)
        try:
            hs.jawab(kon, siswa_id, sesi_id, nomor, isian["pilihan"], _sekarang())
        except hs.PilihanTidakSah:
            return penangan._tolak_isian()
    _alihkan(penangan, P.alamat_sesi(sesi_id, nomor))

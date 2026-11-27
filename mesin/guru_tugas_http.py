"""Rute guru tugas untuk anak tertaut: `GET /guru/tugas`, `GET` dan `POST /guru/tugas/<order_id>` (Fase 3c, WP3).

Identitas HANYA dari sesi: `guru_akun` = `id_akun` principal peran guru. `order_id` dari path dicocokkan dengan tautan
di SQL (`guru_tugas_baca.anak_tertaut`); `siswa_id` hanya hasil fungsi itu, tidak pernah dari form atau URL, dan field
`siswa_id` di form diabaikan. Selain guru tertaut, jawaban 404 identik dengan rute tak dikenal (`lembaga_http._tidak_ada`).

Gerbang `guru_tugas_aturan.guru_tugas_aktif()` mati = semua rute tugas 404 identik, tanpa efek samping.

Urutan POST: laju, baca form, tertaut (404 identik), token (403), isian (400), batas dan duplikat (409), lalu buat.
Tertaut diperiksa SEBELUM token supaya guru yang bukan pemilik selalu mendapat 404 identik, bukan 403.

POST membuat sesi latihan biasa lewat `teacher_pages.buat_sesi_seed_baru` dan mencatat tugas di `guru-tugas.db`. Sesi
sudah commit sendiri (`buat_sesi` memakai RELEASE SAVEPOINT), jadi bila catat gagal sesinya DIBATALKAN lewat
`database.batalkan_sesi`, bukan di-rollback. Celah yang diterima: bila commit latihan.db gagal SETELAH catat berhasil,
baris tugas yatim tertinggal (tabel append-only) dan sesinya tetap aktif. Halaman dan batas tugas aktif mengabaikan
tugas yang sesinya tidak ditemukan `guru_tugas_baca.skor_ringkas`, jadi yatim tidak tampil dan tidak dihitung.
"""
from __future__ import annotations

import html
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import database
import form_token
import guru_jadwal_baca as baca
import guru_jadwal_http as jadwal_http
import guru_pertemuan_aturan as pertemuan
import guru_tautan_anak as tautan_anak
import guru_tugas_aturan as aturan
import guru_tugas_baca as tb
import guru_tugas_dasar as dasar
import guru_tugas_pages as halaman
import kontak_http
import lembaga_http
import teacher_pages
import topics
from learning_cycle_http import GalatForm, _batasi_laju
from pesanan_transfer_pages import WIB_JAM
from support_pages import halaman_pesan

_log = logging.getLogger(__name__)
RUTE_TUGAS = "/guru/tugas"
PREFIX_ANAK = RUTE_TUGAS + "/"
DOMAIN_TOKEN_TUGAS = b"guru-tugas-form-v1:"
POLA_ORDER = re.compile(r"kor_[0-9a-f]{32}")
KUNCI_TOKEN = "token"
KUNCI_TOPIK = "topik"
KUNCI_TENGGAT = "tenggat"
MAKS_TUGAS_TAMPIL = 20
JUDUL_TOLAK = "Tugas belum bisa dibuat"
TEKS_TOPIK_TIDAK_SAH = "Pilih topik dari daftar yang tersedia."
TEKS_DUPLIKAT = "Tugas yang sama baru saja dibuat. Tunggu sebentar sebelum mengirim lagi."
TEKS_BATAS = (f"Anak ini sudah punya {aturan.BATAS_TUGAS_AKTIF} tugas yang belum dikerjakan. "
              "Tunggu sampai salah satunya selesai.")
TEKS_GALAT_SIMPAN = "Tugas belum bisa dibuat sekarang. Coba lagi sebentar."
ALASAN_BATAL_CATAT = "tugas guru tidak tercatat"
TEKS_GALAT_BACA = "Tugas belum bisa dibaca sekarang. Coba lagi sebentar."
GALAT_CATAT = (dasar.GalatTugas, ValueError)
GALAT_SIMPAN_BUAT = (dasar.GalatTugas, sqlite3.Error, OSError, RuntimeError, ValueError)
GALAT_BACA_TUGAS = (dasar.GalatTugas, sqlite3.Error, OSError)


# --- gerbang, jalur, dan jam -------------------------------------------------------------------

def hari_ini_wib(kini: str) -> date:
    """Tanggal WIB dari waktu baku UTC naif (`_kini()`). Tanpa jam sistem di dalam logika ini."""
    waktu_utc = datetime.strptime(kini, pertemuan.FORMAT_WAKTU)
    return (waktu_utc + timedelta(hours=WIB_JAM)).date()


def _rute_tugas(jalur: str) -> bool:
    return jalur == RUTE_TUGAS or jalur.startswith(PREFIX_ANAK)


def _order_dari_jalur(jalur: str) -> Optional[str]:
    """`kor_<32 hex>` dari `/guru/tugas/<order_id>`; None untuk jalur tanpa id yang sah."""
    sisa = jalur[len(PREFIX_ANAK):] if jalur.startswith(PREFIX_ANAK) else ""
    return sisa if POLA_ORDER.fullmatch(sisa) else None


def _kirim_tolak(penangan, kode: int, judul: str, teks: str) -> None:
    isi = halaman_pesan(judul, f"<h1>{html.escape(judul)}</h1><p>{html.escape(teks)}</p>")
    penangan._kirim_privat(isi, kode)


def _kirim_galat_laju(penangan, galat: GalatForm) -> None:
    if galat.status == 429:
        _kirim_tolak(penangan, 429, "Terlalu banyak permintaan", "Coba lagi sebentar.")
    else:
        penangan._tolak_isian(galat.status)


# --- token ---------------------------------------------------------------------------------------

def _aksi_token(order_id: str) -> str:
    return f"tugas:{order_id}"


def _buat_token(principal, penangan, order_id: str) -> str:
    return form_token.buat_token(principal, penangan._ambil_token(), domain=DOMAIN_TOKEN_TUGAS,
                                 aksi=_aksi_token(order_id))


def _token_sah(principal, penangan, order_id: str, token) -> bool:
    return form_token.token_sah(principal, penangan._ambil_token(), token, domain=DOMAIN_TOKEN_TUGAS,
                                aksi=_aksi_token(order_id))


# --- muat dari DB admin (ro) dan latihan.db (ro) --------------------------------------------------

def _akun_order(kon, order_id: str) -> Optional[str]:
    """Akun login anak pemilik order (`kelas_order.akun_id`). Hanya SELECT."""
    baris = kon.execute("SELECT akun_id FROM kelas_order WHERE id = ?", (order_id,)).fetchone()
    return baris["akun_id"] if baris else None


def _nama_anak(akun_id: Optional[str]) -> str:
    """Nama login anak (K6: boleh tampil ke guru); tanpa akun yang terbaca memakai placeholder."""
    nama = tautan_anak.nama_login(akun_id) if akun_id else None
    return nama or baca.PLACEHOLDER_NAMA


def _anak_aktif(akun_id: Optional[str], siswa_id: int) -> bool:
    """Invarian F (3b): anak masih ada bila akun murid pemilik order aktif dan siswanya belum dianonimkan.
    Keluarga yang dihapus tidak menyentuh `kelas_order`, jadi tautan saja tidak cukup. Gagal tertutup."""
    return akun_id is not None and tautan_anak.anak_masih_ada(akun_id, siswa_id)


def _muat_tertaut(kon, guru_akun: str, order_id: str, kini: str) -> Optional[dict]:
    """`{siswa_id, akun_id}` bila order tertaut ke guru ini dan anaknya masih ada; None bila tidak (404 identik)."""
    siswa_id = tb.anak_tertaut(kon, guru_akun, order_id, kini)
    if siswa_id is None:
        return None
    akun_id = _akun_order(kon, order_id)
    if not _anak_aktif(akun_id, siswa_id):
        return None
    return {"siswa_id": siswa_id, "akun_id": akun_id}


def _tertaut(principal, order_id: str, kini: str) -> Optional[dict]:
    """Galat baca DB admin dianggap tidak tertaut (fail-closed)."""
    return jadwal_http._baca_admin(lambda kon: _muat_tertaut(kon, principal.id_akun, order_id, kini), None)


def _muat_daftar(kon, guru_akun: str, kini: str) -> List[dict]:
    """Anak tertaut yang masih ada (invarian F); anak yang keluarganya sudah dihapus tidak dimuat."""
    daftar = []
    for tertaut in tb.daftar_tertaut(kon, guru_akun, kini):
        akun_id = _akun_order(kon, tertaut["order_id"])
        if _anak_aktif(akun_id, tertaut["siswa_id"]):
            daftar.append({"order_id": tertaut["order_id"], "akun_id": akun_id})
    return daftar


def _daftar_anak(principal, kini: str) -> List[dict]:
    baris = jadwal_http._baca_admin(lambda kon: _muat_daftar(kon, principal.id_akun, kini), [])
    daftar = [{"nama": _nama_anak(b["akun_id"]), "order_id": b["order_id"]} for b in baris]
    return sorted(daftar, key=lambda anak_: anak_["nama"].casefold())


def _skor_sesi(tugas: List[dict]) -> Dict[int, dict]:
    """Skor ringkas sesi milik tugas-tugas itu, dibaca dari latihan.db mode ro. Galat baca melempar ke pemanggil."""
    pasangan = [(t["sesi_id"], t["siswa_id"]) for t in tugas]
    if not pasangan:
        return {}
    with jadwal_http._buka_belajar_baca() as kon:
        kon.row_factory = sqlite3.Row  # `skor_ringkas` membaca kolom bernama
        return tb.skor_ringkas(kon, pasangan)


def _tugas_guru_untuk_anak(principal, siswa_id: int) -> List[dict]:
    """Tugas guru ini untuk anak itu, terbaru dulu, hanya yang sesinya ditemukan. Melempar bila sumber tak terbaca."""
    milik = [t for t in dasar.daftar_siswa(siswa_id) if t["guru_akun"] == principal.id_akun]
    skor = _skor_sesi(milik)
    return [{**t, **skor[t["sesi_id"]]} for t in milik if t["sesi_id"] in skor]


# --- tampilan --------------------------------------------------------------------------------------

def _baris_tampilan(tugas: dict, hari_ini: date) -> dict:
    return {"topik": pertemuan.label_topik(tugas["topik"]), "tenggat": tugas["tenggat"],
            "status_tenggat": aturan.status_tenggat(tugas["tenggat"], hari_ini),
            "selesai": bool(tugas["selesai"]), "benar": tugas["benar"], "total": tugas["total"]}


def _tugas_tampilan(principal, siswa_id: int, hari_ini: date) -> Optional[List[dict]]:
    """None bila daftar tak terbaca; galat baca dicatat tanpa id."""
    try:
        tugas = _tugas_guru_untuk_anak(principal, siswa_id)
    except GALAT_BACA_TUGAS as galat:
        _log.warning("tugas guru tidak terbaca: %s", type(galat).__name__)
        return None
    return [_baris_tampilan(t, hari_ini) for t in tugas][:MAKS_TUGAS_TAMPIL]


def _tingkat_anak(siswa_id: int) -> Optional[str]:
    """Tingkat anak dari latihan.db (ro). None bila anak tak ada; galat baca melempar ke pemanggil."""
    with jadwal_http._buka_belajar_baca() as kon:
        baris = kon.execute("SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
    return baris[0] if baris else None


def _tingkat_aman(siswa_id: int) -> Optional[str]:
    try:
        return _tingkat_anak(siswa_id)
    except GALAT_BACA_TUGAS as galat:
        _log.warning("tingkat anak tidak terbaca: %s", type(galat).__name__)
        return None


def _topik_untuk_tingkat(id_topik: str, tingkat: Optional[str]) -> bool:
    """Topik hanya boleh ditugaskan bila paketnya punya soal untuk tingkat anak (sama dengan palang buat_lembar)."""
    if tingkat is None:
        return False
    try:
        return tingkat in topics.ambil(id_topik).komposisi
    except (KeyError, ValueError):
        return False


def _opsi_topik(tingkat: Optional[str]) -> Optional[list]:
    """Pilihan topik untuk form. None bila tingkat tak terbaca atau env materi tak sah: halaman tanpa form."""
    if tingkat is None:
        return None
    try:
        return [(id_topik, label) for id_topik, label in aturan.daftar_topik_tugas()
                if _topik_untuk_tingkat(id_topik, tingkat)]
    except ValueError:
        _log.warning("daftar topik tugas tidak terbaca")
        return None


def _tampilan_anak(principal, penangan, order_id: str, tertaut: dict, kini: str) -> dict:
    hari_ini = hari_ini_wib(kini)
    opsi = _opsi_topik(_tingkat_aman(tertaut["siswa_id"]))
    bisa_isi = bool(opsi)
    return {
        "nama": _nama_anak(tertaut["akun_id"]),
        "order_id": order_id,
        "opsi_topik": opsi,
        "hari_ini": hari_ini.isoformat(),
        "tenggat_maks": (hari_ini + timedelta(days=aturan.TENGGAT_MAKS_HARI)).isoformat(),
        "token": _buat_token(principal, penangan, order_id) if bisa_isi else None,
        "tugas": _tugas_tampilan(principal, tertaut["siswa_id"], hari_ini),
    }


def _kirim_daftar(penangan, principal, kini: str) -> None:
    penangan._kirim_privat(halaman.halaman_daftar(jadwal_http._ident(principal), _daftar_anak(principal, kini)))


def _kirim_anak(penangan, principal, order_id: str, tertaut: dict, kini: str) -> None:
    tampilan = _tampilan_anak(principal, penangan, order_id, tertaut, kini)
    penangan._kirim_privat(halaman.halaman_anak(jadwal_http._ident(principal), tampilan))


# --- POST: urutan tiap langkah gagal = berhenti tanpa tulis --------------------------------------

def _isian_sah(penangan, data: dict, tingkat: Optional[str], kini: str) -> Optional[tuple]:
    """(topik, tenggat) bila isian sah; None bila sudah dibalas 400 atau 503."""
    topik = data.get(KUNCI_TOPIK)
    try:
        sah = aturan.topik_tugas_sah(topik) and _topik_untuk_tingkat(topik, tingkat)
    except ValueError:
        _log.warning("daftar topik tugas tidak terbaca saat kirim")
        _kirim_tolak(penangan, 503, JUDUL_TOLAK, TEKS_GALAT_SIMPAN)
        return None
    if not sah:
        _kirim_tolak(penangan, 400, JUDUL_TOLAK, TEKS_TOPIK_TIDAK_SAH)
        return None
    try:
        tenggat = aturan.baca_tenggat(data.get(KUNCI_TENGGAT), hari_ini_wib(kini))
    except ValueError as galat:
        _kirim_tolak(penangan, 400, JUDUL_TOLAK, str(galat))
        return None
    return topik, tenggat


def _detik_sejak(dibuat: str, kini: str) -> float:
    selisih = datetime.strptime(kini, pertemuan.FORMAT_WAKTU) - datetime.strptime(dibuat, pertemuan.FORMAT_WAKTU)
    return selisih.total_seconds()


def _duplikat(tugas: List[dict], topik: str, tenggat: Optional[str], kini: str) -> bool:
    """Tugas guru+anak+topik+tenggat yang sama dibuat kurang dari JENDELA_DUPLIKAT_DETIK yang lalu."""
    return any(
        t["topik"] == topik and t["tenggat"] == tenggat
        and 0 <= _detik_sejak(t["dibuat"], kini) < aturan.JENDELA_DUPLIKAT_DETIK
        for t in tugas
    )


def _aktif_belum_selesai(tugas: List[dict], skor: Dict[int, dict]) -> int:
    return sum(1 for t in tugas if t["sesi_id"] in skor and not skor[t["sesi_id"]]["selesai"])


def _cek_batas_dan_duplikat(penangan, principal, siswa_id: int, topik: str, tenggat, kini: str) -> bool:
    """True bila boleh dibuat. Batas dan duplikat dihitung dari tugas guru ini untuk anak ini saja."""
    try:
        milik = [t for t in dasar.daftar_siswa(siswa_id) if t["guru_akun"] == principal.id_akun]
        skor = _skor_sesi(milik)
    except GALAT_BACA_TUGAS as galat:
        _log.warning("tugas guru tidak terbaca saat cek batas: %s", type(galat).__name__)
        _kirim_tolak(penangan, 503, JUDUL_TOLAK, TEKS_GALAT_BACA)
        return False
    if _aktif_belum_selesai(milik, skor) >= aturan.BATAS_TUGAS_AKTIF:
        _kirim_tolak(penangan, 409, JUDUL_TOLAK, TEKS_BATAS)
        return False
    if _duplikat(milik, topik, tenggat, kini):
        _kirim_tolak(penangan, 409, JUDUL_TOLAK, TEKS_DUPLIKAT)
        return False
    return True


def _buat_sesi_dan_catat(siswa_id: int, guru_akun: str, topik: str, tenggat, kini: str) -> bool:
    """Sesi latihan biasa dan baris tugas. False bila catat gagal, dan sesinya DIBATALKAN, tidak dihapus.

    `buat_sesi` sudah commit lewat RELEASE SAVEPOINT di dalamnya, jadi rollback `database.buka()` tidak bisa
    membatalkan sesi. Pembatalan lewat `database.batalkan_sesi` (fungsi yang sudah ada, mencatat kejadian) dilakukan
    di dalam blok yang lalu commit normal: jangan naikkan pengecualian di dalam blok, karena rollback akan
    membatalkan pembatalan itu.
    """
    with database.buka() as kon:
        sesi_id = teacher_pages.buat_sesi_seed_baru(kon, siswa_id, topik=topik)
        try:
            dasar.catat(sesi_id, siswa_id, guru_akun, topik, tenggat, kini)
        except GALAT_CATAT:
            database.batalkan_sesi(kon, sesi_id, ALASAN_BATAL_CATAT)
            return False
    return True


def _catat_isian(penangan, principal, order_id: str, siswa_id: int, tingkat: Optional[str],
                 data: dict, kini: str) -> None:
    isian = _isian_sah(penangan, data, tingkat, kini)
    if isian is None:
        return
    topik, tenggat = isian
    if not _cek_batas_dan_duplikat(penangan, principal, siswa_id, topik, tenggat, kini):
        return
    try:
        berhasil = _buat_sesi_dan_catat(siswa_id, principal.id_akun, topik, tenggat, kini)
    except GALAT_SIMPAN_BUAT as galat:
        _log.error("tugas guru gagal dibuat: %s", type(galat).__name__)
        berhasil = False
    if not berhasil:
        _kirim_tolak(penangan, 500, JUDUL_TOLAK, TEKS_GALAT_SIMPAN)
        return
    lembaga_http._alihkan(penangan, f"{RUTE_TUGAS}/{order_id}")


def _proses_post(penangan, principal, order_id: str, kini: str) -> None:
    try:
        _batasi_laju(penangan, principal.pengguna)
    except GalatForm as galat:
        _kirim_galat_laju(penangan, galat)
        return
    data = kontak_http._baca_form(penangan)
    if data is None:
        penangan._tolak_isian()
        return
    tertaut = _tertaut(principal, order_id, kini)
    if tertaut is None:
        lembaga_http._tidak_ada(penangan)
        return
    if not _token_sah(principal, penangan, order_id, data.get(KUNCI_TOKEN)):
        penangan._tolak_isian(403)
        return
    try:
        tingkat = _tingkat_anak(tertaut["siswa_id"])
    except GALAT_BACA_TUGAS as galat:
        _log.warning("tingkat anak tidak terbaca saat kirim: %s", type(galat).__name__)
        _kirim_tolak(penangan, 503, JUDUL_TOLAK, TEKS_GALAT_BACA)
        return
    _catat_isian(penangan, principal, order_id, tertaut["siswa_id"], tingkat, data, kini)


# --- dispatcher ----------------------------------------------------------------------------------

def tangani_get(penangan, jalur: str) -> bool:
    """GET `/guru/tugas` dan `/guru/tugas/<order_id>`. False untuk jalur di luar rute tugas."""
    if not _rute_tugas(jalur):
        return False
    principal = jadwal_http._principal_guru(penangan)
    if not aturan.guru_tugas_aktif() or principal is None:
        lembaga_http._tidak_ada(penangan)
        return True
    kini = jadwal_http._kini()
    if jalur == RUTE_TUGAS:
        _kirim_daftar(penangan, principal, kini)
        return True
    order_id = _order_dari_jalur(jalur)
    tertaut = _tertaut(principal, order_id, kini) if order_id else None
    if tertaut is None:
        lembaga_http._tidak_ada(penangan)
        return True
    _kirim_anak(penangan, principal, order_id, tertaut, kini)
    return True


def tangani_post(penangan, jalur: str) -> bool:
    """POST `/guru/tugas/<order_id>`. Dipanggil setelah palang sandi dan guard asal dispatcher."""
    if not _rute_tugas(jalur):
        return False
    principal = jadwal_http._principal_guru(penangan)
    order_id = _order_dari_jalur(jalur)
    if not aturan.guru_tugas_aktif() or principal is None or order_id is None:
        lembaga_http._tidak_ada(penangan)
        return True
    _proses_post(penangan, principal, order_id, jadwal_http._kini())
    return True

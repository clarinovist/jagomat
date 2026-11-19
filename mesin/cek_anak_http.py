"""Rute anak `/mulai/{token}` khusus sesi Cek Kemampuan gratis.

Dipanggil ``share_http`` hanya bila sakelar funnel hidup DAN sesi token ada di
``cek_gratis``; selain itu jalur lama tetap persis seperti sebelumnya. Token
sudah divalidasi ``share_links.ambil`` oleh pemanggil.

Satu soal per layar (``?soal=N``), jeda regang (``?jeda=N``), peta soal
(``?peta=1``), layar keluar (``?keluar=1``); aksi lewat POST dengan PRG (303).
Validasi server otoritatif: nomor soal, opsi milik butir itu, dan revisi
pekerjaan. Tidak ada kunci/skor yang dibaca di sini; satu-satunya modul yang
menyentuh penilaian adalah helper finalisasi bersama dengan jalur lama.
"""
from __future__ import annotations

import re
import urllib.parse

import database
from cek_anak_komponen import NILAI_DI_HP_INI, JEDA_SETELAH, Konteks, url
from cek_anak_pages import (
    PESAN_BELUM_PILIH, layar_hore, layar_jeda, layar_keluar, layar_pesan, layar_peta,
    layar_sapaan, layar_soal, lokasi_berikut, sudah_dijawab,
)
from share_finalisasi import catat_kiriman_tautan, finalkan_kiriman_tautan
from support_pages import halaman_pesan as _halaman

KUNCI_LAYAR = ("soal", "jeda", "peta", "keluar")
BATAS_FIELD_QUERY = 16
POLA_ANGKA = re.compile(r"[0-9]{1,3}")
AKSI_SAH = ("mulai", "simpan", "keluar", "kumpul")
FIELD_BOLEH = {
    "mulai": frozenset({"aksi"}),
    "simpan": frozenset({"aksi", "soal", "revisi_pekerjaan", "dari"}),
    "keluar": frozenset({"aksi", "soal", "revisi_pekerjaan", "dari"}),
    "kumpul": frozenset({"aksi", "revisi_pekerjaan"}),
}
GALAT_ISIAN = "Isian tidak bisa diproses. Muat ulang halaman, lalu coba lagi."
GALAT_USANG = "Jawabanmu berubah di halaman lain. Muat ulang halaman, lalu lanjutkan."
STATUS_USANG = 409


def adalah_sesi_cek(kon, sesi_id: int) -> bool:
    """Sesi ini dibuat jalur cek gratis (baris `cek_gratis`)."""
    return kon.execute(
        "SELECT 1 FROM cek_gratis WHERE sesi_id = ?", (sesi_id,)
    ).fetchone() is not None


def _tidak_ada(penangan) -> bool:
    penangan._kirim_tautan(_halaman("404", "<h1>Halaman tidak ada</h1>"), 404)
    return True


def _alihkan(penangan, lokasi: str) -> bool:
    penangan.send_response(303)
    penangan.send_header("Location", lokasi)
    penangan.send_header("Content-Length", "0")
    penangan.send_header("Cache-Control", "no-store")
    penangan.send_header("X-Robots-Tag", "noindex, nofollow")
    penangan.end_headers()
    return True


def _baca_query(jalur_mentah: str):
    """Query GET sebagai dict nilai tunggal; ``None`` bila kunci dikenal ganda/terlalu banyak."""
    try:
        pasangan = urllib.parse.parse_qs(
            urllib.parse.urlparse(jalur_mentah).query,
            keep_blank_values=True, max_num_fields=BATAS_FIELD_QUERY,
        )
    except ValueError:
        return None
    if any(len(nilai) != 1 for nilai in pasangan.values()):
        return None
    return {nama: nilai[0] for nama, nilai in pasangan.items()}


def _angka(teks, maks: int):
    """Bilangan 1..maks dari teks ketat, selain itu ``None``."""
    if not isinstance(teks, str) or not POLA_ANGKA.fullmatch(teks):
        return None
    nilai = int(teks)
    return nilai if 1 <= nilai <= maks else None


def _muat(kon, akses):
    """(info, daftar soal murid tanpa kunci); ``None`` bila sesi tak terbaca."""
    import students

    siswa_id, sesi_id = int(akses["siswa_id"]), int(akses["sesi_id"])
    info = students.sesi_murid(kon, siswa_id, sesi_id)
    daftar = students.soal_murid(kon, sesi_id, siswa_id)
    if not info or not daftar:
        return None
    return info, daftar


def _tujuan_lanjut(k: Konteks, daftar: list) -> str:
    """Titik lanjut: soal kosong pertama, atau peta bila semua terisi."""
    for entri in daftar:
        if not sudah_dijawab(entri):
            return url(k, soal=entri["nomor"])
    return url(k, peta=1)


def tangani_get(penangan, kon, token: str, akses) -> bool:
    """Layar anak sesuai query; GET murni (tidak menulis)."""
    q = _baca_query(penangan.path)
    if q is None or sum(1 for nama in KUNCI_LAYAR if nama in q) > 1:
        return _tidak_ada(penangan)
    k = Konteks(token, q.get("di") == NILAI_DI_HP_INI)
    muat = _muat(kon, akses)
    if muat is None:
        return _tidak_ada(penangan)
    info, daftar = muat
    jumlah = len(daftar)
    if "soal" in q:
        return _get_soal(penangan, kon, k, akses, q, info, daftar)
    if "jeda" in q:
        return _get_jeda(penangan, k, q["jeda"], daftar)
    if "peta" in q:
        revisi = _revisi(kon, akses)
        penangan._kirim_tautan(layar_peta(k, info["nama"], daftar, revisi, kabar=q.get("ok", "")))
        return True
    if "keluar" in q:
        penangan._kirim_tautan(layar_keluar(k))
        return True
    if not any(sudah_dijawab(e) for e in daftar):
        penangan._kirim_tautan(layar_sapaan(k, info["nama"], jumlah))
        return True
    return _alihkan(penangan, _tujuan_lanjut(k, daftar))


def _revisi(kon, akses) -> int:
    import student_submissions as kiriman

    return kiriman.revisi(kon, int(akses["sesi_id"]))


def _get_soal(penangan, kon, k, akses, q, info, daftar) -> bool:
    nomor = _angka(q["soal"], len(daftar))
    if nomor is None:
        return _tidak_ada(penangan)
    penangan._kirim_tautan(layar_soal(
        k, info["nama"], daftar, nomor, _revisi(kon, akses),
        dari_peta=q.get("dari") == "peta", kabar=q.get("ok", ""),
    ))
    return True


def _get_jeda(penangan, k, nilai, daftar) -> bool:
    """Jeda hanya setelah soal 5/10 dan hanya selama belum ada soal sesudahnya terjawab."""
    nomor = _angka(nilai, len(daftar))
    if nomor is None or nomor not in JEDA_SETELAH or nomor >= len(daftar):
        return _tidak_ada(penangan)
    if any(sudah_dijawab(e) for e in daftar if e["nomor"] > nomor):
        return _alihkan(penangan, url(k, soal=nomor + 1))
    penangan._kirim_tautan(layar_jeda(k, nomor, len(daftar)))
    return True


def _tolak(penangan, kon, k, kode: int, teks: str, tujuan: str) -> bool:
    kon.rollback()
    penangan._kirim_tautan(
        layar_pesan("Belum tersimpan", teks, "Buka kembali", tujuan), kode
    )
    return True


def tangani_post(penangan, kon, token: str, akses, data: dict) -> bool:
    """Aksi anak; pemanggil sudah membuka transaksi (BEGIN IMMEDIATE) dan memvalidasi token."""
    q = _baca_query(penangan.path)
    k = Konteks(token, bool(q) and q.get("di") == NILAI_DI_HP_INI)
    aksi = data.get("aksi")
    if q is None or aksi not in AKSI_SAH:
        return _tolak(penangan, kon, k, 400, GALAT_ISIAN, url(k))
    asing = [n for n in data if n not in FIELD_BOLEH[aksi] and not n.startswith("opsi_")]
    punya_opsi = [n for n in data if n.startswith("opsi_")]
    if asing or (punya_opsi and aksi not in ("simpan", "keluar")):
        return _tolak(penangan, kon, k, 400, GALAT_ISIAN, url(k))
    muat = _muat(kon, akses)
    if muat is None:
        kon.rollback()
        return _tidak_ada(penangan)
    info, daftar = muat
    if aksi == "mulai":
        return _post_mulai(penangan, kon, k, akses)
    if aksi == "kumpul":
        return _post_kumpul(penangan, kon, k, akses, data, info, daftar)
    return _post_simpan(penangan, kon, k, akses, data, info, daftar, aksi, punya_opsi)


def _post_mulai(penangan, kon, k, akses) -> bool:
    database.tandai_mulai(kon, int(akses["sesi_id"]))
    kon.commit()
    return _alihkan(penangan, url(k, soal=1))


def _pilihan_sah(entri: dict, nama_opsi: list, data: dict):
    """Nilai opsi (id) milik butir ini, ``None`` bila tak ada, ``False`` bila tidak sah."""
    if not nama_opsi:
        return None
    if len(nama_opsi) != 1 or nama_opsi[0] != f"opsi_{entri['sesi_soal_id']}":
        return False
    nilai = data[nama_opsi[0]]
    if nilai not in {o.id for o in entri["pilihan"].opsi}:
        return False
    return nilai


def _post_simpan(penangan, kon, k, akses, data, info, daftar, aksi, nama_opsi) -> bool:
    import student_submissions as kiriman
    import students

    siswa_id, sesi_id = int(akses["siswa_id"]), int(akses["sesi_id"])
    nomor = _angka(data.get("soal"), len(daftar))
    dari = data.get("dari", "")
    if nomor is None or dari not in ("", "peta"):
        return _tolak(penangan, kon, k, 400, GALAT_ISIAN, url(k))
    entri = daftar[nomor - 1]
    nilai = _pilihan_sah(entri, nama_opsi, data)
    balik = url(k, soal=nomor, dari=dari or None)
    if nilai is False:
        return _tolak(penangan, kon, k, 400, GALAT_ISIAN, balik)
    try:
        kiriman.validasi_versi(kon, sesi_id, data)
        if nilai is not None:
            students.simpan_jawaban_murid(kon, siswa_id, sesi_id, {
                nama_opsi[0]: nilai, "revisi_pekerjaan": data["revisi_pekerjaan"],
            })
    except ValueError as galat:
        status = getattr(galat, "status", 400)
        teks = GALAT_USANG if status == STATUS_USANG else GALAT_ISIAN
        return _tolak(penangan, kon, k, status, teks, balik)
    if nilai is not None:
        database.tandai_mulai(kon, sesi_id)
    kon.commit()
    if nilai is not None:
        import sensor_http
        sensor_http.sesi(sesi_id, "pekerjaan_disimpan")
    if aksi == "keluar":
        return _alihkan(penangan, url(k, keluar=1))
    if nilai is None:
        penangan._kirim_tautan(layar_soal(
            k, info["nama"], daftar, nomor, kiriman.revisi(kon, sesi_id),
            dari_peta=dari == "peta", galat=PESAN_BELUM_PILIH,
        ))
        return True
    return _alihkan(penangan, lokasi_berikut(k, nomor, len(daftar), dari == "peta", "simpan"))


def _post_kumpul(penangan, kon, k, akses, data, info, daftar) -> bool:
    import student_submissions as kiriman

    sesi_id = int(akses["sesi_id"])
    try:
        kiriman.validasi_versi(kon, sesi_id, data)
    except ValueError as galat:
        status = getattr(galat, "status", 400)
        teks = GALAT_USANG if status == STATUS_USANG else GALAT_ISIAN
        return _tolak(penangan, kon, k, status, teks, url(k, peta=1))
    dijawab = sum(1 for e in daftar if sudah_dijawab(e))
    kiriman_baru = finalkan_kiriman_tautan(kon, sesi_id)
    kon.commit()
    catat_kiriman_tautan(sesi_id, kiriman_baru)
    penangan._kirim_tautan(layar_hore(k, info["nama"], dijawab, len(daftar)))
    return True

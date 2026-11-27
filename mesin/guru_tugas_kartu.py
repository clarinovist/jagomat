"""Kartu "Tugas dari Guru" di beranda anak (`/murid`): daftar tugas dari guru, tanpa skor, nama, atau akun guru.

Gerbang `guru_tugas_aturan.guru_tugas_aktif()`. Gerbang mati, tanpa tugas yang tampil, atau galat baca -> "" (beranda
tidak berubah). Tugas dibaca hanya untuk `siswa_id` dari sesi murid. Dari `guru_tugas_baca.skor_ringkas` hanya
kunci sesi dan `selesai` yang dipakai; `benar` dan `total` tidak pernah dibaca di sini (palang murid). Tugas yang
sesinya tidak ada atau dibatalkan dibuang sebelum batas jumlah tampil, supaya tidak memakan jatah.
"""
from __future__ import annotations

import html
import logging
import sqlite3
from datetime import date
from typing import Dict, FrozenSet, List, Tuple

import format_tanggal
import guru_pertemuan_aturan as pertemuan
import guru_tugas_aturan as aturan
import guru_tugas_baca as baca
import guru_tugas_dasar as dasar

_log = logging.getLogger(__name__)

GALAT_BACA = (dasar.GalatTugas, sqlite3.Error, ValueError, OSError)
JUDUL = "Tugas dari Guru"
ID_JUDUL = "judul-tugas-guru"
TEKS_SELESAI = "Selesai"
TEKS_LEWAT = "Lewat tenggat"
TEKS_KERJAKAN = "Kerjakan"
JALUR_KERJAKAN = "/murid/kerjakan/{}"
BATAS_BELUM_SELESAI = 5
BATAS_SELESAI = 3
SEMBUNYI_KOSONG: FrozenSet[int] = frozenset()


def _selesai_per_sesi(kon, siswa_id: int, sesi_ids: List[int]) -> Dict[int, bool]:
    """Status kirim tiap sesi yang ada dan tidak dibatalkan. Sesi yang tidak ditemukan tidak masuk hasil."""
    hasil = baca.skor_ringkas(kon, [(sid, siswa_id) for sid in sesi_ids])
    return {sid: bool(nilai["selesai"]) for sid, nilai in hasil.items()}


def _proyeksi(tugas: List[dict], selesai: Dict[int, bool]) -> List[dict]:
    """Hanya field yang boleh tampil, dan hanya untuk tugas yang sesinya ditemukan (yatim dan dibatalkan dibuang)."""
    return [
        {"sesi_id": t["sesi_id"], "topik": t["topik"], "tenggat": t["tenggat"], "selesai": selesai[t["sesi_id"]]}
        for t in tugas if t["sesi_id"] in selesai
    ]


def _pilih(proyeksi: List[dict]) -> List[dict]:
    """Belum selesai dulu (terbaru dulu, paling banyak BATAS_BELUM_SELESAI), lalu selesai (paling banyak BATAS_SELESAI)."""
    belum = [t for t in proyeksi if not t["selesai"]][:BATAS_BELUM_SELESAI]
    sudah = [t for t in proyeksi if t["selesai"]][:BATAS_SELESAI]
    return belum + sudah


def _baris_tenggat(tenggat) -> str:
    if tenggat is None:
        return ""
    return f"<p>Tenggat {html.escape(format_tanggal.tanggal_dari_teks(tenggat))}</p>"


def _penanda_lewat(item: dict, hari_ini: date) -> str:
    """Hanya label (keputusan T4): sesi yang sudah lewat tenggat tetap bisa dikerjakan."""
    if item["selesai"]:
        return ""
    if aturan.status_tenggat(item["tenggat"], hari_ini) != aturan.TENGGAT_LEWAT:
        return ""
    return f"<p><b>{TEKS_LEWAT}</b></p>"


def _aksi(item: dict) -> str:
    if item["selesai"]:
        return f'<span class="st-badge selesai">{TEKS_SELESAI}</span>'
    jalur = JALUR_KERJAKAN.format(int(item["sesi_id"]))
    return f'<a class="murid-tombol-utama-st" href="{jalur}">{TEKS_KERJAKAN}</a>'


def _item_html(item: dict, hari_ini: date) -> str:
    judul = html.escape(pertemuan.label_topik(item["topik"]))
    isi = f"<p><b>{judul}</b></p>" + _baris_tenggat(item["tenggat"]) + _penanda_lewat(item, hari_ini)
    return f'<div class="tugas-guru-item">{isi}{_aksi(item)}</div>'


def _kartu_html(tampil: List[dict], hari_ini: date) -> str:
    isi = "".join(_item_html(t, hari_ini) for t in tampil)
    return (f'<section class="murid-latihan-lain-st" aria-labelledby="{ID_JUDUL}" style="margin-block-end: 1rem">'
            f'<div class="murid-kepala-bagian-st"><h2 id="{ID_JUDUL}">{JUDUL}</h2></div>'
            f'<div class="st-kartu">{isi}</div></section>')


def _sembunyi(tampil: List[dict]) -> FrozenSet[int]:
    """Sesi yang tampil di kartu dan BELUM selesai: disembunyikan dari daftar latihan biasa beranda.

    Sesi selesai tetap di daftar (menunggu diperiksa/riwayat punya tautan hasil). Sesi yang tidak tampil di
    kartu (lewat batas, yatim, dibatalkan) tidak disembunyikan, supaya tidak ada sesi yang hilang dari beranda.
    """
    return frozenset(t["sesi_id"] for t in tampil if not t["selesai"])


def _beranda_dari_db(kon, siswa_id: int, hari_ini: date) -> Tuple[str, FrozenSet[int]]:
    tugas = dasar.daftar_siswa(siswa_id)
    if not tugas:
        return "", SEMBUNYI_KOSONG
    selesai = _selesai_per_sesi(kon, siswa_id, [t["sesi_id"] for t in tugas])
    tampil = _pilih(_proyeksi(tugas, selesai))
    if not tampil:
        return "", SEMBUNYI_KOSONG
    return _kartu_html(tampil, hari_ini), _sembunyi(tampil)


def tugas_beranda_untuk(kon, siswa_id: int, hari_ini: date) -> Tuple[str, FrozenSet[int]]:
    """(HTML kartu "Tugas dari Guru", id sesi yang harus disembunyikan dari daftar latihan biasa).

    Gerbang mati, tidak ada tugas yang tampil, atau galat baca -> ("", kosong): beranda tidak berubah dan tidak
    ada sesi yang disembunyikan. `kon` adalah koneksi DB belajar (sqlite3.Row) milik rute `/murid`; `siswa_id`
    hanya dari sesi murid; `hari_ini` adalah tanggal WIB yang disuntik pemanggil.
    """
    if not aturan.guru_tugas_aktif():
        return "", SEMBUNYI_KOSONG
    try:
        return _beranda_dari_db(kon, siswa_id, hari_ini)
    except GALAT_BACA as galat:
        _log.warning("kartu tugas guru dilewati: %s", type(galat).__name__)
        return "", SEMBUNYI_KOSONG


def kartu_beranda_untuk(kon, siswa_id: int, hari_ini: date) -> str:
    """Hanya HTML kartu "Tugas dari Guru" (pembungkus `tugas_beranda_untuk` untuk pemanggil yang tidak butuh sembunyi)."""
    return tugas_beranda_untuk(kon, siswa_id, hari_ini)[0]

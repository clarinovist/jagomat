"""Sapuan retensi cek kemampuan gratis (dijadwalkan lewat cron `cek_retensi.py`).

Aturan (plan funnel Fase 2 §2.8):

- cek selesai lebih dari `RETENSI_SELESAI_HARI`: baris `sesi` miliknya dihapus
  (cascade jawaban/diagnosis), `sesi_id` menjadi NULL dan `bahan_dihapus_pada`
  terisi; turunan (skor, kategori, ringkasan) tetap;
- cek yang sesinya belum selesai lebih dari `RETENSI_BELUM_SELESAI_HARI` sejak
  `dibuat`: sesi dan baris cek dihapus;
- cek yang sesinya sudah selesai tetapi skornya tidak pernah dihitung dan sudah
  lebih dari `RETENSI_SELESAI_HARI` sejak sesi selesai: sesi dan baris dihapus
  (tidak ada turunan yang perlu dijaga; sapuan tidak boleh membaca jawaban);
- cek yatim (akun tidak lagi hidup, atau anaknya sudah tidak ada): baris dan
  sesinya dihapus.

Sesi yang punya bukti belajar (konfirmasi guru, kejadian, bukti fokus, pilot)
ditahan basis data (`ON DELETE RESTRICT`); sapuan tidak pernah memaksanya, hanya
menghitungnya sebagai `terlindungi`. Sapuan tidak menyentuh sesi biasa lain,
siswa, atau kontak, dan tidak membaca isi jawaban. Hasil hanya agregat jumlah.
"""
from __future__ import annotations

import sqlite3
from datetime import timedelta

from auth import id_akun_sah
from cek_gratis_skor import (
    FORMAT_WAKTU, RETENSI_BELUM_SELESAI_HARI, RETENSI_SELESAI_HARI, waktu_baku,
)

_SAVEPOINT_SAPU = "sapu_cek_gratis"
_SAVEPOINT_SESI = "sapu_cek_sesi"

_SQL_YATIM = """SELECT id, sesi_id, id_akun,
        EXISTS (SELECT 1 FROM siswa w WHERE w.id = cek_gratis.siswa_id) AS anak_ada
    FROM cek_gratis"""
_SQL_BELUM_SELESAI = """SELECT c.id, c.sesi_id
    FROM cek_gratis c LEFT JOIN sesi s ON s.id = c.sesi_id
    WHERE c.selesai_pada IS NULL AND c.dibuat < ?
      AND (s.id IS NULL OR s.selesai IS NULL OR s.dibatalkan IS NOT NULL)"""
_SQL_TAK_TERHITUNG = """SELECT c.id, c.sesi_id
    FROM cek_gratis c JOIN sesi s ON s.id = c.sesi_id
    WHERE c.selesai_pada IS NULL
      AND s.selesai IS NOT NULL AND s.dibatalkan IS NULL
      AND substr(s.selesai, 1, 10) < substr(?, 1, 10)"""
_SQL_BAHAN_KEDALUWARSA = """SELECT id, sesi_id FROM cek_gratis
    WHERE selesai_pada IS NOT NULL AND selesai_pada < ? AND sesi_id IS NOT NULL"""


def _periksa_akun_hidup(akun_hidup) -> None:
    """Guard: daftar akun gagal dibaca tidak boleh berubah menjadi 'semua yatim'."""
    if type(akun_hidup) not in (set, frozenset) or not akun_hidup:
        raise ValueError("daftar akun hidup harus himpunan tidak kosong")
    if not all(id_akun_sah(i) for i in akun_hidup):
        raise ValueError("daftar akun hidup memuat id_akun tidak sah")


def _periksa_fk_aktif(kon) -> None:
    """Tanpa FK aktif, RESTRICT bukti belajar tidak berlaku: gagal tertutup."""
    if kon.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ValueError("foreign key harus aktif untuk sapuan cek")


def _hapus_sesi(kon, sesi_id) -> bool:
    """Hapus satu sesi; False bila ditahan bukti belajar (sesi tetap utuh)."""
    kon.execute("SAVEPOINT " + _SAVEPOINT_SESI)
    try:
        kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))
    except sqlite3.IntegrityError:
        kon.execute("ROLLBACK TO " + _SAVEPOINT_SESI)
        kon.execute("RELEASE " + _SAVEPOINT_SESI)
        return False
    kon.execute("RELEASE " + _SAVEPOINT_SESI)
    return True


def _hapus_baris_dan_sesi(kon, baris) -> tuple:
    """Hapus baris cek beserta sesinya; (baris terhapus, sesi tertahan bukti)."""
    tertahan = 0
    for cek_id, sesi_id in baris:
        if sesi_id is not None and not _hapus_sesi(kon, sesi_id):
            tertahan += 1
        kon.execute("DELETE FROM cek_gratis WHERE id = ?", (cek_id,))
    return len(baris), tertahan


def _hapus_yatim(kon, akun_hidup) -> tuple:
    yatim = [(r["id"], r["sesi_id"]) for r in kon.execute(_SQL_YATIM).fetchall()
             if r["id_akun"] not in akun_hidup or not r["anak_ada"]]
    return _hapus_baris_dan_sesi(kon, yatim)


def _hapus_menurut(kon, sql, batas) -> tuple:
    return _hapus_baris_dan_sesi(kon, [tuple(r) for r in kon.execute(sql, (batas,)).fetchall()])


def _hapus_bahan(kon, batas: str, waktu: str) -> tuple:
    """Hapus sesi cek selesai kedaluwarsa; baris cek dan turunannya tetap."""
    dihapus = tertahan = 0
    for cek_id, sesi_id in [tuple(r) for r in kon.execute(_SQL_BAHAN_KEDALUWARSA, (batas,))]:
        if not _hapus_sesi(kon, sesi_id):
            tertahan += 1
            continue
        kon.execute(
            "UPDATE cek_gratis SET sesi_id = NULL, bahan_dihapus_pada = ? WHERE id = ?",
            (waktu, cek_id),
        )
        dihapus += 1
    return dihapus, tertahan


def _sapu(kon, akun_hidup, waktu) -> dict:
    batas_selesai = (waktu - timedelta(days=RETENSI_SELESAI_HARI)).strftime(FORMAT_WAKTU)
    batas_belum = (waktu - timedelta(days=RETENSI_BELUM_SELESAI_HARI)).strftime(FORMAT_WAKTU)
    yatim, tahan_1 = _hapus_yatim(kon, akun_hidup)
    belum, tahan_2 = _hapus_menurut(kon, _SQL_BELUM_SELESAI, batas_belum)
    tak_terhitung, tahan_3 = _hapus_menurut(kon, _SQL_TAK_TERHITUNG, batas_selesai)
    bahan, tahan_4 = _hapus_bahan(kon, batas_selesai, waktu.strftime(FORMAT_WAKTU))
    return {"bahan_dihapus": bahan, "belum_selesai": belum,
            "tak_terhitung": tak_terhitung, "yatim": yatim,
            "terlindungi": tahan_1 + tahan_2 + tahan_3 + tahan_4}


def sapu_cek_gratis(kon, sekarang, akun_hidup) -> dict:
    """Terapkan retensi cek gratis; hasil hanya agregat jumlah.

    `akun_hidup` wajib `set`/`frozenset` tidak kosong berisi id_akun sah; selain
    itu ValueError dan tidak ada yang dihapus. Koneksi wajib berFK aktif. Atomik
    lewat SAVEPOINT: gagal di tengah berarti rollback utuh (bila tanpa transaksi
    pemanggil, RELEASE menyimpan hasilnya). Cek yatim dihitung di `yatim` meski
    juga kedaluwarsa.
    """
    _periksa_akun_hidup(akun_hidup)
    _periksa_fk_aktif(kon)
    waktu = waktu_baku(sekarang)
    kon.execute("SAVEPOINT " + _SAVEPOINT_SAPU)
    try:
        hasil = _sapu(kon, akun_hidup, waktu)
    except Exception:
        kon.execute("ROLLBACK TO " + _SAVEPOINT_SAPU)
        kon.execute("RELEASE " + _SAVEPOINT_SAPU)
        raise
    kon.execute("RELEASE " + _SAVEPOINT_SAPU)
    return hasil

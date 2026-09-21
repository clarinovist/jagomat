"""Latihan manual serupa untuk materi yang baru dikenalkan.

Sumber hanya hasil final T pada sesi yang selesai dan masih selevel. Latihan
hasilnya sengaja berupa drill bebas: ia bukan remedial, bukan probe setelah
pengenalan, dan tidak membawa provenance siklus belajar.
"""
from __future__ import annotations

import random
import sqlite3
from typing import Any

import database
from generator import buat_soal
from topics import pemilik_template

JUMLAH_SOAL = 5
_BATAS_PERCOBAAN = 500


class LatihanSerupaTidakTersedia(ValueError):
    """Sumber tidak lagi sah atau tidak terikat ke sesi yang diminta."""


def kandidat_sesi(
    kon: sqlite3.Connection, sesi_id: int
) -> list[dict[str, Any]]:
    """Satu kandidat per template T final, beserta nomor soal sumbernya."""
    baris = kon.execute(
        """SELECT ss.id AS sesi_soal_id, ss.nomor, so.template_id
           FROM sesi se
           JOIN siswa sw ON sw.id = se.siswa_id
           JOIN sesi_soal ss ON ss.sesi_id = se.id
           JOIN soal so ON so.id = ss.soal_id
           JOIN jawaban j ON j.sesi_soal_id = ss.id
           JOIN diagnosis d ON d.jawaban_id = j.id
           WHERE se.id = ? AND se.format_jawaban='isian'
             AND se.selesai IS NOT NULL
             AND se.dibatalkan IS NULL
             AND se.level = sw.tingkat
             AND d.benar = 0
             AND d.kode_final = 'T'
           ORDER BY ss.nomor, ss.id""",
        (sesi_id,),
    ).fetchall()
    per_template: dict[str, dict[str, Any]] = {}
    for item in baris:
        template_id = str(item["template_id"])
        kandidat = per_template.setdefault(
            template_id,
            {
                "template_id": template_id,
                "sesi_soal_id": int(item["sesi_soal_id"]),
                "nomor": [],
            },
        )
        kandidat["nomor"].append(int(item["nomor"]))
    return list(per_template.values())


def _pilih_soal_baru(
    template_id: str,
    level: str,
    seed: int,
    tanda_tangan_terlarang: set[str],
):
    """Bangkitkan lima soal unik secara deterministik dari seed awal."""
    topik = pemilik_template(template_id)
    if topik is None:
        raise LatihanSerupaTidakTersedia("template sumber tidak tersedia")
    hasil = []
    tanda_tangan = set(tanda_tangan_terlarang)
    rng = random.Random(seed)
    for _ in range(_BATAS_PERCOBAAN):
        calon = buat_soal(
            template_id,
            rng.randint(0, 2_147_483_647),
            level=level,
            topik=topik,
        )
        if calon.tanda_tangan in tanda_tangan:
            continue
        hasil.append(calon)
        tanda_tangan.add(calon.tanda_tangan)
        if len(hasil) == JUMLAH_SOAL:
            return tuple(hasil), topik
    raise RuntimeError("variasi soal serupa belum cukup untuk membuat latihan")


def buat_dari_hasil_t(
    kon: sqlite3.Connection,
    sesi_id: int,
    sesi_soal_id: int,
    *,
    seed: int,
) -> int:
    """Validasi sumber di server lalu buat drill bebas lima soal secara atomik."""
    if kon.execute('SELECT 1 FROM pilot_sesi WHERE sesi_id=?',(sesi_id,)).fetchone():
        raise LatihanSerupaTidakTersedia('Lanjutkan tuntutan ini melalui rencana pilot.')
    sumber = kon.execute(
        """SELECT se.siswa_id, se.level, sw.tingkat AS level_aktif,
                  ss.id AS sesi_soal_id, so.template_id
           FROM sesi se
           JOIN siswa sw ON sw.id = se.siswa_id
           JOIN sesi_soal ss ON ss.sesi_id = se.id
           JOIN soal so ON so.id = ss.soal_id
           JOIN jawaban j ON j.sesi_soal_id = ss.id
           JOIN diagnosis d ON d.jawaban_id = j.id
           WHERE se.id = ? AND ss.id = ?
             AND se.selesai IS NOT NULL
             AND se.dibatalkan IS NULL
             AND se.level = sw.tingkat
             AND d.benar = 0
             AND d.kode_final = 'T'""",
        (sesi_id, sesi_soal_id),
    ).fetchone()
    if sumber is None:
        raise LatihanSerupaTidakTersedia("hasil sumber tidak tersedia")

    tanda_tangan_sumber = {
        str(baris["tanda_tangan"])
        for baris in kon.execute(
            """SELECT so.tanda_tangan FROM sesi_soal ss
               JOIN soal so ON so.id = ss.soal_id
               WHERE ss.sesi_id = ?""",
            (sesi_id,),
        ).fetchall()
    }
    soal, topik = _pilih_soal_baru(
        str(sumber["template_id"]),
        str(sumber["level"]),
        seed,
        tanda_tangan_sumber,
    )
    return database.buat_sesi_dari_urutan(
        kon,
        int(sumber["siswa_id"]),
        seed,
        urutan=(str(sumber["template_id"]),) * JUMLAH_SOAL,
        topik=topik,
        level=str(sumber["level"]),
        mode="drill",
        jenis="biasa",
        soal_terpilih=soal,
    )

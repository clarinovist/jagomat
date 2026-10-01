"""Query proyeksi laporan; transaksi tetap dimiliki pemanggil."""
from __future__ import annotations

import sqlite3


def ringkasan(
    kon: sqlite3.Connection, siswa_id: int | None = None,
) -> list[sqlite3.Row]:
    if siswa_id is None:
        return kon.execute(
            """SELECT r.* FROM ringkasan_sesi r
               JOIN sesi s ON s.id = r.sesi_id
               WHERE s.selesai IS NOT NULL
               ORDER BY r.tanggal DESC, r.sesi_id DESC"""
        ).fetchall()
    return kon.execute(
        """SELECT r.* FROM ringkasan_sesi r
           JOIN sesi s ON s.id = r.sesi_id
           WHERE r.siswa_id = ? AND s.selesai IS NOT NULL
           ORDER BY r.tanggal DESC, r.sesi_id DESC""",
        (siswa_id,),
    ).fetchall()


def miskonsepsi_berulang(
    kon: sqlite3.Connection, siswa_id: int, minimal: int = 1,
) -> list[sqlite3.Row]:
    """Miskonsepsi dihitung per malrule, bukan per nomor soal."""
    return kon.execute(
        """SELECT d.malrule_id,
                  s.template_id,
                  se.topik                   AS topik,
                  MAX(d.alasan)              AS alasan,
                  COUNT(*)                   AS kemunculan,
                  COUNT(DISTINCT se.id)      AS jumlah_sesi,
                  MIN(se.tanggal)            AS pertama,
                  MAX(se.tanggal)            AS terakhir
           FROM diagnosis d
           JOIN jawaban j    ON j.id  = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id  = ss.soal_id
           WHERE se.siswa_id = ? AND se.format_jawaban='isian'
             AND se.selesai IS NOT NULL
             AND d.kode_final = 'K'
             AND d.malrule_id IS NOT NULL
           GROUP BY d.malrule_id, s.template_id, se.topik
           HAVING COUNT(*) >= ?
           ORDER BY jumlah_sesi DESC, kemunculan DESC""",
        (siswa_id, minimal),
    ).fetchall()


def peta_materi_baru(
    kon: sqlite3.Connection, siswa_id: int,
) -> list[sqlite3.Row]:
    """Tipe soal berkode T adalah materi baru, bukan kegagalan."""
    return kon.execute(
        """SELECT s.template_id, se.topik AS topik,
                  COUNT(*) AS kali, MAX(se.tanggal) AS terakhir
           FROM diagnosis d
           JOIN jawaban j    ON j.id  = d.jawaban_id
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se      ON se.id = ss.sesi_id
           JOIN soal s       ON s.id  = ss.soal_id
           WHERE se.siswa_id = ? AND se.format_jawaban='isian' AND se.selesai IS NOT NULL
             AND d.kode_final = 'T'
           GROUP BY s.template_id, se.topik
           ORDER BY kali DESC""",
        (siswa_id,),
    ).fetchall()

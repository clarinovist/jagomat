"""Bank soal SQLite; transaksi tetap dimiliki pemanggil."""
from __future__ import annotations

import json
import sqlite3

from templates import Soal


def simpan_soal(kon: sqlite3.Connection, soal: Soal) -> int:
    """Masukkan soal secara idempoten lewat tanda tangan kanonis."""
    ada = kon.execute(
        "SELECT id FROM soal WHERE tanda_tangan = ?", (soal.tanda_tangan,)
    ).fetchone()
    if ada:
        return int(ada["id"])

    cur = kon.execute(
        """INSERT INTO soal (tanda_tangan, template_id, parameter, kunci,
                             bagian, tantangan, level)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            soal.tanda_tangan,
            soal.template_id,
            json.dumps(soal.parameter, ensure_ascii=False, sort_keys=True),
            soal.kunci,
            soal.bagian,
            int(soal.tantangan),
            soal.level,
        ),
    )
    soal_id = int(cur.lastrowid)
    for malrule in soal.malrule:
        kon.execute(
            """INSERT OR IGNORE INTO malrule
                   (soal_id, malrule_id, jawaban, kode, alasan)
               VALUES (?, ?, ?, ?, ?)""",
            (soal_id, malrule.id, malrule.jawaban, malrule.kode, malrule.alasan),
        )
    return soal_id


def statistik_bank(kon: sqlite3.Connection) -> list[sqlite3.Row]:
    return kon.execute(
        """SELECT template_id, COUNT(*) AS jumlah
           FROM soal GROUP BY template_id ORDER BY jumlah DESC"""
    ).fetchall()

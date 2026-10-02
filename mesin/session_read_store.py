"""Query dan mutasi metadata dasar sesi; transaksi dimiliki pemanggil."""
from __future__ import annotations

import sqlite3


def isi_sesi(
    kon: sqlite3.Connection, sesi_id: int,
) -> list[sqlite3.Row]:
    """Soal satu sesi beserta jawaban dan diagnosis, urut nomor."""
    return kon.execute(
        """SELECT ss.id AS sesi_soal_id, ss.nomor,
                  ss.teks_soal, ss.bagian_soal, ss.tantangan_soal,
                  ss.minta_restatement, ss.penyajian_json,
                  ss.penyajian_versi, ss.renderer_versi, ss.asal_teks,
                  ss.status_visual, ss.mode_representasi,
                  ss.fingerprint_matematis, ss.fingerprint_penyajian,
                  s.id AS soal_id, s.template_id, s.parameter, s.kunci,
                  s.bagian, s.tantangan, s.level, s.cerita,
                  j.id AS jawaban_id, j.restatement, j.cara, j.jawaban,
                  j.belum_pernah, j.detik,
                  d.benar, d.kode_usulan, d.kode_final, d.malrule_id,
                  d.alasan, d.manual, d.catatan
           FROM sesi_soal ss
           JOIN soal s        ON s.id = ss.soal_id
           LEFT JOIN jawaban j   ON j.sesi_soal_id = ss.id
           LEFT JOIN diagnosis d ON d.jawaban_id = j.id
           WHERE ss.sesi_id = ?
           ORDER BY ss.nomor""",
        (sesi_id,),
    ).fetchall()


def hapus_sesi(kon: sqlite3.Connection, sesi_id: int) -> bool:
    """Hard-delete sesi yang telah lolos guard domain di lapisan pemanggil."""
    cur = kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))
    return cur.rowcount > 0


def tandai_mulai(kon: sqlite3.Connection, sesi_id: int) -> None:
    """Catat waktu mulai sekali saja."""
    kon.execute(
        """UPDATE sesi SET mulai = datetime('now', '+7 hours')
           WHERE id = ? AND mulai IS NULL""",
        (sesi_id,),
    )


def tandai_selesai(kon: sqlite3.Connection, sesi_id: int) -> None:
    """Catat waktu selesai sekali saja."""
    kon.execute(
        """UPDATE sesi SET selesai = datetime('now', '+7 hours')
           WHERE id = ? AND selesai IS NULL""",
        (sesi_id,),
    )


def malrule_soal(
    kon: sqlite3.Connection, soal_id: int,
) -> list[sqlite3.Row]:
    return kon.execute(
        "SELECT malrule_id, jawaban, kode, alasan FROM malrule WHERE soal_id = ?",
        (soal_id,),
    ).fetchall()

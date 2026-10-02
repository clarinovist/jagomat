"""Penyimpanan jawaban, diagnosis, dan invalidasi konfirmasi aktif."""
from __future__ import annotations

import json
import sqlite3


def simpan_jawaban(
    kon: sqlite3.Connection,
    sesi_soal_id: int,
    jawaban: str = "",
    cara: str = "",
    restatement: str = "",
    belum_pernah: bool = False,
    detik: int | None = None,
    *,
    invalidasi,
) -> int:
    """Simpan/perbarui jawaban satu soal. Idempoten per sesi_soal."""
    kon.execute(
        """INSERT INTO jawaban (sesi_soal_id, restatement, cara, jawaban,
                                belum_pernah, detik)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(sesi_soal_id) DO UPDATE SET
               restatement  = excluded.restatement,
               cara         = excluded.cara,
               jawaban      = excluded.jawaban,
               belum_pernah = excluded.belum_pernah,
               detik        = excluded.detik""",
        (sesi_soal_id, restatement, cara, jawaban, int(belum_pernah), detik),
    )
    baris = kon.execute(
        "SELECT id FROM jawaban WHERE sesi_soal_id = ?", (sesi_soal_id,)
    ).fetchone()
    # Simpan_jawaban juga dapat mengubah outcome setelah konfirmasi. Jalur ini
    # memakai helper invalidasi yang sama dengan koreksi diagnosis.
    invalidasi(kon, int(baris["id"]))
    return int(baris["id"])


def simpan_diagnosis(
    kon: sqlite3.Connection,
    jawaban_id: int,
    benar: bool,
    kode_usulan: str | None,
    kode_final: str | None,
    malrule_id: str | None = None,
    alasan: str = "",
    manual: bool = False,
    catatan: str = "",
    *,
    invalidasi,
) -> int:
    kon.execute(
        """INSERT INTO diagnosis (jawaban_id, benar, kode_usulan, kode_final,
                                  malrule_id, alasan, manual, catatan)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(jawaban_id) DO UPDATE SET
               benar       = excluded.benar,
               kode_usulan = excluded.kode_usulan,
               kode_final  = excluded.kode_final,
               malrule_id  = excluded.malrule_id,
               alasan      = excluded.alasan,
               manual      = excluded.manual,
               catatan     = excluded.catatan""",
        (
            jawaban_id,
            int(benar),
            kode_usulan,
            kode_final,
            malrule_id,
            alasan,
            int(manual),
            catatan,
        ),
    )
    invalidasi(kon, jawaban_id)
    baris = kon.execute(
        "SELECT id FROM diagnosis WHERE jawaban_id = ?", (jawaban_id,)
    ).fetchone()
    return int(baris["id"])


def _invalidasi_konfirmasi_dari_jawaban(
    kon: sqlite3.Connection, jawaban_id: int
) -> None:
    """Batalkan cache bukti aktif setelah diagnosis ditulis ulang.

    Snapshot lama tetap immutable. Event hanya lahir bila sesi sebelumnya
    memang punya konfirmasi aktif, sehingga penulisan diagnosis awal tidak
    menciptakan invalidasi palsu.
    """
    sesi = kon.execute(
        """SELECT se.id, se.siswa_id, se.putaran_id, se.dikonfirmasi_guru,
                  kh.id AS konfirmasi_id
           FROM jawaban j
           JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
           JOIN sesi se ON se.id = ss.sesi_id
           LEFT JOIN konfirmasi_hasil kh
             ON kh.id = (
                 SELECT aktif.id
                 FROM konfirmasi_hasil aktif
                 WHERE aktif.sesi_id = se.id
                   AND aktif.fingerprint = se.fingerprint_konfirmasi
                 ORDER BY aktif.nomor_urut DESC, aktif.id DESC
                 LIMIT 1
             )
           WHERE j.id = ?""",
        (jawaban_id,),
    ).fetchone()
    if sesi is None or sesi["dikonfirmasi_guru"] is None:
        return
    kon.execute(
        """INSERT INTO kejadian_belajar
               (siswa_id, putaran_id, sesi_id, konfirmasi_id, jenis, data)
           VALUES (?, ?, ?, ?, 'konfirmasi_dibatalkan', ?)""",
        (
            sesi["siswa_id"],
            sesi["putaran_id"],
            sesi["id"],
            sesi["konfirmasi_id"],
            json.dumps({"alasan": "diagnosis_diubah"}, sort_keys=True),
        ),
    )
    kon.execute(
        """UPDATE sesi
           SET dikonfirmasi_guru = NULL, fingerprint_konfirmasi = NULL
           WHERE id = ?""",
        (sesi["id"],),
    )

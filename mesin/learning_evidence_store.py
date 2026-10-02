"""Snapshot konfirmasi append-only dan loader bukti siklus belajar."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from typing import Optional

import outcome_presentations


def _target_per_butir(
    kon: sqlite3.Connection, sesi_id: int
) -> dict[int, tuple[str, str, Optional[str]]]:
    event = kon.execute(
        """SELECT data FROM kejadian_belajar
           WHERE sesi_id = ? AND jenis = 'sesi_dibuat'
           ORDER BY id DESC LIMIT 1""",
        (sesi_id,),
    ).fetchone()
    if event is None:
        return {}
    data = json.loads(event["data"] or "{}")
    target = data.get("target_per_nomor", {}) if isinstance(data, dict) else {}
    hasil = {}
    for nomor, mentah in target.items():
        if not isinstance(mentah, list) or len(mentah) != 3:
            continue
        hasil[int(nomor)] = (mentah[0], mentah[1], mentah[2])
    return hasil


def konfirmasi_hasil(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    dilewati: set[int] | None = None,
    cek_pemahaman: dict[int, str] | None = None,
    *,
    outcome_presentations_module,
    konfirmasi_impl,
) -> int:
    """Sahkan snapshot dan provenance atomik, tanpa meng-commit pemanggil."""
    with outcome_presentations_module.transaksi(kon):
        return konfirmasi_impl(kon, sesi_id, guru, dilewati, cek_pemahaman)


def _konfirmasi_hasil(
    kon: sqlite3.Connection,
    sesi_id: int,
    guru: str,
    dilewati: set[int] | None,
    cek_pemahaman: dict[int, str] | None,
    *,
    muat_outcome,
    target_per_butir,
) -> int:
    """Sahkan outcome lengkap menjadi snapshot immutable dan event audit."""
    dilewati = dilewati or set()
    cek_pemahaman = cek_pemahaman or {}
    sesi = kon.execute("SELECT * FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    if sesi is None:
        raise ValueError("sesi tidak dikenal")
    if sesi["dibatalkan"] is not None:
        raise ValueError("sesi dibatalkan")
    if sesi["selesai"] is None:
        raise ValueError("sesi belum selesai")

    outcome = muat_outcome(kon, sesi_id)
    jumlah_butir = kon.execute(
        "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?", (sesi_id,)
    ).fetchone()[0]
    if len(outcome) != jumlah_butir:
        raise ValueError("hubungan snapshot penyajian sesi tidak lengkap")
    if not outcome:
        raise ValueError("sesi tidak memiliki butir")
    id_butir = {int(b["sesi_soal_id"]) for b in outcome}
    if not dilewati <= id_butir or not set(cek_pemahaman) <= id_butir:
        raise ValueError("referensi butir tidak dikenal")
    pemahaman_sah = {"bisa_menjelaskan", "ragu", "menghafal"}
    if any(nilai not in pemahaman_sah for nilai in cek_pemahaman.values()):
        raise ValueError("cek pemahaman tidak dikenal")
    for butir in outcome:
        butir_id = int(butir["sesi_soal_id"])
        if butir_id in dilewati:
            continue
        if butir["jawaban_id"] is None or butir["benar"] is None:
            raise ValueError("outcome belum lengkap")
        if not bool(butir["benar"]) and butir["kode_final"] is None:
            raise ValueError("outcome belum lengkap")
        if bool(butir["benar"]) and (
            butir["kode_final"] is not None or butir["malrule_id"] is not None
        ):
            raise ValueError("outcome belum lengkap")

    if sesi['format_jawaban'] == 'pilihan_ganda':
        from choice_store import validasi_arsip
        validasi_arsip(kon, sesi_id)
    import review_store
    tinjauan = review_store.validasi_bukti(kon, sesi_id, outcome, dilewati)
    target_fokus_butir = target_per_butir(kon, sesi_id)
    import context_store
    konteks = context_store.proyeksi(kon, sesi_id, target_fokus_butir)
    kanonis = []
    for butir in outcome:
        butir_id = int(butir["sesi_soal_id"])
        lewat = butir_id in dilewati
        target_fokus = target_fokus_butir.get(int(butir["nomor"]))
        kanonis.append(
            {
                "nomor": int(butir["nomor"]),
                "template_id": butir["template_id"],
                "jawaban": "" if lewat else (butir["jawaban"] or ""),
                "benar": None if lewat else int(butir["benar"]),
                "kode_final": None if lewat else butir["kode_final"],
                "malrule_id": None if lewat else butir["malrule_id"],
                "dilewati": int(lewat),
                "level_efektif": sesi["level"],
                "cek_pemahaman": cek_pemahaman.get(butir_id),
                "target_template_id": None if target_fokus is None else target_fokus[0],
                "target_kode_intervensi": None if target_fokus is None else target_fokus[1],
                "target_malrule_id": None if target_fokus is None else target_fokus[2],
            }
        )
    isi_fingerprint = {"outcome": kanonis, "tinjauan": tinjauan} if tinjauan else kanonis
    if sesi['format_jawaban'] == 'pilihan_ganda':
        from choice_store import proyeksi_konfirmasi
        isi_fingerprint = {'hasil': isi_fingerprint, 'pilihan': proyeksi_konfirmasi(kon, sesi_id)}
    # Konteks v1 homogen diproyeksikan oleh template_id, level_efektif, nomor,
    # dan target_* yang sudah ada dalam fingerprint. Arsip baru mengikat
    # konfirmasi_id yang sama; jangan mengubah identitas retry historis.
    from skill_pilot_store import baca_kontrak, bungkus_konfirmasi
    kontrak_pilot = baca_kontrak(kon, sesi_id, sesi['siswa_id'])
    isi_fingerprint = bungkus_konfirmasi(isi_fingerprint, kontrak_pilot)
    serial = json.dumps(isi_fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serial.encode("utf-8")).hexdigest()
    aktif = kon.execute(
        """SELECT kh.id
           FROM konfirmasi_hasil kh
           JOIN sesi se ON se.id = kh.sesi_id
           WHERE kh.sesi_id = ?
             AND kh.fingerprint = ?
             AND se.dikonfirmasi_guru IS NOT NULL
             AND se.fingerprint_konfirmasi = kh.fingerprint
           ORDER BY kh.nomor_urut DESC, kh.id DESC
           LIMIT 1""",
        (sesi_id, fingerprint),
    ).fetchone()
    if aktif is not None:
        context_store.validasi_arsip(kon, sesi_id, int(aktif['id']), target_fokus_butir)
        if sesi['format_jawaban'] == 'pilihan_ganda':
            validasi_arsip(kon, sesi_id, int(aktif['id']))
        outcome_presentations.lengkapi(kon, int(aktif["id"]))
        from skill_pilot_store import validasi_konfirmasi
        validasi_konfirmasi(kon, sesi_id, sesi['siswa_id'], int(aktif['id']))
        return int(aktif["id"])
    nomor_urut = int(
        kon.execute(
            """SELECT COALESCE(MAX(nomor_urut), 0) + 1
               FROM konfirmasi_hasil WHERE sesi_id = ?""",
            (sesi_id,),
        ).fetchone()[0]
    )
    cur = kon.execute(
        """INSERT INTO konfirmasi_hasil
               (sesi_id, nomor_urut, guru, fingerprint)
           VALUES (?, ?, ?, ?)""",
        (sesi_id, nomor_urut, guru, fingerprint),
    )
    konfirmasi_id = int(cur.lastrowid)
    context_store.arsipkan(kon, konfirmasi_id, konteks)
    if tinjauan:
        kon.execute("INSERT INTO tinjauan_outcome VALUES (?,?)",
                    (konfirmasi_id, json.dumps(tinjauan, ensure_ascii=False, sort_keys=True)))
    for butir, salinan in zip(outcome, kanonis):
        kon.execute(
            """INSERT INTO snapshot_outcome
                   (konfirmasi_id, sesi_soal_id, nomor, template_id, jawaban,
                    benar, kode_final, malrule_id, dilewati, level_efektif,
                    cek_pemahaman, target_template_id, target_kode_intervensi,
                    target_malrule_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                konfirmasi_id,
                butir["sesi_soal_id"],
                salinan["nomor"],
                salinan["template_id"],
                salinan["jawaban"],
                salinan["benar"],
                salinan["kode_final"],
                salinan["malrule_id"],
                salinan["dilewati"],
                salinan["level_efektif"],
                salinan["cek_pemahaman"],
                salinan["target_template_id"],
                salinan["target_kode_intervensi"],
                salinan["target_malrule_id"],
            ),
        )
    outcome_presentations.lengkapi(kon, konfirmasi_id)
    from skill_pilot_store import arsipkan_konfirmasi
    arsipkan_konfirmasi(kon, kontrak_pilot, konfirmasi_id)
    from choice_store import arsipkan_pilihan
    arsipkan_pilihan(kon, sesi_id, konfirmasi_id)
    kon.execute(
        """INSERT INTO kejadian_belajar
               (siswa_id, putaran_id, sesi_id, konfirmasi_id, jenis, data)
           VALUES (?, ?, ?, ?, 'hasil_dikonfirmasi', ?)""",
        (
            sesi["siswa_id"],
            sesi["putaran_id"],
            sesi_id,
            konfirmasi_id,
            json.dumps({"nomor_urut": nomor_urut}, sort_keys=True),
        ),
    )
    kon.execute(
        """UPDATE sesi
           SET dikonfirmasi_guru = datetime('now', '+7 hours'),
               fingerprint_konfirmasi = ?
           WHERE id = ?""",
        (fingerprint, sesi_id),
    )
    return konfirmasi_id


# ── Loader immutable siklus belajar ─────────────────────────────────────


def _tanggal_domain(nilai: str) -> date:
    """Ambil tanggal dari nilai SQLite date/datetime."""
    return date.fromisoformat(nilai[:10])


def _tanggal_domain_opsional(nilai: Optional[str]) -> Optional[date]:
    if nilai is None:
        return None
    return _tanggal_domain(nilai)


def _data_kejadian(nilai: str) -> tuple[tuple[str, object], ...]:
    data = json.loads(nilai or "{}")
    if not isinstance(data, dict):
        return ()

    def bekukan(objek):
        if isinstance(objek, list):
            return tuple(bekukan(item) for item in objek)
        if isinstance(objek, dict):
            return tuple(sorted((kunci, bekukan(isi)) for kunci, isi in objek.items()))
        return objek

    return tuple(sorted((kunci, bekukan(isi)) for kunci, isi in data.items()))


def muat_bukti_siklus(kon: sqlite3.Connection, siswa_id: int, *, validasi_pilot=True):
    """Muat snapshot aktif dan histori append-only sebagai input reducer murni."""
    from learning_cycle import (
        BuktiSiklus,
        KejadianSiklus,
        OutcomeSiklus,
        PutaranSiklus,
        SesiSiklus,
    )

    siswa = kon.execute(
        "SELECT id, tingkat FROM siswa WHERE id = ?", (siswa_id,)
    ).fetchone()
    if siswa is None:
        raise ValueError("siswa tidak dikenal")

    from skill_pilot_store import daftar_pilot
    pilot_sesi, pilot_putaran = daftar_pilot(kon, siswa_id)
    fokus_per_putaran: dict[int, list[tuple[str, str, Optional[str]]]] = {}
    for baris in kon.execute(
        """SELECT putaran_id, slot, template_id, kode_intervensi,
                  malrule_id_kanonis
           FROM anggota_fokus
           WHERE putaran_id IN (SELECT id FROM putaran_fokus WHERE siswa_id = ?)
           ORDER BY putaran_id, slot""",
        (siswa_id,),
    ).fetchall():
        fokus_per_putaran.setdefault(int(baris["putaran_id"]), []).append(
            (
                baris["template_id"],
                baris["kode_intervensi"],
                baris["malrule_id_kanonis"] or None,
            )
        )

    putaran = tuple(
        PutaranSiklus(
            int(baris["id"]),
            siswa_id,
            baris["level"],
            _tanggal_domain(baris["dibuka"]),
            tuple(fokus_per_putaran.get(int(baris["id"]), ())),
            pilot=int(baris['id']) in pilot_putaran,
        )
        for baris in kon.execute(
            """SELECT id, level, dibuka FROM putaran_fokus
               WHERE siswa_id = ? ORDER BY id""",
            (siswa_id,),
        ).fetchall()
    )

    kejadian = tuple(
        KejadianSiklus(
            int(baris["id"]),
            baris["jenis"],
            _tanggal_domain(baris["dibuat"]),
            baris["putaran_id"],
            baris["sesi_id"],
            baris["konfirmasi_id"],
            _data_kejadian(baris["data"]),
        )
        for baris in kon.execute(
            """SELECT id, jenis, dibuat, putaran_id, sesi_id, konfirmasi_id, data
               FROM kejadian_belajar WHERE siswa_id = ? ORDER BY id""",
            (siswa_id,),
        ).fetchall()
    )
    metadata_sesi = {
        event.sesi_id: event
        for event in kejadian
        if event.jenis == "sesi_dibuat" and event.sesi_id is not None
    }

    sesi_hasil = []
    sesi_baris = kon.execute(
        """SELECT id, level, tujuan, tanggal, dibuat, selesai, direview, format_jawaban,
                  dikonfirmasi_guru, putaran_id, bagian_checkpoint, dibatalkan,
                  fingerprint_konfirmasi
           FROM sesi WHERE siswa_id = ? ORDER BY tanggal, id""",
        (siswa_id,),
    ).fetchall()
    for baris in sesi_baris:
        outcome = ()
        aktif = None
        metadata = metadata_sesi.get(int(baris["id"]))
        target_fokus = ()
        occurrence = None
        if metadata is not None:
            fokus_mentah = metadata.nilai("fokus", ())
            if isinstance(fokus_mentah, tuple):
                target_fokus = tuple(tuple(kunci) for kunci in fokus_mentah)
            occurrence_mentah = metadata.nilai("occurrence")
            if isinstance(occurrence_mentah, int):
                occurrence = occurrence_mentah
        if baris["dikonfirmasi_guru"] is not None:
            aktif = kon.execute(
                """SELECT id FROM konfirmasi_hasil
                   WHERE sesi_id = ? AND fingerprint = ?
                   ORDER BY nomor_urut DESC, id DESC LIMIT 1""",
                (baris["id"], baris["fingerprint_konfirmasi"]),
            ).fetchone()
            if aktif is not None:
                import context_store
                target_snapshot = {
                    b['nomor']: (b['target_template_id'], b['target_kode_intervensi'], b['target_malrule_id'])
                    for b in kon.execute('SELECT * FROM snapshot_outcome WHERE konfirmasi_id=?', (aktif['id'],))
                    if b['target_template_id'] is not None
                }
                context_store.validasi_arsip(kon, baris['id'], int(aktif['id']), target_snapshot)
                if baris['format_jawaban'] == 'pilihan_ganda':
                    from choice_store import validasi_arsip
                    validasi_arsip(kon, baris['id'], int(aktif['id']))
                outcome = tuple(
                    OutcomeSiklus(
                        item["template_id"],
                        None if item["benar"] is None else bool(item["benar"]),
                        item["kode_final"],
                        item["malrule_id"],
                        bool(item["dilewati"]),
                        item["cek_pemahaman"],
                        (
                            None
                            if item["target_template_id"] is None
                            else (
                                item["target_template_id"],
                                item["target_kode_intervensi"],
                                item["target_malrule_id"],
                            )
                        ),
                        mode_representasi=item["mode_representasi"],
                        fingerprint_penyajian=item["fingerprint_penyajian"],
                    )
                    for item in outcome_presentations.muat(kon, int(aktif["id"]))
                )
        sesi_hasil.append(
            SesiSiklus(
                int(baris["id"]),
                siswa_id,
                baris["level"],
                baris["tujuan"],
                _tanggal_domain(baris["tanggal"]),
                baris["dibuat"],
                baris["selesai"],
                baris["direview"],
                baris["dikonfirmasi_guru"],
                baris["putaran_id"],
                baris["bagian_checkpoint"],
                baris["dibatalkan"],
                outcome,
                target_fokus,
                occurrence,
                None if aktif is None else int(aktif["id"]),
                _tanggal_domain_opsional(baris["selesai"]),
                _tanggal_domain_opsional(baris["dikonfirmasi_guru"]),
                format_jawaban=baris['format_jawaban'],
                pilot=int(baris['id']) in pilot_sesi or baris['putaran_id'] in pilot_putaran,
            )
        )
    import interventions
    from learning_cycle import _putaran_dengan_override

    putaran_efektif = tuple(
        _putaran_dengan_override(item, kejadian) for item in putaran
    )
    pendekatan_tersedia = tuple(
        (
            kunci,
            tuple(
                materi.pendekatan_id
                for materi in interventions.pilihan_untuk_fokus(kunci)
                if materi.tersedia
            ),
        )
        for satu_putaran in putaran_efektif
        if satu_putaran is not None
        for kunci in satu_putaran.fokus
    )
    if validasi_pilot:
        from skill_pilot_store import baca_kontrak, validasi_konfirmasi
        for sesi in sesi_hasil:
            if sesi.pilot:
                baca_kontrak(kon, sesi.id, siswa_id)
                if sesi.konfirmasi_id is not None:
                    validasi_konfirmasi(kon, sesi.id, siswa_id, sesi.konfirmasi_id)
    return BuktiSiklus(
        siswa_id,
        siswa["tingkat"],
        tuple(sesi_hasil),
        putaran,
        kejadian,
        pendekatan_tersedia,
    )

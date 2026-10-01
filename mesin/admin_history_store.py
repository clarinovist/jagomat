"""Proyeksi histori journal admin tanpa payload sensitif."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from admin_contracts import JENIS_TARGET, STATUS_OPERASI, validasi_id
from admin_journal_store import DataAuditTidakSah


@dataclass(frozen=True)
class PerubahanRiwayat:
    field_kode: str
    nilai_lama: str
    nilai_baru: str


@dataclass(frozen=True)
class EntriRiwayat:
    operasi_id: str
    actor_id: str
    aksi: str
    jenis_target: str
    target_id: str
    target_peran: Optional[str]
    status: str
    hasil_kode: Optional[str]
    revisi_hasil: Optional[int]
    hasil_id: Optional[str]
    credential_status: str
    dibuat: int
    perubahan: Tuple[PerubahanRiwayat, ...]


@dataclass(frozen=True)
class HalamanRiwayat:
    item: Tuple[EntriRiwayat, ...]
    total: int
    halaman: int
    per_halaman: int
    jumlah_halaman: int

def daftar_riwayat(
    path=None,
    *,
    actor_id: str = "",
    aksi: str = "",
    status: str = "",
    mulai: Optional[int] = None,
    selesai: Optional[int] = None,
    halaman: int = 1,
    per_halaman: int = 25,
    buka_baca,
) -> HalamanRiwayat:
    """Proyeksi journal aman, termasuk reserved/uncertain tanpa raw payload."""
    if actor_id:
        validasi_id(actor_id, "actor_id")
    if aksi and aksi not in JENIS_TARGET:
        raise DataAuditTidakSah("filter aksi tidak sah")
    if status and status not in STATUS_OPERASI:
        raise DataAuditTidakSah("filter status tidak sah")
    if type(halaman) is not int or halaman < 1:
        raise DataAuditTidakSah("halaman tidak sah")
    if type(per_halaman) is not int or not 1 <= per_halaman <= 100:
        raise DataAuditTidakSah("per_halaman tidak sah")
    for nilai, label in ((mulai, "mulai"), (selesai, "selesai")):
        if nilai is not None and (type(nilai) is not int or nilai < 0):
            raise DataAuditTidakSah("filter %s tidak sah" % label)
    if mulai is not None and selesai is not None and mulai > selesai:
        raise DataAuditTidakSah("rentang tanggal tidak sah")
    klausa = []
    argumen = []
    if actor_id:
        klausa.append("actor_id=?")
        argumen.append(actor_id)
    if aksi:
        klausa.append("aksi=?")
        argumen.append(aksi)
    if status:
        klausa.append("status=?")
        argumen.append(status)
    if mulai is not None:
        klausa.append("dibuat>=?")
        argumen.append(mulai)
    if selesai is not None:
        klausa.append("dibuat<=?")
        argumen.append(selesai)
    where = " WHERE " + " AND ".join(klausa) if klausa else ""
    with buka_baca(path) as kon:
        total = int(kon.execute(
            "SELECT COUNT(*) FROM operasi_admin" + where, tuple(argumen)
        ).fetchone()[0])
        baris = kon.execute(
            "SELECT * FROM operasi_admin" + where
            + " ORDER BY dibuat DESC,operasi_id DESC LIMIT ? OFFSET ?",
            tuple(argumen) + (per_halaman, (halaman - 1) * per_halaman),
        ).fetchall()
        operasi_ids = [item["operasi_id"] for item in baris]
        perubahan = {}
        if operasi_ids:
            placeholder = ",".join("?" for _ in operasi_ids)
            semua = kon.execute(
                """SELECT a.operasi_id,p.field_kode,p.nilai_lama,p.nilai_baru
                   FROM audit_admin_perubahan p
                   JOIN audit_admin a ON a.id=p.audit_id
                   WHERE a.operasi_id IN (%s)
                   ORDER BY a.operasi_id,p.field_kode""" % placeholder,
                tuple(operasi_ids),
            ).fetchall()
            for item in semua:
                perubahan.setdefault(item["operasi_id"], []).append(
                    PerubahanRiwayat(
                        item["field_kode"], item["nilai_lama"], item["nilai_baru"]
                    )
                )
    jumlah_halaman = max(1, (total + per_halaman - 1) // per_halaman)
    return HalamanRiwayat(
        tuple(
            EntriRiwayat(
                item["operasi_id"], item["actor_id"], item["aksi"],
                item["jenis_target"], item["target_id"], item["target_peran"],
                item["status"], item["hasil_kode"], item["revisi_hasil"],
                item["hasil_id"], item["credential_status"], item["dibuat"],
                tuple(perubahan.get(item["operasi_id"], ())),
            )
            for item in baris
        ),
        total,
        halaman,
        per_halaman,
        jumlah_halaman,
    )

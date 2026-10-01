"""Journal, audit, dan konfigurasi pusat kendali admin."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Mapping, Optional, Tuple

from admin_contracts import (
    AKSI_UBAH_PENDAFTARAN, FIELD_AUDIT, HASIL_KODE, JENIS_TARGET,
    PESAN_PENDAFTARAN, STATUS_OPERASI, STATUS_TERMINAL, HasilOperasi,
    ReceiptAkun, receipt_cocok, sidik_perintah, validasi_id, validasi_revisi,
)
from admin_store_core import StoreBelumSiap


RETENSI_AUDIT_HARI = 180

class KonflikOperasi(RuntimeError):
    """Revisi stale atau operation ID memiliki identitas berbeda."""

class DataAuditTidakSah(ValueError):
    """Metadata audit tidak masuk allow-list."""

@dataclass(frozen=True)
class KonfigurasiPendaftaran:
    revisi: int
    dibuka: bool
    pesan_kode: str
    diperbarui: int


@dataclass(frozen=True)
class ReservasiOperasi:
    dibuat_baru: bool
    hasil: HasilOperasi

def _hasil_dari_baris(baris) -> HasilOperasi:
    return HasilOperasi(
        baris["operasi_id"],
        baris["aksi"],
        baris["target_id"],
        baris["target_peran"],
        baris["status"],
        baris["hasil_kode"],
        None if baris["revisi_hasil"] is None else int(baris["revisi_hasil"]),
        baris["credential_status"],
        baris["hasil_id"],
    )

def baca_operasi(
    path, operasi_id: str, *, buka_baca,
) -> Optional[HasilOperasi]:
    validasi_id(operasi_id, "operasi_id")
    with buka_baca(path) as kon:
        baris = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?", (operasi_id,)
        ).fetchone()
        return None if baris is None else _hasil_dari_baris(baris)

def _baris_cocok_perintah(baris, perintah) -> bool:
    return bool(
        baris["actor_id"] == perintah.actor_id
        and baris["aksi"] == perintah.aksi
        and baris["jenis_target"] == JENIS_TARGET[perintah.aksi]
        and baris["target_id"] == perintah.target_id
        and baris["target_peran"] == perintah.target_peran
        and int(baris["revisi_target"]) == perintah.target_revisi
        and baris["sidik_perintah"] == sidik_perintah(perintah)
    )

def reservasi(
    path,
    perintah,
    *,
    sekarang: Optional[int] = None,
    transaksi,
) -> ReservasiOperasi:
    """Reservasi idempoten; transaksi berakhir sebelum domain auth dikunci."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    sidik = sidik_perintah(perintah)
    with transaksi(path) as kon:
        lama = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        if lama is not None:
            if not _baris_cocok_perintah(lama, perintah):
                raise KonflikOperasi("operasi_id dipakai perintah berbeda")
            return ReservasiOperasi(False, _hasil_dari_baris(lama))
        credential = (
            "unconfirmed"
            if perintah.aksi in (
                "account_password_reset", "account_teacher_create",
                "student_login_create",
            )
            else "not_applicable"
        )
        kon.execute(
            """INSERT INTO operasi_admin(
                   operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                   revisi_target,sidik_perintah,status,credential_status,
                   dibuat,diperbarui)
               VALUES(?,?,?,?,?,?,?,?, 'reserved',?,?,?)""",
            (
                perintah.operasi_id,
                perintah.actor_id,
                perintah.aksi,
                JENIS_TARGET[perintah.aksi],
                perintah.target_id,
                perintah.target_peran,
                perintah.target_revisi,
                sidik,
                credential,
                kini,
                kini,
            ),
        )
        baris = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        return ReservasiOperasi(True, _hasil_dari_baris(baris))

def _validasi_nilai_audit(field_kode: str, nilai: str) -> None:
    if type(nilai) is not str:
        raise DataAuditTidakSah("nilai audit harus kode teks")
    if field_kode == "auth_revision":
        sah = nilai.isdigit() and 0 <= int(nilai) <= 2_147_483_647
    elif field_kode == "student_level":
        sah = nilai in ("P3", "P4", "P5", "P6")
    elif field_kode == 'student_school_grade':
        sah = nilai in ('', '1', '2', '3', '4', '5', '6')
    elif field_kode == "registration_open":
        sah = nilai in ("0", "1")
    elif field_kode == "registration_message":
        sah = nilai in PESAN_PENDAFTARAN
    else:
        sah = False
    if not sah:
        raise DataAuditTidakSah("field atau nilai audit tidak diizinkan")

def validasi_perubahan_audit(
    perubahan: Mapping[str, Tuple[str, str]],
) -> Tuple[Tuple[str, str, str], ...]:
    """Terima hanya mapping field-code ke pasangan kode lama/baru."""
    if not isinstance(perubahan, Mapping):
        raise DataAuditTidakSah("perubahan audit bukan mapping")
    hasil = []
    for field_kode, pasangan in perubahan.items():
        if field_kode not in FIELD_AUDIT:
            raise DataAuditTidakSah("field audit tidak diizinkan")
        if type(pasangan) is not tuple or len(pasangan) != 2:
            raise DataAuditTidakSah("nilai audit bukan pasangan")
        lama, baru = pasangan
        _validasi_nilai_audit(field_kode, lama)
        _validasi_nilai_audit(field_kode, baru)
        hasil.append((field_kode, lama, baru))
    return tuple(sorted(hasil))

def _tulis_audit(
    kon,
    *,
    operasi_id: str,
    actor_id: str,
    aksi: str,
    jenis_target: str,
    target_id: str,
    target_peran: Optional[str],
    status: str,
    hasil_kode: str,
    perubahan: Mapping[str, Tuple[str, str]],
    sekarang: int,
) -> None:
    if aksi not in JENIS_TARGET or JENIS_TARGET[aksi] != jenis_target:
        raise DataAuditTidakSah("aksi/target audit tidak cocok")
    if status not in STATUS_OPERASI or status == "reserved":
        raise DataAuditTidakSah("status audit tidak sah")
    if hasil_kode not in HASIL_KODE:
        raise DataAuditTidakSah("hasil audit tidak sah")
    daftar = validasi_perubahan_audit(perubahan)
    kursor = kon.execute(
        """INSERT OR IGNORE INTO audit_admin(
               operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
               status,hasil_kode,dibuat) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            operasi_id, actor_id, aksi, jenis_target, target_id, target_peran,
            status, hasil_kode, sekarang,
        ),
    )
    if not kursor.rowcount:
        return
    audit_id = int(kursor.lastrowid)
    kon.executemany(
        "INSERT INTO audit_admin_perubahan VALUES(?,?,?,?)",
        [(audit_id, field, lama, baru) for field, lama, baru in daftar],
    )

def finalisasi_sukses(
    path,
    perintah,
    receipt: ReceiptAkun,
    *,
    sekarang: Optional[int] = None,
    perubahan: Optional[Mapping[str, Tuple[str, str]]] = None,
    transaksi,
) -> HasilOperasi:
    if not receipt_cocok(receipt, perintah):
        raise KonflikOperasi("receipt tidak cocok dengan journal")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with transaksi(path) as kon:
        baris = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        if baris is None or not _baris_cocok_perintah(baris, perintah):
            raise KonflikOperasi("journal tidak cocok dengan receipt")
        if baris["status"] == "succeeded":
            if (
                baris["hasil_kode"] != receipt.hasil_kode
                or int(baris["revisi_hasil"]) != receipt.revisi_hasil
                or baris["hasil_id"] != getattr(receipt, "hasil_id", None)
            ):
                raise KonflikOperasi("hasil journal berbeda dari receipt")
            # Audit boleh sudah terpurge setelah 180 hari; journal durable dan
            # receipt domain tetap menjadi sumber dedup/replay.
            return _hasil_dari_baris(baris)
        if baris["status"] in STATUS_TERMINAL:
            raise KonflikOperasi("operasi terminal tidak dapat difinalkan sukses")
        kon.execute(
            """UPDATE operasi_admin SET status='succeeded',hasil_kode=?,
                   revisi_hasil=?,hasil_id=?,diperbarui=? WHERE operasi_id=?""",
            (
                receipt.hasil_kode,
                receipt.revisi_hasil,
                getattr(receipt, "hasil_id", None),
                kini,
                perintah.operasi_id,
            ),
        )
        if perubahan is None:
            if JENIS_TARGET[perintah.aksi] in ("account", "account_candidate"):
                perubahan = {
                    "auth_revision": (
                        str(receipt.revisi_awal), str(receipt.revisi_hasil)
                    )
                }
            else:
                perubahan = dict(
                    (field, (lama, baru))
                    for field, lama, baru in getattr(receipt, "perubahan", ())
                )
        _tulis_audit(
            kon,
            operasi_id=perintah.operasi_id,
            actor_id=perintah.actor_id,
            aksi=perintah.aksi,
            jenis_target=JENIS_TARGET[perintah.aksi],
            target_id=perintah.target_id,
            target_peran=perintah.target_peran,
            status="succeeded",
            hasil_kode=receipt.hasil_kode,
            perubahan=perubahan,
            sekarang=kini,
        )
        akhir = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        return _hasil_dari_baris(akhir)

def finalisasi_gagal(
    path,
    perintah,
    *,
    status: str,
    hasil_kode: str,
    sekarang: Optional[int] = None,
    transaksi,
) -> HasilOperasi:
    if status not in ("failed_before_commit", "conflict", "uncertain", "cancelled"):
        raise DataAuditTidakSah("status gagal tidak diizinkan")
    if hasil_kode not in (
        "target_changed", "input_rejected", "domain_not_committed", "domain_uncertain"
    ):
        raise DataAuditTidakSah("kode gagal tidak diizinkan")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with transaksi(path) as kon:
        baris = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        if baris is None or not _baris_cocok_perintah(baris, perintah):
            raise KonflikOperasi("journal operasi tidak cocok")
        if baris["status"] == "succeeded":
            return _hasil_dari_baris(baris)
        if baris["status"] in STATUS_TERMINAL:
            return _hasil_dari_baris(baris)
        if baris["status"] == "uncertain" and status == "uncertain":
            return _hasil_dari_baris(baris)
        credential = (
            "unconfirmed"
            if status == "uncertain" and perintah.aksi in (
                "account_password_reset", "account_teacher_create",
                "student_login_create",
            )
            else "not_applicable"
        )
        kon.execute(
            """UPDATE operasi_admin SET status=?,hasil_kode=?,
                   credential_status=?,diperbarui=? WHERE operasi_id=?""",
            (status, hasil_kode, credential, kini, perintah.operasi_id),
        )
        _tulis_audit(
            kon,
            operasi_id=perintah.operasi_id,
            actor_id=perintah.actor_id,
            aksi=perintah.aksi,
            jenis_target=JENIS_TARGET[perintah.aksi],
            target_id=perintah.target_id,
            target_peran=perintah.target_peran,
            status=status,
            hasil_kode=hasil_kode,
            perubahan={},
            sekarang=kini,
        )
        akhir = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        return _hasil_dari_baris(akhir)

def baca_konfigurasi(
    path=None, *, buka_baca,
) -> KonfigurasiPendaftaran:
    with buka_baca(path) as kon:
        baris = kon.execute(
            "SELECT revisi,dibuka,pesan_kode,diperbarui FROM konfigurasi_pendaftaran WHERE id=1"
        ).fetchone()
        if baris is None:
            raise StoreBelumSiap("konfigurasi pendaftaran tidak tersedia")
        return KonfigurasiPendaftaran(
            int(baris["revisi"]), bool(baris["dibuka"]),
            str(baris["pesan_kode"]), int(baris["diperbarui"]),
        )

def _sidik_config(
    operasi_id: str,
    actor_id: str,
    revisi: int,
    dibuka: bool,
    pesan_kode: str,
    token_tinjauan: str,
) -> str:
    validasi_id(operasi_id, "operasi_id")
    validasi_id(actor_id, "actor_id")
    validasi_revisi(revisi, "revisi")
    if type(dibuka) is not bool or pesan_kode not in PESAN_PENDAFTARAN:
        raise DataAuditTidakSah("nilai konfigurasi tidak sah")
    if type(token_tinjauan) is not str or len(token_tinjauan) < 32:
        raise DataAuditTidakSah("token tinjauan tidak sah")
    data = {
        "operasi_id": operasi_id,
        "actor_id": actor_id,
        "aksi": AKSI_UBAH_PENDAFTARAN,
        "target_id": "config_registration",
        "revisi": revisi,
        "dibuka": dibuka,
        "pesan_kode": pesan_kode,
        "token_tinjauan": token_tinjauan,
    }
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")).hexdigest()

def ubah_konfigurasi(
    path,
    *,
    operasi_id: str,
    actor_id: str,
    revisi: int,
    dibuka: bool,
    pesan_kode: str,
    token_tinjauan: str,
    sekarang: Optional[int] = None,
    failpoint: Optional[str] = None,
    transaksi,
) -> HasilOperasi:
    """Update konfigurasi+journal+audit dalam satu transaksi."""
    sidik = _sidik_config(
        operasi_id, actor_id, revisi, dibuka, pesan_kode, token_tinjauan
    )
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with transaksi(path) as kon:
        lama = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?", (operasi_id,)
        ).fetchone()
        if lama is not None:
            cocok = bool(
                lama["actor_id"] == actor_id
                and lama["aksi"] == AKSI_UBAH_PENDAFTARAN
                and lama["jenis_target"] == "registration_config"
                and lama["target_id"] == "config_registration"
                and int(lama["revisi_target"]) == revisi
                and lama["sidik_perintah"] == sidik
            )
            if not cocok:
                raise KonflikOperasi("operasi konfigurasi berbeda")
            return _hasil_dari_baris(lama)
        config = kon.execute(
            "SELECT * FROM konfigurasi_pendaftaran WHERE id=1"
        ).fetchone()
        if config is None:
            raise StoreBelumSiap("konfigurasi pendaftaran tidak tersedia")
        if int(config["revisi"]) != revisi:
            raise KonflikOperasi("revisi konfigurasi stale")
        revisi_hasil = revisi + 1
        kon.execute(
            """INSERT INTO operasi_admin(
                   operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                   revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
                   credential_status,dibuat,diperbarui)
               VALUES(?,?,?,'registration_config','config_registration',NULL,
                      ?,?,'succeeded','config_updated',?,'not_applicable',?,?)""",
            (
                operasi_id, actor_id, AKSI_UBAH_PENDAFTARAN, revisi, sidik,
                revisi_hasil, kini, kini,
            ),
        )
        kon.execute(
            """UPDATE konfigurasi_pendaftaran
               SET revisi=?,dibuka=?,pesan_kode=?,diperbarui=? WHERE id=1""",
            (revisi_hasil, int(dibuka), pesan_kode, kini),
        )
        if failpoint == "setelah_config_sebelum_audit":
            raise RuntimeError("failpoint konfigurasi sintetis")
        perubahan = {}
        if int(config["dibuka"]) != int(dibuka):
            perubahan["registration_open"] = (
                str(int(config["dibuka"])), str(int(dibuka))
            )
        if config["pesan_kode"] != pesan_kode:
            perubahan["registration_message"] = (
                str(config["pesan_kode"]), pesan_kode
            )
        _tulis_audit(
            kon,
            operasi_id=operasi_id,
            actor_id=actor_id,
            aksi=AKSI_UBAH_PENDAFTARAN,
            jenis_target="registration_config",
            target_id="config_registration",
            target_peran=None,
            status="succeeded",
            hasil_kode="config_updated",
            perubahan=perubahan,
            sekarang=kini,
        )
        baris = kon.execute(
            "SELECT * FROM operasi_admin WHERE operasi_id=?", (operasi_id,)
        ).fetchone()
        return _hasil_dari_baris(baris)

def purge_audit(
    path=None, *, sekarang: Optional[int] = None, batas_baris: int = 500,
    transaksi,
) -> int:
    """Hapus audit >180 hari secara bounded; journal/receipt tidak ikut."""
    if type(batas_baris) is not int or not 1 <= batas_baris <= 10_000:
        raise DataAuditTidakSah("batas purge audit tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    batas = kini - RETENSI_AUDIT_HARI * 86400
    with transaksi(path) as kon:
        ids = [row[0] for row in kon.execute(
            "SELECT id FROM audit_admin WHERE dibuat < ? ORDER BY id LIMIT ?",
            (batas, batas_baris),
        )]
        if not ids:
            return 0
        placeholder = ",".join("?" for _ in ids)
        kursor = kon.execute(
            "DELETE FROM audit_admin WHERE id IN (%s)" % placeholder, tuple(ids)
        )
        return int(kursor.rowcount)

"""SQLite privat untuk konfigurasi, journal, dan audit pusat kendali admin.

Bootstrap hanya melalui :func:`siapkan`. Semua reader/mutator lain membuka file
existing dengan mode URI ``ro``/``rw`` agar GET atau kegagalan konfigurasi tidak
membuat database kosong diam-diam.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Mapping, Optional, Tuple

from admin_contracts import (
    AKSI_UBAH_PENDAFTARAN,
    FIELD_AUDIT,
    HASIL_KODE,
    JENIS_TARGET,
    PESAN_PENDAFTARAN,
    STATUS_OPERASI,
    STATUS_TERMINAL,
    HasilOperasi,
    ReceiptAkun,
    receipt_cocok,
    sidik_perintah,
    validasi_id,
    validasi_revisi,
    validasi_sidik,
)


BAWAAN = Path(os.environ.get("ADMIN_BERKAS_DB", "/data/admin-control.db"))
VERSI_SKEMA = 7
RETENSI_AUDIT_HARI = 180


class StoreBelumSiap(RuntimeError):
    """Database admin belum dibootstrap atau tidak dapat dibuka aman."""


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


_DDL = """
CREATE TABLE IF NOT EXISTS konfigurasi_pendaftaran (
    id INTEGER PRIMARY KEY CHECK (id=1),
    revisi INTEGER NOT NULL CHECK (revisi>=1),
    dibuka INTEGER NOT NULL CHECK (dibuka IN (0,1)),
    pesan_kode TEXT NOT NULL CHECK (
        pesan_kode IN ('closed_standard','closed_maintenance')
    ),
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS operasi_admin (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL CHECK (aksi IN (
        'account_password_reset','account_session_revoke',
        'account_login_delete','student_login_delete_step','account_teacher_create',
        'student_login_create','student_level_update','student_school_grade_update','student_delete',
        'registration_config_update'
    )),
    jenis_target TEXT NOT NULL CHECK (
        jenis_target IN ('account','account_candidate','student','registration_config')
    ),
    target_id TEXT NOT NULL,
    target_peran TEXT CHECK (target_peran IS NULL OR target_peran IN ('guru','murid')),
    revisi_target INTEGER NOT NULL CHECK (revisi_target>=0),
    sidik_perintah TEXT NOT NULL CHECK (length(sidik_perintah)=64),
    status TEXT NOT NULL CHECK (status IN (
        'reserved','succeeded','failed_before_commit',
        'conflict','uncertain','cancelled'
    )),
    hasil_kode TEXT,
    revisi_hasil INTEGER,
    hasil_id TEXT,
    credential_status TEXT NOT NULL CHECK (
        credential_status IN ('not_applicable','unconfirmed','confirmed')
    ),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS receipt_admin (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL CHECK(aksi IN ('student_level_update','student_school_grade_update','student_delete')),
    jenis_target TEXT NOT NULL CHECK(jenis_target='student'),
    target_id TEXT NOT NULL,
    sidik_perintah TEXT NOT NULL CHECK(length(sidik_perintah)=64),
    hasil_kode TEXT NOT NULL CHECK(hasil_kode IN ('student_level_updated','student_school_grade_updated','student_deleted')),
    dibuat INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_admin (
    id INTEGER PRIMARY KEY,
    operasi_id TEXT NOT NULL REFERENCES operasi_admin(operasi_id) ON DELETE RESTRICT,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL,
    jenis_target TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_peran TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'succeeded','failed_before_commit','conflict','uncertain','cancelled'
    )),
    hasil_kode TEXT NOT NULL CHECK (hasil_kode IN (
        'password_reset','sessions_revoked','login_deleted','teacher_created',
        'student_login_created','student_level_updated','student_school_grade_updated','student_deleted','config_updated',
        'target_changed','input_rejected','domain_not_committed','domain_uncertain'
    )),
    dibuat INTEGER NOT NULL,
    UNIQUE (operasi_id,status)
);
CREATE INDEX IF NOT EXISTS idx_audit_admin_waktu
    ON audit_admin(dibuat DESC,id DESC);
CREATE TABLE IF NOT EXISTS audit_admin_perubahan (
    audit_id INTEGER NOT NULL REFERENCES audit_admin(id) ON DELETE CASCADE,
    field_kode TEXT NOT NULL,
    nilai_lama TEXT NOT NULL,
    nilai_baru TEXT NOT NULL,
    PRIMARY KEY (audit_id,field_kode)
);
CREATE TABLE IF NOT EXISTS batch_admin (
    batch_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    session_hash TEXT NOT NULL CHECK(length(session_hash)=64),
    aksi TEXT NOT NULL CHECK(aksi IN (
        'account_teacher_create','account_password_reset','account_session_revoke'
    )),
    target_peran TEXT NOT NULL CHECK(target_peran IN ('guru','murid')),
    jumlah_total INTEGER NOT NULL CHECK(jumlah_total BETWEEN 1 AND 100),
    status TEXT NOT NULL CHECK(status IN (
        'ready','running','partial','stopped','succeeded','attention'
    )),
    kelompok_aktif_id TEXT,
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS batch_admin_item (
    batch_id TEXT NOT NULL REFERENCES batch_admin(batch_id) ON DELETE RESTRICT,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    operasi_id TEXT NOT NULL UNIQUE,
    target_id TEXT NOT NULL,
    target_revisi INTEGER NOT NULL CHECK(target_revisi>=0),
    status TEXT NOT NULL CHECK(status IN (
        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'
    )),
    hasil_id TEXT,
    credential_status TEXT NOT NULL CHECK(
        credential_status IN ('not_applicable','unconfirmed','confirmed')
    ),
    diperbarui INTEGER NOT NULL,
    PRIMARY KEY(batch_id,item_id),
    UNIQUE(batch_id,target_id)
);
CREATE TABLE IF NOT EXISTS kelompok_admin (
    kelompok_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batch_admin(batch_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('running','completed','attention')),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kelompok_admin_item (
    kelompok_id TEXT NOT NULL REFERENCES kelompok_admin(kelompok_id) ON DELETE RESTRICT,
    batch_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    PRIMARY KEY(kelompok_id,item_id),
    FOREIGN KEY(batch_id,item_id) REFERENCES batch_admin_item(batch_id,item_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS penyerahan_admin (
    operasi_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batch_admin(batch_id) ON DELETE RESTRICT,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    sidik_item TEXT NOT NULL CHECK(length(sidik_item)=64),
    jumlah INTEGER NOT NULL CHECK(jumlah BETWEEN 1 AND 100),
    dibuat INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS penyerahan_admin_item (
    operasi_id TEXT NOT NULL REFERENCES penyerahan_admin(operasi_id) ON DELETE RESTRICT,
    batch_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    PRIMARY KEY(operasi_id,item_id),
    FOREIGN KEY(batch_id,item_id) REFERENCES batch_admin_item(batch_id,item_id) ON DELETE RESTRICT
);
"""

_KOLOM_WAJIB = {
    "konfigurasi_pendaftaran": {
        "id", "revisi", "dibuka", "pesan_kode", "diperbarui",
    },
    "operasi_admin": {
        "operasi_id", "actor_id", "aksi", "jenis_target", "target_id",
        "target_peran", "revisi_target", "sidik_perintah", "status",
        "hasil_kode", "revisi_hasil", "hasil_id", "credential_status", "dibuat",
        "diperbarui",
    },
    "receipt_admin": {
        "operasi_id", "actor_id", "aksi", "jenis_target", "target_id",
        "sidik_perintah", "hasil_kode", "dibuat",
    },
    "audit_admin": {
        "id", "operasi_id", "actor_id", "aksi", "jenis_target",
        "target_id", "target_peran", "status", "hasil_kode", "dibuat",
    },
    "audit_admin_perubahan": {
        "audit_id", "field_kode", "nilai_lama", "nilai_baru",
    },
    "batch_admin": {
        "batch_id", "actor_id", "actor_revisi", "session_hash", "aksi",
        "target_peran", "jumlah_total", "status", "kelompok_aktif_id",
        "dibuat", "diperbarui",
    },
    "batch_admin_item": {
        "batch_id", "item_id", "urutan", "operasi_id", "target_id",
        "target_revisi", "status", "hasil_id", "credential_status",
        "diperbarui",
    },
    "kelompok_admin": {
        "kelompok_id", "batch_id", "status", "dibuat", "diperbarui",
    },
    "kelompok_admin_item": {
        "kelompok_id", "batch_id", "item_id", "urutan",
    },
    "penyerahan_admin": {
        "operasi_id", "batch_id", "actor_id", "actor_revisi",
        "sidik_item", "jumlah", "dibuat",
    },
    "penyerahan_admin_item": {
        "operasi_id", "batch_id", "item_id",
    },
}


def _tujuan(path=None) -> Path:
    return Path(path) if path is not None else BAWAAN


def _uri(path: Path, mode: str) -> str:
    return path.resolve().as_uri() + "?mode=" + mode


def _koneksi(path: Path, mode: str) -> sqlite3.Connection:
    try:
        kon = sqlite3.connect(_uri(path, mode), uri=True, timeout=5.0)
    except sqlite3.Error as galat:
        raise StoreBelumSiap("store admin tidak tersedia") from galat
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys=ON")
    kon.execute("PRAGMA busy_timeout=5000")
    return kon


@contextmanager
def buka_baca(path=None):
    """Buka readonly tanpa membuat file atau menjalankan migrasi."""
    kon = _koneksi(_tujuan(path), "ro")
    try:
        kon.execute("PRAGMA query_only=ON")
        _validasi_skema(kon)
        yield kon
    finally:
        kon.close()


@contextmanager
def _transaksi(path=None):
    kon = _koneksi(_tujuan(path), "rw")
    try:
        _validasi_skema(kon)
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def _validasi_skema(kon: sqlite3.Connection) -> None:
    versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
    if versi > VERSI_SKEMA:
        raise StoreBelumSiap("skema admin lebih baru dari aplikasi")
    if versi != VERSI_SKEMA:
        raise StoreBelumSiap("store admin belum dimigrasikan")
    for tabel, wajib in _KOLOM_WAJIB.items():
        aktual = {
            str(baris[1]) for baris in kon.execute("PRAGMA table_info(%s)" % tabel)
        }
        if not wajib <= aktual:
            raise StoreBelumSiap("struktur store admin tidak lengkap")
    import subscription_schema
    try:
        subscription_schema.validasi(kon)
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur ledger langganan tidak lengkap") from None
    import admin_launch_schema
    try:
        admin_launch_schema.validasi(kon)
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur layanan admin tidak lengkap") from None


def _jalankan_ddl(kon: sqlite3.Connection, skrip: str) -> None:
    """Jalankan DDL utuh tanpa implicit commit dari ``executescript``."""
    bagian = ""
    for baris in skrip.splitlines(keepends=True):
        bagian += baris
        if sqlite3.complete_statement(bagian):
            kon.execute(bagian)
            bagian = ""
    if bagian.strip():
        raise StoreBelumSiap("DDL store admin tidak lengkap")


def _migrasi_registry_aksi(
    kon: sqlite3.Connection, *, sumber_punya_hasil_id: bool, pertahankan_batch: bool = False
) -> None:
    """Rebuild CHECK registry sambil mempertahankan seluruh data lama."""
    ada_anchor = kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='receipt_admin'"
    ).fetchone() is not None
    tabel_batch = (
        "penyerahan_admin_item", "penyerahan_admin", "kelompok_admin_item",
        "kelompok_admin", "batch_admin_item", "batch_admin",
    )
    for tabel in (() if pertahankan_batch else tabel_batch):
        if kon.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabel,)
        ).fetchone():
            kon.execute('DROP TABLE "%s"' % tabel)
    _jalankan_ddl(
        kon,
        """
        ALTER TABLE audit_admin_perubahan RENAME TO audit_admin_perubahan_v1;
        ALTER TABLE audit_admin RENAME TO audit_admin_v1;
        ALTER TABLE operasi_admin RENAME TO operasi_admin_v1;
        DROP INDEX IF EXISTS idx_audit_admin_waktu;
        """,
    )
    if ada_anchor:
        kon.execute("ALTER TABLE receipt_admin RENAME TO receipt_admin_v1")
    _jalankan_ddl(kon, _DDL)
    kolom_hasil_id = "hasil_id" if sumber_punya_hasil_id else "NULL"
    kon.execute(
        """INSERT INTO operasi_admin(
               operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
               revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
               hasil_id,credential_status,dibuat,diperbarui)
           SELECT operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
               revisi_target,sidik_perintah,status,hasil_kode,revisi_hasil,
               %s,credential_status,dibuat,diperbarui
           FROM operasi_admin_v1""" % kolom_hasil_id
    )
    kon.execute(
        """INSERT INTO audit_admin
           SELECT id,operasi_id,actor_id,aksi,jenis_target,target_id,target_peran,
                  status,hasil_kode,dibuat FROM audit_admin_v1"""
    )
    kon.execute(
        """INSERT INTO audit_admin_perubahan
           SELECT audit_id,field_kode,nilai_lama,nilai_baru
           FROM audit_admin_perubahan_v1"""
    )
    if ada_anchor:
        kon.execute(
            """INSERT INTO receipt_admin
               SELECT operasi_id,actor_id,aksi,jenis_target,target_id,
                      sidik_perintah,hasil_kode,dibuat FROM receipt_admin_v1"""
        )
        kon.execute("DROP TABLE receipt_admin_v1")
    kon.execute("DROP TABLE audit_admin_perubahan_v1")
    kon.execute("DROP TABLE audit_admin_v1")
    kon.execute("DROP TABLE operasi_admin_v1")


def siapkan(path=None, *, sekarang: Optional[int] = None) -> None:
    """Bootstrap eksplisit; admin5→6 additive tanpa enrollment/backfill akun."""
    tujuan = _tujuan(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kon = sqlite3.connect(str(tujuan), timeout=5.0)
    try:
        kon.row_factory = sqlite3.Row
        versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
        if versi > VERSI_SKEMA:
            raise StoreBelumSiap("skema admin lebih baru dari aplikasi")
        if versi in (0, 1, 2, 3, 4):
            try:
                if versi in (1, 2, 3, 4):
                    # PRAGMA ini harus dijalankan sebelum BEGIN; SQLite
                    # mengabaikan perubahan foreign_keys di dalam transaksi.
                    kon.execute("PRAGMA foreign_keys=OFF")
                else:
                    kon.execute("PRAGMA foreign_keys=ON")
                kon.execute("BEGIN IMMEDIATE")
                # Baca ulang setelah lock; migrator lain mungkin sudah selesai.
                versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
                if versi > VERSI_SKEMA:
                    raise StoreBelumSiap("skema admin lebih baru dari aplikasi")
                if versi in (1, 2, 3, 4):
                    _migrasi_registry_aksi(
                        kon, sumber_punya_hasil_id=(versi >= 2),
                        pertahankan_batch=(versi == 4),
                    )
                elif versi == 0:
                    _jalankan_ddl(kon, _DDL)
                kon.execute(
                    "INSERT OR IGNORE INTO konfigurasi_pendaftaran VALUES(1,1,1,?,?)",
                    ("closed_standard", int(time.time()) if sekarang is None else int(sekarang)),
                )
                for tabel, wajib in _KOLOM_WAJIB.items():
                    aktual = {
                        str(baris[1])
                        for baris in kon.execute("PRAGMA table_info(%s)" % tabel)
                    }
                    if not wajib <= aktual:
                        raise StoreBelumSiap("struktur store admin bentrok")
                if kon.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise StoreBelumSiap('foreign key migrasi admin tidak valid')
                if versi < 5:
                    kon.execute("PRAGMA user_version=5")
                kon.commit()
                kon.execute("PRAGMA foreign_keys=ON")
            except Exception:
                kon.rollback()
                raise
        # Lock sebelum membaca ulang versi: dua migrator tidak menulis DDL ganda.
        kon.execute("PRAGMA foreign_keys=ON")
        kon.execute("BEGIN IMMEDIATE")
        try:
            if kon.execute("PRAGMA user_version").fetchone()[0] == 5:
                import subscription_schema
                _jalankan_ddl(kon, subscription_schema.DDL)
                kon.execute("INSERT INTO langganan_aturan VALUES(?,30,3,10000,5000,25000,10000,'belum_ditetapkan')",
                            ("langganan-v1",))
                kon.execute("PRAGMA user_version=6")
            if kon.execute("PRAGMA user_version").fetchone()[0] == 6:
                import admin_launch_schema
                _jalankan_ddl(kon, admin_launch_schema.DDL)
                kon.execute(
                    "INSERT INTO pembayaran_konfigurasi VALUES(1,'nonaktif',1,?,?)",
                    (int(time.time()) if sekarang is None else int(sekarang), "sistem_migrasi"),
                )
                kon.execute("PRAGMA user_version=7")
            _validasi_skema(kon)
            kon.commit()
        except Exception:
            kon.rollback()
            raise
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StoreBelumSiap("foreign key store admin tidak valid")
    except sqlite3.Error as galat:
        raise StoreBelumSiap("gagal menyiapkan store admin") from galat
    finally:
        kon.close()
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass


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


def baca_operasi(path, operasi_id: str) -> Optional[HasilOperasi]:
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
) -> ReservasiOperasi:
    """Reservasi idempoten; transaksi berakhir sebelum domain auth dikunci."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    sidik = sidik_perintah(perintah)
    with _transaksi(path) as kon:
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
) -> HasilOperasi:
    if not receipt_cocok(receipt, perintah):
        raise KonflikOperasi("receipt tidak cocok dengan journal")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
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
) -> HasilOperasi:
    if status not in ("failed_before_commit", "conflict", "uncertain", "cancelled"):
        raise DataAuditTidakSah("status gagal tidak diizinkan")
    if hasil_kode not in (
        "target_changed", "input_rejected", "domain_not_committed", "domain_uncertain"
    ):
        raise DataAuditTidakSah("kode gagal tidak diizinkan")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
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


def baca_konfigurasi(path=None) -> KonfigurasiPendaftaran:
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
) -> HasilOperasi:
    """Update konfigurasi+journal+audit dalam satu transaksi."""
    sidik = _sidik_config(
        operasi_id, actor_id, revisi, dibuka, pesan_kode, token_tinjauan
    )
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
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
    path=None, *, sekarang: Optional[int] = None, batas_baris: int = 500
) -> int:
    """Hapus audit >180 hari secara bounded; journal/receipt tidak ikut."""
    if type(batas_baris) is not int or not 1 <= batas_baris <= 10_000:
        raise DataAuditTidakSah("batas purge audit tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    batas = kini - RETENSI_AUDIT_HARI * 86400
    with _transaksi(path) as kon:
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


@dataclass(frozen=True)
class BatchDurable:
    batch_id: str
    actor_id: str
    actor_revisi: int
    aksi: str
    target_peran: str
    jumlah_total: int
    status: str
    kelompok_aktif_id: Optional[str]
    dibuat: int
    diperbarui: int


@dataclass(frozen=True)
class ItemBatchDurable:
    batch_id: str
    item_id: str
    urutan: int
    operasi_id: str
    target_id: str
    target_revisi: int
    status: str
    hasil_id: Optional[str]
    credential_status: str
    diperbarui: int


@dataclass(frozen=True)
class KelompokBatchDurable:
    kelompok_id: str
    status: str
    dibuat: int
    diperbarui: int
    item_ids: Tuple[str, ...]


@dataclass(frozen=True)
class PenyerahanBatchDurable:
    operasi_id: str
    actor_id: str
    actor_revisi: int
    jumlah: int
    dibuat: int
    item_ids: Tuple[str, ...]


@dataclass(frozen=True)
class SnapshotBatchDurable:
    batch: BatchDurable
    item: Tuple[ItemBatchDurable, ...]
    kelompok: Tuple[KelompokBatchDurable, ...] = ()
    penyerahan: Tuple[PenyerahanBatchDurable, ...] = ()


@dataclass(frozen=True)
class RingkasanBatchDurable:
    batch_id: str
    actor_id: str
    actor_revisi: int
    aksi: str
    target_peran: str
    jumlah_total: int
    status: str
    jumlah_status: Tuple[Tuple[str, int], ...]
    kelompok_aktif_id: Optional[str]
    dibuat: int
    diperbarui: int


@dataclass(frozen=True)
class HalamanBatchDurable:
    item: Tuple[RingkasanBatchDurable, ...]
    total: int
    halaman: int
    per_halaman: int
    jumlah_halaman: int


def _batch_durable_dari_baris(row) -> BatchDurable:
    # Session hash tetap disimpan sebagai fence operasional, tetapi sengaja
    # tidak diproyeksikan ke DTO audit.
    return BatchDurable(
        row["batch_id"], row["actor_id"], int(row["actor_revisi"]),
        row["aksi"], row["target_peran"], int(row["jumlah_total"]),
        row["status"], row["kelompok_aktif_id"], int(row["dibuat"]),
        int(row["diperbarui"]),
    )


def _item_batch_durable_dari_baris(row) -> ItemBatchDurable:
    return ItemBatchDurable(
        row["batch_id"], row["item_id"], int(row["urutan"]),
        row["operasi_id"], row["target_id"], int(row["target_revisi"]),
        row["status"], row["hasil_id"], row["credential_status"],
        int(row["diperbarui"]),
    )


def _validasi_identitas_batch(
    batch_id, actor_id, actor_revisi, session_hash, aksi, target_peran, item
):
    validasi_id(batch_id, "batch_id")
    validasi_id(actor_id, "actor_id")
    validasi_revisi(actor_revisi, "actor_revisi")
    validasi_sidik(session_hash)
    if aksi not in ("account_teacher_create", "account_password_reset", "account_session_revoke"):
        raise DataAuditTidakSah("aksi batch tidak sah")
    if target_peran not in ("guru", "murid"):
        raise DataAuditTidakSah("peran batch tidak sah")
    if type(item) is not tuple or not 1 <= len(item) <= 100:
        raise DataAuditTidakSah("item batch tidak sah")
    terlihat = set()
    for data in item:
        if type(data) is not tuple or len(data) != 4:
            raise DataAuditTidakSah("item batch tidak sah")
        validasi_id(data[0], "item_id")
        validasi_id(data[1], "operasi_id")
        validasi_id(data[2], "target_id")
        validasi_revisi(data[3], "target_revisi")
        for nilai in data[:3]:
            if nilai in terlihat:
                raise DataAuditTidakSah("ID batch duplikat")
            terlihat.add(nilai)


def _snapshot_batch_durable_kon(kon, batch_id):
    row = kon.execute(
        "SELECT * FROM batch_admin WHERE batch_id=?", (batch_id,)
    ).fetchone()
    if row is None:
        return None
    items = kon.execute(
        "SELECT * FROM batch_admin_item WHERE batch_id=? ORDER BY urutan",
        (batch_id,),
    ).fetchall()
    groups = kon.execute(
        "SELECT * FROM kelompok_admin WHERE batch_id=? ORDER BY dibuat,kelompok_id",
        (batch_id,),
    ).fetchall()
    handovers = kon.execute(
        "SELECT * FROM penyerahan_admin WHERE batch_id=? ORDER BY dibuat,operasi_id",
        (batch_id,),
    ).fetchall()
    kelompok = tuple(
        KelompokBatchDurable(
            data["kelompok_id"], data["status"], int(data["dibuat"]),
            int(data["diperbarui"]), tuple(row_item[0] for row_item in kon.execute(
                """SELECT item_id FROM kelompok_admin_item
                   WHERE kelompok_id=? ORDER BY urutan""",
                (data["kelompok_id"],),
            )),
        )
        for data in groups
    )
    penyerahan = tuple(
        PenyerahanBatchDurable(
            data["operasi_id"], data["actor_id"], int(data["actor_revisi"]),
            int(data["jumlah"]), int(data["dibuat"]),
            tuple(row_item[0] for row_item in kon.execute(
                """SELECT item_id FROM penyerahan_admin_item
                   WHERE operasi_id=? ORDER BY item_id""",
                (data["operasi_id"],),
            )),
        )
        for data in handovers
    )
    return SnapshotBatchDurable(
        _batch_durable_dari_baris(row),
        tuple(_item_batch_durable_dari_baris(data) for data in items),
        kelompok, penyerahan,
    )


def _buat_batch_durable_kon(
    kon, *, batch_id, actor_id, actor_revisi, session_hash, aksi,
    target_peran, item, sekarang,
) -> SnapshotBatchDurable:
    _validasi_identitas_batch(
        batch_id, actor_id, actor_revisi, session_hash, aksi, target_peran, item
    )
    lama = kon.execute(
        "SELECT * FROM batch_admin WHERE batch_id=?", (batch_id,)
    ).fetchone()
    if lama is None:
        kon.execute(
            """INSERT INTO batch_admin VALUES(
                   ?,?,?,?,?,?,?,'ready',NULL,?,?)""",
            (batch_id, actor_id, actor_revisi, session_hash, aksi,
             target_peran, len(item), sekarang, sekarang),
        )
        kon.executemany(
            """INSERT INTO batch_admin_item VALUES(
                   ?,?,?,?,?,?,'pending',NULL,'not_applicable',?)""",
            [(batch_id, data[0], urutan, data[1], data[2], data[3], sekarang)
             for urutan, data in enumerate(item)],
        )
    else:
        identitas = (
            lama["actor_id"], int(lama["actor_revisi"]), lama["session_hash"],
            lama["aksi"], lama["target_peran"], int(lama["jumlah_total"]),
        )
        if identitas != (
            actor_id, actor_revisi, session_hash, aksi, target_peran, len(item)
        ):
            raise KonflikOperasi("batch ID dipakai identitas berbeda")
        aktual = [tuple(row) for row in kon.execute(
            """SELECT item_id,operasi_id,target_id,target_revisi
               FROM batch_admin_item WHERE batch_id=? ORDER BY urutan""",
            (batch_id,),
        )]
        if aktual != list(item):
            raise KonflikOperasi("item batch durable berbeda")
    return _snapshot_batch_durable_kon(kon, batch_id)


def buat_batch_durable(
    path, *, batch_id, actor_id, actor_revisi, session_hash, aksi,
    target_peran, item, sekarang=None,
) -> SnapshotBatchDurable:
    """Buat identitas batch/item tanpa alias atau secret pada store durable."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        return _buat_batch_durable_kon(
            kon, batch_id=batch_id, actor_id=actor_id,
            actor_revisi=actor_revisi, session_hash=session_hash, aksi=aksi,
            target_peran=target_peran, item=item, sekarang=kini,
        )


def baca_batch_durable(path, batch_id) -> Optional[SnapshotBatchDurable]:
    """Reader audit detail; sengaja tidak memerlukan session operasional."""
    validasi_id(batch_id, "batch_id")
    with buka_baca(path) as kon:
        return _snapshot_batch_durable_kon(kon, batch_id)


def baca_batch_operasional_durable(
    path, batch_id, *, actor_id, actor_revisi, session_hash,
) -> Optional[SnapshotBatchDurable]:
    """Reader fenced untuk workflow aktif tanpa mengekspos hash pada DTO."""
    validasi_id(batch_id, "batch_id")
    validasi_id(actor_id, "actor_id")
    validasi_revisi(actor_revisi, "actor_revisi")
    validasi_sidik(session_hash)
    with buka_baca(path) as kon:
        cocok = kon.execute(
            """SELECT 1 FROM batch_admin
               WHERE batch_id=? AND actor_id=? AND actor_revisi=?
                 AND session_hash=?""",
            (batch_id, actor_id, actor_revisi, session_hash),
        ).fetchone()
        if cocok is None:
            return None
        return _snapshot_batch_durable_kon(kon, batch_id)


def daftar_batch_durable(
    path, *, actor_id="", aksi="", status="", mulai=None, selesai=None,
    halaman=1, per_halaman=25,
) -> HalamanBatchDurable:
    """Reader audit batch paginated tanpa alias, secret, atau raw token."""
    if actor_id:
        validasi_id(actor_id, "actor_id")
    if aksi and aksi not in (
        "account_teacher_create", "account_password_reset", "account_session_revoke"
    ):
        raise DataAuditTidakSah("filter aksi batch tidak sah")
    if status and status not in (
        "ready", "running", "partial", "stopped", "succeeded", "attention"
    ):
        raise DataAuditTidakSah("filter status batch tidak sah")
    if type(halaman) is not int or halaman < 1:
        raise DataAuditTidakSah("halaman batch tidak sah")
    if type(per_halaman) is not int or not 1 <= per_halaman <= 100:
        raise DataAuditTidakSah("per_halaman batch tidak sah")
    for nilai, label in ((mulai, "mulai"), (selesai, "selesai")):
        if nilai is not None and (type(nilai) is not int or nilai < 0):
            raise DataAuditTidakSah("filter %s batch tidak sah" % label)
    if mulai is not None and selesai is not None and mulai > selesai:
        raise DataAuditTidakSah("rentang batch tidak sah")
    klausa, argumen = [], []
    for nama, nilai in (("actor_id", actor_id), ("aksi", aksi), ("status", status)):
        if nilai:
            klausa.append(nama + "=?")
            argumen.append(nilai)
    if mulai is not None:
        klausa.append("dibuat>=?"); argumen.append(mulai)
    if selesai is not None:
        klausa.append("dibuat<=?"); argumen.append(selesai)
    where = " WHERE " + " AND ".join(klausa) if klausa else ""
    with buka_baca(path) as kon:
        total = int(kon.execute(
            "SELECT COUNT(*) FROM batch_admin" + where, tuple(argumen)
        ).fetchone()[0])
        rows = kon.execute(
            "SELECT * FROM batch_admin" + where
            + " ORDER BY dibuat DESC,batch_id DESC LIMIT ? OFFSET ?",
            tuple(argumen) + (per_halaman, (halaman - 1) * per_halaman),
        ).fetchall()
        hasil = []
        for row in rows:
            counts = tuple(
                (data["status"], int(data["jumlah"]))
                for data in kon.execute(
                    """SELECT status,COUNT(*) AS jumlah FROM batch_admin_item
                       WHERE batch_id=? GROUP BY status ORDER BY status""",
                    (row["batch_id"],),
                )
            )
            hasil.append(RingkasanBatchDurable(
                row["batch_id"], row["actor_id"], int(row["actor_revisi"]),
                row["aksi"], row["target_peran"], int(row["jumlah_total"]),
                row["status"], counts, row["kelompok_aktif_id"],
                int(row["dibuat"]), int(row["diperbarui"]),
            ))
    jumlah_halaman = max(1, (total + per_halaman - 1) // per_halaman)
    return HalamanBatchDurable(
        tuple(hasil), total, halaman, per_halaman, jumlah_halaman
    )


def buat_batch_durable_dengan_guard(
    path, *, batch_id, actor_id, actor_revisi, session_hash, aksi,
    target_peran, item, sekarang, guard, setelah=None,
) -> SnapshotBatchDurable:
    """Commit durable lalu callback rekonsiliasi sambil guard tetap dipegang.

    Callback menerima ``(dibuat_baru, snapshot)``. Commit lintas dua SQLite
    tidak disebut atomik: durable selalu authoritative, sedangkan callback
    hanya membawa transient menuju state yang sama.
    """
    with guard:
        with _transaksi(path) as kon:
            dibuat_baru = kon.execute(
                "SELECT 1 FROM batch_admin WHERE batch_id=?", (batch_id,)
            ).fetchone() is None
            hasil = _buat_batch_durable_kon(
                kon, batch_id=batch_id, actor_id=actor_id,
                actor_revisi=actor_revisi, session_hash=session_hash, aksi=aksi,
                target_peran=target_peran, item=item, sekarang=sekarang,
            )
        if setelah is not None:
            setelah(dibuat_baru, hasil)
        return hasil


def mulai_kelompok_durable(
    path, *, batch_id, kelompok_id, item_ids, sekarang=None
) -> Tuple[ItemBatchDurable, ...]:
    validasi_id(batch_id, "batch_id")
    validasi_id(kelompok_id, "kelompok_id")
    if type(item_ids) is not tuple or not 1 <= len(item_ids) <= 10:
        raise DataAuditTidakSah("item kelompok tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        batch = kon.execute(
            "SELECT * FROM batch_admin WHERE batch_id=?", (batch_id,)
        ).fetchone()
        if batch is None:
            raise KonflikOperasi("batch durable tidak tersedia")
        lama = kon.execute(
            "SELECT * FROM kelompok_admin WHERE kelompok_id=?", (kelompok_id,)
        ).fetchone()
        if lama is not None:
            if lama["batch_id"] != batch_id:
                raise KonflikOperasi("kelompok ID dipakai batch berbeda")
            rows = kon.execute(
                """SELECT i.* FROM kelompok_admin_item k JOIN batch_admin_item i
                   ON i.batch_id=k.batch_id AND i.item_id=k.item_id
                   WHERE k.kelompok_id=? ORDER BY k.urutan""", (kelompok_id,),
            ).fetchall()
            if tuple(row["item_id"] for row in rows) != item_ids:
                raise KonflikOperasi("item kelompok durable berbeda")
            return tuple(_item_batch_durable_dari_baris(row) for row in rows)
        if batch["kelompok_aktif_id"] is not None:
            raise KonflikOperasi("batch memiliki kelompok aktif")
        if batch["status"] not in ("ready", "partial"):
            raise KonflikOperasi("batch durable tidak menerima kelompok baru")
        rows = []
        for item_id in item_ids:
            validasi_id(item_id, "item_id")
            row = kon.execute(
                "SELECT * FROM batch_admin_item WHERE batch_id=? AND item_id=?",
                (batch_id, item_id),
            ).fetchone()
            if row is None or row["status"] != "pending":
                raise KonflikOperasi("item kelompok berubah")
            rows.append(row)
        if len({row["item_id"] for row in rows}) != len(rows):
            raise DataAuditTidakSah("item kelompok duplikat")
        kon.execute(
            "INSERT INTO kelompok_admin VALUES(?,?,'running',?,?)",
            (kelompok_id, batch_id, kini, kini),
        )
        kon.executemany(
            "INSERT INTO kelompok_admin_item VALUES(?,?,?,?)",
            [(kelompok_id, batch_id, row["item_id"], nomor)
             for nomor, row in enumerate(rows)],
        )
        kon.execute(
            """UPDATE batch_admin SET status='running',kelompok_aktif_id=?,
                   diperbarui=? WHERE batch_id=?""",
            (kelompok_id, kini, batch_id),
        )
        return tuple(_item_batch_durable_dari_baris(row) for row in rows)


def mulai_kelompok_durable_dengan_guard(
    path, *, batch_id, kelompok_id, item_ids, sekarang, guard, setelah=None,
) -> Tuple[ItemBatchDurable, ...]:
    """Commit fencing kelompok lalu rekonsiliasi transient di bawah guard."""
    with guard:
        hasil = mulai_kelompok_durable(
            path, batch_id=batch_id, kelompok_id=kelompok_id,
            item_ids=item_ids, sekarang=sekarang,
        )
        if setelah is not None:
            setelah(hasil)
        return hasil


def catat_item_batch_durable(
    path, *, batch_id, item_id, status, hasil_id, credential_status,
    sekarang=None, setelah=None,
) -> None:
    if status not in (
        "succeeded", "failed_before_commit", "conflict", "uncertain", "cancelled"
    ):
        raise DataAuditTidakSah("status item batch tidak sah")
    if credential_status not in ("not_applicable", "unconfirmed", "confirmed"):
        raise DataAuditTidakSah("status credential batch tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        kursor = kon.execute(
            """UPDATE batch_admin_item SET status=?,hasil_id=?,credential_status=?,
                   diperbarui=? WHERE batch_id=? AND item_id=? AND status='pending'""",
            (status, hasil_id, credential_status, kini, batch_id, item_id),
        )
        if kursor.rowcount != 1:
            lama = kon.execute(
                "SELECT status,hasil_id,credential_status FROM batch_admin_item WHERE batch_id=? AND item_id=?",
                (batch_id, item_id),
            ).fetchone()
            if lama is None or tuple(lama) != (status, hasil_id, credential_status):
                raise KonflikOperasi("hasil item batch berbeda")
    if setelah is not None:
        setelah()


def selesaikan_kelompok_durable(
    path, *, batch_id, kelompok_id, status, sekarang=None
) -> None:
    if status not in ("completed", "attention"):
        raise DataAuditTidakSah("status kelompok tidak sah")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        row = kon.execute(
            "SELECT batch_id,status FROM kelompok_admin WHERE kelompok_id=?",
            (kelompok_id,),
        ).fetchone()
        if row is None or row["batch_id"] != batch_id:
            raise KonflikOperasi("kelompok durable tidak tersedia")
        if row["status"] not in ("running", status):
            raise KonflikOperasi("status kelompok durable berbeda")
        statuses = [data[0] for data in kon.execute(
            "SELECT status FROM batch_admin_item WHERE batch_id=?", (batch_id,)
        )]
        batch_status = (
            "attention" if "uncertain" in statuses
            else "partial" if "pending" in statuses
            else "succeeded" if statuses and all(x == "succeeded" for x in statuses)
            else "partial"
        )
        kon.execute(
            "UPDATE kelompok_admin SET status=?,diperbarui=? WHERE kelompok_id=?",
            (status, kini, kelompok_id),
        )
        kon.execute(
            """UPDATE batch_admin SET status=?,kelompok_aktif_id=NULL,diperbarui=?
               WHERE batch_id=? AND kelompok_aktif_id=?""",
            (batch_status, kini, batch_id, kelompok_id),
        )


def _hentikan_batch_durable_kon(kon, *, batch_id, sekarang) -> None:
    row = kon.execute(
        "SELECT kelompok_aktif_id FROM batch_admin WHERE batch_id=?",
        (batch_id,),
    ).fetchone()
    if row is None:
        raise KonflikOperasi("batch durable tidak tersedia")
    if row["kelompok_aktif_id"] is not None:
        raise KonflikOperasi("kelompok masih aktif")
    kon.execute(
        "UPDATE batch_admin_item SET status='cancelled',diperbarui=? WHERE batch_id=? AND status='pending'",
        (sekarang, batch_id),
    )
    kon.execute(
        "UPDATE batch_admin SET status='stopped',diperbarui=? WHERE batch_id=?",
        (sekarang, batch_id),
    )


def batalkan_batch_aktif_durable(path, *, batch_id, sekarang=None) -> None:
    """Tahan sisa batch setelah sesi mati; sukses lama tetap tercatat."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        row = kon.execute(
            "SELECT kelompok_aktif_id FROM batch_admin WHERE batch_id=?",
            (batch_id,),
        ).fetchone()
        if row is None:
            raise KonflikOperasi("batch durable tidak tersedia")
        kon.execute(
            "UPDATE batch_admin_item SET status='cancelled',diperbarui=? WHERE batch_id=? AND status='pending'",
            (kini, batch_id),
        )
        if row["kelompok_aktif_id"] is not None:
            kon.execute(
                """UPDATE kelompok_admin SET status='completed',diperbarui=?
                   WHERE kelompok_id=? AND status='running'""",
                (kini, row["kelompok_aktif_id"]),
            )
        kon.execute(
            """UPDATE batch_admin SET status='stopped',kelompok_aktif_id=NULL,
                   diperbarui=? WHERE batch_id=?""",
            (kini, batch_id),
        )


def hentikan_batch_durable(path, *, batch_id, sekarang=None) -> None:
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        _hentikan_batch_durable_kon(kon, batch_id=batch_id, sekarang=kini)


def hentikan_batch_durable_dengan_guard(
    path, *, batch_id, sekarang, guard, setelah=None,
) -> None:
    with guard:
        with _transaksi(path) as kon:
            _hentikan_batch_durable_kon(
                kon, batch_id=batch_id, sekarang=sekarang
            )
        if setelah is not None:
            setelah()


def _konfirmasi_penyerahan_durable_kon(
    kon, *, operasi_id, batch_id, actor_id, actor_revisi, item_ids, sekarang,
) -> None:
    validasi_id(operasi_id, "operasi_id")
    validasi_id(actor_id, "actor_id")
    validasi_revisi(actor_revisi, "actor_revisi")
    if type(item_ids) is not tuple or not 1 <= len(item_ids) <= 100:
        raise DataAuditTidakSah("item penyerahan tidak sah")
    daftar = tuple(sorted(item_ids))
    if len(set(daftar)) != len(daftar):
        raise DataAuditTidakSah("item penyerahan duplikat")
    for item_id in daftar:
        validasi_id(item_id, "item_id")
    sidik = hashlib.sha256("\0".join(daftar).encode("ascii")).hexdigest()
    batch = kon.execute(
        "SELECT actor_id,actor_revisi FROM batch_admin WHERE batch_id=?",
        (batch_id,),
    ).fetchone()
    if batch is None or (
        batch["actor_id"], int(batch["actor_revisi"])
    ) != (actor_id, actor_revisi):
        raise KonflikOperasi("batch durable berubah")
    lama = kon.execute(
        "SELECT * FROM penyerahan_admin WHERE operasi_id=?", (operasi_id,)
    ).fetchone()
    if lama is not None:
        if (
            lama["batch_id"], lama["actor_id"], int(lama["actor_revisi"]),
            lama["sidik_item"], int(lama["jumlah"]),
        ) != (batch_id, actor_id, actor_revisi, sidik, len(daftar)):
            raise KonflikOperasi("operasi penyerahan berbeda")
        return
    placeholder = ",".join("?" for _ in daftar)
    rows = kon.execute(
        """SELECT item_id,status,credential_status FROM batch_admin_item
           WHERE batch_id=? AND item_id IN (%s)""" % placeholder,
        (batch_id, *daftar),
    ).fetchall()
    if len(rows) != len(daftar) or any(
        row["status"] != "succeeded"
        or row["credential_status"] not in ("unconfirmed", "confirmed")
        for row in rows
    ):
        raise KonflikOperasi("item penyerahan berubah")
    kon.execute(
        "INSERT INTO penyerahan_admin VALUES(?,?,?,?,?,?,?)",
        (operasi_id, batch_id, actor_id, actor_revisi, sidik, len(daftar), sekarang),
    )
    kon.executemany(
        "INSERT INTO penyerahan_admin_item VALUES(?,?,?)",
        [(operasi_id, batch_id, item_id) for item_id in daftar],
    )
    kon.execute(
        """UPDATE batch_admin_item SET credential_status='confirmed',diperbarui=?
           WHERE batch_id=? AND item_id IN (%s)""" % placeholder,
        (sekarang, batch_id, *daftar),
    )


def konfirmasi_penyerahan_durable(
    path, *, operasi_id, batch_id, actor_id, actor_revisi, item_ids,
    sekarang=None,
) -> None:
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with _transaksi(path) as kon:
        _konfirmasi_penyerahan_durable_kon(
            kon, operasi_id=operasi_id, batch_id=batch_id,
            actor_id=actor_id, actor_revisi=actor_revisi,
            item_ids=item_ids, sekarang=kini,
        )


def konfirmasi_penyerahan_durable_dengan_guard(
    path, *, operasi_id, batch_id, actor_id, actor_revisi, item_ids,
    sekarang, guard, setelah=None,
) -> None:
    with guard:
        with _transaksi(path) as kon:
            _konfirmasi_penyerahan_durable_kon(
                kon, operasi_id=operasi_id, batch_id=batch_id,
                actor_id=actor_id, actor_revisi=actor_revisi,
                item_ids=item_ids, sekarang=sekarang,
            )
        if setelah is not None:
            setelah()


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

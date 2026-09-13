"""Batch akun: alias transient, metadata/receipt durable, sesi hidup per aksi."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import csv
import fcntl
import hashlib
import io
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import threading
import time
from typing import Optional, Sequence, Tuple

import admin_accounts
from admin_contracts import (
    AKSI_BUAT_GURU,
    AKSI_CABUT_SESI,
    AKSI_RESET_SANDI,
    PerintahAkun,
    PerintahPembuatanAkun,
    validasi_id,
    validasi_revisi,
)
import admin_registration
import admin_service
import admin_store
import auth
import sessions


BATAS_BYTE_CSV = 64 * 1024
BATAS_ITEM = 100
BATAS_KELOMPOK = 10
TTL_DRAFT = 900
VERSI_TRANSIENT = 2


class BulkTidakSah(ValueError):
    """CSV, snapshot, atau state batch tidak memenuhi kontrak sempit."""


@dataclass(frozen=True)
class TargetBulk:
    item_id: str
    operasi_id: str
    target_id: str
    target_revisi: int
    target_peran: str
    alias: Optional[str] = field(default=None, repr=False)


@dataclass(frozen=True)
class HasilItemBulk:
    item_id: str
    status: str
    hasil_id: Optional[str]
    credential_sekali: Optional[str] = field(default=None, repr=False)


@dataclass(frozen=True)
class ItemBatch:
    item_id: str
    operasi_id: str
    target_id: str
    target_revisi: int
    alias_valid: Optional[str] = field(default=None, repr=False)
    status: str = "pending"
    hasil_id: Optional[str] = None
    credential_status: str = "not_applicable"


@dataclass(frozen=True)
class Batch:
    batch_id: str
    aksi: str
    target_peran: str
    status: str
    item: Tuple[ItemBatch, ...]
    draft_tersedia: bool
    boleh_proses: bool
    kelompok_aktif_id: Optional[str]


_DDL_TRANSIENT = """
CREATE TABLE IF NOT EXISTS draft_bulk (
    batch_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    session_binding TEXT NOT NULL CHECK(length(session_binding)=64),
    aksi TEXT NOT NULL,
    target_peran TEXT NOT NULL CHECK(target_peran IN ('guru','murid')),
    kedaluwarsa INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ready','running','partial','stopped','succeeded','attention')),
    preflight_selesai INTEGER NOT NULL DEFAULT 0 CHECK(preflight_selesai IN (0,1)),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS item_bulk (
    batch_id TEXT NOT NULL REFERENCES draft_bulk(batch_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    operasi_id TEXT NOT NULL UNIQUE,
    target_id TEXT NOT NULL,
    target_revisi INTEGER NOT NULL CHECK(target_revisi>=0),
    alias_valid TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'
    )),
    hasil_id TEXT,
    credential_status TEXT NOT NULL DEFAULT 'not_applicable'
        CHECK(credential_status IN ('not_applicable','unconfirmed','confirmed')),
    PRIMARY KEY(batch_id,item_id),
    UNIQUE(batch_id,target_id)
);
CREATE TABLE IF NOT EXISTS kelompok_bulk (
    kelompok_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES draft_bulk(batch_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('running','completed','attention')),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kelompok_bulk_item (
    kelompok_id TEXT NOT NULL REFERENCES kelompok_bulk(kelompok_id) ON DELETE CASCADE,
    batch_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    PRIMARY KEY(kelompok_id,item_id),
    FOREIGN KEY(batch_id,item_id) REFERENCES item_bulk(batch_id,item_id) ON DELETE CASCADE
);
"""


class _State:
    def __init__(self):
        self.thread = threading.RLock()
        self.local = threading.local()


_REGISTRY_GUARD = threading.Lock()
_REGISTRY = {}


def _uri(path: Path, mode: str) -> str:
    return path.resolve().as_uri() + "?mode=" + mode


def siapkan_transient(path) -> None:
    tujuan = Path(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kon = sqlite3.connect(str(tujuan), timeout=5.0)
    try:
        versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
        if versi > VERSI_TRANSIENT:
            raise BulkTidakSah("skema draft lebih baru")
        kon.execute("PRAGMA foreign_keys=OFF" if versi == 1 else "PRAGMA foreign_keys=ON")
        if versi == 1:
            kon.execute("BEGIN IMMEDIATE")
            kon.execute(
                "ALTER TABLE draft_bulk ADD COLUMN preflight_selesai INTEGER NOT NULL DEFAULT 0 CHECK(preflight_selesai IN (0,1))"
            )
            kon.execute("ALTER TABLE item_bulk RENAME TO item_bulk_v1")
            kon.execute(
                """CREATE TABLE item_bulk (
                    batch_id TEXT NOT NULL REFERENCES draft_bulk(batch_id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL,
                    urutan INTEGER NOT NULL,
                    operasi_id TEXT NOT NULL UNIQUE,
                    target_id TEXT NOT NULL,
                    target_revisi INTEGER NOT NULL CHECK(target_revisi>=0),
                    alias_valid TEXT,
                    status TEXT NOT NULL CHECK(status IN (
                        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'
                    )),
                    hasil_id TEXT,
                    credential_status TEXT NOT NULL DEFAULT 'not_applicable'
                        CHECK(credential_status IN ('not_applicable','unconfirmed','confirmed')),
                    PRIMARY KEY(batch_id,item_id),
                    UNIQUE(batch_id,target_id)
                )"""
            )
            kon.execute(
                """INSERT INTO item_bulk(
                       batch_id,item_id,urutan,operasi_id,target_id,target_revisi,
                       alias_valid,status,hasil_id,credential_status)
                   SELECT batch_id,item_id,urutan,operasi_id,target_id,target_revisi,
                          alias_valid,status,NULL,
                          CASE WHEN status='succeeded' AND EXISTS(
                              SELECT 1 FROM draft_bulk d
                              WHERE d.batch_id=item_bulk_v1.batch_id
                                AND d.aksi IN ('account_teacher_create','account_password_reset')
                          ) THEN 'unconfirmed' ELSE 'not_applicable' END
                   FROM item_bulk_v1"""
            )
            kon.execute("DROP TABLE item_bulk_v1")
            kon.execute("PRAGMA user_version=2")
            kon.commit()
            kon.execute("PRAGMA foreign_keys=ON")
        kon.executescript(_DDL_TRANSIENT)
        kon.execute("PRAGMA user_version=2")
        kon.commit()
        if kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BulkTidakSah("integritas store transient gagal")
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BulkTidakSah("foreign key store transient gagal")
    except Exception:
        if kon.in_transaction:
            kon.rollback()
        raise
    finally:
        kon.close()
    tujuan.chmod(0o600)


@contextmanager
def _transaksi(path):
    try:
        kon = sqlite3.connect(_uri(Path(path), "rw"), uri=True, timeout=5.0)
    except sqlite3.Error as galat:
        raise BulkTidakSah("store transient tidak tersedia") from galat
    kon.row_factory = sqlite3.Row
    try:
        kon.execute("PRAGMA foreign_keys=ON")
        if int(kon.execute("PRAGMA user_version").fetchone()[0]) != VERSI_TRANSIENT:
            raise BulkTidakSah("store transient belum siap")
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()


def _buka_baca_transient(path):
    try:
        kon = sqlite3.connect(_uri(Path(path), "ro"), uri=True, timeout=5.0)
    except sqlite3.Error:
        return None
    kon.row_factory = sqlite3.Row
    try:
        if int(kon.execute("PRAGMA user_version").fetchone()[0]) != VERSI_TRANSIENT:
            kon.close()
            return None
    except sqlite3.Error:
        kon.close()
        return None
    return kon


def _path_lock(path_transient, batch_id):
    sidik = hashlib.sha256(batch_id.encode()).hexdigest()
    return Path(path_transient).resolve().parent / (".admin-batch-%s.lock" % sidik)


@contextmanager
def kunci_batch(path_transient, batch_id):
    path = _path_lock(path_transient, batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _REGISTRY_GUARD:
        state = _REGISTRY.setdefault(str(path), _State())
    with state.thread:
        depth = getattr(state.local, "depth", 0)
        if depth == 0:
            try:
                info_path = path.lstat()
            except FileNotFoundError:
                info_path = None
            if info_path is not None and not stat.S_ISREG(info_path.st_mode):
                raise BulkTidakSah("lock batch tidak aman")
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(str(path), flags, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise BulkTidakSah("lock batch tidak aman")
                fcntl.flock(fd, fcntl.LOCK_EX)
                os.fchmod(fd, 0o600)
            except Exception:
                os.close(fd)
                raise
            state.local.fd = fd
        state.local.depth = depth + 1
        try:
            yield
        finally:
            state.local.depth -= 1
            if state.local.depth == 0:
                fd = state.local.fd
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
                    del state.local.fd
                    del state.local.depth


def parse_csv_alias(data: bytes) -> Tuple[str, ...]:
    if type(data) is not bytes or not 0 < len(data) <= BATAS_BYTE_CSV:
        raise BulkTidakSah("ukuran CSV tidak sah")
    if b"\x00" in data:
        raise BulkTidakSah("CSV memuat NUL")
    try:
        teks = data.decode("utf-8-sig", "strict")
        baris = list(csv.reader(io.StringIO(teks, newline=""), strict=True))
    except (UnicodeError, csv.Error) as galat:
        raise BulkTidakSah("format/encoding CSV tidak sah") from galat
    if not baris or baris[0] != ["pengguna"]:
        raise BulkTidakSah("header CSV harus tepat pengguna")
    isi = baris[1:]
    if not 1 <= len(isi) <= BATAS_ITEM:
        raise BulkTidakSah("jumlah baris CSV harus 1..100")
    hasil = []
    terlihat = set()
    for nomor, kolom in enumerate(isi, start=2):
        if len(kolom) != 1:
            raise BulkTidakSah("kolom asing pada baris %d" % nomor)
        try:
            alias = admin_accounts.validasi_alias(kolom[0])
        except ValueError as galat:
            raise BulkTidakSah("alias tidak sah pada baris %d" % nomor) from galat
        key = alias.casefold()
        if key in terlihat:
            raise BulkTidakSah("alias duplikat pada baris %d" % nomor)
        terlihat.add(key)
        hasil.append(alias)
    return tuple(hasil)


def _binding(token_sesi):
    if type(token_sesi) is not str or len(token_sesi) < 32:
        raise BulkTidakSah("token sesi tidak sah")
    return hashlib.sha256(token_sesi.encode()).hexdigest()


def _waktu(sekarang):
    return time.time() if sekarang is None else sekarang


def _principal_hidup_terkunci(
    path_auth, path_sesi, token_sesi, actor_id, actor_revisi, sekarang
):
    principal = sessions.ambil_principal(
        token_sesi, Path(path_sesi), sekarang=sekarang, path_akun=Path(path_auth)
    )
    if (
        principal is None or principal.metode != "cookie"
        or principal.peran != "admin" or principal.id_akun != actor_id
        or principal.revisi_auth != actor_revisi
    ):
        raise PermissionError("Sesi pengelola berubah atau berakhir.")
    return principal


def _guard_principal(path_auth, path_sesi, token_sesi, actor_id, actor_revisi, sekarang):
    @contextmanager
    def guard():
        # Lock auth→session; sama dengan issuance sesi. Guard dilepas segera
        # setelah admission/commit metadata, bukan ditahan untuk seluruh batch.
        from json_storage import transaksi_json

        with transaksi_json(Path(path_auth)):
            with transaksi_json(Path(path_sesi)):
                _principal_hidup_terkunci(
                    path_auth, path_sesi, token_sesi,
                    actor_id, actor_revisi, sekarang,
                )
                yield
    return guard()


def _principal_hidup(path_auth, path_sesi, token_sesi, actor_id, actor_revisi, sekarang):
    with _guard_principal(
        path_auth, path_sesi, token_sesi, actor_id, actor_revisi, sekarang
    ):
        return None


def _item_tuple(target):
    return tuple(
        (item.item_id, item.operasi_id, item.target_id, item.target_revisi)
        for item in target
    )


def _cocok_batch_durable(
    path_admin, batch_id, actor_id, actor_revisi, session_hash,
):
    return admin_store.baca_batch_operasional_durable(
        path_admin, batch_id, actor_id=actor_id,
        actor_revisi=actor_revisi, session_hash=session_hash,
    )


def _upsert_transient_batch(
    path_transient, *, batch_id, actor_id, actor_revisi, session_hash,
    aksi, target_peran, target, kini,
):
    """Rekonsiliasi draft create; tidak menimpa alias dari draft lama."""
    with _transaksi(path_transient) as kon:
        lama = kon.execute(
            "SELECT * FROM draft_bulk WHERE batch_id=?", (batch_id,)
        ).fetchone()
        if lama is not None:
            if (
                lama["actor_id"], int(lama["actor_revisi"]),
                lama["session_binding"], lama["aksi"], lama["target_peran"],
            ) != (actor_id, actor_revisi, session_hash, aksi, target_peran):
                raise BulkTidakSah("batch transient berbeda")
            aktual = [tuple(row) for row in kon.execute(
                """SELECT item_id,operasi_id,target_id,target_revisi,alias_valid
                   FROM item_bulk WHERE batch_id=? ORDER BY urutan""",
                (batch_id,),
            )]
            harapan = [
                (x.item_id, x.operasi_id, x.target_id, x.target_revisi, x.alias)
                for x in target
            ]
            if aktual != harapan:
                raise BulkTidakSah("item batch transient berbeda")
            return
        kon.execute(
            """INSERT INTO draft_bulk(
                   batch_id,actor_id,actor_revisi,session_binding,aksi,target_peran,
                   kedaluwarsa,status,preflight_selesai,dibuat,diperbarui)
               VALUES(?,?,?,?,?,?,?,'ready',0,?,?)""",
            (batch_id, actor_id, actor_revisi, session_hash, aksi,
             target_peran, int(kini) + TTL_DRAFT, int(kini), int(kini)),
        )
        kon.executemany(
            """INSERT INTO item_bulk(
                   batch_id,item_id,urutan,operasi_id,target_id,target_revisi,
                   alias_valid,status,hasil_id,credential_status)
               VALUES(?,?,?,?,?,?,?,'pending',NULL,'not_applicable')""",
            [(batch_id, x.item_id, i, x.operasi_id, x.target_id,
              x.target_revisi, x.alias) for i, x in enumerate(target)],
        )


def buat_batch(path_admin, path_transient, *, path_auth, path_sesi, token_sesi,
               batch_id, actor_id, actor_revisi, aksi, target_peran,
               target: Sequence[TargetBulk], sekarang=None):
    validasi_id(batch_id, "batch_id")
    validasi_id(actor_id, "actor_id")
    validasi_revisi(actor_revisi, "actor_revisi")
    kini = _waktu(sekarang)
    _principal_hidup(
        path_auth, path_sesi, token_sesi, actor_id, actor_revisi, kini
    )
    if aksi not in (AKSI_BUAT_GURU, AKSI_RESET_SANDI, AKSI_CABUT_SESI):
        raise BulkTidakSah("aksi bulk tidak diizinkan")
    if target_peran not in ("guru", "murid") or (
        aksi == AKSI_BUAT_GURU and target_peran != "guru"
    ):
        raise BulkTidakSah("peran bulk tidak diizinkan")
    if not 1 <= len(target) <= BATAS_ITEM:
        raise BulkTidakSah("jumlah target harus 1..100")
    seen = set()
    for item in target:
        for nilai, label in (
            (item.item_id, "item_id"), (item.operasi_id, "operasi_id"),
            (item.target_id, "target_id"),
        ):
            validasi_id(nilai, label)
            if nilai in seen:
                raise BulkTidakSah("ID item bulk duplikat")
            seen.add(nilai)
        validasi_revisi(item.target_revisi, "target_revisi")
        if item.target_peran != target_peran:
            raise BulkTidakSah("peran item campur")
        if aksi == AKSI_BUAT_GURU:
            if item.alias is None:
                raise BulkTidakSah("alias create wajib")
            admin_accounts.validasi_alias(item.alias)
        elif item.alias is not None:
            raise BulkTidakSah("alias hanya untuk create")
    session_hash = _binding(token_sesi)
    def tulis_transient(_dibuat_baru, _snapshot):
        _upsert_transient_batch(
            path_transient, batch_id=batch_id, actor_id=actor_id,
            actor_revisi=actor_revisi, session_hash=session_hash, aksi=aksi,
            target_peran=target_peran, target=target, kini=kini,
        )

    # Commit durable mendahului transient. Crash di batas ini meninggalkan batch
    # durable pending/attention; retry command identik merekonsiliasi draft tanpa
    # membuat batch atau operasi baru. Dua SQLite ini sengaja bukan klaim atomik.
    admin_store.buat_batch_durable_dengan_guard(
        path_admin, batch_id=batch_id, actor_id=actor_id,
        actor_revisi=actor_revisi, session_hash=session_hash, aksi=aksi,
        target_peran=target_peran, item=_item_tuple(target), sekarang=int(kini),
        guard=_guard_principal(
            path_auth, path_sesi, token_sesi, actor_id, actor_revisi, kini
        ),
        setelah=tulis_transient,
    )


def _batch(kon, batch_id, actor_id, actor_revisi, token_sesi, sekarang):
    row = kon.execute(
        "SELECT * FROM draft_bulk WHERE batch_id=? AND actor_id=?",
        (batch_id, actor_id),
    ).fetchone()
    if (
        row is None or int(row["actor_revisi"]) != actor_revisi
        or row["session_binding"] != _binding(token_sesi)
    ):
        raise LookupError("batch tidak ditemukan")
    if int(row["kedaluwarsa"]) <= sekarang:
        raise BulkTidakSah("batch kedaluwarsa")
    return row


def _item_batch(row, alias=None) -> ItemBatch:
    def ambil(nama):
        try:
            return row[nama]
        except TypeError:
            return getattr(row, nama)

    return ItemBatch(
        ambil("item_id"), ambil("operasi_id"), ambil("target_id"),
        int(ambil("target_revisi")), alias, ambil("status"),
        ambil("hasil_id"), ambil("credential_status"),
    )


def _batch_dari_durable(snapshot, *, draft_tersedia, alias_per_item=None):
    alias_per_item = alias_per_item or {}
    item = tuple(
        _item_batch(row, alias_per_item.get(row.item_id)) for row in snapshot.item
    )
    status = snapshot.batch.status
    boleh = bool(
        draft_tersedia and status in ("ready", "partial", "running")
        and not any(
            data.status == "pending" and snapshot.batch.aksi == AKSI_BUAT_GURU
            and data.alias_valid is None for data in item
        )
    )
    if not draft_tersedia and any(data.status == "pending" for data in item):
        status = "attention"
        boleh = False
    return Batch(
        snapshot.batch.batch_id, snapshot.batch.aksi,
        snapshot.batch.target_peran, status, item, draft_tersedia, boleh,
        snapshot.batch.kelompok_aktif_id,
    )


def baca_batch(path_admin, path_transient, *, path_auth, path_sesi, token_sesi,
               batch_id, actor_id, actor_revisi, sekarang=None) -> Batch:
    """Baca operasional exact-session; fallback durable tidak punya alias."""
    validasi_id(batch_id, "batch_id")
    validasi_id(actor_id, "actor_id")
    validasi_revisi(actor_revisi, "actor_revisi")
    kini = _waktu(sekarang)
    _principal_hidup(
        path_auth, path_sesi, token_sesi, actor_id, actor_revisi, kini
    )
    durable = _cocok_batch_durable(
        path_admin, batch_id, actor_id, actor_revisi, _binding(token_sesi)
    )
    if durable is None:
        raise LookupError("batch tidak ditemukan")
    kon = _buka_baca_transient(path_transient)
    if kon is None:
        return _batch_dari_durable(durable, draft_tersedia=False)
    try:
        try:
            transient = _batch(
                kon, batch_id, actor_id, actor_revisi, token_sesi, kini
            )
        except (LookupError, BulkTidakSah):
            return _batch_dari_durable(durable, draft_tersedia=False)
        rows = kon.execute(
            "SELECT item_id,alias_valid FROM item_bulk WHERE batch_id=? ORDER BY urutan",
            (batch_id,),
        ).fetchall()
        alias = {row["item_id"]: row["alias_valid"] for row in rows}
        hasil = _batch_dari_durable(durable, draft_tersedia=True, alias_per_item=alias)
        # Durable authoritative; mismatch transient menahan aksi baru.
        if transient["aksi"] != hasil.aksi or transient["target_peran"] != hasil.target_peran:
            raise BulkTidakSah("metadata batch tidak cocok")
        return hasil
    finally:
        kon.close()


def _preflight_create_semua(path_auth, path_db, item):
    akun = auth.muat_akun(Path(path_auth))
    alias_existing = {a["pengguna"].strip().casefold() for a in akun}
    alias_batch = set()
    with admin_registration.kunci_database_pemilik(path_db) as kon:
        for row in item:
            alias = row["alias_valid"]
            key = alias.casefold()
            if (
                key in alias_batch or key in alias_existing
                or admin_registration.alias_pemilik_ada(kon, alias)
            ):
                raise BulkTidakSah("seluruh alias create harus valid sebelum eksekusi")
            alias_batch.add(key)


def _preflight_target_semua(path_auth, item, *, target_peran):
    akun = auth.muat_akun(Path(path_auth))
    per_id = {}
    for target in akun:
        per_id.setdefault(target.get("id_akun"), []).append(target)
    for row in item:
        cocok = per_id.get(row["target_id"], ())
        if (
            len(cocok) != 1
            or cocok[0].get("peran", "guru") != target_peran
            or target_peran == "admin"
            or auth.revisi_auth(cocok[0]) != int(row["target_revisi"])
        ):
            raise BulkTidakSah("seluruh target harus valid sebelum eksekusi")


def _baris_kelompok(kon, kelompok_id):
    return kon.execute(
        """SELECT i.* FROM kelompok_bulk_item k
           JOIN item_bulk i ON i.batch_id=k.batch_id AND i.item_id=k.item_id
           WHERE k.kelompok_id=? ORDER BY k.urutan""",
        (kelompok_id,),
    ).fetchall()


def _hasil_kelompok_durable(path_admin, kelompok_id):
    with admin_store.buka_baca(path_admin) as kon:
        row = kon.execute(
            "SELECT batch_id FROM kelompok_admin WHERE kelompok_id=?",
            (kelompok_id,),
        ).fetchone()
        batch_id = None if row is None else row["batch_id"]
    snapshot = (
        None if batch_id is None
        else admin_store.baca_batch_durable(path_admin, batch_id)
    )
    if snapshot is None:
        return ()
    ids = next(
        (group.item_ids for group in snapshot.kelompok
         if group.kelompok_id == kelompok_id), ()
    )
    per_id = {item.item_id: item for item in snapshot.item}
    return tuple(
        HasilItemBulk(item_id, per_id[item_id].status, per_id[item_id].hasil_id, None)
        for item_id in ids
    )


def _status_item(status):
    if status in (
        "succeeded", "failed_before_commit", "conflict", "uncertain",
        "cancelled",
    ):
        return status
    return "uncertain"


def _status_batch(statuses):
    if "uncertain" in statuses:
        return "attention"
    if "pending" in statuses:
        return "partial"
    if statuses and all(status == "succeeded" for status in statuses):
        return "succeeded"
    return "partial"


def _batalkan_pending(path_transient, batch_id, kini):
    with _transaksi(path_transient) as kon:
        kon.execute(
            "UPDATE item_bulk SET status='cancelled' WHERE batch_id=? AND status='pending'",
            (batch_id,),
        )
        kon.execute(
            "UPDATE kelompok_bulk SET status='completed',diperbarui=? WHERE batch_id=? AND status='running'",
            (int(kini), batch_id),
        )
        kon.execute(
            "UPDATE draft_bulk SET status='stopped',diperbarui=? WHERE batch_id=?",
            (int(kini), batch_id),
        )


def _rekonsiliasi_kelompok_kon(kon, snapshot, kelompok_id, kini):
    """Bawa transient terkunci ke receipt durable tanpa credential."""
    group = next(
        (data for data in snapshot.kelompok
         if data.kelompok_id == kelompok_id), None
    )
    if group is None:
        raise BulkTidakSah("kelompok durable tidak tersedia")
    per_item = {data.item_id: data for data in snapshot.item}
    batch = kon.execute(
        "SELECT batch_id FROM draft_bulk WHERE batch_id=?", (snapshot.batch.batch_id,)
    ).fetchone()
    if batch is None:
        raise BulkTidakSah("draft batch tidak tersedia")
    lama = kon.execute(
        "SELECT batch_id FROM kelompok_bulk WHERE kelompok_id=?",
        (kelompok_id,),
    ).fetchone()
    if lama is None:
        kon.execute(
            "INSERT INTO kelompok_bulk VALUES(?,?,?,?,?)",
            (kelompok_id, snapshot.batch.batch_id, group.status,
             group.dibuat, group.diperbarui),
        )
        kon.executemany(
            "INSERT INTO kelompok_bulk_item VALUES(?,?,?,?)",
            [(kelompok_id, snapshot.batch.batch_id, item_id, urutan)
             for urutan, item_id in enumerate(group.item_ids)],
        )
    elif lama["batch_id"] != snapshot.batch.batch_id:
        raise BulkTidakSah("kelompok transient berbeda")
    for item_id in group.item_ids:
        data = per_item[item_id]
        kon.execute(
            """UPDATE item_bulk SET status=?,hasil_id=?,credential_status=?
               WHERE batch_id=? AND item_id=?""",
            (data.status, data.hasil_id, data.credential_status,
             snapshot.batch.batch_id, item_id),
        )
    kon.execute(
        "UPDATE kelompok_bulk SET status=?,diperbarui=? WHERE kelompok_id=?",
        (group.status, int(kini), kelompok_id),
    )
    kon.execute(
        "UPDATE draft_bulk SET status=?,diperbarui=? WHERE batch_id=?",
        (snapshot.batch.status, int(kini), snapshot.batch.batch_id),
    )


def _rekonsiliasi_kelompok_transient(path_transient, snapshot, kelompok_id, kini):
    with _transaksi(path_transient) as kon:
        _rekonsiliasi_kelompok_kon(kon, snapshot, kelompok_id, kini)


def _sinkronkan_transient_durable_kon(kon, snapshot, kini):
    if kon.execute(
        "SELECT 1 FROM draft_bulk WHERE batch_id=?",
        (snapshot.batch.batch_id,),
    ).fetchone() is None:
        return
    for data in snapshot.item:
        kon.execute(
            """UPDATE item_bulk SET status=?,hasil_id=?,credential_status=?
               WHERE batch_id=? AND item_id=?""",
            (data.status, data.hasil_id, data.credential_status,
             snapshot.batch.batch_id, data.item_id),
        )
    for group in snapshot.kelompok:
        kon.execute(
            "UPDATE kelompok_bulk SET status=?,diperbarui=? WHERE kelompok_id=?",
            (group.status, int(kini), group.kelompok_id),
        )
    kon.execute(
        "UPDATE draft_bulk SET status=?,diperbarui=? WHERE batch_id=?",
        (snapshot.batch.status, int(kini), snapshot.batch.batch_id),
    )


def _sinkronkan_transient_durable(path_transient, snapshot, kini):
    """Best-effort projection durable untuk stop/handover yang sudah commit."""
    with _transaksi(path_transient) as kon:
        _sinkronkan_transient_durable_kon(kon, snapshot, kini)


def proses_kelompok(path_admin, path_auth, path_db, *, path_transient,
                     path_sesi, token_sesi, batch_id, actor_id, actor_revisi,
                     kelompok_id, sekarang=None, maksimum=BATAS_KELOMPOK):
    """Jalankan atau pulihkan tepat satu kelompok dengan guard sesi per item."""
    validasi_id(kelompok_id, "kelompok_id")
    if type(maksimum) is not int or not 1 <= maksimum <= BATAS_KELOMPOK:
        raise BulkTidakSah("ukuran kelompok harus 1..10")
    with kunci_batch(path_transient, batch_id):
        kini = _waktu(sekarang)
        _principal_hidup(
            path_auth, path_sesi, token_sesi, actor_id, actor_revisi, kini
        )
        durable = _cocok_batch_durable(
            path_admin, batch_id, actor_id, actor_revisi,
            _binding(token_sesi),
        )
        if durable is None:
            raise LookupError("batch tidak ditemukan")
        kon = _buka_baca_transient(path_transient)
        if kon is None:
            if durable.batch.kelompok_aktif_id == kelompok_id:
                return _hasil_kelompok_durable(path_admin, kelompok_id)
            raise BulkTidakSah("draft batch tidak tersedia")
        kon.close()
        durable_group = next(
            (group for group in durable.kelompok
             if group.kelompok_id == kelompok_id), None
        )
        if durable.batch.kelompok_aktif_id is not None and durable_group is None:
            raise BulkTidakSah("batch memiliki kelompok durable lain")
        if durable_group is not None:
            _rekonsiliasi_kelompok_transient(
                path_transient, durable, kelompok_id, kini
            )
        with _transaksi(path_transient) as kon:
            batch = _batch(
                kon, batch_id, actor_id, actor_revisi, token_sesi, kini
            )
            lama = kon.execute(
                "SELECT * FROM kelompok_bulk WHERE kelompok_id=?", (kelompok_id,)
            ).fetchone()
            perlu_rekonsiliasi_kelompok = False
            if lama is not None:
                if lama["batch_id"] != batch_id:
                    raise BulkTidakSah("kelompok_id dipakai batch berbeda")
                if lama["status"] != "running":
                    return _hasil_kelompok_durable(path_admin, kelompok_id)
                item = _baris_kelompok(kon, kelompok_id)
            elif durable_group is not None:
                # Receipt kelompok durable sudah direkonsiliasi ke transient;
                # gunakan daftar item kanonik yang sama untuk melanjutkan.
                placeholder = ",".join("?" for _ in durable_group.item_ids)
                item = kon.execute(
                    """SELECT * FROM item_bulk WHERE batch_id=?
                       AND item_id IN (%s) ORDER BY urutan""" % placeholder,
                    (batch_id, *durable_group.item_ids),
                ).fetchall()
                if tuple(row["item_id"] for row in item) != durable_group.item_ids:
                    raise BulkTidakSah("item kelompok transient berbeda")
                perlu_rekonsiliasi_kelompok = True
            else:
                if batch["status"] == "running":
                    raise BulkTidakSah("batch memiliki kelompok yang belum selesai")
                if batch["status"] in ("stopped", "succeeded", "attention"):
                    return ()
                semua = kon.execute(
                    "SELECT * FROM item_bulk WHERE batch_id=? ORDER BY urutan",
                    (batch_id,),
                ).fetchall()
                pending = [row for row in semua if row["status"] == "pending"]
                if batch["aksi"] == AKSI_BUAT_GURU:
                    _preflight_create_semua(path_auth, path_db, pending)
                else:
                    _preflight_target_semua(
                        path_auth, pending, target_peran=batch["target_peran"]
                    )
                if not bool(batch["preflight_selesai"]):
                    kon.execute(
                        "UPDATE draft_bulk SET preflight_selesai=1 WHERE batch_id=?",
                        (batch_id,),
                    )
                item = pending[:maksimum]
                if not item:
                    return ()
                item_ids = tuple(row["item_id"] for row in item)

                def tulis_kelompok_transient(_hasil):
                    kon.execute(
                        "INSERT INTO kelompok_bulk VALUES(?,?,'running',?,?)",
                        (kelompok_id, batch_id, int(kini), int(kini)),
                    )
                    kon.executemany(
                        "INSERT INTO kelompok_bulk_item VALUES(?,?,?,?)",
                        [(kelompok_id, batch_id, item_id, nomor)
                         for nomor, item_id in enumerate(item_ids)],
                    )
                    kon.execute(
                        """UPDATE draft_bulk SET status='running',diperbarui=?
                           WHERE batch_id=?""",
                        (int(kini), batch_id),
                    )

                admin_store.mulai_kelompok_durable_dengan_guard(
                    path_admin, batch_id=batch_id, kelompok_id=kelompok_id,
                    item_ids=item_ids, sekarang=int(kini),
                    guard=_guard_principal(
                        path_auth, path_sesi, token_sesi,
                        actor_id, actor_revisi, _waktu(sekarang),
                    ),
                    setelah=tulis_kelompok_transient,
                )
        if perlu_rekonsiliasi_kelompok:
            # Baris ``item`` di atas adalah snapshot sebelum rekonsiliasi; hanya
            # item durable yang masih pending boleh masuk jalur eksekusi lagi.
            per_durable = {data.item_id: data for data in durable.item}
            item = [
                row for row in item
                if per_durable[row["item_id"]].status == "pending"
            ]
        fresh = {}
        for row in item:
            if row["status"] != "pending":
                continue
            kini = _waktu(sekarang)
            try:
                _principal_hidup(
                    path_auth, path_sesi, token_sesi,
                    actor_id, actor_revisi, kini,
                )
            except PermissionError:
                admin_store.batalkan_batch_aktif_durable(
                    path_admin, batch_id=batch_id, sekarang=int(kini)
                )
                try:
                    _batalkan_pending(path_transient, batch_id, kini)
                finally:
                    fresh.clear()
                raise
            with _transaksi(path_transient) as kon:
                kini_row = kon.execute(
                    "SELECT status FROM item_bulk WHERE batch_id=? AND item_id=?",
                    (batch_id, row["item_id"]),
                ).fetchone()
                _batch(kon, batch_id, actor_id, actor_revisi, token_sesi, kini)
                if kini_row is None or kini_row["status"] != "pending":
                    continue
            try:
                if batch["aksi"] == AKSI_BUAT_GURU:
                    perintah = PerintahPembuatanAkun(
                        row["operasi_id"], actor_id, actor_revisi, AKSI_BUAT_GURU,
                        row["target_id"], "guru", row["alias_valid"], token_sesi,
                    )
                    sandi = secrets.token_urlsafe(24)
                    layanan = admin_service.buat_akun(
                        path_admin, path_auth, path_db, perintah,
                        sandi_baru=sandi, sekarang=int(kini),
                    )
                else:
                    perintah = PerintahAkun(
                        row["operasi_id"], actor_id, actor_revisi, batch["aksi"],
                        row["target_id"], int(row["target_revisi"]),
                        batch["target_peran"], token_sesi,
                    )
                    sandi = secrets.token_urlsafe(24) if batch["aksi"] == AKSI_RESET_SANDI else None
                    layanan = admin_service.jalankan(
                        path_admin, path_auth, perintah,
                        sandi_baru=sandi, sekarang=int(kini),
                    )
                status = _status_item(layanan.hasil.status)
                hasil_id = layanan.hasil.hasil_id
                fresh[row["item_id"]] = HasilItemBulk(
                    row["item_id"], status, hasil_id,
                    layanan.credential_sekali,
                )
            except admin_service.OperasiTidakDapatDilanjutkan:
                op = admin_store.baca_operasi(path_admin, row["operasi_id"])
                status = _status_item(None if op is None else op.status)
                hasil_id = None if op is None else op.hasil_id
            credential = (
                "unconfirmed"
                if status == "succeeded" and batch["aksi"] in (
                    AKSI_BUAT_GURU, AKSI_RESET_SANDI,
                )
                else "not_applicable"
            )
            def tulis_item_transient():
                with _transaksi(path_transient) as kon:
                    kon.execute(
                        """UPDATE item_bulk SET status=?,hasil_id=?,credential_status=?
                           WHERE batch_id=? AND item_id=? AND status='pending'""",
                        (status, hasil_id, credential, batch_id, row["item_id"]),
                    )

            # Receipt durable item selalu lebih dahulu. Jika transient gagal,
            # replay kelompok merekonsiliasi dari receipt tanpa operasi ulang.
            admin_store.catat_item_batch_durable(
                path_admin, batch_id=batch_id, item_id=row["item_id"],
                status=status, hasil_id=hasil_id,
                credential_status=credential, sekarang=int(kini),
                setelah=tulis_item_transient,
            )
            if status == "uncertain":
                break
        durable = admin_store.baca_batch_durable(path_admin, batch_id)
        group_items = next(
            (group.item_ids for group in durable.kelompok
             if group.kelompok_id == kelompok_id), ()
        )
        status_group = {
            item.item_id: item.status for item in durable.item
            if item.item_id in group_items
        }
        status_kelompok = (
            "attention" if "uncertain" in status_group.values()
            else "completed"
        )
        admin_store.selesaikan_kelompok_durable(
            path_admin, batch_id=batch_id, kelompok_id=kelompok_id,
            status=status_kelompok, sekarang=int(_waktu(sekarang)),
        )
        final = admin_store.baca_batch_durable(path_admin, batch_id)
        _rekonsiliasi_kelompok_transient(
            path_transient, final, kelompok_id, _waktu(sekarang)
        )
        metadata = _hasil_kelompok_durable(path_admin, kelompok_id)
        try:
            _principal_hidup(
                path_auth, path_sesi, token_sesi, actor_id, actor_revisi,
                _waktu(sekarang),
            )
        except PermissionError:
            raise
        return tuple(fresh.get(item.item_id, item) for item in metadata)


def hentikan(path_admin, path_transient, *, path_auth, path_sesi, token_sesi,
             batch_id, actor_id, actor_revisi, sekarang=None):
    with kunci_batch(path_transient, batch_id):
        kini = _waktu(sekarang)
        _principal_hidup(
            path_auth, path_sesi, token_sesi, actor_id, actor_revisi, kini
        )
        durable = _cocok_batch_durable(
            path_admin, batch_id, actor_id, actor_revisi,
            _binding(token_sesi),
        )
        if durable is None:
            raise LookupError("batch tidak ditemukan")
        tampilan = baca_batch(path_admin, path_transient, path_auth=path_auth,
                              path_sesi=path_sesi, token_sesi=token_sesi,
                              batch_id=batch_id, actor_id=actor_id,
                              actor_revisi=actor_revisi, sekarang=kini)
        if not tampilan.draft_tersedia:
            admin_store.hentikan_batch_durable_dengan_guard(
                path_admin, batch_id=batch_id, sekarang=int(kini),
                guard=_guard_principal(path_auth, path_sesi, token_sesi,
                                       actor_id, actor_revisi, _waktu(sekarang)),
            )
            return
        if durable.batch.status == "stopped":
            with _transaksi(path_transient) as kon:
                _batch(kon, batch_id, actor_id, actor_revisi, token_sesi, kini)
                with _guard_principal(
                    path_auth, path_sesi, token_sesi,
                    actor_id, actor_revisi, _waktu(sekarang),
                ):
                    _sinkronkan_transient_durable_kon(kon, durable, kini)
            return
        with _transaksi(path_transient) as kon:
            _batch(kon, batch_id, actor_id, actor_revisi, token_sesi, kini)
            # Guard diulang sesaat sebelum kedua metadata store ditulis.
            _principal_hidup(
                path_auth, path_sesi, token_sesi, actor_id, actor_revisi,
                _waktu(sekarang),
            )
            def tulis_stop_transient():
                kon.execute(
                    """UPDATE item_bulk SET status='cancelled'
                       WHERE batch_id=? AND status='pending'""",
                    (batch_id,),
                )
                kon.execute(
                    """UPDATE draft_bulk SET status='stopped',diperbarui=?
                       WHERE batch_id=?""",
                    (int(kini), batch_id),
                )

            admin_store.hentikan_batch_durable_dengan_guard(
                path_admin, batch_id=batch_id, sekarang=int(kini),
                guard=_guard_principal(
                    path_auth, path_sesi, token_sesi,
                    actor_id, actor_revisi, _waktu(sekarang),
                ),
                setelah=tulis_stop_transient,
            )


def konfirmasi_penyerahan(
    path_admin, path_transient, *, path_auth, path_sesi, token_sesi,
    batch_id, actor_id, actor_revisi, item_ids, operasi_id, sekarang=None,
):
    """Commit receipt penyerahan durable tanpa menerima/menyimpan credential."""
    validasi_id(operasi_id, "operasi_id")
    if type(item_ids) not in (tuple, list) or not item_ids:
        raise BulkTidakSah("item penyerahan wajib")
    item_ids = tuple(item_ids)
    if len(item_ids) > BATAS_ITEM or len(set(item_ids)) != len(item_ids):
        raise BulkTidakSah("item penyerahan duplikat/berlebih")
    for item_id in item_ids:
        validasi_id(item_id, "item_id")
    with kunci_batch(path_transient, batch_id):
        kini = _waktu(sekarang)
        _principal_hidup(
            path_auth, path_sesi, token_sesi, actor_id, actor_revisi, kini
        )
        tampilan = baca_batch(path_admin, path_transient, path_auth=path_auth,
                              path_sesi=path_sesi, token_sesi=token_sesi,
                              batch_id=batch_id, actor_id=actor_id,
                              actor_revisi=actor_revisi, sekarang=kini)
        if not tampilan.draft_tersedia:
            if tampilan.aksi == AKSI_CABUT_SESI:
                raise BulkTidakSah("aksi ini tidak memiliki credential")
            admin_store.konfirmasi_penyerahan_durable_dengan_guard(
                path_admin, operasi_id=operasi_id, batch_id=batch_id,
                actor_id=actor_id, actor_revisi=actor_revisi, item_ids=item_ids,
                sekarang=int(kini),
                guard=_guard_principal(path_auth, path_sesi, token_sesi,
                                       actor_id, actor_revisi, _waktu(sekarang)),
            )
            return
        with _transaksi(path_transient) as kon:
            batch = _batch(
                kon, batch_id, actor_id, actor_revisi, token_sesi, kini
            )
            durable = _cocok_batch_durable(
                path_admin, batch_id, actor_id, actor_revisi,
                _binding(token_sesi),
            )
            if durable is None:
                raise LookupError("batch tidak ditemukan")
            receipt = next(
                (data for data in durable.penyerahan
                 if data.operasi_id == operasi_id), None
            )
            if receipt is not None:
                if tuple(sorted(item_ids)) != receipt.item_ids:
                    raise admin_store.KonflikOperasi(
                        "operasi penyerahan berbeda"
                    )
                with _guard_principal(
                    path_auth, path_sesi, token_sesi,
                    actor_id, actor_revisi, _waktu(sekarang),
                ):
                    _sinkronkan_transient_durable_kon(kon, durable, kini)
                return
            if batch["aksi"] == AKSI_CABUT_SESI:
                raise BulkTidakSah("aksi ini tidak memiliki credential")
            placeholder = ",".join("?" for _ in item_ids)
            rows = kon.execute(
                """SELECT item_id,status,credential_status FROM item_bulk
                   WHERE batch_id=? AND item_id IN (%s)""" % placeholder,
                (batch_id, *item_ids),
            ).fetchall()
            if len(rows) != len(item_ids) or any(
                row["status"] != "succeeded"
                or row["credential_status"] not in ("unconfirmed", "confirmed")
                for row in rows
            ):
                raise BulkTidakSah("hanya hasil sukses dapat dikonfirmasi")
            _principal_hidup(
                path_auth, path_sesi, token_sesi, actor_id, actor_revisi,
                _waktu(sekarang),
            )
            def tulis_penyerahan_transient():
                kon.execute(
                    """UPDATE item_bulk SET credential_status='confirmed'
                       WHERE batch_id=? AND item_id IN (%s)""" % placeholder,
                    (batch_id, *item_ids),
                )
                kon.execute(
                    "UPDATE draft_bulk SET diperbarui=? WHERE batch_id=?",
                    (int(kini), batch_id),
                )

            admin_store.konfirmasi_penyerahan_durable_dengan_guard(
                path_admin, operasi_id=operasi_id, batch_id=batch_id,
                actor_id=actor_id, actor_revisi=actor_revisi,
                item_ids=item_ids, sekarang=int(kini),
                guard=_guard_principal(
                    path_auth, path_sesi, token_sesi,
                    actor_id, actor_revisi, _waktu(sekarang),
                ),
                setelah=tulis_penyerahan_transient,
            )


def purge_draft(path_transient, *, sekarang=None, batas_batch=100):
    """Hapus draft kedaluwarsa secara bounded; durable metadata tetap."""
    if type(batas_batch) is not int or not 1 <= batas_batch <= 1000:
        raise BulkTidakSah("batas purge draft tidak sah")
    kini = int(_waktu(sekarang))
    with _transaksi(path_transient) as kon:
        ids = [row[0] for row in kon.execute(
            """SELECT batch_id FROM draft_bulk WHERE kedaluwarsa<=?
               ORDER BY kedaluwarsa,batch_id LIMIT ?""",
            (kini, batas_batch),
        )]
    terhapus = 0
    for batch_id in ids:
        with kunci_batch(path_transient, batch_id):
            with _transaksi(path_transient) as kon:
                kursor = kon.execute(
                    "DELETE FROM draft_bulk WHERE batch_id=? AND kedaluwarsa<=?",
                    (batch_id, kini),
                )
                terhapus += int(kursor.rowcount)
    return terhapus

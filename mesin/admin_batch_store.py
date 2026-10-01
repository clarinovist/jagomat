"""Store durable batch admin; boundary koneksi dipanggil terlambat."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Optional, Tuple

from admin_contracts import validasi_id, validasi_revisi, validasi_sidik
from admin_journal_store import DataAuditTidakSah, KonflikOperasi


def _transaksi(path=None):
    import admin_store
    return admin_store._transaksi(path)


def buka_baca(path=None):
    import admin_store
    return admin_store.buka_baca(path)


def _buat_batch_durable_kon_dispatch(*args, **kwargs):
    import admin_store
    return admin_store._buat_batch_durable_kon(*args, **kwargs)


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

def _buat_batch_durable_kon_impl(
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
        return _buat_batch_durable_kon_dispatch(
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
            hasil = _buat_batch_durable_kon_dispatch(
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

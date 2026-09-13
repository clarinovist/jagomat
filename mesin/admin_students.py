"""Mutasi siswa admin dengan receipt di DB belajar dan anchor di DB admin."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
from typing import Optional, Union

import admin_accounts
from admin_contracts import (
    AKSI_HAPUS_SISWA,
    AKSI_UBAH_LEVEL,
    HASIL_PER_AKSI,
    PerintahHapusSiswa,
    PerintahSiswa,
    ReceiptSiswa,
    receipt_cocok,
    sidik_perintah,
)
import admin_store
import database


class KonflikSiswa(RuntimeError):
    """Siswa hilang/berubah atau receipt tidak cocok."""


class KonflikSetelahLoginDihapus(KonflikSiswa):
    """Guard DB gagal setelah langkah auth sudah commit."""


class DomainSiswaTidakSah(RuntimeError):
    """Storage receipt siswa tidak tersedia atau rusak."""


@dataclass(frozen=True)
class SnapshotHapusSiswa:
    siswa_id: int
    expected_level: str
    login_id: Optional[str]
    login_revisi: Optional[int]


_DDL_DOMAIN = """
CREATE TABLE IF NOT EXISTS operasi_admin_siswa (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL CHECK(aksi IN ('student_level_update','student_delete')),
    siswa_id INTEGER NOT NULL,
    sidik_perintah TEXT NOT NULL CHECK(length(sidik_perintah)=64),
    hasil_kode TEXT NOT NULL CHECK(hasil_kode IN ('student_level_updated','student_deleted')),
    level_lama TEXT NOT NULL,
    level_baru TEXT NOT NULL,
    login_receipt_id TEXT,
    dibuat INTEGER NOT NULL
);
"""


def siapkan(path_db) -> None:
    path = Path(path_db)
    kon = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5.0)
    try:
        kon.execute("PRAGMA foreign_keys=ON")
        kon.execute("BEGIN IMMEDIATE")
        kon.execute(_DDL_DOMAIN)
        kon.commit()
    except Exception:
        kon.rollback(); raise
    finally:
        kon.close()


def _receipt_dari_baris(baris) -> ReceiptSiswa:
    return ReceiptSiswa(
        1, baris["operasi_id"], baris["actor_id"], baris["aksi"],
        "student_%d" % int(baris["siswa_id"]), None, 0, 0,
        baris["hasil_kode"], int(baris["dibuat"]), baris["sidik_perintah"],
        (("student_level", baris["level_lama"], baris["level_baru"]),)
        if baris["aksi"] == AKSI_UBAH_LEVEL else (),
    )


def _validasi_receipt(baris, perintah):
    if baris is None:
        return None
    receipt = _receipt_dari_baris(baris)
    if not receipt_cocok(receipt, perintah):
        raise KonflikSiswa("operation ID siswa berbeda")
    return receipt


def baca_receipt(
    path_db, perintah: Union[PerintahSiswa, PerintahHapusSiswa]
) -> Optional[ReceiptSiswa]:
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    kon.row_factory = sqlite3.Row
    try:
        baris = kon.execute("SELECT * FROM operasi_admin_siswa WHERE operasi_id=?", (perintah.operasi_id,)).fetchone()
    except sqlite3.Error as galat:
        raise DomainSiswaTidakSah("receipt siswa tidak tersedia") from galat
    finally:
        kon.close()
    return _validasi_receipt(baris, perintah)


def baca_receipt_dengan_actor(
    path_db, path_auth,
    perintah: Union[PerintahSiswa, PerintahHapusSiswa],
) -> Optional[ReceiptSiswa]:
    """Baca receipt dan validasi actor dengan urutan lock DB→auth."""
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + "?mode=rw", uri=True, timeout=5.0)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute("PRAGMA busy_timeout=5000")
        kon.execute("BEGIN IMMEDIATE")
        baris = kon.execute(
            "SELECT * FROM operasi_admin_siswa WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        with admin_accounts.kunci_actor(path_auth, perintah):
            receipt = _validasi_receipt(baris, perintah)
        kon.rollback()
        return receipt
    except sqlite3.Error as galat:
        if kon.in_transaction:
            kon.rollback()
        raise DomainSiswaTidakSah("receipt siswa tidak tersedia") from galat
    except Exception:
        if kon.in_transaction:
            kon.rollback()
        raise
    finally:
        kon.close()


def _baca_anchor_admin(kon, perintah):
    row = kon.execute("SELECT * FROM receipt_admin WHERE operasi_id=?", (perintah.operasi_id,)).fetchone()
    if row is None:
        return None
    receipt = ReceiptSiswa(
        1, row["operasi_id"], row["actor_id"], row["aksi"], row["target_id"],
        None, 0, 0, row["hasil_kode"], int(row["dibuat"]),
        row["sidik_perintah"], (),
    )
    if not receipt_cocok(receipt, perintah):
        raise KonflikSiswa("anchor siswa berbeda")
    return receipt


def siapkan_anchor_admin(
    path_admin, perintah: Union[PerintahSiswa, PerintahHapusSiswa], *, sekarang=None
) -> None:
    """Anchor sebelum mutasi domain mencegah purge DB belajar membuka replay."""
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with admin_store._transaksi(path_admin) as kon:
        lama = _baca_anchor_admin(kon, perintah)
        if lama is not None:
            return
        kon.execute(
            "INSERT INTO receipt_admin VALUES(?,?,?,?,?,?,?,?)",
            (perintah.operasi_id, perintah.actor_id, perintah.aksi, "student",
             perintah.target_id, sidik_perintah(perintah),
             HASIL_PER_AKSI[perintah.aksi], kini),
        )


def baca_anchor_admin(
    path_admin, perintah: Union[PerintahSiswa, PerintahHapusSiswa]
) -> Optional[ReceiptSiswa]:
    with admin_store.buka_baca(path_admin) as kon:
        return _baca_anchor_admin(kon, perintah)


def hapus_anchor_admin(
    path_admin, perintah: Union[PerintahSiswa, PerintahHapusSiswa]
) -> None:
    with admin_store._transaksi(path_admin) as kon:
        kon.execute("DELETE FROM receipt_admin WHERE operasi_id=?", (perintah.operasi_id,))


def ubah_kelas_domain(
    path_db,
    path_auth,
    perintah: PerintahSiswa,
    *,
    sekarang=None,
    failpoint=None,
):
    """Commit level+receipt dengan urutan lock DB belajar lalu auth.

    Urutan ini selaras create login murid dan caller `/akun` existing yang
    memegang transaksi DB sebelum menulis auth. Actor tetap direvalidasi sambil
    lock DB aktif dan lock auth dipertahankan sampai commit DB selesai.
    """
    path = Path(path_db)
    kon = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5.0)
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys=ON")
    try:
        kon.execute("BEGIN IMMEDIATE")
        lama = kon.execute("SELECT * FROM operasi_admin_siswa WHERE operasi_id=?", (perintah.operasi_id,)).fetchone()
        if lama is not None:
            receipt = _receipt_dari_baris(lama)
            if not receipt_cocok(receipt, perintah):
                raise KonflikSiswa("operation ID siswa berbeda")
            kon.rollback(); return receipt
        # DB -> auth, tidak pernah auth -> DB. Commit terjadi sebelum lock auth
        # dilepas agar actor tidak bisa dicabut di antara validasi dan mutasi.
        with admin_accounts.kunci_actor(path_auth, perintah):
            siswa = kon.execute("SELECT tingkat FROM siswa WHERE id=?", (perintah.siswa_id,)).fetchone()
            if siswa is None: raise KonflikSiswa("siswa tidak tersedia")
            if siswa["tingkat"] != perintah.expected_level: raise KonflikSiswa("level siswa berubah")
            database.ganti_level(kon, perintah.siswa_id, perintah.level_baru)
            receipt = ReceiptSiswa(
                1, perintah.operasi_id, perintah.actor_id, AKSI_UBAH_LEVEL,
                perintah.target_id, None, 0, 0, HASIL_PER_AKSI[AKSI_UBAH_LEVEL],
                int(time.time()) if sekarang is None else int(sekarang),
                sidik_perintah(perintah),
                (("student_level", perintah.expected_level, perintah.level_baru),),
            )
            kon.execute(
                "INSERT INTO operasi_admin_siswa VALUES(?,?,?,?,?,?,?,?,?,?)",
                (receipt.operasi_id, receipt.actor_id, receipt.aksi, perintah.siswa_id,
                 receipt.sidik_perintah, receipt.hasil_kode,
                 perintah.expected_level, perintah.level_baru, None, receipt.dibuat),
            )
            if failpoint == "sebelum_commit":
                raise RuntimeError("failpoint siswa sebelum commit")
            kon.commit()
        if failpoint == "setelah_commit":
            raise RuntimeError("failpoint siswa setelah commit")
        return receipt
    except Exception:
        if kon.in_transaction: kon.rollback()
        raise
    finally:
        kon.close()


@contextmanager
def kunci_guard_login(path_db, perintah):
    if perintah.siswa_id is None: raise KonflikSiswa("siswa_id wajib")
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + "?mode=rw", uri=True, timeout=5.0)
    kon.row_factory = sqlite3.Row
    try:
        kon.execute("PRAGMA foreign_keys=ON"); kon.execute("PRAGMA busy_timeout=5000"); kon.execute("BEGIN IMMEDIATE")
        siswa = kon.execute("SELECT id,nama,pemilik FROM siswa WHERE id=?", (perintah.siswa_id,)).fetchone()
        if siswa is None:
            guard = {"siswa_ada": False, "owner_pengguna": None, "siswa_nama": None, "jumlah_nama": 0}
        else:
            jumlah = int(kon.execute("SELECT COUNT(*) FROM siswa WHERE lower(nama)=lower(?)", (siswa["nama"],)).fetchone()[0])
            guard = {"siswa_ada": True, "owner_pengguna": str(siswa["pemilik"] or "") or None,
                     "siswa_nama": str(siswa["nama"]), "jumlah_nama": jumlah}
        yield guard
        # Hanya fencing/read guard; tidak ada commit DB setelah auth replace.
        kon.rollback()
    except Exception:
        kon.rollback(); raise
    finally:
        kon.close()


def _referensi_siswa_ada(kon, siswa_id: int) -> bool:
    for nama, kolom in (
        ("sesi", "siswa_id"),
        ("putaran_fokus", "siswa_id"),
        ("kejadian_belajar", "siswa_id"),
    ):
        if kon.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nama,)
        ).fetchone() and kon.execute(
            "SELECT 1 FROM %s WHERE %s=? LIMIT 1" % (nama, kolom), (siswa_id,)
        ).fetchone():
            return True
    return False


def hapus_siswa_domain(
    path_db,
    path_auth,
    perintah: PerintahHapusSiswa,
    *,
    sekarang=None,
    failpoint=None,
):
    """Saga DB→auth: hapus login lalu siswa kosong, tanpa restorasi login."""
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + "?mode=rw", uri=True, timeout=5.0)
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys=ON")
    try:
        kon.execute("BEGIN IMMEDIATE")
        lama = kon.execute(
            "SELECT * FROM operasi_admin_siswa WHERE operasi_id=?",
            (perintah.operasi_id,),
        ).fetchone()
        if lama is not None:
            receipt = _receipt_dari_baris(lama)
            if not receipt_cocok(receipt, perintah):
                raise KonflikSiswa("operation ID hapus siswa berbeda")
            kon.rollback(); return receipt
        siswa = kon.execute(
            "SELECT nama,tingkat FROM siswa WHERE id=?", (perintah.siswa_id,)
        ).fetchone()
        if siswa is None:
            # Crash setelah commit DB: receipt harus ada. Siswa hilang tanpa
            # receipt bukan bukti operasi ini yang menghapusnya.
            raise KonflikSiswa("siswa tidak tersedia")
        if siswa["tingkat"] != perintah.expected_level:
            raise KonflikSiswa("snapshot siswa berubah")
        if _referensi_siswa_ada(kon, perintah.siswa_id):
            raise KonflikSiswa("siswa memiliki riwayat terlindungi")
        with admin_accounts.langkah_login_hapus_siswa(
            path_auth,
            perintah,
            siswa_nama=siswa["nama"],
            sekarang=sekarang,
            failpoint=failpoint,
        ) as login_receipt:
            # Lock auth tetap dimiliki hingga commit DB: login baru tidak bisa
            # tersisip di antara verifikasi dan penghapusan siswa.
            if _referensi_siswa_ada(kon, perintah.siswa_id):
                raise KonflikSetelahLoginDihapus("riwayat muncul setelah login dihapus")
            kon.execute("DELETE FROM siswa WHERE id=?", (perintah.siswa_id,))
            if failpoint == "setelah_student_delete_sebelum_commit":
                raise RuntimeError("failpoint setelah delete siswa")
            receipt = ReceiptSiswa(
                1, perintah.operasi_id, perintah.actor_id, AKSI_HAPUS_SISWA,
                perintah.target_id, None, 0, 0, HASIL_PER_AKSI[AKSI_HAPUS_SISWA],
                int(time.time()) if sekarang is None else int(sekarang),
                sidik_perintah(perintah), (),
            )
            kon.execute(
                "INSERT INTO operasi_admin_siswa VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    receipt.operasi_id, receipt.actor_id, receipt.aksi,
                    perintah.siswa_id, receipt.sidik_perintah, receipt.hasil_kode,
                    perintah.expected_level, perintah.expected_level,
                    None if login_receipt is None else login_receipt.operasi_id,
                    receipt.dibuat,
                ),
            )
            kon.commit()
        if failpoint == "setelah_domain_commit":
            raise RuntimeError("failpoint setelah commit hapus siswa")
        return receipt
    except Exception:
        if kon.in_transaction:
            kon.rollback()
        raise
    finally:
        kon.close()


def tinjau_hapus_siswa(path_db, path_auth, siswa_id: int) -> Optional[SnapshotHapusSiswa]:
    """Buat snapshot ID/revisi tanpa mengeluarkan nama siswa ke kontrak."""
    if type(siswa_id) is not int or siswa_id <= 0:
        raise ValueError("siswa_id tidak sah")
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    kon.row_factory = sqlite3.Row
    try:
        siswa = kon.execute("SELECT nama,tingkat FROM siswa WHERE id=?", (siswa_id,)).fetchone()
        if siswa is None or _referensi_siswa_ada(kon, siswa_id):
            return None
        login = admin_accounts.ringkasan_login_siswa(
            path_auth, siswa_id=siswa_id, siswa_nama=siswa["nama"]
        )
        return SnapshotHapusSiswa(
            siswa_id, siswa["tingkat"],
            None if login is None else login[0],
            None if login is None else login[1],
        )
    finally:
        kon.close()


def siswa_boleh_dihapus(path_db, siswa_id: int) -> bool:
    """Guard readonly konservatif; commit tetap wajib melalui saga service."""
    kon = sqlite3.connect(Path(path_db).resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    try:
        if _referensi_siswa_ada(kon, siswa_id):
            return False
        return kon.execute("SELECT 1 FROM siswa WHERE id=?", (siswa_id,)).fetchone() is not None
    finally:
        kon.close()

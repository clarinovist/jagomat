"""Store memori privat Pendamping; seluruh query tetap owner-scoped."""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Optional


def _wajib_account_id_late(account_id):
    import assistant_store
    return assistant_store._wajib_account_id(account_id)


def _teks_aman_late(teks, *, batas):
    import assistant_store
    return assistant_store._teks_aman(teks, batas=batas)


def _id_late(awalan):
    import assistant_store
    return assistant_store._id(awalan)


def ambil_chat_late(kon, account_id, chat_id):
    import assistant_store
    return assistant_store.ambil_chat(kon, account_id, chat_id)


@dataclass(frozen=True)
class Memori:
    id: str
    account_id: str
    lingkup: str
    isi: str
    versi: int
    sumber_chat_id: Optional[str]
    dikonfirmasi: bool
    dibuat: int
    dihapus: Optional[int]

def _memori_dari_baris(baris: sqlite3.Row) -> Memori:
    data = dict(baris)
    data["dikonfirmasi"] = bool(data["dikonfirmasi"])
    return Memori(**data)

def tambah_memori(
    kon: sqlite3.Connection,
    account_id: str,
    isi: str,
    *,
    sumber_chat_id: Optional[str],
    dikonfirmasi: bool,
    sekarang: int,
    lingkup: str = "preferensi_orang_tua",
) -> Memori:
    account_id = _wajib_account_id_late(account_id)
    if lingkup != "preferensi_orang_tua":
        raise ValueError("lingkup memori tidak sah")
    bersih = _teks_aman_late(isi, batas=500)
    if sumber_chat_id is not None and ambil_chat_late(kon, account_id, sumber_chat_id) is None:
        raise LookupError("chat sumber tidak ditemukan")
    memori_id = _id_late("memori_")
    kon.execute(
        """INSERT INTO memori(
               id, account_id, lingkup, isi, sumber_chat_id,
               dikonfirmasi, dibuat
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            memori_id,
            account_id,
            lingkup,
            bersih,
            sumber_chat_id,
            1 if dikonfirmasi else 0,
            sekarang,
        ),
    )
    if dikonfirmasi:
        _naikkan_versi_memori(kon, account_id, sekarang)
    baris = kon.execute("SELECT * FROM memori WHERE id = ?", (memori_id,)).fetchone()
    return _memori_dari_baris(baris)

def penggunaan_memori_aktif(
    kon: sqlite3.Connection, account_id: str
) -> bool:
    account_id = _wajib_account_id_late(account_id)
    baris = kon.execute(
        "SELECT aktif FROM preferensi_memori WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return bool(baris["aktif"]) if baris is not None else False

def daftar_memori(
    kon: sqlite3.Connection,
    account_id: str,
    *,
    termasuk_draft: bool = True,
) -> tuple[Memori, ...]:
    account_id = _wajib_account_id_late(account_id)
    syarat = "" if termasuk_draft else " AND dikonfirmasi = 1"
    baris = kon.execute(
        """SELECT * FROM memori
           WHERE account_id = ? AND dihapus IS NULL
             AND lingkup = 'preferensi_orang_tua'""" + syarat +
        " ORDER BY dibuat, id",
        (account_id,),
    ).fetchall()
    return tuple(_memori_dari_baris(item) for item in baris)

def _query_memori(
    kon: sqlite3.Connection, account_id: str
) -> tuple[Memori, ...]:
    baris = kon.execute(
        """SELECT * FROM memori
           WHERE account_id = ? AND dikonfirmasi = 1 AND dihapus IS NULL
             AND lingkup = 'preferensi_orang_tua'
           ORDER BY dibuat, id""",
        (account_id,),
    ).fetchall()
    return tuple(_memori_dari_baris(item) for item in baris)

def versi_memori(kon: sqlite3.Connection, account_id: str) -> int:
    account_id = _wajib_account_id_late(account_id)
    baris = kon.execute(
        "SELECT versi FROM preferensi_memori WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    return int(baris["versi"]) if baris else 0

def _naikkan_versi_memori(
    kon: sqlite3.Connection, account_id: str, sekarang: int
) -> int:
    versi = versi_memori(kon, account_id)
    if versi == 0:
        kon.execute(
            """INSERT INTO preferensi_memori(account_id, aktif, versi, diperbarui)
               VALUES (?, 0, 1, ?)""",
            (account_id, sekarang),
        )
        return 1
    kon.execute(
        """UPDATE preferensi_memori
           SET versi = versi + 1, diperbarui = ? WHERE account_id = ?""",
        (sekarang, account_id),
    )
    return versi + 1

def atur_penggunaan_memori(
    kon: sqlite3.Connection,
    account_id: str,
    aktif: bool,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> int:
    account_id = _wajib_account_id_late(account_id)
    kini = versi_memori(kon, account_id)
    if kini != versi_diharapkan:
        raise ValueError("versi memori berubah")
    if kini == 0:
        kon.execute(
            """INSERT INTO preferensi_memori(account_id, aktif, versi, diperbarui)
               VALUES (?, ?, 1, ?)""",
            (account_id, 1 if aktif else 0, sekarang),
        )
        return 1
    kon.execute(
        """UPDATE preferensi_memori
           SET aktif = ?, versi = versi + 1, diperbarui = ?
           WHERE account_id = ? AND versi = ?""",
        (1 if aktif else 0, sekarang, account_id, versi_diharapkan),
    )
    return kini + 1

def konfirmasi_memori(
    kon: sqlite3.Connection,
    account_id: str,
    memori_id: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id_late(account_id)
    hasil = kon.execute(
        """UPDATE memori
           SET dikonfirmasi = 1, versi = versi + 1
           WHERE id = ? AND account_id = ? AND dihapus IS NULL
             AND dikonfirmasi = 0 AND versi = ?""",
        (memori_id, account_id, versi_diharapkan),
    )
    if hasil.rowcount == 1:
        _naikkan_versi_memori(kon, account_id, sekarang)
        return True
    return False

def ubah_memori(
    kon: sqlite3.Connection,
    account_id: str,
    memori_id: str,
    isi: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id_late(account_id)
    # POST manual memakai kebijakan isi yang sama dengan draft model. Kembalikan
    # False sesuai kontrak mutasi agar input invalid tidak memutus HTTP atau
    # menampilkan isi sensitif lewat exception/halaman galat.
    from assistant_policy import validasi_isi_memori

    try:
        bersih = validasi_isi_memori(isi)
    except ValueError:
        return False
    hasil = kon.execute(
        """UPDATE memori
           SET isi = ?, versi = versi + 1
           WHERE id = ? AND account_id = ? AND dihapus IS NULL
             AND versi = ? AND lingkup = 'preferensi_orang_tua'""",
        (bersih, memori_id, account_id, versi_diharapkan),
    )
    if hasil.rowcount == 1:
        _naikkan_versi_memori(kon, account_id, sekarang)
        return True
    return False

def hapus_memori(
    kon: sqlite3.Connection,
    account_id: str,
    memori_id: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id_late(account_id)
    hasil = kon.execute(
        """UPDATE memori
           SET dihapus = ?, versi = versi + 1
           WHERE id = ? AND account_id = ? AND dihapus IS NULL AND versi = ?""",
        (sekarang, memori_id, account_id, versi_diharapkan),
    )
    if hasil.rowcount == 1:
        _naikkan_versi_memori(kon, account_id, sekarang)
        return True
    return False

def hapus_semua_memori(
    kon: sqlite3.Connection,
    account_id: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> int:
    account_id = _wajib_account_id_late(account_id)
    if versi_memori(kon, account_id) != versi_diharapkan:
        raise ValueError("versi memori berubah")
    hasil = kon.execute(
        """UPDATE memori SET dihapus = ?, versi = versi + 1
           WHERE account_id = ? AND dihapus IS NULL""",
        (sekarang, account_id),
    )
    if hasil.rowcount:
        _naikkan_versi_memori(kon, account_id, sekarang)
    return hasil.rowcount

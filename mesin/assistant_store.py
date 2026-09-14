"""Penyimpanan privat Pendamping dengan kepemilikan wajib.

Semua operasi resource menerima ``account_id`` dari principal terverifikasi.
Tidak ada parameter peran atau bypass admin. Modul ini juga menolak kontak dan
credential sebelum teks masuk ke SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import secrets
import sqlite3
from typing import Optional


_ID_AKUN = re.compile(r"akun_[0-9a-f]{32}\Z")
_EMAIL = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TELEPON = re.compile(r"(?<!\d)(?:\+?62[\s().-]*|0)8(?:[\s().-]*\d){8,12}(?!\d)")
_CREDENTIAL = re.compile(
    r"(?i)(?:authorization\s*:\s*bearer\s+\S{8,}|"
    r"(?:api[_ -]?key|access[_ -]?token|secret)\s*[:=]\s*\S{8,}|"
    r"\bsk-[A-Za-z0-9_-]{12,})"
)
_MODE_MEMORI = ("aktif", "tanpa_memori")
_PERAN_PESAN = ("pengguna", "asisten")
RETENSI_CHAT_DETIK = 180 * 24 * 3600
RETENSI_OPERASI_GAGAL_DETIK = 7 * 24 * 3600


@dataclass(frozen=True)
class Chat:
    id: str
    account_id: str
    mode_memori: str
    versi: int
    dibuat: int
    diperbarui: int
    dihapus: Optional[int]
    purge_setelah: Optional[int]
    context_kind: Optional[str] = None
    context_id: Optional[str] = None
    context_version: Optional[int] = None
    context_resource_version: Optional[str] = None


@dataclass(frozen=True)
class Pesan:
    id: str
    chat_id: str
    urut: int
    peran: str
    teks: str
    status: str
    request_id: Optional[str]
    dibuat: int


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


@dataclass(frozen=True)
class Operasi:
    request_id: str
    chat_id: str
    account_id: str
    status: str
    chat_version: int
    consent_version: int
    memory_version: int
    context_version: int
    dibuat: int
    selesai: Optional[int]


@dataclass(frozen=True)
class Persetujuan:
    id: str
    account_id: str
    policy_version: str
    provider_id: str
    kategori: str
    diberikan: int
    dicabut: Optional[int]
    versi: int


@dataclass(frozen=True)
class PersetujuanKonteks:
    id: str
    account_id: str
    jenis: str
    resource_id: str
    resource_version: str
    kategori: str
    diberikan: int
    dicabut: Optional[int]
    versi: int


@dataclass(frozen=True)
class CatatanUsulan:
    id: str
    account_id: str
    chat_id: str
    sumber_request_id: str
    payload_json: str
    hash_usulan: str
    versi: int
    chat_version: int
    consent_version: int
    context_version: int
    context_resource_version: str
    status: str
    request_id_konfirmasi: Optional[str]
    sesi_id: Optional[int]
    dibuat: int
    selesai: Optional[int]


def _id(awalan: str) -> str:
    return awalan + secrets.token_hex(16)


def _wajib_account_id(account_id: str) -> str:
    if type(account_id) is not str or not _ID_AKUN.fullmatch(account_id):
        raise ValueError("account_id wajib ID akun kanonik")
    return account_id


def _teks_aman(teks: str, *, batas: int) -> str:
    if type(teks) is not str:
        raise ValueError("teks wajib string")
    bersih = teks.strip()
    if not bersih or len(bersih) > batas:
        raise ValueError("panjang teks tidak sah")
    if _EMAIL.search(bersih) or _TELEPON.search(bersih) or _CREDENTIAL.search(bersih):
        raise ValueError("teks memuat kontak atau credential")
    return bersih


def _chat_dari_baris(baris: sqlite3.Row) -> Chat:
    return Chat(
        id=baris["id"],
        account_id=baris["account_id"],
        mode_memori=baris["mode_memori"],
        versi=baris["versi"],
        dibuat=baris["dibuat"],
        diperbarui=baris["diperbarui"],
        dihapus=baris["dihapus"],
        purge_setelah=baris["purge_setelah"],
        context_kind=baris["context_kind"],
        context_id=baris["context_id"],
        context_version=baris["context_version"],
        context_resource_version=baris["context_resource_version"],
    )


def _pesan_dari_baris(baris: sqlite3.Row) -> Pesan:
    return Pesan(**dict(baris))


def _memori_dari_baris(baris: sqlite3.Row) -> Memori:
    data = dict(baris)
    data["dikonfirmasi"] = bool(data["dikonfirmasi"])
    return Memori(**data)


def _operasi_dari_baris(baris: sqlite3.Row) -> Operasi:
    return Operasi(**dict(baris))


def _persetujuan_dari_baris(baris: sqlite3.Row) -> Persetujuan:
    return Persetujuan(**dict(baris))


def _persetujuan_konteks_dari_baris(
    baris: sqlite3.Row,
) -> PersetujuanKonteks:
    return PersetujuanKonteks(**dict(baris))


def _usulan_dari_baris(baris: sqlite3.Row) -> CatatanUsulan:
    return CatatanUsulan(**dict(baris))


def buat_chat(
    kon: sqlite3.Connection,
    account_id: str,
    mode_memori: str,
    *,
    sekarang: int,
    context_kind: Optional[str] = None,
    context_id: Optional[str] = None,
    context_version: Optional[int] = None,
    context_resource_version: Optional[str] = None,
    context_category: Optional[str] = None,
) -> Chat:
    account_id = _wajib_account_id(account_id)
    if mode_memori not in _MODE_MEMORI:
        raise ValueError("mode memori tidak sah")
    ada_konteks = any(
        nilai is not None for nilai in (
            context_kind, context_id, context_version, context_resource_version,
            context_category,
        )
    )
    if ada_konteks:
        if (
            context_kind not in ("anak", "sesi", "soal")
            or not context_id
            or type(context_version) is not int
            or not context_resource_version
            or context_category not in ("ringkasan_netral", "soal_resmi")
            or not persetujuan_konteks_aktif(
                kon,
                account_id,
                jenis=context_kind,
                resource_id=context_id,
                resource_version=context_resource_version,
                kategori=context_category,
                versi=context_version,
            )
        ):
            raise ValueError("persetujuan konteks tidak sah")
    chat_id = _id("chat_")
    kon.execute(
        """INSERT INTO chat(
               id, account_id, mode_memori, context_kind, context_id,
               context_version, context_resource_version, dibuat, diperbarui
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            chat_id, account_id, mode_memori, context_kind, context_id,
            context_version, context_resource_version, sekarang, sekarang,
        ),
    )
    baris = kon.execute(
        "SELECT * FROM chat WHERE id = ? AND account_id = ?",
        (chat_id, account_id),
    ).fetchone()
    return _chat_dari_baris(baris)


def ambil_chat(
    kon: sqlite3.Connection, account_id: str, chat_id: str
) -> Optional[Chat]:
    account_id = _wajib_account_id(account_id)
    baris = kon.execute(
        """SELECT * FROM chat
           WHERE id = ? AND account_id = ? AND dihapus IS NULL""",
        (chat_id, account_id),
    ).fetchone()
    return _chat_dari_baris(baris) if baris else None


def daftar_chat(kon: sqlite3.Connection, account_id: str) -> tuple[Chat, ...]:
    account_id = _wajib_account_id(account_id)
    baris = kon.execute(
        """SELECT * FROM chat
           WHERE account_id = ? AND dihapus IS NULL
           ORDER BY diperbarui DESC, id DESC""",
        (account_id,),
    ).fetchall()
    return tuple(_chat_dari_baris(item) for item in baris)


def ubah_konteks_chat(
    kon: sqlite3.Connection,
    account_id: str,
    chat_id: str,
    *,
    context_kind: str,
    context_id: str,
) -> None:
    """Konteks chat immutable; mengganti/melepas konteks wajib chat baru."""
    _wajib_account_id(account_id)
    raise ValueError("konteks chat immutable; buka chat baru")


def pesan_dari_request(
    kon: sqlite3.Connection,
    account_id: str,
    request_id: str,
    *,
    peran: Optional[str] = None,
) -> Optional[Pesan]:
    account_id = _wajib_account_id(account_id)
    syarat_peran = " AND pesan.peran = ?" if peran is not None else ""
    parameter = (request_id, account_id, peran) if peran is not None else (
        request_id, account_id
    )
    baris = kon.execute(
        """SELECT pesan.* FROM pesan
           JOIN chat ON chat.id = pesan.chat_id
           WHERE pesan.request_id = ? AND chat.account_id = ?""" + syarat_peran,
        parameter,
    ).fetchone()
    return _pesan_dari_baris(baris) if baris else None


def tambah_pesan(
    kon: sqlite3.Connection,
    account_id: str,
    chat_id: str,
    peran: str,
    teks: str,
    *,
    request_id: Optional[str],
    sekarang: int,
    status: str = "final",
) -> Pesan:
    account_id = _wajib_account_id(account_id)
    if peran not in _PERAN_PESAN:
        raise ValueError("peran pesan tidak sah")
    if status not in ("final", "gagal"):
        raise ValueError("status pesan tidak sah")
    bersih = _teks_aman(teks, batas=8000)
    chat = ambil_chat(kon, account_id, chat_id)
    if chat is None:
        raise LookupError("chat tidak ditemukan")
    urut = kon.execute(
        "SELECT COALESCE(MAX(urut), 0) + 1 FROM pesan WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()[0]
    pesan_id = _id("pesan_")
    kon.execute(
        """INSERT INTO pesan(
               id, chat_id, urut, peran, teks, status, request_id, dibuat
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (pesan_id, chat_id, urut, peran, bersih, status, request_id, sekarang),
    )
    kon.execute(
        """UPDATE chat SET diperbarui = ?, versi = versi + 1
           WHERE id = ? AND account_id = ? AND dihapus IS NULL""",
        (sekarang, chat_id, account_id),
    )
    baris = kon.execute("SELECT * FROM pesan WHERE id = ?", (pesan_id,)).fetchone()
    return _pesan_dari_baris(baris)


def daftar_pesan(
    kon: sqlite3.Connection, account_id: str, chat_id: str
) -> tuple[Pesan, ...]:
    account_id = _wajib_account_id(account_id)
    if ambil_chat(kon, account_id, chat_id) is None:
        return ()
    baris = kon.execute(
        "SELECT * FROM pesan WHERE chat_id = ? ORDER BY urut", (chat_id,)
    ).fetchall()
    return tuple(_pesan_dari_baris(item) for item in baris)


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
    account_id = _wajib_account_id(account_id)
    if lingkup != "preferensi_orang_tua":
        raise ValueError("lingkup memori tidak sah")
    bersih = _teks_aman(isi, batas=500)
    if sumber_chat_id is not None and ambil_chat(kon, account_id, sumber_chat_id) is None:
        raise LookupError("chat sumber tidak ditemukan")
    memori_id = _id("memori_")
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
    account_id = _wajib_account_id(account_id)
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
    account_id = _wajib_account_id(account_id)
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


def memori_untuk_chat(
    kon: sqlite3.Connection, account_id: str, chat_id: str
) -> tuple[Memori, ...]:
    account_id = _wajib_account_id(account_id)
    chat = ambil_chat(kon, account_id, chat_id)
    if chat is None or chat.mode_memori == "tanpa_memori":
        return ()
    if not penggunaan_memori_aktif(kon, account_id):
        return ()
    return _query_memori(kon, account_id)


def versi_memori(kon: sqlite3.Connection, account_id: str) -> int:
    account_id = _wajib_account_id(account_id)
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
    account_id = _wajib_account_id(account_id)
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
    account_id = _wajib_account_id(account_id)
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
    account_id = _wajib_account_id(account_id)
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
    account_id = _wajib_account_id(account_id)
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
    account_id = _wajib_account_id(account_id)
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


def beri_persetujuan_konteks(
    kon: sqlite3.Connection,
    account_id: str,
    *,
    jenis: str,
    resource_id: str,
    resource_version: str,
    kategori: str,
    sekarang: int,
) -> PersetujuanKonteks:
    account_id = _wajib_account_id(account_id)
    if jenis not in ("anak", "sesi", "soal"):
        raise ValueError("jenis konteks tidak sah")
    if kategori not in ("ringkasan_netral", "soal_resmi"):
        raise ValueError("kategori konteks tidak sah")
    if not resource_id or not resource_version:
        raise ValueError("resource konteks tidak lengkap")
    versi = int(kon.execute(
        """SELECT COALESCE(MAX(versi), 0) + 1 FROM persetujuan_konteks
           WHERE account_id = ?""",
        (account_id,),
    ).fetchone()[0])
    identitas = _id("context_")
    kon.execute(
        """INSERT INTO persetujuan_konteks(
               id, account_id, jenis, resource_id, resource_version,
               kategori, diberikan, versi
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            identitas, account_id, jenis, resource_id, resource_version,
            kategori, sekarang, versi,
        ),
    )
    baris = kon.execute(
        """SELECT * FROM persetujuan_konteks
           WHERE id = ? AND account_id = ?""",
        (identitas, account_id),
    ).fetchone()
    return _persetujuan_konteks_dari_baris(baris)


def versi_persetujuan_konteks(
    kon: sqlite3.Connection, account_id: str
) -> int:
    account_id = _wajib_account_id(account_id)
    return int(kon.execute(
        """SELECT COALESCE(MAX(versi), 0) FROM persetujuan_konteks
           WHERE account_id = ?""",
        (account_id,),
    ).fetchone()[0])


def persetujuan_konteks_aktif(
    kon: sqlite3.Connection,
    account_id: str,
    *,
    jenis: str,
    resource_id: str,
    resource_version: Optional[str] = None,
    kategori: Optional[str] = None,
    versi: Optional[int] = None,
) -> bool:
    account_id = _wajib_account_id(account_id)
    baris = kon.execute(
        """SELECT resource_version, kategori, versi, dicabut
           FROM persetujuan_konteks
           WHERE account_id = ? AND jenis = ? AND resource_id = ?
           ORDER BY versi DESC, rowid DESC LIMIT 1""",
        (account_id, jenis, resource_id),
    ).fetchone()
    if baris is None or baris["dicabut"] is not None:
        return False
    return (
        (resource_version is None or baris["resource_version"] == resource_version)
        and (kategori is None or baris["kategori"] == kategori)
        and (versi is None or int(baris["versi"]) == versi)
    )


def cabut_persetujuan_konteks(
    kon: sqlite3.Connection,
    account_id: str,
    persetujuan_id: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id(account_id)
    hasil = kon.execute(
        """UPDATE persetujuan_konteks SET dicabut = ?, versi = versi + 1
           WHERE id = ? AND account_id = ? AND dicabut IS NULL AND versi = ?""",
        (sekarang, persetujuan_id, account_id, versi_diharapkan),
    )
    return hasil.rowcount == 1


def beri_persetujuan(
    kon: sqlite3.Connection,
    account_id: str,
    *,
    policy_version: str,
    provider_id: str,
    kategori: str,
    sekarang: int,
) -> Persetujuan:
    account_id = _wajib_account_id(account_id)
    if not policy_version or not provider_id or not kategori:
        raise ValueError("persetujuan tidak lengkap")
    persetujuan_id = _id("consent_")
    versi = versi_persetujuan(kon, account_id) + 1
    kon.execute(
        """INSERT INTO persetujuan(
               id, account_id, policy_version, provider_id, kategori,
               diberikan, versi
           ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            persetujuan_id,
            account_id,
            policy_version,
            provider_id,
            kategori,
            sekarang,
            versi,
        ),
    )
    baris = kon.execute(
        "SELECT * FROM persetujuan WHERE id = ? AND account_id = ?",
        (persetujuan_id, account_id),
    ).fetchone()
    return _persetujuan_dari_baris(baris)


def versi_persetujuan(kon: sqlite3.Connection, account_id: str) -> int:
    account_id = _wajib_account_id(account_id)
    return int(kon.execute(
        "SELECT COALESCE(MAX(versi), 0) FROM persetujuan WHERE account_id = ?",
        (account_id,),
    ).fetchone()[0])


def persetujuan_aktif(
    kon: sqlite3.Connection,
    account_id: str,
    *,
    kategori: str,
    provider_id: str,
) -> bool:
    account_id = _wajib_account_id(account_id)
    return kon.execute(
        """SELECT 1 FROM persetujuan
           WHERE account_id = ? AND kategori = ? AND provider_id = ?
             AND dicabut IS NULL
           LIMIT 1""",
        (account_id, kategori, provider_id),
    ).fetchone() is not None


def cabut_persetujuan(
    kon: sqlite3.Connection,
    account_id: str,
    persetujuan_id: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id(account_id)
    versi_baru = versi_persetujuan(kon, account_id) + 1
    hasil = kon.execute(
        """UPDATE persetujuan
           SET dicabut = ?, versi = ?
           WHERE id = ? AND account_id = ? AND dicabut IS NULL AND versi = ?""",
        (sekarang, versi_baru, persetujuan_id, account_id, versi_diharapkan),
    )
    return hasil.rowcount == 1


def simpan_usulan(
    kon: sqlite3.Connection,
    account_id: str,
    chat_id: str,
    sumber_request_id: str,
    *,
    payload_json: str,
    hash_usulan: str,
    chat_version: int,
    consent_version: int,
    context_version: int,
    context_resource_version: str,
    sekarang: int,
) -> CatatanUsulan:
    """Simpan kandidat tervalidasi; owner selalu berasal dari principal."""
    account_id = _wajib_account_id(account_id)
    chat = ambil_chat(kon, account_id, chat_id)
    if (
        chat is None
        or chat.context_kind is None
        or chat.context_version != context_version
        or chat.context_resource_version != context_resource_version
        or chat.versi != chat_version
        or not re.fullmatch(r"[0-9a-f]{64}", hash_usulan)
    ):
        raise ValueError("usulan tidak cocok dengan chat dan konteks")
    lama = kon.execute(
        """SELECT * FROM usulan_latihan
           WHERE sumber_request_id = ? AND account_id = ?""",
        (sumber_request_id, account_id),
    ).fetchone()
    if lama is not None:
        if (
            lama["chat_id"] != chat_id
            or lama["payload_json"] != payload_json
            or lama["hash_usulan"] != hash_usulan
        ):
            raise ValueError("request usulan dipakai untuk isi berbeda")
        return _usulan_dari_baris(lama)
    usulan_id = _id("usulan_")
    kon.execute(
        """INSERT INTO usulan_latihan(
               id, account_id, chat_id, sumber_request_id, payload_json,
               hash_usulan, chat_version, consent_version, context_version,
               context_resource_version, dibuat
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            usulan_id, account_id, chat_id, sumber_request_id, payload_json,
            hash_usulan, chat_version, consent_version, context_version,
            context_resource_version, sekarang,
        ),
    )
    return ambil_usulan(kon, account_id, usulan_id)


def ambil_usulan(
    kon: sqlite3.Connection, account_id: str, usulan_id: str
) -> Optional[CatatanUsulan]:
    account_id = _wajib_account_id(account_id)
    baris = kon.execute(
        "SELECT * FROM usulan_latihan WHERE id = ? AND account_id = ?",
        (usulan_id, account_id),
    ).fetchone()
    return _usulan_dari_baris(baris) if baris is not None else None


def daftar_usulan_chat(
    kon: sqlite3.Connection, account_id: str, chat_id: str
) -> tuple[CatatanUsulan, ...]:
    account_id = _wajib_account_id(account_id)
    if ambil_chat(kon, account_id, chat_id) is None:
        return ()
    baris = kon.execute(
        """SELECT * FROM usulan_latihan
           WHERE account_id = ? AND chat_id = ?
           ORDER BY dibuat, id""",
        (account_id, chat_id),
    ).fetchall()
    return tuple(_usulan_dari_baris(item) for item in baris)


def selesaikan_usulan(
    kon: sqlite3.Connection,
    account_id: str,
    usulan_id: str,
    *,
    versi_diharapkan: int,
    hash_diharapkan: str,
    request_id: str,
    sesi_id: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id(account_id)
    hasil = kon.execute(
        """UPDATE usulan_latihan
           SET status = 'selesai', request_id_konfirmasi = ?, sesi_id = ?,
               selesai = ?
           WHERE id = ? AND account_id = ? AND status = 'menunggu'
             AND versi = ? AND hash_usulan = ?
             AND request_id_konfirmasi IS NULL""",
        (
            request_id, sesi_id, sekarang, usulan_id, account_id,
            versi_diharapkan, hash_diharapkan,
        ),
    )
    if hasil.rowcount == 1:
        return True
    lama = ambil_usulan(kon, account_id, usulan_id)
    return bool(
        lama is not None
        and lama.status == "selesai"
        and lama.request_id_konfirmasi == request_id
        and lama.sesi_id == sesi_id
        and lama.versi == versi_diharapkan
        and lama.hash_usulan == hash_diharapkan
    )


def hapus_chat(
    kon: sqlite3.Connection,
    account_id: str,
    chat_id: str,
    *,
    versi_diharapkan: int,
    sekarang: int,
    retensi_detik: int,
) -> bool:
    account_id = _wajib_account_id(account_id)
    if retensi_detik < 0:
        raise ValueError("retensi tidak boleh negatif")
    hasil = kon.execute(
        """UPDATE chat
           SET dihapus = ?, purge_setelah = ?, diperbarui = ?
           WHERE id = ? AND account_id = ? AND dihapus IS NULL AND versi = ?""",
        (
            sekarang,
            sekarang + retensi_detik,
            sekarang,
            chat_id,
            account_id,
            versi_diharapkan,
        ),
    )
    return hasil.rowcount == 1


def jadwalkan_retensi_chat(
    kon: sqlite3.Connection, *, sekarang: int
) -> int:
    """Tombstone chat tidak aktif 180 hari tanpa menghapus memori akun."""
    batas = sekarang - RETENSI_CHAT_DETIK
    hasil = kon.execute(
        """UPDATE chat
           SET dihapus = ?, purge_setelah = ?
           WHERE dihapus IS NULL AND diperbarui <= ?""",
        (sekarang, sekarang, batas),
    )
    return hasil.rowcount


def purge(kon: sqlite3.Connection, *, sekarang: int) -> int:
    """Hapus chat jatuh tempo beserta turunan dalam satu transaksi pemanggil."""
    ids = tuple(
        baris["id"]
        for baris in kon.execute(
            "SELECT id FROM chat WHERE purge_setelah IS NOT NULL AND purge_setelah <= ?",
            (sekarang,),
        ).fetchall()
    )
    for chat_id in ids:
        kon.execute("DELETE FROM usulan_latihan WHERE chat_id = ?", (chat_id,))
        kon.execute("DELETE FROM operasi WHERE chat_id = ?", (chat_id,))
        # Memori terkonfirmasi mengikuti retensi akun, bukan retensi chat.
        # Putuskan provenance chat yang dipurge; draft yang belum pernah
        # disetujui tidak mempunyai alasan untuk dipertahankan.
        kon.execute(
            """UPDATE memori SET sumber_chat_id = NULL
               WHERE sumber_chat_id = ? AND dikonfirmasi = 1""",
            (chat_id,),
        )
        kon.execute(
            """DELETE FROM memori
               WHERE sumber_chat_id = ? AND dikonfirmasi = 0""",
            (chat_id,),
        )
        kon.execute("DELETE FROM pesan WHERE chat_id = ?", (chat_id,))
        kon.execute("DELETE FROM chat WHERE id = ?", (chat_id,))
    return len(ids)


def mulai_operasi(
    kon: sqlite3.Connection,
    account_id: str,
    chat_id: str,
    request_id: str,
    *,
    consent_version: int,
    memory_version: int,
    context_version: int,
    sekarang: int,
) -> Operasi:
    account_id = _wajib_account_id(account_id)
    lama = kon.execute(
        "SELECT * FROM operasi WHERE request_id = ? AND account_id = ?",
        (request_id, account_id),
    ).fetchone()
    if lama:
        operasi = _operasi_dari_baris(lama)
        if (
            operasi.chat_id != chat_id
            or operasi.consent_version != consent_version
            or operasi.memory_version != memory_version
            or operasi.context_version != context_version
        ):
            raise ValueError("request_id dipakai untuk operasi berbeda")
        return operasi
    chat = ambil_chat(kon, account_id, chat_id)
    if chat is None:
        raise LookupError("chat tidak ditemukan")
    try:
        kon.execute(
            """INSERT INTO operasi(
                   request_id, chat_id, account_id, status, chat_version,
                   consent_version, memory_version, context_version, dibuat
               ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
            (
                request_id,
                chat_id,
                account_id,
                chat.versi,
                consent_version,
                memory_version,
                context_version,
                sekarang,
            ),
        )
    except sqlite3.IntegrityError:
        # Request ID milik akun lain tidak dibocorkan sebagai hasil idempoten.
        raise ValueError("request_id tidak tersedia") from None
    baris = kon.execute(
        "SELECT * FROM operasi WHERE request_id = ? AND account_id = ?",
        (request_id, account_id),
    ).fetchone()
    return _operasi_dari_baris(baris)


def gagalkan_operasi(
    kon: sqlite3.Connection,
    account_id: str,
    request_id: str,
    *,
    sekarang: int,
) -> bool:
    """Tandai operasi milik akun gagal tanpa menyimpan isi galat/provider."""
    account_id = _wajib_account_id(account_id)
    hasil = kon.execute(
        """UPDATE operasi SET status = 'gagal', selesai = ?
           WHERE request_id = ? AND account_id = ? AND status = 'pending'""",
        (sekarang, request_id, account_id),
    )
    return hasil.rowcount == 1


def purge_operasi(kon: sqlite3.Connection, *, sekarang: int) -> int:
    """Buang operasi gagal/pending yang telah melewati retensi tujuh hari."""
    batas = sekarang - RETENSI_OPERASI_GAGAL_DETIK
    hasil = kon.execute(
        """DELETE FROM operasi
           WHERE status IN ('pending', 'gagal') AND dibuat <= ?""",
        (batas,),
    )
    return hasil.rowcount


def selesaikan_operasi(
    kon: sqlite3.Connection,
    account_id: str,
    request_id: str,
    *,
    chat_version: int,
    consent_version: int,
    memory_version: int,
    context_version: int,
    sekarang: int,
) -> bool:
    account_id = _wajib_account_id(account_id)
    if versi_persetujuan(kon, account_id) != consent_version:
        return False
    if versi_memori(kon, account_id) != memory_version:
        return False
    hasil = kon.execute(
        """UPDATE operasi
           SET status = 'selesai', selesai = ?
           WHERE request_id = ? AND account_id = ? AND status = 'pending'
             AND chat_version = ? AND consent_version = ?
             AND memory_version = ? AND context_version = ?
             AND EXISTS (
                 SELECT 1 FROM chat
                 WHERE chat.id = operasi.chat_id
                   AND chat.account_id = operasi.account_id
                   AND chat.dihapus IS NULL
                   AND chat.versi = operasi.chat_version
             )""",
        (
            sekarang,
            request_id,
            account_id,
            chat_version,
            consent_version,
            memory_version,
            context_version,
        ),
    )
    return hasil.rowcount == 1

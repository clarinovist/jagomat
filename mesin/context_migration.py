"""Perluas CHECK konteks lama tanpa mengubah metadata bukti historis."""

from __future__ import annotations

import hashlib
import re
import sqlite3

from context_schema import SKEMA_KONTEKS
from templates import LEVEL


# Token SQL, bukan pencarian substring: komentar/string tidak menjadi identifier.
_TOKEN_SQL = re.compile(
    r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|"
    r"`(?:``|[^`])*`|\[[^\]]*\]|[A-Za-z_][A-Za-z_0-9]*|[^\s]",
    re.DOTALL,
)
_KOLOM = "sesi_soal_id, template_id, profil_parameter, konteks_id"


def _token_sql(ddl: str) -> list[tuple[str, str]]:
    hasil = []
    for cocok in _TOKEN_SQL.finditer(ddl):
        teks = cocok.group()
        if teks.startswith(("--", "/*")):
            continue
        if teks.startswith("'") and len(teks) >= 2:
            hasil.append(("string", teks[1:-1].replace("''", "'")))
        elif teks[0] in ('"', '`', '[') and len(teks) >= 2:
            akhir = ']' if teks[0] == '[' else teks[0]
            hasil.append(("nama", teks[1:-1].replace(akhir * 2, akhir).lower()))
        elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", teks):
            hasil.append(("kata", teks.lower()))
        else:
            hasil.append(("tanda", teks))
    return hasil


def _profil_dari_ddl(ddl: str) -> set[str]:
    """Parse tepat satu CHECK profil IN literal; ekspresi lain ditolak."""
    token = _token_sql(ddl)
    kandidat = []
    for posisi, bagian in enumerate(token):
        if bagian != ("kata", "check"):
            continue
        if token[posisi + 1:posisi + 2] != [("tanda", "(")]:
            raise ValueError("CHECK konteks_butir tidak dapat diparse")
        kedalaman = 1
        akhir = posisi + 2
        while akhir < len(token) and kedalaman:
            if token[akhir] == ("tanda", "("):
                kedalaman += 1
            elif token[akhir] == ("tanda", ")"):
                kedalaman -= 1
            akhir += 1
        if kedalaman:
            raise ValueError("CHECK konteks_butir tidak lengkap")
        isi = token[posisi + 2:akhir - 1]
        if any(jenis in ("kata", "nama") and nilai == "profil_parameter"
               for jenis, nilai in isi):
            kandidat.append(isi)
    if len(kandidat) != 1:
        raise ValueError("CHECK profil_parameter tidak tunggal atau tidak ditemukan")
    isi = kandidat[0]
    if (len(isi) < 4 or isi[0] not in (("kata", "profil_parameter"),
                                      ("nama", "profil_parameter"))
            or isi[1:3] != [("kata", "in"), ("tanda", "(")]
            or isi[-1] != ("tanda", ")")):
        raise ValueError("CHECK profil_parameter bukan IN literal yang dikenal")
    daftar = isi[3:-1]
    if daftar and (len(daftar) % 2 != 1 or any(
            bagian[0] != "string" if posisi % 2 == 0 else bagian != ("tanda", ",")
            for posisi, bagian in enumerate(daftar))):
        raise ValueError("nilai CHECK profil_parameter tidak dapat diparse")
    return {nilai for _, nilai in daftar[::2]}


def _perlu_rebuild(kon: sqlite3.Connection) -> bool:
    baris = kon.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='konteks_butir'"
    ).fetchone()
    if baris is None:
        return False
    profil = _profil_dari_ddl(baris[0])
    if not profil <= set(LEVEL):
        raise ValueError("CHECK profil_parameter berisi profil di luar LEVEL")
    return profil != set(LEVEL)


def _ddl_tabel_baru() -> str:
    # Ambil statement kanonis utuh, tanpa menyalin definisi kolom/constraint.
    cocok = re.findall(
        r"^CREATE TABLE IF NOT EXISTS konteks_butir \(.*?\n\);",
        SKEMA_KONTEKS, re.MULTILINE | re.DOTALL,
    )
    assert len(cocok) == 1, "DDL konteks_butir kanonis harus tepat satu"
    ddl, jumlah = re.subn(
        r"\bCREATE TABLE IF NOT EXISTS konteks_butir\b",
        "CREATE TABLE konteks_butir_baru", cocok[0],
    )
    assert jumlah == 1, "penggantian nama tabel harus tepat satu"
    assert _profil_dari_ddl(ddl) == set(LEVEL), "DDL konteks berbeda dari LEVEL"
    return ddl


def _sidik_baris(kon: sqlite3.Connection, tabel: str) -> tuple[int, str]:
    if tabel not in ("konteks_butir", "konteks_butir_baru"):
        raise ValueError("tabel sidik konteks tidak dikenal")
    sidik = hashlib.sha256()
    jumlah = 0
    for baris in kon.execute(f"SELECT {_KOLOM} FROM {tabel} ORDER BY sesi_soal_id"):
        # repr tuple skalar SQLite membedakan NULL/teks/angka/blob; panjang
        # eksplisit mencegah ambiguitas batas baris, termasuk newline dan NUL.
        serial = repr(tuple(baris)).encode("utf-8")
        sidik.update(len(serial).to_bytes(8, "big"))
        sidik.update(serial)
        jumlah += 1
    return jumlah, sidik.hexdigest()


def rebuild_konteks_butir(kon: sqlite3.Connection) -> bool:
    """Rebuild subset LEVEL secara atomik; trigger dipasang ulang oleh siapkan.

    Pemanggil dalam transaksi bertanggung jawab atas rollback dan pemasangan
    SKEMA sesudahnya. Pemanggil mandiri juga wajib memasang SKEMA sebelum
    koneksi dipakai aplikasi: helper ini sengaja tidak menduplikasi trigger.
    """
    if not _perlu_rebuild(kon):
        return False
    mandiri = not kon.in_transaction
    fk_awal = kon.execute("PRAGMA foreign_keys").fetchone()[0]
    if not mandiri and fk_awal:
        raise sqlite3.IntegrityError("rebuild membutuhkan transaksi migrasi dengan FK nonaktif")
    try:
        if mandiri:
            kon.execute("PRAGMA foreign_keys = OFF")
            kon.execute("BEGIN IMMEDIATE")
            # Koneksi lain mungkin sudah menyelesaikan migrasi sebelum lock.
            if not _perlu_rebuild(kon):
                kon.commit()
                return False
        sebelum = _sidik_baris(kon, "konteks_butir")
        kon.execute(_ddl_tabel_baru())
        kon.execute(
            f"INSERT INTO konteks_butir_baru ({_KOLOM}) "
            f"SELECT {_KOLOM} FROM konteks_butir ORDER BY sesi_soal_id"
        )
        sesudah = _sidik_baris(kon, "konteks_butir_baru")
        if sebelum != sesudah:
            raise sqlite3.IntegrityError("sidik baris konteks_butir berubah saat rebuild")
        kon.execute("DROP TABLE konteks_butir")
        kon.execute("ALTER TABLE konteks_butir_baru RENAME TO konteks_butir")
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise sqlite3.IntegrityError("rebuild konteks_butir meninggalkan FK rusak")
        if mandiri:
            kon.commit()
    except Exception:
        if mandiri:
            kon.rollback()
        raise
    finally:
        if mandiri:
            kon.execute(f"PRAGMA foreign_keys = {fk_awal}")
    return True

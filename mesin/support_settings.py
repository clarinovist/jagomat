"""Konfigurasi dukungan privat dengan migrasi opt-in dan reader fail-closed."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Optional

import admin_store
import auth
from json_storage import transaksi_json

VERSI_SCHEMA = 1
WHATSAPP_AWAL = "082137111988"
JAM_AWAL = "weekday_0900_1700_wib"
SLA_RESPONS_AWAL = 1
SLA_STATUS_AWAL = 3
JAM_LAYANAN = {
    JAM_AWAL: "Senin–Jumat, 09.00–17.00 WIB",
}
PLACEHOLDER = frozenset((
    "0800000000", "0811111111", "0812345678", "08123456789",
    "081234567890", "089876543210", "089999999999",
))

DDL = """
CREATE TABLE dukungan_schema (
    id INTEGER PRIMARY KEY CHECK(id=1),
    versi INTEGER NOT NULL CHECK(versi=1),
    dipasang INTEGER NOT NULL CHECK(dipasang>=0)
);
CREATE TABLE dukungan_konfigurasi (
    id INTEGER PRIMARY KEY CHECK(id=1),
    whatsapp_digits TEXT NOT NULL CHECK(
        whatsapp_digits GLOB '08[0-9]*' AND
        length(whatsapp_digits) BETWEEN 10 AND 15 AND
        whatsapp_digits NOT GLOB '*[^0-9]*'
    ),
    jam_layanan_kode TEXT NOT NULL CHECK(jam_layanan_kode='weekday_0900_1700_wib'),
    sla_respons_hari INTEGER NOT NULL CHECK(sla_respons_hari BETWEEN 1 AND 30),
    sla_status_hari INTEGER NOT NULL CHECK(sla_status_hari BETWEEN 1 AND 30),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    diperbarui INTEGER NOT NULL CHECK(diperbarui>=0),
    actor_id TEXT NOT NULL
);
CREATE TABLE dukungan_audit (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    revisi_awal INTEGER NOT NULL CHECK(revisi_awal>=1),
    revisi_hasil INTEGER NOT NULL CHECK(revisi_hasil=revisi_awal+1),
    sidik_lama TEXT NOT NULL CHECK(length(sidik_lama)=64),
    sidik_baru TEXT NOT NULL CHECK(length(sidik_baru)=64),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0)
);
CREATE TRIGGER dukungan_config_tolak_delete BEFORE DELETE ON dukungan_konfigurasi
BEGIN SELECT RAISE(ABORT,'konfigurasi dukungan tidak boleh dihapus'); END;
CREATE TRIGGER dukungan_schema_tolak_update BEFORE UPDATE ON dukungan_schema
BEGIN SELECT RAISE(ABORT,'schema dukungan immutable'); END;
CREATE TRIGGER dukungan_schema_tolak_delete BEFORE DELETE ON dukungan_schema
BEGIN SELECT RAISE(ABORT,'schema dukungan immutable'); END;
CREATE TRIGGER dukungan_audit_tolak_update BEFORE UPDATE ON dukungan_audit
BEGIN SELECT RAISE(ABORT,'audit dukungan immutable'); END;
CREATE TRIGGER dukungan_audit_tolak_delete BEFORE DELETE ON dukungan_audit
BEGIN SELECT RAISE(ABORT,'audit dukungan immutable'); END;
CREATE TRIGGER dukungan_audit_tolak_replace BEFORE INSERT ON dukungan_audit
WHEN EXISTS(SELECT 1 FROM dukungan_audit WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'audit dukungan duplikat'); END;
"""


@dataclass(frozen=True)
class KonfigurasiDukungan:
    whatsapp_digits: str
    jam_layanan_kode: str
    sla_respons_hari: int
    sla_status_hari: int
    revisi: int
    diperbarui: int
    actor_id: str


@dataclass(frozen=True)
class DukunganPublik:
    whatsapp_label: str
    whatsapp_url: str
    jam_layanan_label: str
    sla_respons_label: str
    sla_status_label: str


def _struktur(kon):
    return tuple(tuple(row) for row in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE "
        "tbl_name GLOB 'dukungan_*' ORDER BY type,name"
    ))


def validasi_schema(kon) -> bool:
    """Absent sah untuk binary sebelum migrasi; parsial/berbeda selalu ditolak."""
    aktual = _struktur(kon)
    if not aktual:
        return False
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if aktual != _struktur(acuan):
            raise ValueError("struktur dukungan tidak lengkap")
    finally:
        acuan.close()
    row = kon.execute("SELECT versi FROM dukungan_schema WHERE id=1").fetchone()
    if row is None or row[0] != VERSI_SCHEMA:
        raise ValueError("versi dukungan tidak sah")
    return True


def _jalankan_ddl(kon, skrip):
    bagian = ""
    for baris in skrip.splitlines(keepends=True):
        bagian += baris
        if sqlite3.complete_statement(bagian):
            kon.execute(bagian)
            bagian = ""
    if bagian.strip():
        raise RuntimeError("DDL dukungan tidak lengkap")


def migrasikan(path, *, sekarang: int) -> None:
    """Pasang schema dukungan pada admin7/8/9 tanpa mengubah user_version."""
    if type(sekarang) is not int or sekarang < 0:
        raise ValueError("waktu migrasi tidak sah")
    tujuan = Path(path)
    if not tujuan.exists():
        raise admin_store.StoreBelumSiap("store admin tidak tersedia")
    with admin_store._transaksi(tujuan) as kon:
        if not _struktur(kon):
            _jalankan_ddl(kon, DDL)
            kon.execute("INSERT INTO dukungan_schema VALUES(1,?,?)", (VERSI_SCHEMA, sekarang))
            kon.execute(
                "INSERT INTO dukungan_konfigurasi VALUES(1,?,?,?,?,?,?,?)",
                (WHATSAPP_AWAL, JAM_AWAL, SLA_RESPONS_AWAL, SLA_STATUS_AWAL,
                 1, sekarang, "sistem_migrasi"),
            )
        validasi_schema(kon)
        if (kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or kon.execute("PRAGMA foreign_key_check").fetchone()):
            raise admin_store.StoreBelumSiap("integritas migrasi dukungan gagal")


def normalisasi_nomor(nilai: str) -> str:
    if type(nilai) is not str or not nilai or nilai != nilai.strip():
        raise ValueError("nomor WhatsApp tidak sah")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in nilai):
        raise ValueError("nomor WhatsApp tidak sah")
    if not re.fullmatch(r"[0-9 -]+", nilai) or any(not ch.isascii() for ch in nilai):
        raise ValueError("nomor WhatsApp tidak sah")
    digit = nilai.replace(" ", "").replace("-", "")
    if (re.fullmatch(r"08[0-9]{8,13}", digit) is None
            or digit in PLACEHOLDER
            or len(set(digit[2:])) == 1):
        raise ValueError("nomor WhatsApp tidak sah")
    return digit


def _sla(nilai) -> int:
    if type(nilai) is not int or not 1 <= nilai <= 30:
        raise ValueError("SLA dukungan tidak sah")
    return nilai


def konfigurasi(whatsapp, jam_layanan, sla_respons, sla_status, *, revisi, diperbarui, actor_id):
    if jam_layanan not in JAM_LAYANAN:
        raise ValueError("jam layanan tidak sah")
    if type(revisi) is not int or revisi < 1 or type(diperbarui) is not int or diperbarui < 0:
        raise ValueError("metadata dukungan tidak sah")
    if type(actor_id) is not str or not actor_id:
        raise ValueError("aktor dukungan tidak sah")
    return KonfigurasiDukungan(
        normalisasi_nomor(whatsapp), jam_layanan, _sla(sla_respons),
        _sla(sla_status), revisi, diperbarui, actor_id,
    )


def _dari_row(row) -> KonfigurasiDukungan:
    return konfigurasi(
        row["whatsapp_digits"], row["jam_layanan_kode"],
        row["sla_respons_hari"], row["sla_status_hari"],
        revisi=row["revisi"], diperbarui=row["diperbarui"], actor_id=row["actor_id"],
    )


def baca(path=None) -> Optional[KonfigurasiDukungan]:
    """Reader fail-closed dan read-only; tidak membuat atau memperbaiki DB."""
    try:
        with admin_store.buka_baca(path) as kon:
            if not validasi_schema(kon):
                return None
            row = kon.execute("SELECT * FROM dukungan_konfigurasi WHERE id=1").fetchone()
            return None if row is None else _dari_row(row)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, sqlite3.Error):
        return None


def sidik_konfigurasi(nilai: KonfigurasiDukungan) -> str:
    payload = [
        nilai.whatsapp_digits, nilai.jam_layanan_kode,
        nilai.sla_respons_hari, nilai.sla_status_hari, nilai.revisi,
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def ubah(path, path_auth, principal, *, operasi, revisi, sidik_awal, whatsapp,
         jam_layanan, sla_respons, sla_status, sekarang, failpoint=None):
    """Ubah konfigurasi+audit atomik; principal dikunci dan replay aman."""
    from subscription import identitas
    identitas(operasi, "operasi")
    if type(sidik_awal) is not str or re.fullmatch(r"[0-9a-f]{64}", sidik_awal) is None:
        raise ValueError("snapshot dukungan tidak sah")
    if type(sekarang) is not int or sekarang < 0:
        raise ValueError("waktu dukungan tidak sah")
    # Validasi seluruh input sebelum lock/tulis.
    tujuan = konfigurasi(
        whatsapp, jam_layanan, sla_respons, sla_status,
        revisi=revisi, diperbarui=sekarang, actor_id=principal.id_akun,
    )
    import admin_launch_service
    with transaksi_json(path_auth) as terkunci:
        _mentah, daftar, _multi = __import__("admin_accounts")._baca_state_terkunci(terkunci)
        admin_launch_service.principal_hidup(daftar, principal)
        with admin_store._transaksi(path) as kon:
            if not validasi_schema(kon):
                raise admin_store.StoreBelumSiap("schema dukungan belum dipasang")
            row = kon.execute("SELECT * FROM dukungan_konfigurasi WHERE id=1").fetchone()
            if row is None:
                raise admin_store.StoreBelumSiap("konfigurasi dukungan tidak tersedia")
            lama = _dari_row(row)
            sidik_lama = sidik_konfigurasi(lama)
            sidik_baru = hashlib.sha256(json.dumps([
                tujuan.whatsapp_digits, tujuan.jam_layanan_kode,
                tujuan.sla_respons_hari, tujuan.sla_status_hari,
            ], separators=(",", ":")).encode()).hexdigest()
            audit = kon.execute("SELECT * FROM dukungan_audit WHERE operasi_id=?", (operasi,)).fetchone()
            if audit is not None:
                cocok = (
                    audit["actor_id"] == principal.id_akun
                    and audit["actor_revisi"] == principal.revisi_auth
                    and audit["revisi_awal"] == revisi
                    and audit["sidik_lama"] == sidik_awal
                    and audit["sidik_baru"] == sidik_baru
                )
                if not cocok:
                    raise admin_store.KonflikOperasi("operasi dukungan berbeda")
                hasil = kon.execute("SELECT * FROM dukungan_konfigurasi WHERE id=1").fetchone()
                if hasil is None or hasil["revisi"] != audit["revisi_hasil"]:
                    raise admin_store.KonflikOperasi("hasil dukungan tidak cocok")
                return _dari_row(hasil)
            if revisi != lama.revisi or sidik_awal != sidik_lama:
                raise admin_store.KonflikOperasi("revisi dukungan berubah")
            baru = revisi + 1
            kursor = kon.execute(
                "UPDATE dukungan_konfigurasi SET whatsapp_digits=?,jam_layanan_kode=?,"
                "sla_respons_hari=?,sla_status_hari=?,revisi=?,diperbarui=?,actor_id=? "
                "WHERE id=1 AND revisi=?",
                (tujuan.whatsapp_digits, tujuan.jam_layanan_kode,
                 tujuan.sla_respons_hari, tujuan.sla_status_hari, baru,
                 sekarang, principal.id_akun, revisi),
            )
            if kursor.rowcount != 1:
                raise admin_store.KonflikOperasi("revisi dukungan berubah")
            if failpoint == "setelah_update":
                raise RuntimeError("failpoint setelah update")
            kon.execute(
                "INSERT INTO dukungan_audit VALUES(?,?,?,?,?,?,?,?)",
                (operasi, principal.id_akun, principal.revisi_auth, revisi,
                 baru, sidik_awal, sidik_baru, sekarang),
            )
            return _dari_row(kon.execute("SELECT * FROM dukungan_konfigurasi WHERE id=1").fetchone())


def _kelompok_nomor(digit: str) -> str:
    sisa = digit[4:]
    bagian = [digit[:4]]
    while len(sisa) > 4:
        bagian.append(sisa[:4])
        sisa = sisa[4:]
    bagian.append(sisa)
    return " ".join(bagian)


def proyeksi_publik(nilai: Optional[KonfigurasiDukungan]) -> Optional[DukunganPublik]:
    if nilai is None:
        return None
    # Validasi ulang di batas output: object buatan caller tidak otomatis dipercaya.
    cfg = konfigurasi(
        nilai.whatsapp_digits, nilai.jam_layanan_kode,
        nilai.sla_respons_hari, nilai.sla_status_hari,
        revisi=nilai.revisi, diperbarui=nilai.diperbarui, actor_id=nilai.actor_id,
    )
    internasional = "62" + cfg.whatsapp_digits[1:]
    return DukunganPublik(
        _kelompok_nomor(cfg.whatsapp_digits),
        "https://wa.me/" + internasional,
        JAM_LAYANAN[cfg.jam_layanan_kode],
        "Respons awal maksimal %d hari kerja" % cfg.sla_respons_hari,
        "Status atau penyelesaian awal maksimal %d hari kerja" % cfg.sla_status_hari,
    )


def baca_publik(path=None) -> Optional[DukunganPublik]:
    try:
        return proyeksi_publik(baca(path))
    except (ValueError, TypeError):
        return None


def main(argv=None) -> int:
    """Migrator operator eksplisit; tidak pernah dipanggil startup atau GET."""
    import argparse
    import time
    parser = argparse.ArgumentParser(description="Pasang schema konfigurasi dukungan")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    args = parser.parse_args(argv)
    migrasikan(Path(args.database), sekarang=int(time.time()))
    print("Migrasi dukungan selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

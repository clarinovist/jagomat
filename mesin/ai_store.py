"""SQLite privat untuk konfigurasi, reservasi biaya, dan audit AI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sqlite3
import time

import ai_policy

BAWAAN = Path(os.environ.get("AI_BERKAS_DB", "/data/ai-control.db"))
VERSI_SKEMA = 1

_DDL = """
CREATE TABLE IF NOT EXISTS konfigurasi (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revisi INTEGER NOT NULL CHECK (revisi >= 1),
    dihentikan INTEGER NOT NULL CHECK (dihentikan IN (0,1)),
    request_akun_harian INTEGER NOT NULL CHECK (request_akun_harian >= 0),
    uji_harian INTEGER NOT NULL CHECK (uji_harian >= 0),
    uji_cooldown_detik INTEGER NOT NULL CHECK (uji_cooldown_detik >= 0),
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS batas_fitur (
    fitur TEXT PRIMARY KEY,
    aktif INTEGER NOT NULL CHECK (aktif IN (0,1)),
    batas_harian INTEGER NOT NULL CHECK (batas_harian >= 0),
    batas_bulanan INTEGER NOT NULL CHECK (batas_bulanan >= 0)
);
CREATE TABLE IF NOT EXISTS audit_konfigurasi (
    id INTEGER PRIMARY KEY,
    revisi INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    field TEXT NOT NULL,
    lama TEXT NOT NULL,
    baru TEXT NOT NULL,
    dibuat INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_waktu ON audit_konfigurasi(dibuat);
CREATE TABLE IF NOT EXISTS ledger (
    operasi_id TEXT PRIMARY KEY,
    fitur TEXT NOT NULL,
    bucket_akun TEXT,
    revisi INTEGER NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('dicadangkan','selesai','gagal','tak_pasti','dibatalkan')),
    reservation INTEGER NOT NULL CHECK(reservation >= 0),
    biaya INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    durasi_ms INTEGER,
    kategori TEXT,
    periode_hari TEXT NOT NULL,
    periode_bulan TEXT NOT NULL,
    dibuat INTEGER NOT NULL,
    selesai INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ledger_periode ON ledger(periode_hari, periode_bulan, fitur);
CREATE INDEX IF NOT EXISTS idx_ledger_akun ON ledger(bucket_akun, periode_hari);
"""


class Ditolak(RuntimeError):
    """Admission AI ditolak secara aman."""


@dataclass(frozen=True)
class Reservasi:
    operasi_id: str
    fitur: str
    revisi: int
    reservation: int


def buka(path=None, *, timeout: float = 5.0):
    tujuan = Path(path) if path is not None else BAWAAN
    kon = sqlite3.connect(tujuan, timeout=timeout)
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys = ON")
    kon.execute("PRAGMA busy_timeout = 5000")
    return kon


def siapkan(path=None, *, sekarang=None):
    tujuan = Path(path) if path is not None else BAWAAN
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with buka(tujuan) as kon:
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
        if versi > VERSI_SKEMA:
            raise RuntimeError("skema pengaturan AI lebih baru dari aplikasi")
        kon.executescript(_DDL)
        kon.execute(
            "INSERT OR IGNORE INTO konfigurasi VALUES (1,1,0,?,?,?,?)",
            (ai_policy.DEFAULT_REQUEST_AKUN_HARIAN, ai_policy.DEFAULT_UJI_HARIAN,
             ai_policy.DEFAULT_UJI_COOLDOWN_DETIK, kini),
        )
        for fitur, (harian, bulanan) in ai_policy.DEFAULT_LIMIT.items():
            kon.execute(
                "INSERT OR IGNORE INTO batas_fitur VALUES (?,?,?,?)",
                (fitur, 1, harian, bulanan),
            )
        kon.execute("PRAGMA user_version = 1")
    try:
        tujuan.chmod(0o600)
    except OSError:
        pass


def konfigurasi(kon):
    utama = kon.execute("SELECT * FROM konfigurasi WHERE id=1").fetchone()
    batas = {b["fitur"]: b for b in kon.execute("SELECT * FROM batas_fitur")}
    if utama is None or set(batas) != {"global", *ai_policy.FITUR}:
        raise RuntimeError("konfigurasi AI belum lengkap")
    return utama, batas


def _periode(sekarang):
    dt = datetime.fromtimestamp(sekarang, timezone(timedelta(hours=7)))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m")


def _terpakai(kon, *, hari, bulan, fitur=None):
    klausa = " AND fitur = ?" if fitur else ""
    arg_hari = (hari, fitur) if fitur else (hari,)
    arg_bulan = (bulan, fitur) if fitur else (bulan,)
    ekspresi = "COALESCE(biaya,reservation)"
    harian = kon.execute(
        f"SELECT COALESCE(SUM({ekspresi}),0) FROM ledger WHERE periode_hari=? "
        f"AND status!='dibatalkan'{klausa}", arg_hari,
    ).fetchone()[0]
    bulanan = kon.execute(
        f"SELECT COALESCE(SUM({ekspresi}),0) FROM ledger WHERE periode_bulan=? "
        f"AND status!='dibatalkan'{klausa}", arg_bulan,
    ).fetchone()[0]
    return int(harian), int(bulanan)


def reservasi(path, operasi_id, fitur, bucket_akun, model, jumlah, *, sekarang=None):
    if fitur not in ai_policy.FITUR or jumlah < 0:
        raise ValueError("Reservasi AI tidak sah.")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    hari, bulan = _periode(kini)
    with buka(path) as kon:
        kon.execute("BEGIN IMMEDIATE")
        lama = kon.execute("SELECT * FROM ledger WHERE operasi_id=?", (operasi_id,)).fetchone()
        if lama is not None:
            if lama["fitur"] != fitur or lama["bucket_akun"] != bucket_akun:
                raise Ditolak("ID operasi tidak cocok.")
            raise Ditolak("Permintaan ini sudah pernah diproses.")
        utama, batas = konfigurasi(kon)
        if utama["dihentikan"] or not batas[fitur]["aktif"]:
            raise Ditolak("Fitur AI sedang dihentikan.")
        global_h, global_b = _terpakai(kon, hari=hari, bulan=bulan)
        fitur_h, fitur_b = _terpakai(kon, hari=hari, bulan=bulan, fitur=fitur)
        if global_h + jumlah > batas["global"]["batas_harian"]:
            raise Ditolak("Kuota AI harian habis.")
        batas_bulan = min(batas["global"]["batas_bulanan"], ai_policy.hard_ceiling_micro_usd())
        if global_b + jumlah > batas_bulan:
            raise Ditolak("Kuota AI bulanan habis.")
        if fitur_h + jumlah > batas[fitur]["batas_harian"] or fitur_b + jumlah > batas[fitur]["batas_bulanan"]:
            raise Ditolak("Kuota fitur AI habis.")
        if bucket_akun:
            jumlah_akun = kon.execute(
                "SELECT COUNT(*) FROM ledger WHERE bucket_akun=? AND periode_hari=? AND status!='dibatalkan'",
                (bucket_akun, hari),
            ).fetchone()[0]
            if jumlah_akun >= utama["request_akun_harian"]:
                raise Ditolak("Batas request harian akun tercapai.")
        if fitur == "uji_sintetis":
            jumlah_uji = kon.execute(
                "SELECT COUNT(*) FROM ledger WHERE fitur='uji_sintetis' AND periode_hari=? AND status!='dibatalkan'",
                (hari,),
            ).fetchone()[0]
            terakhir = kon.execute(
                "SELECT MAX(dibuat) FROM ledger WHERE fitur='uji_sintetis' AND status!='dibatalkan'"
            ).fetchone()[0]
            if jumlah_uji >= utama["uji_harian"]:
                raise Ditolak("Batas tes koneksi harian tercapai.")
            if terakhir is not None and kini - int(terakhir) < utama["uji_cooldown_detik"]:
                raise Ditolak("Tes koneksi masih dalam masa tunggu.")
        kon.execute(
            """INSERT INTO ledger(operasi_id,fitur,bucket_akun,revisi,model,status,
               reservation,periode_hari,periode_bulan,dibuat)
               VALUES(?,?,?,?,?,'dicadangkan',?,?,?,?)""",
            (operasi_id, fitur, bucket_akun, utama["revisi"], model, jumlah,
             hari, bulan, kini),
        )
        return Reservasi(operasi_id, fitur, utama["revisi"], jumlah)


def admission_masih_sah(path, operasi_id):
    """False bila penghentian/revisi berubah selama request berada di jaringan."""
    with buka(path) as kon:
        baris = kon.execute(
            """SELECT l.revisi, l.fitur, k.revisi AS revisi_kini, k.dihentikan,
                      b.aktif
               FROM ledger l JOIN konfigurasi k ON k.id=1
               JOIN batas_fitur b ON b.fitur=l.fitur
               WHERE l.operasi_id=?""", (operasi_id,),
        ).fetchone()
        return bool(
            baris and baris["revisi"] == baris["revisi_kini"]
            and not baris["dihentikan"] and baris["aktif"]
        )


def selesaikan(path, operasi_id, *, status, biaya=None, input_tokens=None,
               output_tokens=None, durasi_ms=None, kategori=None, sekarang=None):
    if status not in ("selesai", "gagal", "tak_pasti", "dibatalkan"):
        raise ValueError("Status ledger tidak sah.")
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with buka(path) as kon:
        kon.execute("BEGIN IMMEDIATE")
        lama = kon.execute("SELECT status FROM ledger WHERE operasi_id=?", (operasi_id,)).fetchone()
        if lama is None:
            raise LookupError("Operasi AI tidak ditemukan.")
        if lama["status"] != "dicadangkan":
            return False
        kon.execute(
            """UPDATE ledger SET status=?, biaya=?, input_tokens=?, output_tokens=?,
               durasi_ms=?, kategori=?, selesai=? WHERE operasi_id=?""",
            (status, biaya, input_tokens, output_tokens, durasi_ms, kategori, kini, operasi_id),
        )
        return True


def ubah(path, data, actor_id, *, revisi, sekarang=None):
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with buka(path) as kon:
        kon.execute("BEGIN IMMEDIATE")
        utama, batas = konfigurasi(kon)
        if int(utama["revisi"]) != int(revisi):
            raise Ditolak("Pengaturan berubah di tab lain. Tinjau ulang.")
        field_lama = {
            "dihentikan": str(utama["dihentikan"]),
            "request_akun_harian": str(utama["request_akun_harian"]),
            "uji_harian": str(utama["uji_harian"]),
            "uji_cooldown_detik": str(utama["uji_cooldown_detik"]),
        }
        baru = {}
        for nama in field_lama:
            nilai = int(data[nama])
            if nilai < 0:
                raise ValueError("Batas tidak boleh negatif.")
            baru[nama] = nilai
        for fitur in ai_policy.FITUR:
            baru[f"aktif_{fitur}"] = int(data[f"aktif_{fitur}"])
        for fitur in ("global", *ai_policy.FITUR):
            baru[f"harian_{fitur}"] = int(data[f"harian_{fitur}"])
            baru[f"bulanan_{fitur}"] = int(data[f"bulanan_{fitur}"])
            if baru[f"harian_{fitur}"] < 0 or baru[f"bulanan_{fitur}"] < 0:
                raise ValueError("Pagu tidak boleh negatif.")
        revisi_baru = int(revisi) + 1
        kon.execute(
            """UPDATE konfigurasi SET revisi=?,dihentikan=?,request_akun_harian=?,
               uji_harian=?,uji_cooldown_detik=?,diperbarui=? WHERE id=1""",
            (revisi_baru, baru["dihentikan"], baru["request_akun_harian"],
             baru["uji_harian"], baru["uji_cooldown_detik"], kini),
        )
        perubahan = []
        for nama, lama in field_lama.items():
            if lama != str(baru[nama]):
                perubahan.append((nama, lama, str(baru[nama])))
        for fitur in ai_policy.FITUR:
            lama = batas[fitur]
            nilai = baru[f"aktif_{fitur}"]
            if int(lama["aktif"]) != nilai:
                perubahan.append((f"aktif_{fitur}", str(lama["aktif"]), str(nilai)))
        for fitur in ("global", *ai_policy.FITUR):
            lama = batas[fitur]
            for kolom in ("harian", "bulanan"):
                nilai = baru[f"{kolom}_{fitur}"]
                db_kolom = f"batas_{kolom}"
                if int(lama[db_kolom]) != nilai:
                    perubahan.append((f"{kolom}_{fitur}", str(lama[db_kolom]), str(nilai)))
            aktif = baru.get(f"aktif_{fitur}", 1)
            kon.execute(
                "UPDATE batas_fitur SET aktif=?,batas_harian=?,batas_bulanan=? WHERE fitur=?",
                (aktif, baru[f"harian_{fitur}"], baru[f"bulanan_{fitur}"], fitur),
            )
        kon.executemany(
            "INSERT INTO audit_konfigurasi(revisi,actor_id,field,lama,baru,dibuat) VALUES(?,?,?,?,?,?)",
            [(revisi_baru, actor_id, n, l, b, kini) for n, l, b in perubahan],
        )
        return revisi_baru


def ringkasan(kon, *, sekarang=None):
    kini = int(time.time()) if sekarang is None else int(sekarang)
    hari, bulan = _periode(kini)
    hasil = {}
    for fitur in ("global", *ai_policy.FITUR):
        h, b = _terpakai(kon, hari=hari, bulan=bulan,
                         fitur=None if fitur == "global" else fitur)
        hasil[fitur] = {"harian": h, "bulanan": b}
    return hasil


def purge(path=None, *, sekarang=None):
    kini = int(time.time()) if sekarang is None else int(sekarang)
    with buka(path) as kon:
        kon.execute("DELETE FROM ledger WHERE dibuat < ? AND status!='dicadangkan'", (kini - 90 * 86400,))
        kon.execute("DELETE FROM audit_konfigurasi WHERE dibuat < ?", (kini - 180 * 86400,))

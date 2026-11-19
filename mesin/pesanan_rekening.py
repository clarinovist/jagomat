"""Rekening tujuan transfer Paket Coba: konfigurasi admin privat, migrasi opt-in, fail-closed.

Mengikuti pola `support_settings` (singleton + revisi optimistik + audit append-only,
tanpa bump `user_version`, absent sah, parsial/berbeda ditolak), dengan dua selisih
yang disengaja:

* TIDAK ada rekening bawaan: rekening bank bukan nilai yang boleh ditebak. Sampai admin
  mengisinya, `baca`/`baca_publik` mengembalikan None dan halaman pembayaran transfer
  tidak boleh tampil. Penulisan pertama memakai `revisi=0` dan `SIDIK_KOSONG`.
* Audit tidak menyimpan nomor rekening, hanya sidik isi.

Namespace tabel `rekening_*`. Modul ini bukan bagian domain `pesanan_*` (ia memakai kunci
sesi admin `auth`), jadi tidak masuk daftar isolasi domain pesanan.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Optional

import admin_store
from json_storage import transaksi_json

VERSI_SCHEMA = 1
SIDIK_KOSONG = "0" * 64
BATAS_NAMA_BANK = (2, 40)
BATAS_ATAS_NAMA = (2, 60)
BATAS_NOMOR = (5, 20)
KELOMPOK_NOMOR = 4
_PUNKTUASI = frozenset(".,&'()/-")
_POLA_SIDIK = re.compile(r"[0-9a-f]{64}")
_POLA_OPERASI = re.compile(r"[A-Za-z0-9_-]{8,46}")
_POLA_NOMOR = re.compile(r"[0-9]{%d,%d}" % BATAS_NOMOR)

DDL = """
CREATE TABLE rekening_schema (
    id INTEGER PRIMARY KEY CHECK(id=1),
    versi INTEGER NOT NULL CHECK(versi=1),
    dipasang INTEGER NOT NULL CHECK(dipasang>=0)
);
CREATE TABLE rekening_konfigurasi (
    id INTEGER PRIMARY KEY CHECK(id=1),
    nama_bank TEXT NOT NULL CHECK(length(nama_bank) BETWEEN 2 AND 40),
    nomor_rekening TEXT NOT NULL CHECK(
        length(nomor_rekening) BETWEEN 5 AND 20 AND nomor_rekening NOT GLOB '*[^0-9]*'
    ),
    atas_nama TEXT NOT NULL CHECK(length(atas_nama) BETWEEN 2 AND 60),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    diperbarui INTEGER NOT NULL CHECK(diperbarui>=0),
    actor_id TEXT NOT NULL
);
CREATE TABLE rekening_audit (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    revisi_awal INTEGER NOT NULL CHECK(revisi_awal>=0),
    revisi_hasil INTEGER NOT NULL CHECK(revisi_hasil=revisi_awal+1),
    sidik_lama TEXT NOT NULL CHECK(length(sidik_lama)=64),
    sidik_baru TEXT NOT NULL CHECK(length(sidik_baru)=64),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0)
);
CREATE TRIGGER rekening_config_tolak_delete BEFORE DELETE ON rekening_konfigurasi
BEGIN SELECT RAISE(ABORT,'konfigurasi rekening tidak boleh dihapus'); END;
CREATE TRIGGER rekening_schema_tolak_update BEFORE UPDATE ON rekening_schema
BEGIN SELECT RAISE(ABORT,'schema rekening immutable'); END;
CREATE TRIGGER rekening_schema_tolak_delete BEFORE DELETE ON rekening_schema
BEGIN SELECT RAISE(ABORT,'schema rekening immutable'); END;
CREATE TRIGGER rekening_audit_tolak_update BEFORE UPDATE ON rekening_audit
BEGIN SELECT RAISE(ABORT,'audit rekening immutable'); END;
CREATE TRIGGER rekening_audit_tolak_delete BEFORE DELETE ON rekening_audit
BEGIN SELECT RAISE(ABORT,'audit rekening immutable'); END;
CREATE TRIGGER rekening_audit_tolak_replace BEFORE INSERT ON rekening_audit
WHEN EXISTS(SELECT 1 FROM rekening_audit WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'audit rekening duplikat'); END;
"""


@dataclass(frozen=True)
class KonfigurasiRekening:
    nama_bank: str
    nomor_rekening: str
    atas_nama: str
    revisi: int
    diperbarui: int
    actor_id: str


@dataclass(frozen=True)
class RekeningPublik:
    nama_bank: str
    nomor_rekening: str
    nomor_label: str
    atas_nama: str


def _struktur(kon):
    return tuple(tuple(row) for row in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE "
        "tbl_name GLOB 'rekening_*' ORDER BY type,name"))


def validasi_schema(kon) -> bool:
    """Absent sah untuk binary sebelum migrasi; parsial/berbeda selalu ditolak."""
    aktual = _struktur(kon)
    if not aktual:
        return False
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if aktual != _struktur(acuan):
            raise ValueError("struktur rekening tidak lengkap")
    finally:
        acuan.close()
    row = kon.execute("SELECT versi FROM rekening_schema WHERE id=1").fetchone()
    if row is None or row[0] != VERSI_SCHEMA:
        raise ValueError("versi rekening tidak sah")
    return True


def migrasikan(path, *, sekarang: int) -> None:
    """Pasang schema rekening pada admin7/8/9 tanpa mengubah user_version dan tanpa seed."""
    if type(sekarang) is not int or sekarang < 0:
        raise ValueError("waktu migrasi tidak sah")
    tujuan = Path(path)
    if not tujuan.exists():
        raise admin_store.StoreBelumSiap("store admin tidak tersedia")
    import admin_store_core
    with admin_store._transaksi(tujuan) as kon:
        if not _struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
            kon.execute("INSERT INTO rekening_schema VALUES(1,?,?)", (VERSI_SCHEMA, sekarang))
        validasi_schema(kon)
        if (kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or kon.execute("PRAGMA foreign_key_check").fetchone()):
            raise admin_store.StoreBelumSiap("integritas migrasi rekening gagal")


def _teks_nama(nilai, label: str, batas) -> str:
    if (type(nilai) is not str or nilai != nilai.strip() or "  " in nilai
            or not batas[0] <= len(nilai) <= batas[1]):
        raise ValueError("%s tidak sah" % label)
    if any(not (ch.isalnum() or ch in _PUNKTUASI or ch == " ") for ch in nilai):
        raise ValueError("%s tidak sah" % label)
    return nilai


def normalisasi_nama_bank(nilai) -> str:
    return _teks_nama(nilai, "nama bank", BATAS_NAMA_BANK)


def normalisasi_atas_nama(nilai) -> str:
    return _teks_nama(nilai, "atas nama", BATAS_ATAS_NAMA)


def normalisasi_nomor_rekening(nilai) -> str:
    """Hanya digit ASCII 5..20, bukan satu digit berulang (tebakan/placeholder)."""
    if type(nilai) is not str or _POLA_NOMOR.fullmatch(nilai) is None or len(set(nilai)) == 1:
        raise ValueError("nomor rekening tidak sah")
    return nilai


def konfigurasi(nama_bank, nomor_rekening, atas_nama, *, revisi, diperbarui, actor_id):
    if type(revisi) is not int or revisi < 1 or type(diperbarui) is not int or diperbarui < 0:
        raise ValueError("metadata rekening tidak sah")
    if type(actor_id) is not str or not actor_id:
        raise ValueError("aktor rekening tidak sah")
    return KonfigurasiRekening(
        normalisasi_nama_bank(nama_bank), normalisasi_nomor_rekening(nomor_rekening),
        normalisasi_atas_nama(atas_nama), revisi, diperbarui, actor_id)


def _dari_row(row) -> KonfigurasiRekening:
    return konfigurasi(row["nama_bank"], row["nomor_rekening"], row["atas_nama"],
                       revisi=row["revisi"], diperbarui=row["diperbarui"], actor_id=row["actor_id"])


def baca(path=None) -> Optional[KonfigurasiRekening]:
    """Reader fail-closed dan read-only; None bila belum dipasang, belum diisi, atau rusak."""
    try:
        with admin_store.buka_baca(path) as kon:
            if not validasi_schema(kon):
                return None
            row = kon.execute("SELECT * FROM rekening_konfigurasi WHERE id=1").fetchone()
            return None if row is None else _dari_row(row)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, sqlite3.Error):
        return None


def _sidik(payload) -> str:
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def sidik_konfigurasi(nilai: Optional[KonfigurasiRekening]) -> str:
    """Sidik snapshot (termasuk revisi) untuk optimistic concurrency; None -> SIDIK_KOSONG."""
    if nilai is None:
        return SIDIK_KOSONG
    return _sidik([nilai.nama_bank, nilai.nomor_rekening, nilai.atas_nama, nilai.revisi])


def _sidik_isi(nilai: KonfigurasiRekening) -> str:
    return _sidik([nilai.nama_bank, nilai.nomor_rekening, nilai.atas_nama])


def _periksa_ubah(operasi, revisi, sidik_awal, sekarang) -> None:
    if type(operasi) is not str or _POLA_OPERASI.fullmatch(operasi) is None:
        raise ValueError("identitas operasi rekening tidak sah")
    if type(revisi) is not int or revisi < 0:
        raise ValueError("revisi rekening tidak sah")
    if type(sidik_awal) is not str or _POLA_SIDIK.fullmatch(sidik_awal) is None:
        raise ValueError("snapshot rekening tidak sah")
    if type(sekarang) is not int or sekarang < 0:
        raise ValueError("waktu rekening tidak sah")


def _replay(kon, audit, principal, revisi, sidik_awal, tujuan):
    cocok = (audit["actor_id"] == principal.id_akun
             and audit["actor_revisi"] == principal.revisi_auth
             and audit["revisi_awal"] == revisi and audit["sidik_lama"] == sidik_awal
             and audit["sidik_baru"] == _sidik_isi(tujuan))
    if not cocok:
        raise admin_store.KonflikOperasi("operasi rekening berbeda")
    hasil = kon.execute("SELECT * FROM rekening_konfigurasi WHERE id=1").fetchone()
    if hasil is None or hasil["revisi"] != audit["revisi_hasil"]:
        raise admin_store.KonflikOperasi("hasil rekening tidak cocok")
    return _dari_row(hasil)


def _tulis(kon, row, tujuan, revisi, sekarang, principal) -> None:
    """Tulis konfigurasi: sisip pertama (row None) atau UPDATE dengan penjaga revisi."""
    isi = (tujuan.nama_bank, tujuan.nomor_rekening, tujuan.atas_nama, revisi + 1, sekarang,
           principal.id_akun)
    if row is None:
        kon.execute("INSERT INTO rekening_konfigurasi VALUES(1,?,?,?,?,?,?)", isi)
        return
    kursor = kon.execute(
        "UPDATE rekening_konfigurasi SET nama_bank=?,nomor_rekening=?,atas_nama=?,revisi=?,"
        "diperbarui=?,actor_id=? WHERE id=1 AND revisi=?", isi + (revisi,))
    if kursor.rowcount != 1:
        raise admin_store.KonflikOperasi("revisi rekening berubah")


def ubah(path, path_auth, principal, *, operasi, revisi, sidik_awal, nama_bank, nomor_rekening,
         atas_nama, sekarang, failpoint=None):
    """Ubah (atau isi pertama kali) rekening + audit atomik; principal dikunci, replay aman.

    Pengisian pertama: `revisi=0` dan `sidik_awal=SIDIK_KOSONG`. Selanjutnya `revisi` dan
    `sidik_awal=sidik_konfigurasi(baca(path))` dari snapshot yang dilihat admin; berbeda ->
    KonflikOperasi. Seluruh input divalidasi sebelum lock/tulis.
    """
    _periksa_ubah(operasi, revisi, sidik_awal, sekarang)
    tujuan = konfigurasi(nama_bank, nomor_rekening, atas_nama, revisi=revisi + 1,
                         diperbarui=sekarang, actor_id=principal.id_akun)
    import admin_accounts
    import admin_launch_service
    with transaksi_json(path_auth) as terkunci:
        _mentah, daftar, _multi = admin_accounts._baca_state_terkunci(terkunci)
        admin_launch_service.principal_hidup(daftar, principal)
        with admin_store._transaksi(path) as kon:
            if not validasi_schema(kon):
                raise admin_store.StoreBelumSiap("schema rekening belum dipasang")
            row = kon.execute("SELECT * FROM rekening_konfigurasi WHERE id=1").fetchone()
            sidik_lama = sidik_konfigurasi(None if row is None else _dari_row(row))
            audit = kon.execute("SELECT * FROM rekening_audit WHERE operasi_id=?",
                                (operasi,)).fetchone()
            if audit is not None:
                return _replay(kon, audit, principal, revisi, sidik_awal, tujuan)
            lama_revisi = 0 if row is None else row["revisi"]
            if revisi != lama_revisi or sidik_awal != sidik_lama:
                raise admin_store.KonflikOperasi("revisi rekening berubah")
            _tulis(kon, row, tujuan, revisi, sekarang, principal)
            if failpoint == "setelah_update":
                raise RuntimeError("failpoint setelah update")
            kon.execute("INSERT INTO rekening_audit VALUES(?,?,?,?,?,?,?,?)",
                        (operasi, principal.id_akun, principal.revisi_auth, revisi, revisi + 1,
                         sidik_awal, _sidik_isi(tujuan), sekarang))
            return _dari_row(kon.execute("SELECT * FROM rekening_konfigurasi WHERE id=1").fetchone())


def _label_nomor(digit: str) -> str:
    return " ".join(digit[i:i + KELOMPOK_NOMOR] for i in range(0, len(digit), KELOMPOK_NOMOR))


def proyeksi_publik(nilai: Optional[KonfigurasiRekening]) -> Optional[RekeningPublik]:
    """Proyeksi untuk halaman pembayaran; validasi ulang di batas output (tanpa metadata admin)."""
    if nilai is None:
        return None
    cfg = konfigurasi(nilai.nama_bank, nilai.nomor_rekening, nilai.atas_nama,
                      revisi=nilai.revisi, diperbarui=nilai.diperbarui, actor_id=nilai.actor_id)
    return RekeningPublik(cfg.nama_bank, cfg.nomor_rekening, _label_nomor(cfg.nomor_rekening),
                          cfg.atas_nama)


def baca_publik(path=None) -> Optional[RekeningPublik]:
    try:
        return proyeksi_publik(baca(path))
    except (ValueError, TypeError):
        return None

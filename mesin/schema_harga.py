"""Schema harga admin: tabel `harga_produk` (nilai aktif) dan `harga_riwayat` (append-only) di admin-control.db.

Namespace `harga_*` SENGAJA terpisah dari `pesanan_*`, `transfer_*`, `purna_*`, dan `kelas_*` (alasannya sama
dengan `schema_purna`: `validasi` namespace lain membandingkan semua objeknya persis dengan DDL acuan).
Tanpa kunci asing: tabel harga tidak bergantung pada ledger lain, dan tidak ada trigger yang menyentuh namespace lain.

Pola sama dengan `schema_purna`: tanpa bump `user_version`, absen sah (belum dimigrasikan), parsial/berbeda
ditolak (ValueError), tidak diwire ke `admin_store.siapkan`; pemasangan hanya lewat :func:`migrasikan` eksplisit.

* `harga_produk`   satu baris per produk yang pernah diubah admin; baris tak ada = memakai nilai awal kode.
                    Di-upsert, sehingga TIDAK punya trigger append-only.
* `harga_riwayat`  catatan perubahan; UPDATE/DELETE ditolak trigger, dan INSERT OR REPLACE pada id yang sudah ada
                    juga ditolak (replace-guard, karena REPLACE menghapus baris tanpa memicu trigger DELETE).

Rentang dan kelipatan memakai konstanta `harga_aturan` (satu sumber dengan validator domain).
"""
import sqlite3

import harga_aturan as a
import schema_pesanan as sp

_KODE = sp._enum(a.KODE_PRODUK)
_TOLAK_RIWAYAT = "riwayat harga immutable"


def _rentang(kolom):
    return "{k} BETWEEN {min} AND {maks} AND {k} % {kelipatan} = 0".format(
        k=kolom, min=a.HARGA_MIN, maks=a.HARGA_MAKS, kelipatan=a.KELIPATAN)


def _oleh(kolom):
    return "length({k}) BETWEEN 1 AND {maks}".format(k=kolom, maks=a.BATAS_OLEH)

DDL = """
CREATE TABLE harga_produk (
    kode TEXT PRIMARY KEY CHECK(kode IN ({kode})),
    rupiah INTEGER NOT NULL CHECK({rupiah}),
    diubah TEXT NOT NULL CHECK(diubah GLOB {waktu}),
    diubah_oleh TEXT NOT NULL CHECK({oleh_produk})
);
CREATE TABLE harga_riwayat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kode TEXT NOT NULL CHECK(kode IN ({kode})),
    lama INTEGER CHECK(lama IS NULL OR {lama}),
    baru INTEGER NOT NULL CHECK({baru}),
    oleh TEXT NOT NULL CHECK({oleh_riwayat}),
    waktu TEXT NOT NULL CHECK(waktu GLOB {waktu})
);
CREATE TRIGGER harga_riwayat_tolak_update BEFORE UPDATE ON harga_riwayat
BEGIN SELECT RAISE(ABORT, '{tolak}'); END;
CREATE TRIGGER harga_riwayat_tolak_delete BEFORE DELETE ON harga_riwayat
BEGIN SELECT RAISE(ABORT, '{tolak}'); END;
CREATE TRIGGER harga_riwayat_tolak_replace BEFORE INSERT ON harga_riwayat
WHEN NEW.id IS NOT NULL AND EXISTS(SELECT 1 FROM harga_riwayat WHERE id=NEW.id)
BEGIN SELECT RAISE(ABORT, 'riwayat harga duplikat'); END;
""".format(kode=_KODE, rupiah=_rentang("rupiah"), waktu=sp._WAKTU, tolak=_TOLAK_RIWAYAT,
           lama=_rentang("lama"), baru=_rentang("baru"),
           oleh_produk=_oleh("diubah_oleh"), oleh_riwayat=_oleh("oleh"))

TABEL = ("harga_produk", "harga_riwayat")


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'harga_*' ORDER BY type,name"))


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila parsial atau berbeda dari DDL acuan."""
    aktual = struktur(kon)
    if not aktual:
        return False
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError("struktur harga tidak lengkap atau berbeda")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten; tanpa prasyarat ledger lain (harga tidak punya kunci asing)."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)

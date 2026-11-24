"""Schema jadwal Paket Belajar (kelompok Mini Class, penempatan, dan 8 pertemuan) di admin-control.db.

Namespace baru `jadwal_*` SENGAJA terpisah dari `kelas_*`: `schema_kelas.validasi` membandingkan SELURUH objek
ber-`tbl_name GLOB 'kelas_*'`, jadi menambah tabel di sana akan membuat image recovery sekarang menolak DB.
Dengan namespace sendiri, image lama tetap dapat membuka DB berisi jadwal (rollback aman).

Pola sama dengan `schema_kelas`/`schema_purna`: tanpa bump `user_version`, absen sah (belum dimigrasikan),
parsial/berbeda ditolak, migrasi hanya lewat :func:`migrasikan` eksplisit. `jadwal_*` mensyaratkan `kelas_*`
sudah terpasang (kunci asing ke `kelas_order`).

Keputusan Pemilik 25 Nov 2026: Mini Class = kelompok (maks. 5 anak, satu lokasi/guru, 8 pertemuan mingguan);
Private = per anak (guru per anak, lokasi "Online"). Jadwal bukan ledger keuangan: baris boleh diubah
(waktu, batal) dengan `diubah`; identitas baris (`kelompok_id`/`order_id`/`ke`) tidak boleh berpindah.

Guard DB:
* satu penempatan per order (PK) dan satu penempatan per anak (trigger);
* kuota kelompok ditegakkan saat insert penempatan dan saat kuota diturunkan;
* paket harus cocok: Mini -> kelompok, Private -> tanpa kelompok; sesi kelompok hanya untuk kelompok mini,
  sesi order hanya untuk order private;
* identitas sesi tidak bisa diubah lewat UPDATE.
"""
import sqlite3

import schema_kelas
import schema_pesanan as sp
import schema_transfer as st

ID_KELOMPOK = "klp_"
KODE_PAKET_MINI = "mini"
KODE_PAKET_PRIVATE = "private"
KUOTA_MAKS = 5
MENIT_MIN = 30
MENIT_MAKS = 180
PERTEMUAN_PER_PAKET = 8
LOKASI_PRIVATE = "Online"

TABEL = ("jadwal_kelompok", "jadwal_penempatan", "jadwal_pertemuan")

_AKUN = "length({k})=37 AND substr({k},1,5)='akun_' AND substr({k},6) " + sp._HEX

DDL = """
CREATE TABLE jadwal_kelompok (
    id TEXT PRIMARY KEY CHECK(length(id)=36 AND substr(id,1,4)='klp_' AND substr(id,5) {hex}),
    paket TEXT NOT NULL CHECK(paket='mini'),
    nama TEXT NOT NULL CHECK(length(nama) BETWEEN 1 AND 80),
    lokasi TEXT NOT NULL CHECK(length(lokasi) BETWEEN 1 AND 200),
    guru_id TEXT NOT NULL CHECK({akun_guru}),
    kuota INTEGER NOT NULL CHECK(kuota BETWEEN 1 AND {kuota}),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    diubah TEXT NOT NULL CHECK(diubah GLOB {waktu}),
    dibuat_oleh TEXT NOT NULL CHECK(length(dibuat_oleh) BETWEEN 1 AND 64 AND dibuat_oleh {pelaku}),
    diubah_oleh TEXT NOT NULL CHECK(length(diubah_oleh) BETWEEN 1 AND 64 AND diubah_oleh {pelaku})
);
CREATE TABLE jadwal_penempatan (
    order_id TEXT PRIMARY KEY REFERENCES kelas_order(id) ON DELETE RESTRICT,
    kelompok_id TEXT REFERENCES jadwal_kelompok(id) ON DELETE RESTRICT,
    guru_id TEXT CHECK(guru_id IS NULL OR {akun_guru}),
    lokasi TEXT CHECK(lokasi IS NULL OR length(lokasi) BETWEEN 1 AND 200),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    diubah TEXT NOT NULL CHECK(diubah GLOB {waktu}),
    dibuat_oleh TEXT NOT NULL CHECK(length(dibuat_oleh) BETWEEN 1 AND 64 AND dibuat_oleh {pelaku}),
    diubah_oleh TEXT NOT NULL CHECK(length(diubah_oleh) BETWEEN 1 AND 64 AND diubah_oleh {pelaku}),
    CHECK(
        (kelompok_id IS NOT NULL AND guru_id IS NULL AND lokasi IS NULL)
        OR (kelompok_id IS NULL AND guru_id IS NOT NULL AND lokasi IS NOT NULL)
    )
);
CREATE TABLE jadwal_pertemuan (
    id INTEGER PRIMARY KEY,
    kelompok_id TEXT REFERENCES jadwal_kelompok(id) ON DELETE RESTRICT,
    order_id TEXT REFERENCES kelas_order(id) ON DELETE RESTRICT,
    ke INTEGER NOT NULL CHECK(ke BETWEEN 1 AND {pertemuan}),
    mulai TEXT NOT NULL CHECK(mulai GLOB {waktu}),
    menit INTEGER NOT NULL CHECK(menit BETWEEN {menit_min} AND {menit_maks}),
    dibatalkan INTEGER NOT NULL DEFAULT 0 CHECK(dibatalkan IN (0,1)),
    diubah TEXT NOT NULL CHECK(diubah GLOB {waktu}),
    diubah_oleh TEXT NOT NULL CHECK(length(diubah_oleh) BETWEEN 1 AND 64 AND diubah_oleh {pelaku}),
    CHECK((kelompok_id IS NOT NULL) <> (order_id IS NOT NULL))
);
CREATE UNIQUE INDEX idx_jadwal_pertemuan_kelompok ON jadwal_pertemuan(kelompok_id, ke)
    WHERE kelompok_id IS NOT NULL;
CREATE UNIQUE INDEX idx_jadwal_pertemuan_order ON jadwal_pertemuan(order_id, ke)
    WHERE order_id IS NOT NULL;
CREATE INDEX idx_jadwal_penempatan_kelompok ON jadwal_penempatan(kelompok_id);
""".format(
    hex=sp._HEX,
    akun_guru=_AKUN.format(k="guru_id"),
    kuota=KUOTA_MAKS,
    pertemuan=PERTEMUAN_PER_PAKET,
    menit_min=MENIT_MIN,
    menit_maks=MENIT_MAKS,
    waktu=sp._WAKTU,
    pelaku=st._PELAKU,
)


def _trigger(nama, tabel, kejadian, kondisi, pesan):
    return ("CREATE TRIGGER {nama} BEFORE {kejadian} ON {tabel}\nWHEN {kondisi}\n"
            "BEGIN SELECT RAISE(ABORT, '{pesan}'); END;\n").format(
                nama=nama, kejadian=kejadian, tabel=tabel, kondisi=kondisi, pesan=pesan)


DDL += _trigger(
    "jadwal_penempatan_paket", "jadwal_penempatan", "INSERT",
    "(NEW.kelompok_id IS NOT NULL AND (SELECT paket FROM kelas_order WHERE id=NEW.order_id)<>'mini') "
    "OR (NEW.kelompok_id IS NULL AND (SELECT paket FROM kelas_order WHERE id=NEW.order_id)<>'private')",
    "paket dan jenis penempatan tidak cocok")
DDL += _trigger(
    "jadwal_penempatan_anak", "jadwal_penempatan", "INSERT",
    "EXISTS(SELECT 1 FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
    "JOIN kelas_order n ON n.id=NEW.order_id WHERE o.siswa_id=n.siswa_id)",
    "anak sudah punya penempatan")
DDL += _trigger(
    "jadwal_penempatan_kuota", "jadwal_penempatan", "INSERT",
    "NEW.kelompok_id IS NOT NULL AND (SELECT COUNT(*) FROM jadwal_penempatan "
    "WHERE kelompok_id=NEW.kelompok_id) >= (SELECT kuota FROM jadwal_kelompok WHERE id=NEW.kelompok_id)",
    "kelompok penuh")
DDL += _trigger(
    "jadwal_kelompok_kuota_turun", "jadwal_kelompok", "UPDATE OF kuota",
    "NEW.kuota < (SELECT COUNT(*) FROM jadwal_penempatan WHERE kelompok_id=NEW.id)",
    "kuota lebih kecil dari anggota")
DDL += _trigger(
    "jadwal_penempatan_tetap", "jadwal_penempatan", "UPDATE",
    "1", "penempatan tidak boleh diubah; lepas lalu tempatkan lagi")
DDL += _trigger(
    "jadwal_pertemuan_paket", "jadwal_pertemuan", "INSERT",
    "(NEW.kelompok_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM jadwal_kelompok k "
    "WHERE k.id=NEW.kelompok_id AND k.paket='mini')) OR (NEW.order_id IS NOT NULL AND "
    "NOT EXISTS(SELECT 1 FROM kelas_order o WHERE o.id=NEW.order_id AND o.paket='private'))",
    "sesi jadwal tidak cocok dengan paket")
DDL += _trigger(
    "jadwal_pertemuan_identitas", "jadwal_pertemuan", "UPDATE OF kelompok_id, order_id, ke",
    "1", "identitas pertemuan tidak boleh diubah")


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name GLOB 'jadwal_*' "
        "ORDER BY type,name"))


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila parsial, berbeda, atau tanpa kelas."""
    aktual = struktur(kon)
    if not aktual:
        return False
    if not schema_kelas.validasi(kon):
        raise ValueError("jadwal tanpa kelas")
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(schema_kelas.DDL)
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError("struktur jadwal tidak lengkap")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten; mensyaratkan `kelas_*` sudah terpasang."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not schema_kelas.validasi(kon):
            raise admin_store_core.StoreBelumSiap("kelas belum dipasang")
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("integritas jadwal gagal")

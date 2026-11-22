"""Skema Latihan Lomba (Grand Final Corexis): empat tabel aditif, terpisah dari tabel sesi guru.

`lomba_sesi` menyimpan batas waktu sebagai epoch detik dari jam server; indeks unik parsial
menjamin satu sesi berjalan per anak walau dua permintaan "Mulai" datang bersamaan.
`lomba_soal` menyimpan soal yang sudah dirender (utuh, termasuk kunci dan pembahasan) supaya
mengubah template kelak tidak mengubah riwayat; halaman anak hanya boleh membaca kolom aman.
`lomba_jawaban` menyimpan jawaban terakhir per nomor. Semua milik siswa dan ikut terhapus
bersama siswa (ON DELETE CASCADE), seperti `laporan_ortu`.
`lomba_penugasan` mencatat Mode Lomba per anak yang diaktifkan Guru (satu baris per anak, tanpa baris =
tidak aktif); `target_harian`, `tampil_hitung_mundur`, dan durasi per mode NULL berarti ikut nilai paket.

Simulasi Lomba (22 Nov 2026): `lomba_sesi.mode` ('latihan'/'simulasi') dan dua kolom durasi di `lomba_penugasan`
ditambahkan lewat `schema.MIGRASI`; batas nomor soal diperlebar 10 -> 35 lewat `perlebar_nomor_soal` (SQLite tidak bisa
mengubah CHECK di tempat, jadi tabel dibangun ulang dengan isi yang sama).
"""
import sqlite3

_CHECK_NOMOR_LAMA = "BETWEEN 1 AND 10)"
_KOLOM_SOAL = ("sesi_id, nomor, template_id, topik, jenis, tingkat, tanda_tangan, parameter, inggris, teks, svg, "
               "kunci, pilihan_json, gambar_pilihan_json, posisi_kunci, pengecoh_json, pembahasan_json")

SKEMA_LOMBA = """
CREATE TABLE IF NOT EXISTS lomba_sesi (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id      INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    paket_id      TEXT    NOT NULL,
    seed          INTEGER NOT NULL,
    mulai_epoch   INTEGER NOT NULL,
    batas_epoch   INTEGER NOT NULL,
    selesai_epoch INTEGER,
    status        TEXT    NOT NULL CHECK (status IN ('berjalan', 'dikumpul', 'waktu_habis')),
    mode          TEXT    NOT NULL DEFAULT 'latihan' CHECK (mode IN ('latihan', 'simulasi')),
    CHECK (batas_epoch > mulai_epoch),
    CHECK ((status = 'berjalan') = (selesai_epoch IS NULL)),
    CHECK (selesai_epoch IS NULL
           OR (selesai_epoch >= mulai_epoch AND selesai_epoch <= batas_epoch))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lomba_sesi_berjalan ON lomba_sesi(siswa_id) WHERE status = 'berjalan';
CREATE INDEX IF NOT EXISTS idx_lomba_sesi_siswa ON lomba_sesi(siswa_id, id);

CREATE TABLE IF NOT EXISTS lomba_soal (
    sesi_id              INTEGER NOT NULL REFERENCES lomba_sesi(id) ON DELETE CASCADE,
    nomor                INTEGER NOT NULL CHECK (nomor BETWEEN 1 AND 35),
    template_id          TEXT    NOT NULL,
    topik                TEXT    NOT NULL,
    jenis                TEXT    NOT NULL CHECK (jenis IN ('pg', 'isian')),
    tingkat              INTEGER NOT NULL CHECK (tingkat BETWEEN 1 AND 3),
    tanda_tangan         TEXT    NOT NULL,
    parameter            TEXT    NOT NULL,
    inggris              INTEGER NOT NULL DEFAULT 0 CHECK (inggris IN (0, 1)),
    teks                 TEXT    NOT NULL,
    svg                  TEXT    NOT NULL DEFAULT '',
    kunci                TEXT    NOT NULL,
    pilihan_json         TEXT    NOT NULL DEFAULT '[]',
    gambar_pilihan_json  TEXT    NOT NULL DEFAULT '[]',
    posisi_kunci         INTEGER NOT NULL CHECK (posisi_kunci BETWEEN -1 AND 3),
    pengecoh_json        TEXT    NOT NULL DEFAULT '[]',
    pembahasan_json      TEXT    NOT NULL,
    PRIMARY KEY (sesi_id, nomor)
);

CREATE TABLE IF NOT EXISTS lomba_jawaban (
    sesi_id      INTEGER NOT NULL,
    nomor        INTEGER NOT NULL,
    jawaban      TEXT    NOT NULL CHECK (length(jawaban) BETWEEN 1 AND 6),
    diubah_epoch INTEGER NOT NULL,
    PRIMARY KEY (sesi_id, nomor),
    FOREIGN KEY (sesi_id, nomor) REFERENCES lomba_soal(sesi_id, nomor) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lomba_penugasan (
    siswa_id             INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    paket_id             TEXT    NOT NULL CHECK (length(paket_id) BETWEEN 1 AND 64),
    aktif                INTEGER NOT NULL CHECK (aktif IN (0, 1)),
    target_harian        INTEGER CHECK (target_harian IS NULL OR target_harian BETWEEN 0 AND 5),
    tampil_hitung_mundur INTEGER CHECK (tampil_hitung_mundur IS NULL OR tampil_hitung_mundur IN (0, 1)),
    diubah_epoch         INTEGER NOT NULL,
    diubah_oleh          TEXT    NOT NULL DEFAULT '' CHECK (length(diubah_oleh) <= 64),
    durasi_latihan_detik  INTEGER CHECK (durasi_latihan_detik IS NULL OR durasi_latihan_detik BETWEEN 300 AND 10800),
    durasi_simulasi_detik INTEGER CHECK (durasi_simulasi_detik IS NULL OR durasi_simulasi_detik BETWEEN 300 AND 10800)
);
"""


def _ddl_soal(nama: str) -> str:
    """DDL `lomba_soal` dari SKEMA_LOMBA (satu sumber), dengan nama tabel `nama`."""
    awal = SKEMA_LOMBA.index("CREATE TABLE IF NOT EXISTS lomba_soal (")
    akhir = SKEMA_LOMBA.index(");", awal) + 2
    return SKEMA_LOMBA[awal:akhir].replace("CREATE TABLE IF NOT EXISTS lomba_soal (", f"CREATE TABLE {nama} (", 1)


def perlebar_nomor_soal(kon: sqlite3.Connection) -> bool:
    """Bangun ulang `lomba_soal` bila CHECK nomor masih 1..10; True bila dibangun ulang. Idempoten.

    Wajib dipanggil di dalam transaksi migrasi dengan foreign key NONAKTIF (`database.siapkan`): `lomba_jawaban`
    punya FK ON DELETE CASCADE ke tabel ini, jadi DROP dengan FK hidup akan menghapus semua jawaban. Urutan: buat
    tabel baru, salin semua baris dengan kolom eksplisit, DROP lama, RENAME baru (bukan rename lama lebih dulu,
    karena SQLite modern menulis ulang FK anak ke tabel yang di-rename). Jumlah baris dan `foreign_key_check`
    diperiksa sebelum kembali; gagal di mana pun -> exception, pemanggil menggulung balik seluruh transaksi.
    """
    baris = kon.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'lomba_soal'").fetchone()
    if baris is None or _CHECK_NOMOR_LAMA not in baris[0]:
        return False
    if not kon.in_transaction or kon.execute("PRAGMA foreign_keys").fetchone()[0]:
        raise sqlite3.IntegrityError("perlebar lomba_soal membutuhkan transaksi migrasi dengan FK nonaktif")
    jumlah_soal = kon.execute("SELECT COUNT(*) FROM lomba_soal").fetchone()[0]
    jumlah_jawaban = kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0]
    kon.execute(_ddl_soal("lomba_soal_baru"))
    kon.execute(f"INSERT INTO lomba_soal_baru ({_KOLOM_SOAL}) SELECT {_KOLOM_SOAL} FROM lomba_soal")
    kon.execute("DROP TABLE lomba_soal")
    kon.execute("ALTER TABLE lomba_soal_baru RENAME TO lomba_soal")
    if (kon.execute("SELECT COUNT(*) FROM lomba_soal").fetchone()[0] != jumlah_soal
            or kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0] != jumlah_jawaban):
        raise sqlite3.IntegrityError("perlebar lomba_soal mengubah jumlah baris")
    if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise sqlite3.IntegrityError("perlebar lomba_soal meninggalkan foreign key rusak")
    return True

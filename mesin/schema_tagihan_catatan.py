"""Catatan batal/pulih tagihan Paket Belajar: tabel `tagihan_catatan` (append-only) di admin-control.db.

Namespace `tagihan_*` SENGAJA terpisah dari `kelas_*`: `schema_kelas.validasi` membandingkan semua objek `kelas_*` persis
dengan DDL acuan, jadi objek baru di sana akan membuat store pada image lama ditolak. Objek `kelas_*` tidak diubah.

Pola sama dengan `schema_kelas`/`schema_harga`: tanpa bump `user_version`, absen sah (belum dimigrasikan), parsial atau
berbeda ditolak (ValueError), tidak diwire ke `admin_store.siapkan`; pemasangan hanya lewat :func:`migrasikan` eksplisit.
Mensyaratkan skema kelas sudah terpasang (tabel acuan order, bukti, dan verifikasi ada di DB yang sama).

Satu baris = satu aksi pada satu tagihan (order). Status batal tidak disimpan di tabel lain: "dibatalkan" berarti catatan
terakhir untuk order itu adalah `batal` (lihat `kelas_catatan`). Trigger BEFORE INSERT menjaga aturan:

* `batal`  hanya bila order belum punya bukti, belum lunas, catatan terakhirnya bukan `batal`, dan jendela bayar belum lewat;
* `pulih`  hanya bila catatan terakhir `batal` dan jendela bayar belum lewat.

Penjagaan deposit Peta pada pemulihan TIDAK ada di sini (itu keadaan lintas tabel milik domain, `kelas_batal`).
"""
import sqlite3

import schema_kelas as sk
import schema_pesanan as sp

AKSI_BATAL = "batal"
AKSI_PULIH = "pulih"
_PESAN_UBAH = "catatan tagihan immutable"
_PESAN_DUPLIKAT = "catatan tagihan duplikat"

# Kondisi pemicu (fragmen SQL). Nama konstanta dipakai juga oleh tes mutasi; ubah dengan hati-hati.
_BATAL_ADA_BUKTI = "EXISTS(SELECT 1 FROM kelas_bukti WHERE order_id=NEW.order_id)"
_BATAL_SUDAH_LUNAS = "EXISTS(SELECT 1 FROM kelas_verifikasi WHERE order_id=NEW.order_id AND keputusan='setuju')"
_AKSI_TERAKHIR = "(SELECT aksi FROM tagihan_catatan WHERE order_id=NEW.order_id ORDER BY id DESC LIMIT 1)"
_JENDELA_LEWAT = "NEW.dibuat>=(SELECT kedaluwarsa FROM kelas_order WHERE id=NEW.order_id)"

# (nama trigger, kondisi abort, pesan). Setiap aturan punya pesan sendiri agar tes dapat membedakan pelanggarannya.
_ATURAN_INSERT = (
    ("tagihan_catatan_batal_bukti", "NEW.aksi='batal' AND " + _BATAL_ADA_BUKTI,
     "batal ditolak: tagihan sudah punya bukti"),
    ("tagihan_catatan_batal_lunas", "NEW.aksi='batal' AND " + _BATAL_SUDAH_LUNAS,
     "batal ditolak: tagihan sudah lunas"),
    ("tagihan_catatan_batal_ganda", "NEW.aksi='batal' AND COALESCE(" + _AKSI_TERAKHIR + ",'')='batal'",
     "batal ditolak: tagihan sudah dibatalkan"),
    ("tagihan_catatan_batal_jendela", "NEW.aksi='batal' AND " + _JENDELA_LEWAT,
     "batal ditolak: jendela bayar sudah lewat"),
    ("tagihan_catatan_pulih_tanpa_batal", "NEW.aksi='pulih' AND COALESCE(" + _AKSI_TERAKHIR + ",'')<>'batal'",
     "pulih ditolak: tagihan tidak sedang dibatalkan"),
    ("tagihan_catatan_pulih_jendela", "NEW.aksi='pulih' AND " + _JENDELA_LEWAT,
     "pulih ditolak: jendela bayar sudah lewat"),
)

DDL = """
CREATE TABLE tagihan_catatan (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES kelas_order(id) ON DELETE RESTRICT,
    aksi TEXT NOT NULL CHECK(aksi IN ('{batal}','{pulih}')),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE INDEX idx_tagihan_catatan_order ON tagihan_catatan(order_id, id);
CREATE TRIGGER tagihan_catatan_tolak_update BEFORE UPDATE ON tagihan_catatan
BEGIN SELECT RAISE(ABORT, '{tolak_ubah}'); END;
CREATE TRIGGER tagihan_catatan_tolak_delete BEFORE DELETE ON tagihan_catatan
BEGIN SELECT RAISE(ABORT, '{tolak_ubah}'); END;
CREATE TRIGGER tagihan_catatan_tolak_replace BEFORE INSERT ON tagihan_catatan
WHEN NEW.id IS NOT NULL AND EXISTS(SELECT 1 FROM tagihan_catatan WHERE id=NEW.id)
BEGIN SELECT RAISE(ABORT, '{duplikat}'); END;
""".format(batal=AKSI_BATAL, pulih=AKSI_PULIH, waktu=sp._WAKTU, tolak_ubah=_PESAN_UBAH, duplikat=_PESAN_DUPLIKAT)


def _trigger_insert(nama, kondisi, pesan):
    return ("CREATE TRIGGER {nama} BEFORE INSERT ON tagihan_catatan\nWHEN {kondisi}\n"
            "BEGIN SELECT RAISE(ABORT, '{pesan}'); END;\n").format(nama=nama, kondisi=kondisi, pesan=pesan)


for _nama, _kondisi, _pesan in _ATURAN_INSERT:
    DDL += _trigger_insert(_nama, _kondisi, _pesan)

TABEL = "tagihan_catatan"


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'tagihan_*' ORDER BY type,name"))


def terpasang(kon):
    """True bila tabel catatan sudah dimigrasikan (cek ringan, bukan validasi; sama dengan `purna.terpasang`)."""
    return kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABEL,)).fetchone() is not None


def _acuan():
    """DB acuan dalam memori: ledger pesanan, kelas, lalu catatan tagihan (urutan wajib: trigger butuh tabel ON-nya)."""
    acuan = sqlite3.connect(":memory:")
    acuan.executescript(sp.DDL)
    acuan.executescript(sk.DDL)
    acuan.executescript(DDL)
    return acuan


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila kelas belum lengkap, atau catatan parsial/berbeda dari DDL acuan."""
    aktual = struktur(kon)
    if not aktual:
        return False
    if not sk.validasi(kon):
        raise ValueError("tagihan tanpa skema kelas")
    acuan = _acuan()
    try:
        if aktual != struktur(acuan):
            raise ValueError("struktur tagihan tidak lengkap atau berbeda")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten; mensyaratkan skema kelas sudah terpasang."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not sk.validasi(kon):
            raise admin_store_core.StoreBelumSiap("kelas belum dipasang")
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("integritas tagihan gagal")

"""Schema purna (voucher pemakaian + pilihan terlambat) untuk order Paket Coba yang sudah lunas.

Namespace `purna_*` SENGAJA terpisah dari `pesanan_*` dan `transfer_*`: `schema_pesanan.validasi`
membandingkan semua objek ber-`tbl_name GLOB 'pesanan_*'` persis dengan DDL acuannya (begitu pula
`schema_transfer.validasi` untuk `transfer_*`), jadi satu objek baru di namespace itu membuat seluruh
store admin ditolak (fail-closed) pada image lama. Dengan namespace sendiri, DDL, `validasi`, dan `TABEL`
pesanan/transfer tetap byte-identik; image lama tetap dapat membuka DB yang sudah bertabel `purna_*`
(rollback aman).

Pola sama dengan `schema_transfer`: tanpa bump `user_version`, absen sah (belum dimigrasikan),
parsial/berbeda ditolak (ValueError), migrasi hanya lewat :func:`migrasikan` eksplisit. Ketiga tabel
append-only (trigger ABORT atas UPDATE/DELETE dan replace-guard); koreksi hanya lewat baris baru. Status
tidak disimpan:

* `purna_voucher_pakai`      satu catatan pemakaian voucher per order (kelas atau lainnya);
* `purna_pilihan_terlambat`  pilihan pembeli bila voucher terlambat, MONOTON per order: baris
  `menunggu` boleh disusul baris `uang_kembali` (kunci `(order_id, pilihan)`); `uang_kembali` FINAL;
* `purna_laporan_terbit`     waktu laporan Peta Kemampuan diterbitkan untuk order itu (satu per order).

Aturan lapis kedua di tingkat DB (BEFORE INSERT, ABORT), di luar domain:

* ketiga tabel hanya untuk order LUNAS (receipt Midtrans `lunas` atau `transfer_lunas`);
* ketiga tabel ditolak bila order sudah direfund di salah satu ledger (`pesanan_refund` atau `transfer_refund`);
* pilihan terlambat ditolak bila voucher order itu sudah dipakai;
* `menunggu` ditolak bila order itu sudah memilih `uang_kembali` (monoton);
* voucher ditolak bila order sudah memilih `uang_kembali`;
* laporan terbit ditolak bila waktu terbit lebih awal dari waktu lunas order.

BATAS YANG DISENGAJA: larangan "refund setelah voucher dipakai" TIDAK dapat menjadi trigger di sini,
karena tabel refund milik namespace lain dan DDL-nya harus tetap identik (syarat rollback aman).
Larangan itu ditegakkan domain (V2/V3) sebelum menulis refund, bukan oleh skema ini.

Idempotensi domain = SELECT lalu INSERT; `INSERT OR IGNORE` tidak boleh dipakai sebagai idempotensi
karena replace-guard di sini sengaja membuat duplikat selalu ABORT.
"""
import sqlite3

import schema_pesanan as sp
import schema_transfer as st

CATATAN_PAKAI = ("kelas", "lainnya")
PILIHAN_TERLAMBAT = ("menunggu", "uang_kembali")
_PELAKU_MAKS = 64

DDL = """
CREATE TABLE purna_voucher_pakai (
    operasi_id TEXT PRIMARY KEY CHECK(length(operasi_id) BETWEEN 8 AND 64 AND operasi_id {id}),
    order_id TEXT NOT NULL UNIQUE REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    dicatat_oleh TEXT NOT NULL CHECK(length(dicatat_oleh) BETWEEN 1 AND {pelaku_maks} AND dicatat_oleh {pelaku}),
    catatan_kode TEXT NOT NULL CHECK(catatan_kode IN ({catatan})),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE purna_pilihan_terlambat (
    order_id TEXT NOT NULL REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    pilihan TEXT NOT NULL CHECK(pilihan IN ({pilihan})),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    PRIMARY KEY(order_id, pilihan)
);
CREATE TABLE purna_laporan_terbit (
    order_id TEXT PRIMARY KEY REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    terbit TEXT NOT NULL CHECK(terbit GLOB {waktu}),
    dicatat_oleh TEXT NOT NULL CHECK(length(dicatat_oleh) BETWEEN 1 AND {pelaku_maks} AND dicatat_oleh {pelaku}),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
""".format(id=sp._ID, waktu=sp._WAKTU, pelaku=st._PELAKU, pelaku_maks=_PELAKU_MAKS,
           catatan=sp._enum(CATATAN_PAKAI), pilihan=sp._enum(PILIHAN_TERLAMBAT))

TABEL = ("purna_voucher_pakai", "purna_pilihan_terlambat", "purna_laporan_terbit")

# Kunci unik per tabel untuk replace-guard (BEFORE INSERT menggigit INSERT OR REPLACE).
_KUNCI = {
    "purna_voucher_pakai": ("operasi_id=NEW.operasi_id", "order_id=NEW.order_id"),
    "purna_pilihan_terlambat": ("(order_id=NEW.order_id AND pilihan=NEW.pilihan)",),
    "purna_laporan_terbit": ("order_id=NEW.order_id",),
}


def _trigger(nama, tabel, kondisi, pesan):
    return ("CREATE TRIGGER {nama} BEFORE INSERT ON {tabel}\nWHEN {kondisi}\n"
            "BEGIN SELECT RAISE(ABORT, '{pesan}'); END;\n").format(
                nama=nama, tabel=tabel, kondisi=kondisi, pesan=pesan)


def _ledger(tabel):
    ddl = ""
    for aksi in ("update", "delete"):
        ddl += ("CREATE TRIGGER {t}_tolak_{a} BEFORE {A} ON {t}\n"
                "BEGIN SELECT RAISE(ABORT, 'ledger purna immutable'); END;\n").format(
                    t=tabel, a=aksi, A=aksi.upper())
    cocok = " OR ".join(_KUNCI[tabel])
    return ddl + _trigger(tabel + "_tolak_replace", tabel,
                          "EXISTS(SELECT 1 FROM %s WHERE %s)" % (tabel, cocok),
                          "ledger purna duplikat")


_BELUM_LUNAS = ("NOT EXISTS(SELECT 1 FROM pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas') "
                "AND NOT EXISTS(SELECT 1 FROM transfer_lunas WHERE order_id=NEW.order_id)")
_SUDAH_REFUND = ("EXISTS(SELECT 1 FROM pesanan_refund WHERE order_id=NEW.order_id) "
                 "OR EXISTS(SELECT 1 FROM transfer_refund WHERE order_id=NEW.order_id)")

# Waktu lunas = receipt Midtrans lunas, selain itu transfer_lunas (urutan sama dengan domain `purna`).
# Bila order belum lunas hasilnya NULL (perbandingan tidak menolak; trigger `_lunas` yang menolak).
_TERBIT_SEBELUM_LUNAS = (
    "NEW.terbit < COALESCE((SELECT dibuat FROM pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas'),"
    "(SELECT dibuat FROM transfer_lunas WHERE order_id=NEW.order_id))")

# Aturan lapis kedua di luar domain: (nama trigger, tabel, kondisi abort, pesan).
_ATURAN = (
    ("purna_voucher_pakai_lunas", "purna_voucher_pakai", _BELUM_LUNAS,
     "voucher purna hanya untuk order lunas"),
    ("purna_pilihan_terlambat_lunas", "purna_pilihan_terlambat", _BELUM_LUNAS,
     "pilihan terlambat hanya untuk order lunas"),
    ("purna_voucher_pakai_refund", "purna_voucher_pakai", _SUDAH_REFUND,
     "voucher purna ditolak: order sudah direfund"),
    ("purna_pilihan_terlambat_refund", "purna_pilihan_terlambat", _SUDAH_REFUND,
     "pilihan terlambat ditolak: order sudah direfund"),
    ("purna_pilihan_terlambat_voucher_dipakai", "purna_pilihan_terlambat",
     "EXISTS(SELECT 1 FROM purna_voucher_pakai WHERE order_id=NEW.order_id)",
     "pilihan terlambat ditolak: voucher order sudah dipakai"),
    ("purna_voucher_pakai_uang_kembali", "purna_voucher_pakai",
     "EXISTS(SELECT 1 FROM purna_pilihan_terlambat WHERE order_id=NEW.order_id "
     "AND pilihan='uang_kembali')",
     "voucher purna ditolak: order sudah memilih uang kembali"),
    ("purna_pilihan_terlambat_menunggu_setelah_uang_kembali", "purna_pilihan_terlambat",
     "NEW.pilihan='menunggu' AND EXISTS(SELECT 1 FROM purna_pilihan_terlambat "
     "WHERE pilihan='uang_kembali' AND order_id=NEW.order_id)",
     "pilihan terlambat ditolak: sudah memilih uang kembali"),
    ("purna_laporan_terbit_lunas", "purna_laporan_terbit", _BELUM_LUNAS,
     "laporan terbit hanya untuk order lunas"),
    ("purna_laporan_terbit_refund", "purna_laporan_terbit", _SUDAH_REFUND,
     "laporan terbit ditolak: order sudah direfund"),
    ("purna_laporan_terbit_sebelum_lunas", "purna_laporan_terbit", _TERBIT_SEBELUM_LUNAS,
     "laporan terbit ditolak: lebih awal dari waktu lunas"),
)

for _tabel in TABEL:
    DDL += _ledger(_tabel)
for _aturan in _ATURAN:
    DDL += _trigger(*_aturan)


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'purna_*' ORDER BY type,name"))


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila parsial, berbeda, atau tanpa pesanan/transfer."""
    aktual = struktur(kon)
    if not aktual:
        return False
    if not sp.validasi(kon):
        raise ValueError("purna tanpa ledger pesanan")
    if not st.validasi(kon):
        raise ValueError("purna tanpa ledger transfer")
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(sp.DDL)
        acuan.executescript(st.DDL)
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError("struktur purna tidak lengkap")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten; mensyaratkan ledger pesanan dan transfer sudah terpasang."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not sp.validasi(kon):
            raise admin_store_core.StoreBelumSiap("pesanan belum dipasang")
        if not st.validasi(kon):
            raise admin_store_core.StoreBelumSiap("transfer belum dipasang")
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("integritas purna gagal")

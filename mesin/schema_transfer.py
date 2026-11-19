"""Schema transfer rekening (verifikasi manual admin) untuk pesanan Paket Coba.

Namespace `transfer_*` SENGAJA terpisah dari `pesanan_*`: `schema_pesanan.validasi`
membandingkan semua objek ber-`tbl_name GLOB 'pesanan_*'` persis dengan DDL
acuannya, jadi satu tabel/trigger/indeks baru berawalan `pesanan_` akan membuat
seluruh store admin ditolak (fail-closed) pada image lama. Dengan namespace sendiri,
DDL, `validasi`, dan `TABEL` pesanan tetap byte-identik; image lama tetap dapat
membuka DB yang sudah bertabel `transfer_*` (rollback aman).

Pola sama dengan `schema_pesanan`: tanpa bump `user_version`, absent sah (belum
dimigrasikan), parsial/berbeda ditolak, migrasi hanya lewat :func:`migrasikan`
eksplisit. Semua tabel append-only (trigger ABORT atas UPDATE/DELETE dan
replace-guard); koreksi hanya lewat baris baru. Status tidak disimpan:

* `transfer_tagihan`  nominal unik per jendela bayar (order, urutan);
* `transfer_bukti`    metadata berkas bukti (isi berkas di luar DB);
* `transfer_bukti_hapus` penanda hapus bukti (tabel terpisah agar bukti tak diubah);
* `transfer_verifikasi` keputusan admin setuju/tolak, mencatat bukti terakhir yang diputuskan;
* `transfer_lunas`    receipt lunas jalur transfer (mirip `pesanan_receipt`);
* `transfer_refund`   catatan refund manual untuk order lunas-transfer.
"""
import sqlite3

import schema_pesanan as sp

MAKS_BUKTI = 5
BATAS_UKURAN_BUKTI = 5 * 1024 * 1024
MIME_BUKTI = ("image/jpeg", "image/png", "application/pdf")
KODE_MIN = 1
KODE_MAKS = 999
KEPUTUSAN = ("setuju", "tolak")
BATAS_ALASAN = 200
BATAS_RUPIAH = 10_000_000
_PELAKU = "NOT GLOB '*[^A-Za-z0-9_.-]*'"
_AKUN = ("length({k})=37 AND substr({k},1,5)='akun_' AND substr({k},6) " + sp._HEX)

DDL = """
CREATE TABLE transfer_tagihan (
    order_id TEXT NOT NULL,
    urutan INTEGER NOT NULL CHECK(urutan>=1),
    kode_unik INTEGER NOT NULL CHECK(kode_unik BETWEEN {kode_min} AND {kode_maks}),
    nominal_transfer INTEGER NOT NULL CHECK(nominal_transfer BETWEEN 2 AND {nominal_maks}),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    PRIMARY KEY(order_id,urutan),
    FOREIGN KEY(order_id,urutan) REFERENCES pesanan_jendela(order_id,urutan) ON DELETE RESTRICT
);
CREATE TABLE transfer_bukti (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    berkas TEXT NOT NULL UNIQUE CHECK(length(berkas)=32 AND berkas {hex}),
    mime TEXT NOT NULL CHECK(mime IN ({mime})),
    ukuran INTEGER NOT NULL CHECK(ukuran BETWEEN 1 AND {ukuran_maks}),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 {hex}),
    diunggah_oleh TEXT NOT NULL CHECK({akun}),
    diunggah TEXT NOT NULL CHECK(diunggah GLOB {waktu}),
    FOREIGN KEY(order_id,urutan) REFERENCES transfer_tagihan(order_id,urutan) ON DELETE RESTRICT
);
CREATE TABLE transfer_bukti_hapus (
    bukti_id INTEGER PRIMARY KEY REFERENCES transfer_bukti(id) ON DELETE RESTRICT,
    dihapus TEXT NOT NULL CHECK(dihapus GLOB {waktu})
);
CREATE TABLE transfer_verifikasi (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    keputusan TEXT NOT NULL CHECK(keputusan IN ({keputusan})),
    admin_id TEXT NOT NULL CHECK(length(admin_id) BETWEEN 1 AND 64 AND admin_id {pelaku}),
    alasan TEXT CHECK(alasan IS NULL OR length(alasan) BETWEEN 1 AND {alasan_maks}),
    bukti_hingga_id INTEGER NOT NULL REFERENCES transfer_bukti(id) ON DELETE RESTRICT,
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    CHECK((keputusan='tolak')=(alasan IS NOT NULL)),
    FOREIGN KEY(order_id,urutan) REFERENCES transfer_tagihan(order_id,urutan) ON DELETE RESTRICT
);
CREATE TABLE transfer_lunas (
    order_id TEXT PRIMARY KEY REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    verifikasi_id INTEGER NOT NULL UNIQUE REFERENCES transfer_verifikasi(id) ON DELETE RESTRICT,
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 1 AND {rupiah_maks}),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE transfer_refund (
    operasi_id TEXT PRIMARY KEY CHECK(length(operasi_id) BETWEEN 8 AND 64 AND operasi_id {id}),
    order_id TEXT NOT NULL UNIQUE REFERENCES transfer_lunas(order_id) ON DELETE RESTRICT,
    dicatat_oleh TEXT NOT NULL CHECK(length(dicatat_oleh) BETWEEN 1 AND 64),
    catatan_kode TEXT NOT NULL CHECK(catatan_kode IN ({catatan})),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
""".format(hex=sp._HEX, id=sp._ID, waktu=sp._WAKTU, pelaku=_PELAKU,
           kode_min=KODE_MIN, kode_maks=KODE_MAKS, nominal_maks=BATAS_RUPIAH + KODE_MAKS,
           mime=sp._enum(MIME_BUKTI),
           ukuran_maks=BATAS_UKURAN_BUKTI, keputusan=sp._enum(KEPUTUSAN),
           alasan_maks=BATAS_ALASAN, rupiah_maks=BATAS_RUPIAH,
           catatan=sp._enum(sp.CATATAN_REFUND), akun=_AKUN.format(k="diunggah_oleh"))

TABEL = ("transfer_tagihan", "transfer_bukti", "transfer_bukti_hapus",
         "transfer_verifikasi", "transfer_lunas", "transfer_refund")

# Kunci unik per tabel untuk replace-guard (BEFORE INSERT menggigit INSERT OR REPLACE).
# Kunci INTEGER PRIMARY KEY dijaga hanya bila eksplisit (NEW.id NULL = rowid otomatis).
_KUNCI = {
    "transfer_tagihan": ("(order_id=NEW.order_id AND urutan=NEW.urutan)",),
    "transfer_bukti": ("(NEW.id IS NOT NULL AND id=NEW.id)", "berkas=NEW.berkas"),
    "transfer_bukti_hapus": ("bukti_id=NEW.bukti_id",),
    "transfer_verifikasi": ("(NEW.id IS NOT NULL AND id=NEW.id)",),
    "transfer_lunas": ("order_id=NEW.order_id", "verifikasi_id=NEW.verifikasi_id"),
    "transfer_refund": ("operasi_id=NEW.operasi_id", "order_id=NEW.order_id"),
}


def _trigger(nama, tabel, kondisi, pesan):
    return ("CREATE TRIGGER {nama} BEFORE INSERT ON {tabel}\nWHEN {kondisi}\n"
            "BEGIN SELECT RAISE(ABORT, '{pesan}'); END;\n").format(
                nama=nama, tabel=tabel, kondisi=kondisi, pesan=pesan)


def _ledger(tabel):
    ddl = ""
    for aksi in ("update", "delete"):
        ddl += ("CREATE TRIGGER {t}_tolak_{a} BEFORE {A} ON {t}\n"
                "BEGIN SELECT RAISE(ABORT, 'ledger transfer immutable'); END;\n").format(
                    t=tabel, a=aksi, A=aksi.upper())
    cocok = " OR ".join(_KUNCI[tabel])
    return ddl + _trigger(tabel + "_tolak_replace", tabel,
                          "EXISTS(SELECT 1 FROM %s WHERE %s)" % (tabel, cocok),
                          "ledger transfer duplikat")


# Aturan lapis kedua di luar domain: (nama trigger, tabel, kondisi abort, pesan).
_ATURAN = (
    ("transfer_tagihan_nominal", "transfer_tagihan",
     "NEW.nominal_transfer IS NOT (SELECT rupiah FROM pesanan_order WHERE order_id=NEW.order_id)"
     "+NEW.kode_unik", "nominal tagihan transfer tidak cocok dengan order"),
    ("transfer_bukti_batas", "transfer_bukti",
     "(SELECT COUNT(*) FROM transfer_bukti WHERE order_id=NEW.order_id)>=%d" % MAKS_BUKTI,
     "batas bukti transfer tercapai"),
    ("transfer_bukti_pemilik", "transfer_bukti",
     "NEW.diunggah_oleh IS NOT (SELECT akun_id FROM pesanan_order WHERE order_id=NEW.order_id)",
     "bukti transfer bukan dari pemilik order"),
    ("transfer_bukti_jendela", "transfer_bukti",
     "NEW.diunggah>=(SELECT kedaluwarsa FROM pesanan_jendela WHERE order_id=NEW.order_id "
     "AND urutan=NEW.urutan)", "bukti transfer di luar jendela bayar"),
    ("transfer_bukti_setelah_lunas", "transfer_bukti",
     "EXISTS(SELECT 1 FROM transfer_lunas WHERE order_id=NEW.order_id)",
     "bukti transfer setelah lunas"),
    ("transfer_verifikasi_bukti_terbaru", "transfer_verifikasi",
     "NEW.bukti_hingga_id IS NOT (SELECT MAX(id) FROM transfer_bukti WHERE order_id=NEW.order_id) "
     "OR NEW.urutan IS NOT (SELECT urutan FROM transfer_bukti WHERE id=NEW.bukti_hingga_id)",
     "keputusan transfer harus atas bukti terbaru"),
    ("transfer_verifikasi_bukti_baru", "transfer_verifikasi",
     "NEW.bukti_hingga_id<=COALESCE((SELECT MAX(bukti_hingga_id) FROM transfer_verifikasi "
     "WHERE order_id=NEW.order_id),0)", "keputusan transfer tanpa bukti baru"),
    ("transfer_verifikasi_satu_setuju", "transfer_verifikasi",
     "EXISTS(SELECT 1 FROM transfer_verifikasi WHERE order_id=NEW.order_id AND keputusan='setuju')",
     "order transfer sudah punya keputusan setuju"),
    ("transfer_lunas_nominal", "transfer_lunas",
     "NEW.rupiah IS NOT (SELECT rupiah FROM pesanan_order WHERE order_id=NEW.order_id)",
     "lunas transfer tidak cocok dengan order"),
    ("transfer_lunas_verifikasi", "transfer_lunas",
     "NOT EXISTS(SELECT 1 FROM transfer_verifikasi WHERE id=NEW.verifikasi_id "
     "AND order_id=NEW.order_id AND keputusan='setuju')", "lunas transfer tanpa verifikasi setuju"),
    ("transfer_lunas_tanpa_receipt", "transfer_lunas",
     "EXISTS(SELECT 1 FROM pesanan_receipt WHERE order_id=NEW.order_id)",
     "order sudah punya receipt provider"),
    ("transfer_bukti_hapus_putusan", "transfer_bukti_hapus",
     "NOT EXISTS(SELECT 1 FROM transfer_verifikasi v WHERE v.bukti_hingga_id>=NEW.bukti_id "
     "AND v.order_id=(SELECT order_id FROM transfer_bukti WHERE id=NEW.bukti_id))",
     "bukti belum diputuskan"),
)

for _tabel in TABEL:
    DDL += _ledger(_tabel)
for _aturan in _ATURAN:
    DDL += _trigger(*_aturan)


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'transfer_*' ORDER BY type,name"))


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila parsial, berbeda, atau tanpa pesanan."""
    aktual = struktur(kon)
    if not aktual:
        return False
    if not sp.validasi(kon):
        raise ValueError("transfer tanpa ledger pesanan")
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(sp.DDL)
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError("struktur transfer tidak lengkap")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten; mensyaratkan ledger pesanan sudah terpasang."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not sp.validasi(kon):
            raise admin_store_core.StoreBelumSiap("pesanan belum dipasang")
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("integritas transfer gagal")

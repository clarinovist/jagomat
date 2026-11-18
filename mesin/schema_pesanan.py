"""Schema pesanan Paket Coba (sekali bayar); opt-in additive di DB admin-control.

Mengikuti pola `sensor_schema`/`policy_schema`: tanpa bump `user_version`, absent
sah (belum dimigrasikan), parsial/berbeda ditolak (fail-closed), dan migrasi
hanya lewat :func:`migrasikan` eksplisit (bukan startup/GET). Namespace
`pesanan_*` sengaja terpisah dari `langganan_*`: tidak ada FK ke sana, ke DB
belajar, maupun ke auth. Semua tabel append-only (trigger ABORT atas
UPDATE/DELETE dan replace-guard untuk setiap kunci unik); koreksi hanya lewat
baris baru, tidak pernah UPDATE/REPLACE.
"""
import sqlite3

# Waktu kanonis UTC naif 'YYYY-MM-DDTHH:MM:SS' agar urutan teks = urutan waktu.
_WAKTU = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
_HEX = "NOT GLOB '*[^0-9a-f]*'"
_ID = "NOT GLOB '*[^A-Za-z0-9_-]*'"

ALASAN_KODE = ("ok", "nominal", "merchant", "mata_uang", "kanal", "refund", "lainnya")
CATATAN_REFUND = ("permintaan_pembeli", "kesalahan_sistem", "kebijakan", "lainnya")


def _enum(nilai):
    return ",".join("'%s'" % n for n in nilai)


DDL = """
CREATE TABLE pesanan_order (
    order_id TEXT PRIMARY KEY CHECK(length(order_id)=36 AND substr(order_id,1,4)='ord_'
        AND substr(order_id,5) {hex}),
    akun_id TEXT NOT NULL CHECK(length(akun_id)=37 AND substr(akun_id,1,5)='akun_'
        AND substr(akun_id,6) {hex}),
    siswa_id INTEGER NOT NULL CHECK(siswa_id>=1),
    cek_id INTEGER NOT NULL CHECK(cek_id>=1),
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 1 AND 10000000),
    currency TEXT NOT NULL CHECK(currency='IDR'),
    provider TEXT NOT NULL CHECK(provider='midtrans'),
    channel TEXT NOT NULL CHECK(channel='qris'),
    merchant TEXT NOT NULL CHECK(length(merchant) BETWEEN 1 AND 64 AND merchant {id}),
    idempotency_key TEXT NOT NULL UNIQUE CHECK(length(idempotency_key) BETWEEN 8 AND 46),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    kedaluwarsa TEXT NOT NULL CHECK(kedaluwarsa GLOB {waktu} AND kedaluwarsa>dibuat),
    UNIQUE(siswa_id)
);
CREATE TABLE pesanan_pengamatan (
    operasi_id TEXT PRIMARY KEY CHECK(length(operasi_id) BETWEEN 8 AND 64 AND operasi_id {id}),
    order_id TEXT NOT NULL REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    sumber TEXT NOT NULL CHECK(sumber IN ('callback','status')),
    transaction_status TEXT NOT NULL CHECK(length(transaction_status) BETWEEN 1 AND 32),
    status_code TEXT NOT NULL CHECK(length(status_code) BETWEEN 0 AND 8),
    transaksi_id TEXT CHECK(transaksi_id IS NULL OR (length(transaksi_id) BETWEEN 1 AND 64
        AND transaksi_id {id})),
    gross_amount_teks TEXT NOT NULL CHECK(length(gross_amount_teks) BETWEEN 0 AND 20),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE pesanan_receipt (
    provider TEXT NOT NULL CHECK(provider='midtrans'),
    transaksi_id TEXT NOT NULL CHECK(length(transaksi_id) BETWEEN 1 AND 64 AND transaksi_id {id}),
    order_id TEXT NOT NULL UNIQUE REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    hasil TEXT NOT NULL CHECK(hasil IN ('lunas','perlu_diperiksa')),
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 0 AND 99999999),
    alasan_kode TEXT NOT NULL CHECK(alasan_kode IN ({alasan})),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    PRIMARY KEY(provider,transaksi_id),
    CHECK((hasil='lunas')=(alasan_kode='ok'))
);
CREATE TABLE pesanan_yatim (
    operasi_id TEXT PRIMARY KEY CHECK(length(operasi_id) BETWEEN 8 AND 64 AND operasi_id {id}),
    order_id_teks TEXT NOT NULL CHECK(length(order_id_teks) BETWEEN 1 AND 40),
    status_hint TEXT NOT NULL CHECK(length(status_hint) BETWEEN 1 AND 32),
    hash_payload TEXT NOT NULL CHECK(length(hash_payload)=64 AND hash_payload {hex}),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE pesanan_refund (
    operasi_id TEXT PRIMARY KEY CHECK(length(operasi_id) BETWEEN 8 AND 64 AND operasi_id {id}),
    order_id TEXT NOT NULL UNIQUE REFERENCES pesanan_receipt(order_id) ON DELETE RESTRICT,
    dicatat_oleh TEXT NOT NULL CHECK(length(dicatat_oleh) BETWEEN 1 AND 64),
    catatan_kode TEXT NOT NULL CHECK(catatan_kode IN ({catatan})),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
""".format(hex=_HEX, id=_ID, waktu=_WAKTU, alasan=_enum(ALASAN_KODE),
           catatan=_enum(CATATAN_REFUND))

TABEL = ("pesanan_order", "pesanan_pengamatan", "pesanan_receipt",
         "pesanan_yatim", "pesanan_refund")

# Kunci unik per tabel; dipakai replace-guard (BEFORE INSERT menggigit juga
# INSERT OR REPLACE tanpa recursive_triggers). Akibatnya INSERT OR IGNORE tidak
# dapat dipakai sebagai idempotensi: domain memakai SELECT lalu INSERT.
_KUNCI = {
    "pesanan_order": ("order_id=NEW.order_id", "siswa_id=NEW.siswa_id",
                      "idempotency_key=NEW.idempotency_key"),
    "pesanan_pengamatan": ("operasi_id=NEW.operasi_id",),
    "pesanan_receipt": ("(provider=NEW.provider AND transaksi_id=NEW.transaksi_id)",
                        "order_id=NEW.order_id"),
    "pesanan_yatim": ("operasi_id=NEW.operasi_id",),
    "pesanan_refund": ("operasi_id=NEW.operasi_id", "order_id=NEW.order_id"),
}

for _tabel in TABEL:
    for _aksi in ("UPDATE", "DELETE"):
        DDL += """
CREATE TRIGGER {tabel}_tolak_{nama} BEFORE {aksi} ON {tabel}
BEGIN SELECT RAISE(ABORT, 'ledger pesanan immutable'); END;
""".format(tabel=_tabel, nama=_aksi.lower(), aksi=_aksi)
    DDL += """
CREATE TRIGGER {tabel}_tolak_replace BEFORE INSERT ON {tabel}
WHEN EXISTS(SELECT 1 FROM {tabel} WHERE {cocok})
BEGIN SELECT RAISE(ABORT, 'ledger pesanan duplikat'); END;
""".format(tabel=_tabel, cocok=" OR ".join(_KUNCI[_tabel]))

# Receipt lunas wajib bernominal sama dengan order (lapis kedua di luar domain).
DDL += """
CREATE TRIGGER pesanan_receipt_lunas_nominal BEFORE INSERT ON pesanan_receipt
WHEN NEW.hasil='lunas' AND NEW.rupiah IS NOT (SELECT rupiah FROM pesanan_order WHERE order_id=NEW.order_id)
BEGIN SELECT RAISE(ABORT, 'receipt lunas tidak cocok dengan order'); END;
"""


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'pesanan_*' ORDER BY type,name"))


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila parsial atau berbeda."""
    aktual = struktur(kon)
    if not aktual:
        return False
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError("struktur pesanan tidak lengkap")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten pada DB admin yang sudah disiapkan."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("integritas pesanan gagal")

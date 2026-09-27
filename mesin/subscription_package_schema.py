"""Schema paket v2 additive admin8; ledger v1 tetap utuh.

Hanya dipasang lewat admin_store.siapkan(paket_v2=True), bukan GET/startup default.
Tidak memberi trial/grant, enrollment atau kampanye otomatis.
"""
import sqlite3

VERSI_SKEMA = 8
DDL = """
CREATE TABLE paket_akun (
    akun_id TEXT PRIMARY KEY REFERENCES langganan_enrollment(akun_id) ON DELETE RESTRICT,
    operasi_id TEXT NOT NULL UNIQUE,
    versi TEXT NOT NULL CHECK(versi='paket-jago-v2'),
    mulai INTEGER NOT NULL CHECK(mulai>=0),
    peserta_promo INTEGER NOT NULL CHECK(peserta_promo IN (0,1)),
    kampanye TEXT,
    CHECK((peserta_promo=1 AND kampanye IS NOT NULL) OR (peserta_promo=0 AND kampanye IS NULL))
);
CREATE TABLE paket_invoice (
    invoice_id TEXT PRIMARY KEY,
    akun_id TEXT NOT NULL REFERENCES paket_akun(akun_id) ON DELETE RESTRICT,
    urutan INTEGER NOT NULL CHECK(urutan>=1),
    versi TEXT NOT NULL CHECK(versi='paket-jago-v2'),
    paket TEXT NOT NULL CHECK(paket IN ('jago','jago_pro')),
    penagihan TEXT NOT NULL CHECK(penagihan IN ('bulanan','tahunan')),
    profil_json TEXT NOT NULL,
    promo INTEGER NOT NULL CHECK(promo IN (0,1)),
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 1 AND 10000000),
    normal INTEGER NOT NULL CHECK(normal BETWEEN rupiah AND 10000000),
    balasan INTEGER NOT NULL CHECK(balasan IN (0,50)),
    foto INTEGER NOT NULL CHECK(foto IN (0,5)),
    currency TEXT NOT NULL CHECK(currency='IDR'),
    provider TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel='qris'),
    merchant TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE CHECK(length(idempotency_key) BETWEEN 8 AND 46),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0),
    kedaluwarsa INTEGER NOT NULL CHECK(kedaluwarsa>dibuat),
    pajak TEXT NOT NULL CHECK(pajak='termasuk_bila_berlaku'),
    UNIQUE(akun_id,urutan)
);
CREATE TABLE paket_receipt (
    provider TEXT NOT NULL,
    transaksi_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL REFERENCES paket_invoice(invoice_id) ON DELETE RESTRICT,
    akun_id TEXT NOT NULL REFERENCES paket_akun(akun_id) ON DELETE RESTRICT,
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 1 AND 10000000),
    diterima INTEGER NOT NULL CHECK(diterima>=0),
    hasil TEXT NOT NULL CHECK(hasil IN ('grant','perlu_diperiksa')),
    PRIMARY KEY(provider,transaksi_id)
);
CREATE TABLE paket_grant (
    invoice_id TEXT PRIMARY KEY REFERENCES paket_invoice(invoice_id) ON DELETE RESTRICT,
    akun_id TEXT NOT NULL REFERENCES paket_akun(akun_id) ON DELETE RESTRICT,
    urutan INTEGER NOT NULL CHECK(urutan>=1),
    provider TEXT NOT NULL,
    transaksi_id TEXT NOT NULL,
    mulai INTEGER NOT NULL CHECK(mulai>=0),
    akhir INTEGER NOT NULL CHECK(akhir>mulai),
    jangkar_mulai INTEGER NOT NULL CHECK(jangkar_mulai>=0),
    indeks_bulan INTEGER NOT NULL CHECK(indeks_bulan>=0),
    UNIQUE(akun_id,urutan),
    UNIQUE(provider,transaksi_id),
    FOREIGN KEY(provider,transaksi_id) REFERENCES paket_receipt(provider,transaksi_id) ON DELETE RESTRICT
);
CREATE TABLE paket_rekonsiliasi (
    operasi_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES paket_invoice(invoice_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('belum_terverifikasi','perlu_diperiksa','settlement')),
    diamati INTEGER NOT NULL CHECK(diamati>=0),
    rujukan TEXT REFERENCES paket_rekonsiliasi(operasi_id) ON DELETE RESTRICT
);
"""
TABEL = ("paket_akun", "paket_invoice", "paket_receipt", "paket_grant", "paket_rekonsiliasi")
_KUNCI = {
    "paket_akun": "akun_id=NEW.akun_id OR operasi_id=NEW.operasi_id",
    "paket_invoice": "invoice_id=NEW.invoice_id OR (akun_id=NEW.akun_id AND urutan=NEW.urutan) OR idempotency_key=NEW.idempotency_key",
    "paket_receipt": "provider=NEW.provider AND transaksi_id=NEW.transaksi_id",
    "paket_grant": "invoice_id=NEW.invoice_id OR (akun_id=NEW.akun_id AND urutan=NEW.urutan) OR (provider=NEW.provider AND transaksi_id=NEW.transaksi_id)",
    "paket_rekonsiliasi": "operasi_id=NEW.operasi_id",
}
for _tabel in TABEL:
    for _aksi in ("UPDATE", "DELETE"):
        DDL += f"""
CREATE TRIGGER {_tabel}_tolak_{_aksi.lower()} BEFORE {_aksi} ON {_tabel}
BEGIN SELECT RAISE(ABORT, 'ledger paket immutable'); END;
"""
    DDL += f"""
CREATE TRIGGER {_tabel}_tolak_replace BEFORE INSERT ON {_tabel}
WHEN EXISTS(SELECT 1 FROM {_tabel} WHERE {_KUNCI[_tabel]})
BEGIN SELECT RAISE(ABORT, 'ledger paket duplikat'); END;
"""


def tersedia(kon):
    """Versi DB, bukan keberadaan satu tabel, menentukan reader yang wajib."""
    return kon.execute("PRAGMA user_version").fetchone()[0] == VERSI_SKEMA


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'paket_*' ORDER BY type,name"))


def validasi(kon):
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if struktur(kon) != struktur(acuan):
            raise ValueError("struktur ledger paket tidak lengkap")
    finally:
        acuan.close()

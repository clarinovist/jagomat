"""DDL additive admin6; ledger minimum tanpa data belajar/kontak/payload provider.

Migrasi hanya dipanggil admin_store.siapkan. Seluruh catatan append-only; koreksi
kelak melalui referensi baru, bukan UPDATE/REPLACE/DELETE atau purge audit admin.
"""

import sqlite3

DDL = """
CREATE TABLE langganan_aturan (
    versi TEXT PRIMARY KEY,
    hari_trial INTEGER NOT NULL CHECK(hari_trial=30),
    periode_promo INTEGER NOT NULL CHECK(periode_promo=3),
    dasar_promo INTEGER NOT NULL CHECK(dasar_promo=10000),
    anak_promo INTEGER NOT NULL CHECK(anak_promo=5000),
    dasar_lanjutan INTEGER NOT NULL CHECK(dasar_lanjutan=25000),
    anak_lanjutan INTEGER NOT NULL CHECK(anak_lanjutan=10000),
    pajak TEXT NOT NULL CHECK(pajak='belum_ditetapkan')
);
CREATE TABLE langganan_kampanye (
    kampanye_id TEXT PRIMARY KEY,
    mulai INTEGER NOT NULL CHECK(mulai>=0),
    akhir INTEGER NOT NULL CHECK(akhir=mulai+4838400),
    kuota INTEGER NOT NULL CHECK(kuota=100)
);
CREATE TABLE langganan_enrollment (
    akun_id TEXT PRIMARY KEY,
    sumber_id TEXT NOT NULL UNIQUE,
    asal TEXT NOT NULL CHECK(asal IN ('publik','transisi')),
    mulai INTEGER NOT NULL CHECK(mulai>=0),
    peserta_promo INTEGER NOT NULL CHECK(peserta_promo IN (0,1)),
    kampanye_id TEXT REFERENCES langganan_kampanye(kampanye_id) ON DELETE RESTRICT,
    versi TEXT NOT NULL REFERENCES langganan_aturan(versi) ON DELETE RESTRICT,
    CHECK(asal!='publik' OR peserta_promo=0 OR kampanye_id IS NOT NULL)
);
CREATE TABLE langganan_cakupan (
    operasi_id TEXT PRIMARY KEY,
    akun_id TEXT NOT NULL REFERENCES langganan_enrollment(akun_id) ON DELETE RESTRICT,
    urutan INTEGER NOT NULL CHECK(urutan>=1),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    profil_json TEXT NOT NULL,
    dibuat INTEGER NOT NULL,
    UNIQUE(akun_id,urutan,revisi)
);
CREATE TABLE langganan_invoice (
    invoice_id TEXT PRIMARY KEY,
    akun_id TEXT NOT NULL REFERENCES langganan_enrollment(akun_id) ON DELETE RESTRICT,
    urutan INTEGER NOT NULL CHECK(urutan>=1),
    versi TEXT NOT NULL REFERENCES langganan_aturan(versi) ON DELETE RESTRICT,
    cakupan_id TEXT NOT NULL REFERENCES langganan_cakupan(operasi_id) ON DELETE RESTRICT,
    profil_json TEXT NOT NULL,
    promo INTEGER NOT NULL CHECK(promo IN (0,1)),
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 1 AND 10000000),
    currency TEXT NOT NULL CHECK(currency='IDR'),
    provider TEXT NOT NULL,
    channel TEXT NOT NULL,
    merchant TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE CHECK(length(idempotency_key) BETWEEN 8 AND 46),
    dibuat INTEGER NOT NULL,
    kedaluwarsa INTEGER NOT NULL CHECK(kedaluwarsa>dibuat),
    pajak TEXT NOT NULL CHECK(pajak='belum_ditetapkan'),
    koreksi_dari TEXT REFERENCES langganan_invoice(invoice_id) ON DELETE RESTRICT,
    UNIQUE(akun_id,urutan)
);
CREATE TABLE langganan_receipt (
    provider TEXT NOT NULL,
    transaksi_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL REFERENCES langganan_invoice(invoice_id) ON DELETE RESTRICT,
    akun_id TEXT NOT NULL REFERENCES langganan_enrollment(akun_id) ON DELETE RESTRICT,
    rupiah INTEGER NOT NULL CHECK(rupiah BETWEEN 1 AND 10000000),
    diterima INTEGER NOT NULL,
    hasil TEXT NOT NULL CHECK(hasil IN ('grant','perlu_diperiksa')),
    PRIMARY KEY(provider,transaksi_id)
);
CREATE TABLE langganan_grant (
    invoice_id TEXT PRIMARY KEY REFERENCES langganan_invoice(invoice_id) ON DELETE RESTRICT,
    akun_id TEXT NOT NULL REFERENCES langganan_enrollment(akun_id) ON DELETE RESTRICT,
    urutan INTEGER NOT NULL CHECK(urutan>=1),
    provider TEXT NOT NULL,
    transaksi_id TEXT NOT NULL,
    mulai INTEGER NOT NULL,
    akhir INTEGER NOT NULL CHECK(akhir>mulai),
    jangkar INTEGER NOT NULL CHECK(jangkar BETWEEN 1 AND 31),
    profil_json TEXT NOT NULL,
    promo INTEGER NOT NULL CHECK(promo IN (0,1)),
    UNIQUE(akun_id,urutan),
    UNIQUE(provider,transaksi_id),
    FOREIGN KEY(provider,transaksi_id) REFERENCES langganan_receipt(provider,transaksi_id) ON DELETE RESTRICT
);
CREATE TABLE langganan_rekonsiliasi (
    operasi_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES langganan_invoice(invoice_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('belum_terverifikasi','perlu_diperiksa','settlement')),
    diamati INTEGER NOT NULL,
    rujukan TEXT REFERENCES langganan_rekonsiliasi(operasi_id) ON DELETE RESTRICT
);
"""

TABEL = ("langganan_aturan", "langganan_kampanye", "langganan_enrollment",
         "langganan_cakupan", "langganan_invoice", "langganan_receipt",
         "langganan_grant", "langganan_rekonsiliasi")
for _tabel in TABEL:
    for _aksi in ("UPDATE", "DELETE"):
        DDL += """
CREATE TRIGGER {tabel}_tolak_{nama} BEFORE {aksi} ON {tabel}
BEGIN SELECT RAISE(ABORT, 'ledger langganan immutable'); END;
""".format(tabel=_tabel, nama=_aksi.lower(), aksi=_aksi)
    # BEFORE INSERT tetap menggigit INSERT OR REPLACE tanpa recursive_triggers.
    _kunci = {"langganan_aturan": "versi", "langganan_kampanye": "kampanye_id",
              "langganan_enrollment": "akun_id", "langganan_receipt": "provider,transaksi_id"}.get(_tabel, "invoice_id" if _tabel in ("langganan_invoice", "langganan_grant") else "operasi_id")
    _cocok = " AND ".join(k + "=NEW." + k for k in _kunci.split(","))
    # Semua unique key juga dilindungi dari REPLACE melalui indeks alternatif.
    _alternatif = {
        "langganan_enrollment": " OR sumber_id=NEW.sumber_id",
        "langganan_cakupan": " OR (akun_id=NEW.akun_id AND urutan=NEW.urutan AND revisi=NEW.revisi)",
        "langganan_invoice": " OR (akun_id=NEW.akun_id AND urutan=NEW.urutan) OR idempotency_key=NEW.idempotency_key",
        "langganan_grant": " OR (akun_id=NEW.akun_id AND urutan=NEW.urutan) OR (provider=NEW.provider AND transaksi_id=NEW.transaksi_id)",
    }.get(_tabel, "")
    DDL += """
CREATE TRIGGER {tabel}_tolak_replace BEFORE INSERT ON {tabel}
WHEN EXISTS(SELECT 1 FROM {tabel} WHERE ({cocok}){alternatif})
BEGIN SELECT RAISE(ABORT, 'ledger langganan duplikat'); END;
""".format(tabel=_tabel, cocok=_cocok, alternatif=_alternatif)


def struktur(kon):
    return tuple(kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name LIKE 'langganan_%' ORDER BY type,name"
    ).fetchall())


def validasi(kon):
    """Bandingkan DDL/unique/FK/trigger, bukan percaya user_version/nama saja."""
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if tuple(tuple(r) for r in struktur(kon)) != struktur(acuan):
            raise ValueError("struktur ledger langganan tidak lengkap")
    finally:
        acuan.close()

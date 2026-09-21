"""Schema aditif pilot; startup memasang tabel tanpa membuat keputusan belajar.

Versi konteks v1 homogen tetap utuh. Tabel baru menambah ikatan tuntutan dengan
sumber snapshot tanpa mengubah fingerprint/konfirmasi historis.
"""
SKEMA_PILOT = """
CREATE TABLE IF NOT EXISTS pilot_aksi (
    kunci TEXT PRIMARY KEY,
    siswa_id INTEGER NOT NULL REFERENCES siswa(id) ON DELETE RESTRICT,
    tujuan TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS pilot_aksi_tolak_update BEFORE UPDATE ON pilot_aksi
BEGIN SELECT RAISE(ABORT,'receipt pilot immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilot_aksi_tolak_delete BEFORE DELETE ON pilot_aksi
BEGIN SELECT RAISE(ABORT,'receipt pilot immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilot_aksi_tolak_replace BEFORE INSERT ON pilot_aksi
WHEN EXISTS (SELECT 1 FROM pilot_aksi WHERE kunci=NEW.kunci)
BEGIN SELECT RAISE(ABORT,'receipt pilot immutable'); END;
CREATE TABLE IF NOT EXISTS pilot_putaran (
    putaran_id INTEGER PRIMARY KEY REFERENCES putaran_fokus(id) ON DELETE RESTRICT,
    konteks_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS pilot_putaran_tolak_update
BEFORE UPDATE ON pilot_putaran BEGIN
    SELECT RAISE(ABORT,'putaran pilot immutable');
END;
CREATE TRIGGER IF NOT EXISTS pilot_putaran_tolak_delete
BEFORE DELETE ON pilot_putaran BEGIN
    SELECT RAISE(ABORT,'putaran pilot immutable');
END;
CREATE TRIGGER IF NOT EXISTS pilot_putaran_tolak_replace
BEFORE INSERT ON pilot_putaran WHEN EXISTS (
    SELECT 1 FROM pilot_putaran WHERE putaran_id=NEW.putaran_id
) BEGIN
    SELECT RAISE(ABORT,'putaran pilot immutable');
END;
CREATE TABLE IF NOT EXISTS pilot_fokus_sumber (
    anggota_id INTEGER NOT NULL REFERENCES anggota_fokus(id) ON DELETE RESTRICT,
    konfirmasi_id INTEGER NOT NULL REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
    PRIMARY KEY(anggota_id, konfirmasi_id)
);
CREATE TRIGGER IF NOT EXISTS pilot_fokus_sumber_update BEFORE UPDATE ON pilot_fokus_sumber
BEGIN SELECT RAISE(ABORT,'sumber fokus pilot immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilot_fokus_sumber_delete BEFORE DELETE ON pilot_fokus_sumber
BEGIN SELECT RAISE(ABORT,'sumber fokus pilot immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilot_fokus_sumber_replace BEFORE INSERT ON pilot_fokus_sumber
WHEN EXISTS (SELECT 1 FROM pilot_fokus_sumber WHERE anggota_id=NEW.anggota_id AND konfirmasi_id=NEW.konfirmasi_id)
BEGIN SELECT RAISE(ABORT,'sumber fokus pilot immutable'); END;
CREATE TABLE IF NOT EXISTS pilot_sesi (
    sesi_id INTEGER PRIMARY KEY REFERENCES sesi(id) ON DELETE RESTRICT,
    versi INTEGER NOT NULL CHECK (versi=1),
    kontrak_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64)
);
CREATE TABLE IF NOT EXISTS pilot_konfirmasi (
    konfirmasi_id INTEGER PRIMARY KEY REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
    sesi_id INTEGER NOT NULL REFERENCES pilot_sesi(sesi_id) ON DELETE RESTRICT,
    kontrak_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64)
);
CREATE TRIGGER IF NOT EXISTS pilot_sesi_tolak_replace
BEFORE INSERT ON pilot_sesi WHEN EXISTS (
    SELECT 1 FROM pilot_sesi WHERE sesi_id=NEW.sesi_id
) BEGIN
    SELECT RAISE(ABORT,'konteks pilot immutable');
END;
CREATE TRIGGER IF NOT EXISTS pilot_konfirmasi_tolak_replace
BEFORE INSERT ON pilot_konfirmasi WHEN EXISTS (
    SELECT 1 FROM pilot_konfirmasi WHERE konfirmasi_id=NEW.konfirmasi_id
) BEGIN
    SELECT RAISE(ABORT,'konfirmasi pilot append-only');
END;
CREATE TRIGGER IF NOT EXISTS pilot_sesi_tolak_update
BEFORE UPDATE ON pilot_sesi BEGIN
    SELECT RAISE(ABORT,'konteks pilot immutable');
END;
CREATE TRIGGER IF NOT EXISTS pilot_sesi_tolak_delete
BEFORE DELETE ON pilot_sesi BEGIN
    SELECT RAISE(ABORT,'konteks pilot immutable');
END;
CREATE TRIGGER IF NOT EXISTS pilot_konfirmasi_tolak_update
BEFORE UPDATE ON pilot_konfirmasi BEGIN
    SELECT RAISE(ABORT,'konfirmasi pilot append-only');
END;
CREATE TRIGGER IF NOT EXISTS pilot_konfirmasi_tolak_delete
BEFORE DELETE ON pilot_konfirmasi BEGIN
    SELECT RAISE(ABORT,'konfirmasi pilot append-only');
END;
CREATE TRIGGER IF NOT EXISTS pilot_konfirmasi_sumber
BEFORE INSERT ON pilot_konfirmasi
WHEN NOT EXISTS (
    SELECT 1 FROM konfirmasi_hasil kh JOIN pilot_sesi ps ON ps.sesi_id=kh.sesi_id
    WHERE kh.id=NEW.konfirmasi_id AND ps.sesi_id=NEW.sesi_id
      AND ps.kontrak_json=NEW.kontrak_json AND ps.fingerprint=NEW.fingerprint
) BEGIN
    SELECT RAISE(ABORT,'sumber konfirmasi pilot tidak cocok');
END;
"""


def siapkan_pilot(kon):
    """Migrasi lokal eksplisit, idempoten dan gagal atomik; tanpa backfill."""
    from database import _jalankan_skema
    kon.execute("SAVEPOINT schema_pilot")
    try:
        _jalankan_skema(kon, SKEMA_PILOT)
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("foreign key pilot tidak utuh")
        kon.execute("RELEASE SAVEPOINT schema_pilot")
    except Exception:
        kon.execute("ROLLBACK TO SAVEPOINT schema_pilot")
        kon.execute("RELEASE SAVEPOINT schema_pilot")
        raise

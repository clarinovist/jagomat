"""Metadata konteks aditif; histori tanpa marker tetap memakai kontrak lama."""

SKEMA_KONTEKS = """
CREATE TABLE IF NOT EXISTS konteks_sesi (
    sesi_id INTEGER PRIMARY KEY REFERENCES sesi(id) ON DELETE CASCADE,
    versi INTEGER NOT NULL CHECK(versi = 1)
);
CREATE TABLE IF NOT EXISTS konteks_butir (
    sesi_soal_id INTEGER PRIMARY KEY REFERENCES sesi_soal(id) ON DELETE CASCADE,
    template_id TEXT NOT NULL,
    profil_parameter TEXT NOT NULL CHECK(profil_parameter IN ('P3','P4','P5','P6')),
    konteks_id TEXT
);
CREATE TRIGGER IF NOT EXISTS konteks_butir_validasi_insert
BEFORE INSERT ON konteks_butir
WHEN NOT EXISTS (
    SELECT 1 FROM sesi_soal ss JOIN soal so ON so.id=ss.soal_id
    JOIN sesi se ON se.id=ss.sesi_id JOIN konteks_sesi ks ON ks.sesi_id=se.id
    WHERE ss.id=NEW.sesi_soal_id AND so.template_id=NEW.template_id
      AND so.level=NEW.profil_parameter AND se.level=NEW.profil_parameter
      AND se.mulai IS NULL AND se.selesai IS NULL
      AND se.dikonfirmasi_guru IS NULL AND se.penyajian_dibekukan IS NULL
      AND se.dibatalkan IS NULL
) OR (NEW.konteks_id IS NOT NULL AND
      NEW.konteks_id != 'warisan-v1:' || NEW.template_id || ':' || NEW.profil_parameter)
BEGIN SELECT RAISE(ABORT, 'konteks butir tidak cocok sumber'); END;
CREATE TABLE IF NOT EXISTS konteks_konfirmasi (
    konfirmasi_id INTEGER PRIMARY KEY REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
    snapshot_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS konteks_konfirmasi_validasi_insert
BEFORE INSERT ON konteks_konfirmasi
WHEN NOT EXISTS (
    SELECT 1 FROM konfirmasi_hasil kh JOIN konteks_sesi ks ON ks.sesi_id=kh.sesi_id
    WHERE kh.id=NEW.konfirmasi_id
)
BEGIN SELECT RAISE(ABORT, 'konfirmasi tanpa kontrak konteks'); END;
"""

for tabel, kunci, induk, relasi in (
    ('konteks_sesi', 'sesi_id', 'sesi', 'id=OLD.sesi_id'),
    ('konteks_butir', 'sesi_soal_id', 'sesi_soal', 'id=OLD.sesi_soal_id'),
    ('konteks_konfirmasi', 'konfirmasi_id', 'konfirmasi_hasil', 'id=OLD.konfirmasi_id'),
):
    SKEMA_KONTEKS += f"""
CREATE TRIGGER IF NOT EXISTS {tabel}_immutable_update BEFORE UPDATE ON {tabel}
BEGIN SELECT RAISE(ABORT, 'metadata konteks immutable'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_immutable_replace BEFORE INSERT ON {tabel}
WHEN EXISTS (SELECT 1 FROM {tabel} WHERE {kunci}=NEW.{kunci})
BEGIN SELECT RAISE(ABORT, 'metadata konteks immutable'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_immutable_delete BEFORE DELETE ON {tabel}
WHEN EXISTS (SELECT 1 FROM {induk} WHERE {relasi})
BEGIN SELECT RAISE(ABORT, 'metadata konteks immutable'); END;
"""

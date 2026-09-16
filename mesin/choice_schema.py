"""Skema additive PG: snapshot publik, lifecycle, dan arsip immutable."""

SKEMA_PILIHAN = """
CREATE TRIGGER IF NOT EXISTS pilihan_format_immutable
BEFORE UPDATE OF format_jawaban ON sesi WHEN OLD.format_jawaban IS NOT NEW.format_jawaban
BEGIN SELECT RAISE(ABORT, 'format sesi immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_sesi_manual_insert
BEFORE INSERT ON sesi WHEN NEW.format_jawaban='pilihan_ganda'
 AND (NEW.tujuan!='bebas' OR NEW.jenis!='biasa' OR NEW.putaran_id IS NOT NULL)
BEGIN SELECT RAISE(ABORT, 'pilihan ganda hanya latihan manual'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_sesi_manual_update
BEFORE UPDATE ON sesi WHEN NEW.format_jawaban='pilihan_ganda'
 AND (NEW.tujuan!='bebas' OR NEW.jenis!='biasa' OR NEW.putaran_id IS NOT NULL)
BEGIN SELECT RAISE(ABORT, 'pilihan ganda hanya latihan manual'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_tolak_pemetaan
BEFORE INSERT ON kejadian_belajar WHEN NEW.jenis='sertakan_pemetaan'
 AND EXISTS(SELECT 1 FROM sesi WHERE id=NEW.sesi_id AND format_jawaban='pilihan_ganda')
BEGIN SELECT RAISE(ABORT, 'pilihan ganda bukan bukti pemetaan'); END;
CREATE TABLE IF NOT EXISTS pilihan_butir (
    sesi_soal_id INTEGER PRIMARY KEY REFERENCES sesi_soal(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL,
    fingerprint_opsi TEXT NOT NULL CHECK(length(fingerprint_opsi) = 64)
);
CREATE TRIGGER IF NOT EXISTS pilihan_butir_validasi_insert
BEFORE INSERT ON pilihan_butir
WHEN NOT EXISTS (
    SELECT 1 FROM sesi_soal ss JOIN sesi se ON se.id=ss.sesi_id
    WHERE ss.id=NEW.sesi_soal_id AND se.format_jawaban='pilihan_ganda' AND se.tujuan='bebas'
      AND se.jenis='biasa' AND se.putaran_id IS NULL
      AND se.mulai IS NULL AND se.selesai IS NULL AND se.dibatalkan IS NULL
      AND se.penyajian_dibekukan IS NULL AND se.dikonfirmasi_guru IS NULL
      AND NOT EXISTS (SELECT 1 FROM jawaban j JOIN sesi_soal lain
                      ON lain.id=j.sesi_soal_id WHERE lain.sesi_id=se.id)
      AND NOT EXISTS (SELECT 1 FROM pengiriman_sesi p WHERE p.sesi_id=se.id)
      AND NOT EXISTS (SELECT 1 FROM konfirmasi_hasil k WHERE k.sesi_id=se.id)
) OR pilihan_snapshot_sah(NEW.snapshot_json, NEW.fingerprint_opsi,
    NEW.sesi_soal_id, (SELECT fingerprint_penyajian FROM sesi_soal
                      WHERE id=NEW.sesi_soal_id)) IS NOT 1
BEGIN SELECT RAISE(ABORT, 'snapshot pilihan tidak sah atau sesi terkunci'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_butir_tolak_replace
BEFORE INSERT ON pilihan_butir
WHEN EXISTS (SELECT 1 FROM pilihan_butir WHERE sesi_soal_id=NEW.sesi_soal_id)
BEGIN SELECT RAISE(ABORT, 'snapshot pilihan immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_butir_tolak_update
BEFORE UPDATE ON pilihan_butir
BEGIN SELECT RAISE(ABORT, 'snapshot pilihan immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_butir_tolak_delete
BEFORE DELETE ON pilihan_butir
WHEN EXISTS (SELECT 1 FROM sesi_soal WHERE id=OLD.sesi_soal_id)
BEGIN SELECT RAISE(ABORT, 'snapshot pilihan immutable'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_butir_kunci_pertanyaan
BEFORE UPDATE OF id, sesi_id, soal_id, nomor, fingerprint_penyajian,
                 penyajian_json, teks_soal, fingerprint_matematis,
                 bagian_soal, tantangan_soal, minta_restatement, penyajian_versi,
                 renderer_versi, asal_teks, status_visual, mode_representasi ON sesi_soal
WHEN EXISTS (SELECT 1 FROM pilihan_butir WHERE sesi_soal_id=OLD.id)
BEGIN SELECT RAISE(ABORT, 'pertanyaan memiliki snapshot pilihan'); END;
CREATE TRIGGER IF NOT EXISTS pilihan_butir_tolak_hapus_pertanyaan
BEFORE DELETE ON sesi_soal
WHEN EXISTS (SELECT 1 FROM pilihan_butir WHERE sesi_soal_id=OLD.id)
 AND EXISTS (SELECT 1 FROM sesi WHERE id=OLD.sesi_id)
BEGIN SELECT RAISE(ABORT, 'pertanyaan memiliki snapshot pilihan'); END;
CREATE TABLE IF NOT EXISTS pengiriman_pilihan (
 sesi_id INTEGER NOT NULL,
 sesi_soal_id INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL,
 fingerprint_opsi TEXT NOT NULL,
 PRIMARY KEY(sesi_id,sesi_soal_id),
 FOREIGN KEY(sesi_id,sesi_soal_id) REFERENCES pengiriman_butir(sesi_id,sesi_soal_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS konfirmasi_pilihan (
 konfirmasi_id INTEGER NOT NULL REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
 sesi_soal_id INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL,
 fingerprint_opsi TEXT NOT NULL,
 PRIMARY KEY(konfirmasi_id,sesi_soal_id)
);
"""

for aksi in ('INSERT', 'UPDATE'):
    SKEMA_PILIHAN += f"""
CREATE TRIGGER IF NOT EXISTS pilihan_jawaban_{aksi.lower()}
BEFORE {aksi} ON jawaban
WHEN EXISTS(SELECT 1 FROM sesi_soal ss JOIN sesi se ON se.id=ss.sesi_id
            WHERE ss.id=NEW.sesi_soal_id AND se.format_jawaban='pilihan_ganda')
 AND NOT EXISTS(SELECT 1 FROM pilihan_butir p JOIN sesi_soal ss ON ss.id=p.sesi_soal_id
   WHERE p.sesi_soal_id=NEW.sesi_soal_id AND pilihan_jawaban_sah(
       p.snapshot_json,p.fingerprint_opsi,ss.id,ss.fingerprint_penyajian,NEW.jawaban)=1)
BEGIN SELECT RAISE(ABORT, 'jawaban tidak cocok opsi tersimpan'); END;
"""
for tabel, kunci in (('pengiriman_pilihan', 'sesi_id'), ('konfirmasi_pilihan', 'konfirmasi_id')):
    kondisi = "WHEN EXISTS(SELECT 1 FROM sesi WHERE id=OLD.sesi_id)" if tabel == 'pengiriman_pilihan' else ''
    induk_sesi = 'NEW.sesi_id' if tabel == 'pengiriman_pilihan' else '(SELECT sesi_id FROM konfirmasi_hasil WHERE id=NEW.konfirmasi_id)'
    SKEMA_PILIHAN += f"""
CREATE TRIGGER IF NOT EXISTS {tabel}_validasi_insert BEFORE INSERT ON {tabel}
WHEN NOT EXISTS(SELECT 1 FROM pilihan_butir p JOIN sesi_soal ss ON ss.id=p.sesi_soal_id
 WHERE ss.sesi_id={induk_sesi} AND p.sesi_soal_id=NEW.sesi_soal_id
 AND p.snapshot_json=NEW.snapshot_json AND p.fingerprint_opsi=NEW.fingerprint_opsi)
BEGIN SELECT RAISE(ABORT, 'arsip pilihan tidak cocok sumber'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_immutable_update BEFORE UPDATE ON {tabel}
BEGIN SELECT RAISE(ABORT, 'arsip pilihan immutable'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_immutable_delete BEFORE DELETE ON {tabel} {kondisi}
BEGIN SELECT RAISE(ABORT, 'arsip pilihan immutable'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_immutable_replace BEFORE INSERT ON {tabel}
WHEN EXISTS(SELECT 1 FROM {tabel} WHERE {kunci}=NEW.{kunci} AND sesi_soal_id=NEW.sesi_soal_id)
BEGIN SELECT RAISE(ABORT, 'arsip pilihan immutable'); END;
"""

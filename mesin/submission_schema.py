"""Skema additive refleksi, arsip pengiriman, dan tinjauan guru lokal."""

SKEMA_PENGIRIMAN = """
CREATE TABLE IF NOT EXISTS refleksi_jawaban (
    sesi_soal_id INTEGER PRIMARY KEY REFERENCES sesi_soal(id) ON DELETE CASCADE,
    alasan TEXT NOT NULL CHECK (alasan IN ('', 'maksud_soal', 'langkah_awal',
        'belum_sempat', 'belum_bisa_menjelaskan'))
);
CREATE TABLE IF NOT EXISTS versi_pekerjaan (
    sesi_id INTEGER PRIMARY KEY REFERENCES sesi(id) ON DELETE CASCADE,
    revisi INTEGER NOT NULL DEFAULT 0 CHECK (revisi >= 0)
);
CREATE TABLE IF NOT EXISTS pengiriman_sesi (
    sesi_id INTEGER PRIMARY KEY REFERENCES sesi(id) ON DELETE CASCADE,
    sumber TEXT NOT NULL CHECK (sumber IN ('akun', 'tautan', 'foto')),
    dibuat TEXT NOT NULL DEFAULT (datetime('now', '+7 hours')),
    lampiran_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS pengiriman_butir (
    sesi_id INTEGER NOT NULL REFERENCES pengiriman_sesi(sesi_id) ON DELETE CASCADE,
    sesi_soal_id INTEGER NOT NULL,
    nomor INTEGER NOT NULL,
    jawaban TEXT NOT NULL, cara TEXT NOT NULL, restatement TEXT NOT NULL,
    belum_pernah INTEGER NOT NULL CHECK (belum_pernah IN (0, 1)),
    alasan TEXT NOT NULL CHECK (alasan IN ('', 'maksud_soal', 'langkah_awal',
        'belum_sempat', 'belum_bisa_menjelaskan')),
    penyajian_json TEXT NOT NULL,
    PRIMARY KEY (sesi_id, sesi_soal_id), UNIQUE (sesi_id, nomor)
);
CREATE TABLE IF NOT EXISTS tinjauan_guru (
    sesi_soal_id INTEGER PRIMARY KEY REFERENCES sesi_soal(id) ON DELETE CASCADE,
    revisi INTEGER NOT NULL CHECK (revisi > 0),
    catatan TEXT NOT NULL DEFAULT '',
    provenance TEXT NOT NULL DEFAULT '' CHECK (provenance IN
        ('', 'penjelasan_asli', 'koreksi_transkripsi', 'setelah_bantuan')),
    jawaban_bantuan TEXT NOT NULL DEFAULT '',
    pemahaman TEXT NOT NULL DEFAULT '' CHECK (pemahaman IN
        ('', 'bisa_menjelaskan', 'ragu', 'menghafal')),
    dilewati INTEGER NOT NULL DEFAULT 0 CHECK (dilewati IN (0, 1)),
    guru TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tinjauan_outcome (
    konfirmasi_id INTEGER PRIMARY KEY REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
    data_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS pengiriman_butir_validasi
BEFORE INSERT ON pengiriman_butir
WHEN NOT EXISTS (SELECT 1 FROM sesi_soal WHERE id=NEW.sesi_soal_id
                 AND sesi_id=NEW.sesi_id AND nomor=NEW.nomor)
BEGIN SELECT RAISE(ABORT, 'butir pengiriman tidak sah'); END;
"""

for tabel in ('pengiriman_sesi', 'pengiriman_butir', 'tinjauan_outcome'):
    kunci = 'konfirmasi_id' if tabel == 'tinjauan_outcome' else 'sesi_id'
    if tabel == 'pengiriman_butir':
        syarat = 'sesi_id=NEW.sesi_id AND sesi_soal_id=NEW.sesi_soal_id'
    else:
        syarat = f'{kunci}=NEW.{kunci}'
    # Arsip pengiriman mengikuti lifecycle sesi belum berbukti; bukti existing
    # tetap RESTRICT. Hapus langsung saat sesi masih ada selalu ditolak.
    kondisi_hapus = (
        '' if tabel == 'tinjauan_outcome'
        else 'WHEN EXISTS (SELECT 1 FROM sesi WHERE id=OLD.sesi_id)'
    )
    SKEMA_PENGIRIMAN += f"""
CREATE TRIGGER IF NOT EXISTS {tabel}_tolak_update
BEFORE UPDATE ON {tabel} BEGIN SELECT RAISE(ABORT, 'arsip immutable'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_tolak_replace
BEFORE INSERT ON {tabel} WHEN EXISTS (SELECT 1 FROM {tabel} WHERE {syarat})
BEGIN SELECT RAISE(ABORT, 'arsip immutable'); END;
CREATE TRIGGER IF NOT EXISTS {tabel}_tolak_delete
BEFORE DELETE ON {tabel} {kondisi_hapus}
BEGIN SELECT RAISE(ABORT, 'arsip immutable'); END;
"""

for tabel, kolom in (
    ('jawaban', ('jawaban', 'cara', 'restatement', 'belum_pernah')),
    ('refleksi_jawaban', ('alasan',)),
):
    for aksi in ('INSERT', 'UPDATE', 'DELETE'):
        ref = 'OLD' if aksi == 'DELETE' else 'NEW'
        beda = 'WHEN ' + ' OR '.join(f'OLD.{k} IS NOT NEW.{k}' for k in kolom) if aksi == 'UPDATE' else ''
        SKEMA_PENGIRIMAN += f"""
CREATE TRIGGER IF NOT EXISTS {tabel}_versi_{aksi.lower()}
AFTER {aksi} ON {tabel} {beda}
BEGIN
    INSERT INTO versi_pekerjaan (sesi_id, revisi)
    SELECT sesi_id, 1 FROM sesi_soal WHERE id={ref}.sesi_soal_id
    ON CONFLICT(sesi_id) DO UPDATE SET revisi=revisi+1;
END;
"""

"""Skema admin7 additive untuk operasi layanan dan analitik opt-in."""

import sqlite3

DDL = """
CREATE TABLE pembayaran_konfigurasi (
    id INTEGER PRIMARY KEY CHECK(id=1), tahap TEXT NOT NULL CHECK(tahap IN
        ('nonaktif','rekonsiliasi','checkout','penegakan')),
    revisi INTEGER NOT NULL CHECK(revisi>=1), diperbarui INTEGER NOT NULL,
    actor_id TEXT NOT NULL
);
CREATE TABLE pembayaran_audit (
    operasi_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, actor_revisi INTEGER NOT NULL,
    tahap_lama TEXT NOT NULL CHECK(tahap_lama IN
        ('nonaktif','rekonsiliasi','checkout','penegakan')),
    tahap_baru TEXT NOT NULL CHECK(tahap_baru IN
        ('nonaktif','rekonsiliasi','checkout','penegakan')),
    revisi INTEGER NOT NULL CHECK(revisi>=1), dibuat INTEGER NOT NULL
);
CREATE TRIGGER pembayaran_config_tolak_delete BEFORE DELETE ON pembayaran_konfigurasi
BEGIN SELECT RAISE(ABORT,'konfigurasi pembayaran tidak boleh dihapus'); END;
CREATE TRIGGER pembayaran_audit_tolak_update BEFORE UPDATE ON pembayaran_audit
BEGIN SELECT RAISE(ABORT,'audit pembayaran immutable'); END;
CREATE TRIGGER pembayaran_audit_tolak_delete BEFORE DELETE ON pembayaran_audit
BEGIN SELECT RAISE(ABORT,'audit pembayaran immutable'); END;
CREATE TRIGGER pembayaran_audit_tolak_replace BEFORE INSERT ON pembayaran_audit
WHEN EXISTS(SELECT 1 FROM pembayaran_audit WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'audit pembayaran duplikat'); END;
CREATE TABLE layanan_operasi (
    operasi_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, actor_revisi INTEGER NOT NULL,
    aksi TEXT NOT NULL CHECK(aksi IN ('periksa_pembayaran','atur_pembayaran','biaya','eksperimen')),
    target_id TEXT NOT NULL, sidik TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('tertunda','selesai','perlu_diperiksa')),
    hasil TEXT NOT NULL, dibuat INTEGER NOT NULL, diperbarui INTEGER NOT NULL
);
CREATE TABLE kpi_eksperimen (
    id TEXT PRIMARY KEY, versi TEXT NOT NULL, mulai INTEGER NOT NULL,
    akhir INTEGER NOT NULL CHECK(akhir>mulai), koleksi INTEGER NOT NULL CHECK(koleksi IN (0,1)),
    revisi INTEGER NOT NULL CHECK(revisi>=1), kualitas TEXT NOT NULL
        CHECK(kualitas IN ('belum_terverifikasi','lengkap','terganggu')),
    boot_id TEXT NOT NULL, diperbarui INTEGER NOT NULL
);
CREATE TABLE kpi_peserta (
    id TEXT PRIMARY KEY, eksperimen TEXT NOT NULL REFERENCES kpi_eksperimen(id),
    akun_id TEXT NOT NULL, t0 INTEGER NOT NULL, consent INTEGER NOT NULL,
    versi_consent TEXT NOT NULL, consent_boot TEXT NOT NULL, sumber TEXT NOT NULL CHECK(sumber IN
        ('rekomendasi','pencarian','komunitas','iklan','lainnya','tidak_diketahui')),
    terlambat INTEGER NOT NULL CHECK(terlambat IN (0,1)),
    UNIQUE(eksperimen,akun_id)
);
CREATE TABLE kpi_aktivitas (
    peserta TEXT NOT NULL REFERENCES kpi_peserta(id) ON DELETE CASCADE,
    hari TEXT NOT NULL, kode TEXT NOT NULL CHECK(kode IN
        ('latihan_dikirim','lembar_soal_disajikan','panduan_hasil_disajikan')),
    jendela INTEGER NOT NULL CHECK(jendela IN (1,2,3)),
    PRIMARY KEY(peserta,hari,kode,jendela)
);
CREATE TABLE kpi_survei (
    peserta TEXT PRIMARY KEY REFERENCES kpi_peserta(id) ON DELETE CASCADE,
    ditawari INTEGER NOT NULL, jawaban TEXT CHECK(jawaban IN ('ya','sebagian','belum')),
    dijawab INTEGER, versi TEXT NOT NULL
);
CREATE TABLE kpi_biaya (
    bulan TEXT PRIMARY KEY, revisi INTEGER NOT NULL CHECK(revisi>=1),
    anggaran INTEGER NOT NULL CHECK(anggaran BETWEEN 0 AND 1000000000),
    server INTEGER NOT NULL CHECK(server BETWEEN 0 AND 1000000000),
    domain INTEGER NOT NULL CHECK(domain BETWEEN 0 AND 1000000000),
    ai INTEGER NOT NULL CHECK(ai BETWEEN 0 AND 1000000000),
    pendukung INTEGER NOT NULL CHECK(pendukung BETWEEN 0 AND 1000000000),
    lengkap INTEGER NOT NULL CHECK(lengkap IN (0,1)), diperbarui INTEGER NOT NULL
);
CREATE TABLE kpi_audit_biaya (
    operasi_id TEXT PRIMARY KEY REFERENCES layanan_operasi(operasi_id),
    bulan TEXT NOT NULL, revisi INTEGER NOT NULL, snapshot TEXT NOT NULL,
    UNIQUE(bulan,revisi)
);
CREATE TABLE kpi_cakupan (
    eksperimen TEXT PRIMARY KEY REFERENCES kpi_eksperimen(id),
    dicabut INTEGER NOT NULL DEFAULT 0, kedaluwarsa INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE kpi_agregat (
    eksperimen TEXT NOT NULL REFERENCES kpi_eksperimen(id), minggu INTEGER NOT NULL,
    peserta INTEGER NOT NULL, aktivasi INTEGER NOT NULL, kembali INTEGER NOT NULL,
    penawaran INTEGER NOT NULL, respons INTEGER NOT NULL, positif INTEGER NOT NULL,
    organik INTEGER NOT NULL, terlambat INTEGER NOT NULL,
    dibuat INTEGER NOT NULL, hapus_setelah INTEGER NOT NULL,
    PRIMARY KEY(eksperimen,minggu)
);
CREATE INDEX idx_layanan_status ON layanan_operasi(status,diperbarui);
CREATE INDEX idx_kpi_retensi ON kpi_peserta(t0);
CREATE TRIGGER kpi_audit_tolak_update BEFORE UPDATE ON kpi_audit_biaya
BEGIN SELECT RAISE(ABORT,'audit biaya immutable'); END;
CREATE TRIGGER kpi_audit_tolak_delete BEFORE DELETE ON kpi_audit_biaya
BEGIN SELECT RAISE(ABORT,'audit biaya immutable'); END;
CREATE TRIGGER kpi_audit_tolak_replace BEFORE INSERT ON kpi_audit_biaya
WHEN EXISTS(SELECT 1 FROM kpi_audit_biaya WHERE operasi_id=NEW.operasi_id
    OR (bulan=NEW.bulan AND revisi=NEW.revisi))
BEGIN SELECT RAISE(ABORT,'audit biaya duplikat'); END;
"""


def validasi(kon):
    """Verifikasi struktur exact agar versi saja tidak menjadi bukti kesiapan."""
    acuan = sqlite3.connect(':memory:')
    try:
        acuan.executescript(DDL)
        sql = ("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE "
               "tbl_name LIKE 'kpi_%' OR tbl_name IN "
               "('layanan_operasi','pembayaran_konfigurasi','pembayaran_audit') "
               "ORDER BY type,name")
        if tuple(tuple(r) for r in kon.execute(sql)) != tuple(acuan.execute(sql)):
            raise ValueError('struktur layanan tidak lengkap')
    finally:
        acuan.close()

"""Migrasi Simulasi Lomba: lomba_soal dibangun ulang (nomor 1..35) tanpa kehilangan sesi/soal/jawaban/penugasan.

DB lama dibuat dari DDL beku (salinan SKEMA_LOMBA sebelum 22 Nov 2026), bukan impor modul, supaya tes tetap
menggambarkan DB produksi lama walau skema kode berubah lagi.
"""
import sqlite3

import pytest

import database
import schema_lomba

DDL_LOMBA_LAMA = """
CREATE TABLE IF NOT EXISTS lomba_sesi (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id      INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    paket_id      TEXT    NOT NULL,
    seed          INTEGER NOT NULL,
    mulai_epoch   INTEGER NOT NULL,
    batas_epoch   INTEGER NOT NULL,
    selesai_epoch INTEGER,
    status        TEXT    NOT NULL CHECK (status IN ('berjalan', 'dikumpul', 'waktu_habis')),
    CHECK (batas_epoch > mulai_epoch),
    CHECK ((status = 'berjalan') = (selesai_epoch IS NULL)),
    CHECK (selesai_epoch IS NULL
           OR (selesai_epoch >= mulai_epoch AND selesai_epoch <= batas_epoch))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lomba_sesi_berjalan ON lomba_sesi(siswa_id) WHERE status = 'berjalan';
CREATE INDEX IF NOT EXISTS idx_lomba_sesi_siswa ON lomba_sesi(siswa_id, id);

CREATE TABLE IF NOT EXISTS lomba_soal (
    sesi_id              INTEGER NOT NULL REFERENCES lomba_sesi(id) ON DELETE CASCADE,
    nomor                INTEGER NOT NULL CHECK (nomor BETWEEN 1 AND 10),
    template_id          TEXT    NOT NULL,
    topik                TEXT    NOT NULL,
    jenis                TEXT    NOT NULL CHECK (jenis IN ('pg', 'isian')),
    tingkat              INTEGER NOT NULL CHECK (tingkat BETWEEN 1 AND 3),
    tanda_tangan         TEXT    NOT NULL,
    parameter            TEXT    NOT NULL,
    inggris              INTEGER NOT NULL DEFAULT 0 CHECK (inggris IN (0, 1)),
    teks                 TEXT    NOT NULL,
    svg                  TEXT    NOT NULL DEFAULT '',
    kunci                TEXT    NOT NULL,
    pilihan_json         TEXT    NOT NULL DEFAULT '[]',
    gambar_pilihan_json  TEXT    NOT NULL DEFAULT '[]',
    posisi_kunci         INTEGER NOT NULL CHECK (posisi_kunci BETWEEN -1 AND 3),
    pengecoh_json        TEXT    NOT NULL DEFAULT '[]',
    pembahasan_json      TEXT    NOT NULL,
    PRIMARY KEY (sesi_id, nomor)
);

CREATE TABLE IF NOT EXISTS lomba_jawaban (
    sesi_id      INTEGER NOT NULL,
    nomor        INTEGER NOT NULL,
    jawaban      TEXT    NOT NULL CHECK (length(jawaban) BETWEEN 1 AND 6),
    diubah_epoch INTEGER NOT NULL,
    PRIMARY KEY (sesi_id, nomor),
    FOREIGN KEY (sesi_id, nomor) REFERENCES lomba_soal(sesi_id, nomor) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lomba_penugasan (
    siswa_id             INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    paket_id             TEXT    NOT NULL CHECK (length(paket_id) BETWEEN 1 AND 64),
    aktif                INTEGER NOT NULL CHECK (aktif IN (0, 1)),
    target_harian        INTEGER CHECK (target_harian IS NULL OR target_harian BETWEEN 0 AND 5),
    tampil_hitung_mundur INTEGER CHECK (tampil_hitung_mundur IS NULL OR tampil_hitung_mundur IN (0, 1)),
    diubah_epoch         INTEGER NOT NULL,
    diubah_oleh          TEXT    NOT NULL DEFAULT '' CHECK (length(diubah_oleh) <= 64)
);
"""
TABEL_LOMBA = ("lomba_jawaban", "lomba_soal", "lomba_penugasan", "lomba_sesi")


def _kolom_soal(sesi_id, nomor):
    return (sesi_id, nomor, "bil_x", "bilangan", "pg" if nomor % 2 else "isian", 1, f"bil_x|{sesi_id}-{nomor}", "[]", 0,
            f"Soal {nomor}", "", "7", '["7","8","9","10"]' if nomor % 2 else "[]", "[]", 0 if nomor % 2 else -1, "[]", '["a"]')


def _buat_db_lama(path):
    """DB lengkap versi sekarang, lalu tabel lomba diganti DDL lama berisi dua anak, tiga sesi, soal, jawaban."""
    database.siapkan(path)
    kon = sqlite3.connect(str(path))
    kon.execute("PRAGMA foreign_keys = OFF")
    for tabel in TABEL_LOMBA:
        kon.execute(f"DROP TABLE IF EXISTS {tabel}")
    kon.executescript(DDL_LOMBA_LAMA)
    kon.execute("PRAGMA foreign_keys = ON")
    for nama in ("Anak A", "Anak B"):
        kon.execute("INSERT INTO siswa(nama, pemilik) VALUES (?, 'guru')", (nama,))
    a, b = [r[0] for r in kon.execute("SELECT id FROM siswa WHERE nama IN ('Anak A', 'Anak B') ORDER BY nama")]
    for siswa, status, selesai in ((a, "dikumpul", 1500), (a, "berjalan", None), (b, "waktu_habis", 1900)):
        sesi = kon.execute(
            "INSERT INTO lomba_sesi(siswa_id, paket_id, seed, mulai_epoch, batas_epoch, selesai_epoch, status) "
            "VALUES (?, 'corexis_l1_matematika', 1, 1000, 1900, ?, ?)", (siswa, selesai, status)).lastrowid
        for nomor in range(1, 11):
            kon.execute("INSERT INTO lomba_soal VALUES (" + ",".join("?" * 17) + ")", _kolom_soal(sesi, nomor))
            if nomor <= 6:
                kon.execute("INSERT INTO lomba_jawaban VALUES (?, ?, ?, 1200)", (sesi, nomor, "A" if nomor % 2 else "7"))
    kon.execute("INSERT INTO lomba_penugasan VALUES (?, 'corexis_l1_matematika', 1, 3, 0, 1000, 'guru')", (a,))
    kon.commit()
    kon.close()
    return a, b


def _isi(path):
    with database.buka(path) as kon:
        return {t: kon.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall() for t in TABEL_LOMBA}


def _baris_mentah(isi):
    return {t: [tuple(r) for r in baris] for t, baris in isi.items()}


def _sql(kon, nama):
    return kon.execute("SELECT sql FROM sqlite_master WHERE name = ?", (nama,)).fetchone()[0]


def test_migrasi_memperlebar_nomor_tanpa_mengubah_isi_dan_idempoten(tmp_path):
    path = tmp_path / "lama.db"
    _buat_db_lama(path)
    with database.buka(path) as kon:
        fk_jawaban_lama = _sql(kon, "lomba_jawaban")
    sebelum = _baris_mentah(_isi(path))

    database.siapkan(path)
    sesudah_sekali = _isi(path)
    database.siapkan(path)
    sesudah_dua_kali = _isi(path)

    assert len(sebelum["lomba_soal"]) == 30 and len(sebelum["lomba_jawaban"]) == 18
    for tabel in ("lomba_soal", "lomba_jawaban"):
        assert _baris_mentah(sesudah_sekali)[tabel] == sebelum[tabel]
    assert [tuple(r)[:-1] for r in sesudah_sekali["lomba_sesi"]] == sebelum["lomba_sesi"]
    assert {r["mode"] for r in sesudah_sekali["lomba_sesi"]} == {"latihan"}
    penugasan = sesudah_sekali["lomba_penugasan"][0]
    assert tuple(penugasan)[:7] == sebelum["lomba_penugasan"][0]
    assert penugasan["durasi_latihan_detik"] is None and penugasan["durasi_simulasi_detik"] is None
    assert _baris_mentah(sesudah_dua_kali) == _baris_mentah(sesudah_sekali)
    with database.buka(path) as kon:
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
        assert _sql(kon, "lomba_jawaban") == fk_jawaban_lama
        assert "BETWEEN 1 AND 35" in _sql(kon, "lomba_soal")
        assert kon.execute("SELECT name FROM sqlite_master WHERE name = 'lomba_soal_baru'").fetchone() is None


def test_setelah_migrasi_nomor_35_diterima_36_ditolak_dan_jawaban_tetap_berkunci_ke_soal(tmp_path):
    path = tmp_path / "lama.db"
    a, _ = _buat_db_lama(path)
    database.siapkan(path)
    with database.buka(path) as kon:
        sesi = kon.execute("SELECT id FROM lomba_sesi WHERE siswa_id = ? AND status = 'berjalan'", (a,)).fetchone()[0]

        kon.execute("INSERT INTO lomba_soal VALUES (" + ",".join("?" * 17) + ")", _kolom_soal(sesi, 35))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO lomba_soal VALUES (" + ",".join("?" * 17) + ")", _kolom_soal(sesi, 36))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO lomba_jawaban VALUES (?, 20, 'A', 1)", (sesi,))   # FK ke soal tetap hidup


def test_hapus_siswa_setelah_migrasi_tetap_kaskade_ke_semua_tabel_lomba(tmp_path):
    path = tmp_path / "lama.db"
    a, b = _buat_db_lama(path)
    database.siapkan(path)
    with database.buka(path) as kon:
        kon.execute("DELETE FROM siswa WHERE id = ?", (a,))
        kon.commit()
        sisa_sesi = {r[0] for r in kon.execute("SELECT siswa_id FROM lomba_sesi")}
        assert sisa_sesi == {b}
        assert kon.execute("SELECT COUNT(*) FROM lomba_soal").fetchone()[0] == 10
        assert kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0] == 6
        assert kon.execute("SELECT COUNT(*) FROM lomba_penugasan").fetchone()[0] == 0


def test_db_baru_langsung_lebar_dan_tidak_dibangun_ulang(tmp_path):
    path = tmp_path / "baru.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        kon.execute("PRAGMA foreign_keys = OFF")
        kon.execute("BEGIN IMMEDIATE")
        assert schema_lomba.perlebar_nomor_soal(kon) is False
        kon.rollback()
        assert "BETWEEN 1 AND 35" in _sql(kon, "lomba_soal")


def test_perlebar_menolak_bila_foreign_key_hidup_tanpa_menyentuh_jawaban(tmp_path):
    """Palang: DROP lomba_soal dengan FK hidup akan menghapus semua jawaban lewat CASCADE."""
    path = tmp_path / "lama.db"
    _buat_db_lama(path)
    kon = sqlite3.connect(str(path))
    kon.execute("PRAGMA foreign_keys = ON")
    kon.execute("BEGIN IMMEDIATE")
    with pytest.raises(sqlite3.IntegrityError):
        schema_lomba.perlebar_nomor_soal(kon)
    kon.rollback()
    assert kon.execute("SELECT COUNT(*) FROM lomba_jawaban").fetchone()[0] == 18
    assert "BETWEEN 1 AND 10" in _sql(kon, "lomba_soal")
    kon.close()


def test_perlebar_menolak_di_luar_transaksi(tmp_path):
    path = tmp_path / "lama.db"
    _buat_db_lama(path)
    kon = sqlite3.connect(str(path), isolation_level=None)
    kon.execute("PRAGMA foreign_keys = OFF")
    with pytest.raises(sqlite3.IntegrityError):
        schema_lomba.perlebar_nomor_soal(kon)
    assert "BETWEEN 1 AND 10" in _sql(kon, "lomba_soal")
    kon.close()

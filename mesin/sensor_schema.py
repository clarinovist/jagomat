"""Schema sensor internal opt-in; absent sah, parsial/berbeda ditolak."""
import sqlite3

VERSI = 1
DDL = """
CREATE TABLE sensor_schema (
    id INTEGER PRIMARY KEY CHECK(id=1),
    versi INTEGER NOT NULL CHECK(versi=1)
);
CREATE TABLE sensor_peserta (
    akun_id TEXT PRIMARY KEY,
    generasi TEXT NOT NULL UNIQUE CHECK(length(generasi)=32),
    salt TEXT NOT NULL CHECK(length(salt)=64),
    boot TEXT NOT NULL,
    mulai INTEGER NOT NULL CHECK(mulai>=0),
    berakhir INTEGER NOT NULL CHECK(berakhir=mulai+7776000),
    versi_consent TEXT NOT NULL CHECK(versi_consent='sensor-keluarga-v1'),
    hasil INTEGER NOT NULL CHECK(hasil IN (0,1)),
    chat INTEGER NOT NULL CHECK(chat IN (0,1))
);
CREATE TABLE sensor_episode (
    peserta TEXT NOT NULL REFERENCES sensor_peserta(generasi) ON DELETE CASCADE,
    token TEXT NOT NULL CHECK(length(token)=64),
    jalur TEXT NOT NULL CHECK(jalur IN ('manual','terpandu')),
    mulai INTEGER NOT NULL CHECK(mulai>=0),
    PRIMARY KEY(peserta,token)
);
CREATE TABLE sensor_event (
    peserta TEXT NOT NULL,
    token TEXT NOT NULL,
    kode TEXT NOT NULL CHECK(kode IN ('disiapkan','pekerjaan_disimpan','dikirim','tinjauan_disimpan','dikonfirmasi','dibatalkan','lanjutan_disiapkan','lembar_disajikan')),
    jam INTEGER NOT NULL CHECK(jam>=0),
    PRIMARY KEY(peserta,token,kode),
    FOREIGN KEY(peserta,token) REFERENCES sensor_episode(peserta,token) ON DELETE CASCADE
);
CREATE TABLE sensor_hasil (
    peserta TEXT NOT NULL,
    token TEXT NOT NULL,
    jumlah INTEGER NOT NULL CHECK(jumlah BETWEEN 1 AND 100),
    benar INTEGER NOT NULL CHECK(benar BETWEEN 0 AND jumlah),
    belum_jelas INTEGER NOT NULL CHECK(belum_jelas BETWEEN 0 AND jumlah),
    kode_b INTEGER NOT NULL CHECK(kode_b BETWEEN 0 AND jumlah),
    kode_k INTEGER NOT NULL CHECK(kode_k BETWEEN 0 AND jumlah),
    kode_h INTEGER NOT NULL CHECK(kode_h BETWEEN 0 AND jumlah),
    kode_e INTEGER NOT NULL CHECK(kode_e BETWEEN 0 AND jumlah),
    kode_n INTEGER NOT NULL CHECK(kode_n BETWEEN 0 AND jumlah),
    kode_t INTEGER NOT NULL CHECK(kode_t BETWEEN 0 AND jumlah),
    PRIMARY KEY(peserta,token),
    FOREIGN KEY(peserta,token) REFERENCES sensor_episode(peserta,token) ON DELETE CASCADE
);
CREATE TABLE sensor_chat (
    peserta TEXT NOT NULL REFERENCES sensor_peserta(generasi) ON DELETE CASCADE,
    token TEXT NOT NULL CHECK(length(token)=64),
    kategori TEXT NOT NULL CHECK(kategori IN ('penjelasan','latihan','hasil','penggunaan','belum_diketahui')),
    jam INTEGER NOT NULL CHECK(jam>=0),
    PRIMARY KEY(peserta,token)
);
CREATE INDEX sensor_episode_retensi ON sensor_episode(mulai);
CREATE INDEX sensor_chat_retensi ON sensor_chat(jam);
"""


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'sensor_*' ORDER BY type,name"))


def validasi(kon):
    aktual = struktur(kon)
    if not aktual:
        return False
    acuan = sqlite3.connect(':memory:')
    try:
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError('struktur sensor tidak lengkap')
    finally:
        acuan.close()
    rows = list(kon.execute('SELECT versi FROM sensor_schema WHERE id=1'))
    if len(rows) != 1 or rows[0][0] != VERSI:
        raise ValueError('versi sensor tidak sah')
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik dan idempoten; tanpa consent atau backfill."""
    import admin_store
    with admin_store._transaksi(path) as kon:
        if not struktur(kon):
            import admin_store_core
            admin_store_core.jalankan_ddl(kon, DDL)
            kon.execute('INSERT INTO sensor_schema VALUES(1,?)', (VERSI,))
        validasi(kon)
        if kon.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('integritas sensor gagal')

"""Skema basis data mesin latihan.

Keputusan bentuk data yang menentukan seluruh sisanya:

**Yang disimpan adalah parameter, bukan teks soal.** Tabel `soal` menyimpan
`template_id` + `parameter` + `kunci`, dan teks soalnya dibangkitkan ulang
saat perlu. Konsekuensinya: soal dengan angka berbeda tetap bisa
dibandingkan lewat `template_id`, dan bank soal tumbuh sendiri tiap
generate tanpa duplikat (dijaga `tanda_tangan` yang UNIQUE).

**Diagnosis dipisah dari jawaban.** Satu jawaban bisa didiagnosis ulang
kalau guru berubah pikiran, tanpa kehilangan jawaban aslinya. Kolom
`kode_usulan` (dari mesin) dan `kode_final` (dari guru) sengaja terpisah —
supaya nanti bisa diukur seberapa sering mesin salah menebak.

**Miskonsepsi dicatat sebagai malrule_id, bukan nomor soal.** Ini yang
membuat "satu miskonsepsi yang muncul di tiga soal" terhitung satu, sesuai
aturan di lembar penilaian.
"""

SKEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Anak. Disimpan inisial/nama panggilan saja, bukan nama lengkap:
-- mengurangi dampak kalau basis data ini bocor.
--
-- `pemilik` = username akun guru/orang tua pemiliknya (multi-keluarga).
-- Kosong berarti warisan era single-family: hanya terlihat oleh admin,
-- dan dibackfill ke username admin saat startup. Nama boleh dobel ANTAR
-- pemilik (UNIQUE komposit), tapi tidak dalam satu keluarga.
CREATE TABLE IF NOT EXISTS siswa (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nama        TEXT    NOT NULL,
    tingkat     TEXT    NOT NULL DEFAULT 'P3',
    pemilik     TEXT    NOT NULL DEFAULT '',
    dibuat      TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours')),
    UNIQUE (nama, pemilik)
);
CREATE INDEX IF NOT EXISTS idx_siswa_pemilik ON siswa(pemilik);

-- Bank soal. Tumbuh tiap generate; tanda_tangan mencegah duplikat.
--
-- `level` ikut masuk tanda_tangan (lihat Soal.tanda_tangan): template dengan
-- parameter sama bisa sah di dua level, dan tanpa level keduanya bertabrakan
-- jadi satu baris.
CREATE TABLE IF NOT EXISTS soal (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tanda_tangan  TEXT    NOT NULL UNIQUE,
    template_id   TEXT    NOT NULL,
    parameter     TEXT    NOT NULL,          -- JSON murni: list tetap list,
                                               -- tanpa bentuk string per-template
                                               -- (kontrak A4; restorasi tanpa cabang)
    kunci         TEXT    NOT NULL,
    bagian        TEXT    NOT NULL DEFAULT '',
    tantangan     INTEGER NOT NULL DEFAULT 0,
    level         TEXT    NOT NULL DEFAULT 'P3',
    -- Kalimat soal versi cerita dari LLM (B2). Kosong = pakai kalimat bawaan.
    --
    -- Disimpan, bukan dihasilkan ulang saat render: kalimatnya sudah dibayar
    -- sekali, dan yang lebih penting — anak mengerjakan kalimat TERTENTU.
    -- Menghasilkan ulang berarti lembar yang dicetak guru bisa berbeda dari
    -- yang dikerjakan anak, dan itu membuat diagnosisnya menilai soal yang salah.
    cerita        TEXT    NOT NULL DEFAULT '',
    dibuat        TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);

CREATE INDEX IF NOT EXISTS idx_soal_template ON soal(template_id);
CREATE INDEX IF NOT EXISTS idx_soal_level ON soal(level);

-- Putaran adalah identitas stabil. Penutupan/perubahan status tidak ditulis
-- di sini, melainkan sebagai kejadian append-only.
CREATE TABLE IF NOT EXISTS putaran_fokus (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id    INTEGER NOT NULL REFERENCES siswa(id) ON DELETE RESTRICT,
    level       TEXT    NOT NULL,
    dibuka      TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);
CREATE INDEX IF NOT EXISTS idx_putaran_siswa
    ON putaran_fokus(siswa_id, dibuka);

-- Malrule per soal: jawaban salah yang bisa diprediksi + kodenya.
-- Disimpan (bukan dihitung saat baca) supaya diagnosis lama tetap terbaca
-- apa adanya kalau definisi malrule di kode berubah kemudian.
CREATE TABLE IF NOT EXISTS malrule (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    soal_id    INTEGER NOT NULL REFERENCES soal(id) ON DELETE CASCADE,
    malrule_id TEXT    NOT NULL,
    jawaban    TEXT    NOT NULL,
    kode       TEXT    NOT NULL CHECK (kode IN ('B','K','H','E','T','N')),
    alasan     TEXT    NOT NULL DEFAULT '',
    UNIQUE (soal_id, malrule_id)
);

-- Satu kali latihan. seed disimpan supaya lembarnya bisa dicetak ulang persis.
--
-- `level` disimpan di sesi, bukan dibaca ulang dari siswa.tingkat saat
-- mencetak: kalau anak naik dari P3 ke P4, lembar sesi lamanya harus tetap
-- tercetak sebagai P3. Membaca tingkat siswa saat render akan diam-diam
-- mengubah sejarah.
CREATE TABLE IF NOT EXISTS sesi (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id  INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    seed      INTEGER NOT NULL,
    topik     TEXT    NOT NULL DEFAULT 'pola-bilangan',
    level     TEXT    NOT NULL DEFAULT 'P3',
    mode      TEXT    NOT NULL DEFAULT 'diagnostik',
    timer_mode    TEXT    NOT NULL DEFAULT 'tanpa',
    durasi_menit  INTEGER NOT NULL DEFAULT 15,
    timer_auto    INTEGER NOT NULL DEFAULT 0,
    tanggal   TEXT    NOT NULL DEFAULT (date('now', '+7 hours')),
    mulai     TEXT,
    selesai   TEXT,
    -- diisi saat guru membuka halaman sesi yang sudah terisi penuh — penanda "guru sudah melihat hasilnya"
    direview  TEXT,
    jenis     TEXT    NOT NULL DEFAULT 'biasa'
        CHECK (jenis IN ('biasa', 'remedial')),
    -- Sesi hasil latihan ulang boleh menunjuk sesi yang menjadi sumbernya.
    -- Jika sumber dihapus, sesi remedial tetap dipertahankan sebagai riwayat.
    sumber_sesi_id INTEGER REFERENCES sesi(id) ON DELETE SET NULL,
    -- Metadata orkestrator. Sesi lama/manual aman sebagai `bebas`; NULL berarti
    -- tidak ada pengesahan, putaran, bagian checkpoint, atau pembatalan.
    tujuan    TEXT NOT NULL DEFAULT 'bebas'
        CHECK (tujuan IN ('bebas', 'pemetaan', 'latihan_terbimbing',
                          'penguatan', 'evaluasi', 'checkpoint', 'pengenalan',
                          'maintenance')),
    dikonfirmasi_guru TEXT,
    fingerprint_konfirmasi TEXT,
    putaran_id INTEGER REFERENCES putaran_fokus(id) ON DELETE RESTRICT,
    bagian_checkpoint INTEGER
        CHECK (bagian_checkpoint IS NULL OR bagian_checkpoint IN (1, 2)),
    -- Begitu lembar cetak dirender, snapshot penyajian menjadi sejarah.
    -- Timestamp terpisah agar cetak tidak berpura-pura sebagai mulai/selesai anak.
    penyajian_dibekukan TEXT,
    -- Kunci occurrence aktif; NULL untuk sesi manual/warisan. Indeks parsial
    -- di bawah membedakan double-submit dari retry setelah pembatalan.
    kunci_idempotensi TEXT,
    -- Idempotensi tindakan manual dari Pendamping terpisah dari occurrence
    -- siklus. Sesi ini tetap tujuan `bebas`, tanpa putaran atau bukti.
    kunci_pendamping TEXT,
    dibatalkan TEXT,
    catatan   TEXT    NOT NULL DEFAULT '',
    dibuat    TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);

CREATE INDEX IF NOT EXISTS idx_sesi_siswa ON sesi(siswa_id, tanggal);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sesi_siklus_aktif
    ON sesi(kunci_idempotensi)
    WHERE kunci_idempotensi IS NOT NULL AND dibatalkan IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sesi_pendamping_aktif
    ON sesi(kunci_pendamping)
    WHERE kunci_pendamping IS NOT NULL AND dibatalkan IS NULL;

-- Bukti eksekusi Pendamping bertahan setelah sesi/chat dihapus. Kunci opaque
-- mengikat generasi akun + usulan, tanpa teks chat, nama, atau jawaban anak.
-- sesi_id sengaja BUKAN FK: penghapusan sesi tidak membuka eksekusi kedua.
CREATE TABLE IF NOT EXISTS eksekusi_pendamping (
    kunci TEXT PRIMARY KEY CHECK (length(kunci) = 64),
    sesi_id INTEGER NOT NULL UNIQUE,
    token_hash TEXT NOT NULL CHECK (length(token_hash) = 64),
    ikatan_hash TEXT NOT NULL CHECK (length(ikatan_hash) = 64)
);

-- CHECK pada CREATE TABLE tidak ditambahkan ke tabel warisan oleh ALTER COLUMN.
-- Trigger ini memberi aturan identik untuk pemasangan baru dan hasil migrasi.
CREATE TRIGGER IF NOT EXISTS sesi_validasi_insert
BEFORE INSERT ON sesi
WHEN NEW.tujuan NOT IN (
        'bebas', 'pemetaan', 'latihan_terbimbing', 'penguatan',
 'evaluasi', 'checkpoint', 'pengenalan', 'maintenance'
     )
  OR NEW.bagian_checkpoint IS NOT NULL
     AND NEW.bagian_checkpoint NOT IN (1, 2)
BEGIN
    SELECT RAISE(ABORT, 'metadata sesi tidak valid');
END;
CREATE TRIGGER IF NOT EXISTS sesi_validasi_update
BEFORE UPDATE OF tujuan, bagian_checkpoint ON sesi
WHEN NEW.tujuan NOT IN (
        'bebas', 'pemetaan', 'latihan_terbimbing', 'penguatan',
 'evaluasi', 'checkpoint', 'pengenalan', 'maintenance'
     )
  OR NEW.bagian_checkpoint IS NOT NULL
     AND NEW.bagian_checkpoint NOT IN (1, 2)
BEGIN
    SELECT RAISE(ABORT, 'metadata sesi tidak valid');
END;

-- Tautan bearer untuk satu sesi. Token mentah tidak disimpan: hanya hash
-- SHA-256, supaya salinan basis data tidak langsung menjadi kunci masuk.
-- Satu sesi hanya punya satu tautan; buat ulang mengganti tautan sebelumnya.
CREATE TABLE IF NOT EXISTS tautan_sesi (
    sesi_id      INTEGER PRIMARY KEY REFERENCES sesi(id) ON DELETE CASCADE,
    token_hash   TEXT    NOT NULL UNIQUE,
    dibuat       INTEGER NOT NULL,
    kedaluarsa   INTEGER NOT NULL,
    dicabut      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tautan_sesi_hash ON tautan_sesi(token_hash);

-- Urutan soal dalam satu sesi.
CREATE TABLE IF NOT EXISTS sesi_soal (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    sesi_id                  INTEGER NOT NULL REFERENCES sesi(id) ON DELETE CASCADE,
    soal_id                  INTEGER NOT NULL REFERENCES soal(id),
    nomor                    INTEGER NOT NULL,
    teks_soal                TEXT,
    bagian_soal              TEXT,
    tantangan_soal           INTEGER,
    minta_restatement        INTEGER,
    penyajian_json           TEXT,
    penyajian_versi          INTEGER,
    renderer_versi           INTEGER,
    asal_teks                TEXT,
    status_visual            TEXT,
    mode_representasi        TEXT,
    fingerprint_matematis    TEXT,
    fingerprint_penyajian    TEXT,
    UNIQUE (sesi_id, nomor),
    CHECK (
        (
            teks_soal IS NULL AND bagian_soal IS NULL
            AND tantangan_soal IS NULL AND minta_restatement IS NULL
            AND penyajian_json IS NULL AND penyajian_versi IS NULL
            AND renderer_versi IS NULL AND asal_teks IS NULL
            AND status_visual IS NULL AND mode_representasi IS NULL
            AND fingerprint_matematis IS NULL
            AND fingerprint_penyajian IS NULL
        )
        OR
        (
            teks_soal IS NOT NULL AND bagian_soal IS NOT NULL
            AND tantangan_soal IS NOT NULL
            AND minta_restatement IS NOT NULL
            AND penyajian_json IS NOT NULL
            AND penyajian_versi IS NOT NULL
            AND renderer_versi IS NOT NULL
            AND asal_teks IS NOT NULL AND status_visual IS NOT NULL
            AND mode_representasi IS NOT NULL
            AND fingerprint_matematis IS NOT NULL
            AND fingerprint_penyajian IS NOT NULL
            AND typeof(teks_soal) = 'text'
            AND typeof(bagian_soal) = 'text'
            AND typeof(tantangan_soal) = 'integer'
            AND typeof(minta_restatement) = 'integer'
            AND typeof(penyajian_json) = 'text'
            AND typeof(penyajian_versi) = 'integer'
            AND typeof(renderer_versi) = 'integer'
            AND typeof(asal_teks) = 'text'
            AND typeof(status_visual) = 'text'
            AND typeof(mode_representasi) = 'text'
            AND typeof(fingerprint_matematis) = 'text'
            AND typeof(fingerprint_penyajian) = 'text'
            AND tantangan_soal IN (0, 1)
            AND minta_restatement IN (0, 1)
            AND penyajian_versi > 0 AND renderer_versi > 0
            AND asal_teks IN ('warisan', 'bawaan', 'cerita')
            AND status_visual IN (
                'tanpa_visual', 'siap', 'warisan', 'tidak_valid'
            )
            AND LENGTH(TRIM(mode_representasi)) > 0
            AND LENGTH(TRIM(fingerprint_matematis)) > 0
            AND LENGTH(TRIM(fingerprint_penyajian)) > 0
        )
    )
);

-- ALTER TABLE hanya menambah kolom pada database warisan, bukan CHECK tabel.
-- Trigger menjaga kontrak all-or-none yang sama untuk pemasangan lama dan baru.
CREATE TRIGGER IF NOT EXISTS sesi_soal_snapshot_validasi_insert
BEFORE INSERT ON sesi_soal
WHEN NOT (
    (
        NEW.teks_soal IS NULL AND NEW.bagian_soal IS NULL
        AND NEW.tantangan_soal IS NULL AND NEW.minta_restatement IS NULL
        AND NEW.penyajian_json IS NULL AND NEW.penyajian_versi IS NULL
        AND NEW.renderer_versi IS NULL AND NEW.asal_teks IS NULL
        AND NEW.status_visual IS NULL AND NEW.mode_representasi IS NULL
        AND NEW.fingerprint_matematis IS NULL
        AND NEW.fingerprint_penyajian IS NULL
    )
    OR
    (
        NEW.teks_soal IS NOT NULL AND NEW.bagian_soal IS NOT NULL
        AND NEW.tantangan_soal IS NOT NULL
        AND NEW.minta_restatement IS NOT NULL
        AND NEW.penyajian_json IS NOT NULL
        AND NEW.penyajian_versi IS NOT NULL
        AND NEW.renderer_versi IS NOT NULL
        AND NEW.asal_teks IS NOT NULL AND NEW.status_visual IS NOT NULL
        AND NEW.mode_representasi IS NOT NULL
        AND NEW.fingerprint_matematis IS NOT NULL
        AND NEW.fingerprint_penyajian IS NOT NULL
        AND typeof(NEW.teks_soal) = 'text'
        AND typeof(NEW.bagian_soal) = 'text'
        AND typeof(NEW.tantangan_soal) = 'integer'
        AND typeof(NEW.minta_restatement) = 'integer'
        AND typeof(NEW.penyajian_json) = 'text'
        AND typeof(NEW.penyajian_versi) = 'integer'
        AND typeof(NEW.renderer_versi) = 'integer'
        AND typeof(NEW.asal_teks) = 'text'
        AND typeof(NEW.status_visual) = 'text'
        AND typeof(NEW.mode_representasi) = 'text'
        AND typeof(NEW.fingerprint_matematis) = 'text'
        AND typeof(NEW.fingerprint_penyajian) = 'text'
        AND NEW.tantangan_soal IN (0, 1)
        AND NEW.minta_restatement IN (0, 1)
        AND NEW.penyajian_versi > 0 AND NEW.renderer_versi > 0
        AND NEW.asal_teks IN ('warisan', 'bawaan', 'cerita')
        AND NEW.status_visual IN (
            'tanpa_visual', 'siap', 'warisan', 'tidak_valid'
        )
        AND LENGTH(TRIM(NEW.mode_representasi)) > 0
        AND LENGTH(TRIM(NEW.fingerprint_matematis)) > 0
        AND LENGTH(TRIM(NEW.fingerprint_penyajian)) > 0
    )
)
BEGIN
    SELECT RAISE(ABORT, 'snapshot penyajian sesi_soal tidak valid');
END;

CREATE TRIGGER IF NOT EXISTS sesi_soal_snapshot_validasi_update
BEFORE UPDATE ON sesi_soal
WHEN NOT (
    (
        NEW.teks_soal IS NULL AND NEW.bagian_soal IS NULL
        AND NEW.tantangan_soal IS NULL AND NEW.minta_restatement IS NULL
        AND NEW.penyajian_json IS NULL AND NEW.penyajian_versi IS NULL
        AND NEW.renderer_versi IS NULL AND NEW.asal_teks IS NULL
        AND NEW.status_visual IS NULL AND NEW.mode_representasi IS NULL
        AND NEW.fingerprint_matematis IS NULL
        AND NEW.fingerprint_penyajian IS NULL
    )
    OR
    (
        NEW.teks_soal IS NOT NULL AND NEW.bagian_soal IS NOT NULL
        AND NEW.tantangan_soal IS NOT NULL
        AND NEW.minta_restatement IS NOT NULL
        AND NEW.penyajian_json IS NOT NULL
        AND NEW.penyajian_versi IS NOT NULL
        AND NEW.renderer_versi IS NOT NULL
        AND NEW.asal_teks IS NOT NULL AND NEW.status_visual IS NOT NULL
        AND NEW.mode_representasi IS NOT NULL
        AND NEW.fingerprint_matematis IS NOT NULL
        AND NEW.fingerprint_penyajian IS NOT NULL
        AND typeof(NEW.teks_soal) = 'text'
        AND typeof(NEW.bagian_soal) = 'text'
        AND typeof(NEW.tantangan_soal) = 'integer'
        AND typeof(NEW.minta_restatement) = 'integer'
        AND typeof(NEW.penyajian_json) = 'text'
        AND typeof(NEW.penyajian_versi) = 'integer'
        AND typeof(NEW.renderer_versi) = 'integer'
        AND typeof(NEW.asal_teks) = 'text'
        AND typeof(NEW.status_visual) = 'text'
        AND typeof(NEW.mode_representasi) = 'text'
        AND typeof(NEW.fingerprint_matematis) = 'text'
        AND typeof(NEW.fingerprint_penyajian) = 'text'
        AND NEW.tantangan_soal IN (0, 1)
        AND NEW.minta_restatement IN (0, 1)
        AND NEW.penyajian_versi > 0 AND NEW.renderer_versi > 0
        AND NEW.asal_teks IN ('warisan', 'bawaan', 'cerita')
        AND NEW.status_visual IN (
            'tanpa_visual', 'siap', 'warisan', 'tidak_valid'
        )
        AND LENGTH(TRIM(NEW.mode_representasi)) > 0
        AND LENGTH(TRIM(NEW.fingerprint_matematis)) > 0
        AND LENGTH(TRIM(NEW.fingerprint_penyajian)) > 0
    )
)
BEGIN
    SELECT RAISE(ABORT, 'snapshot penyajian sesi_soal tidak valid');
END;

-- Pertahanan berlapis untuk UPDATE raw SQL: snapshot pengalaman anak hanya
-- boleh berubah sebelum sesi dikerjakan atau dipakai sebagai bukti. Pembatasan
-- `UPDATE OF` membuat perubahan kolom sesi_soal lain tidak ikut tertolak.
CREATE TRIGGER IF NOT EXISTS sesi_soal_snapshot_tolak_update_terkunci
BEFORE UPDATE OF
    sesi_id, soal_id, nomor, teks_soal, bagian_soal, tantangan_soal, minta_restatement,
    penyajian_json, penyajian_versi, renderer_versi, asal_teks,
    status_visual, mode_representasi, fingerprint_matematis,
    fingerprint_penyajian
ON sesi_soal
WHEN EXISTS (
        SELECT 1 FROM sesi se
        WHERE se.id IN (OLD.sesi_id, NEW.sesi_id)
          AND (
              se.mulai IS NOT NULL OR se.selesai IS NOT NULL
              OR se.penyajian_dibekukan IS NOT NULL OR se.dibatalkan IS NOT NULL
          )
     )
  OR EXISTS (
        SELECT 1 FROM jawaban j
        JOIN sesi_soal lain ON lain.id = j.sesi_soal_id
        WHERE lain.sesi_id IN (OLD.sesi_id, NEW.sesi_id)
     )
  OR EXISTS (
        SELECT 1 FROM konfirmasi_hasil kh WHERE kh.sesi_id IN (OLD.sesi_id, NEW.sesi_id)
     )
  OR EXISTS (
        SELECT 1 FROM bukti_fokus bf WHERE bf.sesi_id IN (OLD.sesi_id, NEW.sesi_id)
     )
BEGIN
    SELECT RAISE(ABORT, 'snapshot penyajian terkunci');
END;

-- Jawaban anak. Empat kotak dari format lembar diagnostik:
--   restatement    -> "soal ini mintanya apa?"  (memisahkan B)
--   cara           -> kotak "Caraku"            (memisahkan K dari H)
--   jawaban        -> jawaban akhir             (memisahkan E)
--   belum_pernah   -> centang "belum pernah lihat" (memisahkan T dari N)
CREATE TABLE IF NOT EXISTS jawaban (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sesi_soal_id  INTEGER NOT NULL UNIQUE REFERENCES sesi_soal(id) ON DELETE CASCADE,
    restatement   TEXT    NOT NULL DEFAULT '',
    cara          TEXT    NOT NULL DEFAULT '',
    jawaban       TEXT    NOT NULL DEFAULT '',
    belum_pernah  INTEGER NOT NULL DEFAULT 0,
    detik         INTEGER,
    dicatat       TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);

-- Diagnosis. kode_usulan dari mesin, kode_final dari guru.
-- Dipisah supaya akurasi mesin bisa diukur belakangan.
CREATE TABLE IF NOT EXISTS diagnosis (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    jawaban_id    INTEGER NOT NULL UNIQUE REFERENCES jawaban(id) ON DELETE CASCADE,
    benar         INTEGER NOT NULL DEFAULT 0,
    kode_usulan   TEXT    CHECK (kode_usulan IS NULL OR kode_usulan IN ('B','K','H','E','T','N')),
    kode_final    TEXT    CHECK (kode_final  IS NULL OR kode_final  IN ('B','K','H','E','T','N')),
    malrule_id    TEXT,
    alasan        TEXT    NOT NULL DEFAULT '',
    manual        INTEGER NOT NULL DEFAULT 0,   -- guru mengubah usulan mesin
    catatan       TEXT    NOT NULL DEFAULT '',
    didiagnosis   TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);

-- Lampiran foto lembar (Fase 2): foto hasil kerja anak di kertas,
-- dianalisa AI vision, lalu dikonfirmasi guru sebelum masuk laporan.
CREATE TABLE IF NOT EXISTS lampiran (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sesi_id     INTEGER NOT NULL REFERENCES sesi(id) ON DELETE CASCADE,
    nama_berkas TEXT    NOT NULL,
    mime        TEXT    NOT NULL DEFAULT 'image/jpeg',
    hasil_json  TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'baru'
        CHECK (status IN ('baru', 'diterapkan')),
    dibuat      TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);
CREATE INDEX IF NOT EXISTS idx_lampiran_sesi ON lampiran(sesi_id);

-- Maksimal dua anggota ditegakkan lewat slot 1/2 yang unik. Kunci kanonis
-- memakai malrule kosong sebagai representasi SQL untuk nilai domain NULL,
-- karena UNIQUE SQLite memperbolehkan banyak NULL.
CREATE TABLE IF NOT EXISTS anggota_fokus (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    putaran_id         INTEGER NOT NULL REFERENCES putaran_fokus(id) ON DELETE RESTRICT,
    slot               INTEGER NOT NULL CHECK (slot IN (1, 2)),
    template_id        TEXT    NOT NULL,
    kode_intervensi    TEXT    NOT NULL CHECK (kode_intervensi IN ('B','K','H','E','T','N')),
    malrule_id_kanonis TEXT    NOT NULL DEFAULT '',
    dibuat             TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours')),
    UNIQUE (putaran_id, slot),
    UNIQUE (putaran_id, template_id, kode_intervensi, malrule_id_kanonis)
);

CREATE TABLE IF NOT EXISTS bukti_fokus (
    anggota_fokus_id INTEGER NOT NULL REFERENCES anggota_fokus(id) ON DELETE RESTRICT,
    sesi_id          INTEGER NOT NULL REFERENCES sesi(id) ON DELETE RESTRICT,
    PRIMARY KEY (anggota_fokus_id, sesi_id)
);

-- Satu pengesahan immutable per versi hasil. `nomor_urut` monoton per sesi;
-- pasangan unik mencegah nomor yang sama dipakai ulang.
CREATE TABLE IF NOT EXISTS konfirmasi_hasil (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sesi_id     INTEGER NOT NULL REFERENCES sesi(id) ON DELETE RESTRICT,
    nomor_urut  INTEGER NOT NULL CHECK (nomor_urut > 0),
    guru        TEXT    NOT NULL,
    fingerprint TEXT    NOT NULL,
    dibuat      TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours')),
    UNIQUE (sesi_id, nomor_urut)
);

-- Salinan outcome kanonis seluruh butir. Tidak ada FK ke diagnosis/jawaban agar
-- koreksi data aktif tidak mengubah bukti historis.
CREATE TABLE IF NOT EXISTS snapshot_outcome (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    konfirmasi_id    INTEGER NOT NULL REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
    -- Snapshot menyimpan identitas/nomor outcome sebagai nilai immutable;
    -- tidak merujuk sesi_soal agar sesi berbukti dapat dijaga oleh FK sesi
    -- tanpa bergantung pada anak tabel yang punya cascade existing.
    sesi_soal_id     INTEGER NOT NULL,
    nomor            INTEGER NOT NULL,
    template_id      TEXT    NOT NULL,
    jawaban          TEXT    NOT NULL DEFAULT '',
    benar            INTEGER,
    kode_final       TEXT CHECK (kode_final IS NULL OR kode_final IN ('B','K','H','E','T','N')),
    malrule_id       TEXT,
    dilewati         INTEGER NOT NULL DEFAULT 0 CHECK (dilewati IN (0, 1)),
    level_efektif    TEXT    NOT NULL,
    cek_pemahaman    TEXT CHECK (
        cek_pemahaman IS NULL OR
        cek_pemahaman IN ('bisa_menjelaskan', 'ragu', 'menghafal')
    ),
    target_template_id TEXT,
    target_kode_intervensi TEXT CHECK (
        target_kode_intervensi IS NULL OR
        target_kode_intervensi IN ('B','K','H','E','T','N')
    ),
    target_malrule_id TEXT,
    CHECK (
        (dilewati = 1 AND benar IS NULL AND kode_final IS NULL AND malrule_id IS NULL)
        OR
        (dilewati = 0 AND (
            (benar = 0 AND kode_final IS NOT NULL)
            OR
            (benar = 1 AND kode_final IS NULL AND malrule_id IS NULL)
        ))
    ),
    UNIQUE (konfirmasi_id, sesi_soal_id),
    UNIQUE (konfirmasi_id, nomor)
);

-- CHECK tabel melindungi pemasangan baru; trigger yang sama juga ditempelkan
-- pada tabel snapshot warisan yang sudah telanjur dibuat tanpa CHECK ini.
CREATE TRIGGER IF NOT EXISTS snapshot_outcome_validasi_insert
BEFORE INSERT ON snapshot_outcome
WHEN (NEW.dilewati = 1 AND (
          NEW.benar IS NOT NULL OR NEW.kode_final IS NOT NULL
          OR NEW.malrule_id IS NOT NULL
      ))
  OR (NEW.dilewati = 0 AND (
          NEW.benar IS NULL OR NEW.benar NOT IN (0, 1)
          OR (NEW.benar = 0 AND NEW.kode_final IS NULL)
          OR (NEW.benar = 1 AND (
              NEW.kode_final IS NOT NULL OR NEW.malrule_id IS NOT NULL
          ))
      ))
BEGIN
    SELECT RAISE(ABORT, 'outcome snapshot tidak valid');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_outcome_target_validasi_insert
BEFORE INSERT ON snapshot_outcome
WHEN NEW.target_kode_intervensi IS NOT NULL
 AND NEW.target_kode_intervensi NOT IN ('B','K','H','E','T','N')
BEGIN
    SELECT RAISE(ABORT, 'target fokus snapshot tidak valid');
END;

-- Provenance penyajian terpisah: tidak mengubah fingerprint outcome historis.
CREATE TABLE IF NOT EXISTS penyajian_outcome (
    snapshot_outcome_id INTEGER PRIMARY KEY
        REFERENCES snapshot_outcome(id) ON DELETE RESTRICT,
    mode_representasi TEXT NOT NULL CHECK (
        typeof(mode_representasi) = 'text' AND LENGTH(TRIM(mode_representasi)) > 0
    ),
    fingerprint_penyajian TEXT CHECK (
        fingerprint_penyajian IS NULL OR (
            typeof(fingerprint_penyajian) = 'text'
            AND LENGTH(fingerprint_penyajian) = 64
            AND fingerprint_penyajian NOT GLOB '*[^0-9a-f]*'
        )
    )
);
CREATE TRIGGER IF NOT EXISTS penyajian_outcome_validasi_insert
BEFORE INSERT ON penyajian_outcome
WHEN NOT EXISTS (
    SELECT 1 FROM snapshot_outcome so
    JOIN konfirmasi_hasil kh ON kh.id = so.konfirmasi_id
    JOIN sesi_soal ss ON ss.id = so.sesi_soal_id
        AND ss.sesi_id = kh.sesi_id AND ss.nomor = so.nomor
    JOIN soal s ON s.id = ss.soal_id AND s.template_id = so.template_id
    WHERE so.id = NEW.snapshot_outcome_id
      AND osn_provenance_outcome_sah(
          NEW.mode_representasi, NEW.fingerprint_penyajian,
          ss.teks_soal, ss.bagian_soal, ss.tantangan_soal, ss.minta_restatement,
          ss.penyajian_json, ss.penyajian_versi, ss.renderer_versi, ss.asal_teks,
          ss.status_visual, ss.mode_representasi, ss.fingerprint_matematis,
          ss.fingerprint_penyajian, s.template_id, s.parameter, s.level, s.cerita
      ) = 1
)
BEGIN
    SELECT RAISE(ABORT, 'provenance penyajian outcome tidak valid');
END;
CREATE TRIGGER IF NOT EXISTS penyajian_outcome_tolak_replace
BEFORE INSERT ON penyajian_outcome
WHEN EXISTS (SELECT 1 FROM penyajian_outcome
             WHERE snapshot_outcome_id = NEW.snapshot_outcome_id)
BEGIN
    SELECT RAISE(ABORT, 'penyajian_outcome append-only');
END;
CREATE TRIGGER IF NOT EXISTS penyajian_outcome_tolak_update
BEFORE UPDATE ON penyajian_outcome BEGIN
    SELECT RAISE(ABORT, 'penyajian_outcome append-only');
END;
CREATE TRIGGER IF NOT EXISTS penyajian_outcome_tolak_delete
BEFORE DELETE ON penyajian_outcome BEGIN
    SELECT RAISE(ABORT, 'penyajian_outcome append-only');
END;

-- Kejadian domain append-only. `data` adalah JSON kanonis untuk payload yang
-- berbeda per jenis; FK opsional menjaga provenance sesi/putaran/konfirmasi.
CREATE TABLE IF NOT EXISTS kejadian_belajar (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id        INTEGER NOT NULL REFERENCES siswa(id) ON DELETE RESTRICT,
    putaran_id      INTEGER REFERENCES putaran_fokus(id) ON DELETE RESTRICT,
    sesi_id         INTEGER REFERENCES sesi(id) ON DELETE RESTRICT,
    konfirmasi_id   INTEGER REFERENCES konfirmasi_hasil(id) ON DELETE RESTRICT,
    jenis           TEXT    NOT NULL,
    data            TEXT    NOT NULL DEFAULT '{}',
    dibuat          TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours'))
);
CREATE INDEX IF NOT EXISTS idx_kejadian_siswa
    ON kejadian_belajar(siswa_id, id);

-- Empat tabel riwayat tidak boleh diperbarui atau dihapus. Koreksi selalu
-- menambah kejadian/snapshot versi baru.
CREATE TRIGGER IF NOT EXISTS putaran_fokus_tolak_update
BEFORE UPDATE ON putaran_fokus BEGIN
    SELECT RAISE(ABORT, 'putaran_fokus append-only');
END;
CREATE TRIGGER IF NOT EXISTS putaran_fokus_tolak_delete
BEFORE DELETE ON putaran_fokus BEGIN
    SELECT RAISE(ABORT, 'putaran_fokus append-only');
END;
CREATE TRIGGER IF NOT EXISTS konfirmasi_hasil_tolak_update
BEFORE UPDATE ON konfirmasi_hasil BEGIN
    SELECT RAISE(ABORT, 'konfirmasi_hasil append-only');
END;
CREATE TRIGGER IF NOT EXISTS konfirmasi_hasil_tolak_delete
BEFORE DELETE ON konfirmasi_hasil BEGIN
    SELECT RAISE(ABORT, 'konfirmasi_hasil append-only');
END;
CREATE TRIGGER IF NOT EXISTS snapshot_outcome_tolak_update
BEFORE UPDATE ON snapshot_outcome BEGIN
    SELECT RAISE(ABORT, 'snapshot_outcome append-only');
END;
CREATE TRIGGER IF NOT EXISTS snapshot_outcome_tolak_delete
BEFORE DELETE ON snapshot_outcome BEGIN
    SELECT RAISE(ABORT, 'snapshot_outcome append-only');
END;
CREATE TRIGGER IF NOT EXISTS kejadian_belajar_tolak_update
BEFORE UPDATE ON kejadian_belajar BEGIN
    SELECT RAISE(ABORT, 'kejadian_belajar append-only');
END;
CREATE TRIGGER IF NOT EXISTS kejadian_belajar_tolak_delete
BEFORE DELETE ON kejadian_belajar BEGIN
    SELECT RAISE(ABORT, 'kejadian_belajar append-only');
END;
CREATE TRIGGER IF NOT EXISTS anggota_fokus_tolak_update
BEFORE UPDATE ON anggota_fokus BEGIN
    SELECT RAISE(ABORT, 'anggota_fokus append-only');
END;
CREATE TRIGGER IF NOT EXISTS anggota_fokus_tolak_delete
BEFORE DELETE ON anggota_fokus BEGIN
    SELECT RAISE(ABORT, 'anggota_fokus append-only');
END;
CREATE TRIGGER IF NOT EXISTS bukti_fokus_tolak_update
BEFORE UPDATE ON bukti_fokus BEGIN
    SELECT RAISE(ABORT, 'bukti_fokus append-only');
END;
CREATE TRIGGER IF NOT EXISTS bukti_fokus_tolak_delete
BEFORE DELETE ON bukti_fokus BEGIN
    SELECT RAISE(ABORT, 'bukti_fokus append-only');
END;

-- Ringkasan per sesi supaya laporan tidak perlu menghitung ulang tiap buka.
CREATE VIEW IF NOT EXISTS ringkasan_sesi AS
SELECT
    s.id                                              AS sesi_id,
    s.siswa_id,
    w.nama                                            AS siswa,
    s.tanggal,
    s.seed,
    s.level,
    s.topik,
    COUNT(ss.id)                                      AS jumlah_soal,
    SUM(COALESCE(d.benar, 0))                         AS benar,
    SUM(CASE WHEN d.kode_final = 'K' THEN 1 ELSE 0 END) AS k,
    SUM(CASE WHEN d.kode_final = 'B' THEN 1 ELSE 0 END) AS b,
    SUM(CASE WHEN d.kode_final = 'H' THEN 1 ELSE 0 END) AS h,
    SUM(CASE WHEN d.kode_final = 'E' THEN 1 ELSE 0 END) AS e,
    SUM(CASE WHEN d.kode_final = 'T' THEN 1 ELSE 0 END) AS t,
    SUM(CASE WHEN d.kode_final = 'N' THEN 1 ELSE 0 END) AS n
FROM sesi s
JOIN siswa w        ON w.id = s.siswa_id
LEFT JOIN sesi_soal ss ON ss.sesi_id = s.id
LEFT JOIN jawaban j    ON j.sesi_soal_id = ss.id
LEFT JOIN diagnosis d  ON d.jawaban_id = j.id
GROUP BY s.id;
"""

# Tabel baru additive: sesi warisan tidak diberi arsip pengiriman palsu.
from submission_schema import SKEMA_PENGIRIMAN

SKEMA = SKEMA.replace('-- Ringkasan per sesi supaya laporan', SKEMA_PENGIRIMAN + '\n-- Ringkasan per sesi supaya laporan')

# Migrasi untuk basis data yang SUDAH berisi data.
#
# `CREATE TABLE IF NOT EXISTS` di atas tidak menyentuh tabel yang sudah ada —
# ia diam saja. Jadi menambah kolom pada pemasangan yang sudah jalan (VPS
# sudah berisi sesi anak) butuh ALTER eksplisit, dan tanpa ini kolom `level`
# hanya lahir di basis data baru. Kegagalannya senyap dan hanya muncul saat
# deploy: kueri menyebut kolom yang tidak ada.
#
# Tiap langkah harus aman dijalankan berulang. SQLite tidak punya
# "ADD COLUMN IF NOT EXISTS", jadi kolom yang ada diperiksa dulu lewat
# PRAGMA table_info dan langkah yang tidak perlu dilewati.
#
# View sengaja di-DROP lalu dibiarkan dibuat ulang oleh SKEMA: definisinya
# ikut berubah (kolom `level` masuk ringkasan), dan CREATE VIEW IF NOT EXISTS
# tidak memperbarui view lama.
MIGRASI: list[tuple[str, str, str]] = [
    # (tabel, kolom, pernyataan ALTER)
    ("soal", "level", "ALTER TABLE soal ADD COLUMN level TEXT NOT NULL DEFAULT 'P3'"),
    ("sesi", "level", "ALTER TABLE sesi ADD COLUMN level TEXT NOT NULL DEFAULT 'P3'"),
    ("soal", "cerita", "ALTER TABLE soal ADD COLUMN cerita TEXT NOT NULL DEFAULT ''"),
    # Mode sesi (29 Aug 2026): 'diagnostik' (default) | 'drill' (Latihan Cepat).
    ("sesi", "mode", "ALTER TABLE sesi ADD COLUMN mode TEXT NOT NULL DEFAULT 'diagnostik'"),
    # Timer untuk Latihan Cepat: 'tanpa'|'sesi'|'soal', durasi menit (default
    # 15), timer_auto 0 = peringatan saja / 1 = auto-submit & kunci.
    ("sesi", "timer_mode", "ALTER TABLE sesi ADD COLUMN timer_mode TEXT NOT NULL DEFAULT 'tanpa'"),
    ("sesi", "durasi_menit", "ALTER TABLE sesi ADD COLUMN durasi_menit INTEGER NOT NULL DEFAULT 15"),
    ("sesi", "timer_auto", "ALTER TABLE sesi ADD COLUMN timer_auto INTEGER NOT NULL DEFAULT 0"),
    # Kepemilikan keluarga (30 Agu 2026): username akun guru pemilik anak.
    # ALTER ini hanya menambah kolom; kendala UNIQUE(nama) lama masih menempel
    # di definisi tabel — database.rebuild_siswa_unik yang menggantinya jadi
    # UNIQUE(nama, pemilik) lewat rebuild tabel.
    ("siswa", "pemilik", "ALTER TABLE siswa ADD COLUMN pemilik TEXT NOT NULL DEFAULT ''"),
    # Penanda guru sudah melihat hasil sesi — pelengkap `selesai` untuk
    # badge status di daftar sesi anak (student_pages.halaman_daftar_sesi_baru).
    ("sesi", "direview", "ALTER TABLE sesi ADD COLUMN direview TEXT"),
    # Metadata latihan ulang. SQLite mengizinkan REFERENCES pada ADD COLUMN
    # selama nilai bawaan NULL; SET NULL menjaga sesi remedial saat sumber dihapus.
    ("sesi", "jenis", "ALTER TABLE sesi ADD COLUMN jenis TEXT NOT NULL DEFAULT 'biasa'"),
    ("sesi", "sumber_sesi_id", "ALTER TABLE sesi ADD COLUMN sumber_sesi_id INTEGER REFERENCES sesi(id) ON DELETE SET NULL"),
    # Siklus belajar terpandu (6 Sep 2026). Semua sesi warisan tetap manual;
    # tidak ada backfill keputusan pedagogis dari `direview`/`kode_final`.
    ("sesi", "tujuan", "ALTER TABLE sesi ADD COLUMN tujuan TEXT NOT NULL DEFAULT 'bebas'"),
    ("sesi", "dikonfirmasi_guru", "ALTER TABLE sesi ADD COLUMN dikonfirmasi_guru TEXT"),
    ("sesi", "fingerprint_konfirmasi", "ALTER TABLE sesi ADD COLUMN fingerprint_konfirmasi TEXT"),
    ("sesi", "putaran_id", "ALTER TABLE sesi ADD COLUMN putaran_id INTEGER REFERENCES putaran_fokus(id) ON DELETE RESTRICT"),
    ("sesi", "bagian_checkpoint", "ALTER TABLE sesi ADD COLUMN bagian_checkpoint INTEGER"),
    # Pembekuan eksplisit saat lembar dicetak; nullable untuk semua sesi warisan.
    ("sesi", "penyajian_dibekukan", "ALTER TABLE sesi ADD COLUMN penyajian_dibekukan TEXT"),
    ("sesi", "kunci_idempotensi", "ALTER TABLE sesi ADD COLUMN kunci_idempotensi TEXT"),
    ("sesi", "kunci_pendamping", "ALTER TABLE sesi ADD COLUMN kunci_pendamping TEXT"),
    ("sesi", "dibatalkan", "ALTER TABLE sesi ADD COLUMN dibatalkan TEXT"),
    ("snapshot_outcome", "target_template_id", "ALTER TABLE snapshot_outcome ADD COLUMN target_template_id TEXT"),
    ("snapshot_outcome", "target_kode_intervensi", "ALTER TABLE snapshot_outcome ADD COLUMN target_kode_intervensi TEXT"),
    ("snapshot_outcome", "target_malrule_id", "ALTER TABLE snapshot_outcome ADD COLUMN target_malrule_id TEXT"),
    # Snapshot penyajian per butir (Fase 1 Slice 2). Nullable menjaga baris
    # warisan; trigger SKEMA menegakkan all-or-none setelah migrasi.
    ("sesi_soal", "teks_soal", "ALTER TABLE sesi_soal ADD COLUMN teks_soal TEXT"),
    ("sesi_soal", "bagian_soal", "ALTER TABLE sesi_soal ADD COLUMN bagian_soal TEXT"),
    ("sesi_soal", "tantangan_soal", "ALTER TABLE sesi_soal ADD COLUMN tantangan_soal INTEGER"),
    ("sesi_soal", "minta_restatement", "ALTER TABLE sesi_soal ADD COLUMN minta_restatement INTEGER"),
    ("sesi_soal", "penyajian_json", "ALTER TABLE sesi_soal ADD COLUMN penyajian_json TEXT"),
    ("sesi_soal", "penyajian_versi", "ALTER TABLE sesi_soal ADD COLUMN penyajian_versi INTEGER"),
    ("sesi_soal", "renderer_versi", "ALTER TABLE sesi_soal ADD COLUMN renderer_versi INTEGER"),
    ("sesi_soal", "asal_teks", "ALTER TABLE sesi_soal ADD COLUMN asal_teks TEXT"),
    ("sesi_soal", "status_visual", "ALTER TABLE sesi_soal ADD COLUMN status_visual TEXT"),
    ("sesi_soal", "mode_representasi", "ALTER TABLE sesi_soal ADD COLUMN mode_representasi TEXT"),
    ("sesi_soal", "fingerprint_matematis", "ALTER TABLE sesi_soal ADD COLUMN fingerprint_matematis TEXT"),
    ("sesi_soal", "fingerprint_penyajian", "ALTER TABLE sesi_soal ADD COLUMN fingerprint_penyajian TEXT"),
]

# View yang definisinya berubah dan karena itu harus dibangun ulang.
VIEW_USANG: list[str] = ["ringkasan_sesi"]

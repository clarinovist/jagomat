"""Schema Paket Belajar 1 Bulan (Private dan Mini Class): tabel ledger `kelas_*` di admin-control.db.

Namespace `kelas_*` SENGAJA terpisah dari `pesanan_*`, `transfer_*`, dan `purna_*` (alasannya sama dengan
`schema_purna`: `validasi` namespace lain membandingkan semua objeknya persis dengan DDL acuan, jadi satu objek
baru di sana membuat store admin ditolak pada image lama). Tabelnya SENGAJA di admin-control.db, bukan DB belajar,
supaya akses kelas dan pemakaian deposit Peta (`purna_voucher_pakai`) dapat ditulis atomik dalam SATU transaksi.

Pola sama dengan `schema_purna`: tanpa bump `user_version`/`VERSI_SKEMA`, absen sah (belum dimigrasikan),
parsial/berbeda ditolak (ValueError), tidak diwire ke `admin_store.siapkan`; pemasangan hanya lewat
:func:`migrasikan` eksplisit. Tidak ada kunci asing ke DB belajar (siswa ada di DB lain); satu-satunya kunci asing
ke luar namespace adalah `deposit_order_id` -> `pesanan_order` (DB yang sama).

Ledger append-only (trigger ABORT atas UPDATE/DELETE dan replace-guard); koreksi hanya lewat baris baru. Status
tidak disimpan, diturunkan dari fakta (lihat `kelas_store`):

* `kelas_order`       satu pembelian satu paket oleh satu anak, atas nama satu akun pembayar;
* `kelas_tagihan`     rincian nominal (harga dasar, potongan deposit, potongan diskon) + kode unik + total (1:1);
* `kelas_bukti`       metadata berkas bukti transfer (isi berkas di subfolder `kelas`, di luar DB);
* `kelas_verifikasi`  keputusan admin setuju/tolak atas bukti terbaru;
* `kelas_akses`       masa aktif; sah hanya bila ada verifikasi setuju untuk order yang sama;
* `kelas_keluarga`    penanda keluarga oleh admin (dasar diskon anak kedua); BUKAN ledger: baris tidak boleh
  diubah, tetapi boleh dihapus lewat jalur admin kelak (rincian tagihan lama adalah salinan, tidak terpengaruh).

Harga paket TIDAK dikunci di DDL (berbeda dengan harian): kebenaran nominal terhadap katalog dijaga domain;
DB menjaga hitungan (nominal = harga dasar - potongan, total = nominal + kode unik, tidak pernah <= 0, deposit dan
diskon tidak menumpuk). Dengan begitu perubahan harga di katalog tidak memerlukan migrasi skema.

Lapis kedua di tingkat DB (trigger BEFORE INSERT): satu order terbuka per (anak, paket); semua order satu anak
atas nama akun yang sama; deposit hanya dari order Peta milik akun dan anak yang sama; bukti maksimal 5, hanya di
dalam jendela bayar, tidak setelah lunas, dan satu berkas (sha256) tidak pernah dipakai dua kali; keputusan hanya
atas bukti terbaru yang belum diputuskan (dengan bukti tertutup setelah lunas, ini sekaligus menjamin satu
keputusan setuju per order); akses hanya dari verifikasi setuju untuk anak pemilik order.
"""
import sqlite3

import paket_belajar_katalog as katalog
import schema_pesanan as sp
import schema_transfer as st

KODE_MIN = st.KODE_MIN
KODE_MAKS = st.KODE_MAKS
MAKS_BUKTI = st.MAKS_BUKTI

_PAKET = ",".join("'%s'" % p.kode for p in katalog.DAFTAR_PAKET)
_AKUN = ("length({k})=37 AND substr({k},1,5)='akun_' AND substr({k},6) " + sp._HEX)
_ID_BERAWALAN = "length({k})=36 AND substr({k},1,4)='{awalan}' AND substr({k},5) " + sp._HEX

DDL = """
CREATE TABLE kelas_order (
    id TEXT PRIMARY KEY CHECK({id_order}),
    akun_id TEXT NOT NULL CHECK({akun}),
    siswa_id INTEGER NOT NULL CHECK(siswa_id>=1),
    paket TEXT NOT NULL CHECK(paket IN ({paket})),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    kedaluwarsa TEXT NOT NULL CHECK(kedaluwarsa GLOB {waktu} AND kedaluwarsa>dibuat)
);
CREATE TABLE kelas_tagihan (
    order_id TEXT PRIMARY KEY REFERENCES kelas_order(id) ON DELETE RESTRICT,
    harga_dasar INTEGER NOT NULL CHECK(harga_dasar>0),
    potongan_deposit INTEGER NOT NULL CHECK(potongan_deposit IN (0,{deposit})),
    potongan_diskon INTEGER NOT NULL CHECK(potongan_diskon>=0),
    deposit_order_id TEXT REFERENCES pesanan_order(order_id) ON DELETE RESTRICT,
    nominal INTEGER NOT NULL,
    kode_unik INTEGER NOT NULL CHECK(kode_unik BETWEEN {kode_min} AND {kode_maks}),
    total_transfer INTEGER NOT NULL,
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    CHECK(nominal>0 AND nominal=harga_dasar-potongan_deposit-potongan_diskon),
    CHECK(total_transfer=nominal+kode_unik),
    CHECK(potongan_deposit=0 OR potongan_diskon=0),
    CHECK((potongan_deposit>0)=(deposit_order_id IS NOT NULL))
);
CREATE TABLE kelas_bukti (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES kelas_tagihan(order_id) ON DELETE RESTRICT,
    berkas TEXT NOT NULL UNIQUE CHECK(length(berkas)=32 AND berkas {hex}),
    mime TEXT NOT NULL CHECK(mime IN ({mime})),
    ukuran INTEGER NOT NULL CHECK(ukuran BETWEEN 1 AND {ukuran_maks}),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 {hex}),
    diunggah TEXT NOT NULL CHECK(diunggah GLOB {waktu})
);
CREATE TABLE kelas_verifikasi (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES kelas_tagihan(order_id) ON DELETE RESTRICT,
    keputusan TEXT NOT NULL CHECK(keputusan IN ('setuju','tolak')),
    admin_id TEXT NOT NULL CHECK(length(admin_id) BETWEEN 1 AND 64 AND admin_id {pelaku}),
    alasan TEXT CHECK(alasan IS NULL OR length(alasan) BETWEEN 1 AND {alasan_maks}),
    bukti_hingga_id INTEGER NOT NULL REFERENCES kelas_bukti(id) ON DELETE RESTRICT,
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    CHECK((keputusan='tolak')=(alasan IS NOT NULL))
);
CREATE TABLE kelas_akses (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE REFERENCES kelas_order(id) ON DELETE RESTRICT,
    siswa_id INTEGER NOT NULL CHECK(siswa_id>=1),
    verifikasi_id INTEGER NOT NULL UNIQUE REFERENCES kelas_verifikasi(id) ON DELETE RESTRICT,
    mulai TEXT NOT NULL CHECK(mulai GLOB {waktu}),
    berakhir TEXT NOT NULL CHECK(berakhir GLOB {waktu} AND berakhir>mulai),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE kelas_keluarga (
    id INTEGER PRIMARY KEY,
    keluarga_id TEXT NOT NULL CHECK({id_keluarga}),
    siswa_id INTEGER NOT NULL UNIQUE CHECK(siswa_id>=1),
    ditautkan_oleh TEXT NOT NULL CHECK(length(ditautkan_oleh) BETWEEN 1 AND 64 AND ditautkan_oleh {pelaku}),
    waktu TEXT NOT NULL CHECK(waktu GLOB {waktu})
);
CREATE INDEX idx_kelas_order_siswa ON kelas_order(siswa_id, paket, dibuat);
CREATE INDEX idx_kelas_bukti_order ON kelas_bukti(order_id, id);
CREATE INDEX idx_kelas_akses_siswa ON kelas_akses(siswa_id, berakhir);
CREATE INDEX idx_kelas_keluarga_keluarga ON kelas_keluarga(keluarga_id);
""".format(
    id_order=_ID_BERAWALAN.format(k="id", awalan="kor_"), akun=_AKUN.format(k="akun_id"),
    id_keluarga=_ID_BERAWALAN.format(k="keluarga_id", awalan="kel_"), paket=_PAKET,
    deposit=katalog.RUPIAH_DEPOSIT, kode_min=KODE_MIN, kode_maks=KODE_MAKS,
    hex=sp._HEX, waktu=sp._WAKTU, pelaku=st._PELAKU, mime=sp._enum(st.MIME_BUKTI),
    ukuran_maks=st.BATAS_UKURAN_BUKTI, alasan_maks=st.BATAS_ALASAN)

TABEL = ("kelas_order", "kelas_tagihan", "kelas_bukti", "kelas_verifikasi", "kelas_akses", "kelas_keluarga")
TABEL_LEDGER = TABEL[:-1]

# Kunci unik per tabel untuk replace-guard (INSERT OR REPLACE menghapus baris lama tanpa memicu trigger DELETE).
_KUNCI = {
    "kelas_order": ("id=NEW.id",),
    "kelas_tagihan": ("order_id=NEW.order_id",),
    "kelas_bukti": ("(NEW.id IS NOT NULL AND id=NEW.id)", "berkas=NEW.berkas"),
    "kelas_verifikasi": ("(NEW.id IS NOT NULL AND id=NEW.id)",),
    "kelas_akses": ("(NEW.id IS NOT NULL AND id=NEW.id)", "order_id=NEW.order_id",
                    "verifikasi_id=NEW.verifikasi_id"),
    "kelas_keluarga": ("(NEW.id IS NOT NULL AND id=NEW.id)", "siswa_id=NEW.siswa_id"),
}

# Fragmen untuk order beralias `o`: bukti terbaru belum diputuskan; sudah lunas (ada keputusan setuju).
SQL_BELUM_DIPUTUSKAN = ("EXISTS(SELECT 1 FROM kelas_bukti b WHERE b.order_id=o.id AND b.id>COALESCE("
                        "(SELECT MAX(v.bukti_hingga_id) FROM kelas_verifikasi v WHERE v.order_id=o.id),0))")
SQL_SUDAH_LUNAS = "EXISTS(SELECT 1 FROM kelas_verifikasi v WHERE v.order_id=o.id AND v.keputusan='setuju')"

# (nama trigger, tabel, kondisi abort, pesan)
_ATURAN = (
    ("kelas_order_satu_akun", "kelas_order",
     "EXISTS(SELECT 1 FROM kelas_order o WHERE o.siswa_id=NEW.siswa_id AND o.akun_id<>NEW.akun_id)",
     "anak sudah punya order kelas atas nama akun lain"),
    ("kelas_order_satu_terbuka", "kelas_order",
     "EXISTS(SELECT 1 FROM kelas_order o WHERE o.siswa_id=NEW.siswa_id AND o.paket=NEW.paket AND NOT %s "
     "AND (o.kedaluwarsa>NEW.dibuat OR %s))" % (SQL_SUDAH_LUNAS, SQL_BELUM_DIPUTUSKAN),
     "anak sudah punya tagihan paket ini yang masih terbuka"),
    ("kelas_tagihan_deposit_milik", "kelas_tagihan",
     "NEW.deposit_order_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM pesanan_order p JOIN kelas_order o "
     "ON o.id=NEW.order_id WHERE p.order_id=NEW.deposit_order_id AND p.akun_id=o.akun_id "
     "AND p.siswa_id=o.siswa_id)",
     "deposit hanya dari order Peta milik akun dan anak yang sama"),
    ("kelas_bukti_batas", "kelas_bukti",
     "(SELECT COUNT(*) FROM kelas_bukti WHERE order_id=NEW.order_id)>=%d" % MAKS_BUKTI,
     "batas bukti kelas tercapai"),
    ("kelas_bukti_jendela", "kelas_bukti",
     "NEW.diunggah>=(SELECT kedaluwarsa FROM kelas_order WHERE id=NEW.order_id)",
     "bukti kelas di luar jendela bayar"),
    ("kelas_bukti_setelah_lunas", "kelas_bukti",
     "EXISTS(SELECT 1 FROM kelas_verifikasi WHERE order_id=NEW.order_id AND keputusan='setuju')",
     "bukti kelas setelah lunas"),
    ("kelas_bukti_sha_baru", "kelas_bukti",
     "EXISTS(SELECT 1 FROM kelas_bukti WHERE sha256=NEW.sha256)",
     "berkas bukti kelas sudah pernah dipakai"),
    ("kelas_verifikasi_bukti_terbaru", "kelas_verifikasi",
     "NEW.bukti_hingga_id IS NOT (SELECT MAX(id) FROM kelas_bukti WHERE order_id=NEW.order_id)",
     "keputusan kelas harus atas bukti terbaru"),
    ("kelas_verifikasi_bukti_baru", "kelas_verifikasi",
     "NEW.bukti_hingga_id<=COALESCE((SELECT MAX(bukti_hingga_id) FROM kelas_verifikasi "
     "WHERE order_id=NEW.order_id),0)", "keputusan kelas tanpa bukti baru"),
    ("kelas_akses_verifikasi", "kelas_akses",
     "NOT EXISTS(SELECT 1 FROM kelas_verifikasi WHERE id=NEW.verifikasi_id AND order_id=NEW.order_id "
     "AND keputusan='setuju')", "akses kelas tanpa verifikasi setuju"),
    ("kelas_akses_siswa", "kelas_akses",
     "NEW.siswa_id IS NOT (SELECT siswa_id FROM kelas_order WHERE id=NEW.order_id)",
     "akses kelas bukan untuk anak pemilik order"),
)


def _trigger(nama, tabel, kondisi, pesan):
    return ("CREATE TRIGGER {nama} BEFORE INSERT ON {tabel}\nWHEN {kondisi}\n"
            "BEGIN SELECT RAISE(ABORT, '{pesan}'); END;\n").format(
                nama=nama, tabel=tabel, kondisi=kondisi, pesan=pesan)


def _tolak(tabel, aksi):
    return ("CREATE TRIGGER {t}_tolak_{a} BEFORE {A} ON {t}\n"
            "BEGIN SELECT RAISE(ABORT, 'ledger kelas immutable'); END;\n").format(
                t=tabel, a=aksi, A=aksi.upper())


def _penjaga(tabel):
    """Trigger penjaga satu tabel: UPDATE selalu ditolak, DELETE ditolak untuk ledger, replace-guard."""
    ddl = _tolak(tabel, "update")
    if tabel in TABEL_LEDGER:
        ddl += _tolak(tabel, "delete")
    cocok = " OR ".join(_KUNCI[tabel])
    return ddl + _trigger(tabel + "_tolak_replace", tabel,
                          "EXISTS(SELECT 1 FROM %s WHERE %s)" % (tabel, cocok), "ledger kelas duplikat")


for _tabel in TABEL:
    DDL += _penjaga(_tabel)
for _aturan in _ATURAN:
    DDL += _trigger(*_aturan)


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'kelas_*' ORDER BY type,name"))


def validasi(kon):
    """False bila belum dimigrasikan; ValueError bila parsial, berbeda, atau tanpa ledger pesanan."""
    aktual = struktur(kon)
    if not aktual:
        return False
    if not sp.validasi(kon):
        raise ValueError("kelas tanpa ledger pesanan")
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(sp.DDL)
        acuan.executescript(DDL)
        if aktual != struktur(acuan):
            raise ValueError("struktur kelas tidak lengkap")
    finally:
        acuan.close()
    return True


def migrasikan(path):
    """Migrasi eksplisit, atomik, idempoten; mensyaratkan ledger pesanan sudah terpasang."""
    import admin_store
    import admin_store_core
    with admin_store._transaksi(path) as kon:
        if not sp.validasi(kon):
            raise admin_store_core.StoreBelumSiap("pesanan belum dipasang")
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon, DDL)
        validasi(kon)
        if kon.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("integritas kelas gagal")

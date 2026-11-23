"""Skema langganan Latihan Harian (F5): enam tabel aditif dan idempoten di DB belajar, tanpa migrasi.

Namespace `harian_` (di luar `lomba_`, `langganan_`, `paket_`, `pesanan_`, `transfer_`; F4 memakai
`harian_sesi/soal/jawaban`). Dijalankan tiap `database.siapkan`, jadi semuanya `IF NOT EXISTS`.

Semua tabel append-only (trigger ABORT atas UPDATE/DELETE dan replace-guard); koreksi hanya lewat baris baru.
Status TIDAK disimpan, diturunkan dari fakta:

* `harian_order`      satu pembelian paket oleh satu anak (nominal paket dikunci CHECK, bukan dari klien);
* `harian_tagihan`    kode unik + nominal transfer order (1:1);
* `harian_bukti`      metadata berkas bukti (isi berkas di folder khusus, di luar DB);
* `harian_verifikasi` keputusan admin setuju/tolak atas bukti terbaru;
* `harian_akses`      masa aktif langganan; baris hanya sah bila ada verifikasi setuju untuk order yang sama;
* `harian_bukti_hapus` penanda berkas bukti sudah dihapus retensi 30 hari (`harian_bukti_retensi`); tabel
  terpisah supaya `harian_bukti` tetap tak berubah, dan hanya bukti yang sudah diputuskan yang bisa ditandai.

Ledger keuangan ini dipertahankan saat keluarga dihapus (siswa hanya dianonimkan); FK ke `siswa` RESTRICT.
Dua trigger penting lapis kedua: tepat satu order terbuka per anak, dan akses tanpa verifikasi setuju ditolak DB.
"""
import harian_langganan_dasar as h
from schema_transfer import BATAS_ALASAN, BATAS_UKURAN_BUKTI, MIME_BUKTI

_WAKTU = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'"
_HEX = "NOT GLOB '*[^0-9a-f]*'"
_PELAKU = "NOT GLOB '*[^A-Za-z0-9_.-]*'"
_PAKET = ",".join("'%s'" % k for k in h.PAKET)
_HARGA = " OR ".join("(paket='%s' AND rupiah=%d)" % (p.kode, p.rupiah) for p in h.PAKET.values())
_MIME = ",".join("'%s'" % m for m in MIME_BUKTI)

_TABEL = """
CREATE TABLE IF NOT EXISTS harian_order (
    id TEXT PRIMARY KEY CHECK(length(id)=36 AND substr(id,1,4)='hor_' AND substr(id,5) {hex}),
    siswa_id INTEGER NOT NULL REFERENCES siswa(id) ON DELETE RESTRICT,
    paket TEXT NOT NULL CHECK(paket IN ({paket})),
    rupiah INTEGER NOT NULL,
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    kedaluwarsa TEXT NOT NULL CHECK(kedaluwarsa GLOB {waktu} AND kedaluwarsa>dibuat),
    CHECK({harga})
);
CREATE TABLE IF NOT EXISTS harian_tagihan (
    order_id TEXT PRIMARY KEY REFERENCES harian_order(id) ON DELETE RESTRICT,
    kode_unik INTEGER NOT NULL CHECK(kode_unik BETWEEN {kode_min} AND {kode_maks}),
    nominal_transfer INTEGER NOT NULL,
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE IF NOT EXISTS harian_bukti (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES harian_tagihan(order_id) ON DELETE RESTRICT,
    berkas TEXT NOT NULL UNIQUE CHECK(length(berkas)=32 AND berkas {hex}),
    mime TEXT NOT NULL CHECK(mime IN ({mime})),
    ukuran INTEGER NOT NULL CHECK(ukuran BETWEEN 1 AND {ukuran_maks}),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 {hex}),
    diunggah TEXT NOT NULL CHECK(diunggah GLOB {waktu})
);
CREATE TABLE IF NOT EXISTS harian_verifikasi (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES harian_tagihan(order_id) ON DELETE RESTRICT,
    keputusan TEXT NOT NULL CHECK(keputusan IN ('setuju','tolak')),
    admin_id TEXT NOT NULL CHECK(length(admin_id) BETWEEN 1 AND 64 AND admin_id {pelaku}),
    alasan TEXT CHECK(alasan IS NULL OR length(alasan) BETWEEN 1 AND {alasan_maks}),
    bukti_hingga_id INTEGER NOT NULL REFERENCES harian_bukti(id) ON DELETE RESTRICT,
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu}),
    CHECK((keputusan='tolak')=(alasan IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS harian_akses (
    id INTEGER PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE REFERENCES harian_order(id) ON DELETE RESTRICT,
    siswa_id INTEGER NOT NULL REFERENCES siswa(id) ON DELETE RESTRICT,
    verifikasi_id INTEGER NOT NULL UNIQUE REFERENCES harian_verifikasi(id) ON DELETE RESTRICT,
    mulai TEXT NOT NULL CHECK(mulai GLOB {waktu}),
    berakhir TEXT NOT NULL CHECK(berakhir GLOB {waktu} AND berakhir>mulai),
    dibuat TEXT NOT NULL CHECK(dibuat GLOB {waktu})
);
CREATE TABLE IF NOT EXISTS harian_bukti_hapus (
    bukti_id INTEGER PRIMARY KEY REFERENCES harian_bukti(id) ON DELETE RESTRICT,
    dihapus TEXT NOT NULL CHECK(dihapus GLOB {waktu})
);
CREATE INDEX IF NOT EXISTS idx_harian_order_siswa ON harian_order(siswa_id, dibuat);
CREATE INDEX IF NOT EXISTS idx_harian_bukti_order ON harian_bukti(order_id, id);
CREATE INDEX IF NOT EXISTS idx_harian_akses_siswa ON harian_akses(siswa_id, berakhir);
""".format(hex=_HEX, waktu=_WAKTU, paket=_PAKET, harga=_HARGA, kode_min=h.KODE_MIN, kode_maks=h.KODE_MAKS,
           mime=_MIME, ukuran_maks=BATAS_UKURAN_BUKTI, pelaku=_PELAKU, alasan_maks=BATAS_ALASAN)

TABEL = ("harian_order", "harian_tagihan", "harian_bukti", "harian_verifikasi", "harian_akses", "harian_bukti_hapus")

# Kunci unik per tabel untuk replace-guard (INSERT OR REPLACE menghapus baris lama tanpa memicu trigger DELETE).
_KUNCI = {
    "harian_order": ("id=NEW.id",),
    "harian_tagihan": ("order_id=NEW.order_id",),
    "harian_bukti": ("(NEW.id IS NOT NULL AND id=NEW.id)", "berkas=NEW.berkas"),
    "harian_verifikasi": ("(NEW.id IS NOT NULL AND id=NEW.id)",),
    "harian_akses": ("(NEW.id IS NOT NULL AND id=NEW.id)", "order_id=NEW.order_id",
                     "verifikasi_id=NEW.verifikasi_id"),
    "harian_bukti_hapus": ("bukti_id=NEW.bukti_id",),
}

# Bukti terbaru yang belum diputuskan: id bukti lebih besar dari keputusan terakhir untuk order itu.
SQL_BELUM_DIPUTUSKAN = ("EXISTS(SELECT 1 FROM harian_bukti b WHERE b.order_id=o.id AND b.id>COALESCE("
                     "(SELECT MAX(v.bukti_hingga_id) FROM harian_verifikasi v WHERE v.order_id=o.id),0))")
SQL_SUDAH_LUNAS = "EXISTS(SELECT 1 FROM harian_verifikasi v WHERE v.order_id=o.id AND v.keputusan='setuju')"

# (nama trigger, tabel, kondisi abort, pesan)
_ATURAN = (
    ("harian_tagihan_nominal", "harian_tagihan",
     "NEW.nominal_transfer IS NOT (SELECT rupiah FROM harian_order WHERE id=NEW.order_id)+NEW.kode_unik",
     "nominal tagihan langganan tidak cocok dengan order"),
    ("harian_order_satu_terbuka", "harian_order",
     "EXISTS(SELECT 1 FROM harian_order o WHERE o.siswa_id=NEW.siswa_id AND NOT %s AND (o.kedaluwarsa>NEW.dibuat OR %s))"
     % (SQL_SUDAH_LUNAS, SQL_BELUM_DIPUTUSKAN), "anak sudah punya tagihan langganan yang masih terbuka"),
    ("harian_bukti_batas", "harian_bukti",
     "(SELECT COUNT(*) FROM harian_bukti WHERE order_id=NEW.order_id)>=5", "batas bukti langganan tercapai"),
    ("harian_bukti_jendela", "harian_bukti",
     "NEW.diunggah>=(SELECT kedaluwarsa FROM harian_order WHERE id=NEW.order_id)",
     "bukti langganan di luar jendela bayar"),
    ("harian_bukti_setelah_lunas", "harian_bukti",
     "EXISTS(SELECT 1 FROM harian_verifikasi WHERE order_id=NEW.order_id AND keputusan='setuju')",
     "bukti langganan setelah lunas"),
    ("harian_verifikasi_bukti_terbaru", "harian_verifikasi",
     "NEW.bukti_hingga_id IS NOT (SELECT MAX(id) FROM harian_bukti WHERE order_id=NEW.order_id)",
     "keputusan langganan harus atas bukti terbaru"),
    ("harian_verifikasi_bukti_baru", "harian_verifikasi",
     "NEW.bukti_hingga_id<=COALESCE((SELECT MAX(bukti_hingga_id) FROM harian_verifikasi "
     "WHERE order_id=NEW.order_id),0)", "keputusan langganan tanpa bukti baru"),
    ("harian_verifikasi_satu_setuju", "harian_verifikasi",
     "EXISTS(SELECT 1 FROM harian_verifikasi WHERE order_id=NEW.order_id AND keputusan='setuju')",
     "order langganan sudah punya keputusan setuju"),
    ("harian_akses_verifikasi", "harian_akses",
     "NOT EXISTS(SELECT 1 FROM harian_verifikasi WHERE id=NEW.verifikasi_id AND order_id=NEW.order_id "
     "AND keputusan='setuju')", "akses langganan tanpa verifikasi setuju"),
    ("harian_bukti_hapus_putusan", "harian_bukti_hapus",
     "NOT EXISTS(SELECT 1 FROM harian_verifikasi v WHERE v.bukti_hingga_id>=NEW.bukti_id "
     "AND v.order_id=(SELECT order_id FROM harian_bukti WHERE id=NEW.bukti_id))",
     "bukti langganan belum diputuskan"),
    ("harian_akses_siswa", "harian_akses",
     "NEW.siswa_id IS NOT (SELECT siswa_id FROM harian_order WHERE id=NEW.order_id)",
     "akses langganan bukan untuk anak pemilik order"),
)


def _trigger(nama, tabel, kondisi, pesan):
    return ("CREATE TRIGGER IF NOT EXISTS {nama} BEFORE INSERT ON {tabel}\nWHEN {kondisi}\n"
            "BEGIN SELECT RAISE(ABORT, '{pesan}'); END;\n").format(
                nama=nama, tabel=tabel, kondisi=kondisi, pesan=pesan)


def _ledger(tabel):
    ddl = ""
    for aksi in ("update", "delete"):
        ddl += ("CREATE TRIGGER IF NOT EXISTS {t}_tolak_{a} BEFORE {A} ON {t}\n"
                "BEGIN SELECT RAISE(ABORT, 'ledger langganan immutable'); END;\n").format(
                    t=tabel, a=aksi, A=aksi.upper())
    cocok = " OR ".join(_KUNCI[tabel])
    return ddl + _trigger(tabel + "_tolak_replace", tabel,
                          "EXISTS(SELECT 1 FROM %s WHERE %s)" % (tabel, cocok), "ledger langganan duplikat")


def _bangun():
    ddl = _TABEL
    for tabel in TABEL:
        ddl += _ledger(tabel)
    for aturan in _ATURAN:
        ddl += _trigger(*aturan)
    return ddl


SKEMA_HARIAN_LANGGANAN = _bangun()

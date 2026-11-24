"""Skema kelas_*: opt-in di admin-control.db, fail-closed, append-only, guard tingkat DB. Data sintetis.

Skenario guard ditulis sebagai fungsi `skenario_*(kon)` yang melempar `GuardSalah` bila DB tidak berperilaku
sesuai aturan. Tes biasa menjalankannya pada DB hasil `schema_kelas.migrasikan`; tes mutation menjalankan skenario
YANG SAMA pada DB yang DDL-nya sudah dilucuti satu guard dan menuntut `GuardSalah` (merah karena asersi guard,
bukan karena fixture rusak), lalu hijau pada DB utuh. Pola sama dengan `test_schema_purna.py`.
"""
import contextlib
import re
import sqlite3

import pytest

import admin_store
import admin_store_core
import pesanan
import schema_kelas
import schema_pesanan
import schema_purna
import schema_transfer
from kelas_kit import (ADMIN, AKUN_A, AKUN_B, KINI, SESUDAH_JENDELA, SESUDAH_UPLOAD, baris, kel, kor,
                       peta_lunas, sha, siapkan_db_kelas, sisip_bukti, sisip_order, sisip_tagihan,
                       sisip_verifikasi)
from purna_kit import siapkan_db_purna

BAWAAN_AKSES = ("2026-11-20T09:30:00", "2026-12-20T09:30:00")


class GuardSalah(AssertionError):
    """Guard DB tidak berperilaku sesuai aturan (tidak menolak, salah pesan, atau salah menolak)."""


def harus_abort(kon, sql, params, pesan):
    try:
        kon.execute(sql, params)
    except sqlite3.IntegrityError as galat:
        if pesan not in str(galat):
            raise GuardSalah("pesan abort %r tidak memuat %r" % (str(galat), pesan))
        return
    raise GuardSalah("tidak ditolak: %s" % sql)


def harus_lolos(fungsi, *args, **kw):
    try:
        return fungsi(*args, **kw)
    except sqlite3.IntegrityError as galat:
        raise GuardSalah("salah ditolak (%s)" % galat)


def dump(path):
    with contextlib.closing(sqlite3.connect(path)) as kon:
        return tuple(kon.iterdump())


def sisip_akses(kon, oid, vid, siswa=1, *, mulai=BAWAAN_AKSES[0], berakhir=BAWAAN_AKSES[1]):
    return kon.execute("INSERT INTO kelas_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) "
                       "VALUES(?,?,?,?,?,?)", (oid, siswa, vid, mulai, berakhir, SESUDAH_UPLOAD)).lastrowid


def rantai(kon, n=1, *, siswa=1, paket="mini", akun=AKUN_A):
    """Order + tagihan + bukti + verifikasi setuju + akses lengkap; mengembalikan (order, bukti, verifikasi, akses)."""
    oid = harus_lolos(sisip_order, kon, n, siswa=siswa, paket=paket, akun=akun)
    harus_lolos(sisip_tagihan, kon, oid)
    bid = harus_lolos(sisip_bukti, kon, oid, n)
    vid = harus_lolos(sisip_verifikasi, kon, oid, bid)
    return oid, bid, vid, harus_lolos(sisip_akses, kon, oid, vid, siswa)


# --- skenario guard (dipakai tes biasa DAN tes mutation) -----------------------------------

def skenario_total_salah(kon):
    oid = sisip_order(kon, 1)
    harus_lolos(sisip_tagihan, kon, oid, kode=7)
    oid2 = sisip_order(kon, 2, siswa=2)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid2, 250_000, 0, 0, None, 250_000, 7, 250_008, KINI), "total_transfer=nominal+kode_unik")


def skenario_nominal_tidak_sama_rincian(kon):
    oid = sisip_order(kon, 1)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, 250_000, 0, 50_000, None, 250_000, 7, 250_007, KINI), "nominal=harga_dasar-potongan")


def skenario_nominal_tidak_positif(kon):
    oid = sisip_order(kon, 1)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, 49_000, 0, 49_000, None, 0, 7, 7, KINI), "nominal>0")


def skenario_deposit_dan_diskon_menumpuk(kon):
    peta = peta_lunas(kon, 1)
    oid = sisip_order(kon, 1)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, 250_000, 49_000, 20_000, peta, 181_000, 7, 181_007, KINI),
                "potongan_deposit=0 OR potongan_diskon=0")


def skenario_deposit_butuh_order_peta(kon):
    peta = peta_lunas(kon, 1)
    oid, oid2 = sisip_order(kon, 1), sisip_order(kon, 2, paket="private")
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, 250_000, 49_000, 0, None, 201_000, 7, 201_007, KINI), "deposit_order_id IS NOT NULL")
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid2, 250_000, 0, 0, peta, 250_000, 7, 250_007, KINI), "deposit_order_id IS NOT NULL")


def skenario_kode_unik_di_luar_rentang(kon):
    oid, oid2 = sisip_order(kon, 1), sisip_order(kon, 2, siswa=2)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, 250_000, 0, 0, None, 250_000, 0, 250_000, KINI), "kode_unik BETWEEN")
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid2, 250_000, 0, 0, None, 250_000, 1000, 251_000, KINI), "kode_unik BETWEEN")
    harus_lolos(sisip_tagihan, kon, oid, kode=999)


def skenario_deposit_milik_akun_dan_anak(kon):
    peta = peta_lunas(kon, 1, AKUN_A)
    sah = sisip_order(kon, 1, siswa=1, akun=AKUN_A)
    harus_lolos(sisip_tagihan, kon, sah, deposit=49_000, deposit_order=peta)
    akun_lain = sisip_order(kon, 2, siswa=2, akun=AKUN_B)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (akun_lain, 250_000, 49_000, 0, peta, 201_000, 7, 201_007, KINI), "milik akun dan anak")
    anak_lain = sisip_order(kon, 3, siswa=3, akun=AKUN_A)
    harus_abort(kon, "INSERT INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (anak_lain, 250_000, 49_000, 0, peta, 201_000, 7, 201_007, KINI), "milik akun dan anak")


def skenario_satu_order_terbuka(kon):
    sisip_order(kon, 1)
    harus_abort(kon, "INSERT INTO kelas_order VALUES(?,?,?,?,?,?)",
                (kor(2), AKUN_A, 1, "mini", KINI, SESUDAH_JENDELA), "masih terbuka")
    harus_lolos(sisip_order, kon, 3, paket="private")             # paket lain boleh
    harus_lolos(sisip_order, kon, 4, siswa=2)                     # anak lain boleh
    harus_lolos(sisip_order, kon, 5, dibuat=SESUDAH_JENDELA, kedaluwarsa="2026-11-22T09:00:00")  # lama kedaluwarsa


def skenario_order_terbuka_menunggu_tidak_lepas(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    sisip_bukti(kon, oid, 1)
    harus_abort(kon, "INSERT INTO kelas_order VALUES(?,?,?,?,?,?)",
                (kor(2), AKUN_A, 1, "mini", "2026-11-22T09:00:00", "2026-11-23T09:00:00"), "masih terbuka")


def skenario_order_lunas_tidak_menghalangi(kon):
    rantai(kon, 1)
    harus_lolos(sisip_order, kon, 2, dibuat="2026-11-21T00:00:00", kedaluwarsa="2026-11-22T00:00:00")


def skenario_satu_akun_per_anak(kon):
    sisip_order(kon, 1, akun=AKUN_A, paket="mini")
    harus_abort(kon, "INSERT INTO kelas_order VALUES(?,?,?,?,?,?)",
                (kor(2), AKUN_B, 1, "private", KINI, SESUDAH_JENDELA), "akun lain")


def skenario_bukti_maksimal_lima(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    for n in range(1, 6):
        harus_lolos(sisip_bukti, kon, oid, n)
    harus_abort(kon, "INSERT INTO kelas_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                (oid, "%032x" % 99, "image/png", 10, "%064x" % 99, SESUDAH_UPLOAD), "batas bukti")


def skenario_bukti_di_luar_jendela(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    harus_abort(kon, "INSERT INTO kelas_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                (oid, "%032x" % 1, "image/png", 10, "%064x" % 1, SESUDAH_JENDELA), "jendela bayar")
    harus_lolos(sisip_bukti, kon, oid, 2, diunggah="2026-11-21T08:59:59")


def skenario_bukti_setelah_lunas(kon):
    oid, _, _, _ = rantai(kon, 1)
    harus_abort(kon, "INSERT INTO kelas_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                (oid, "%032x" % 99, "image/png", 10, "%064x" % 99, SESUDAH_UPLOAD), "setelah lunas")


def skenario_bukti_tidak_dipakai_ulang(kon):
    o1, o2 = sisip_order(kon, 1), sisip_order(kon, 2, siswa=2)
    sisip_tagihan(kon, o1)
    sisip_tagihan(kon, o2)
    sisip_bukti(kon, o1, 1)
    harus_abort(kon, "INSERT INTO kelas_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                (o2, "%032x" % 99, "image/png", 10, sha(1), SESUDAH_UPLOAD), "sudah pernah dipakai")
    harus_lolos(sisip_bukti, kon, o2, 2)


def skenario_keputusan_hanya_atas_bukti_terbaru(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    b1, b2 = sisip_bukti(kon, oid, 1), sisip_bukti(kon, oid, 2)
    harus_abort(kon, "INSERT INTO kelas_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, "setuju", ADMIN, None, b1, SESUDAH_UPLOAD), "bukti terbaru")
    harus_lolos(sisip_verifikasi, kon, oid, b2)


def skenario_keputusan_butuh_bukti_baru(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    b1 = sisip_bukti(kon, oid, 1)
    harus_lolos(sisip_verifikasi, kon, oid, b1, keputusan="tolak", alasan="buram")
    harus_abort(kon, "INSERT INTO kelas_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, "tolak", ADMIN, "lagi", b1, SESUDAH_UPLOAD), "tanpa bukti baru")


def skenario_tolak_wajib_alasan_setuju_tanpa_alasan(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    b1, b2 = sisip_bukti(kon, oid, 1), sisip_bukti(kon, oid, 2)
    harus_abort(kon, "INSERT INTO kelas_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, "tolak", ADMIN, None, b2, SESUDAH_UPLOAD),
                "(keputusan='tolak')=(alasan IS NOT NULL)")


def skenario_akses_butuh_verifikasi_setuju(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    b1 = sisip_bukti(kon, oid, 1)
    tolak = sisip_verifikasi(kon, oid, b1, keputusan="tolak", alasan="buram")
    harus_abort(kon, "INSERT INTO kelas_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, 1, tolak) + BAWAAN_AKSES + (SESUDAH_UPLOAD,), "tanpa verifikasi setuju")
    lain, _, vlain, _ = rantai(kon, 2, siswa=2)
    harus_abort(kon, "INSERT INTO kelas_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, 1, vlain) + BAWAAN_AKSES + (SESUDAH_UPLOAD,), "tanpa verifikasi setuju")


def skenario_akses_hanya_untuk_anak_pemilik(kon):
    oid = sisip_order(kon, 1, siswa=1)
    sisip_tagihan(kon, oid)
    vid = sisip_verifikasi(kon, oid, sisip_bukti(kon, oid, 1))
    harus_abort(kon, "INSERT INTO kelas_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, 2, vid) + BAWAAN_AKSES + (SESUDAH_UPLOAD,), "bukan untuk anak pemilik")
    harus_lolos(sisip_akses, kon, oid, vid, 1)


def skenario_akses_berakhir_sesudah_mulai(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    vid = sisip_verifikasi(kon, oid, sisip_bukti(kon, oid, 1))
    harus_abort(kon, "INSERT INTO kelas_akses(order_id,siswa_id,verifikasi_id,mulai,berakhir,dibuat) "
                "VALUES(?,?,?,?,?,?)", (oid, 1, vid, BAWAAN_AKSES[1], BAWAAN_AKSES[0], SESUDAH_UPLOAD),
                "berakhir>mulai")


_UBAH = {"kelas_order": "dibuat", "kelas_tagihan": "dibuat", "kelas_bukti": "ukuran",
         "kelas_verifikasi": "dibuat", "kelas_akses": "dibuat", "kelas_keluarga": "waktu"}


def _isi_semua(kon):
    rantai(kon, 1)
    kon.execute("INSERT INTO kelas_keluarga(keluarga_id,siswa_id,ditautkan_oleh,waktu) VALUES(?,?,?,?)",
                (kel(1), 1, ADMIN, KINI))


def _skenario_update(tabel):
    def skenario(kon):
        _isi_semua(kon)
        harus_abort(kon, "UPDATE %s SET %s=%s" % (tabel, _UBAH[tabel], _UBAH[tabel]), (), "immutable")
    return skenario


def _skenario_delete(tabel):
    def skenario(kon):
        _isi_semua(kon)
        harus_abort(kon, "DELETE FROM %s" % tabel, (), "immutable")
        assert kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0] == 1
    return skenario


def skenario_replace_order(kon):
    oid, _, _, _ = rantai(kon, 1)
    harus_abort(kon, "INSERT OR REPLACE INTO kelas_order VALUES(?,?,?,?,?,?)",
                (oid, AKUN_A, 1, "mini", KINI, SESUDAH_JENDELA), "duplikat")


def skenario_replace_tagihan(kon):
    oid, _, _, _ = rantai(kon, 1)
    harus_abort(kon, "INSERT OR REPLACE INTO kelas_tagihan VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, 250_000, 0, 0, None, 250_000, 9, 250_009, KINI), "duplikat")


def skenario_replace_bukti(kon):
    oid = sisip_order(kon, 1)
    sisip_tagihan(kon, oid)
    bid = sisip_bukti(kon, oid, 1)
    harus_abort(kon, "INSERT OR REPLACE INTO kelas_bukti VALUES(?,?,?,?,?,?,?)",
                (bid, oid, "%032x" % 98, "image/png", 10, "%064x" % 98, SESUDAH_UPLOAD), "duplikat")
    harus_abort(kon, "INSERT OR REPLACE INTO kelas_bukti VALUES(NULL,?,?,?,?,?,?)",
                (oid, "%032x" % (1 + 0xB0), "image/png", 10, "%064x" % 97, SESUDAH_UPLOAD), "duplikat")


def skenario_replace_keluarga(kon):
    _isi_semua(kon)
    harus_abort(kon, "INSERT OR REPLACE INTO kelas_keluarga VALUES(NULL,?,?,?,?)",
                (kel(2), 1, ADMIN, KINI), "duplikat")
    assert baris(kon, "kelas_keluarga")[0][1] == kel(1)


def skenario_keluarga_boleh_dihapus_tetapi_siswa_unik(kon):
    _isi_semua(kon)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO kelas_keluarga(keluarga_id,siswa_id,ditautkan_oleh,waktu) VALUES(?,?,?,?)",
                    (kel(2), 1, ADMIN, KINI))
    kon.execute("DELETE FROM kelas_keluarga")
    assert kon.execute("SELECT COUNT(*) FROM kelas_keluarga").fetchone()[0] == 0


SKENARIO = {n[len("skenario_"):]: f for n, f in list(globals().items()) if n.startswith("skenario_")}
for _t in schema_kelas.TABEL:
    SKENARIO["update_" + _t] = _skenario_update(_t)
for _t in schema_kelas.TABEL_LEDGER:
    SKENARIO["delete_" + _t] = _skenario_delete(_t)


def jalankan(path, nama):
    """Jalankan satu skenario pada koneksi baru; semua tulisan dibuang sesudahnya."""
    with pesanan.buka(path, tulis_data=True) as kon:
        try:
            SKENARIO[nama](kon)
        finally:
            kon.rollback()


@pytest.fixture
def db(tmp_path):
    return siapkan_db_kelas(tmp_path)


# --- pemasangan, absen sah, fail-closed ------------------------------------------------------

def test_konstanta_publik():
    assert schema_kelas.TABEL == ("kelas_order", "kelas_tagihan", "kelas_bukti", "kelas_verifikasi",
                                  "kelas_akses", "kelas_keluarga")
    assert schema_kelas.TABEL_LEDGER == schema_kelas.TABEL[:-1]
    assert (schema_kelas.KODE_MIN, schema_kelas.KODE_MAKS, schema_kelas.MAKS_BUKTI) == (1, 999, 5)


def test_absen_sah_dan_tidak_dipasang_oleh_siapkan_atau_migrasi_lain(tmp_path):
    path = siapkan_db_purna(tmp_path)
    admin_store.siapkan(path, sekarang=99)
    with admin_store.buka_baca(path) as kon:
        assert schema_kelas.validasi(kon) is False
        assert not schema_kelas.struktur(kon)
        assert schema_purna.validasi(kon) is True


def test_migrasi_idempoten_user_version_tetap_dan_tabel_lengkap(tmp_path):
    path = siapkan_db_purna(tmp_path)
    with contextlib.closing(sqlite3.connect(path)) as kon:
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
    schema_kelas.migrasikan(path)
    pertama = dump(path)
    schema_kelas.migrasikan(path)
    admin_store.siapkan(path, sekarang=99)
    assert dump(path) == pertama
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert schema_kelas.validasi(kon) is True
        assert {r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'kelas_*'")} == set(schema_kelas.TABEL)
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()


def test_store_admin_tetap_membuka_dan_ddl_namespace_lain_byte_identik(tmp_path):
    path = siapkan_db_purna(tmp_path)

    def lain(p):
        with contextlib.closing(sqlite3.connect(p)) as kon:
            return tuple(tuple(r) for r in kon.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name NOT GLOB 'kelas_*' "
                "ORDER BY type,name"))

    sebelum = lain(path)
    schema_kelas.migrasikan(path)
    assert lain(path) == sebelum
    with admin_store.buka_baca(path) as kon:
        admin_store_core.validasi_skema(kon)
        assert schema_pesanan.validasi(kon) and schema_transfer.validasi(kon) and schema_purna.validasi(kon)


def test_migrasi_ditolak_bila_pesanan_belum_terpasang(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    with pytest.raises(admin_store.StoreBelumSiap):
        schema_kelas.migrasikan(path)
    with admin_store.buka_baca(path) as kon:
        assert not schema_kelas.struktur(kon)


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER kelas_order_satu_terbuka",
    "DROP TRIGGER kelas_tagihan_deposit_milik",
    "DROP TRIGGER kelas_akses_verifikasi",
    "DROP TRIGGER kelas_bukti_tolak_replace",
    "DROP INDEX idx_kelas_akses_siswa",
])
def test_struktur_parsial_atau_berbeda_ditolak(db, rusak):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute(rusak)
        kon.commit()
    sebelum = dump(db)
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_kelas.validasi(kon)
    with pytest.raises((ValueError, admin_store.StoreBelumSiap)):
        schema_kelas.migrasikan(db)
    assert dump(db) == sebelum


def test_definisi_tabel_berbeda_ditolak(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute("ALTER TABLE kelas_tagihan ADD COLUMN bebas TEXT")
        kon.commit()
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_kelas.validasi(kon)


def test_kelas_tanpa_ledger_pesanan_ditolak_validasi(tmp_path):
    kosong = tmp_path / "kosong.db"
    with contextlib.closing(sqlite3.connect(kosong)) as kon:
        kon.executescript("CREATE TABLE kelas_order(id TEXT);")
        with pytest.raises(ValueError):
            schema_kelas.validasi(kon)


def test_fk_deposit_ke_pesanan_order_restrict_dan_tanpa_fk_ke_db_belajar(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        fk = {t: [(r[2], r[3], r[4], r[6]) for r in kon.execute("PRAGMA foreign_key_list(%s)" % t)]
              for t in schema_kelas.TABEL}
    assert ("pesanan_order", "deposit_order_id", "order_id", "RESTRICT") in fk["kelas_tagihan"]
    assert all(tujuan.startswith("kelas_") or tujuan == "pesanan_order"
               for daftar in fk.values() for tujuan, _, _, _ in daftar)
    assert not any(tujuan == "siswa" for daftar in fk.values() for tujuan, _, _, _ in daftar)


def test_fk_deposit_menolak_order_peta_tak_ada_dan_menahan_hapus_order_peta(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        peta = peta_lunas(kon, 1)
        oid = sisip_order(kon, 1)
        sisip_tagihan(kon, oid, deposit=49_000, deposit_order=peta)
        kon.commit()
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("DELETE FROM pesanan_order WHERE order_id=?", (peta,))


@pytest.mark.parametrize("sql,params", [
    ("INSERT INTO kelas_order VALUES(?,?,?,?,?,?)", ("kor_xyz", AKUN_A, 1, "mini", KINI, SESUDAH_JENDELA)),
    ("INSERT INTO kelas_order VALUES(?,?,?,?,?,?)", (kor(1), "akun_xyz", 1, "mini", KINI, SESUDAH_JENDELA)),
    ("INSERT INTO kelas_order VALUES(?,?,?,?,?,?)", (kor(1), AKUN_A, 0, "mini", KINI, SESUDAH_JENDELA)),
    ("INSERT INTO kelas_order VALUES(?,?,?,?,?,?)", (kor(1), AKUN_A, 1, "vip", KINI, SESUDAH_JENDELA)),
    ("INSERT INTO kelas_order VALUES(?,?,?,?,?,?)", (kor(1), AKUN_A, 1, "mini", "kemarin", SESUDAH_JENDELA)),
    ("INSERT INTO kelas_order VALUES(?,?,?,?,?,?)", (kor(1), AKUN_A, 1, "mini", KINI, KINI)),
])
def test_check_kolom_order(db, sql, params):
    with pesanan.buka(db, tulis_data=True) as kon:
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(sql, params)
        kon.rollback()
        assert baris(kon, "kelas_order") == []


@pytest.mark.parametrize("ganti", [
    dict(mime="text/html"), dict(ukuran=0), dict(ukuran=5 * 1024 * 1024 + 1),
    dict(sha256="xyz"), dict(berkas="pendek"),
])
def test_check_kolom_bukti(db, ganti):
    with pesanan.buka(db, tulis_data=True) as kon:
        oid = sisip_order(kon, 1)
        sisip_tagihan(kon, oid)
        with pytest.raises(sqlite3.IntegrityError):
            sisip_bukti(kon, oid, 1, **ganti)
        kon.rollback()


def test_keluarga_check_kolom(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        for nilai in ((kel(1)[:-1], 1, ADMIN, KINI), (kel(1), 0, ADMIN, KINI), (kel(1), 1, "", KINI),
                      (kel(1), 1, "a b", KINI), (kel(1), 1, ADMIN, "kemarin")):
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute("INSERT INTO kelas_keluarga(keluarga_id,siswa_id,ditautkan_oleh,waktu) "
                            "VALUES(?,?,?,?)", nilai)


# --- guard tingkat DB pada skema utuh -----------------------------------------------------------

@pytest.mark.parametrize("nama", sorted(SKENARIO))
def test_skenario_guard_hijau_pada_skema_utuh(db, nama):
    jalankan(db, nama)


# --- mutation: tiap guard dilucuti pada DDL; skenario yang menjaganya harus MERAH ---------------

def _lucuti_trigger(ddl, nama):
    hasil, n = re.subn(r"CREATE TRIGGER %s BEFORE .*?END;\n" % re.escape(nama), "", ddl, flags=re.DOTALL)
    assert n == 1, "mutasi hampa: trigger %s tidak ditemukan" % nama
    return hasil


def _ganti(ddl, lama, baru):
    assert ddl.count(lama) == 1, "pola mutasi harus unik dan ada: %r" % lama
    return ddl.replace(lama, baru)


def _db_mutasi(tmp_path, ddl):
    path = siapkan_db_purna(tmp_path)
    with contextlib.closing(sqlite3.connect(path)) as kon:
        kon.executescript(ddl)
    return path


GUARD_TRIGGER = (
    ("kelas_order_satu_akun", "satu_akun_per_anak"),
    ("kelas_order_satu_terbuka", "satu_order_terbuka"),
    ("kelas_order_satu_terbuka", "order_terbuka_menunggu_tidak_lepas"),
    ("kelas_tagihan_deposit_milik", "deposit_milik_akun_dan_anak"),
    ("kelas_bukti_batas", "bukti_maksimal_lima"),
    ("kelas_bukti_jendela", "bukti_di_luar_jendela"),
    ("kelas_bukti_setelah_lunas", "bukti_setelah_lunas"),
    ("kelas_bukti_sha_baru", "bukti_tidak_dipakai_ulang"),
    ("kelas_verifikasi_bukti_terbaru", "keputusan_hanya_atas_bukti_terbaru"),
    ("kelas_verifikasi_bukti_baru", "keputusan_butuh_bukti_baru"),
    ("kelas_akses_verifikasi", "akses_butuh_verifikasi_setuju"),
    ("kelas_akses_siswa", "akses_hanya_untuk_anak_pemilik"),
    ("kelas_order_tolak_replace", "replace_order"),
    ("kelas_tagihan_tolak_replace", "replace_tagihan"),
    ("kelas_bukti_tolak_replace", "replace_bukti"),
    ("kelas_keluarga_tolak_replace", "replace_keluarga"),
) + tuple(("%s_tolak_update" % t, "update_" + t) for t in schema_kelas.TABEL) + tuple(
    ("%s_tolak_delete" % t, "delete_" + t) for t in schema_kelas.TABEL_LEDGER)

# Guard yang sengaja TIDAK punya skenario mutation karena dijaga lapis lain yang tak terpisahkan:
# replace verifikasi/akses selalu juga ditolak trigger bukti-baru/akses-verifikasi pada kunci yang sama.
_TANPA_SKENARIO_MUTASI = {"kelas_verifikasi_tolak_replace", "kelas_akses_tolak_replace"}


def test_daftar_guard_mutation_lengkap_sama_dengan_trigger_di_skema(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        trigger = {r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name GLOB 'kelas_*'")}
    assert trigger == {nama for nama, _ in GUARD_TRIGGER} | _TANPA_SKENARIO_MUTASI


@pytest.mark.parametrize("nama,skenario", GUARD_TRIGGER, ids=["%s/%s" % g for g in GUARD_TRIGGER])
def test_mutation_tanpa_trigger_skenario_merah_lalu_hijau_saat_dipulihkan(tmp_path, nama, skenario):
    dimutasi = _db_mutasi(tmp_path / "mutasi", _lucuti_trigger(schema_kelas.DDL, nama))
    with pytest.raises(GuardSalah):
        jalankan(dimutasi, skenario)
    jalankan(siapkan_db_kelas(tmp_path / "pulih"), skenario)


CABANG = (
    ("total-sama-nominal-tambah-kode",
     ("    CHECK(total_transfer=nominal+kode_unik),\n", ""), "total_salah"),
    ("nominal-sama-rincian",
     ("CHECK(nominal>0 AND nominal=harga_dasar-potongan_deposit-potongan_diskon)", "CHECK(nominal>0)"),
     "nominal_tidak_sama_rincian"),
    ("nominal-positif",
     ("CHECK(nominal>0 AND nominal=harga_dasar-potongan_deposit-potongan_diskon)",
      "CHECK(nominal=harga_dasar-potongan_deposit-potongan_diskon)"), "nominal_tidak_positif"),
    ("deposit-dan-diskon-tidak-menumpuk",
     ("    CHECK(potongan_deposit=0 OR potongan_diskon=0),\n", ""), "deposit_dan_diskon_menumpuk"),
    ("deposit-sepasang-order-peta",
     ("    CHECK((potongan_deposit>0)=(deposit_order_id IS NOT NULL))\n", "    CHECK(1)\n"),
     "deposit_butuh_order_peta"),
    ("kode-unik-dalam-rentang",
     ("CHECK(kode_unik BETWEEN 1 AND 999)", "CHECK(kode_unik>=0)"), "kode_unik_di_luar_rentang"),
    ("tolak-wajib-alasan",
     ("    CHECK((keputusan='tolak')=(alasan IS NOT NULL))\n", "    CHECK(1)\n"),
     "tolak_wajib_alasan_setuju_tanpa_alasan"),
    ("akses-berakhir-sesudah-mulai",
     ("CHECK(berakhir GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]' "
      "AND berakhir>mulai)",
      "CHECK(berakhir GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]')"),
     "akses_berakhir_sesudah_mulai"),
    ("order-lunas-tidak-menghalangi",
     ("AND NOT EXISTS(SELECT 1 FROM kelas_verifikasi v WHERE v.order_id=o.id AND v.keputusan='setuju') AND (o.ked",
      "AND (o.ked"), "order_lunas_tidak_menghalangi"),
    ("order-kedaluwarsa-melepas",
     ("(o.kedaluwarsa>NEW.dibuat OR", "(1 OR"), "satu_order_terbuka"),
)


@pytest.mark.parametrize("label,penggantian,skenario", CABANG, ids=[c[0] for c in CABANG])
def test_mutation_cabang_kondisi_dilucuti_skenario_merah(tmp_path, label, penggantian, skenario):
    ddl = _ganti(schema_kelas.DDL, *penggantian)
    with pytest.raises(GuardSalah):
        jalankan(_db_mutasi(tmp_path / "mutasi", ddl), skenario)
    jalankan(siapkan_db_kelas(tmp_path / "pulih"), skenario)


def test_replace_verifikasi_dan_akses_tidak_mengubah_data(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        _, bid, vid, aid = rantai(kon, 1)
        sebelum = (baris(kon, "kelas_verifikasi"), baris(kon, "kelas_akses"))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT OR REPLACE INTO kelas_verifikasi VALUES(?,?,?,?,?,?,?)",
                        (vid, kor(1), "setuju", ADMIN, None, bid, SESUDAH_UPLOAD))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT OR REPLACE INTO kelas_akses VALUES(?,?,?,?,?,?,?)",
                        (aid, kor(1), 1, vid) + BAWAAN_AKSES[:1] + ("2027-01-20T09:30:00", SESUDAH_UPLOAD))
        assert (baris(kon, "kelas_verifikasi"), baris(kon, "kelas_akses")) == sebelum

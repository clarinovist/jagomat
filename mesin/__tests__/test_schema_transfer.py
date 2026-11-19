"""Skema transfer_*: aditif di atas pesanan v1, fail-closed, append-only, guard tingkat DB."""
import sqlite3

import pytest

import admin_store
import pesanan
import schema_pesanan
import schema_transfer
from pesanan_kit import AKUN_A, AKUN_B, SEKARANG, buat, hitung, operasi, siapkan_db, terapkan
from transfer_kit import ADMIN, berkas, menunggu, sha, siapkan_db_transfer, tagihan, unggah
import pesanan_transfer as tf

WAKTU_UPLOAD = "2026-11-18T12:00:00"


def dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def struktur_pesanan(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name GLOB 'pesanan_*' "
            "ORDER BY type,name"))


@pytest.fixture
def db(tmp_path):
    return siapkan_db_transfer(tmp_path)


def test_absent_sah_dan_tidak_dipasang_oleh_migrasi_pesanan(tmp_path):
    path = siapkan_db(tmp_path)
    with admin_store.buka_baca(path) as kon:
        assert schema_transfer.validasi(kon) is False
        assert not schema_transfer.struktur(kon)
    with pytest.raises(admin_store.StoreBelumSiap):
        with tf.buka(path):
            pass


def test_migrasi_idempoten_user_version_tetap_dan_tabel_lengkap(tmp_path):
    path = siapkan_db(tmp_path)
    with sqlite3.connect(path) as kon:
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
    schema_transfer.migrasikan(path)
    pertama = dump(path)
    schema_transfer.migrasikan(path)
    admin_store.siapkan(path, sekarang=99)
    assert dump(path) == pertama
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert schema_transfer.validasi(kon) is True
        assert {r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'transfer_*'")
        } == set(schema_transfer.TABEL)
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()


def test_migrasi_dari_pesanan_v1_terisi_tidak_mengubah_satu_baris_v1(tmp_path):
    path = siapkan_db(tmp_path)
    with pesanan.buka(path, tulis_data=True) as kon:
        order = buat(kon, 1)
        terapkan(kon, order, 1)
        pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kebijakan", SEKARANG)
    sebelum = dump(path)
    struktur_lama = struktur_pesanan(path)
    schema_transfer.migrasikan(path)
    sesudah = dump(path)
    assert struktur_pesanan(path) == struktur_lama
    isi_v1 = [b for b in sebelum if "INSERT INTO \"pesanan_" in b]
    assert isi_v1 and all(b in sesudah for b in isi_v1)
    with pesanan.buka(path) as kon:
        assert schema_pesanan.validasi(kon) is True
        assert pesanan.status_order(kon, order["order_id"], AKUN_A, SEKARANG)["status"] == "direfund"


def test_namespace_baru_tidak_cocok_glob_pesanan_agar_validasi_v1_utuh(db):
    with sqlite3.connect(db) as kon:
        assert not kon.execute(
            "SELECT 1 FROM sqlite_master WHERE tbl_name GLOB 'pesanan_*' AND name GLOB 'transfer_*'"
        ).fetchall()
        assert kon.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE tbl_name GLOB 'transfer_*'").fetchone()[0] > 0
        assert schema_pesanan.validasi(kon) is True


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER transfer_refund_tolak_update",
    "DROP TRIGGER transfer_lunas_nominal",
    "DROP TRIGGER transfer_verifikasi_satu_setuju",
])
def test_skema_parsial_atau_berbeda_ditolak_fail_closed(db, rusak):
    with sqlite3.connect(db) as kon:
        kon.execute(rusak)
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(db):
            pass
    with pytest.raises(admin_store.StoreBelumSiap):
        with tf.buka(db, tulis_data=True):
            pass
    with pytest.raises(ValueError):
        with sqlite3.connect(db) as kon:
            schema_transfer.validasi(kon)


def test_tabel_hilang_sebagian_ditolak(db):
    with sqlite3.connect(db) as kon:
        kon.execute("PRAGMA foreign_keys=OFF")
        for trg in [r[0] for r in kon.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='transfer_refund'")]:
            kon.execute("DROP TRIGGER %s" % trg)
        kon.execute("DROP TABLE transfer_refund")
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(db):
            pass


def test_transfer_tanpa_pesanan_ditolak_dan_migrasi_butuh_pesanan(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    with pytest.raises(admin_store.StoreBelumSiap):
        schema_transfer.migrasikan(path)
    with sqlite3.connect(path) as kon:
        kon.execute("PRAGMA foreign_keys=OFF")
        kon.executescript(schema_transfer.DDL)
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(path):
            pass


def _isi_semua(kon):
    """Satu baris di setiap tabel transfer_* (tagihan→bukti→verifikasi→lunas→refund→hapus)."""
    order, _ = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, WAKTU_UPLOAD)
    tf.catat_refund_transfer(kon, order["order_id"], operasi(5), ADMIN, "kebijakan", WAKTU_UPLOAD)
    kon.execute("INSERT INTO transfer_bukti_hapus VALUES(1,?)", ("2026-12-30T00:00:00",))
    kon.commit()


@pytest.mark.parametrize("tabel", schema_transfer.TABEL)
@pytest.mark.parametrize("aksi,sql", [
    ("update", "UPDATE {t} SET dibuat='2030-01-01T00:00:00'"),
    ("delete", "DELETE FROM {t}"),
])
def test_tabel_transfer_tolak_update_dan_delete(db, tabel, aksi, sql):
    kolom_waktu = {"transfer_bukti": "diunggah", "transfer_bukti_hapus": "dihapus"}
    pernyataan = sql.format(t=tabel).replace("dibuat", kolom_waktu.get(tabel, "dibuat"))
    with pesanan.buka(db, tulis_data=True) as kon:
        _isi_semua(kon)
        assert hitung(kon, tabel) >= 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            kon.execute(pernyataan)
        kon.rollback()
        assert hitung(kon, tabel) >= 1


def test_insert_or_replace_ditolak_pada_semua_tabel_dan_isi_tak_berubah(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        _isi_semua(kon)
        sebelum = dump(db)
        for tabel in schema_transfer.TABEL:
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute("INSERT OR REPLACE INTO %s SELECT * FROM %s" % (tabel, tabel))
        kon.rollback()
    assert dump(db) == sebelum


def test_replace_guard_menjawab_duplikat_pada_tagihan_dan_bukti_id_eksplisit(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        menunggu(kon, 1)
        for tabel in ("transfer_tagihan", "transfer_bukti"):
            with pytest.raises(sqlite3.IntegrityError, match="duplikat"):
                kon.execute("INSERT OR REPLACE INTO %s SELECT * FROM %s" % (tabel, tabel))
        kon.rollback()


def test_nominal_tagihan_wajib_rupiah_ditambah_kode_di_tingkat_db(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order = buat(kon, 1)
        with pytest.raises(sqlite3.IntegrityError, match="nominal"):
            kon.execute("INSERT INTO transfer_tagihan VALUES(?,1,7,49000,?)",
                        (order["order_id"], SEKARANG))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO transfer_tagihan VALUES(?,1,1000,50000,?)",
                        (order["order_id"], SEKARANG))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO transfer_tagihan VALUES(?,1,0,49000,?)",
                        (order["order_id"], SEKARANG))
        kon.execute("INSERT INTO transfer_tagihan VALUES(?,1,7,49007,?)",
                    (order["order_id"], SEKARANG))
        kon.rollback()


def _sisip_bukti(kon, order_id, n, *, akun=AKUN_A, urutan=1, waktu=WAKTU_UPLOAD, mime="image/png",
                 ukuran=10, sha_hex=None):
    kon.execute("INSERT INTO transfer_bukti(order_id,urutan,berkas,mime,ukuran,sha256,"
                "diunggah_oleh,diunggah) VALUES(?,?,?,?,?,?,?,?)",
                (order_id, urutan, berkas(n), mime, ukuran, sha_hex or sha(n), akun, waktu))


def test_guard_bukti_di_tingkat_db(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order, _ = tagihan(kon, 1)
        oid = order["order_id"]
        for n, kwargs in enumerate((
                dict(akun=AKUN_B),                       # bukan pemilik order
                dict(waktu="2026-11-19T10:00:00"),       # tepat di batas kedaluwarsa jendela
                dict(mime="image/gif"), dict(ukuran=0), dict(ukuran=5 * 1024 * 1024 + 1),
                dict(sha_hex="zz" * 32)), start=20):
            with pytest.raises(sqlite3.IntegrityError):
                _sisip_bukti(kon, oid, n, **kwargs)
        for n in range(1, 6):
            _sisip_bukti(kon, oid, n)
        with pytest.raises(sqlite3.IntegrityError, match="batas"):
            _sisip_bukti(kon, oid, 6)
        with pytest.raises(sqlite3.IntegrityError):
            _sisip_bukti(kon, oid, 1)    # nama berkas tersimpan harus unik
        kon.rollback()


def _sisip_verifikasi(kon, order_id, *, keputusan="setuju", alasan=None, hingga, urutan=1):
    return kon.execute("INSERT INTO transfer_verifikasi(order_id,urutan,keputusan,admin_id,alasan,"
                       "bukti_hingga_id,dibuat) VALUES(?,?,?,?,?,?,?)",
                       (order_id, urutan, keputusan, ADMIN, alasan, hingga, WAKTU_UPLOAD))


def test_guard_verifikasi_di_tingkat_db(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order, _ = menunggu(kon, 1)
        oid = order["order_id"]
        with pytest.raises(sqlite3.IntegrityError):      # tolak wajib alasan
            _sisip_verifikasi(kon, oid, keputusan="tolak", hingga=1)
        with pytest.raises(sqlite3.IntegrityError):      # setuju tak boleh beralasan
            _sisip_verifikasi(kon, oid, alasan="x", hingga=1)
        with pytest.raises(sqlite3.IntegrityError):      # keputusan tanpa bukti terbaru
            _sisip_verifikasi(kon, oid, hingga=2)
        with pytest.raises(sqlite3.IntegrityError):      # alasan kepanjangan
            _sisip_verifikasi(kon, oid, keputusan="tolak", alasan="x" * 201, hingga=1)
        _sisip_verifikasi(kon, oid, keputusan="tolak", alasan="buram", hingga=1)
        with pytest.raises(sqlite3.IntegrityError):      # tanpa bukti baru sesudah keputusan
            _sisip_verifikasi(kon, oid, keputusan="tolak", alasan="lagi", hingga=1)
        _sisip_bukti(kon, oid, 2)
        _sisip_verifikasi(kon, oid, hingga=2)
        _sisip_bukti(kon, oid, 3)
        with pytest.raises(sqlite3.IntegrityError, match="setuju"):
            _sisip_verifikasi(kon, oid, keputusan="tolak", alasan="susulan", hingga=3)
        kon.rollback()


def test_guard_lunas_dan_hapus_di_tingkat_db(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order, _ = menunggu(kon, 1)
        oid = order["order_id"]
        with pytest.raises(sqlite3.IntegrityError, match="belum"):
            kon.execute("INSERT INTO transfer_bukti_hapus VALUES(1,?)", (WAKTU_UPLOAD,))
        with pytest.raises(sqlite3.IntegrityError):      # lunas tanpa verifikasi setuju
            kon.execute("INSERT INTO transfer_lunas VALUES(?,1,49000,?)", (oid, WAKTU_UPLOAD))
        _sisip_verifikasi(kon, oid, hingga=1)
        with pytest.raises(sqlite3.IntegrityError, match="tidak cocok"):
            kon.execute("INSERT INTO transfer_lunas VALUES(?,1,48000,?)", (oid, WAKTU_UPLOAD))
        kon.execute("INSERT INTO transfer_lunas VALUES(?,1,49000,?)", (oid, WAKTU_UPLOAD))
        kon.rollback()


def test_lunas_transfer_ditolak_bila_order_sudah_punya_receipt_midtrans(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order, _ = menunggu(kon, 1)
        terapkan(kon, order, 1)
        _sisip_verifikasi(kon, order["order_id"], hingga=1)
        with pytest.raises(sqlite3.IntegrityError, match="receipt"):
            kon.execute("INSERT INTO transfer_lunas VALUES(?,1,49000,?)",
                        (order["order_id"], WAKTU_UPLOAD))
        kon.rollback()


def test_pesanan_midtrans_tetap_jalan_dengan_namespace_transfer_terpasang(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order = buat(kon, 1)
        hasil = terapkan(kon, order, 1)
        assert hasil["status"] == "sudah_dibayar" and hasil["receipt"] == "lunas"

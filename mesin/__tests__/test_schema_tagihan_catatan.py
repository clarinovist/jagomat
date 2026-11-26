"""Skema `tagihan_catatan` (batal/pulih tagihan): DDL terpasang persis, validasi, dan trigger append-only serta aturan batal/pulih.

Tiap sisipan mentah melanggar tepat satu aturan agar pesan trigger yang diasersi adalah aturan yang dimaksud.
"""
import sqlite3

import pytest

import admin_store_core
import kelas_kit as kk
import pesanan
import schema_tagihan_catatan as stc
from purna_kit import siapkan_db_purna
from tagihan_kit import db_tagihan, jumlah_catatan, kon_tagihan, semua_catatan, sisip_catatan  # noqa: F401

NAMA_OBJEK = {
    "tagihan_catatan", "idx_tagihan_catatan_order",
    "tagihan_catatan_tolak_update", "tagihan_catatan_tolak_delete", "tagihan_catatan_tolak_replace",
    "tagihan_catatan_batal_bukti", "tagihan_catatan_batal_lunas", "tagihan_catatan_batal_ganda",
    "tagihan_catatan_batal_jendela", "tagihan_catatan_pulih_tanpa_batal", "tagihan_catatan_pulih_jendela",
}


def _objek(path):
    with pesanan.buka(path) as kon:
        return {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE tbl_name GLOB 'tagihan_*'")}


def _harus_tolak(kon, pesan, sql, params):
    with pytest.raises(sqlite3.IntegrityError, match=pesan):
        kon.execute(sql, params)


def _order_tanpa_bukti(kon):
    return kk.tagih(kon, 1, "mini").order_id


# --- pemasangan dan validasi -----------------------------------------------------------------

def test_belum_dimigrasikan_validasi_false_dan_tanpa_objek(tmp_path):
    path = kk.siapkan_db_kelas(tmp_path)
    with pesanan.buka(path) as kon:
        assert stc.terpasang(kon) is False
        assert stc.validasi(kon) is False
        assert stc.struktur(kon) == ()


def test_migrasi_memasang_objek_persis_dan_idempoten(db_tagihan):
    assert _objek(db_tagihan) == NAMA_OBJEK
    with pesanan.buka(db_tagihan) as kon:
        struktur_awal = stc.struktur(kon)
    stc.migrasikan(db_tagihan)
    with pesanan.buka(db_tagihan) as kon:
        assert stc.struktur(kon) == struktur_awal
        assert stc.validasi(kon) is True and stc.terpasang(kon) is True


def test_migrasi_menolak_bila_kelas_belum_dipasang(tmp_path):
    path = siapkan_db_purna(tmp_path)
    with pytest.raises(admin_store_core.StoreBelumSiap):
        stc.migrasikan(path)
    assert _objek(path) == set()


def test_validasi_menolak_tabel_parsial(db_tagihan):
    with pesanan.buka(db_tagihan, tulis_data=True) as kon:
        kon.execute("DROP TRIGGER tagihan_catatan_batal_bukti")
        kon.commit()
        with pytest.raises(ValueError):
            stc.validasi(kon)


# --- append-only dan replace-guard -----------------------------------------------------------

def test_update_dan_delete_catatan_ditolak(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    id_catatan = sisip_catatan(kon_tagihan, oid, "batal")
    _harus_tolak(kon_tagihan, "catatan tagihan immutable", "UPDATE tagihan_catatan SET aksi='pulih' WHERE id=?",
                 (id_catatan,))
    _harus_tolak(kon_tagihan, "catatan tagihan immutable", "DELETE FROM tagihan_catatan WHERE id=?", (id_catatan,))
    assert jumlah_catatan(kon_tagihan) == 1


def test_insert_or_replace_pada_id_yang_sama_ditolak(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    sisip_catatan(kon_tagihan, oid, "batal", id_catatan=1)
    # 'pulih' setelah 'batal' dan dalam jendela akan diterima aturan lain; yang menolak hanya replace-guard.
    with pytest.raises(sqlite3.IntegrityError, match="catatan tagihan duplikat"):
        sisip_catatan(kon_tagihan, oid, "pulih", id_catatan=1, ganti=True)
    assert semua_catatan(kon_tagihan)[0][2] == "batal"


# --- aturan batal -----------------------------------------------------------------------------

def test_batal_ditolak_bila_tagihan_sudah_punya_bukti(kon_tagihan):
    tagihan = kk.tagih(kon_tagihan, 1, "mini")
    kk.unggah(kon_tagihan, 1, "mini")
    _harus_tolak(kon_tagihan, "batal ditolak: tagihan sudah punya bukti",
                 "INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)",
                 (tagihan.order_id, "batal", kk.KINI))
    assert jumlah_catatan(kon_tagihan) == 0


def test_batal_ditolak_bila_tagihan_sudah_lunas(kon_tagihan):
    tagihan = kk.lunas(kon_tagihan, 1, "mini")
    _harus_tolak(kon_tagihan, "batal ditolak",
                 "INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)",
                 (tagihan.order_id, "batal", kk.KINI))
    assert jumlah_catatan(kon_tagihan) == 0


def test_batal_ganda_ditolak(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    sisip_catatan(kon_tagihan, oid, "batal")
    _harus_tolak(kon_tagihan, "batal ditolak: tagihan sudah dibatalkan",
                 "INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)", (oid, "batal", kk.KINI))


def test_batal_ditolak_setelah_jendela_bayar_lewat(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    _harus_tolak(kon_tagihan, "batal ditolak: jendela bayar sudah lewat",
                 "INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)",
                 (oid, "batal", kk.SESUDAH_JENDELA))


# --- aturan pulih -----------------------------------------------------------------------------

def test_pulih_ditolak_bila_tidak_ada_batal(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    _harus_tolak(kon_tagihan, "pulih ditolak: tagihan tidak sedang dibatalkan",
                 "INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)", (oid, "pulih", kk.KINI))


def test_pulih_ditolak_setelah_jendela_bayar_lewat(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    sisip_catatan(kon_tagihan, oid, "batal")
    _harus_tolak(kon_tagihan, "pulih ditolak: jendela bayar sudah lewat",
                 "INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)",
                 (oid, "pulih", kk.SESUDAH_JENDELA))


def test_urutan_batal_pulih_batal_diterima_dan_terakhir_menentukan(kon_tagihan):
    oid = _order_tanpa_bukti(kon_tagihan)
    sisip_catatan(kon_tagihan, oid, "batal")
    sisip_catatan(kon_tagihan, oid, "pulih")
    sisip_catatan(kon_tagihan, oid, "batal")
    assert [r[2] for r in semua_catatan(kon_tagihan)] == ["batal", "pulih", "batal"]

"""Skema jadwal Paket Belajar: opt-in, guard DDL, dan trigger kuota/paket/identitas pada DB sintetis."""
import sqlite3

import pytest

import admin_store
import admin_store_core
import jadwal_dasar as jd
import kelas_kit
import schema_jadwal
import schema_kelas


def _db(tmp_path, *, kelas=True):
    path = tmp_path / "admin-control.db"
    if kelas:
        path = kelas_kit.siapkan_db_kelas(tmp_path)
    else:
        admin_store.siapkan(path, sekarang=1)
    return path


def _status(path):
    with admin_store.buka_baca(path) as kon:
        return schema_jadwal.validasi(kon)


def _dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def test_absen_sah_lalu_migrasi_idempoten_tanpa_bump_versi(tmp_path):
    path = _db(tmp_path)
    assert _status(path) is False
    versi = sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0]
    schema_jadwal.migrasikan(path)
    assert _status(path) is True
    pertama = _dump(path)
    schema_jadwal.migrasikan(path)
    assert _dump(path) == pertama
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone()[0] == versi


def test_migrasi_wajib_kelas_dan_tidak_mengubah_tanpa_prasyarat(tmp_path):
    path = _db(tmp_path, kelas=False)
    sebelum = _dump(path)
    with pytest.raises(admin_store_core.StoreBelumSiap):
        schema_jadwal.migrasikan(path)
    assert _dump(path) == sebelum


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER jadwal_penempatan_kuota",
    "DROP TRIGGER jadwal_pertemuan_paket",
    "DROP INDEX idx_jadwal_pertemuan_order",
])
def test_struktur_parsial_ditolak(tmp_path, rusak):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with sqlite3.connect(path) as kon:
        kon.execute(rusak)
    with pytest.raises(ValueError):
        _status(path)


def test_objek_liar_ditolak(tmp_path):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE jadwal_liar(x)")
    with pytest.raises(ValueError):
        _status(path)


def test_kelas_tetap_valid_setelah_jadwal_ditambah(tmp_path):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with admin_store.buka_baca(path) as kon:
        assert schema_kelas.validasi(kon) is True


def _order(kon, n, siswa, paket="mini"):
    oid = kelas_kit.sisip_order(kon, n, siswa=siswa, paket=paket)
    kelas_kit.sisip_tagihan(kon, oid)
    return oid


def _group(kon, *, kuota=5):
    kid = jd.id_kelompok_baru()
    kini = "2026-11-20T09:00:00"
    kon.execute("INSERT INTO jadwal_kelompok(id,paket,nama,lokasi,guru_id,kuota,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (kid, "mini", "Mini", "Ruang", "akun_" + "9" * 32, kuota, kini, kini, "admin", "admin"))
    return kid


def _tempat(kon, oid, kid):
    kini = "2026-11-20T09:00:00"
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)", (oid, kid, kini, kini, "admin", "admin"))


def test_trigger_kuota_menolak_anggota_berlebih(tmp_path):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with kelas_kit.pesanan.buka(path, tulis_data=True) as kon:
        kid = _group(kon, kuota=2)
        for n in (1, 2):
            _tempat(kon, _order(kon, n, n), kid)
        with pytest.raises(sqlite3.IntegrityError, match="kelompok penuh"):
            _tempat(kon, _order(kon, 3, 3), kid)


def test_trigger_paket_dan_satu_penempatan_per_anak(tmp_path):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with kelas_kit.pesanan.buka(path, tulis_data=True) as kon:
        kid = _group(kon)
        privat = _order(kon, 1, 1, paket="private")
        with pytest.raises(sqlite3.IntegrityError, match="tidak cocok"):
            _tempat(kon, privat, kid)
        _tempat(kon, _order(kon, 2, 2), kid)
        # anak yang sama tidak bisa dua penempatan: private dulu, lalu Mini di kelompok lain
        priv5 = _order(kon, 5, 5, paket="private")
        kini = "2026-11-20T09:00:00"
        kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                    "dibuat_oleh,diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                    (priv5, "akun_" + "8" * 32, "Online", kini, kini, "admin", "admin"))
        kid2 = _group(kon)
        with pytest.raises(sqlite3.IntegrityError, match="sudah punya penempatan"):
            _tempat(kon, _order(kon, 6, 5), kid2)


def test_trigger_kuota_tidak_boleh_diturunkan_dan_identitas_tetap(tmp_path):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with kelas_kit.pesanan.buka(path, tulis_data=True) as kon:
        kid = _group(kon, kuota=2)
        _tempat(kon, _order(kon, 1, 1), kid)
        _tempat(kon, _order(kon, 2, 2), kid)
        with pytest.raises(sqlite3.IntegrityError, match="kuota"):
            kon.execute("UPDATE jadwal_kelompok SET kuota=1 WHERE id=?", (kid,))
        kon.execute("INSERT INTO jadwal_pertemuan(kelompok_id,ke,mulai,menit,dibatalkan,diubah,diubah_oleh) "
                    "VALUES(?,?,?,?,0,?,?)", (kid, 1, "2026-11-25T02:00:00", 60,
                                              "2026-11-20T09:00:00", "admin"))
        with pytest.raises(sqlite3.IntegrityError, match="identitas"):
            kon.execute("UPDATE jadwal_pertemuan SET ke=2 WHERE kelompok_id=?", (kid,))

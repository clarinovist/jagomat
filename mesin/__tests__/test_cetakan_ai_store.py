"""Kuota harian + audit permintaan draf AI (`cetakan_ai_store`): batas 20/hari WIB, atomik, fail-closed.

Data SINTETIS; DB selalu di tmp_path. Waktu disuntik lewat parameter `sekarang`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import sqlite3
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cetakan_ai_store as ks  # noqa: E402
from cetakan_ai_kit import impor_berkas, modul_mesin_terimpor  # noqa: E402

PELAKU = "akun-admin-sintetis"
SEKARANG = datetime(2026, 11, 20, 3, 0, 0, tzinfo=timezone.utc)  # 10.00 WIB
AKHIR_HARI_WIB = datetime(2026, 11, 20, 16, 59, 59, tzinfo=timezone.utc)  # 23.59.59 WIB
AWAL_HARI_BARU_WIB = datetime(2026, 11, 20, 17, 0, 0, tzinfo=timezone.utc)  # 00.00.00 WIB hari berikutnya


@pytest.fixture()
def db(tmp_path):
    return tmp_path / "cetakan_ai.db"


def pakai(db, jumlah, waktu=SEKARANG):
    return [ks.reservasi(2, 3, PELAKU, sekarang=waktu, path=db) for _ in range(jumlah)]


def baris(db, sql="SELECT * FROM permintaan ORDER BY id"):
    with sqlite3.connect(db) as kon:
        kon.row_factory = sqlite3.Row
        return kon.execute(sql).fetchall()


# --- reservasi dan kuota ---------------------------------------------------------------------

def test_reservasi_membuat_berkas_privat_wal_dan_baris_berjalan(db):
    id_p = ks.reservasi(2, 3, PELAKU, sekarang=SEKARANG, path=db)
    assert id_p == 1 and stat.S_IMODE(os.stat(db).st_mode) == 0o600
    r = baris(db)[0]
    assert (r["kelas"], r["bab"], r["actor_id"], r["status"], r["jumlah_draf"], r["hasil_json"]) == (
        2, 3, PELAKU, "berjalan", 0, "{}")
    assert r["hari_wib"] == "2026-11-20" and r["dibuat"] == "2026-11-20T03:00:00+00:00"
    with sqlite3.connect(db) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == ks.VERSI_SKEMA == 1
        assert kon.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_batas_harian_dua_puluh_dan_reservasi_ke_21_kuota_habis(db):
    assert ks.BATAS_HARIAN == 20
    assert pakai(db, 20) == list(range(1, 21))
    with pytest.raises(ks.KuotaHabis):
        ks.reservasi(2, 3, PELAKU, sekarang=SEKARANG, path=db)
    assert len(baris(db)) == 20  # penolakan tidak menyisipkan baris


def test_sisa_hari_ini_menghitung_semua_status_termasuk_gagal(db):
    ids = pakai(db, 3)
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) == 17
    ks.selesaikan(ids[0], "gagal", 0, ditolak=["AI mati"], path=db)
    ks.selesaikan(ids[1], "selesai", 1, draf=[7], path=db)
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) == 17  # slot tetap terpakai walau gagal


def test_sisa_penuh_bila_berkas_belum_ada_dan_tak_membuat_berkas(db):
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) == 20 and not db.exists()
    assert ks.ambil(1, path=db) is None and not db.exists()


def test_sisa_tak_pernah_negatif_walau_baris_melebihi_batas(db):
    pakai(db, 20)
    with sqlite3.connect(db) as kon:
        for _ in range(3):
            kon.execute("INSERT INTO permintaan(kelas, bab, actor_id, dibuat, hari_wib, status) "
                        "VALUES (2, 3, 'x', 'y', '2026-11-20', 'berjalan')")
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) == 0


def test_batas_hari_memakai_wib_bukan_utc(db):
    pakai(db, 20, AKHIR_HARI_WIB)
    with pytest.raises(ks.KuotaHabis):
        ks.reservasi(2, 3, PELAKU, sekarang=AKHIR_HARI_WIB, path=db)
    assert ks.sisa_hari_ini(sekarang=AKHIR_HARI_WIB, path=db) == 0
    assert ks.sisa_hari_ini(sekarang=AWAL_HARI_BARU_WIB, path=db) == 20
    assert ks.reservasi(2, 3, PELAKU, sekarang=AWAL_HARI_BARU_WIB, path=db) == 21
    assert baris(db)[-1]["hari_wib"] == "2026-11-21"


def test_pukul_2330_utc_sudah_hari_wib_berikutnya():
    assert ks.hari_wib(datetime(2026, 11, 20, 23, 30, tzinfo=timezone.utc)) == "2026-11-21"
    assert ks.hari_wib(datetime(2026, 11, 20, 16, 30, tzinfo=timezone.utc)) == "2026-11-20"
    assert ks.hari_wib(datetime(2026, 12, 31, 17, 0, tzinfo=timezone.utc)) == "2027-01-01"


def test_waktu_tanpa_zona_ditolak(db):
    with pytest.raises(ValueError):
        ks.reservasi(2, 3, PELAKU, sekarang=datetime(2026, 11, 20, 3, 0), path=db)
    with pytest.raises(ValueError):
        ks.sisa_hari_ini(sekarang=datetime(2026, 11, 20, 3, 0), path=db)


def test_kuota_global_semua_admin_berbagi_batas(db):
    for no in range(20):
        ks.reservasi(2, 3, "admin-%d" % (no % 4), sekarang=SEKARANG, path=db)
    with pytest.raises(ks.KuotaHabis):
        ks.reservasi(2, 3, "admin-baru", sekarang=SEKARANG, path=db)


@pytest.mark.parametrize("pelaku", ["", "  ", None, 5, "x" * 101])
def test_pelaku_tak_sah_ditolak_tanpa_berkas(db, pelaku):
    with pytest.raises(ValueError):
        ks.reservasi(2, 3, pelaku, sekarang=SEKARANG, path=db)
    assert not db.exists()


def test_reservasi_serentak_atomik_tepat_dua_puluh_lolos(db):
    pakai(db, 1)  # berkas dan skema sudah ada

    def coba(_):
        try:
            return ks.reservasi(2, 3, PELAKU, sekarang=SEKARANG, path=db)
        except ks.KuotaHabis:
            return None

    with ThreadPoolExecutor(max_workers=24) as kolam:
        hasil = list(kolam.map(coba, range(40)))
    lolos = [h for h in hasil if h is not None]
    assert len(lolos) == 19 and len(set(lolos)) == 19 and len(baris(db)) == 20


# --- selesaikan dan ambil ---------------------------------------------------------------------

def test_selesaikan_mencatat_hasil_ringkas_dan_dipotong(db):
    id_p = pakai(db, 1)[0]
    ks.selesaikan(id_p, "selesai", 2, draf=[4, 5, 6, 7], ditolak=["a" * 250, "b", "c", "d"], path=db)
    p = ks.ambil(id_p, path=db)
    assert (p.status, p.jumlah_draf, p.kelas, p.bab, p.actor_id, p.hari_wib) == ("selesai", 2, 2, 3, PELAKU, "2026-11-20")
    assert p.draf == (4, 5, 6) and p.ditolak == ("a" * 200, "b", "c")


def test_selesaikan_dua_kali_atau_id_tak_ada_value_error(db):
    id_p = pakai(db, 1)[0]
    ks.selesaikan(id_p, "gagal", 0, ditolak=["x"], path=db)
    with pytest.raises(ValueError):
        ks.selesaikan(id_p, "selesai", 0, path=db)
    with pytest.raises(ValueError):
        ks.selesaikan(99, "selesai", 0, path=db)
    assert ks.ambil(id_p, path=db).status == "gagal"


@pytest.mark.parametrize("status,jumlah,draf", [("berjalan", 0, ()), ("lain", 0, ()), ("selesai", -1, ()),
                                                 ("selesai", True, ()), ("selesai", 0, (0,)), ("selesai", 0, ("1",))])
def test_selesaikan_masukan_tak_sah(db, status, jumlah, draf):
    id_p = pakai(db, 1)[0]
    with pytest.raises(ValueError):
        ks.selesaikan(id_p, status, jumlah, draf=draf, path=db)
    assert ks.ambil(id_p, path=db).status == "berjalan"


def test_selesaikan_tanpa_berkas_galat_kuota_dan_tak_membuat_berkas(db):
    with pytest.raises(ks.GalatKuota):
        ks.selesaikan(1, "selesai", 0, path=db)
    assert not db.exists()


def test_ambil_menolak_id_tak_sah_dan_menoleransi_hasil_rusak(db):
    id_p = pakai(db, 1)[0]
    for sembarang in (0, -1, "1", None, True):
        assert ks.ambil(sembarang, path=db) is None
    assert ks.ambil(999, path=db) is None
    for rusak in ("bukan json", "[]", '{"draf": "x", "ditolak": []}', '{"draf": [0], "ditolak": []}', '{"draf": []}'):
        with sqlite3.connect(db) as kon:
            kon.execute("UPDATE permintaan SET hasil_json = ?", (rusak,))
        p = ks.ambil(id_p, path=db)
        assert p is not None and p.draf == () and p.ditolak == ()


# --- fail-closed -----------------------------------------------------------------------------

SAMPAH = b"bukan sqlite sama sekali"


def _asing_dengan_tabel(db):
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE bukan_milik_kita(x INTEGER)")


def _skema_versi_lain(db):
    with sqlite3.connect(db) as kon:
        kon.execute("PRAGMA user_version = 99")


@pytest.mark.parametrize("buat_rusak", ["sampah", "asing", "versi"])
def test_db_rusak_atau_asing_fail_closed_dan_berkas_tak_berubah(db, buat_rusak):
    if buat_rusak == "sampah":
        db.write_bytes(SAMPAH)
    elif buat_rusak == "asing":
        _asing_dengan_tabel(db)
    else:
        pakai(db, 1)
        _skema_versi_lain(db)
    sebelum = db.read_bytes()
    with pytest.raises(ks.GalatKuota):
        ks.reservasi(2, 3, PELAKU, sekarang=SEKARANG, path=db)
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) is None
    assert ks.ambil(1, path=db) is None
    with pytest.raises(ks.GalatKuota):
        ks.selesaikan(1, "selesai", 0, path=db)
    assert db.read_bytes() == sebelum


def test_berkas_kosong_nol_byte_dianggap_belum_ada_pemakaian_lalu_diberi_skema(db):
    db.write_bytes(b"")
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) == 20
    assert ks.reservasi(2, 3, PELAKU, sekarang=SEKARANG, path=db) == 1
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) == 19


def test_tabel_hilang_dari_db_berversi_sama_fail_closed(db):
    pakai(db, 1)
    with sqlite3.connect(db) as kon:
        kon.execute("DROP TABLE permintaan")
    assert ks.sisa_hari_ini(sekarang=SEKARANG, path=db) is None


def test_path_dari_env_dibaca_saat_dipanggil(tmp_path, monkeypatch):
    monkeypatch.setenv(ks.ENV_BERKAS_DB, str(tmp_path / "lain.db"))
    assert ks.reservasi(2, 3, PELAKU, sekarang=SEKARANG) == 1 and (tmp_path / "lain.db").exists()


def test_env_dan_berkas_bawaan_bukan_cetakan_db():
    assert ks.ENV_BERKAS_DB == "CETAKAN_AI_BERKAS_DB" and ks.BERKAS_BAWAAN == "/data/cetakan_ai.db"
    import cetakan_store
    assert ks.BERKAS_BAWAAN != cetakan_store.BERKAS_BAWAAN and ks.ENV_BERKAS_DB != cetakan_store.ENV_BERKAS_DB


# --- penutupan impor -------------------------------------------------------------------------

def test_store_hanya_menarik_jurnal_wal_dari_mesin():
    assert modul_mesin_terimpor("import cetakan_ai_store") == {"cetakan_ai_store", "jurnal_wal"}


def test_store_hanya_mengimpor_stdlib_dan_jurnal_wal():
    assert impor_berkas("cetakan_ai_store.py") == {
        "__future__", "contextlib", "dataclasses", "datetime", "json", "logging", "os", "pathlib", "sqlite3",
        "typing", "jurnal_wal"}

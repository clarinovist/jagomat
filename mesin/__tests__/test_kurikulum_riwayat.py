"""Tes `kurikulum_override.riwayat_cp`: baca-saja audit CP per grup, aman terhadap berkas hilang/rusak."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kurikulum_cp  # noqa: E402
import kurikulum_override as ko  # noqa: E402

KUNCI = ("bilangan-dasar", "nilai_tempat")
LAIN = ("bilangan-dasar", "membandingkan")
BAWAAN = kurikulum_cp.CP_PER_GRUP[KUNCI]


@pytest.fixture(autouse=True)
def _cache_kosong():
    ko.bersihkan_cache()
    yield
    ko.bersihkan_cache()


@pytest.fixture
def db(tmp_path):
    return tmp_path / "kurikulum.db"


def _ubah(db, isi, revisi, *, kunci=KUNCI, actor="adm-1"):
    return ko.ubah_cp(*kunci, isi, actor_id=actor, revisi_diharapkan=revisi, path=db)


def test_berkas_tidak_ada_tuple_kosong_dan_tidak_membuat_berkas(db):
    assert ko.riwayat_cp(*KUNCI, path=db) == ()
    assert not db.exists()


def test_riwayat_terbaru_dulu_dengan_lama_baru_pelaku_dan_hanya_grup_itu(db):
    _ubah(db, (("A.geometri.1", "penuh"),), 0, actor="adm-1")
    _ubah(db, (("A.geometri.4", "sebagian"),), 1, actor="adm-2")
    _ubah(db, (("A.geometri.4", "sebagian"),), 0, kunci=LAIN, actor="adm-3")
    riwayat = ko.riwayat_cp(*KUNCI, path=db)
    assert [r.revisi for r in riwayat] == [2, 1] and [r.actor_id for r in riwayat] == ["adm-2", "adm-1"]
    assert riwayat[1].lama == BAWAAN and riwayat[1].baru == (("A.geometri.1", "penuh"),)
    assert riwayat[0].lama == (("A.geometri.1", "penuh"),)
    assert all(isinstance(r.dibuat, str) and r.dibuat for r in riwayat)


def test_batas_membatasi_jumlah_dan_batas_tak_sah_ditolak(db):
    _ubah(db, (("A.geometri.1", "penuh"),), 0)
    _ubah(db, (("A.geometri.4", "penuh"),), 1)
    assert len(ko.riwayat_cp(*KUNCI, 1, path=db)) == 1
    for batas in (0, -1, ko.BATAS_RIWAYAT_MAKS + 1, True, "10", None):
        with pytest.raises(ValueError):
            ko.riwayat_cp(*KUNCI, batas, path=db)
    with pytest.raises(ValueError):
        ko.riwayat_cp("asing", "grup", path=db)


def test_berkas_rusak_atau_skema_asing_tuple_kosong(db):
    db.write_bytes(b"bukan sqlite")
    assert ko.riwayat_cp(*KUNCI, path=db) == ()
    db.unlink()
    with sqlite3.connect(db) as kon:
        kon.execute("PRAGMA user_version = 99")
    assert ko.riwayat_cp(*KUNCI, path=db) == ()


def test_baris_audit_rusak_dilewati_baris_lain_tetap_tampil(db):
    _ubah(db, (("A.geometri.1", "penuh"),), 0)
    with sqlite3.connect(db) as kon:
        kon.execute(
            "INSERT INTO audit_kurikulum(jenis, kunci, lama, baru, revisi, actor_id, dibuat)"
            " VALUES ('cp', ?, 'bukan json', '[]', 9, 'adm-x', 'sekarang')", ("%s/%s" % KUNCI,))
    riwayat = ko.riwayat_cp(*KUNCI, path=db)
    assert [r.revisi for r in riwayat] == [1]

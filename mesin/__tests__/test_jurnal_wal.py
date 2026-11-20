"""Jurnal SQLite harus WAL setelah siapkan(), bukan `delete`.

Konteks: `PRAGMA journal_mode = WAL` di `schema.SKEMA` dijalankan di dalam
`BEGIN IMMEDIATE`, jadi diabaikan SQLite. Tes ini menjaga agar setiap store
durable benar-benar meninggalkan berkas dalam mode WAL, dan tetap WAL saat
siapkan() dijalankan ulang (startup berulang).
"""
import sqlite3

import pytest

import admin_store
import ai_store
import assistant_schema
import cetakan_store
import database
import feature_switch
import kurikulum_override
import research_store


def _mode(path):
    with sqlite3.connect(path) as kon:
        return kon.execute("PRAGMA journal_mode").fetchone()[0]


KASUS = [
    ("latihan", lambda path: database.siapkan(path)),
    ("admin", lambda path: admin_store.siapkan(path)),
    ("ai", lambda path: ai_store.siapkan(path)),
    ("pendamping", lambda path: assistant_schema.siapkan(path)),
    ("riset", lambda path: research_store.siapkan(path)),
]


@pytest.mark.parametrize("nama,siapkan", KASUS, ids=[k[0] for k in KASUS])
def test_siapkan_mengaktifkan_wal(tmp_path, nama, siapkan):
    path = tmp_path / f"{nama}.db"

    siapkan(path)

    assert _mode(path) == "wal"


@pytest.mark.parametrize("nama,siapkan", KASUS, ids=[k[0] for k in KASUS])
def test_siapkan_ulang_tetap_wal(tmp_path, nama, siapkan):
    path = tmp_path / f"{nama}.db"
    siapkan(path)

    siapkan(path)

    assert _mode(path) == "wal"


def test_ubah_sakelar_membuat_db_wal(tmp_path):
    path = tmp_path / "sakelar.db"
    seed = {nama: False for nama in feature_switch.NAMA_SAKELAR}

    feature_switch.ubah(
        feature_switch.NAMA_SAKELAR[0],
        True,
        actor_id="uji-wal",
        revisi_diharapkan=1,
        seed=seed,
        path=path,
    )

    assert _mode(path) == "wal"


def test_ubah_label_kurikulum_membuat_db_wal(tmp_path):
    path = tmp_path / "kurikulum.db"

    kurikulum_override.ubah_label(
        "pola-bilangan",
        "Pola bilangan (uji)",
        actor_id="uji-wal",
        revisi_diharapkan=0,
        path=path,
    )

    assert _mode(path) == "wal"


def test_buat_draf_cetakan_membuat_db_wal(tmp_path):
    path = tmp_path / "cetakan.db"
    isi = {
        "kelas": 2, "bab": 2, "judul": "Penjumlahan uji WAL",
        "teks": "Ada {a} kelereng dan {b} kelereng. Berapa semuanya?",
        "variabel": {"a": [10, 50], "b": [1, 40]}, "kunci": "a + b",
    }

    cetakan_store.buat_draf(isi, sumber="manual", actor_id="uji-wal", path=path)

    assert _mode(path) == "wal"


def test_cetakan_tolak_db_asing_sebelum_wal(tmp_path):
    path = tmp_path / "cetakan.db"
    with sqlite3.connect(str(path)) as kon:
        kon.execute("CREATE TABLE asing (x INTEGER)")
    isi = {
        "kelas": 2, "bab": 2, "judul": "Penjumlahan uji WAL",
        "teks": "Ada {a} kelereng dan {b} kelereng. Berapa semuanya?",
        "variabel": {"a": [10, 50], "b": [1, 40]}, "kunci": "a + b",
    }

    with pytest.raises(cetakan_store.GalatCetakan):
        cetakan_store.buat_draf(isi, sumber="manual", actor_id="uji-wal", path=path)

    assert _mode(path) != "wal"

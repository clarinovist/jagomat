"""Tes store cetakan (C1): DB terpisah, fail ke kosong, revisi, audit, kelayakan saat setujui, cache.

Semua DB uji di tmp_path dengan data sintetis; kasus "tangan" (baris rusak, user_version asing)
ditanam lewat sqlite3 langsung, bukan lewat API tulis.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import logging
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys

import pytest

MESIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MESIN))

import cetakan_pola  # noqa: E402
import cetakan_store as cs  # noqa: E402


@pytest.fixture(autouse=True)
def _cache_kosong_dan_jam_pulih():
    cs.bersihkan_cache()
    jam_asli = cs._jam
    yield
    cs._jam = jam_asli
    cs.bersihkan_cache()


@pytest.fixture
def db(tmp_path):
    return tmp_path / "cetakan.db"


def isi_sah(**ubah):
    isi = {
        "kelas": 2, "bab": 2, "judul": "Penjumlahan dua angka dalam soal cerita",
        "teks": "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa kelereng {nama} sekarang?",
        "variabel": {"a": [10, 50], "b": [1, 40]}, "nama": True,
        "syarat": ["a + b <= 99"], "kunci": "a + b", "pembahasan": "{a} + {b} = {kunci}",
    }
    isi.update(ubah)
    return isi


def isi_sempit(**ubah):
    """Valid secara skema tetapi gagal uji kelayakan (hanya 5 soal unik)."""
    return isi_sah(variabel={"a": [1, 5]}, teks="{nama} punya {a} apel", syarat=[], kunci="a",
                   pembahasan="", **ubah)


def buat(db, isi=None, *, sumber="manual", actor="admin"):
    return cs.buat_draf(isi if isi is not None else isi_sah(), sumber=sumber, actor_id=actor, path=db)


def baris(db, sql, parameter=()):
    with sqlite3.connect(db) as kon:
        kon.row_factory = sqlite3.Row
        hasil = [dict(b) for b in kon.execute(sql, parameter)]
    kon.close()
    return hasil


def jalankan(db, *sql):
    with sqlite3.connect(db) as kon:
        for s in sql:
            kon.execute(*s) if isinstance(s, tuple) else kon.execute(s)
    kon.close()


def ubah_isi_langsung(db, id_cetakan, isi):
    """Timpa isi_json di balik layar API (simulasi isi berubah antara draf dan persetujuan)."""
    teks = cetakan_pola.ke_json(cetakan_pola.validasi(isi))
    jalankan(db, ("UPDATE cetakan SET isi_json = ? WHERE id = ?", (teks, id_cetakan)))


def db_tangan(db, rows=(), *, versi=1, audit=()):
    """DB v1 tangan TANPA CHECK agar baris rusak bisa ditanam."""
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE cetakan (id INTEGER PRIMARY KEY AUTOINCREMENT, kelas, bab, status,"
                    " sumber, isi_json, revisi, dibuat, diperbarui)")
        kon.execute("CREATE TABLE audit_cetakan (id INTEGER PRIMARY KEY AUTOINCREMENT, cetakan_id,"
                    " aksi, lama, baru, revisi, actor_id, dibuat)")
        kon.executemany("INSERT INTO cetakan(kelas, bab, status, sumber, isi_json, revisi, dibuat, diperbarui)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        kon.executemany("INSERT INTO audit_cetakan(cetakan_id, aksi, lama, baru, revisi, actor_id, dibuat)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)", audit)
        kon.execute(f"PRAGMA user_version = {versi}")
    kon.close()


def json_sah(**ubah):
    return cetakan_pola.ke_json(cetakan_pola.validasi(isi_sah(**ubah)))


def siapkan_aktif(db):
    item = buat(db)
    return cs.setujui(item.id, actor_id="admin", revisi_diharapkan=1, path=db)


# --- berkas tidak ada --------------------------------------------------------

def test_berkas_tidak_ada_semua_baca_kosong_dan_tidak_membuat_berkas(db):
    assert cs.daftar(path=db) == () and cs.ambil(1, path=db) is None
    assert cs.aktif_untuk_bab(2, 2, path=db) == () and cs.riwayat(1, path=db) == ()
    assert not db.exists()


@pytest.mark.parametrize("operasi", ["ubah", "setujui", "nonaktifkan", "aktifkan"])
def test_transisi_pada_berkas_tak_ada_ditolak_tanpa_membuat_berkas(db, operasi):
    panggil = {
        "ubah": lambda: cs.ubah_draf(1, isi_sah(), actor_id="a", revisi_diharapkan=1, path=db),
        "setujui": lambda: cs.setujui(1, actor_id="a", revisi_diharapkan=1, path=db),
        "nonaktifkan": lambda: cs.nonaktifkan(1, actor_id="a", revisi_diharapkan=1, path=db),
        "aktifkan": lambda: cs.aktifkan_kembali(1, actor_id="a", revisi_diharapkan=1, path=db),
    }[operasi]
    with pytest.raises(ValueError, match="tidak ditemukan"):
        panggil()
    assert not db.exists()


def test_path_dari_env_lalu_bawaan(tmp_path, monkeypatch):
    berkas = tmp_path / "dari-env.db"
    monkeypatch.setenv(cs.ENV_BERKAS_DB, str(berkas))
    cs.buat_draf(isi_sah(), sumber="manual", actor_id="admin")
    assert berkas.exists() and len(cs.daftar()) == 1
    assert cs.BERKAS_BAWAAN == "/data/cetakan.db" and cs.ENV_BERKAS_DB == "CETAKAN_BERKAS_DB"


# --- buat / ubah / siklus status ---------------------------------------------

def test_buat_draf_revisi_satu_diaudit_dan_berkas_privat(db):
    item = buat(db, sumber="ai", actor="admin-1")

    assert (item.id, item.status, item.sumber, item.revisi) == (1, "draf", "ai", 1)
    assert (item.kelas, item.bab) == (2, 2) and item.cetakan == cetakan_pola.validasi(isi_sah())
    assert item.dibuat == item.diperbarui
    audit = baris(db, "SELECT * FROM audit_cetakan")
    assert len(audit) == 1
    assert (audit[0]["cetakan_id"], audit[0]["aksi"], audit[0]["lama"], audit[0]["revisi"],
            audit[0]["actor_id"]) == (1, "buat", None, 1, "admin-1")
    assert audit[0]["baru"] == cetakan_pola.ke_json(item.cetakan)
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600
    assert baris(db, "PRAGMA user_version") == [{"user_version": cs.VERSI_SKEMA}]
    assert cs.ambil(1, path=db) == item and cs.daftar(path=db) == (item,)


def test_skema_membuat_tabel_yang_dinamai_tabel_skema(db):
    buat(db)
    tabel = {b["name"] for b in baris(db, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(cs.TABEL_SKEMA) <= tabel and cs.TABEL_SKEMA == ("cetakan", "audit_cetakan")


def test_item_beku(db):
    item = buat(db)
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.status = "aktif"


def test_ubah_draf_menaikkan_revisi_memperbarui_kolom_dan_mengaudit(db):
    awal = buat(db)
    baru = isi_sah(kelas=3, bab=2, judul="Judul baru", kunci="a + b + 1")

    item = cs.ubah_draf(awal.id, baru, actor_id="guru-2", revisi_diharapkan=1, path=db)

    assert item.revisi == 2 and item.status == "draf" and item.cetakan.judul == "Judul baru"
    assert (item.kelas, item.bab) == (3, 2)
    assert baris(db, "SELECT kelas, bab FROM cetakan") == [{"kelas": 3, "bab": 2}]
    audit = baris(db, "SELECT aksi, lama, baru, revisi, actor_id FROM audit_cetakan ORDER BY id")
    assert [a["aksi"] for a in audit] == ["buat", "ubah"]
    assert audit[1]["lama"] == cetakan_pola.ke_json(awal.cetakan) and audit[1]["revisi"] == 2
    assert audit[1]["baru"] == cetakan_pola.ke_json(item.cetakan) and audit[1]["actor_id"] == "guru-2"


def test_siklus_penuh_status_revisi_dan_audit(db):
    item = buat(db)
    item = cs.setujui(item.id, actor_id="a1", revisi_diharapkan=1, path=db)
    assert (item.status, item.revisi) == ("aktif", 2)
    assert cs.aktif_untuk_bab(2, 2, path=db) == (item,)
    item = cs.nonaktifkan(item.id, actor_id="a2", revisi_diharapkan=2, path=db)
    assert (item.status, item.revisi) == ("nonaktif", 3)
    assert cs.aktif_untuk_bab(2, 2, path=db) == ()
    item = cs.aktifkan_kembali(item.id, actor_id="a3", revisi_diharapkan=3, path=db)
    assert (item.status, item.revisi) == ("aktif", 4)
    audit = baris(db, "SELECT aksi, lama, baru, revisi, actor_id FROM audit_cetakan ORDER BY id")
    assert [(a["aksi"], a["lama"], a["baru"], a["revisi"], a["actor_id"]) for a in audit[1:]] == [
        ("setujui", "draf", "aktif", 2, "a1"),
        ("nonaktifkan", "aktif", "nonaktif", 3, "a2"),
        ("aktifkan", "nonaktif", "aktif", 4, "a3"),
    ]
    assert baris(db, "SELECT COUNT(*) AS n FROM cetakan") == [{"n": 1}]  # tidak ada hapus


@pytest.mark.parametrize("status_awal,operasi", [
    ("aktif", "ubah"), ("nonaktif", "ubah"),
    ("aktif", "setujui"), ("nonaktif", "setujui"),
    ("draf", "nonaktifkan"), ("nonaktif", "nonaktifkan"),
    ("draf", "aktifkan"), ("aktif", "aktifkan"),
])
def test_transisi_terlarang_ditolak_tanpa_efek(db, status_awal, operasi):
    item = buat(db)
    revisi = 1
    if status_awal in ("aktif", "nonaktif"):
        item = cs.setujui(item.id, actor_id="a", revisi_diharapkan=revisi, path=db)
        revisi = item.revisi
    if status_awal == "nonaktif":
        item = cs.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=revisi, path=db)
        revisi = item.revisi
    sebelum = (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan"))
    panggil = {
        "ubah": lambda: cs.ubah_draf(item.id, isi_sah(judul="X"), actor_id="a", revisi_diharapkan=revisi, path=db),
        "setujui": lambda: cs.setujui(item.id, actor_id="a", revisi_diharapkan=revisi, path=db),
        "nonaktifkan": lambda: cs.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=revisi, path=db),
        "aktifkan": lambda: cs.aktifkan_kembali(item.id, actor_id="a", revisi_diharapkan=revisi, path=db),
    }[operasi]

    with pytest.raises(ValueError, match="berstatus"):
        panggil()

    assert (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan")) == sebelum


def test_id_tidak_ada_ditolak(db):
    buat(db)
    with pytest.raises(ValueError, match="tidak ditemukan"):
        cs.setujui(99, actor_id="a", revisi_diharapkan=1, path=db)
    with pytest.raises(ValueError, match="tidak ditemukan"):
        cs.ubah_draf(99, isi_sah(), actor_id="a", revisi_diharapkan=1, path=db)


# --- kelayakan saat setujui --------------------------------------------------

def test_setujui_gagal_bila_kelayakan_gagal_tanpa_efek(db):
    item = buat(db, isi_sempit())
    sebelum = (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan"))

    with pytest.raises(ValueError, match="Uji kelayakan gagal"):
        cs.setujui(item.id, actor_id="admin", revisi_diharapkan=1, path=db)

    assert (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan")) == sebelum
    assert cs.ambil(item.id, path=db).status == "draf" and cs.aktif_untuk_bab(2, 2, path=db) == ()


def test_setujui_menguji_isi_tersimpan_bukan_yang_pernah_dilihat(db):
    item = buat(db)                                        # draf baik
    ubah_isi_langsung(db, item.id, isi_sempit())           # isi berubah di balik layar
    cs.bersihkan_cache()
    with pytest.raises(ValueError, match="Uji kelayakan gagal"):
        cs.setujui(item.id, actor_id="admin", revisi_diharapkan=1, path=db)
    assert baris(db, "SELECT status, revisi FROM cetakan") == [{"status": "draf", "revisi": 1}]


def test_aktifkan_kembali_juga_menguji_kelayakan(db):
    item = siapkan_aktif(db)
    item = cs.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=2, path=db)
    ubah_isi_langsung(db, item.id, isi_sempit())
    cs.bersihkan_cache()
    with pytest.raises(ValueError, match="Uji kelayakan gagal"):
        cs.aktifkan_kembali(item.id, actor_id="a", revisi_diharapkan=3, path=db)
    assert baris(db, "SELECT status, revisi FROM cetakan") == [{"status": "nonaktif", "revisi": 3}]


def test_nonaktifkan_tidak_butuh_kelayakan(db):
    item = siapkan_aktif(db)
    ubah_isi_langsung(db, item.id, isi_sempit())           # sudah tak layak, tetap bisa dimatikan
    cs.bersihkan_cache()
    assert cs.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=2, path=db).status == "nonaktif"


# --- revisi ------------------------------------------------------------------

@pytest.mark.parametrize("operasi", ["ubah", "setujui"])
def test_konflik_revisi_pada_draf_digulung_balik(db, operasi):
    item = buat(db)
    sebelum = (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan"))
    panggil = {
        "ubah": lambda: cs.ubah_draf(item.id, isi_sah(judul="Z"), actor_id="a", revisi_diharapkan=5, path=db),
        "setujui": lambda: cs.setujui(item.id, actor_id="a", revisi_diharapkan=5, path=db),
    }[operasi]
    with pytest.raises(cs.KonflikRevisi):
        panggil()
    assert (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan")) == sebelum


@pytest.mark.parametrize("operasi", ["nonaktifkan", "aktifkan"])
def test_konflik_revisi_pada_transisi_aktif_digulung_balik(db, operasi):
    item = siapkan_aktif(db)
    if operasi == "aktifkan":
        item = cs.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=2, path=db)
    sebelum = (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan"))
    fungsi = cs.nonaktifkan if operasi == "nonaktifkan" else cs.aktifkan_kembali
    with pytest.raises(cs.KonflikRevisi):
        fungsi(item.id, actor_id="a", revisi_diharapkan=item.revisi - 1, path=db)
    assert (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan")) == sebelum


def test_klien_basi_tidak_bisa_menimpa_setelah_perubahan_lain(db):
    item = buat(db)
    cs.ubah_draf(item.id, isi_sah(judul="Pertama"), actor_id="a", revisi_diharapkan=1, path=db)
    with pytest.raises(cs.KonflikRevisi):
        cs.ubah_draf(item.id, isi_sah(judul="Basi"), actor_id="b", revisi_diharapkan=1, path=db)
    assert cs.ambil(item.id, path=db).cetakan.judul == "Pertama"


# --- validasi sebelum DB -----------------------------------------------------

def test_isi_tak_sah_ditolak_sebelum_menyentuh_db_dan_tidak_membuat_berkas(db):
    with pytest.raises(ValueError, match="kunci"):
        cs.buat_draf(isi_sah(kunci="a ** 2"), sumber="manual", actor_id="a", path=db)
    assert not db.exists()


def test_ubah_isi_tak_sah_tidak_mengubah_apa_pun(db):
    item = buat(db)
    sebelum = (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan"))
    with pytest.raises(ValueError, match="kunci"):
        cs.ubah_draf(item.id, isi_sah(kunci="__import__('os')"), actor_id="a", revisi_diharapkan=1, path=db)
    assert (baris(db, "SELECT * FROM cetakan"), baris(db, "SELECT * FROM audit_cetakan")) == sebelum


@pytest.mark.parametrize("sumber", ["", "AI", None, "otomatis", 1])
def test_sumber_tak_sah(db, sumber):
    with pytest.raises(ValueError, match="Sumber"):
        cs.buat_draf(isi_sah(), sumber=sumber, actor_id="a", path=db)
    assert not db.exists()


@pytest.mark.parametrize("actor", ["", "   ", None, 5, "x" * 101])
def test_pelaku_tak_sah(db, actor):
    with pytest.raises(ValueError, match="pelaku"):
        cs.buat_draf(isi_sah(), sumber="manual", actor_id=actor, path=db)
    assert not db.exists()


@pytest.mark.parametrize("revisi", [0, -1, True, "1", None, 1.0])
def test_revisi_diharapkan_tak_sah(db, revisi):
    item = buat(db)
    with pytest.raises(ValueError, match="Revisi"):
        cs.setujui(item.id, actor_id="a", revisi_diharapkan=revisi, path=db)


@pytest.mark.parametrize("id_cetakan", [0, -1, True, "1", None])
def test_id_tak_sah(db, id_cetakan):
    with pytest.raises(ValueError, match="Id"):
        cs.ambil(id_cetakan, path=db)
    with pytest.raises(ValueError, match="Id"):
        cs.setujui(id_cetakan, actor_id="a", revisi_diharapkan=1, path=db)


# --- baca: daftar, saring, riwayat -------------------------------------------

def test_daftar_urut_id_dan_penyaringan(db):
    a = buat(db)
    b = buat(db, isi_sah(kelas=3, bab=2))
    c = buat(db, isi_sah(bab=1, teks="{nama} {a} {b}"))
    cs.setujui(b.id, actor_id="a", revisi_diharapkan=1, path=db)
    assert [i.id for i in cs.daftar(path=db)] == [a.id, b.id, c.id]
    assert [i.id for i in cs.daftar(kelas=2, path=db)] == [a.id, c.id]
    assert [i.id for i in cs.daftar(kelas=2, bab=2, path=db)] == [a.id]
    assert [i.id for i in cs.daftar(status="aktif", path=db)] == [b.id]
    assert [i.id for i in cs.aktif_untuk_bab(3, 2, path=db)] == [b.id]
    assert cs.aktif_untuk_bab(2, 2, path=db) == ()
    assert cs.ambil(c.id, path=db).bab == 1 and cs.ambil(999, path=db) is None


def test_riwayat_terbaru_dulu_dan_dibatasi(db):
    item = buat(db)
    cs.ubah_draf(item.id, isi_sah(judul="V2"), actor_id="b", revisi_diharapkan=1, path=db)
    cs.setujui(item.id, actor_id="c", revisi_diharapkan=2, path=db)
    semua = cs.riwayat(item.id, path=db)
    assert [(r.aksi, r.revisi, r.actor_id) for r in semua] == [
        ("setujui", 3, "c"), ("ubah", 2, "b"), ("buat", 1, "admin")]
    assert (semua[0].lama, semua[0].baru) == ("draf", "aktif")
    assert [r.aksi for r in cs.riwayat(item.id, 1, path=db)] == ["setujui"]
    assert cs.riwayat(999, path=db) == ()
    for batas in (0, 51, True, "5"):
        with pytest.raises(ValueError, match="Batas"):
            cs.riwayat(item.id, batas, path=db)


def test_riwayat_baris_audit_rusak_dilewati(db):
    db_tangan(db, audit=[
        (1, "buat", None, "{}", 1, "admin", "2026-01-01"),
        (1, "aneh", None, None, 2, "admin", "2026-01-02"),
        (1, "ubah", "{}", "{}", 0, "admin", "2026-01-03"),
        (1, "ubah", "{}", "{}", 3, None, "2026-01-04"),
        (1, "ubah", "{}", 5, 4, "admin", "2026-01-05"),
    ])
    assert [r.revisi for r in cs.riwayat(1, path=db)] == [1]


# --- baca: fail ke kosong ----------------------------------------------------

def test_db_bukan_sqlite_dibaca_kosong_dan_dicatat(db, caplog):
    db.write_bytes(bytes(range(256)) * 64)
    with caplog.at_level(logging.WARNING, logger=cs.__name__):
        assert cs.daftar(path=db) == () and cs.riwayat(1, path=db) == ()
    assert "dianggap kosong" in caplog.text


def test_user_version_asing_dibaca_kosong(db):
    db_tangan(db, [(2, 2, "aktif", "manual", json_sah(), 1, "x", "x")], versi=2)
    assert cs.daftar(path=db) == () and cs.riwayat(1, path=db) == ()


def test_user_version_nol_dibaca_kosong(db):
    db_tangan(db, [(2, 2, "aktif", "manual", json_sah(), 1, "x", "x")], versi=0)
    assert cs.daftar(path=db) == ()


def test_tabel_hilang_dibaca_kosong(db):
    with sqlite3.connect(db) as kon:
        kon.execute("PRAGMA user_version = 1")
    kon.close()
    assert cs.daftar(path=db) == () and cs.riwayat(1, path=db) == ()


def test_baris_rusak_dilewati_baris_lain_tetap(db, caplog):
    sah = json_sah()
    rows = [
        (2, 2, "aktif", "manual", sah, 1, "2026-01-01", "2026-01-01"),                       # 1 sah
        (2, 2, "aktif", "manual", "{bukan json", 1, "2026-01-01", "2026-01-01"),             # 2
        (2, 2, "aktif", "manual", json_sah().replace("a + b", "a ** 2"), 1, "x", "x"),       # 3
        (2, 2, "terbit", "manual", sah, 1, "x", "x"),                                        # 4 status asing
        (2, 2, "aktif", "robot", sah, 1, "x", "x"),                                          # 5 sumber asing
        (3, 2, "aktif", "manual", sah, 1, "x", "x"),                                         # 6 kelas tak cocok
        (2, 1, "aktif", "manual", sah, 1, "x", "x"),                                         # 7 bab tak cocok
        (2, 2, "aktif", "manual", sah, 0, "x", "x"),                                         # 8 revisi 0
        (2, 2, "aktif", "manual", sah, 1, None, "x"),                                        # 9 dibuat bukan teks
        (2, 2, "aktif", "manual", None, 1, "x", "x"),                                        # 10 isi null
        (2, 2, "draf", "ai", sah.replace("Penjumlahan", "Lain"), 2, "x", "x"),               # 11 sah
    ]
    db_tangan(db, rows)
    with caplog.at_level(logging.WARNING, logger=cs.__name__):
        hasil = cs.daftar(path=db)
    assert [i.id for i in hasil] == [1, 11]
    assert hasil[1].cetakan.judul.startswith("Lain") and hasil[1].sumber == "ai"
    assert "bukan json" not in caplog.text and "a ** 2" not in caplog.text   # log tanpa isi
    assert cs.ambil(2, path=db) is None


def test_baris_rusak_tak_bisa_ditransisikan(db):
    db_tangan(db, [(2, 2, "draf", "manual", "{bukan json", 1, "x", "x")])
    with pytest.raises(cs.GalatCetakan):
        cs.setujui(1, actor_id="a", revisi_diharapkan=1, path=db)
    assert baris(db, "SELECT status FROM cetakan") == [{"status": "draf"}]


# --- tulis ke skema asing ----------------------------------------------------

def test_tulis_ke_user_version_asing_galat_dan_berkas_tak_berubah(db):
    db_tangan(db, versi=2)
    sebelum = db.read_bytes()
    with pytest.raises(cs.GalatCetakan):
        buat(db)
    with pytest.raises(cs.GalatCetakan):
        cs.setujui(1, actor_id="a", revisi_diharapkan=1, path=db)
    assert db.read_bytes() == sebelum


def test_tulis_ke_db_v0_berisi_tabel_asing_galat_dan_tak_berubah(db):
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE milik_orang (x INTEGER)")
    kon.close()
    sebelum = db.read_bytes()
    with pytest.raises(cs.GalatCetakan):
        buat(db)
    assert db.read_bytes() == sebelum


def test_tulis_ke_berkas_bukan_sqlite_galat(db):
    db.write_bytes(bytes(range(256)) * 64)
    with pytest.raises(cs.GalatCetakan):
        buat(db)


def test_tulis_ke_direktori_tak_ada_galat(tmp_path):
    with pytest.raises(cs.GalatCetakan):
        buat(tmp_path / "tidak-ada" / "cetakan.db")


def test_tulis_ke_tabel_berkolom_asing_galat(db):
    with sqlite3.connect(db) as kon:
        kon.execute("CREATE TABLE cetakan (x INTEGER)")
        kon.execute("PRAGMA user_version = 1")
    kon.close()
    with pytest.raises(cs.GalatCetakan):
        buat(db)


def test_berkas_tetap_privat_setelah_banyak_tulis(db):
    item = buat(db)
    os.chmod(db, 0o644)
    cs.setujui(item.id, actor_id="a", revisi_diharapkan=1, path=db)
    assert stat.S_IMODE(os.stat(db).st_mode) == 0o600


# --- cache -------------------------------------------------------------------

def test_cache_setelah_tulis_langsung_melihat_nilai_baru(db):
    assert cs.daftar(path=db) == ()
    item = buat(db)
    assert cs.daftar(path=db) == (item,)
    baru = cs.setujui(item.id, actor_id="a", revisi_diharapkan=1, path=db)
    assert cs.ambil(item.id, path=db) == baru


def test_cache_dipakai_dalam_ttl_dan_segar_setelah_ttl(db):
    waktu = [1000.0]
    cs._jam = lambda: waktu[0]
    item = buat(db)
    assert cs.daftar(path=db) == (item,)
    jalankan(db, ("UPDATE cetakan SET status = 'nonaktif' WHERE id = 1",))   # di balik layar
    assert cs.daftar(path=db)[0].status == "draf"                            # masih cache
    waktu[0] += cs.TTL_DETIK + 1
    assert cs.daftar(path=db)[0].status == "nonaktif"


# --- penutupan impor ---------------------------------------------------------

def _modul_mesin_terimpor(impor: str) -> set:
    kode = (
        "import sys; sys.path.insert(0, %r); %s; "
        "print(sorted(n for n, m in sys.modules.items() "
        "if getattr(m, '__file__', None) and m.__file__.startswith(%r)))"
        % (str(MESIN), impor, str(MESIN) + "/"))
    keluar = subprocess.run([sys.executable, "-c", kode], capture_output=True, text=True, check=True).stdout
    return set(ast.literal_eval(keluar.strip()))


def test_store_hanya_menarik_pola_dan_kurikulum_kelas_dari_mesin():
    assert _modul_mesin_terimpor("import cetakan_store") == {"cetakan_store", "cetakan_pola", "jurnal_wal", "kurikulum_kelas"}


def test_generator_tidak_menarik_cetakan_store():
    assert "cetakan_store" not in _modul_mesin_terimpor("import generator")


def test_store_hanya_mengimpor_stdlib_dan_cetakan_pola():
    pohon = ast.parse((MESIN / "cetakan_store.py").read_text(encoding="utf-8"))
    modul = set()
    for node in pohon.body:
        if isinstance(node, ast.Import):
            modul.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modul.add(node.module)
    assert modul == {"__future__", "contextlib", "dataclasses", "datetime", "logging", "os", "pathlib",
                     "sqlite3", "threading", "time", "typing", "cetakan_pola", "jurnal_wal"}


def test_isi_tersimpan_kanonik_pulang_pergi(db):
    item = buat(db, isi_sah(variabel={"b": [1, 40], "a": [10, 50]}))
    tersimpan = baris(db, "SELECT isi_json FROM cetakan")[0]["isi_json"]
    assert tersimpan == cetakan_pola.ke_json(item.cetakan)
    assert json.loads(tersimpan) == cetakan_pola.ke_dict(item.cetakan)
    assert cetakan_pola.validasi(cetakan_pola.ke_dict(item.cetakan)) == item.cetakan

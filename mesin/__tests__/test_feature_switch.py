"""Tes mesin sakelar fitur (F1): baca fail-closed, seed/ubah, audit, cache.

Semua DB uji di tmp_path; kasus "tangan" (nilai hantu, user_version salah,
baris belum di-seed) ditanam lewat sqlite3 langsung, bukan lewat ubah().
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feature_switch as fs  # noqa: E402

SEED = {
    "FUNNEL_AKTIF": False,
    "PESANAN_TRANSFER_AKTIF": False,
    "OSN_CETAK_RINGKAS": True,
    "OSN_BANK_KALIMAT": False,
    "OSN_LOMBA": False,
    "DAFTAR_AKUN_ANAK": False,
    "LATIHAN_HARIAN": False,
}
URUTAN = list(fs.NAMA_SAKELAR)


@pytest.fixture(autouse=True)
def _cache_kosong_dan_jam_pulih():
    """Tiap tes mulai dengan cache kosong; jam palsu dipulihkan setelahnya."""
    fs.bersihkan_cache()
    jam_asli = fs._jam
    yield
    fs._jam = jam_asli
    fs.bersihkan_cache()


def _ubah(path, nama, nilai, *, revisi=1, actor="admin", seed=SEED):
    """Panggilan ubah() ringkas dengan nilai wajar untuk arrange tes."""
    return fs.ubah(nama, nilai, actor_id=actor, revisi_diharapkan=revisi,
                   seed=seed, path=path)


def _db_tangan(path, baris, *, versi=1):
    """Buat DB v1 tangan TANPA CHECK agar nilai hantu bisa ditanam."""
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE sakelar (nama TEXT PRIMARY KEY,"
                    " aktif INTEGER NOT NULL, revisi INTEGER NOT NULL,"
                    " diperbarui TEXT NOT NULL)")
        kon.executemany("INSERT INTO sakelar VALUES"
                        " (?, ?, ?, '2026-01-01T00:00:00+00:00')", baris)
        kon.execute(f"PRAGMA user_version = {versi}")


def _fallback_pencatat(hasil):
    """Fallback tanpa argumen yang menghitung berapa kali ia dipanggil."""
    catatan = {"n": 0}

    def fallback():
        catatan["n"] += 1
        return hasil

    return fallback, catatan


def _jumlah_baris_sakelar(path):
    """Jumlah baris tabel sakelar; 0 bila berkas atau tabelnya belum ada."""
    if not path.exists():
        return 0
    with sqlite3.connect(path) as kon:
        ada = kon.execute("SELECT name FROM sqlite_master"
                          " WHERE type='table' AND name='sakelar'").fetchone()
        return 0 if ada is None else kon.execute(
            "SELECT COUNT(*) FROM sakelar").fetchone()[0]


# --- konstanta dan validasi nama ---

def test_nama_sakelar_tepat_tujuh_tanpa_pendamping():
    assert fs.NAMA_SAKELAR == ("FUNNEL_AKTIF", "PESANAN_TRANSFER_AKTIF",
                              "OSN_CETAK_RINGKAS", "OSN_BANK_KALIMAT", "OSN_LOMBA",
                              "DAFTAR_AKUN_ANAK", "LATIHAN_HARIAN")
    assert "PENDAMPING_AKTIF" not in fs.NAMA_SAKELAR


def test_nama_tak_dikenal_valueerror(tmp_path):
    path = tmp_path / "sakelar.db"

    with pytest.raises(ValueError, match="tidak dikenal"):
        fs.aktif("PENDAMPING_AKTIF", lambda: True, path=path)
    with pytest.raises(ValueError, match="tidak dikenal"):
        _ubah(path, "PENDAMPING_AKTIF", True)

    assert not path.exists()


# --- aktif(): baca urutan fail-closed dengan fallback env ---

def test_db_tak_ada_fallback_segar_dan_berkas_tak_dibuat(tmp_path):
    path = tmp_path / "sakelar.db"
    fallback, catatan = _fallback_pencatat(True)

    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is True
    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is True

    assert catatan["n"] == 2      # jalur tanpa DB tidak pernah dicache
    assert not path.exists()


def test_db_tak_ada_valueerror_fallback_merambat(tmp_path):
    def fallback_marah():
        raise ValueError("env rusak")

    with pytest.raises(ValueError, match="env rusak"):
        fs.aktif("FUNNEL_AKTIF", fallback_marah, path=tmp_path / "sakelar.db")


@pytest.mark.parametrize("nilai_db,harapan", [(1, True), (0, False)],
                         ids=["db-nyala", "db-mati"])
def test_baris_ada_db_menang_atas_env(tmp_path, nilai_db, harapan):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", nilai_db, 1)])
    fallback, catatan = _fallback_pencatat(not harapan)

    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is harapan

    assert catatan["n"] == 0


def test_db_ada_baris_belum_ada_ke_env(tmp_path):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("OSN_BANK_KALIMAT", 1, 1)])
    fallback, catatan = _fallback_pencatat(True)

    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is True
    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is True

    assert catatan["n"] == 2      # baris belum ada -> fallback tetap segar
    assert fs.aktif("OSN_BANK_KALIMAT", lambda: False, path=path) is True


@pytest.mark.parametrize("isi", [os.urandom(512), b""],
                         ids=["sampah-acak", "tanpa-skema"])
def test_berkas_tak_terbaca_false_tanpa_fallback(tmp_path, isi):
    path = tmp_path / "sakelar.db"
    path.write_bytes(isi)
    fallback, catatan = _fallback_pencatat(True)

    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is False

    assert catatan["n"] == 0


def test_user_version_salah_false(tmp_path):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 1, 1)], versi=7)
    fallback, catatan = _fallback_pencatat(True)

    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is False

    assert catatan["n"] == 0


def test_nilai_aktif_hantu_false(tmp_path):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 5, 1)])
    fallback, catatan = _fallback_pencatat(True)

    assert fs.aktif("FUNNEL_AKTIF", fallback, path=path) is False

    assert catatan["n"] == 0


# --- daftar(): halaman admin ---

def test_daftar_tanpa_db_sumber_env_revisi_nol(tmp_path):
    path = tmp_path / "sakelar.db"

    hasil = fs.daftar(seed=SEED, path=path)

    assert [s.nama for s in hasil] == URUTAN
    assert all(s.sumber == "env" and s.revisi == 0 for s in hasil)
    assert [s.aktif for s in hasil] == [SEED[nama] for nama in URUTAN]
    assert not path.exists()


def test_daftar_dengan_db_sumber_db(tmp_path):
    path = tmp_path / "sakelar.db"
    _ubah(path, "PESANAN_TRANSFER_AKTIF", True)

    hasil = fs.daftar(seed=SEED, path=path)

    assert [s.sumber for s in hasil] == ["db"] * 7
    assert [(s.nama, s.aktif, s.revisi) for s in hasil] == [
        ("FUNNEL_AKTIF", SEED["FUNNEL_AKTIF"], 1),
        ("PESANAN_TRANSFER_AKTIF", True, 2),
        ("OSN_CETAK_RINGKAS", SEED["OSN_CETAK_RINGKAS"], 1),
        ("OSN_BANK_KALIMAT", SEED["OSN_BANK_KALIMAT"], 1),
        ("OSN_LOMBA", SEED["OSN_LOMBA"], 1),
        ("DAFTAR_AKUN_ANAK", SEED["DAFTAR_AKUN_ANAK"], 1),
        ("LATIHAN_HARIAN", SEED["LATIHAN_HARIAN"], 1),
    ]


def test_daftar_db_rusak_galatsakelar(tmp_path):
    path = tmp_path / "rusak.db"
    path.write_bytes(os.urandom(256))

    with pytest.raises(fs.GalatSakelar):
        fs.daftar(seed=SEED, path=path)


# --- ubah(): seed, revisi, audit ---

def test_ubah_menyeed_semua_nama_lalu_menerapkan(tmp_path):
    path = tmp_path / "sakelar.db"

    hasil = _ubah(path, "FUNNEL_AKTIF", True, actor="admin-satu")

    assert (hasil.nama, hasil.aktif, hasil.revisi, hasil.sumber) == (
        "FUNNEL_AKTIF", True, 2, "db")
    with sqlite3.connect(path) as kon:
        baris = {n: (a, r) for n, a, r in
                 kon.execute("SELECT nama, aktif, revisi FROM sakelar")}
        assert baris == {
            "FUNNEL_AKTIF": (1, 2),
            "PESANAN_TRANSFER_AKTIF": (0, 1),
            "OSN_CETAK_RINGKAS": (1, 1),
            "OSN_BANK_KALIMAT": (0, 1),
            "OSN_LOMBA": (0, 1),
            "DAFTAR_AKUN_ANAK": (0, 1),
            "LATIHAN_HARIAN": (0, 1),
        }
        assert kon.execute("SELECT nama, lama, baru, revisi, actor_id"
                           " FROM audit_sakelar").fetchall() == [
            ("FUNNEL_AKTIF", 0, 1, 2, "admin-satu")]


def test_konflik_revisi_db_baru_tak_ada_seed(tmp_path):
    path = tmp_path / "sakelar.db"

    with pytest.raises(fs.KonflikRevisi):
        _ubah(path, "FUNNEL_AKTIF", True, revisi=7)

    assert _jumlah_baris_sakelar(path) == 0


def test_konflik_revisi_db_ada_tak_berubah(tmp_path):
    path = tmp_path / "sakelar.db"
    _ubah(path, "OSN_CETAK_RINGKAS", False)

    with pytest.raises(fs.KonflikRevisi):
        _ubah(path, "OSN_CETAK_RINGKAS", True)   # revisi 1 basi, sekarang 2

    with sqlite3.connect(path) as kon:
        assert kon.execute("SELECT aktif, revisi FROM sakelar"
                           " WHERE nama='OSN_CETAK_RINGKAS'").fetchone() == (0, 2)
        assert kon.execute(
            "SELECT COUNT(*) FROM audit_sakelar").fetchone()[0] == 1


def test_ubah_noop_tak_menaikkan_revisi_atau_audit(tmp_path):
    path = tmp_path / "sakelar.db"

    hasil = _ubah(path, "OSN_BANK_KALIMAT", False)

    assert (hasil.aktif, hasil.revisi, hasil.sumber) == (False, 1, "db")
    with sqlite3.connect(path) as kon:
        assert kon.execute("SELECT revisi FROM sakelar"
                           " WHERE nama='OSN_BANK_KALIMAT'").fetchone()[0] == 1
        assert kon.execute(
            "SELECT COUNT(*) FROM audit_sakelar").fetchone()[0] == 0


def test_ubah_pulihkan_baris_nilai_hantu(tmp_path):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 5, 1)])

    hasil = _ubah(path, "FUNNEL_AKTIF", True)

    assert (hasil.aktif, hasil.revisi) == (True, 2)
    with sqlite3.connect(path) as kon:
        assert kon.execute("SELECT aktif, revisi FROM sakelar"
                           " WHERE nama='FUNNEL_AKTIF'").fetchone() == (1, 2)
        assert kon.execute(
            "SELECT lama, baru FROM audit_sakelar").fetchall() == [(5, 1)]


# --- validasi ubah() dan seed ---

@pytest.mark.parametrize("nilai", [1, "1"], ids=["angka-satu", "teks-satu"])
def test_ubah_aktif_bukan_bool_valueerror(tmp_path, nilai):
    path = tmp_path / "sakelar.db"

    with pytest.raises(ValueError, match="bool"):
        _ubah(path, "FUNNEL_AKTIF", nilai)

    assert not path.exists()


@pytest.mark.parametrize("actor", ["", "   ", "x" * 101],
                         ids=["kosong", "spasi-saja", "terlalu-panjang"])
def test_ubah_actor_id_tidak_sah_valueerror(tmp_path, actor):
    path = tmp_path / "sakelar.db"

    with pytest.raises(ValueError, match="pelaku"):
        _ubah(path, "FUNNEL_AKTIF", True, actor=actor)

    assert not path.exists()


@pytest.mark.parametrize("seed", [
    {k: v for k, v in SEED.items() if k != "OSN_BANK_KALIMAT"},
    dict(SEED, PENDAMPING_AKTIF=True),
    dict(SEED, FUNNEL_AKTIF=1),
], ids=["kurang-satu-nama", "lebih-satu-nama", "nilai-bukan-bool"])
def test_seed_salah_valueerror(tmp_path, seed):
    path = tmp_path / "sakelar.db"

    with pytest.raises(ValueError):
        fs.daftar(seed=seed, path=path)
    with pytest.raises(ValueError):
        _ubah(path, "FUNNEL_AKTIF", True, seed=seed)

    assert not path.exists()


def test_ubah_user_version_salah_galatsakelar(tmp_path):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 1, 1)], versi=2)

    with pytest.raises(fs.GalatSakelar):
        _ubah(path, "FUNNEL_AKTIF", False)

    with sqlite3.connect(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 2
    assert _jumlah_baris_sakelar(path) == 1     # baris tangan tak tersentuh


# --- cache TTL dan pembersihan ---

def test_cache_db_dipakai_dalam_ttl_segar_sesudahnya(tmp_path, monkeypatch):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 0, 1)])
    jam = {"kini": 0.0}
    monkeypatch.setattr(fs, "_jam", lambda: jam["kini"])

    assert fs.aktif("FUNNEL_AKTIF", lambda: True, path=path) is False

    with sqlite3.connect(path) as kon:
        kon.execute("UPDATE sakelar SET aktif=1 WHERE nama='FUNNEL_AKTIF'")

    jam["kini"] = 2.0
    assert fs.aktif("FUNNEL_AKTIF", lambda: True, path=path) is False

    jam["kini"] = 2.0 + fs.TTL_DETIK
    assert fs.aktif("FUNNEL_AKTIF", lambda: True, path=path) is True


def test_ubah_membersihkan_cache(tmp_path):
    path = tmp_path / "sakelar.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 0, 1)])

    assert fs.aktif("FUNNEL_AKTIF", lambda: True, path=path) is False

    _ubah(path, "FUNNEL_AKTIF", True)

    assert fs.aktif("FUNNEL_AKTIF", lambda: True, path=path) is True


# --- izin berkas, path, dan pesan galat ---

def test_ubah_izin_berkas_0600(tmp_path):
    path = tmp_path / "sakelar.db"

    _ubah(path, "FUNNEL_AKTIF", True)

    assert (path.stat().st_mode & 0o777) == 0o600


def test_pesan_galat_tak_memuat_path(tmp_path):
    path = tmp_path / "sakelar.db"

    with pytest.raises(fs.KonflikRevisi) as info:
        _ubah(path, "FUNNEL_AKTIF", True, revisi=9)

    assert str(path) not in str(info.value)

    path_rusak = tmp_path / "rusak.db"
    path_rusak.write_bytes(os.urandom(256))
    with pytest.raises(fs.GalatSakelar) as info_rusak:
        fs.daftar(seed=SEED, path=path_rusak)

    assert str(path_rusak) not in str(info_rusak.value)


def test_env_sakelar_berkas_db_dibaca_saat_panggil(tmp_path, monkeypatch):
    path = tmp_path / "env.db"
    _db_tangan(path, [("FUNNEL_AKTIF", 1, 1)])
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(path))

    assert fs.aktif("FUNNEL_AKTIF", lambda: False) is True
    assert fs.daftar(seed=SEED)[0].sumber == "db"

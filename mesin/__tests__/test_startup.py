"""Bootstrap startup: promosi admin + backfill pemilik data warisan.

Pemasangan lama (single-family) naik kelas ke multi-keluarga tanpa langkah
manual: akun guru pertama jadi admin, dan seluruh siswa warisan ber-pemilik
' ' dibubuhi nama admin itu. Keduanya idempoten — startup boleh berulang.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import serve  # noqa: E402
import auth  # noqa: E402

SANDI_GURU = "sandi-guru-panjang-123"


@pytest.fixture()
def pasangan(tmp_path, monkeypatch):
    """DB + berkas sandi sementara, terpasang sebagai bawaan modul."""
    db = tmp_path / "uji.db"
    berkas = tmp_path / "sandi.json"
    database.siapkan(db)
    monkeypatch.setattr(database, "BAWAAN", db)
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    return db, berkas


def test_startup_mempromosikan_admin_dan_backfill_pemilik(pasangan):
    db, berkas = pasangan
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Rara", "P3")  # warisan: pemilik ''
        database.tambah_siswa(kon, "Bima", "P4")
    auth.simpan_sandi(SANDI_GURU, "guru", berkas)

    admin = serve.siapkan_admin_dan_pemilik()

    assert admin == "guru"
    assert auth.cari_akun("guru", berkas)["peran"] == "admin"
    with database.buka(db) as kon:
        pemilik = {
            r["nama"]: r["pemilik"]
            for r in kon.execute("SELECT nama, pemilik FROM siswa")
        }
    assert pemilik == {"Rara": "guru", "Bima": "guru"}


def test_startup_memigrasikan_revisi_auth_legacy_ke_nol(pasangan):
    _db, berkas = pasangan
    auth.simpan_sandi(SANDI_GURU, "guru", berkas)
    data = __import__("json").loads(berkas.read_text())
    data.pop("revisi_auth", None)
    berkas.write_text(__import__("json").dumps(data), encoding="utf-8")

    assert serve.siapkan_admin_dan_pemilik() == "guru"
    akun = auth.cari_akun("guru", berkas)
    # Migrasi 0 lalu promosi role menaikkan revisi untuk mencabut snapshot lama.
    assert akun["revisi_auth"] == 1
    assert akun["peran"] == "admin"


def test_startup_idempoten(pasangan):
    db, berkas = pasangan
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Rara", "P3")
    auth.simpan_sandi(SANDI_GURU, "guru", berkas)

    assert serve.siapkan_admin_dan_pemilik() == "guru"
    assert serve.siapkan_admin_dan_pemilik() == "guru"

    akun = auth.muat_akun(berkas)
    assert len(akun) == 1
    assert akun[0]["peran"] == "admin"
    assert akun[0]["revisi_auth"] == 2
    assert auth.id_akun_sah(akun[0]["id_akun"])
    with database.buka(db) as kon:
        pemilik = [
            r["pemilik"] for r in kon.execute("SELECT pemilik FROM siswa")
        ]
    assert pemilik == ["guru"]


def test_startup_tanpa_berkas_sandi_tak_menyentuh_db(pasangan):
    """Mode lokal (tanpa sandi.json): tidak ada yang dipromosikan, dan
    baris warisan dibiarkan ber-pemilik kosong."""
    db, _ = pasangan
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Rara", "P3")

    assert serve.siapkan_admin_dan_pemilik() is None

    with database.buka(db) as kon:
        pemilik = [
            r["pemilik"] for r in kon.execute("SELECT pemilik FROM siswa")
        ]
    assert pemilik == [""]


def test_startup_dengan_admin_ada_tidak_mengubah_siswa(pasangan):
    db, berkas = pasangan
    auth.tambah_akun("pengelola", "sandi-pengelola-9999", "admin", berkas)
    auth.tambah_akun("ortu-a", "sandi-ortu-a-123456", "guru", berkas)
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Rara", "P3", pemilik="ortu-a")

    assert serve.siapkan_admin_dan_pemilik() == "pengelola"

    with database.buka(db) as kon:
        baris = kon.execute("SELECT pemilik FROM siswa").fetchone()
    assert baris["pemilik"] == "ortu-a"

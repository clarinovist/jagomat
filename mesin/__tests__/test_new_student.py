"""Fase B.2: aksi gabungan "anak_baru" — siswa + akun murid sekaligus.

Kontrak proses_akun aksi=anak_baru:
1. Data lengkap -> siswa dibuat + akun murid dibuat (nama sama) -> pesan sukses.
2. Nama siswa sudah ada -> galat, TIDAK ada apa pun yang dibuat.
3. Nama akun sudah dipakai (tapi siswa belum) -> galat, siswa TIDAK dibuat.
4. Tingkat tak valid -> galat (kontrak sama dengan aksi "siswa").
5. Sandi anak < 8 -> galat, siswa TIDAK dibuat (atomic, tanpa setengah jadi).
6. Privasi mengikuti policy awal; tambah anak tidak mencatat consent baru
   ataupun mengubah izin penggunaan data tambahan.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import auth  # noqa: E402
import web  # noqa: E402
import account_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    berkas = tmp_path / "sandi.json"
    auth.simpan_sandi("sandi-guru-panjang-123", "guru", path=berkas)
    monkeypatch.setattr(auth, "BERKAS_SANDI", berkas)
    db_path = tmp_path / "uji.db"
    database.siapkan(db_path)
    monkeypatch.setattr(database, "BAWAAN", db_path)
    with database.buka(db_path) as kon:
        yield kon


DATA_LENGKAP = {
    "aksi": "anak_baru",
    "nama": "Aisha",
    "tingkat": "P4",
    "sandi_anak": "sandi-aisha-12345",
}


def test_anak_baru_membuat_siswa_dan_akun(db):
    pesan, galat = account_pages.proses_akun(db, dict(DATA_LENGKAP), "guru")
    assert galat == ""
    assert "Aisha" in pesan
    # siswa ada dengan tingkat yang diminta
    baris = db.execute("SELECT * FROM siswa WHERE nama='Aisha'").fetchone()
    assert baris is not None and baris["tingkat"] == "P4"
    # akun murid ada dan bisa diautentikasi
    akun = auth.cari_akun("Aisha")
    assert akun is not None and akun["peran"] == "murid"
    assert auth.periksa("Aisha", "sandi-aisha-12345")


def test_anak_baru_nama_siswa_sudah_ada(db):
    account_pages.proses_akun(db, dict(DATA_LENGKAP), "guru")
    pesan, galat = account_pages.proses_akun(db, dict(DATA_LENGKAP), "guru")
    assert galat != ""
    jumlah = db.execute("SELECT COUNT(*) c FROM siswa WHERE nama='Aisha'").fetchone()["c"]
    assert jumlah == 1


def test_anak_baru_siswa_tidak_dibuat_bila_akun_gagal(db, tmp_path):
    # nama akun sudah terpakai oleh akun lain -> tambah_akun gagal ->
    # siswa TIDAK boleh tertinggal setengah jadi
    auth.tambah_akun("Aisha", "akun-lain-123456", "guru")
    pesan, galat = account_pages.proses_akun(db, dict(DATA_LENGKAP), "guru")
    assert galat != ""
    assert db.execute("SELECT COUNT(*) c FROM siswa WHERE nama='Aisha'").fetchone()["c"] == 0


def test_anak_baru_tingkat_tak_valid_ditolak(db):
    data = dict(DATA_LENGKAP, tingkat="kelas-4")
    _, galat = account_pages.proses_akun(db, data, "guru")
    assert galat != ""
    assert db.execute("SELECT COUNT(*) c FROM siswa").fetchone()["c"] == 0


def test_anak_baru_sandi_pendek_ditolak_tanpa_siswa_yatim(db):
    data = dict(DATA_LENGKAP, sandi_anak="pendek")
    _, galat = account_pages.proses_akun(db, data, "guru")
    assert galat != ""
    assert db.execute("SELECT COUNT(*) c FROM siswa").fetchone()["c"] == 0
    assert auth.cari_akun("Aisha") is None


def test_anak_baru_nama_login_opsional(db):
    """Nama login boleh beda dari nama anak — jalannya bila nama anak
    sudah dipakai keluarga lain sebagai login global."""
    pesan, galat = account_pages.proses_akun(
        db, dict(DATA_LENGKAP, nama_akun="aisha-santoso"), "ortu-a"
    )
    assert galat == ""
    baris = db.execute("SELECT id FROM siswa WHERE nama='Aisha'").fetchone()
    assert baris is not None
    akun = auth.cari_akun("aisha-santoso")
    assert akun is not None and akun["siswa_id"] == baris["id"]
    assert auth.cari_akun("Aisha") is None, "login bawaan tidak boleh ikut dibuat"
    assert "aisha-santoso" in pesan, "pesan harus menyebut nama loginnya"


def test_anak_baru_dobel_nama_antar_keluarga_via_login_beda(db):
    """Janji README: dua keluarga boleh sama-sama punya 'Bima'. Kalau nama
    login 'Bima' sudah dipakai keluarga pertama, keluarga kedua cukup
    memakai variasi nama login; dalam satu keluarga tetap ditolak."""
    _, g1 = account_pages.proses_akun(db, dict(
        DATA_LENGKAP, nama="Bima", tingkat="P3", sandi_anak="sandi-bima-12345",
    ), "ortu-a")
    _, g2 = account_pages.proses_akun(db, dict(
        DATA_LENGKAP, nama="Bima", tingkat="P3",
        sandi_anak="sandi-bima-67890", nama_akun="bima-kedua",
    ), "ortu-b")
    _, g3 = account_pages.proses_akun(db, dict(
        DATA_LENGKAP, nama="BIMA", tingkat="P3", sandi_anak="sandi-bima-abcde",
    ), "ortu-a")
    n = db.execute(
        "SELECT COUNT(*) c FROM siswa WHERE nama='Bima'"
    ).fetchone()["c"]
    assert g1 == "" and g2 == ""
    assert g3 != "" and "sudah ada" in g3.lower()
    assert n == 2


# ── Multi-keluarga: pemilik & tautan siswa_id ───────────────────────────


def test_anak_baru_membubuhkan_pemilik_dan_siswa_id_akun(db):
    _, galat = account_pages.proses_akun(db, dict(DATA_LENGKAP), "ortu-a")
    assert galat == ""
    baris = db.execute(
        "SELECT id, pemilik FROM siswa WHERE nama='Aisha'"
    ).fetchone()
    assert baris["pemilik"] == "ortu-a"
    akun = auth.cari_akun("Aisha")
    assert akun["siswa_id"] == baris["id"]

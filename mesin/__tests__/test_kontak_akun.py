"""Kontak WhatsApp per akun (K1): normalisasi, upsert, dan struktur skema.

Semua data sintetis di tmp_path. Nomor uji adalah nomor rekaan, bukan milik siapa pun.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import kontak_akun  # noqa: E402

ID_AKUN = "akun_" + "a1" * 16
ID_LAIN = "akun_" + "b2" * 16
WA = "6281234567890"
WA_LAIN = "6285551234567"
T1 = "2026-11-17T10:00:00"
T2 = "2026-11-18T09:30:00"


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "kontak.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


# --- normalisasi_wa -------------------------------------------------------

@pytest.mark.parametrize(
    "masukan",
    [
        "081234567890",
        "+6281234567890",
        "6281234567890",
        "0812 3456 7890",
        "0812-3456-7890",
        "+62 812-3456-7890",
        "(0812) 3456.7890",
        "  081234567890  ",
    ],
)
def test_normalisasi_menerima_format_umum(masukan):
    assert kontak_akun.normalisasi_wa(masukan) == WA


def test_normalisasi_menerima_batas_panjang_bawah_dan_atas():
    assert kontak_akun.normalisasi_wa("628" + "1" * 8) == "628" + "1" * 8
    assert kontak_akun.normalisasi_wa("628" + "1" * 12) == "628" + "1" * 12


@pytest.mark.parametrize(
    "masukan",
    [
        "",
        "   ",
        "abc",
        "0812abc4567",
        "08123",                      # terlalu pendek
        "628" + "1" * 7,              # satu digit kurang dari batas
        "628" + "1" * 13,             # satu digit lebih dari batas
        "6221" + "1" * 8,             # awalan 62 tetapi bukan 628
        "0212345678901",              # telepon rumah
        "+6181234567890",             # kode negara salah
        "+0812345678901",             # plus dengan awalan lokal
        "0062812345678",              # awalan internasional lain
        "62812345+67890",             # plus di tengah
        "08123456789٠",          # digit non-ASCII
        "0" * 40,                     # melewati batas input
        "0812 3456 7890" + " " * 40,  # spasi berlebih tetap ditolak
    ],
)
def test_normalisasi_menolak_yang_tidak_sah(masukan):
    assert kontak_akun.normalisasi_wa(masukan) is None


@pytest.mark.parametrize("masukan", [None, 81234567890, 6281234567890, b"6281234567890", [], 1.5])
def test_normalisasi_menolak_tipe_bukan_str(masukan):
    assert kontak_akun.normalisasi_wa(masukan) is None


# --- simpan / ambil / hapus ----------------------------------------------

def test_ambil_akun_tanpa_kontak_mengembalikan_none(kon):
    assert kontak_akun.ambil(kon, ID_AKUN) is None


def test_simpan_lalu_ambil_mengembalikan_isi_persis(kon):
    kontak_akun.simpan(kon, ID_AKUN, WA, T1)

    assert kontak_akun.ambil(kon, ID_AKUN) == {
        "id_akun": ID_AKUN,
        "wa": WA,
        "dibuat": T1,
        "diperbarui": T1,
        "aktivitas_terakhir": T1,
    }


def test_simpan_dua_kali_memperbarui_tanpa_mengubah_dibuat(kon):
    kontak_akun.simpan(kon, ID_AKUN, WA, T1)
    kontak_akun.simpan(kon, ID_AKUN, WA_LAIN, T2)

    baris = kontak_akun.ambil(kon, ID_AKUN)
    assert baris["wa"] == WA_LAIN
    assert baris["dibuat"] == T1
    assert baris["diperbarui"] == T2
    jumlah = kon.execute("SELECT COUNT(*) FROM kontak_akun").fetchone()[0]
    assert jumlah == 1


def test_simpan_tidak_menyentuh_akun_lain(kon):
    kontak_akun.simpan(kon, ID_AKUN, WA, T1)
    kontak_akun.simpan(kon, ID_LAIN, WA_LAIN, T2)

    assert kontak_akun.ambil(kon, ID_AKUN)["wa"] == WA
    assert kontak_akun.ambil(kon, ID_LAIN)["wa"] == WA_LAIN


def test_simpan_tidak_commit_sendiri(tmp_path):
    jalur = tmp_path / "rollback.db"
    database.siapkan(jalur)
    kon = sqlite3.connect(str(jalur))
    try:
        kon.execute("BEGIN")
        kontak_akun.simpan(kon, ID_AKUN, WA, T1)
        kon.rollback()
        assert kontak_akun.ambil(kon, ID_AKUN) is None
    finally:
        kon.close()


def test_hapus_menghapus_hanya_akun_target(kon):
    kontak_akun.simpan(kon, ID_AKUN, WA, T1)
    kontak_akun.simpan(kon, ID_LAIN, WA_LAIN, T1)

    assert kontak_akun.hapus(kon, ID_AKUN) is True

    assert kontak_akun.ambil(kon, ID_AKUN) is None
    assert kontak_akun.ambil(kon, ID_LAIN)["wa"] == WA_LAIN


def test_hapus_akun_tanpa_kontak_mengembalikan_false(kon):
    assert kontak_akun.hapus(kon, ID_AKUN) is False


# --- penolakan ------------------------------------------------------------

@pytest.mark.parametrize(
    "id_akun",
    [None, "", "guru", "akun_", "akun_" + "a" * 31, "akun_" + "A1" * 16, "akun_" + "zz" * 16, 123],
)
def test_simpan_menolak_id_akun_tidak_sah_tanpa_tulis(kon, id_akun):
    sebelum = kon.total_changes

    with pytest.raises(ValueError):
        kontak_akun.simpan(kon, id_akun, WA, T1)

    assert kon.total_changes == sebelum
    assert kon.execute("SELECT COUNT(*) FROM kontak_akun").fetchone()[0] == 0


@pytest.mark.parametrize("id_akun", [None, "guru", "akun_x"])
def test_ambil_dan_hapus_menolak_id_akun_tidak_sah(kon, id_akun):
    with pytest.raises(ValueError):
        kontak_akun.ambil(kon, id_akun)
    with pytest.raises(ValueError):
        kontak_akun.hapus(kon, id_akun)


@pytest.mark.parametrize("wa_mentah", ["081234567890", "+6281234567890", "0812 3456 7890", "6281", "", None, 6281234567890])
def test_simpan_menolak_wa_yang_belum_ternormalisasi_tanpa_tulis(kon, wa_mentah):
    sebelum = kon.total_changes

    with pytest.raises(ValueError) as galat:
        kontak_akun.simpan(kon, ID_AKUN, wa_mentah, T1)

    assert kon.total_changes == sebelum
    assert kontak_akun.ambil(kon, ID_AKUN) is None
    assert "6281" not in str(galat.value)
    assert "0812" not in str(galat.value)


@pytest.mark.parametrize("waktu", [None, "", "kemarin", 20261117])
def test_simpan_menolak_waktu_tidak_sah(kon, waktu):
    with pytest.raises(ValueError):
        kontak_akun.simpan(kon, ID_AKUN, WA, waktu)

    assert kontak_akun.ambil(kon, ID_AKUN) is None


def test_pesan_galat_tidak_memuat_nomor(kon):
    with pytest.raises(ValueError) as galat:
        kontak_akun.simpan(kon, "akun_xyz", "081299998888", T1)

    assert "08129999" not in str(galat.value)
    assert "62812999" not in str(galat.value)


def test_skema_menolak_wa_salah_bentuk_meski_lewat_sql_langsung(kon):
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(
            "INSERT INTO kontak_akun(id_akun, wa, dibuat, diperbarui, aktivitas_terakhir)"
            " VALUES (?, ?, ?, ?, ?)",
            (ID_AKUN, "081234567890", T1, T1, T1),
        )


# --- struktur: terpisah dari data anak -----------------------------------

def test_skema_kontak_akun_tidak_punya_kolom_atau_kunci_ke_siswa(kon):
    kolom = [baris[1] for baris in kon.execute("PRAGMA table_info(kontak_akun)")]
    kunci_asing = list(kon.execute("PRAGMA foreign_key_list(kontak_akun)"))

    assert kolom == ["id_akun", "wa", "dibuat", "diperbarui", "aktivitas_terakhir"]
    assert kunci_asing == []
    assert not any("siswa" in nama or "anak" in nama or "nama" in nama for nama in kolom)


def test_tidak_ada_tabel_lain_yang_mengacu_ke_kontak_akun(kon):
    tabel = [baris[0] for baris in kon.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    pengacu = [
        nama
        for nama in tabel
        if any(baris[2] == "kontak_akun" for baris in kon.execute(f"PRAGMA foreign_key_list({nama})"))
    ]

    assert pengacu == []


def test_siapkan_dua_kali_idempoten_dan_menyimpan_baris(tmp_path):
    jalur = tmp_path / "idem.db"
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        kontak_akun.simpan(kon, ID_AKUN, WA, T1)

    database.siapkan(jalur)

    with database.buka(jalur) as kon:
        assert kontak_akun.ambil(kon, ID_AKUN)["wa"] == WA

"""Cek kemampuan gratis (funnel Fase 2a): penilaian, baca hasil, skema, hapus keluarga.

Semua data sintetis di basis sementara. Mulai ada di test_cek_gratis.py, sapuan di test_cek_gratis_sapu.py.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import database  # noqa: E402
import topics  # noqa: E402
from cek_gratis_kit import (  # noqa: E402
    ID_A, ID_B, ID_C, SEKARANG, TABEL_BUKTI_SIKLUS, hitung, jawab, mulai_cek,
    tambah_anak, tandai_selesai,
)

NAMA_ANAK = "Anak Sintetis Rahasia"
KUNCI_HASIL = {"status", "skor", "kategori", "ringkasan", "jumlah_soal"}


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "cek.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


@pytest.fixture(autouse=True)
def materi_dasar_mati(monkeypatch):
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)


def _nama(topik_id):
    return topics.ambil(topik_id).nama


def _keadaan(kon):
    return tuple(hitung(kon, t) for t in ("cek_gratis", "sesi", "sesi_soal", "jawaban"))


# --- selesaikan_jika_siap / baca_hasil --------------------------------------

def test_baca_hasil_belum_mulai_tanpa_skor(kon):
    hasil = cek_gratis.baca_hasil(kon, ID_A)
    assert set(hasil) == KUNCI_HASIL
    assert (hasil["status"], hasil["skor"], hasil["kategori"]) == ("belum_mulai", None, None)
    assert hasil["ringkasan"] == {"kuat": [], "perlu": []}


def test_sesi_belum_selesai_tidak_menghasilkan_skor(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)  # semua benar, tetapi sesi belum ditutup

    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is False

    hasil = cek_gratis.baca_hasil(kon, ID_A)
    assert set(hasil) == KUNCI_HASIL
    assert (hasil["status"], hasil["skor"], hasil["kategori"]) == ("belum_selesai", None, None)
    assert kon.execute("SELECT skor, kategori, ringkasan, selesai_pada FROM cek_gratis").fetchone()[:] == (None,) * 4


def test_sesi_dibatalkan_tidak_menghasilkan_skor(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)
    tandai_selesai(kon, sesi_id)
    kon.execute("UPDATE sesi SET dibatalkan = '2026-11-18 09:30:00' WHERE id = ?", (sesi_id,))

    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is False
    assert cek_gratis.baca_hasil(kon, ID_A)["status"] == "belum_selesai"


@pytest.mark.parametrize("benar,skor,kategori", [
    (0, 0, "Perlu pendampingan"), (5, 33, "Perlu pendampingan"),
    (6, 40, "Perlu penguatan"), (9, 60, "Perlu penguatan"),
    (10, 67, "Cukup baik"), (12, 80, "Cukup baik"),
    (13, 87, "Sangat baik"), (15, 100, "Sangat baik"),
])
def test_skor_dan_kategori_dari_jumlah_benar(kon, benar, skor, kategori):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=benar)
    tandai_selesai(kon, sesi_id)

    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True

    hasil = cek_gratis.baca_hasil(kon, ID_A)
    assert (hasil["status"], hasil["skor"], hasil["kategori"], hasil["jumlah_soal"]) == (
        "selesai", skor, kategori, 15)


def test_soal_tak_dijawab_dihitung_salah(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    baris = database.isi_sesi(kon, sesi_id)
    for b in baris[:5]:  # 5 benar, 10 sisanya tanpa baris jawaban sama sekali
        database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban=b["kunci"])
    tandai_selesai(kon, sesi_id)

    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    assert cek_gratis.baca_hasil(kon, ID_A)["skor"] == 33


def test_selesaikan_idempoten_dan_selesai_pada_dari_waktu_sesi(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)
    tandai_selesai(kon, sesi_id)

    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True
    baris = tuple(kon.execute("SELECT * FROM cek_gratis").fetchone())
    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, "2027-01-01T00:00:00") is False

    assert tuple(kon.execute("SELECT * FROM cek_gratis").fetchone()) == baris
    assert kon.execute("SELECT selesai_pada FROM cek_gratis").fetchone()[0] == "2026-11-18T09:00:00"


def test_ringkasan_terstruktur_dengan_nama_topik_resmi(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 5)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, {"pola-bilangan": 5, "statistika": 3, "geometri-datar": 1})
    tandai_selesai(kon, sesi_id)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    hasil = cek_gratis.baca_hasil(kon, ID_A)

    assert hasil["ringkasan"] == {"kuat": [_nama("pola-bilangan")], "perlu": [_nama("geometri-datar")]}
    assert hasil["skor"] == 60


def test_ringkasan_maksimal_dua_butir_per_jenis(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 5)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, {"pola-bilangan": 5, "statistika": 5, "geometri-datar": 5})
    tandai_selesai(kon, sesi_id)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    hasil = cek_gratis.baca_hasil(kon, ID_A)

    assert hasil["ringkasan"] == {
        "kuat": [_nama("geometri-datar"), _nama("pola-bilangan")], "perlu": []}  # seri: urut id topik


def test_ringkasan_kelas_1_hanya_satu_topik_dasar(kon, monkeypatch):
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 1)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    for b in database.isi_sesi(kon, sesi_id):
        database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban=b["kunci"])
    tandai_selesai(kon, sesi_id)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    hasil = cek_gratis.baca_hasil(kon, ID_A)

    assert (hasil["skor"], hasil["ringkasan"]) == (100, {"kuat": [_nama("bilangan-dasar")], "perlu": []})


def test_baca_hasil_hanya_kunci_tetap_tanpa_kunci_jawaban_atau_id(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, {"pola-bilangan": 5, "statistika": 2, "geometri-datar": 0})
    tandai_selesai(kon, sesi_id)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    hasil = cek_gratis.baca_hasil(kon, ID_A)

    assert set(hasil) == KUNCI_HASIL
    assert set(hasil["ringkasan"]) == {"kuat", "perlu"}
    teks = repr(hasil)
    assert NAMA_ANAK not in teks and ID_A not in teks
    kunci_sesi = {str(b["kunci"]) for b in database.isi_sesi(kon, sesi_id)}
    assert not any(k in hasil["kategori"] for k in kunci_sesi if len(k) > 3)


def test_baca_hasil_hanya_milik_akun_pemanggil(kon):
    anak_a = tambah_anak(kon, "Anak A", "guru-a", 4)
    anak_b = tambah_anak(kon, "Anak B", "guru-b", 4)
    sesi_a = mulai_cek(kon, ID_A, anak_a, "guru-a")
    mulai_cek(kon, ID_B, anak_b, "guru-b")
    jawab(kon, sesi_a, semua_benar=15)
    tandai_selesai(kon, sesi_a)
    assert cek_gratis.selesaikan_jika_siap(kon, ID_B, SEKARANG) is False  # B belum selesai
    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True

    hasil_b = cek_gratis.baca_hasil(kon, ID_B)
    hasil_c = cek_gratis.baca_hasil(kon, ID_C)

    assert cek_gratis.baca_hasil(kon, ID_A)["skor"] == 100
    assert (hasil_b["status"], hasil_b["skor"]) == ("belum_selesai", None)
    assert (hasil_c["status"], hasil_c["skor"]) == ("belum_mulai", None)


def test_selesaikan_hanya_menilai_cek_milik_akun_itu(kon):
    anak_a = tambah_anak(kon, "Anak A", "guru-a", 4)
    sesi_a = mulai_cek(kon, ID_A, anak_a, "guru-a")
    jawab(kon, sesi_a, semua_benar=15)
    tandai_selesai(kon, sesi_a)

    assert cek_gratis.selesaikan_jika_siap(kon, ID_B, SEKARANG) is False

    assert kon.execute("SELECT skor FROM cek_gratis").fetchone()[0] is None


def test_baca_hasil_dengan_dua_anak_mengembalikan_cek_terbaru(kon):
    anak_1 = tambah_anak(kon, "Anak Satu", "guru-a", 4)
    anak_2 = tambah_anak(kon, "Anak Dua", "guru-a", 4)
    sesi_1 = mulai_cek(kon, ID_A, anak_1, "guru-a")
    jawab(kon, sesi_1, semua_benar=15)
    tandai_selesai(kon, sesi_1)
    mulai_cek(kon, ID_A, anak_2, "guru-a")
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    assert cek_gratis.baca_hasil(kon, ID_A)["status"] == "belum_selesai"


def test_hasil_siswa_membaca_cek_anak_itu_bukan_cek_terbaru_akun(kon):
    anak_1 = tambah_anak(kon, "Anak Satu", "guru-a", 4)
    anak_2 = tambah_anak(kon, "Anak Dua", "guru-a", 4)
    sesi_1 = mulai_cek(kon, ID_A, anak_1, "guru-a")
    sesi_2 = mulai_cek(kon, ID_A, anak_2, "guru-a")
    jawab(kon, sesi_2, semua_benar=15)
    tandai_selesai(kon, sesi_2)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    assert sesi_1 != sesi_2
    assert cek_gratis.baca_hasil(kon, ID_A)["status"] == "selesai"  # cek terbaru = anak kedua
    satu = cek_gratis.hasil_siswa(kon, ID_A, anak_1)
    dua = cek_gratis.hasil_siswa(kon, ID_A, anak_2)
    assert set(satu) == set(dua) == KUNCI_HASIL
    assert (satu["status"], satu["skor"]) == ("belum_selesai", None)
    assert (dua["status"], dua["skor"]) == ("selesai", 100)


def test_hasil_siswa_kunci_akun_dan_anak_keduanya(kon):
    anak_a = tambah_anak(kon, "Anak A", "guru-a", 4)
    sesi_a = mulai_cek(kon, ID_A, anak_a, "guru-a")
    jawab(kon, sesi_a, semua_benar=15)
    tandai_selesai(kon, sesi_a)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)

    assert cek_gratis.hasil_siswa(kon, ID_A, anak_a)["skor"] == 100
    asing = cek_gratis.hasil_siswa(kon, ID_B, anak_a)  # akun lain, anak yang sama
    assert (asing["status"], asing["skor"]) == ("belum_mulai", None)


@pytest.mark.parametrize("siswa_id", [None, 0, -1, "1", 999999, True])
def test_hasil_siswa_anak_tidak_dikenal_atau_tipe_salah_belum_mulai(kon, siswa_id):
    hasil = cek_gratis.hasil_siswa(kon, ID_A, siswa_id)
    assert set(hasil) == KUNCI_HASIL and (hasil["status"], hasil["skor"]) == ("belum_mulai", None)


@pytest.mark.parametrize("id_akun", [None, "", "akun_x", 7])
def test_hasil_siswa_menolak_id_akun_tidak_sah(kon, id_akun):
    with pytest.raises(ValueError):
        cek_gratis.hasil_siswa(kon, id_akun, 1)


@pytest.mark.parametrize("id_akun", [None, "", "akun_x", "akun_" + "G" * 32, 7])
def test_baca_dan_selesaikan_menolak_id_akun_tidak_sah(kon, id_akun):
    with pytest.raises(ValueError):
        cek_gratis.baca_hasil(kon, id_akun)
    with pytest.raises(ValueError):
        cek_gratis.selesaikan_jika_siap(kon, id_akun, SEKARANG)


def test_ringkasan_rusak_di_basis_data_ditolak_bukan_dikembalikan(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)
    tandai_selesai(kon, sesi_id)
    cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG)
    kon.execute("UPDATE cek_gratis SET ringkasan = ?", ('{"kuat": ["x"], "kunci": [7]}',))

    with pytest.raises(ValueError, match="Ringkasan cek tidak sah"):
        cek_gratis.baca_hasil(kon, ID_A)


# --- skema ------------------------------------------------------------------

def test_siapkan_dua_kali_idempoten_dan_tabel_ada(tmp_path):
    jalur = tmp_path / "ulang.db"
    database.siapkan(jalur)
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        kolom = [r[1] for r in kon.execute("PRAGMA table_info(cek_gratis)")]
    assert kolom == ["id", "siswa_id", "id_akun", "sesi_id", "setuju_pada", "versi_notice",
                     "dibuat", "selesai_pada", "skor", "kategori", "ringkasan",
                     "jumlah_soal", "bahan_dihapus_pada"]


@pytest.mark.parametrize("kolom,nilai", [
    ("id_akun", "akun_" + "A" * 32), ("id_akun", "akun_" + "a" * 31), ("id_akun", "pengguna"),
    ("skor", 101), ("skor", -1), ("kategori", "Luar biasa"), ("jumlah_soal", 0),
])
def test_check_skema_menolak_nilai_tidak_sah(kon, kolom, nilai):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    dasar = {"siswa_id": anak, "id_akun": ID_A, "setuju_pada": "t", "versi_notice": "v1", "dibuat": "t"}
    if kolom in ("skor", "kategori"):
        dasar.update(selesai_pada="t", skor=50, kategori="Perlu penguatan", ringkasan="{}")
    dasar[kolom] = nilai
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO cek_gratis(%s) VALUES (%s)" % (
            ",".join(dasar), ",".join("?" * len(dasar))), tuple(dasar.values()))


def test_kolom_turunan_hanya_boleh_terisi_bersamaan(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(
            """INSERT INTO cek_gratis(siswa_id, id_akun, setuju_pada, versi_notice, dibuat, skor)
               VALUES (?, ?, 't', 'v1', 't', 50)""", (anak, ID_A))


def test_hapus_anak_membawa_turunan_dan_hapus_sesi_mengosongkan_sesi_id(kon):
    anak_1 = tambah_anak(kon, "Anak Satu", "guru-a", 4)
    anak_2 = tambah_anak(kon, "Anak Dua", "guru-b", 4)
    mulai_cek(kon, ID_A, anak_1, "guru-a")
    sesi_2 = mulai_cek(kon, ID_B, anak_2, "guru-b")

    kon.execute("DELETE FROM siswa WHERE id = ?", (anak_1,))
    kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_2,))

    baris = kon.execute("SELECT id_akun, sesi_id FROM cek_gratis").fetchall()
    assert [tuple(b) for b in baris] == [(ID_B, None)]


# --- hapus_cek_keluarga -----------------------------------------------------

def test_hapus_cek_keluarga_menghapus_milik_target_saja(kon):
    anak_a = tambah_anak(kon, "Anak A", "guru-a", 4)
    anak_b = tambah_anak(kon, "Anak B", "guru-b", 4)
    mulai_cek(kon, ID_A, anak_a, "guru-a")
    mulai_cek(kon, ID_B, anak_b, "guru-b")

    jumlah = cek_gratis.hapus_cek_keluarga(kon, ID_A, (anak_a,))

    assert jumlah == 1
    assert [r[0] for r in kon.execute("SELECT id_akun FROM cek_gratis")] == [ID_B]


def test_hapus_cek_keluarga_menangkap_cek_lewat_id_akun_dan_lewat_anak(kon):
    anak_a = tambah_anak(kon, "Anak A", "guru-a", 4)
    anak_b = tambah_anak(kon, "Anak B", "guru-a", 4)
    mulai_cek(kon, ID_A, anak_a, "guru-a")
    mulai_cek(kon, ID_C, anak_b, "guru-a")  # id_akun lain tetapi anak keluarga ini

    jumlah = cek_gratis.hapus_cek_keluarga(kon, ID_A, (anak_a, anak_b))

    assert jumlah == 2 and hitung(kon, "cek_gratis") == 0


@pytest.mark.parametrize("id_akun,siswa_ids", [("x", ()), (ID_A, ("1",)), (ID_A, (True,))])
def test_hapus_cek_keluarga_menolak_masukan_tidak_sah_tanpa_menghapus(kon, id_akun, siswa_ids):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    mulai_cek(kon, ID_A, anak, "guru-a")
    with pytest.raises(ValueError):
        cek_gratis.hapus_cek_keluarga(kon, id_akun, siswa_ids)
    assert hitung(kon, "cek_gratis") == 1



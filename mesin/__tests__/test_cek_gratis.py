"""Cek kemampuan gratis (funnel Fase 2a): mulai (persetujuan, kepemilikan, bentuk sesi, satu cek per anak).

Semua data sintetis di basis sementara. Penilaian/hasil/skema ada di test_cek_gratis_hasil.py, sapuan di test_cek_gratis_sapu.py.
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


# --- mulai: persetujuan -----------------------------------------------------

@pytest.mark.parametrize("setuju", [False, None, 1, 0, "1", "true", "on", [], "setuju"])
def test_mulai_tanpa_setuju_tidak_menulis_apa_pun(kon, setuju):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    awal = _keadaan(kon)

    with pytest.raises(cek_gratis.CekPersetujuanDiperlukan):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", setuju, SEKARANG)

    assert _keadaan(kon) == awal == (0, 0, 0, 0)


# --- mulai: kepemilikan -----------------------------------------------------

def test_mulai_bukan_pemilik_ditolak_tanpa_efek_samping(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    awal = _keadaan(kon)

    with pytest.raises(cek_gratis.CekTidakDitemukan) as galat:
        cek_gratis.mulai(kon, ID_B, anak, "guru-b", True, SEKARANG)

    assert _keadaan(kon) == awal == (0, 0, 0, 0)
    assert NAMA_ANAK not in str(galat.value) and ID_B not in str(galat.value)


@pytest.mark.parametrize("siswa_id,pemilik", [(9999, "guru-a"), ("1", "guru-a"), (None, "guru-a"),
                                              (True, "guru-a"), (1, ""), (1, None), (1, "GURU-A")])
def test_mulai_anak_tak_ada_atau_masukan_aneh_sama_dengan_bukan_pemilik(kon, siswa_id, pemilik):
    tambah_anak(kon, NAMA_ANAK, "guru-a", 4)

    with pytest.raises(cek_gratis.CekTidakDitemukan):
        cek_gratis.mulai(kon, ID_A, siswa_id, pemilik, True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_mulai_pesan_bukan_pemilik_identik_dengan_anak_tak_ada(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    with pytest.raises(cek_gratis.CekTidakDitemukan) as lain:
        cek_gratis.mulai(kon, ID_B, anak, "guru-b", True, SEKARANG)
    with pytest.raises(cek_gratis.CekTidakDitemukan) as hilang:
        cek_gratis.mulai(kon, ID_B, anak + 100, "guru-b", True, SEKARANG)
    assert str(lain.value) == str(hilang.value)


def test_mulai_bukan_pemilik_tidak_membocorkan_keberadaan_cek(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    mulai_cek(kon, ID_A, anak, "guru-a")
    awal = _keadaan(kon)

    with pytest.raises(cek_gratis.CekTidakDitemukan):
        cek_gratis.mulai(kon, ID_B, anak, "guru-b", True, SEKARANG)

    assert _keadaan(kon) == awal


def test_mulai_id_akun_lain_untuk_anak_yang_sudah_punya_cek_ditolak(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    mulai_cek(kon, ID_A, anak, "guru-a")
    awal = _keadaan(kon)

    with pytest.raises(cek_gratis.CekTidakDitemukan):
        cek_gratis.mulai(kon, ID_B, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == awal


@pytest.mark.parametrize("id_akun", [None, "", "akun_xyz", "akun_" + "A" * 32, "x" * 37, 5])
def test_mulai_id_akun_tidak_sah_ditolak_tanpa_menulis(kon, id_akun):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    with pytest.raises(ValueError):
        cek_gratis.mulai(kon, id_akun, anak, "guru-a", True, SEKARANG)
    assert _keadaan(kon) == (0, 0, 0, 0)


@pytest.mark.parametrize("waktu", [None, "bukan waktu", 17])
def test_mulai_waktu_tidak_sah_ditolak_tanpa_menulis(kon, waktu):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    with pytest.raises(ValueError):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, waktu)
    assert _keadaan(kon) == (0, 0, 0, 0)


# --- mulai: bentuk sesi -----------------------------------------------------

@pytest.mark.parametrize("kelas", [3, 4, 5, 6])
def test_mulai_kelas_3_sampai_6_membuat_sesi_pg_15_soal_tiga_topik(kon, kelas):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", kelas)

    hasil = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert hasil["baru"] is True
    sesi = kon.execute("SELECT * FROM sesi WHERE id = ?", (hasil["sesi_id"],)).fetchone()
    assert sesi["topik"] == "gabungan:pola-bilangan,statistika,geometri-datar"
    assert (sesi["level"], sesi["tujuan"], sesi["jenis"], sesi["mode"]) == ("P%d" % kelas, "bebas", "biasa", "drill")
    assert (sesi["format_jawaban"], sesi["timer_mode"], sesi["putaran_id"]) == ("pilihan_ganda", "tanpa", None)
    peta = cek_gratis._peta_template_ke_topik()
    per_topik = {}
    for baris in database.isi_sesi(kon, hasil["sesi_id"]):
        per_topik[peta[baris["template_id"]]] = per_topik.get(peta[baris["template_id"]], 0) + 1
    assert per_topik == {"pola-bilangan": 5, "statistika": 5, "geometri-datar": 5}
    cek = kon.execute("SELECT * FROM cek_gratis").fetchone()
    assert (cek["siswa_id"], cek["id_akun"], cek["sesi_id"]) == (anak, ID_A, hasil["sesi_id"])
    assert (cek["versi_notice"], cek["jumlah_soal"], cek["setuju_pada"], cek["dibuat"]) == ("v1", 15, SEKARANG, SEKARANG)
    assert (cek["selesai_pada"], cek["skor"], cek["kategori"], cek["ringkasan"], cek["bahan_dihapus_pada"]) == (None,) * 5


@pytest.mark.parametrize("kelas", [1, 2])
def test_mulai_kelas_1_2_satu_topik_dasar_bila_materi_dasar_aktif(kon, monkeypatch, kelas):
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", kelas)

    hasil = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    sesi = kon.execute("SELECT * FROM sesi WHERE id = ?", (hasil["sesi_id"],)).fetchone()
    assert (sesi["topik"], sesi["level"], sesi["tujuan"], sesi["format_jawaban"]) == (
        "bilangan-dasar", "P%d" % kelas, "bebas", "pilihan_ganda")
    assert len(database.isi_sesi(kon, hasil["sesi_id"])) == 15


@pytest.mark.parametrize("kelas", [1, 2])
def test_mulai_kelas_1_2_tanpa_sakelar_materi_dasar_ditolak_jujur(kon, kelas):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", kelas)

    with pytest.raises(cek_gratis.CekBelumTersedia, match="belum tersedia untuk kelas ini"):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_mulai_kelas_kosong_ditolak_tanpa_menulis(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", None)

    with pytest.raises(ValueError, match="belum diisi"):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_mulai_kelas_di_luar_enam_ditolak_tanpa_menulis(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    kon.execute("PRAGMA ignore_check_constraints = ON")
    kon.execute("UPDATE profil_belajar SET kelas_sekolah = 8 WHERE siswa_id = ?", (anak,))
    kon.execute("PRAGMA ignore_check_constraints = OFF")

    with pytest.raises(ValueError, match="kelas 1 sampai 6"):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_mulai_tanpa_seed_memakai_seed_acak_dan_tetap_berhasil(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    hasil = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)
    assert hasil["baru"] is True and hitung(kon, "sesi_soal") == 15


# --- mulai: satu cek per anak ----------------------------------------------

def test_mulai_dua_kali_idempoten_tanpa_sesi_kedua(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    pertama = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)
    awal = _keadaan(kon)

    kedua = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, "2026-11-19T10:00:00")

    assert kedua == {"sesi_id": pertama["sesi_id"], "baru": False}
    assert _keadaan(kon) == awal == (1, 1, 15, 0)
    assert kon.execute("SELECT dibuat FROM cek_gratis").fetchone()[0] == SEKARANG


def test_unique_siswa_di_basis_data(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    mulai_cek(kon, ID_A, anak, "guru-a")

    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(
            """INSERT INTO cek_gratis(siswa_id, id_akun, setuju_pada, versi_notice, dibuat)
               VALUES (?, ?, 't', 'v1', 't')""", (anak, ID_A))

    assert hitung(kon, "cek_gratis") == 1


def test_balapan_unique_membatalkan_sesi_baru_dan_mengembalikan_cek_yang_ada(kon, monkeypatch):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    pertama = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)
    asli = cek_gratis._baris_siswa
    panggilan = []

    def luput_sekali(koneksi, siswa_id):
        panggilan.append(1)
        return None if len(panggilan) == 1 else asli(koneksi, siswa_id)

    monkeypatch.setattr(cek_gratis, "_baris_siswa", luput_sekali)

    hasil = cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert hasil == {"sesi_id": pertama["sesi_id"], "baru": False}
    assert len(panggilan) == 2
    assert _keadaan(kon) == (1, 1, 15, 0)


# --- mulai: jalur gagal -----------------------------------------------------

def test_galat_saat_buat_sesi_tidak_meninggalkan_baris(kon, monkeypatch):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)

    def gagal(*args, **kwargs):
        raise RuntimeError("generator rusak")

    monkeypatch.setattr(database, "buat_sesi_gabungan", gagal)

    with pytest.raises(RuntimeError):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_galat_setelah_sesi_terbentuk_membatalkan_sesinya(kon, monkeypatch):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    asli = database.buat_sesi_gabungan

    def terbentuk_lalu_gagal(*args, **kwargs):
        asli(*args, **kwargs)
        raise RuntimeError("putus setelah sesi dibuat")

    monkeypatch.setattr(database, "buat_sesi_gabungan", terbentuk_lalu_gagal)

    with pytest.raises(RuntimeError):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_gagal_menulis_baris_cek_membatalkan_sesi_yang_baru_dibuat(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    kon.execute("""CREATE TRIGGER tolak_cek BEFORE INSERT ON cek_gratis
                   BEGIN SELECT RAISE(ABORT, 'gagal sengaja'); END""")

    with pytest.raises(sqlite3.IntegrityError):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


def test_komposisi_tidak_lengkap_gagal_tanpa_baris(kon, monkeypatch):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4)
    asli = database.buat_sesi_gabungan

    def kurang_soal(koneksi, siswa_id, **kwargs):
        return asli(koneksi, siswa_id, **{**kwargs, "jumlah_soal": 9})

    monkeypatch.setattr(database, "buat_sesi_gabungan", kurang_soal)

    with pytest.raises(ValueError, match="gagal disusun"):
        cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG)

    assert _keadaan(kon) == (0, 0, 0, 0)


# --- mulai: tidak menyentuh tingkat dan siklus -------------------------------

def test_cek_tidak_mengubah_tingkat_dan_tidak_menulis_bukti_siklus(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", 4, tingkat="P6")
    siswa_awal = tuple(kon.execute("SELECT * FROM siswa WHERE id = ?", (anak,)).fetchone())
    bukti_awal = {t: hitung(kon, t) for t in TABEL_BUKTI_SIKLUS}

    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)
    tandai_selesai(kon, sesi_id)
    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True

    assert tuple(kon.execute("SELECT * FROM siswa WHERE id = ?", (anak,)).fetchone()) == siswa_awal
    assert kon.execute("SELECT tingkat FROM siswa WHERE id = ?", (anak,)).fetchone()[0] == "P6"
    assert {t: hitung(kon, t) for t in TABEL_BUKTI_SIKLUS} == bukti_awal
    sesi = kon.execute("SELECT tujuan, jenis, putaran_id, dikonfirmasi_guru FROM sesi").fetchone()
    assert tuple(sesi) == ("bebas", "biasa", None, None)


# --- galat tidak membocorkan data ------------------------------------------

def test_pesan_galat_tidak_memuat_nama_anak_id_akun_atau_skor(kon):
    anak = tambah_anak(kon, NAMA_ANAK, "guru-a", None)
    galat = []
    for panggil in (
        lambda: cek_gratis.mulai(kon, ID_A, anak, "guru-a", False, SEKARANG),
        lambda: cek_gratis.mulai(kon, ID_A, anak, "guru-b", True, SEKARANG),
        lambda: cek_gratis.mulai(kon, ID_A, anak, "guru-a", True, SEKARANG),
    ):
        with pytest.raises(Exception) as e:
            panggil()
        galat.append(str(e.value))
    assert len(galat) == 3
    assert not any(NAMA_ANAK in g or ID_A in g or "guru-a" in g for g in galat)

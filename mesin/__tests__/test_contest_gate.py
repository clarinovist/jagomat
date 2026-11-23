"""Gerbang fitur Latihan Lomba: bawaan mati; hanya nilai persis "1" yang menyalakan."""
import datetime
import pytest

import contest_gate as G


def test_bawaan_mati_bila_env_tidak_diatur(monkeypatch):
    monkeypatch.delenv("OSN_LOMBA", raising=False)
    assert G.aktif() is False


def test_nilai_satu_menyalakan(monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    assert G.aktif() is True


@pytest.mark.parametrize("nilai", ["", "0", "2", "true", "ya", "01", "on"])
def test_nilai_lain_tetap_mati(monkeypatch, nilai):
    monkeypatch.setenv("OSN_LOMBA", nilai)
    assert G.aktif() is False


# --- sakelar admin menggantikan env sebagai sumber utama -------------------------------------

import sqlite3
from contextlib import closing

import feature_switch

SEED = {nama: False for nama in feature_switch.NAMA_SAKELAR}


@pytest.fixture
def berkas_sakelar(tmp_path, monkeypatch):
    path = tmp_path / "sakelar.db"
    monkeypatch.setenv(feature_switch.ENV_BERKAS_DB, str(path))
    feature_switch.bersihkan_cache()
    yield path
    feature_switch.bersihkan_cache()


def _atur(path, aktif):
    feature_switch.ubah("OSN_LOMBA", aktif, actor_id="uji", revisi_diharapkan=1, seed=SEED, path=path)


def test_tanpa_berkas_sakelar_gerbang_mengikuti_env(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    assert G.aktif() is True
    feature_switch.bersihkan_cache()
    monkeypatch.setenv("OSN_LOMBA", "0")
    assert G.aktif() is False


def test_sakelar_hidup_menyalakan_gerbang_walau_env_mati(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")
    _atur(berkas_sakelar, True)
    assert G.aktif() is True


def test_sakelar_mati_mematikan_gerbang_walau_env_menyala(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    _atur(berkas_sakelar, False)
    feature_switch.bersihkan_cache()
    assert G.aktif() is False


def test_berkas_sakelar_rusak_mematikan_gerbang_walau_env_menyala(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    berkas_sakelar.write_text("bukan sqlite")
    assert G.aktif() is False


def test_perubahan_sakelar_berlaku_setelah_cache_dibersihkan(berkas_sakelar, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")
    _atur(berkas_sakelar, True)
    assert G.aktif() is True
    feature_switch.ubah("OSN_LOMBA", False, actor_id="uji", revisi_diharapkan=2, seed=SEED, path=berkas_sakelar)
    assert G.aktif() is False        # ubah() membersihkan cache sendiri


# --- gerbang per anak: sakelar induk DAN penugasan Guru ----------------------------------------

import contest_assignment_store as AS
import database

SEKARANG = 1_800_000_000


@pytest.fixture
def kon(tmp_path):
    path = tmp_path / "lomba.db"
    database.siapkan(path)
    with database.buka(path) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Satu", pemilik="guru")


@pytest.fixture
def anak_lain(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Dua", pemilik="guru")


def _tugaskan(kon, siswa_id, aktif=True):
    AS.atur(kon, siswa_id, aktif=aktif, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None, durasi_simulasi_detik=None,
            tanggal_lomba=datetime.date(2026, 12, 12), nama_lomba=None, sekarang=SEKARANG, oleh="guru-uji")


def test_aktif_untuk_hidup_bila_induk_hidup_dan_penugasan_aktif(kon, anak, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    _tugaskan(kon, anak)

    assert G.aktif_untuk(kon, anak) is True


def test_aktif_untuk_mati_tanpa_baris_penugasan_walau_induk_hidup(kon, anak, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")

    assert G.aktif_untuk(kon, anak) is False


def test_aktif_untuk_mati_bila_penugasan_dimatikan_walau_induk_hidup(kon, anak, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    _tugaskan(kon, anak, aktif=False)

    assert G.aktif_untuk(kon, anak) is False


def test_aktif_untuk_mati_bila_induk_mati_walau_penugasan_aktif(kon, anak, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "0")
    _tugaskan(kon, anak)

    assert G.aktif_untuk(kon, anak) is False


def test_aktif_untuk_hanya_untuk_anak_yang_ditugaskan(kon, anak, anak_lain, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    _tugaskan(kon, anak)

    assert (G.aktif_untuk(kon, anak), G.aktif_untuk(kon, anak_lain)) == (True, False)


def test_aktif_untuk_fail_closed_bila_tabel_penugasan_tidak_ada(kon, anak, monkeypatch):
    monkeypatch.setenv("OSN_LOMBA", "1")
    kon.execute("DROP TABLE lomba_penugasan")

    assert G.aktif_untuk(kon, anak) is False


def test_aktif_untuk_tidak_menelan_galat_basis_lain(monkeypatch):
    import sqlite3

    monkeypatch.setenv("OSN_LOMBA", "1")
    salah = sqlite3.connect(":memory:")
    salah.row_factory = sqlite3.Row
    salah.execute("CREATE TABLE lomba_penugasan (x INTEGER)")   # tabel ada, kolom salah -> galat lain

    with pytest.raises(sqlite3.OperationalError):
        G.aktif_untuk(salah, 1)

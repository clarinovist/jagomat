"""Dukungan F3 pada laporan Guru dan beranda murid: terbit_terbaru, penutup tanpa batas berlaku, tautan beranda."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import database
import parent_report_page as halaman
import orang_tua_pages
import parent_report_store as store
import student_pages


@pytest.fixture()
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "laporan.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    return jalur


def _laporan(kon, siswa, catatan, *, terbit, kini=1_790_000_000):
    lap = store.buat_draf(kon, siswa, "2026-11-01", "2026-11-15", {"topik": ["Pecahan"], "langkah": "Latih."})
    store.simpan_catatan(kon, siswa, lap, catatan)
    if terbit:
        store.terbitkan(kon, siswa, lap, "Bu Guru", sekarang=kini)
    return lap


def test_terbit_terbaru_none_tanpa_laporan_terbit(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik="guru")
        _laporan(kon, siswa, "draf", terbit=False)
        assert store.terbit_terbaru(kon, siswa) is None


def test_terbit_terbaru_memilih_id_terbesar_yang_terbit_dan_milik_anak_itu(db):
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "Anak A", "P4", pemilik="guru")
        b = database.tambah_siswa(kon, "Anak B", "P4", pemilik="guru")
        _laporan(kon, a, "lama", terbit=True)
        _laporan(kon, a, "baru", terbit=True)
        _laporan(kon, a, "draf", terbit=False)
        _laporan(kon, b, "milik b", terbit=True)
        hasil = store.terbit_terbaru(kon, a)
    assert hasil["catatan"] == "baru" and hasil["nama"] == "Anak A" and hasil["guru"] == "Bu Guru"
    assert hasil["periode"] == ("2026-11-01", "2026-11-15") and hasil["diterbitkan"]
    assert hasil["isi"]["topik"] == ["Pecahan"]


def test_tautan_dicabut_menyembunyikan_laporan_dan_halaman_menampilkan_kalimat_kosong(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik="guru")
        _laporan(kon, siswa, "CATATAN RAHASIA", terbit=True)
        assert store.cabut_tautan(kon, siswa, sekarang=1_790_000_100) is True
        hasil = store.terbit_terbaru(kon, siswa)
    assert hasil is None
    blok = orang_tua_pages._blok_laporan(hasil)
    assert "Belum ada laporan dari Guru." in blok and "CATATAN RAHASIA" not in blok


def test_tautan_kedaluwarsa_tidak_menyembunyikan_laporan(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik="guru")
        _laporan(kon, siswa, "MASIH TAMPIL", terbit=True, kini=1_790_000_000)
        lewat = 1_790_000_000 + 365 * 24 * 3600
        assert store.tautan_aktif(kon, siswa, sekarang=lewat) is None  # tautan memang sudah mati
        hasil = store.terbit_terbaru(kon, siswa)
    assert hasil is not None and hasil["catatan"] == "MASIH TAMPIL"


def test_laporan_tampil_lagi_setelah_tautan_diganti_atau_terbit_baru(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik="guru")
        lama = _laporan(kon, siswa, "LAMA", terbit=True)
        store.cabut_tautan(kon, siswa, sekarang=1_790_000_100)
        assert store.terbit_terbaru(kon, siswa) is None
        store.ganti_tautan(kon, siswa, lama, sekarang=1_790_000_200)
        assert store.terbit_terbaru(kon, siswa)["catatan"] == "LAMA"
        store.cabut_tautan(kon, siswa, sekarang=1_790_000_300)
        assert store.terbit_terbaru(kon, siswa) is None
        _laporan(kon, siswa, "BARU", terbit=True, kini=1_790_000_400)
        assert store.terbit_terbaru(kon, siswa)["catatan"] == "BARU"


def test_cabut_tautan_satu_anak_tidak_menyembunyikan_laporan_anak_lain(db):
    with database.buka(db) as kon:
        a = database.tambah_siswa(kon, "Anak A", "P4", pemilik="guru")
        b = database.tambah_siswa(kon, "Anak B", "P4", pemilik="guru")
        _laporan(kon, a, "A", terbit=True)
        _laporan(kon, b, "B", terbit=True)
        store.cabut_tautan(kon, a, sekarang=1_790_000_100)
        assert store.terbit_terbaru(kon, a) is None
        assert store.terbit_terbaru(kon, b)["catatan"] == "B"


def _isi(**tambahan):
    return halaman.isi_laporan(nama="Anak", isi={"topik": ["Pecahan"]}, catatan="c", guru="Bu Guru",
                               periode=("2026-11-01", "2026-11-15"), diterbitkan="2026-11-20 10:00:00", **tambahan)


def test_jalur_token_tetap_pratinjau_bila_tanpa_batas_dan_berlaku_bila_ada():
    assert "Pratinjau" in _isi()
    assert "Berlaku sampai" in _isi(kedaluarsa=1_800_000_000)


def test_tanpa_batas_berlaku_hanya_menulis_tanggal_terbit():
    isi = _isi(tanpa_batas_berlaku=True)
    assert "Pratinjau" not in isi and "Berlaku sampai" not in isi and "Tautan ini" not in isi
    assert "Diterbitkan 20 November 2026" in isi


def test_beranda_tombol_orang_tua_default_mati_dan_byte_identik(db):
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P4", pemilik="guru")
        polos = student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak")
        mati = student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak", orang_tua=False)
        hidup = student_pages.halaman_daftar_sesi_baru(kon, siswa, "Anak", orang_tua=True)
    assert polos == mati and b"Untuk Ayah/Bunda" not in polos
    assert hidup.count(b'href="/murid/orang-tua"') == 1 and b"Untuk Ayah/Bunda" in hidup

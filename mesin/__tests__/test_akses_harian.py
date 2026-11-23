"""Kontrak akses Latihan Harian: gratis / les / langganan (kait) dan sakelar LATIHAN_HARIAN (data sintetis)."""
import pytest

import akses_harian as ah
import database
import lembaga_store


@pytest.fixture
def kon(tmp_path, monkeypatch):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.delenv("LATIHAN_HARIAN", raising=False)
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))
    with database.buka(jalur) as k:
        lembaga_store.buat_lembaga(k, nama="Jagomat", pemilik="koordinator-uji")
        k.execute("INSERT INTO anggota_lembaga (lembaga_id, guru) VALUES (1, 'guru-anggota')")
        yield k


def _anak(kon, pemilik):
    return kon.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES ('Anak Uji', 'P3', ?)",
                       (pemilik,)).lastrowid


def test_batas_gratis_satu_sesi_per_hari():
    assert ah.BATAS_GRATIS_PER_HARI == 1


def test_sakelar_bawaan_mati_dan_hanya_satu_menyalakan(monkeypatch):
    monkeypatch.delenv("LATIHAN_HARIAN", raising=False)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", "/tidak/ada/sakelar.db")
    assert ah.aktif() is False
    monkeypatch.setenv("LATIHAN_HARIAN", "1")
    assert ah.aktif() is True
    monkeypatch.setenv("LATIHAN_HARIAN", "true")
    assert ah.aktif() is False


def test_anak_koordinator_gratis(kon):
    assert ah.akses(kon, _anak(kon, "koordinator-uji"), "2026-11-23") == ah.Akses(False, "gratis", None)


def test_anak_guru_anggota_murid_les_tanpa_batas(kon):
    assert ah.akses(kon, _anak(kon, "guru-anggota"), "2026-11-23") == ah.Akses(True, "les", None)


def test_anak_guru_bukan_anggota_gratis(kon):
    assert ah.akses(kon, _anak(kon, "guru-luar"), "2026-11-23").sumber == "gratis"


@pytest.mark.parametrize("nilai", ["", "2", "abc"])
def test_lembaga_antrean_tidak_terkonfigurasi_bukan_les(kon, monkeypatch, nilai):
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", nilai)
    assert ah.akses(kon, _anak(kon, "guru-anggota"), "2026-11-23").sumber == "gratis"


def test_tabel_harian_akses_absen_tidak_error(kon):
    """DB lama tanpa tabel F5: langganan = tidak ada, bukan galat (tabel dibuang dulu karena skema F5 sudah terpasang)."""
    for (nama,) in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name GLOB 'harian_*'").fetchall():
        kon.execute("DROP TRIGGER %s" % nama)
    kon.execute("DROP TABLE harian_akses")
    ada = kon.execute("SELECT 1 FROM sqlite_master WHERE name='harian_akses'").fetchone()
    assert ada is None
    assert ah.akses(kon, _anak(kon, "guru-luar"), "2026-11-23").tanpa_batas is False


def test_langganan_aktif_menang_atas_les(kon, monkeypatch):
    monkeypatch.setattr(ah, "_langganan_aktif", lambda k, s, n: "2026-12-23")
    assert ah.akses(kon, _anak(kon, "guru-luar"), "2026-11-23") == ah.Akses(True, "langganan", "2026-12-23")

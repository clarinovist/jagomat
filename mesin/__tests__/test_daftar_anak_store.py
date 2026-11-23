"""Persetujuan daftar anak dan PIN tirai orang tua: skema aditif, simpan/periksa/hapus (data sintetis)."""
import sqlite3

import pytest

import cek_gratis_skor
import daftar_anak_store as das
import database
import pin_orang_tua_store as pin


@pytest.fixture
def kon(tmp_path):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        k.execute("INSERT INTO siswa(nama, tingkat, pemilik) VALUES ('Anak Uji', 'P3', 'koordinator-uji')")
        yield k


def _siswa_id(kon):
    return kon.execute("SELECT id FROM siswa").fetchone()[0]


def test_skema_dibuat_aditif_dan_idempoten(tmp_path):
    jalur = tmp_path / "b.db"
    database.siapkan(jalur)
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        tabel = {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"persetujuan_daftar_anak", "pin_orang_tua"} <= tabel


def test_persetujuan_memakai_versi_notice_yang_sama_dengan_cek_gratis(kon):
    das.catat_persetujuan(kon, _siswa_id(kon), 1800000000)
    versi, waktu = das.ambil_persetujuan(kon, _siswa_id(kon))
    assert versi == cek_gratis_skor.VERSI_NOTICE
    assert waktu == "2027-01-15T08:00:00"


def test_persetujuan_kedua_untuk_anak_sama_ditolak(kon):
    das.catat_persetujuan(kon, _siswa_id(kon), 1800000000)
    with pytest.raises(sqlite3.IntegrityError):
        das.catat_persetujuan(kon, _siswa_id(kon), 1800000001)


def test_persetujuan_tanpa_anak_ditolak_fk(kon):
    with pytest.raises(sqlite3.IntegrityError):
        das.catat_persetujuan(kon, 9999, 1800000000)


@pytest.mark.parametrize("nilai", ["", "123", "12345", "12a4", "١٢٣٤", " 123", None, 1234, "1234\n"])
def test_pin_tidak_sah_ditolak(kon, nilai):
    assert not pin.pin_sah(nilai)
    with pytest.raises(ValueError):
        pin.simpan(kon, _siswa_id(kon), nilai, 1800000000)
    assert not pin.ada_pin(kon, _siswa_id(kon))


def test_pin_tersimpan_sebagai_hash_dan_periksa_benar_salah(kon):
    sid = _siswa_id(kon)
    pin.simpan(kon, sid, "4821", 1800000000)
    assert pin.ada_pin(kon, sid)
    baris = tuple(kon.execute("SELECT garam, kunci, iterasi FROM pin_orang_tua").fetchone())
    assert "4821" not in "".join(str(x) for x in baris)
    assert pin.periksa_pin(kon, sid, "4821") is True
    assert pin.periksa_pin(kon, sid, "4822") is False
    assert pin.periksa_pin(kon, sid, "") is False
    assert pin.periksa_pin(kon, sid, None) is False


def test_periksa_tanpa_pin_tersimpan_false(kon):
    assert pin.periksa_pin(kon, _siswa_id(kon), "1234") is False


def test_ganti_pin_menaikkan_diperbarui_dan_menjaga_dibuat(kon):
    sid = _siswa_id(kon)
    pin.simpan(kon, sid, "1111", 1800000000)
    pin.simpan(kon, sid, "2222", 1800000100)
    dibuat, diperbarui = kon.execute("SELECT dibuat, diperbarui FROM pin_orang_tua").fetchone()
    assert dibuat < diperbarui
    assert pin.periksa_pin(kon, sid, "2222") and not pin.periksa_pin(kon, sid, "1111")
    assert kon.execute("SELECT COUNT(*) FROM pin_orang_tua").fetchone()[0] == 1


def test_hapus_pin(kon):
    sid = _siswa_id(kon)
    assert pin.hapus(kon, sid) is False
    pin.simpan(kon, sid, "1111", 1800000000)
    assert pin.hapus(kon, sid) is True
    assert not pin.ada_pin(kon, sid) and pin.periksa_pin(kon, sid, "1111") is False


def test_hash_dua_pin_sama_berbeda_garam(kon):
    assert pin.buat_hash_pin("1234")["garam"] != pin.buat_hash_pin("1234")["garam"]


def test_simpan_hash_menolak_bentuk_salah(kon):
    with pytest.raises(ValueError):
        pin.simpan_hash(kon, _siswa_id(kon), {"garam": "aa"}, 1800000000)


def test_pin_ikut_terhapus_bersama_anak(kon):
    sid = _siswa_id(kon)
    pin.simpan(kon, sid, "1111", 1800000000)
    das.catat_persetujuan(kon, sid, 1800000000)
    kon.execute("DELETE FROM siswa WHERE id=?", (sid,))
    assert kon.execute("SELECT COUNT(*) FROM pin_orang_tua").fetchone()[0] == 0
    assert kon.execute("SELECT COUNT(*) FROM persetujuan_daftar_anak").fetchone()[0] == 0

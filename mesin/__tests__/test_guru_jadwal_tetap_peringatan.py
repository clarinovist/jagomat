"""Peringatan jadwal tetap guru: tanda "di luar jam" per pertemuan dan slot. Baca saja, tanpa tulis berkas."""
import logging
from pathlib import Path

import pytest

import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as dasar
import guru_jadwal_tetap_peringatan as pr

ID_GURU = "akun_" + "a" * 32
ID_ADMIN = "akun_" + "c" * 32
WAKTU_DIBUAT = "2026-11-26T00:00:00"
SENIN_08_10 = "1@480-600"                 # Senin 08.00-10.00 WIB
SENIN_DAN_KAMIS_08_10 = "1@480-600;4@480-600"
SENIN_0800_WIB = "2026-11-30T01:00:00"    # Senin 08.00 WIB dalam UTC naif
SENIN_0930_WIB = "2026-11-30T02:30:00"    # Senin 09.30 WIB
SELASA_0900_WIB = "2026-12-01T02:00:00"   # Selasa 09.00 WIB
SENIN_1500_WIB_NAIF = "2026-11-30T08:00:00"  # 08.00 UTC = 15.00 WIB, harus dibaca sebagai UTC
MENIT = 60


@pytest.fixture()
def gerbang_menyala(monkeypatch, tmp_path):
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", True)
    berkas = tmp_path / "guru-jadwal-tetap.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    return berkas


def _tetapkan(blok, guru=ID_GURU):
    dasar.tetapkan_admin(guru_akun=guru, blok=blok, admin_akun=ID_ADMIN, dibuat=WAKTU_DIBUAT)


def _sesi(mulai, *, id_=1, menit=MENIT, dibatalkan=0):
    return {"id": id_, "ke": id_, "mulai": mulai, "menit": menit, "dibatalkan": dibatalkan}


def _bendera(sesi, guru=ID_GURU):
    return [s[pr.KUNCI_LUAR_JAM] for s in pr.tandai(sesi, guru)]


# --- gerbang dan guru tanpa jadwal ------------------------------------------------------------

def test_gerbang_mati_tanpa_tanda_dan_tanpa_membaca_dasar(monkeypatch, tmp_path):
    # Arrange
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", False)
    monkeypatch.setenv(dasar.ENV_DB, str(tmp_path / "guru-jadwal-tetap.db"))

    def _tidak_boleh_dibaca(*_args, **_kwargs):
        raise AssertionError("gerbang mati tidak boleh membaca jadwal tetap")

    monkeypatch.setattr(dasar, "aktif", _tidak_boleh_dibaca)

    # Act
    hasil = pr.tandai([_sesi(SENIN_0930_WIB)], ID_GURU)

    # Assert
    assert pr.blok_aktif(ID_GURU) is None
    assert hasil == [{**_sesi(SENIN_0930_WIB), pr.KUNCI_LUAR_JAM: False}]
    assert pr.slot_luar_jam(ID_GURU, SENIN_0800_WIB) is False


def test_guru_tanpa_jadwal_tetap_aktif_tanpa_tanda_dan_tanpa_berkas(gerbang_menyala):
    # Act
    blok = pr.blok_aktif(ID_GURU)

    # Assert
    assert blok is None
    assert _bendera([_sesi(SENIN_0930_WIB)]) == [False]
    assert pr.slot_luar_jam(ID_GURU, SENIN_0800_WIB) is False
    assert not Path(gerbang_menyala).exists()


def test_guru_akun_kosong_tidak_menyentuh_dasar(gerbang_menyala, monkeypatch):
    monkeypatch.setattr(dasar, "aktif", lambda *_a, **_k: pytest.fail("tidak boleh dipanggil"))

    assert pr.blok_aktif(None) is None
    assert _bendera([_sesi(SENIN_0930_WIB)], guru=None) == [False]


# --- pertemuan dalam dan di luar jam ----------------------------------------------------------

def test_senin_0800_dalam_jam_dan_senin_0930_di_luar_jam(gerbang_menyala):
    # Arrange
    _tetapkan(SENIN_08_10)
    sesi = [_sesi(SENIN_0800_WIB, id_=1), _sesi(SENIN_0930_WIB, id_=2)]

    # Act
    hasil = _bendera(sesi)

    # Assert
    assert hasil == [False, True]


def test_selasa_di_luar_jam_saat_blok_hanya_senin(gerbang_menyala):
    _tetapkan(SENIN_08_10)

    assert _bendera([_sesi(SELASA_0900_WIB)]) == [True]


def test_mulai_dibaca_sebagai_utc_lalu_dikonversi_ke_wib(gerbang_menyala):
    # Arrange: 08.00 UTC Senin = 15.00 WIB Senin, jelas di luar blok 08.00-10.00 WIB
    _tetapkan(SENIN_08_10)

    # Act
    hasil = _bendera([_sesi(SENIN_1500_WIB_NAIF)])

    # Assert
    assert hasil == [True]


def test_blok_kosong_membuat_semua_pertemuan_di_luar_jam(gerbang_menyala):
    _tetapkan("")
    sesi = [_sesi(SENIN_0800_WIB, id_=1), _sesi(SELASA_0900_WIB, id_=2)]

    assert pr.blok_aktif(ID_GURU) == ()
    assert _bendera(sesi) == [True, True]


def test_pertemuan_dibatalkan_tidak_pernah_ditandai(gerbang_menyala):
    _tetapkan(SENIN_08_10)

    hasil = _bendera([_sesi(SELASA_0900_WIB, dibatalkan=1)])

    assert hasil == [False]


def test_tandai_tidak_mengubah_dict_asal(gerbang_menyala):
    _tetapkan(SENIN_08_10)
    asal = [_sesi(SELASA_0900_WIB)]

    hasil = pr.tandai(asal, ID_GURU)

    assert "luar_jam" not in asal[0]
    assert hasil[0]["luar_jam"] is True


def test_tandai_dengan_blok_tidak_membaca_dasar(gerbang_menyala, monkeypatch):
    # Arrange: blok diberikan langsung; dasar tidak boleh dibaca lagi
    blok = aturan.urai_blok(SENIN_08_10)

    def _tidak_boleh_dibaca(*_args, **_kwargs):
        raise AssertionError("tandai_dengan_blok tidak boleh membaca dasar")

    monkeypatch.setattr(dasar, "aktif", _tidak_boleh_dibaca)

    # Act
    hasil = pr.tandai_dengan_blok([_sesi(SENIN_0930_WIB)], blok)

    # Assert
    assert [s["luar_jam"] for s in hasil] == [True]


# --- galat baca ------------------------------------------------------------------------------

def test_galat_tetap_tanpa_tanda_tanpa_lemparan_dan_log_hanya_nama_tipe(gerbang_menyala, monkeypatch, caplog):
    # Arrange
    def _galat_baca(*_args, **_kwargs):
        raise dasar.GalatTetap(dasar.KIND_UMUM, "rahasia: /data/guru-jadwal-tetap.db")

    monkeypatch.setattr(dasar, "aktif", _galat_baca)

    # Act
    with caplog.at_level(logging.WARNING, logger=pr.__name__):
        hasil = _bendera([_sesi(SENIN_0930_WIB)])

    # Assert
    assert hasil == [False]
    assert pr.blok_aktif(ID_GURU) is None
    assert "GalatTetap" in caplog.text
    assert "rahasia" not in caplog.text and "/data/" not in caplog.text


def test_blok_rusak_di_berkas_tanpa_tanda(gerbang_menyala, monkeypatch):
    monkeypatch.setattr(dasar, "aktif", lambda *_a, **_k: {"blok": "bukan-blok-kanonik"})

    assert pr.blok_aktif(ID_GURU) is None
    assert _bendera([_sesi(SENIN_0930_WIB)]) == [False]


# --- slot Private (awal delapan pertemuan) ----------------------------------------------------

def test_slot_dengan_satu_pertemuan_di_luar_jam_memicu_tanda(gerbang_menyala):
    # Arrange: Senin 08.00 mencakup pertemuan Senin (offset 0) tetapi Kamis (offset 3) di luar blok
    _tetapkan(SENIN_08_10)

    # Act
    hasil = pr.slot_luar_jam(ID_GURU, SENIN_0800_WIB)

    # Assert
    assert hasil is True


def test_slot_dengan_seluruh_delapan_pertemuan_di_dalam_jam_tanpa_tanda(gerbang_menyala):
    # Arrange: Senin dan Kamis 08.00-10.00 mencakup delapan pertemuan (Senin/Kamis bergantian)
    _tetapkan(SENIN_DAN_KAMIS_08_10)

    assert pr.slot_luar_jam(ID_GURU, SENIN_0800_WIB) is False


def test_slot_guru_tanpa_jadwal_tidak_ditandai(gerbang_menyala):
    assert pr.slot_luar_jam(ID_GURU, SENIN_0800_WIB) is False


def test_slot_dengan_blok_yang_sudah_dibaca(gerbang_menyala):
    blok = aturan.urai_blok(SENIN_08_10)

    assert pr.slot_luar_jam_dengan_blok(None, SENIN_0800_WIB) is False
    assert pr.slot_luar_jam_dengan_blok(blok, SENIN_0800_WIB) is True
    assert pr.slot_luar_jam_dengan_blok(aturan.urai_blok(SENIN_DAN_KAMIS_08_10), SENIN_0800_WIB) is False

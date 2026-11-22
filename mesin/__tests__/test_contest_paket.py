"""Paket Latihan Lomba sebagai konfigurasi: validasi, hari WIB, hitung mundur, dan sesi asal kumpul."""
import dataclasses
import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_paket as PK  # noqa: E402
import contest_session as S  # noqa: E402
import contest_store as K  # noqa: E402

# 2026-12-12 00:00 WIB = 2026-12-11 17:00 UTC
EPOCH_HARI_H_00_WIB = 1_797_008_400
DETIK_JAM = 3600
PAKET = PK.COREXIS_2026_L1


def _ubah(**perubahan):
    return dataclasses.replace(PAKET, **perubahan)


# --- isi paket dan keterkaitan dengan modul lain ---------------------------------------------------

def test_paket_aktif_adalah_corexis_dengan_nilai_yang_dikunci_tes_lama():
    assert PK.PAKET_AKTIF is PK.COREXIS_2026_L1
    assert (PAKET.id, PAKET.durasi_detik, PAKET.jumlah_soal, PAKET.jumlah_isian) == ("corexis_l1_matematika", 900, 10, 2)
    assert PAKET.tanggal_lomba == datetime.date(2026, 12, 12) and PAKET.target_harian == 2
    assert PAKET.nama_pendek == "Grand Final Corexis" and PAKET.tampil_hitung_mundur is True
    assert PAKET.jumlah_pg == 8 and PAKET.durasi_menit == 15


def test_store_dan_session_mengambil_nilai_dari_paket_aktif():
    assert K.PAKET_ID == PK.PAKET_AKTIF.id and K.DURASI_DETIK == PK.PAKET_AKTIF.durasi_detik
    assert S.JUMLAH_SOAL == PK.PAKET_AKTIF.jumlah_soal and S.JUMLAH_ISIAN == PK.PAKET_AKTIF.jumlah_isian


def test_paket_tidak_bisa_diubah_setelah_dibuat():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PAKET.target_harian = 3


@pytest.mark.parametrize("perubahan", [
    {"jumlah_soal": 9}, {"jumlah_soal": 11}, {"jumlah_isian": 10}, {"jumlah_isian": -1}, {"durasi_detik": 0},
    {"durasi_detik": -60}, {"target_harian": -1}, {"target_harian": 6}, {"id": ""}, {"nama": ""}, {"nama_pendek": ""},
])
def test_paket_tidak_sah_ditolak_saat_dibuat(perubahan):
    with pytest.raises(ValueError):
        _ubah(**perubahan)


@pytest.mark.parametrize("perubahan", [{"target_harian": 0}, {"target_harian": 5}, {"jumlah_isian": 0}, {"jumlah_isian": 9},
                                       {"tampil_hitung_mundur": False}])
def test_paket_pada_batas_yang_sah_diterima(perubahan):
    assert _ubah(**perubahan)


# --- awal hari WIB ---------------------------------------------------------------------------------

@pytest.mark.parametrize("epoch,harapan", [
    (EPOCH_HARI_H_00_WIB, EPOCH_HARI_H_00_WIB),
    (EPOCH_HARI_H_00_WIB + 1, EPOCH_HARI_H_00_WIB),
    (EPOCH_HARI_H_00_WIB - 1, EPOCH_HARI_H_00_WIB - 86_400),
    (EPOCH_HARI_H_00_WIB + 86_399, EPOCH_HARI_H_00_WIB),
    (EPOCH_HARI_H_00_WIB + 86_400, EPOCH_HARI_H_00_WIB + 86_400),
])
def test_awal_hari_wib_jatuh_tepat_pada_tengah_malam_wib(epoch, harapan):
    assert PK.awal_hari_wib(epoch) == harapan


def test_awal_hari_wib_berbeda_dari_awal_hari_utc():
    pukul_20_utc = EPOCH_HARI_H_00_WIB + 3 * DETIK_JAM          # 03.00 WIB hari H = 20.00 UTC hari sebelumnya

    assert PK.awal_hari_wib(pukul_20_utc) == EPOCH_HARI_H_00_WIB


# --- hari menuju lomba dan teks hitung mundur ---------------------------------------------------------

@pytest.mark.parametrize("sekarang,hari", [
    (EPOCH_HARI_H_00_WIB - 5 * 86_400, 5),
    (EPOCH_HARI_H_00_WIB - 1, 1),            # 23.59 WIB sehari sebelumnya
    (EPOCH_HARI_H_00_WIB - 86_400, 1),       # 00.00 WIB sehari sebelumnya
    (EPOCH_HARI_H_00_WIB - 86_401, 2),       # 23.59 WIB dua hari sebelumnya
    (EPOCH_HARI_H_00_WIB, 0),                # tepat tengah malam WIB hari H
    (EPOCH_HARI_H_00_WIB + 86_399, 0),       # 23.59 WIB hari H
    (EPOCH_HARI_H_00_WIB + 86_400, -1),
])
def test_hari_menuju_lomba_menghitung_hari_kalender_wib(sekarang, hari):
    assert PK.hari_menuju_lomba(PAKET, sekarang) == hari


def test_hari_menuju_lomba_memakai_tanggal_wib_bukan_utc():
    pukul_17_utc_hari_sebelum = EPOCH_HARI_H_00_WIB            # sudah 12 Des di WIB, masih 11 Des di UTC

    assert PK.hari_menuju_lomba(PAKET, pukul_17_utc_hari_sebelum) == 0


@pytest.mark.parametrize("sekarang,teks", [
    (EPOCH_HARI_H_00_WIB - 10 * 86_400, "Lomba tinggal 10 hari lagi"),
    (EPOCH_HARI_H_00_WIB - 86_400, "Lomba tinggal 1 hari lagi"),
    (EPOCH_HARI_H_00_WIB + 3600, "Hari ini lombanya. Semangat!"),
    (EPOCH_HARI_H_00_WIB + 86_400, ""),
    (EPOCH_HARI_H_00_WIB + 30 * 86_400, ""),
])
def test_teks_hitung_mundur_untuk_sebelum_hari_h_dan_sesudah_lomba(sekarang, teks):
    assert PK.teks_hitung_mundur(PAKET, sekarang) == teks


def test_teks_hitung_mundur_kosong_bila_paket_mematikannya():
    paket = _ubah(tampil_hitung_mundur=False)

    assert PK.teks_hitung_mundur(paket, EPOCH_HARI_H_00_WIB - 86_400) == ""
    assert PK.teks_hitung_mundur(paket, EPOCH_HARI_H_00_WIB + 60) == ""


# --- sesi asal kumpul ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("detik,terisi,asal", [
    (119, 10, True), (120, 10, False), (0, 0, True), (600, 2, True), (600, 3, False),
    (120, 3, False), (119, 3, True), (900, 10, False), (5, 10, True),
])
def test_asal_kumpul_bila_kurang_dari_120_detik_atau_terisi_kurang_dari_3(detik, terisi, asal):
    assert PK.asal_kumpul(detik, terisi) is asal


def test_batas_asal_kumpul_adalah_konstanta_bernama():
    assert (PK.BATAS_DETIK_ASAL_KUMPUL, PK.BATAS_TERISI_ASAL_KUMPUL) == (120, 3)


def test_konstanta_store_sama_dengan_paket_aktif():
    """`contest_store` sengaja memakai literal (kontrak persistensi rilis tidak boleh bergeser); nilainya dikunci sama."""
    import contest_store
    assert contest_store.DURASI_DETIK == PK.PAKET_AKTIF.durasi_detik
    assert contest_store.PAKET_ID == PK.PAKET_AKTIF.id
    assert contest_store.NOMOR_TERAKHIR == PK.PAKET_AKTIF.jumlah_soal


# --- dua mode sesi ----------------------------------------------------------------------------------------

def test_format_mode_latihan_dan_simulasi():
    latihan, simulasi = PAKET.format_mode(PK.MODE_LATIHAN), PAKET.format_mode(PK.MODE_SIMULASI)
    assert (latihan.jumlah_soal, latihan.jumlah_isian, latihan.durasi_menit, latihan.label) == (10, 2, 15, "Latihan")
    assert (simulasi.jumlah_soal, simulasi.jumlah_isian, simulasi.durasi_menit, simulasi.jumlah_pg) == (35, 5, 60, 30)
    assert simulasi.label == "Simulasi Lomba"
    with pytest.raises(ValueError):
        PAKET.format_mode("ujian")


def test_konstanta_durasi_store_sama_dengan_paket():
    assert K.DURASI_SIMULASI_DETIK == PAKET.durasi_simulasi_detik
    assert K.MAKS_NOMOR == PK.MAKS_NOMOR_SOAL == PAKET.jumlah_soal_simulasi
    assert K.DURASI_MAKS_DETIK == PK.DURASI_MAKS_MENIT * PK.DETIK_PER_MENIT


@pytest.mark.parametrize("perubahan", [{"jumlah_soal_simulasi": 34}, {"jumlah_isian_simulasi": 35},
                                       {"durasi_simulasi_detik": 0}])
def test_paket_simulasi_tidak_sah_ditolak(perubahan):
    with pytest.raises(ValueError):
        _ubah(**perubahan)


@pytest.mark.parametrize("menit,sah", [(5, True), (180, True), (4, False), (181, False), (True, False), (15.0, False)])
def test_menit_sah_5_sampai_180_bulat(menit, sah):
    assert PK.menit_sah(menit) is sah

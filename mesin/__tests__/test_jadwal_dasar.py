"""Dasar domain jadwal: pola 2x seminggu selama 4 pekan, batas waktu mulai, dan penolakan tanpa gema."""
from datetime import datetime, timedelta

import pytest

import jadwal_dasar as jd

SEKARANG = "2026-11-20T09:00:00"      # 16.00 WIB, 20 Nov 2026


def _hari(baku) -> datetime:
    return datetime.strptime(baku, "%Y-%m-%dT%H:%M:%S")


def test_delapan_pertemuan_dua_kali_seminggu_selama_empat_pekan():
    hasil = jd.delapan_pertemuan("2026-11-21T02:00:00")
    selisih = [(_hari(w) - _hari(hasil[0])).days for w in hasil]
    assert selisih == [0, 3, 7, 10, 14, 17, 21, 24]
    assert jd.JARAK_PERTEMUAN_KEDUA_HARI == 3
    assert len(hasil) == 8 and all(w[11:] == "02:00:00" for w in hasil)      # jam sama
    assert _hari(hasil[-1]) - _hari(hasil[0]) <= timedelta(days=24)


def test_delapan_pertemuan_melewati_batas_kalender_menjadi_jadwal_tidak_sah():
    with pytest.raises(jd.JadwalTidakSah):
        jd.delapan_pertemuan("9999-12-30T00:00:00")


def test_pertemuan_pertama_menolak_jam_yang_sudah_lewat_pada_hari_yang_sama():
    with pytest.raises(jd.JadwalTidakSah):
        jd.pertemuan_pertama("2026-11-20", "15:59", SEKARANG)           # 08.59 UTC < 09.00 UTC
    assert jd.pertemuan_pertama("2026-11-20", "16:00", SEKARANG) == "2026-11-20T09:00:00"
    assert jd.pertemuan_pertama("2026-11-20", "17:00", SEKARANG) == "2026-11-20T10:00:00"


def test_pertemuan_pertama_izinkan_lampau_melewati_batas_waktu_lampau():
    assert jd.pertemuan_pertama("2026-11-19", "09:00", SEKARANG, izinkan_lampau=True) == "2026-11-19T02:00:00"


def test_pertemuan_pertama_menolak_lebih_dari_366_hari_ke_depan():
    assert jd.pertemuan_pertama("2027-11-21", "09:00", SEKARANG) == "2027-11-21T02:00:00"   # hari ini + 366
    with pytest.raises(jd.JadwalTidakSah):
        jd.pertemuan_pertama("2027-11-22", "09:00", SEKARANG)


@pytest.mark.parametrize("izinkan", (False, True))
@pytest.mark.parametrize("tanggal,jam", (("9999-12-31", "23:59"), ("0001-01-01", "00:00")))
def test_tahun_ekstrem_jadwal_tidak_sah_bukan_overflow(tanggal, jam, izinkan):
    with pytest.raises(jd.JadwalTidakSah) as galat:
        jd.pertemuan_pertama(tanggal, jam, SEKARANG, izinkan_lampau=izinkan)
    assert tanggal not in str(galat.value)                              # pesan tanpa gema isian


def test_banyak_pertemuan_sama_dengan_paket_dan_waktu_baku_empat_digit_tahun():
    assert len(jd.OFFSET_PERTEMUAN_HARI) == jd.PERTEMUAN
    assert jd.delapan_pertemuan("0999-01-01T00:00:00")[0] == "0999-01-01T00:00:00"

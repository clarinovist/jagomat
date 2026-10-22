"""Satu format tanggal tampilan: "22 Sep 2026"; jam hanya bila perlu."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import format_tanggal as F
import learning_cycle_ui as UI

WIB = timezone(timedelta(hours=7))


@pytest.mark.parametrize("hari,teks", [
    (date(2026, 9, 22), "22 Sep 2026"),
    (date(2026, 1, 5), "5 Jan 2026"),
    (date(2026, 12, 31), "31 Des 2026"),
])
def test_tanggal_pendek_memakai_bulan_tiga_huruf(hari, teks):
    assert F.tanggal_pendek(hari) == teks


def test_waktu_wib_memakai_titik_dan_penanda_zona():
    assert F.waktu_wib(datetime(2026, 10, 19, 5, 2, tzinfo=WIB)) == "19 Okt 2026, 05.02 WIB"


def test_rencana_memakai_format_pendek_bukan_bulan_panjang():
    assert UI._tanggal_indonesia(date(2026, 9, 22)) == "22 Sep 2026"


def test_halaman_langganan_dan_sensor_tidak_memakai_format_numerik():
    import subscription_produksi_pages as S
    detik = int(datetime(2026, 10, 19, 5, 2, tzinfo=WIB).timestamp())
    assert S.tanggal_wib(detik) == "19 Okt 2026, 05.02 WIB"


@pytest.mark.parametrize("mentah,tanggal,waktu", [
    ("2026-10-22", "22 Okt 2026", "22 Okt 2026"),
    ("2026-10-22 08:53:13", "22 Okt 2026", "22 Okt 2026, 08.53 WIB"),
    ("tidak-valid", "tidak-valid", "tidak-valid"),
    ("", "—", "—"),
])
def test_format_dari_teks_database_aman_untuk_data_warisan(mentah, tanggal, waktu):
    assert F.tanggal_dari_teks(mentah) == tanggal
    assert F.waktu_dari_teks(mentah) == waktu


def test_halaman_lampiran_memakai_format_tanggal_seragam(tmp_path, monkeypatch):
    import auth, database, teacher_print_pages as TP
    monkeypatch.setattr(auth, "BERKAS_SANDI", tmp_path / "s.json")
    db = tmp_path / "u.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Anak Uji", pemilik="guru")
        sesi = database.buat_sesi(kon, sid, 5, jumlah_soal=2)
        kon.execute("UPDATE sesi SET tanggal='2026-10-22' WHERE id=?", (sesi,))
        lid = database.simpan_lampiran(kon, sesi, "lembar.jpg")
        kon.execute("UPDATE lampiran SET dibuat='2026-10-22 08:53:13' WHERE id=?", (lid,))
        isi = TP.halaman_sesi_lampiran(kon, sesi).decode()
    assert "22 Okt 2026, 08.53 WIB" in isi and "2026-10-22" not in isi.split("<body", 1)[1].split("<script", 1)[0].replace("datetime=", "")

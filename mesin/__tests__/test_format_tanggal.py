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

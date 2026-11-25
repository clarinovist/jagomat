"""Validator tautan pertemuan Mini Class: tautan sah diterima, isian lain ditolak tanpa gema. Data sintetis."""
from __future__ import annotations

import pytest

import jadwal_dasar as jd
import jadwal_tautan as jt

PREFIKS_ZOOM = "https://zoom.us/j/"                 # 18 karakter
TAUTAN_SAH = [
    "https://zoom.us/j/123456789",
    "https://us02web.zoom.us/j/123?pwd=abc",
    "https://a-b.zoom.us/j/1",
    "https://meet.google.com/abc-defg-hij",
    "https://Meet.Google.com/abc-defg-hij",
    "HTTPS://ZOOM.US/j/1",
    "  https://zoom.us/j/123456789  ",
    PREFIKS_ZOOM + "1" * 182,                       # tepat 200 karakter
]
TAUTAN_TOLAK = [
    "",
    "   ",
    None,
    123,
    b"https://zoom.us/j/1",
    ["https://zoom.us/j/1"],
    "Ruang 1",
    "Online",
    "http://zoom.us/j/1",
    "HTTP://zoom.us/j/1",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "file:///etc/passwd",
    "//zoom.us/j/1",
    "https:zoom.us/j/1",
    "https://user:pass@zoom.us/j/1",
    "https://user@zoom.us/j/1",
    "https://zoom.us:443/j/1",
    "https://zoom.us:8443/j/1",
    "https://zoom.us:/j/1",
    "https://zoom.us.evil.com/j/1",
    "https://evilzoom.us/j/1",
    "https://zoom.us.evil.com",
    "https://meet.google.com.evil.com/abc-defg-hij",
    "https://notmeet.google.com/abc-defg-hij",
    "https://meet.google.com",
    "https://meet.google.com/",
    "https://evil.example/",
    "https://evil.example/j/1",
    "https://[::1]/j/1",
    "https://-x.zoom.us/j/1",
    "https://a..zoom.us/j/1",
    "https://zoom.us/j/1<script>",
    "https://zoom.us/j/1\"x",
    "https://zoom.us/j/1'x",
    "https://zoom.us/j/1`x",
    "https://zoom.us/j/1?x=<",
    "https://zoom.us/j\\1",
    "https://zoom.us/j/1 2",
    "https://zoom.us/j/1\nhttps://evil.example",
    "https://zo\tom.us/j/1",
    "https://zoom.us/j/ü",
    PREFIKS_ZOOM + "1" * 183,                       # 201 karakter
]


def _label(nilai) -> str:
    return repr(nilai)[:60]


@pytest.mark.parametrize("nilai", TAUTAN_SAH, ids=_label)
def test_tautan_sah_diterima_dan_dikembalikan_setelah_strip(nilai):
    # Arrange
    diharapkan = nilai.strip()

    # Act
    hasil = jt.periksa_tautan_meeting(nilai)

    # Assert
    assert hasil == diharapkan
    assert jt.tautan_meeting_sah(nilai) is True


@pytest.mark.parametrize("nilai", TAUTAN_TOLAK, ids=_label)
def test_tautan_tidak_sah_ditolak_dengan_jadwal_tidak_sah(nilai):
    # Arrange: isian di luar aturan (skema, host, port, userinfo, karakter, panjang, tipe)

    # Act / Assert
    with pytest.raises(jd.JadwalTidakSah):
        jt.periksa_tautan_meeting(nilai)
    assert jt.tautan_meeting_sah(nilai) is False


def test_galat_tautan_tidak_menggemakan_isian():
    # Arrange
    isian = "https://evil.example/rahasia-123"

    # Act
    with pytest.raises(jd.JadwalTidakSah) as galat:
        jt.periksa_tautan_meeting(isian)

    # Assert
    assert "rahasia-123" not in str(galat.value)


def test_tautan_tepat_200_karakter_diterima_dan_201_ditolak():
    # Arrange
    tepat = PREFIKS_ZOOM + "1" * 182
    lebih = tepat + "1"

    # Act / Assert
    assert len(tepat) == 200 and jt.tautan_meeting_sah(tepat) is True
    assert len(lebih) == 201 and jt.tautan_meeting_sah(lebih) is False


def test_tautan_meeting_sah_tidak_pernah_melempar_untuk_tipe_apa_pun():
    # Arrange
    isian = [None, 0, 1.5, [], {}, b"x"]

    # Act / Assert
    assert all(jt.tautan_meeting_sah(nilai) is False for nilai in isian)

"""Kalender domain WIB, sama dengan tanggal SQLite dan tidak mengikuti host."""
from datetime import date, datetime, timedelta, timezone

_WIB = timezone(timedelta(hours=7))


def hari_wib() -> date:
    """Tanggal saat ini dalam UTC+7, tanpa bergantung TZ atau paket zona waktu."""
    return datetime.now(_WIB).date()

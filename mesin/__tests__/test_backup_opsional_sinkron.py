"""Daftar OPSIONAL di tool backup operasional dan backup harian harus sama persis (urutan ikut)."""
import importlib.util
from pathlib import Path

from test_operational_backup import backup

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_harian.py"
spec = importlib.util.spec_from_file_location("backup_harian", SCRIPT)
harian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harian)


def test_daftar_opsional_backup_harian_sama_dengan_operational_backup():
    assert tuple(harian.OPSIONAL) == tuple(backup.OPSIONAL)

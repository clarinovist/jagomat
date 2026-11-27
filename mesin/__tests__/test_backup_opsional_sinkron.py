"""Daftar OPSIONAL di tool backup operasional dan backup harian harus sama persis (urutan ikut)."""
import importlib.util
from pathlib import Path

import pytest
from test_operational_backup import backup

import guru_jadwal_tetap_bentuk

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_harian.py"
DOCS = Path(__file__).resolve().parents[2] / "docs" / "operational-backup.md"
spec = importlib.util.spec_from_file_location("backup_harian", SCRIPT)
harian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harian)


def test_daftar_opsional_backup_harian_sama_dengan_operational_backup():
    assert tuple(harian.OPSIONAL) == tuple(backup.OPSIONAL)


def test_daftar_opsional_backup_harian_memuat_berkas_jadwal_tetap():
    assert guru_jadwal_tetap_bentuk.NAMA_BERKAS in harian.OPSIONAL


@pytest.mark.parametrize('nama', backup.OPSIONAL)
def test_setiap_opsional_disebut_di_docs_backup_operasional(nama):
    """Dokumen backup operasional menyebut tiap DB opsional dengan nama berkas dalam backtick."""
    assert '`%s`' % nama in DOCS.read_text(encoding='utf-8')

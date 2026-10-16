"""Regression test untuk discovery instruksi agent Jagomat."""

from pathlib import Path
import importlib.util


AKAR = Path(__file__).resolve().parents[2]


def _muat_check_repo():
    jalur = AKAR / 'scripts' / 'check_repo.py'
    spesifikasi = importlib.util.spec_from_file_location('check_repo_agents', jalur)
    assert spesifikasi is not None and spesifikasi.loader is not None
    modul = importlib.util.module_from_spec(spesifikasi)
    spesifikasi.loader.exec_module(modul)
    return modul


def test_agents_root_diizinkan_oleh_palang_repo():
    """AGENTS.md harus tracked agar aturan codemode ter-discovery di Jagomat."""
    modul = _muat_check_repo()

    assert modul.alasan_larangan('AGENTS.md') is None
    assert modul.alasan_larangan('instruksi-lokal.md') == (
        'berkas root bukan codebase'
    )

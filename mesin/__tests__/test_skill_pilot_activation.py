"""Writer pilot hanya lewat permukaan terotorisasi; codec campuran tetap nonaktif."""
import ast
from pathlib import Path


def test_writer_pilot_hanya_dipanggil_layanan_pilot():
    akar=Path(__file__).resolve().parents[1]
    for berkas in akar.glob('*.py'):
        if berkas.stem in ('skill_pilot_sessions','skill_pilot_service'):
            continue
        for node in ast.walk(ast.parse(berkas.read_text())):
            if isinstance(node,ast.Import):
                assert 'skill_pilot_sessions' not in {n.name for n in node.names},berkas.name
            if isinstance(node,ast.ImportFrom):
                assert node.module!='skill_pilot_sessions',berkas.name
    assert not hasattr(__import__('skill_pilot_store'),'buat_sesi')

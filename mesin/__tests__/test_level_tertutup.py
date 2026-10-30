"""Level tertutup terpusat; schema dan label wajib mengikuti perluasannya."""
import ast
from pathlib import Path
import re

from context_schema import SKEMA_KONTEKS
from question_context import label_profil_parameter
from templates import LEVEL


_ALLOWLIST = {
    'templates.py',  # Definisi tunggal himpunan level tertutup.
    'skill_pilot.py',  # Level yang ditawarkan konten pilot, bukan himpunan tertutup.
    'visual_inventory.py',  # Cakupan konten visual, bukan himpunan tertutup.
}


def _literal_level(node):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('tuple', 'list', 'set', 'frozenset')
            and len(node.args) == 1 and not node.keywords):
        node = node.args[0]
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return False
    if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
        return False
    return {e.value for e in node.elts} - {''} == {'P3', 'P4', 'P5', 'P6'}


def test_literal_level_tertutup_hanya_di_allowlist():
    akar = Path(__file__).resolve().parents[1]
    pelanggaran = set()
    for berkas in sorted(akar.glob('*.py')):
        if berkas.name in _ALLOWLIST:
            continue
        for node in ast.walk(ast.parse(berkas.read_text(encoding='utf-8'))):
            if _literal_level(node):
                pelanggaran.add((berkas.name, node.lineno))
    assert not pelanggaran, 'Gunakan templates.LEVEL, bukan literal level tertutup:\n' + '\n'.join(
        '{}:{}'.format(nama, baris) for nama, baris in sorted(pelanggaran)
    )


def test_check_ddl_sinkron_dengan_level():
    cocok = re.search(
        r'CHECK\s*\(\s*profil_parameter\s+IN\s*\(([^)]*)\)\s*\)',
        SKEMA_KONTEKS, re.IGNORECASE,
    )
    assert cocok is not None, 'CHECK profil_parameter tidak ditemukan dalam DDL konteks'
    nilai = set(re.findall(r"'([^']*)'", cocok.group(1)))
    assert nilai == set(LEVEL), 'Perluasan LEVEL memerlukan migrasi schema'


def test_label_profil_sinkron_dengan_level():
    label = []
    for level in LEVEL:
        try:
            nama = label_profil_parameter(level)
        except KeyError as galat:
            raise AssertionError('Level {} belum memiliki label profil'.format(level)) from galat
        assert not nama.startswith('Konfigurasi lama'), 'Label level {} belum tersedia'.format(level)
        label.append(nama)
    assert len(label) == len(set(label)), 'Label setiap level harus berbeda'

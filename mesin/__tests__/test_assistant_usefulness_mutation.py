"""Mutasi terisolasi: snapshot/alias/allow-list/kepemilikan bukan janji prompt."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
KASUS = (
    ('binding', 'assistant_context.py', '"muatan": muatan, "tautan": tautan}', '"muatan": muatan}',
     'test_binding_alias_berubah_meski_payload_sama'),
    ('allowlist', 'assistant_context.py', '"status": "perlu_ditinjau"}', '"status": "perlu_ditinjau", "sesi_id": sesi["id"]}',
     'test_ringkasan_memilih_antrean_otoritatif_dan_tidak_mengirim_identitas'),
    ('pemilik', 'assistant_context.py',
     '    """Snapshot fakta aplikasi; identitas sesi tetap lokal, bukan payload AI."""\n    if not database.siswa_milik(kon, siswa_id, pemilik):\n        return None',
     '    """Snapshot fakta aplikasi; identitas sesi tetap lokal, bukan payload AI."""\n    pemilik = kon.execute("SELECT pemilik FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0]',
     'test_ringkasan_memilih_antrean_otoritatif_dan_tidak_mengirim_identitas'),
    ('status_aktif', 'profile_history.py',
     "_PERLU_TINJAUAN = ' AND s.dibatalkan IS NULL AND s.selesai IS NOT NULL AND NOT COALESCE(' + _AKTIF + ',0)'",
     "_PERLU_TINJAUAN = ' AND s.dibatalkan IS NULL AND s.selesai IS NOT NULL AND s.dikonfirmasi_guru IS NULL'",
     'test_antrean_memakai_konfirmasi_aktif_terlama_batas_tiga'),
    ('histori_alias', 'assistant_components.py', 'fakta_tinjauan(konteks if not hanya_baca else None)', 'fakta_tinjauan(konteks)',
     'test_tautan_bukan_dari_teks_model_dan_stale_tanpa_alias'),
)


@pytest.mark.parametrize('nama,modul,lama,baru,node', KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_konteks_merah_lalu_hijau(tmp_path, nama, modul, lama, baru, node):
    del nama
    source = tmp_path / 'mesin'
    source.mkdir()
    for berkas in AKAR.glob('*.py'):
        shutil.copyfile(berkas, source / berkas.name)
    shutil.copytree(AKAR / '__tests__', source / '__tests__', ignore=shutil.ignore_patterns('__pycache__'))
    target = source / modul
    asli = target.read_text()
    assert asli.count(lama) == 1
    command = [sys.executable, '-m', 'pytest', str(source / '__tests__' / ('test_assistant_usefulness.py::' + node)),
               '-q', '-W', 'error', '-p', 'no:cacheprovider']
    env = {**os.environ, 'PYTHONPATH': str(source), 'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000'}
    target.write_text(asli.replace(lama, baru, 1))
    merah = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=45)
    assert merah.returncode == 1 and 'AssertionError' in merah.stdout, merah.stdout + merah.stderr
    assert 'ImportError' not in merah.stdout + merah.stderr
    target.write_text(asli)
    hijau = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=45)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

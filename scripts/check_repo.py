"""Palang nama berkas tracked: codebase saja, tanpa membaca data anak."""
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable, Optional, Tuple

FOLDER_KODE = frozenset(('mesin', 'scripts', 'docs', '.github'))
BERKAS_AKAR = frozenset((
    'README.md', 'CLAUDE.md', '.gitignore', '.project-gate.json', 'pytest.ini',
))
FOLDER_LOKAL = frozenset((
    'riset-pasar', 'desain-ui', 'kurikulum', 'latihan', 'produk', 'spike',
    'cadangan', 'lembar', 'hasil', 'kejadian', 'turunan', 'cache_llm',
    '.git', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache',
    '.hermes', '.claude', '.commandcode', '.codegraph', 'graphify-out',
    'build', '.gradle', '.tmp_txt',
))
POLA_DATA = re.compile(r'\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm|journal))?$')


def alasan_larangan(nama: str) -> Optional[str]:
    """Kembalikan alasan statis, bukan nama yang bisa mengandung data pribadi."""
    bagian = tuple(nama.split('/'))
    if (any(x in ('', '.', '..') for x in bagian) or '\\' in nama
            or any(ord(x) < 32 or ord(x) == 127 for x in nama)):
        return 'path tidak valid'
    kecil = tuple(x.lower() for x in bagian)
    berkas = kecil[-1]
    if FOLDER_LOKAL.intersection(kecil[:-1]):
        return 'folder lokal atau non-codebase'
    if (berkas in ('sandi.json', 'sesi.json', '.ds_store', 'local.properties')
            or (berkas.startswith('.') and berkas.endswith('.json.lock'))
            or berkas.startswith('.env') or '-isi.' in berkas
            or (berkas.startswith('prompt-') and berkas.endswith('.md'))
            or POLA_DATA.search(berkas)
            or berkas.endswith(('.pem', '.key', '.pyc', '.apk'))):
        return 'data sensitif atau artefak lokal'
    if kecil[0] == 'docs' and (len(kecil) > 1 and kecil[1] == 'plan'
                              or any(x.startswith('riset-') for x in kecil[1:])):
        return 'riset atau rencana lokal'
    if len(bagian) == 1:
        return None if nama in BERKAS_AKAR else 'berkas root bukan codebase'
    return None if bagian[0] in FOLDER_KODE else 'folder bukan codebase'


def pelanggaran(daftar: Iterable[str]) -> Tuple[str, ...]:
    """Hitung alasan tanpa mengubah masukan atau menyimpan nama berkas."""
    return tuple(alasan for nama in daftar
                 for alasan in (alasan_larangan(nama),) if alasan is not None)


def utama(akar: Path) -> int:
    """Periksa index Git; kegagalan inventaris tidak boleh dianggap bersih."""
    try:
        hasil = subprocess.run(
            ['git', '-C', str(akar), 'ls-files', '-z'],
            check=True, capture_output=True,
        )
        daftar = tuple(x for x in hasil.stdout.decode('utf-8').split('\0') if x)
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        print('Gagal membaca inventaris Git; pemeriksaan dibatalkan.', file=sys.stderr)
        return 2
    masalah = pelanggaran(daftar)
    if masalah:
        print('Palang repo menolak {} berkas. Periksa index lokal; jangan unggah data sensitif.'
              .format(len(masalah)), file=sys.stderr)
        return 1
    print('Bersih: {} berkas codebase, tanpa path data terlarang.'.format(len(daftar)))
    return 0


if __name__ == '__main__':
    sys.exit(utama(Path(__file__).resolve().parents[1]))

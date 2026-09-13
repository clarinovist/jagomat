"""Palang repo menguji nama sintetis; tidak pernah membuka data anak."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]


def _git(akar, *argumen):
    return subprocess.run(
        ['git', '-C', str(akar), *argumen], check=True,
        capture_output=True, text=True,
    )


def _repo(tmp_path, nama):
    _git(tmp_path, 'init', '-q')
    path = tmp_path / nama
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('contoh sintetis, bukan data pengguna')
    _git(tmp_path, 'add', '--', nama)
    if (AKAR / 'scripts/check_repo.py').exists():
        shutil.copytree(AKAR / 'scripts', tmp_path / 'scripts')
    return tmp_path


def _jalankan_ci(akar):
    # Ambil seluruh blok run termasuk indentasi shell di bawahnya.
    teks = (AKAR / '.github/workflows/deploy.yml').read_text()
    blok = teks.split('- name: Pastikan tidak ada data siswa ter-commit', 1)[1]
    nilai = blok.split('run:', 1)[1].lstrip()
    if nilai.startswith('|'):
        baris = nilai.splitlines()[1:]
        batas = next((i for i, b in enumerate(baris) if b.strip() and not b.startswith('          ')), len(baris))
        perintah = '\n'.join(b[10:] for b in baris[:batas])
    else:
        perintah = nilai.splitlines()[0]
    env = {**os.environ, 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']}
    return subprocess.run(['bash', '-eu', '-c', perintah], cwd=akar,
                          env=env, capture_output=True, text=True)


@pytest.mark.parametrize('nama', [
    'mesin/sesi.json', 'mesin/cadangan/cadangan.zip',
    'mesin/lembar/contoh.html', 'mesin/latihan.db-wal',
    'riset-pasar/laporan.md', 'desain-ui/mockup.png',
    'mesin/.tmp_txt/a.txt', 'mesin/PROMPT-catatan.md',
])
def test_ci_menolak_berkas_terlarang(tmp_path, nama):
    akar = _repo(tmp_path, nama)
    hasil = _jalankan_ci(akar)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert (akar / nama).read_text() == 'contoh sintetis, bukan data pengguna'


def test_ci_menerima_aset_runtime(tmp_path):
    akar = _repo(tmp_path, 'mesin/aset/favicon.svg')
    assert _jalankan_ci(akar).returncode == 0


@pytest.fixture
def penjaga():
    path = AKAR / 'scripts/check_repo.py'
    assert path.exists(), 'Palang repo belum dibuat'
    spesifikasi = importlib.util.spec_from_file_location('penjaga_repo', path)
    assert spesifikasi is not None and spesifikasi.loader is not None
    modul = importlib.util.module_from_spec(spesifikasi)
    spesifikasi.loader.exec_module(modul)
    return modul


@pytest.mark.parametrize('nama', [
    'mesin/data.db', 'mesin/data.DB-SHM', 'mesin/data.db-journal',
    'mesin/data.sqlite', 'mesin/data.sqlite3-wal', 'mesin/sandi.json',
    'mesin/.sandi.json.lock', 'mesin/.sesi.json.lock',
    'mesin/.akun-uji.json.lock',
    'mesin/arsip/sesi.json', 'mesin/kejadian/salinan.json',
    'mesin/turunan/a.png', 'mesin/cache_llm/a.json', 'mesin/hasil/a.md',
    'mesin/soal-ISI.md', 'mesin/.env', 'mesin/.env.production',
    'mesin/rahasia.pem', 'mesin/id.key', 'mesin/__pycache__/a.pyc',
    'mesin/.venv/a', 'mesin/.git/config', 'mesin/cadangan lama/a.db',
    'mesin/nama\nbaris.db', 'docs/plan/rencana.md', 'docs/riset-lain.md',
    'produk/PRD.md', 'kurikulum/soal.pdf', 'latihan/soal.md',
    'spike/contoh.py', 'marketing/riset.md', '.hermes/catatan.md',
    'docs/riset-pasar/laporan.md', '../mesin/a.py', '/mesin/a.py',
    'mesin//a.py', 'mesin/../a.py', 'mesin\\sesi.json', '',
])
def test_nama_terlarang(penjaga, nama):
    assert penjaga.alasan_larangan(nama)


@pytest.mark.parametrize('nama', [
    'README.md', 'CLAUDE.md', '.gitignore', '.project-gate.json', 'pytest.ini',
    '.github/workflows/deploy.yml', 'mesin/web.py', 'mesin/aset/mark-penuh.svg',
    'mesin/__tests__/test_students.py', 'mesin/cadangkan.sh', 'mesin/Dockerfile',
    'scripts/check_repo.py', 'docs/siklus-belajar-terpandu.md',
    'docs/design-system.md', 'mesin/__tests__/fixtures/contoh.json',
])
def test_nama_diizinkan(penjaga, nama):
    assert penjaga.alasan_larangan(nama) is None


def test_git_gagal_tidak_dianggap_bersih(penjaga, tmp_path, capsys):
    assert penjaga.utama(tmp_path) == 2
    assert 'gagal' in capsys.readouterr().err.lower()


@pytest.mark.parametrize('nama, kode', [('mesin/web.py', 0), ('mesin/sesi.json', 1)])
def test_utama_membaca_index_tanpa_mengubahnya(penjaga, tmp_path, capsys, nama, kode):
    akar = _repo(tmp_path, nama)
    sebelum = _git(akar, 'ls-files', '-s', '-z').stdout
    assert penjaga.utama(akar) == kode
    assert _git(akar, 'ls-files', '-s', '-z').stdout == sebelum
    keluaran = capsys.readouterr()
    assert nama not in keluaran.out + keluaran.err


def test_cli_nama_newline_tidak_membocorkan_nama(tmp_path):
    akar = _repo(tmp_path, 'mesin/nama\nbaris.db')
    hasil = _jalankan_ci(akar)
    assert hasil.returncode == 1
    assert 'nama' not in hasil.stdout + hasil.stderr


def test_guard_murni_tidak_mengubah_daftar(penjaga):
    nama = ('mesin/web.py', 'mesin/sesi.json')
    assert len(penjaga.pelanggaran(nama)) == 1
    assert nama == ('mesin/web.py', 'mesin/sesi.json')

"""Fallback berbagi editorial dan satu renderer aktif per permukaan."""
import ast
import html
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import auth
import database
import teacher_pages
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID


class Markup(HTMLParser):
    def __init__(self, sumber):
        super().__init__(); self.tag = []; self.feed(sumber)
    def handle_starttag(self, tag, attrs):
        self.tag.append((tag, dict(attrs)))


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        sid = database.tambah_siswa(kon, "Anak Sintetis", pemilik="guru")
        sesi = database.buat_sesi(kon, sid, seed=73, jumlah_soal=2)
    yield s, sid, sesi
    s.berhenti()


def test_fallback_label_landmark_tautan_dan_header_aman(server):
    s, sid, sesi = server
    kode, isi, tajuk = s.minta(f"/sesi/{sesi}/bagikan", auth=("guru", SANDI_GURU), data={})
    assert kode == 200
    m = Markup(isi)
    assert sum(tag == 'main' for tag, _ in m.tag) == 1
    assert sum(tag == 'h1' for tag, _ in m.tag) == 1
    assert ('label', {'id': 'label-tautan', 'for': 'tautan-sesi'}) in m.tag
    bidang = [a for t, a in m.tag if t == 'input' and a.get('id') == 'tautan-sesi']
    assert len(bidang) == 1 and 'readonly' in bidang[0]
    assert bidang[0]['aria-describedby'] == 'petunjuk-tautan'
    tautan = bidang[0]['value']
    assert tautan.startswith('https://jagomat.id/mulai/')
    assert isi.count(f'href="/anak/{sid}?section=riwayat"') == 1
    assert '7 hari' in isi and 'tanpa masuk' in isi
    assert tajuk['Cache-Control'] == 'no-store'
    assert tajuk['Referrer-Policy'] == 'no-referrer'
    assert tajuk['X-Robots-Tag'] == 'noindex, nofollow'
    # Respons tidak membuat form baru atau entry point salin JS palsu.
    assert [a['action'] for t, a in m.tag if t == 'form'] == ['/keluar']
    jalur = tautan.removeprefix('https://jagomat.id')
    assert s.minta(jalur)[0] == 200
    with s.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM tautan_sesi').fetchone()[0] == 1
        assert kon.execute('SELECT COUNT(*) FROM jawaban').fetchone()[0] == 0


def test_fetch_tetap_json_bukan_halaman(server):
    s, _, sesi = server
    kode, isi, tajuk = s.minta(f'/sesi/{sesi}/bagikan', auth=('guru', SANDI_GURU), data={}, headers={'X-Requested-With': 'fetch'})
    assert kode == 200
    assert json.loads(isi)['tautan'].startswith('https://jagomat.id/mulai/')
    assert 'application/json' in tajuk['Content-Type']


def test_tautan_dan_nama_di_escape_tanpa_membaca_db():
    tautan = 'https://contoh.invalid/mulai/"<b>&'
    isi = teacher_pages.halaman_bagikan_sesi(1, 2, tautan, '<akun>', 'guru').decode()
    assert html.escape(tautan, quote=True) in isi
    assert '&lt;akun&gt;' in isi and '<akun>' not in isi


@pytest.mark.parametrize('ident', [None, ('feby', SANDI_MURID), ('asing', 'sandi-asing-sintetis')])
def test_palang_fallback_tidak_menerbitkan_token(server, ident):
    s, _, sesi = server
    auth.tambah_akun('asing', 'sandi-asing-sintetis', 'guru')
    with s.buka() as kon: sebelum = tuple(kon.iterdump())
    kode, isi, _ = s.minta(f'/sesi/{sesi}/bagikan', auth=ident, data={})
    assert kode == (404 if ident and ident[0] == 'asing' else 401)
    assert 'id="tautan-sesi"' not in isi
    if ident and ident[0] == 'asing':
        hilang = s.minta('/sesi/999999/bagikan', auth=ident, data={})
        assert (kode, isi) == hilang[:2]
    with s.buka() as kon: assert tuple(kon.iterdump()) == sebelum


def test_renderer_lama_dan_aset_khusus_tidak_tersisa():
    akar = Path(__file__).resolve().parent.parent
    lama = {'halaman_utama', 'halaman_sesi', 'halaman_kerja', 'halaman_daftar_sesi', 'CSS_MURID'}
    for path in akar.glob('*.py'):
        pohon = ast.parse(path.read_text())
        for n in ast.walk(pohon):
            if isinstance(n, ast.FunctionDef): assert n.name not in lama, path.name
            if isinstance(n, ast.ImportFrom): assert not ({a.name for a in n.names} & lama), path.name
    assert not (akar / 'icons.py').exists()

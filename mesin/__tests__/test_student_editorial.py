"""Kontrak presentasi editorial murid tanpa memperluas permukaan data."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import database
import reports
import student_pages
from style_stitch import GAYA_STITCH
import design_tokens as T


class Markup(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.elemen = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))

    def ambil(self, tag):
        return [attrs for nama, attrs in self.elemen if nama == tag]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / 'editorial.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    return path


@pytest.fixture()
def db_terjaga(db, monkeypatch):
    class RowTerjaga(sqlite3.Row):
        def __getitem__(self, nama):
            if nama in {'kunci', 'malrule_id', 'kode_usulan', 'kode_final', 'alasan'}:
                raise AssertionError('Presentasi murid membaca kolom guru')
            return super().__getitem__(nama)
    monkeypatch.setattr(sqlite3, 'Row', RowTerjaga)
    return db


@pytest.mark.parametrize('mode,timer', [('diagnostik', 'tanpa'), ('drill', 'tanpa'), ('drill', 'sesi'), ('drill', 'soal')])
@pytest.mark.parametrize('token', [False, True])
def test_kerja_editorial_landmark_label_dan_form(db_terjaga, mode, timer, token):
    with database.buka(db_terjaga) as kon:
        siswa = database.tambah_siswa(kon, 'Nama <panjang> & sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, seed=7, jumlah_soal=12, mode=mode, timer_mode=timer)
        isi = student_pages.halaman_kerja_baru(
            kon, siswa, sesi, akses_tautan=token,
            jalur_aksi='/mulai/contoh' if token else None,
        ).decode()
    dom = Markup(isi)
    assert len(dom.ambil('main')) == len(dom.ambil('h1')) == 1
    assert 'kerja-editorial-st' in dom.ambil('body')[0]['class']
    assert 'Nama &lt;panjang&gt; &amp; sintetis' in isi
    label = {a.get('for') for a in dom.ambil('label')}
    for tag in ('input', 'textarea'):
        for el in dom.ambil(tag):
            if el.get('type') in ('radio', 'checkbox'):
                continue
            assert el.get('id') in label, el
    form = dom.ambil('form')
    assert form[0]['method'] == 'post'
    assert form[0]['action'] == ('/mulai/contoh' if token else f'/murid/kerjakan/{sesi}')
    tombol = [b for b in dom.ambil('button') if b.get('name') == 'aksi']
    assert [b['value'] for b in tombol] == ['simpan', 'selesai']
    assert sum(i.get('name', '').startswith('jwb_') for i in dom.ambil('input')) == 12
    assert ('id="timer-strip"' in isi) == (timer == 'sesi')
    assert bool(dom.ambil('fieldset')) == (mode == 'diagnostik')
    badan = isi.split('</style>')[-1].lower()
    for dilarang in ('kode_final', 'malrule', 'diagnosis', 'miskonsepsi'):
        assert dilarang not in badan
    if token:
        assert len(form) == 1
        assert not dom.ambil('a')
        assert not any(i.get('type') == 'file' for i in dom.ambil('input'))
    else:
        assert len(form) == 2  # form kerja + form foto; tidak ada form Keluar (topbar punya Tutup)
        assert not any(f.get('action') == '/keluar' for f in form)
        assert sum(a.get('href') == '/murid' for a in dom.ambil('a')) == 1


def test_kerja_terkirim_tanpa_form_dan_token_tetap_none(db_terjaga):
    with database.buka(db_terjaga) as kon:
        sid = database.tambah_siswa(kon, 'Selesai', pemilik='guru')
        sesi = database.buat_sesi(kon, sid, seed=7, jumlah_soal=1)
        database.tandai_selesai(kon, sesi)
        isi = student_pages.halaman_kerja_baru(kon, sid, sesi).decode()
        assert student_pages.halaman_kerja_baru(kon, sid, sesi, akses_tautan=True) is None
    dom = Markup(isi)
    assert len(dom.ambil('main')) == len(dom.ambil('h1')) == 1
    assert not dom.ambil('form')
    assert 'Jawabanmu sudah dikirim.' in isi


@pytest.mark.parametrize('semua_benar', [False, True])
def test_hasil_editorial_status_dan_pembahasan_tetap(db, semua_benar):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, 'Hasil <contoh>', pemilik='guru')
        sesi = database.buat_sesi(kon, sid, seed=7, jumlah_soal=3)
        for i, s in enumerate(database.isi_sesi(kon, sesi)):
            if semua_benar or i < 2:
                database.simpan_jawaban(kon, s['sesi_soal_id'], jawaban=s['kunci'] if semua_benar or i == 0 else '999', cara='Aku menghitung')
        reports.diagnosa_murid(kon, sesi)
        database.tandai_selesai(kon, sesi)
        assert student_pages.halaman_hasil_murid(kon, sid, sesi) is None
        kon.execute("UPDATE sesi SET direview='2026-09-10' WHERE id=?", (sesi,))
        isi = student_pages.halaman_hasil_murid(kon, sid, sesi).decode()
    dom = Markup(isi)
    assert len(dom.ambil('main')) == len(dom.ambil('h1')) == 1
    assert 'hasil-editorial-st' in dom.ambil('body')[0]['class']
    assert 'jawaban benar' in isi
    assert sum(a.get('href') == '/murid' for a in dom.ambil('a')) == 1
    assert 'Hasil &lt;contoh&gt;' in isi
    assert isi.count('Caranya:') == 3
    badan = isi.split('</style>')[-1]
    assert ('Belum tepat' in badan) != semua_benar
    assert ('Belum dijawab' in badan) != semua_benar
    assert ('class="rumus-blok-st"' in badan) != semua_benar


def test_css_editorial_murid_terisolasi_dan_aksesibel():
    blok = GAYA_STITCH.split('/* WORKER B editorial scoped')[1].split('/* Akhir WORKER B')[0]
    assert '.kerja-editorial-st .kerja-pill-st:has(input:focus-visible)' in blok
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr))' in blok
    assert '@media (max-width: 24rem)' in blok
    assert f'.hasil-editorial-st .st-badge.baru {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; }}' in blok
    assert '.kerja-editorial-st .kerja-centang-st { min-height: 44px;' in blok
    for selector in re.findall(r'([^{}]+)\{', blok):
        if selector.strip().startswith(('@media', '@page')):
            continue
        assert '-editorial-st' in selector, selector

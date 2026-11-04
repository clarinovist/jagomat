"""Lembar PG cetak ringkas: opsi dua kolom, tanpa jarak paragraf layar (ulasan guru 4 Nov 2026)."""
import re

import pytest

import choice_pages
import database


@pytest.fixture
def lembar(tmp_path, monkeypatch):
    monkeypatch.setenv('OSN_CETAK_RINGKAS', '1')
    path = tmp_path / 'pg.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 11, jumlah_soal=8, format_jawaban='pilihan_ganda')
        yield (choice_pages.lembar_pilihan(kon, sesi).decode(),
               choice_pages.lembar_pilihan(kon, sesi, untuk_guru=True).decode())


def _aturan(html, penanda):
    gaya = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    cocok = [b for b in re.findall(r'[^{}]+\{[^{}]*\}', gaya) if penanda in b.split('{')[0]]
    assert cocok, penanda
    return ' '.join(cocok)


@pytest.mark.parametrize('indeks', (0, 1))
def test_opsi_pg_cetak_dua_kolom_dan_rapat(lembar, indeks):
    isi = lembar[indeks]
    daftar = _aturan(isi, '.lembar-editorial .pg-daftar')
    assert 'grid-template-columns' in daftar and 'repeat(2' in daftar
    paragraf = _aturan(isi, '.lembar-editorial .pg-daftar p')
    assert re.search(r'margin:\s*0', paragraf)


def test_cetak_pg_tetap_memuat_ruang_caraku_dan_opsi_utuh(lembar):
    isi = lembar[0]
    assert isi.count('class="cara sedang"') == 8
    assert isi.count('class="pg-daftar"') == 8
    # Semua opsi tetap ada (label A..D bukan hanya ditata ulang).
    assert all(isi.count('<p>' + huruf + '. ') >= 8 for huruf in 'AB')


def test_font_dan_jarak_lembar_pg_diatur_untuk_kertas(lembar):
    gaya = _aturan(lembar[0], 'body.lembar-editorial')
    assert 'font-size' in gaya
    assert '@page' in re.search(r'<style>(.*?)</style>', lembar[0], re.S).group(1)


def _lembar_dengan(tmp_path, monkeypatch, nilai):
    if nilai is None:
        monkeypatch.delenv('OSN_CETAK_RINGKAS', raising=False)
    else:
        monkeypatch.setenv('OSN_CETAK_RINGKAS', nilai)
    path = tmp_path / ('pg-' + str(nilai) + '.db')
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 11, jumlah_soal=8, format_jawaban='pilihan_ganda')
        return choice_pages.lembar_pilihan(kon, sesi).decode()


@pytest.mark.parametrize('nilai', (None, '0'))
def test_bawaan_nonaktif_keluaran_cetak_tidak_berubah(tmp_path, monkeypatch, nilai):
    """Pasangan rilis meng-hash halaman ini; tanpa flag keluaran harus seperti sebelum perubahan."""
    isi = _lembar_dengan(tmp_path, monkeypatch, nilai)
    assert choice_pages.gaya_cetak_pilihan() not in isi


def test_flag_menyala_hanya_menambah_gaya_ringkas(tmp_path, monkeypatch):
    mati = _lembar_dengan(tmp_path, monkeypatch, '0')
    hidup = _lembar_dengan(tmp_path, monkeypatch, '1')
    assert choice_pages.gaya_cetak_pilihan() in hidup
    assert hidup.replace(choice_pages.gaya_cetak_pilihan(), '') == mati


@pytest.mark.parametrize('nilai', ('2', 'true', ''))
def test_nilai_flag_tidak_sah_ditolak(tmp_path, monkeypatch, nilai):
    with pytest.raises(ValueError, match='OSN_CETAK_RINGKAS'):
        _lembar_dengan(tmp_path, monkeypatch, nilai)

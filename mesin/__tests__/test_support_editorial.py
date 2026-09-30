"""Presentasi dukungan, pesan router, dan lembar tetap terpisah dari domain."""
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import design_tokens as T
import landing
import support_settings
import render
import web
from generator import buat_lembar
from print_style import GAYA_CETAK
from screen_style import GAYA_LAYAR
from support_pages import halaman_pesan


@pytest.mark.parametrize('fungsi,kelas', [(landing.halaman_lupa_sandi, 'lupa-editorial-st'), (landing.halaman_kebijakan, 'privasi-editorial-st')])
def test_dukungan_publik_landmark_statis_dan_satu_masuk(fungsi, kelas):
    publik = support_settings.proyeksi_publik(support_settings.KonfigurasiDukungan(
        '082137111988', 'weekday_0900_1700_wib', 1, 3, 1, 1, 'sistem_uji'))
    isi = fungsi(dukungan=publik).decode()
    assert isi.count('<main ') == 1
    assert len(re.findall(r'<h1(?:>| )', isi)) == 1
    assert kelas in isi
    assert isi.count('href="/masuk"') == 1
    assert '<form' not in isi
    assert 'tidak menyimpan email' in isi or 'Tidak ada email' in isi


def test_pesan_mempertahankan_markup_dan_tidak_menambah_aksi():
    markup = '<h1>Halaman tidak ada</h1>'
    isi = halaman_pesan('404', markup)
    assert web._halaman is halaman_pesan
    assert isi == halaman_pesan('404', markup)
    assert markup.encode() in isi
    assert b'<main class="pesan-editorial-st">' in isi
    assert b'<a ' not in isi
    assert b'<form' not in isi
    assert b'<script' not in isi
    assert b'&lt;judul&gt;' in halaman_pesan('<judul>', markup)


def test_pesan_aksi_lama_tetap_satu():
    markup = '<h1>Perlu masuk</h1><p><a href="/masuk">Masuk</a> untuk melanjutkan.</p>'
    isi = halaman_pesan('Perlu masuk', markup).decode()
    assert markup in isi
    assert isi.count('href="/masuk"') == 1


@pytest.mark.parametrize('fungsi', [render.lembar_soal, render.lembar_penilaian])
@pytest.mark.parametrize('gaya', [None, GAYA_LAYAR])
def test_lembar_landmark_dan_konten_kartu_tetap(fungsi, gaya):
    soal = buat_lembar(seed=7).soal
    isi = fungsi(soal, nama='Contoh <aman>', gaya=gaya)
    assert '<body class="lembar-editorial">' in isi
    assert '<main class="wrap">' in isi
    assert isi.count('class="soal"') == 12
    assert 'Contoh &lt;aman&gt;' in isi
    badan = isi.split('</style>')[-1]
    if fungsi is render.lembar_soal:
        assert 'Kunci:' not in badan
        assert 'kunci-tabel' not in badan
        assert badan.count('Caraku:') == 12
    else:
        assert badan.count('Kunci:') == 12
        assert 'Kunci — Rahasia Guru' in badan


def test_cetak_browser_memakai_a4_dan_ruang_tulis_yang_sama():
    assert GAYA_CETAK in GAYA_LAYAR
    assert '@page { size: A4; margin: 13mm 12mm 11mm 12mm; }' in GAYA_CETAK
    for kelas, tinggi in [('kecil', 22), ('sedang', 26), ('besar', 30)]:
        assert re.search(r'\.cara\.' + kelas + r'\s*\{ height: ' + str(tinggi) + 'mm;', GAYA_CETAK)
    assert 'background-size: 4mm 7.5mm;' in GAYA_CETAK
    assert 'background-repeat: repeat;' in GAYA_CETAK
    assert 'table-layout: fixed; overflow-wrap: anywhere' in GAYA_LAYAR
    assert '.lembar-editorial .soal { border-width: .7pt; }' in GAYA_CETAK


def test_kontras_aksen_editorial_di_latar_terpakai():
    def luminansi(warna):
        kanal = [int(warna.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in kanal]
        return sum(v * b for v, b in zip(linear, [.2126, .7152, .0722]))
    for depan, latar in [(T.TEKS_PUTIH, T.AKSEN_TEAL_TUA), (T.TEKS_PUTIH, T.AKSEN_KORAL_TUA), (T.AKSEN_TEAL_TUA, T.LATAR_MURID), (T.TEKS_VARIAN, T.LATAR_MURID)]:
        a, b = sorted([luminansi(depan), luminansi(latar)])
        assert (b + .05) / (a + .05) >= 4.5

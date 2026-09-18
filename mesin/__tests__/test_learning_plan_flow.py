"""Perjalanan pemetaan mengikuti kontrol HTML, bukan melompati handoff."""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database
from http_test_kit import SANDI_GURU, ServerUji


class _KontrolHalaman(HTMLParser):
    """Ambil tujuan form, nama field, dan tautan untuk perjalanan HTTP."""

    def __init__(self):
        super().__init__()
        self.formulir = []
        self.tautan = []
        self.input_tautan = None
        self._aktif = None

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        if tag == 'form':
            self._aktif = {
                'aksi': atribut.get('action', ''),
                'metode': atribut.get('method', 'get'),
                'nama': [],
                'tombol': [],
            }
            self.formulir.append(self._aktif)
        elif tag == 'a' and atribut.get('href'):
            self.tautan.append(atribut['href'])
        elif tag == 'input' and atribut.get('id') == 'tautan-sesi':
            self.input_tautan = atribut.get('value')
        elif self._aktif is not None:
            if tag in {'input', 'select', 'textarea'} and atribut.get('name'):
                self._aktif['nama'].append(atribut['name'])
            if tag == 'button':
                self._aktif['tombol'].append(atribut)

    def handle_endtag(self, tag):
        if tag == 'form':
            self._aktif = None


def _kontrol(isi):
    hasil = _KontrolHalaman()
    hasil.feed(isi)
    return hasil


def _satu_form(isi, akhiran):
    cocok = [f for f in _kontrol(isi).formulir if f['aksi'].endswith(akhiran)]
    assert len(cocok) == 1, 'harus ada tepat satu form untuk langkah ini'
    assert cocok[0]['metode'].lower() == 'post'
    return cocok[0]


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            siswa = database.tambah_siswa(kon, 'Anak Alur Sintetis', 'P3', pemilik='guru')
        yield uji, siswa
    finally:
        uji.berhenti()


def test_pemetaan_dari_kartu_hingga_konfirmasi_dan_jeda(server):
    uji, siswa = server
    ident = ('guru', SANDI_GURU)
    kode, profil, _ = uji.minta(f'/anak/{siswa}', auth=ident)
    assert kode == 200
    rencana_url = [t for t in _kontrol(profil).tautan if t == f'/anak/{siswa}?section=rencana']
    assert rencana_url
    kode, profil, _ = uji.minta(rencana_url[0], auth=ident)
    assert kode == 200
    buat = _satu_form(profil, '/buat')
    assert not buat['nama']
    kode, sesi, _ = uji.minta(buat['aksi'], auth=ident, data={})
    assert kode == 200
    bagikan = _satu_form(sesi, '/bagikan')
    assert not bagikan['nama']
    kode, tautan, header = uji.minta(bagikan['aksi'], auth=ident, data={})
    assert kode == 200 and header['Cache-Control'] == 'no-store'
    url = _kontrol(tautan).input_tautan
    assert url and urlsplit(url).path.startswith('/mulai/')
    jalur_anak = urlsplit(url).path
    kode, halaman_anak, _ = uji.minta(jalur_anak)
    assert kode == 200
    badan_anak = halaman_anak.split('</style>', 1)[-1]
    for rahasia in ('Kunci:', 'malrule', 'Rencana belajar hari ini', 'kode_final'):
        assert rahasia not in badan_anak
    kerja = _satu_form(halaman_anak, jalur_anak)
    tombol = [b for b in kerja['tombol'] if b.get('name') == 'aksi' and b.get('value') == 'selesai']
    assert len(tombol) == 1
    # Kunci fixture hanya untuk menghasilkan respons sintetis yang terdiagnosis;
    # perjalanan tetap menemukan dan mengirim field lewat HTML permukaan anak.
    with uji.buka() as kon:
        sesi_id = int(bagikan['aksi'].split('/')[2])
        nilai_sintetis = {
            f"jwb_{b['sesi_soal_id']}": b['kunci']
            for b in database.isi_sesi(kon, sesi_id)
        }
    jawaban = {nama: nilai_sintetis[nama] for nama in kerja['nama'] if nama.startswith('jwb_')}
    assert len(jawaban) == 15
    jawaban.update({nama: 'Saya menghitung langkahnya.' for nama in kerja['nama'] if nama.startswith('cara_')})
    jawaban[tombol[0]['name']] = tombol[0]['value']
    kode, _, _ = uji.minta(kerja['aksi'], data=jawaban)
    assert kode == 200
    with uji.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM konfirmasi_hasil').fetchone()[0] == 0
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 0

    kode, profil, _ = uji.minta(f'/anak/{siswa}', auth=ident)
    assert kode == 200
    tinjau = [t for t in _kontrol(profil).tautan if t.startswith('/sesi/') and t.count('/') == 2]
    # Kartu utama dan riwayat dapat menunjuk sesi yang sama; pilih satu tujuan unik.
    assert len(set(tinjau)) == 1
    kode, hasil, _ = uji.minta(tinjau[0], auth=ident)
    assert kode == 200
    form_hasil = _satu_form(hasil, tinjau[0])
    konfirmasi = [b for b in form_hasil['tombol'] if b.get('formaction', '').endswith('/konfirmasi')]
    assert len(konfirmasi) == 1
    with uji.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM konfirmasi_hasil').fetchone()[0] == 0
    pemahaman = {nama: 'bisa_menjelaskan' for nama in form_hasil['nama'] if nama.startswith('cek_pemahaman_')}
    assert len(pemahaman) == 15
    kode, sah, _ = uji.minta(konfirmasi[0]['formaction'], auth=ident, data=pemahaman)
    assert kode == 200
    assert 'Hasil sudah dikonfirmasi' in sah
    kembali = [t for t in _kontrol(sah).tautan if t == f'/anak/{siswa}']
    assert len(kembali) == 1
    kode, profil, _ = uji.minta(kembali[0], auth=ident)
    assert kode == 200
    rencana_url = [t for t in _kontrol(profil).tautan if t == f'/anak/{siswa}?section=rencana']
    assert rencana_url
    kode, rencana, _ = uji.minta(rencana_url[0], auth=ident)
    assert kode == 200
    assert '1 dari 3 sesi terkonfirmasi' in rencana
    assert f'action="/siklus/{siswa}/buat"' not in rencana
    with uji.buka() as kon:
        assert kon.execute('SELECT COUNT(*) FROM konfirmasi_hasil').fetchone()[0] == 1
        assert kon.execute('SELECT COUNT(*) FROM snapshot_outcome').fetchone()[0] == 15

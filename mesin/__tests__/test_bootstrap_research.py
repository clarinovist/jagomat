"""Kontrak laporan bootstrap dan aritmetika asumsi, seluruh input sintetis."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import sys
import re

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bootstrap_research as b
import bootstrap_content as c


class Struktur(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.tags = []
        self.handlers = []
        self.regions = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append(tag)
        if 'id' in d:
            self.ids.append(d['id'])
        if tag == 'a':
            self.links.append(d.get('href', ''))
        self.handlers.extend(k for k in d if k.lower().startswith('on'))
        if d.get('role') == 'region':
            self.regions.append(d)


def test_struktur_publik_dan_aksesibilitas_native():
    html = b.halaman().decode()
    p = Struktur()
    p.feed(html)
    assert len(p.ids) == len(set(p.ids))
    assert all(h[1:] in p.ids for h in p.links if h.startswith('#'))
    assert not set(p.tags) & {'script', 'iframe', 'form', 'input'}
    assert not p.handlers
    assert {'action-plan', 'biaya', 'sdm', 'economics', 'kas', 'asumsi', 'sumber'} <= set(p.ids)
    assert p.regions and all(d.get('tabindex') == '0' and d.get('aria-label') for d in p.regions)
    assert html.count('<summary>') >= 20
    for label in ('Fakta sumber', 'Proxy', 'Asumsi manajemen', 'Hasil hitung', 'Rekomendasi'):
        assert label in html
    assert html.count('(Asumsi)') > 20
    assert len(c.SENIN) <= 10
    assert len(c.TAHAP) == 6
    assert len(c.RISIKO) >= 13
    assert 'bukan forecast' in html.lower()
    assert 'belum diinstrumentasi' in html
    assert 'kunci/reducer deterministik' in html


def test_model_cohort_konsisten_dan_kas_tidak_mengandalkan_revenue():
    for i, s in enumerate(b.SKENARIO):
        rows = b.cohort(i)
        assert len(rows) == 12
        assert rows[0]['revenue'] == rows[1]['revenue'] == 0
        prev = 0
        for r in rows:
            assert r['awal'] == prev
            assert r['akhir'] == pytest.approx(prev * .95 + r['baru'])
            assert r['rata'] == pytest.approx((prev + r['akhir']) / 2)
            assert r['revenue'] == pytest.approx(r['rata'] * 35_000)
            assert r['mrr'] == pytest.approx(r['akhir'] * 35_000)
            assert r['neto'] == pytest.approx(r['revenue'] - r['keluar'])
            assert r['onboarding'] == pytest.approx(r['akses'] * 10_000)
            assert r['kontribusi'] == pytest.approx(r['rata'] * 15_020 - r['onboarding'])
            prev = r['akhir']
        assert rows[-1]['akhir'] < s['kapasitas']
        keluar = sum(r['keluar'] for r in rows)
        assert b.modal(i, 12) == pytest.approx(s['awal'] + keluar * 1.15 + s['darurat'])
        assert b.modal(i, 12) - s['awal'] - keluar > s['darurat']
        assert sum(r['revenue'] for r in rows) < rows[-1]['mrr'] * 12


def test_contribution_dan_sensitivitas_tidak_menghitung_support_dua_kali():
    assert b.kontribusi_unit() == 15_020
    assert b.kontribusi_unit(menit=30) == 20
    assert b.kontribusi_unit(arpa=29_000, menit=30, provider=10_000) == -12_812
    assert b.cohort(0, churn=.1)[-1]['akhir'] < b.cohort(0, churn=.02)[-1]['akhir']
    assert b.NILAI_FOUNDER == 96 * 100_000
    assert b.tetap(0) == 1_550_000
    assert b.tetap(1) == 9_250_000
    assert b.tetap(2) == 21_500_000
    assert 'Kas dalam plafon; ekonomi melampaui plafon' in b.ekonomi_html()


def test_pdf_valid_versi_dan_a4_tanpa_dependency_opsional():
    pdf = b.BERKAS_PDF.read_bytes()
    assert pdf.startswith(b'%PDF-') and pdf.rstrip().endswith(b'%%EOF')
    judul = '\ufeff' + f'Bootstrap Jagomat 2026 · {b.VERSI_ISI} · Jagomat'
    assert b'/Title <' + judul.encode('utf-16-be').hex().upper().encode() + b'>' in pdf
    assert f'Revisi isi · {b.VERSI_ISI}' in b.halaman().decode()
    kotak = re.findall(rb'/MediaBox\s*\[0 0 ([\d.]+) ([\d.]+)\]', pdf)
    assert kotak
    assert all(abs(float(w)-595) < 2 and abs(float(h)-842) < 2 for w, h in kotak)
    assert b'/Type /Catalog' in pdf and b'/Type /Page' in pdf
    assert b'/JavaScript' not in pdf
    assert b'127.0.0.1' not in pdf and b'localhost' not in pdf and b'file:' not in pdf
    for url in (b'https://jagomat.id/riset', b'https://jagomat.id/riset/persaingan-bimbel-2026'):
        assert b'/URI (' + url + b')' in pdf
    assert len(pdf) > 50_000


def test_pdf_gagal_aman_tanpa_path(monkeypatch, tmp_path):
    class Penangan:
        def _kirim(self, isi, status):
            self.isi, self.status = isi, status
    monkeypatch.setattr(b, 'BERKAS_PDF', tmp_path / 'privat-hilang.pdf')
    p = Penangan()
    b.kirim_pdf(p)
    assert p.status == 503
    assert b'privat-hilang' not in p.isi


def test_route_murni_tanpa_identitas_database_atau_state(monkeypatch):
    import public_http
    import sqlite3
    from io import BytesIO
    def dilarang(*a, **k):
        raise AssertionError('Riset tidak boleh membaca data atau identitas')
    monkeypatch.setattr(sqlite3, 'connect', dilarang)
    class Penangan:
        _identitas = dilarang
        _lolos_sandi = dilarang
        def __init__(self):
            self.wfile = BytesIO()
        def _kirim(self, isi):
            self.wfile.write(isi)
        def send_response(self, kode):
            assert kode == 200
        def send_header(self, *args):
            pass
        def end_headers(self):
            pass
    for path in (b.JALUR, b.JALUR_PDF):
        p = Penangan()
        assert public_http.tangani_get(p, path)
        assert p.wfile.getvalue()


def test_modul_dan_pdf_masuk_image():
    root = Path(b.__file__).parent
    docker = (root / 'Dockerfile').read_text()
    assert 'COPY --chown=osn:osn *.py /app/' in docker
    assert 'COPY --chown=osn:osn publik/ /app/publik/' in docker
    assert (root / 'bootstrap_content.py').is_file()
    assert (root / 'bootstrap_research.py').is_file()
    assert b.BERKAS_PDF.is_file()

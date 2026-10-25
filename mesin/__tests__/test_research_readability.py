"""Ukuran informasi dan tautan pada laporan riset publik."""
import re

import pytest

import competitive_research as R
import design_tokens as T
from test_ui_readability import aturan


@pytest.mark.parametrize('selector', [
    '.riset-chip', '.riset-label', '.riset-confidence', '.riset-sumbu-y',
    '.riset-kuadran small', '.riset-sumbu-x', '.riset-catatan', '.riset-titik',
])
def test_teks_riset_memakai_token_label(selector):
    blok = aturan(R.GAYA_RISET, selector)
    assert blok
    # Media query boleh hanya mengubah layout; deklarasi font sebelumnya
    # tetap berlaku. Semua ukuran eksplisit harus menjaga batas label.
    ukuran = re.findall(r'font-size:\s*([^;]+)', ';'.join(blok))
    assert ukuran
    assert all(nilai == T.UKURAN_TEKS_LABEL for nilai in ukuran)


def test_target_sentuh_tidak_memperbesar_tautan_cetak():
    cetak = R.GAYA_RISET.split('@media print {', 1)[1]
    blok = aturan(cetak, 'a')[-1]
    assert 'display: inline;' in blok
    assert 'min-height: 0;' in blok
    assert 'min-width: 0;' in blok


def test_tautan_sumber_footer_dan_inline_punya_target_sentuh():
    blok = aturan(R.GAYA_RISET, 'a')[0]
    assert f'min-height: {T.TARGET_SENTUH}' in blok
    assert 'display: inline-flex' in blok


def test_halaman_riset_memuat_stylesheet_yang_diuji():
    assert R.GAYA_RISET.encode() in R.halaman()

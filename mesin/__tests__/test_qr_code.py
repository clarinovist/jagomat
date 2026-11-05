"""Kode QR tautan sesi (stdlib): matriks identik bit per bit dengan libqrencode.

Golden dibangkitkan sekali dengan `qrencode -t ASCII -l M -8 -m 0 <teks>`
(libqrencode, Homebrew) untuk mask yang dipakai libqrencode; CI tidak butuh
qrencode. Pemilihan mask boleh berbeda (skor penalti), keduanya QR sah.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import qr_code  # noqa: E402

# Versi 5-M (37×37), mask 6: panjang tautan produksi (25 + 43 karakter token).
GOLDEN_V5 = ("https://jagomat.id/mulai/" + "A" * 43, 6, ["1fd72b667f", "105256c141", "175c629b5d", "174001195d", "175554945d", "1047916141", "1fd555557f", "70f5900", "13fe22ff97", "526544c76", "f613fa7b1", "1292db358f", "197179b26d", "eaf16af19", "2ffe70a5f", "130c91d1ef", "7586cf257", "1978860e4", "2c21eead5", "88f735cf9", "14c59293fc", "1586cc6615", "9f730b7e9", "1a0854247d", "165f6bd973", "11b7464550", "1a5364c6c7", "1309d2119d", "1344ebfbf9", "19cdc117", "1fdc6e2d51", "105e438b13", "175fb79ff1", "1756c14ec5", "174a8ca191", "1049e835df", "1fd91ba16d"])
# Versi 8-M (49×49), mask 0: tiga pola alignment dan blok info versi.
GOLDEN_V8 = ("https://jagomat.id/mulai/" + "x" * 120, 0, ["1fcca8dddd17f", "1050ed7777741", "17454012aa35d", "174792988c25d", "1754be7ddd85d", "10478b47ffc41", "1fd555555557f", "11145dde00", "154af6ff77612", "69e9cf22202d", "ad6396888987", "13b371dfffd2", "1ee4cbb775638", "8818ea2020ad", "1351e7c8bb907", "a0f8a9dddfd2", "3c15ef777678", "88294e222021", "137fed4888987", "8ccb1d9d3d2", "14c63ab7ff858", "1e24b4e22201d", "19fccd7c001f7", "111037c5ddd12", "157565777558", "131688462211d", "ffbd5fc88bf7", "b6cf75ddd62", "e76c55377528", "a2345aa0028f", "15ca589ca9ad7", "15956975ddd70", "ddf6aa3775a9", "f38300a22241", "11cd491c88a57", "1d058f35d15f2", "aea2263f7928", "b8c188aaa28d", "8e9619c003d7", "e150375ddd72", "1c401e7f775f8", "12f4c62211d", "1fc9a95488b57", "10419fc5ffd12", "1751b3ff777f8", "174be65d101dc", "17538b36aab74", "104d22a1dde22", "1fd07acb7749b"])


def _baris(golden):
    teks, mask, baris = golden
    lebar = len(baris)
    harap = [[c == "1" for c in format(int(h, 16), f"0{lebar}b")] for h in baris]
    return teks, mask, harap


@pytest.mark.parametrize("golden", [GOLDEN_V5, GOLDEN_V8], ids=["v5", "v8"])
def test_matriks_identik_dengan_libqrencode(golden):
    teks, mask, harap = _baris(golden)
    assert qr_code.matriks(teks, mask=mask) == harap


def test_ukuran_versi_mengikuti_panjang_tautan():
    assert len(qr_code.matriks("a")) == 21
    assert len(qr_code.matriks("https://uji.jagomat.id/mulai/" + "z" * 43)) == 37
    assert len(qr_code.matriks("x" * 213)) == 57


def test_teks_di_atas_kapasitas_ditolak_bukan_dipotong():
    with pytest.raises(ValueError):
        qr_code.matriks("x" * 214)


def test_pilihan_mask_deterministik_dan_berpola_finder():
    teks = "https://jagomat.id/mulai/" + "Q" * 43
    a, b = qr_code.matriks(teks), qr_code.matriks(teks)
    assert a == b
    for x0, y0 in ((0, 0), (len(a) - 7, 0), (0, len(a) - 7)):
        assert all(a[y0][x0 + i] for i in range(7)) and all(a[y0 + i][x0] for i in range(7))


def test_svg_tanpa_skrip_dengan_zona_senyap_dan_warna_dari_pemanggil():
    isi = qr_code.svg("https://jagomat.id/mulai/abc", warna_gelap="GELAP", warna_terang="TERANG",
                      label='Kode "tautan"')
    assert isi.startswith("<svg") and "<script" not in isi and "href" not in isi
    assert 'viewBox="0 0 37 37"' in isi  # 28 byte → versi 3 (29 modul) + 2×4 zona senyap
    assert 'fill="GELAP"' in isi and 'fill="TERANG"' in isi
    assert 'aria-label="Kode &quot;tautan&quot;"' in isi


# Versi 1-M, satu golden per mask 0..7 (libqrencode memilih mask itu untuk teks ini):
# memastikan kedelapan rumus mask benar, karena pemilih penalti bisa memakai mask apa pun.
GOLDEN_PER_MASK = (
    ('sesi-0', 0, ['1fcf7f', '105f41', '174d5d', '17425d', '17535d', '104e41', '1fd57f', '400', '154d12', '199ea3', 'adaef', '3b3b1', 'c5ee9', '1869', '1fc11b', '104463', '175d53', '17429e', '1756dd', '104f8a', '1fdae3']),
    ('sesi-58', 1, ['1fd37f', '104a41', '17595d', '174d5d', '174b5d', '105341', '1fd57f', '500', '146825', '1c96c9', '196bb5', '148ecb', '4e3e3', '1433', '1fd071', '10452b', '174459', '174af4', '175fb7', '1046e0', '1fd7c9']),
    ('sesi-9', 2, ['1fca7f', '104641', '17545d', '17595d', '175f5d', '105941', '1fd57f', '1700', '17c97c', '17352d', 'ee9e', 'a903f', 'a4698', '13e7', '1fcd6a', '105bcd', '175132', '175510', '175eac', '104804', '1fd292']),
    ('sesi-3', 3, ['1fdd7f', '105541', '17415d', '175b5d', '174c5d', '104441', '1fd57f', '1400', '16ec4b', 'da92d', '12d9f3', '199589', '1bfe98', '1c8a', '1fd0dc', '1053dd', '174e4f', '1754a6', '1752ac', '104769', '1fd324']),
    ('sesi-6', 4, ['1fde7f', '104541', '174e5d', '17595d', '175b5d', '105541', '1fd57f', '1400', '1179f9', '1c2dce', '1cd982', '1aa723', '1c667b', '1704', '1fda76', '1044e1', '1751e1', '174df3', '1749b0', '104b18', '1fda71']),
    ('sesi-372', 5, ['1fcb7f', '105541', '175b5d', '17505d', '17475d', '104541', '1fd57f', '1700', '1059ce', '11856c', '3426e', '1dac3f', '8ccd3', '13f7', '1fc16a', '1043ad', '174d21', '174130', '174477', '104824', '1fd692']),
    ('sesi-4', 6, ['1fd97f', '105b41', '17515d', '17485d', '17555d', '104f41', '1fd57f', 'b00', '13f997', '10895c', '14f0d7', '178e07', '9f043', '1304', '1fd9f8', '10539c', '175b4b', '175f28', '174077', '104ce7', '1fde00']),
    ('sesi-20', 7, ['1fc87f', '104741', '17435d', '17485d', '174d5d', '105341', '1fd57f', 'f00', '12dca0', '1d3063', '5758d', '39e28', '17dd59', '160b', '1fc892', '1057b1', '174a41', '175217', '17411d', '104cd8', '1fdb2a']),
)


@pytest.mark.parametrize("golden", GOLDEN_PER_MASK, ids=[f"mask{g[1]}" for g in GOLDEN_PER_MASK])
def test_setiap_mask_identik_dengan_libqrencode(golden):
    teks, mask, harap = _baris(golden)
    assert qr_code.matriks(teks, mask=mask) == harap

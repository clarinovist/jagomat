"""Renderer murni blok "Peta Kemampuan lengkap" di halaman orang tua (D1-3): semua bagian, <meter>, escape catatan.

Data sintetis. Renderer menerima hasil `peta_laporan_store.terbit_terakhir` (isi, catatan, diterbitkan) dan TIDAK
boleh memuat nama Guru, kontak, kunci/malrule/diagnosis/pembahasan, peringkat, style inline, JS, atau warna heksa.
Tes ini menjadi sasaran mutation di `test_peta_laporan_ortu_mutation.py`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import peta_laporan_ortu_pages as halaman  # noqa: E402

KATA_TERLARANG = ("kunci", "malrule", "diagnos", "kode_final", "kode_usulan", "pembahasan", "jawaban benar",
                  "tel:", "wa.me", "peringkat", "persentil")
CATATAN = "Anak sudah mantap berhitung.\nLatih pengukuran tiga kali seminggu."


def _isi(**ubah) -> dict:
    isi = {
        "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
        "jumlah_soal": 15,
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 7}],
        "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran"], "ringkasan_perlu": ["Pengukuran"],
    }
    return {**isi, **ubah}


def _peta(catatan=CATATAN, **ubah_isi) -> dict:
    return {"isi": _isi(**ubah_isi), "catatan": catatan, "diterbitkan": "2026-11-24 15:00:00"}


def _teks(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _meter(html: str) -> list:
    return [dict(re.findall(r'([a-z-]+)="([^"]*)"', tag)) for tag in re.findall(r"<meter\b[^>]*>", html)]


def test_tanpa_peta_tidak_merender_apa_pun():
    assert halaman.blok_peta(None) == ""


def test_judul_lencana_dan_dua_tanggal_format_awam():
    html = halaman.blok_peta(_peta())
    assert "Peta Kemampuan lengkap" in html and 'id="ortu-peta"' in html
    assert "Ditinjau Guru Jagomat" in html
    assert "18 November 2026" in html and "24 November 2026" in html
    assert "15:00" not in html and "2026-11-24" not in html


def test_skor_dan_kategori_tampil():
    teks = _teks(halaman.blok_peta(_peta()))
    assert "47" in teks and "dari 100" in teks and "Perlu penguatan" in teks


def test_penguasaan_per_materi_satu_baris_dan_meter_nilai_maks_benar():
    html = halaman.blok_peta(_peta())
    assert "Penguasaan per materi" in html
    meter = _meter(html)
    assert [(m["min"], m["max"], m["value"]) for m in meter] == [("0", "5", "5"), ("0", "7", "2")]
    assert "5 dari 5 benar" in html and "2 dari 7 benar" in html
    assert "Pengukuran" in meter[1]["aria-label"] and "2 dari 7" in meter[1]["aria-label"]


def test_banyak_materi_semuanya_dapat_meter_sendiri_urut_sama():
    materi = [{"materi": "Materi %d" % n, "benar": n % 4, "total": 3 + n % 4} for n in range(12)]
    html = halaman.blok_peta(_peta(per_materi=materi))
    meter = _meter(html)
    assert len(meter) == 12 and html.count("<li") >= 12
    assert [m["value"] for m in meter] == [str(m["benar"]) for m in materi]
    assert [m["max"] for m in meter] == [str(m["total"]) for m in materi]
    urutan = [html.index("Materi %d<" % n) if ("Materi %d<" % n) in html else html.index("Materi %d " % n)
              for n in range(12)]
    assert urutan == sorted(urutan)


def test_meter_tanpa_style_inline_js_dan_warna_heksa():
    html = halaman.blok_peta(_peta())
    assert "style=" not in html.lower() and "<script" not in html.lower() and "onclick" not in html.lower()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", html)


def test_nama_materi_di_escape_termasuk_atribut_meter():
    html = halaman.blok_peta(_peta(per_materi=[{"materi": 'A"><i>B</i>', "benar": 1, "total": 2}],
                                   kuat=[], perlu_dilatih=['A"><i>B</i>']))
    assert "<i>" not in html and "&lt;i&gt;" in html and "&quot;" in html
    assert 'aria-label="Penguasaan A&quot;&gt;' in html


def test_perlu_dilatih_daftar_bernomor_sesuai_urutan_isi():
    html = halaman.blok_peta(_peta(perlu_dilatih=["Pengukuran", "Berhitung"]))
    assert "Yang paling perlu dilatih dulu" in html
    bagian = html[html.index("<ol"):html.index("</ol>")]
    assert bagian.index("Pengukuran") < bagian.index("Berhitung")
    assert bagian.count("<li") == 2


def test_perlu_dilatih_kosong_kalimat_positif_tanpa_daftar_bernomor():
    html = halaman.blok_peta(_peta(perlu_dilatih=[]))
    assert "Yang paling perlu dilatih dulu" in html
    assert "Semua materi sudah baik, pertahankan" in html and "<ol" not in html


def test_materi_kuat_tampil_bila_ada_dan_bagian_hilang_bila_kosong():
    ada = halaman.blok_peta(_peta(kuat=["Berhitung", "Geometri"]))
    assert "Materi yang sudah kuat" in ada and "Geometri" in ada
    assert "Materi yang sudah kuat" not in halaman.blok_peta(_peta(kuat=[]))


def test_catatan_guru_paragraf_dan_baris_baru_dihormati():
    html = halaman.blok_peta(_peta(catatan="Paragraf satu.\nBaris dua.\r\n\r\nParagraf kedua."))
    assert "Catatan dari Guru" in html
    assert html.count("<p>Paragraf") == 2 and "Paragraf satu.<br>Baris dua." in html
    assert "\n" not in html[html.index("Paragraf satu"):html.index("Paragraf kedua")].replace("<br>", "")


def test_catatan_html_dan_skrip_tampil_ter_escape():
    kotor = '<script>alert(1)</script><img src=x onerror=alert(2)> & "kutip"'
    html = halaman.blok_peta(_peta(catatan=kotor))
    assert "<script" not in html.lower() and "<img" not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "&amp;" in html and "&quot;kutip&quot;" in html


def test_tanpa_nama_guru_akun_kontak_atau_kata_terlarang_walau_ada_kunci_tambahan():
    peta = {**_peta(), "guru": "guru-rahasia-sintetis", "diterbitkan_oleh": "guru-rahasia-sintetis",
            "nama": "Nama Anak Sintetis", "wa": "6281234567890"}
    html = halaman.blok_peta(peta)
    for rahasia in ("guru-rahasia-sintetis", "Nama Anak Sintetis", "6281234567890"):
        assert rahasia not in html
    badan = _teks(html).lower()
    for kata in KATA_TERLARANG:
        assert kata not in badan, kata
    assert "href=" not in html and "<form" not in html and "<img" not in html and "<svg" not in html


@pytest.mark.parametrize("benar,total", [(0, 1), (1, 1), (0, 200), (199, 200)])
def test_meter_batas_nilai(benar, total):
    html = halaman.blok_peta(_peta(per_materi=[{"materi": "M", "benar": benar, "total": total}], kuat=[], perlu_dilatih=[]))
    meter = _meter(html)[0]
    assert (meter["min"], meter["max"], meter["value"]) == ("0", str(total), str(benar))

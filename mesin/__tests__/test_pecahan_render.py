"""Kontrak tampilan pecahan: bertumpuk, aman, dan tidak menebak satuan/tanggal."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import choice_pages  # noqa: E402
import pecahan  # noqa: E402
import visual_renderer  # noqa: E402


def test_pecahan_dasar_bertumpuk_dan_berlabel():
    hasil = pecahan.render("Berapakah 5/6 + 1/3?")
    assert hasil.count('class="pecahan"') == 2
    assert 'aria-label="5 per 6"' in hasil
    assert 'aria-label="1 per 3"' in hasil
    assert "5/6" not in hasil


def test_pecahan_pi_tetap_ditampilkan_bertumpuk():
    # 22/7 adalah pecahan (π), bukan tanggal; tetap harus bertumpuk.
    hasil = pecahan.render("Gunakan π = 22/7.")
    assert 'aria-label="22 per 7"' in hasil


def test_satuan_tanggal_versi_dan_rantai_tidak_diubah():
    for teks in ("Kecepatan 50 km/jam.", "Tanggal 2026/11/03.", "Versi v1/2.", "Rantai 1/2/3."):
        assert "pecahan" not in pecahan.render(teks), teks


def test_html_di_escape_sebelum_diberi_markup():
    hasil = pecahan.render("<b>5/6</b>")
    assert "&lt;b&gt;" in hasil and "<b>" not in hasil
    assert 'aria-label="5 per 6"' in hasil


def test_angka_di_luar_batas_tidak_dianggap_pecahan():
    assert "pecahan" not in pecahan.render("Nilai 1234/5678.")
    assert 'aria-label="1 per 2"' in pecahan.render("(1/2)")


def test_renderer_pertanyaan_memakai_pecahan():
    hasil = visual_renderer._render_baris("Hitung 5/6 × 3/8", "kerja-teks-st", "kerja-tanya-st")
    assert 'class="pecahan"' in hasil
    assert 'class="kerja-teks-st"' in hasil


def test_opsi_pilihan_ganda_memakai_pecahan():
    class Opsi:
        label = "A"
        teks = "5/12"
        nilai = "5/12"
        id = "a"

    class Pilihan:
        opsi = [Opsi()]
        sesi_soal_id = 1

    assert 'aria-label="5 per 12"' in choice_pages.ringkas_opsi(Pilihan())
    assert 'aria-label="5 per 12"' in choice_pages.radio_pilihan(Pilihan())

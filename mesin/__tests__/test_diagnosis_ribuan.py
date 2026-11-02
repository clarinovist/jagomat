"""Ribuan gaya Indonesia dinilai benar sebagai bilangan bulat, bukan desimal.

Bug yang dijaga: normalisasi() dulu hanya mengubah koma menjadi titik, jadi
"8.000" (delapan ribu) tidak pernah sama dengan kunci "8000" — jawaban benar
tercatat salah. Sekitar 12,4% soal berkunci bilangan bulat >= 1000, sehingga
kesalahan ini mencemari angka kecocokan, bukan sekadar satu soal.

Batas yang diuji sama pentingnya dengan perbaikannya: desimal satu digit
("1,5"), teks bersatuan ("6 jam 25 menit"), dan daftar bilangan pendek tidak
boleh ikut dirapatkan hanya karena kebetulan berisi tiga digit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diagnosis import diagnosa, normalisasi, setara  # noqa: E402

MALRULE_RIBUAN = [
    {"malrule_id": "ribuan.salah_salin", "jawaban": "2.400", "kode": "H",
     "alasan": "angka benar tapi nolnya kurang satu"},
]


def _usulan(kunci, jawaban, malrule=(), cara="Saya hitung"):
    """diagnosa() tanpa metadata soal: jalur skalar, termasuk malrule."""
    return diagnosa(kunci, jawaban, cara, "", False, list(malrule))


# ── Ribuan titik: "8.000" berarti delapan ribu ───────────────────────────────


def test_ribuan_titik_dibaca_bulat_bukan_desimal():
    assert normalisasi("8.000") == normalisasi("8000") == "8000"
    assert normalisasi("1.234.567") == "1234567"


def test_ribuan_titik_setara_dua_arah():
    assert setara("8000", "8.000")
    assert setara("8.000", "8000")
    assert setara("357000", "357.000")
    assert setara("1.234.567", "1234567")


def test_ribuan_titik_negatif_dan_bertanda_plus():
    assert setara("-1500", "-1.500")
    assert setara("+2500", "+2.500")


# ── Ribuan spasi: "8 000" berarti delapan ribu ───────────────────────────────


def test_ribuan_spasi_setara():
    assert normalisasi("8 000") == "8000"
    assert setara("8000", "8 000")
    assert setara("12 500", "12500")
    assert setara("1 234 567", "1234567")


# ── Yang tidak boleh dirapatkan ──────────────────────────────────────────────


def test_desimal_koma_dan_titik_tetap_desimal():
    """Satu digit di belakang pemisah adalah desimal, bukan ribuan."""
    assert normalisasi("1,5") == normalisasi("1.5") == "1.5"
    assert setara("0,85", "0.85")


def test_koma_tetap_desimal_bahkan_dengan_tiga_angka():
    """Keputusan aman: koma tidak pernah dibaca pemisah ribuan.

    Penulisan Indonesia memakai titik untuk ribuan dan koma untuk desimal,
    jadi hanya titik/spasi yang dirapatkan. Perilaku lama untuk kunci desimal
    ("2,400" berarti 2,4) tidak berubah sama sekali.
    """
    assert normalisasi("2,400") == "2.400"
    assert normalisasi("0,125") == "0.125"
    # "2.400" (dua ribu empat ratus) bukan "2,400" (2,4). Bacaan ini dicatat
    # sebagai pertanyaan produk, bukan dilonggarkan diam-diam.
    assert not setara("2,400", "2.400")


def test_desimal_tidak_lolos_hanya_karena_kunci_ribuan():
    """Kunci 2400 bukan 2,4 — jangan menolong jawaban desimal yang salah."""
    assert not setara("2,4", "2.400")
    assert not setara("2,4", "2400")
    assert not setara("2.4", "2400")
    assert not _usulan("2.400", "2,4").benar


def test_teks_bersatuan_tidak_dirapatkan():
    assert normalisasi("6 jam 25 menit") == "6 jam 25 menit"
    assert setara("6 jam 25menit", "6 jam 25 menit")
    assert setara("357.000 liter", "357000 liter")


def test_daftar_bilangan_pendek_tetap_daftar():
    """Daftar tiga bilangan tiga digit tidak dibaca sebagai satu bilangan.

    "125 250 375" secara bentuk sama dengan grup ribuan. Karena itu grup
    pertama berspasi hanya dirapatkan bila 1-2 digit; daftar tetap daftar.
    """
    assert normalisasi("125 250 375") == "125 250 375"
    assert setara("125 250 375", "125, 250, 375")
    assert setara("100 200 300", "100, 200, 300")


def test_grup_bukan_tiga_digit_tidak_dirapatkan():
    for rusak in ("8.00", "80.00", "8.0000", "8.000.00", "8000.000"):
        assert normalisasi(rusak) == rusak
        assert not setara(rusak, "8000")


def test_salah_satu_satuan_tetap_salah():
    assert not setara("8001", "8000")
    assert not setara("8001", "8.000")
    assert not _usulan("8000", "8001").benar
    assert not _usulan("8000", "8.001").benar


# ── Malrule ikut memakai normalisasi yang sama ───────────────────────────────


def test_malrule_ribuan_terdeteksi():
    """Malrule berbentuk ribuan harus tetap menangkap jawaban bentuk polos."""
    u = _usulan("8000", "2400", MALRULE_RIBUAN)
    assert (u.benar, u.kode, u.malrule_id) == (False, "H", "ribuan.salah_salin")


def test_malrule_ribuan_tidak_mencuri_jawaban_benar():
    u = _usulan("8000", "8.000", MALRULE_RIBUAN)
    assert (u.benar, u.kode) == (True, None)
    assert u.yakin


def test_malrule_desimal_tidak_menangkap_bilangan_bulat():
    """Desimal "2,4" tidak boleh menangkap "2.400" (dua ribu empat ratus)."""
    u = _usulan("9000", "2.400", [{"malrule_id": "desimal", "jawaban": "2,4",
                                   "kode": "K", "alasan": "salah hitung"}])
    assert (u.benar, u.kode, u.malrule_id) == (False, None, None)


# ── End-to-end: alur baca 5 langkah tanpa malrule ────────────────────────────


def test_diagnosa_end_to_end_ribuan_titik():
    u = _usulan("8000", "8.000", malrule=[])
    assert (u.benar, u.kode, u.alasan) == (True, None, "jawaban benar")
    assert u.yakin


def test_diagnosa_end_to_end_ribuan_spasi():
    u = _usulan("8000", "8 000", malrule=[])
    assert (u.benar, u.kode, u.yakin) == (True, None, True)

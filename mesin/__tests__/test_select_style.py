"""Kontrak visual dropdown native dengan chevron yang konsisten."""

import design_tokens as T
from admin_style import GAYA_ADMIN
from assistant_style import GAYA_PENDAMPING
from form_style import GAYA_SELECT
from style_stitch import GAYA_STITCH
from teacher_style import GAYA_GURU


def test_chevron_select_punya_ruang_kanan_dan_posisi_konsisten():
    aturan = GAYA_SELECT.split(
        "select:not([multiple]):not([size]) {", 1
    )[1].split("}", 1)[0]
    assert "-webkit-appearance: none !important" in aturan
    assert "appearance: none !important" in aturan
    assert f"padding-inline-end: {T.SP_7} !important" in aturan
    assert f"right {T.SP_5} center" in aturan
    assert f"right {T.SP_4} center" in aturan
    assert f"background-size: {T.SP_2} {T.SP_2}, {T.SP_2} {T.SP_2}" in aturan
    assert T.TEKS_VARIAN in aturan


def test_select_multiple_dan_size_tidak_diganti_chevronnya():
    assert "select:not([multiple]):not([size])" in GAYA_SELECT
    assert "select {" not in GAYA_SELECT


def test_mode_kontras_paksa_memulihkan_indikator_native():
    fallback = GAYA_SELECT.split("@media (forced-colors: active)", 1)[1]
    assert "appearance: auto !important" in fallback
    assert "background-image: none !important" in fallback


def test_gaya_select_terpasang_di_semua_shell_form():
    for gaya in (GAYA_STITCH, GAYA_GURU, GAYA_ADMIN, GAYA_PENDAMPING):
        assert GAYA_SELECT in gaya

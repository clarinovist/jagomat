"""Modul 4: penyelesaian follow-up operasi_berkurung & volume_prisma_tabung + uji regresi."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction as F
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assessment_revision import kontrak  # noqa: E402
from diagnosis import diagnosa  # noqa: E402
from generator import buat_soal  # noqa: E402
from templates import REGISTRI  # noqa: E402
from topic_solid_geometry_visual import proyeksi_geometri_ruang  # noqa: E402


def _usulan(soal, jawaban: str):
    aturan = [
        {"malrule_id": m.id, "jawaban": m.jawaban, "kode": m.kode, "alasan": m.alasan}
        for m in soal.malrule
    ]
    return diagnosa(soal.kunci, jawaban, "[pilihan] hitung_kertas", "", False, aturan, soal=soal)


def test_operasi_berkurung_revisi2_rasional_tanpa_floor(monkeypatch):
    # ((3 + 4) * 5 - 6) / 3 = 29 / 3 (bukan floor 9!)
    soal = REGISTRI["operasi_berkurung"](3, 4, 5, 6, 3, revisi_penilaian=2)
    assert soal.parameter["revisi_penilaian"] == 2
    assert kontrak(soal) == "rasional-eksak-v1"
    rule = next(m for m in soal.malrule if m.id == "rev2.berkurung.bagi_seluruh")
    assert rule.jawaban == "29/3"
    assert _usulan(soal, "29/3").malrule_id == "rev2.berkurung.bagi_seluruh"
    assert _usulan(soal, "58/6").malrule_id == "rev2.berkurung.bagi_seluruh"
    assert _usulan(soal, "9").malrule_id is None

    # Default writer tidak berubah bila OSN_KATALOG_LANJUTAN nonaktif.
    monkeypatch.setenv("OSN_KATALOG_LANJUTAN", "0")
    lama = buat_soal("operasi_berkurung", 7, "P5", "aritmetika-dasar")
    assert "revisi_penilaian" not in lama.parameter

    monkeypatch.setenv("OSN_KATALOG_LANJUTAN", "1")
    baru = buat_soal("operasi_berkurung", 7, "P5", "aritmetika-dasar")
    assert baru.parameter["revisi_penilaian"] == 2
    assert baru.kunci == lama.kunci
    assert replace(REGISTRI["operasi_berkurung"](**baru.parameter), level="P5") == baru


def test_volume_prisma_tabung_bebas_label_segitiga_dan_revisi2_eksak(monkeypatch):
    # Even legacy tabung harus bebas alasan "luas alas segitiga" yang keliru.
    soal_tabung_lama = REGISTRI["volume_prisma_tabung"]("tabung_V", r=7, t=5)
    for m in soal_tabung_lama.malrule:
        assert "segitiga" not in m.alasan.lower()

    # Prisma balik dengan V=60, a=8, t_segitiga=5 -> kunci t_prisma=3; lupa 1/2 -> 60/40 = 3/2 (bukan kunci+1 = 4)
    soal_prisma_rev2 = REGISTRI["volume_prisma_tabung"](
        "prisma_balik", a=8, t_segitiga=5, t_prisma=3, V=60, revisi_penilaian=2,
    )
    assert soal_prisma_rev2.kunci == "3"
    rule_setengah = next(m for m in soal_prisma_rev2.malrule if m.id == "rev2.volprisma.lupa_setengah_segitiga")
    assert F(rule_setengah.jawaban.replace(",", ".")) == F(3, 2)
    assert _usulan(soal_prisma_rev2, "3/2").malrule_id == "rev2.volprisma.lupa_setengah_segitiga"
    assert _usulan(soal_prisma_rev2, "1,5").malrule_id == "rev2.volprisma.lupa_setengah_segitiga"

    # Visual tetap menerima marker revisi_penilaian=2 pada volume_prisma_tabung & menolak marker cacat.
    monkeypatch.setenv("OSN_KATALOG_LANJUTAN", "1")
    s_gen = buat_soal("volume_prisma_tabung", 3, "P5", "geometri-ruang")
    assert s_gen.parameter["revisi_penilaian"] == 2
    lama_param = {k: v for k, v in s_gen.parameter.items() if k != "revisi_penilaian"}
    proj = proyeksi_geometri_ruang(s_gen.template_id, s_gen.parameter)
    assert proj == proyeksi_geometri_ruang(s_gen.template_id, lama_param)
    assert proj is not None and proj[1].jenis == "geometri_ruang"
    for marker_buruk in (1, True, "2", 3):
        with pytest.raises(ValueError, match="revisi penilaian"):
            proyeksi_geometri_ruang("volume_prisma_tabung", {**s_gen.parameter, "revisi_penilaian": marker_buruk})


@pytest.mark.parametrize("revisi_salah", (None, 0, 1, True, "2", 3))
def test_operasi_berkurung_menolak_revisi_tak_didukung(revisi_salah):
    with pytest.raises(ValueError, match="revisi penilaian"):
        REGISTRI["operasi_berkurung"](3, 4, 5, 6, 3, revisi_penilaian=revisi_salah)

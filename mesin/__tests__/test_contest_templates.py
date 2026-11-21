"""Kontrak generik tiap template Latihan Lomba: 1.000 seed, kunci terverifikasi independen."""
import ast
import json
import random
import re
from pathlib import Path
from xml.etree import ElementTree

import pytest

import contest_core as C
import contest_templates

JUMLAH_SEED = 1000
KAPASITAS_MIN = 30          # varian berbeda minimal per template agar ~40 sesi tidak kehabisan soal
KUNCI_BERBEDA_MIN = 3
MESIN = Path(__file__).resolve().parent.parent
BERKAS_LOMBA = sorted(MESIN.glob("contest_*.py"))
BERKAS_TEMPLATE = sorted(list(MESIN.glob("contest_templates_*.py")) + list(MESIN.glob("contest_svg_*.py")))
IMPOR_TERLARANG = {"urllib", "http", "socket", "requests", "subprocess", "sqlite3", "database",
                   "llm", "os"}
TEMPLATE = contest_templates.katalog()


def _soal(template, seed):
    return C.buat_soal(template, random.Random(seed))


@pytest.fixture(scope="module")
def sapuan():
    return {t.id: [_soal(t, seed) for seed in range(JUMLAH_SEED)] for t in TEMPLATE}


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_seribu_seed_menghasilkan_soal_sah_dengan_metadata_konsisten(template, sapuan):
    soal_semua = sapuan[template.id]
    assert len(soal_semua) == JUMLAH_SEED
    assert {s.template_id for s in soal_semua} == {template.id}
    assert {(s.topik, s.jenis, s.tingkat) for s in soal_semua} == {
        (template.topik, template.jenis, template.tingkat)}
    assert len({s.inggris for s in soal_semua}) == 1


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_kunci_sama_dengan_hitung_ulang_verifikator_independen(template, sapuan):
    for soal in sapuan[template.id]:
        parameter = json.loads(soal.parameter)
        assert template.verifikator(parameter) == soal.kunci, (soal.teks, soal.parameter)


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_soal_dapat_dibangun_ulang_persis_dari_parameter(template, sapuan):
    for soal in sapuan[template.id][:50]:
        assert template.bangun(json.loads(soal.parameter)) == soal


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_seed_sama_menghasilkan_soal_sama(template):
    assert _soal(template, 123) == _soal(template, 123)


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_kapasitas_varian_cukup_untuk_banyak_sesi(template, sapuan):
    varian = {C.tanda_tangan(s) for s in sapuan[template.id]}
    assert len(varian) >= KAPASITAS_MIN, f"hanya {len(varian)} varian"


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_kunci_tidak_konstan(template, sapuan):
    kunci = {s.kunci for s in sapuan[template.id]}
    assert len(kunci) >= KUNCI_BERBEDA_MIN, f"kunci hanya {sorted(kunci)}"


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_semua_svg_soal_dan_pilihan_adalah_xml_well_formed(template, sapuan):
    for soal in sapuan[template.id][:100]:
        for svg in [soal.svg, soal.kunci_svg] + [p.svg for p in soal.pengecoh]:
            if svg:
                ElementTree.fromstring(svg)


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_pembahasan_soal_angka_memuat_jawaban_akhir_di_langkah_terakhir(template, sapuan):
    for soal in sapuan[template.id][:200]:
        if soal.nilai is not None:
            assert str(soal.nilai) in soal.pembahasan[-1], (soal.kunci, soal.pembahasan)


@pytest.mark.parametrize("template", TEMPLATE, ids=lambda t: t.id)
def test_pengecoh_pg_berlabel_dan_pilihan_dapat_disusun_di_semua_posisi(template, sapuan):
    if template.jenis != C.JENIS_PG:
        pytest.skip("isian")
    for soal in sapuan[template.id][:50]:
        for posisi in range(4):
            pilihan = C.susun_pilihan(soal, posisi, random.Random(posisi))
            assert pilihan[posisi] == soal.kunci and len(set(pilihan)) == 4


@pytest.mark.parametrize("berkas", BERKAS_TEMPLATE, ids=lambda p: p.name)
def test_modul_template_tidak_memakai_hash_atau_acak_global(berkas):
    sumber = berkas.read_text()
    assert not re.search(r"\bhash\(", sumber)
    assert not re.search(r"\brandom\.(?!Random\b)\w+\(", sumber)


@pytest.mark.parametrize("berkas", BERKAS_LOMBA, ids=lambda p: p.name)
def test_modul_lomba_tanpa_impor_jaringan_db_atau_llm(berkas):
    for node in ast.walk(ast.parse(berkas.read_text())):
        if isinstance(node, ast.Import):
            akar = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            akar = {(node.module or "").split(".")[0]}
        else:
            continue
        assert not (akar & IMPOR_TERLARANG), (berkas.name, akar & IMPOR_TERLARANG)


@pytest.mark.parametrize("berkas", BERKAS_LOMBA, ids=lambda p: p.name)
def test_modul_lomba_tanpa_warna_hex_literal(berkas):
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", berkas.read_text()), berkas.name

"""Fase 0: denominator kanonis inventaris soal visual."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import topics  # noqa: E402
import visual_inventory  # noqa: E402
from visual_inventory import (  # noqa: E402
    DENOMINATOR_KANONIS,
    INVARIAN_RENDERER_AKTIF,
    STATUS_VISUAL,
    identitas_varian,
    inventaris_template,
)


def _pasangan_aktif():
    hasil = set()
    for topik_id in topics.daftar_topik():
        if topik_id == "campuran":
            continue
        paket = topics.ambil(topik_id)
        for level, urutan in paket.komposisi.items():
            for template_id in set(urutan):
                hasil.add((topik_id, level, template_id))
    return hasil


def test_denominator_kanonis_mencakup_semua_template_level_varian_aktif():
    pasangan_inventory = {
        (baris["topik_id"], baris["level"], baris["template_id"])
        for baris in DENOMINATOR_KANONIS
    }
    assert pasangan_inventory == _pasangan_aktif()
    assert len(DENOMINATOR_KANONIS) == len(
        {
            (r["topik_id"], r["level"], r["template_id"], r["varian"])
            for r in DENOMINATOR_KANONIS
        }
    )
    assert all(
        baris["bukti_klasifikasi"]["keputusan"] == baris["status"]
        for baris in DENOMINATOR_KANONIS
    )


def test_setiap_template_punya_bukti_eksplisit_dan_substantif():
    assert STATUS_VISUAL == frozenset(
        {"wajib_visual", "visual_pendamping", "sengaja_teks"}
    )
    template_ids = {item["template_id"] for item in inventaris_template()}
    assert not hasattr(visual_inventory, "_BUKTI_KELUARGA")
    assert set(visual_inventory._BUKTI_TEMPLATE) == template_ids
    assert len(template_ids) >= 97
    assert {"banyak_kelipatan", "sisa_operasi", "banyak_prima", "jumlah_kelipatan"} <= template_ids

    observasi_normal = set()
    boilerplate = (
        "tersedia lengkap dalam narasi soal",
        "menentukan relasi yang harus dibaca",
        "data utama soal",
        "seluruh data untuk menghitung",
    )
    for item in inventaris_template():
        bukti = item["bukti_klasifikasi"]
        assert set(bukti) == {
            "keluarga", "observasi", "konteks_varian", "keputusan",
        }
        assert bukti["keluarga"]
        assert len(bukti["observasi"].split()) >= 10
        assert bukti["keputusan"] == item["status"]
        assert not bukti["observasi"].startswith(
            (f'{item["template_id"]}:', f'{item["template_id"]} -')
        )
        assert not any(frasa in bukti["observasi"] for frasa in boilerplate)
        assert bukti["observasi"] in item["alasan"]
        observasi_normal.add(" ".join(bukti["observasi"].casefold().split()))

    # Bukti tidak boleh satu observasi keluarga yang dipakai berulang.
    assert len(observasi_normal) == len(template_ids)


def test_bukti_menyebut_konteks_semua_varian_yang_dideklarasikan():
    for item in inventaris_template():
        nilai = item["deklarasi_varian"]["nilai"]
        konteks = item["bukti_klasifikasi"]["konteks_varian"]
        if nilai == ("bawaan",):
            assert konteks == "bawaan"
            continue
        assert len(konteks.split()) >= 5
        nilai_diskriminator = {
            bagian.split("=", 1)[1]
            for identitas in nilai
            for bagian in identitas.split("|")
        }
        assert all(nama in konteks for nama in nilai_diskriminator), (
            item["template_id"], nilai_diskriminator, konteks,
        )


def test_renderer_khusus_yang_menghapus_deret_teks_adalah_wajib_visual():
    status = {i["template_id"]: i["status"] for i in inventaris_template()}
    assert status["korek_api"] == "wajib_visual"
    assert status["titik_segitiga"] == "wajib_visual"


def test_varian_dideklarasikan_dengan_diskriminator_per_template():
    for item in inventaris_template():
        deklarasi = item["deklarasi_varian"]
        assert set(deklarasi) == {"diskriminator", "nilai"}
        diskriminator = deklarasi["diskriminator"]
        nilai = deklarasi["nilai"]
        assert isinstance(diskriminator, tuple)
        assert isinstance(nilai, tuple) and nilai
        if nilai != ("bawaan",):
            assert diskriminator
            for identitas in nilai:
                assert all(f"{nama}=" in identitas for nama in diskriminator)


def test_varian_generator_yang_dideklarasikan_sama_dengan_runtime():
    """Audit terbatas 3.000 seed; deklarasi tetap sumber denominator kanonis."""
    for item in inventaris_template():
        paket = topics.ambil(item["topik_id"])
        template_id = item["template_id"]
        for level, deklarasi in item["varian_generator"].items():
            teramati = {
                identitas_varian(
                    template_id,
                    paket.parameter_untuk(template_id, random.Random(seed), level),
                )
                for seed in range(3000)
            }
            assert teramati == set(deklarasi), (item["topik_id"], template_id, level)


def test_generator_yang_mengeluarkan_varian_tak_dideklarasikan_gagal():
    with pytest.raises(ValueError, match="varian.*tidak dideklarasikan"):
        identitas_varian("debit", {"varian": "cari_harga", "volume": 2})


def test_api_inventaris_beku_sampai_struktur_bersarang():
    item = inventaris_template()[0]
    assert isinstance(item, MappingProxyType)
    assert isinstance(item["deklarasi_varian"], MappingProxyType)
    assert isinstance(item["varian_generator"], MappingProxyType)
    with pytest.raises(TypeError):
        item["status"] = "sengaja_teks"
    with pytest.raises(TypeError):
        item["varian_generator"]["P3"] = ("rusak",)


def test_inventaris_tidak_memakai_artefak_json_raksasa():
    akar = Path(__file__).resolve().parent.parent
    assert not (akar / "visual_inventory.json").exists()
    assert len((akar / "visual_inventory.py").read_text(encoding="utf-8").splitlines()) < 800


def test_renderer_svg_existing_tidak_aktif_tanpa_invariant_matematika():
    assert INVARIAN_RENDERER_AKTIF == {
        "korek_api": (
            "jumlah_ruas",
            "ruas_unik",
            "topologi_tersambung",
            "pertumbuhan_superset",
        ),
        "titik_segitiga": ("jumlah_titik", "titik_unik"),
    }

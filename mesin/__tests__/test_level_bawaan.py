"""Cadangan teks level lama tetap P3 saat level lebih rendah ditambahkan."""
from dataclasses import replace

import pytest

import generator
import question_context
import session_store
import templates
import topics


LEVEL_MASA_DEPAN = ("P1", "P2", "P3", "P4", "P5", "P6")


@pytest.fixture
def topik_sintetis():
    return topics.Topik(
        id="sintetis-level-bawaan",
        nama="Topik sintetis",
        judul_lembar="Latihan sintetis",
        judul_penilaian="Penilaian sintetis",
        templates={},
        komposisi={"P1": ("soal_p1",), "P3": ("soal_p3",)},
        profil={"P1": {"batas": 10}, "P3": {"batas": 100}},
    )


@pytest.mark.parametrize("pakai_writer", [False, True])
def test_komposisi_teks_lama_tetap_p3(monkeypatch, topik_sintetis, pakai_writer):
    monkeypatch.setattr(topics, "LEVEL", LEVEL_MASA_DEPAN)
    paket = topik_sintetis
    sumber = paket.komposisi
    if pakai_writer:
        sumber = {"P1": ("writer_p1",), "P3": ("writer_p3",)}
        paket = replace(paket, komposisi_writer=sumber)
    assert paket.komposisi_untuk("teks-lama") == sumber["P3"]


def test_profil_teks_lama_tetap_p3(monkeypatch, topik_sintetis):
    monkeypatch.setattr(topics, "LEVEL", LEVEL_MASA_DEPAN)
    assert topik_sintetis.profil_untuk("teks-lama") == topik_sintetis.profil["P3"]


def test_profil_otomatis_teks_lama_tetap_p3(monkeypatch, topik_sintetis):
    monkeypatch.setattr(question_context, "LEVEL", LEVEL_MASA_DEPAN)
    paket = {topik_sintetis.id: topik_sintetis}
    monkeypatch.setattr(topics, "daftar_topik", lambda: list(paket))
    monkeypatch.setattr(topics, "ambil", paket.__getitem__)
    assert question_context.profil_otomatis([topik_sintetis.id], "teks-lama") == "P3"


def test_level_terdekat_teks_lama_tetap_p3(monkeypatch, topik_sintetis):
    monkeypatch.setattr(templates, "LEVEL", LEVEL_MASA_DEPAN)
    assert session_store._level_terdekat("teks-lama", topik_sintetis.komposisi) == "P3"


@pytest.mark.parametrize(
    "tersedia, harapan",
    [(("P1", "P4"), "P4"), (("P2", "P4"), "P2"), ((), "teks-lama")],
)
def test_level_terdekat_tanpa_p3(monkeypatch, tersedia, harapan):
    monkeypatch.setattr(templates, "LEVEL", LEVEL_MASA_DEPAN)
    assert session_store._level_terdekat("teks-lama", tersedia) == harapan


@pytest.mark.parametrize("topik_id", topics.daftar_topik())
def test_level_terdekat_topik_nyata_tetap_seperti_lama(topik_id):
    paket = topics.ambil(topik_id)
    urut = [level for level in templates.LEVEL if level in paket.komposisi]
    assert urut, topik_id
    assert session_store._level_terdekat("teks-lama", paket.komposisi) == urut[0]


def test_level_bawaan_generator_memakai_templates():
    assert generator.LEVEL_BAWAAN is templates.LEVEL_BAWAAN
    assert templates.LEVEL_BAWAAN == "P3"

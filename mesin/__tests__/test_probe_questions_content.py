"""Konten pancingan per template: pemuat gagal tertutup, cakupan, dan render guru."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import probe_questions as pq  # noqa: E402
import topics  # noqa: E402

TEMPLATE = "luas_kotak_satuan"


@pytest.fixture()
def konten(tmp_path, monkeypatch):
    monkeypatch.setattr(pq, "DIREKTORI", tmp_path)
    pq._muat.cache_clear()
    yield tmp_path
    pq._muat.cache_clear()


def _data(topik, tid, **ubah):
    isi = {
        "versi_format": 1, "topik": topik, "status": "draf",
        "template": {tid: {"pertanyaan": ["a?", "b?", "c?"], "tindak_lanjut": "Coba gambar."}},
    }
    isi.update(ubah)
    return isi


def _tulis(folder, topik, isi):
    (folder / (topik + ".json")).write_text(json.dumps(isi), encoding="utf-8")
    pq._muat.cache_clear()


def _pemilik():
    pemilik = topics.pemilik_template(TEMPLATE)
    assert pemilik
    return pemilik


def test_berkas_terkirim_semua_sah_dan_tanpa_kata_terlarang():
    assert pq.galat_berkas() == {}


def test_cakupan_semua_template_bertopik_nyata_punya_entri():
    wajib = {t for t in topics.registri() if topics.pemilik_template(t) not in (None, "campuran")}
    ada = set(pq._muat())
    assert wajib - ada == set(), "template tanpa entri"
    assert ada - set(topics.registri()) == set(), "entri untuk template asing"


def test_entri_template_mengalahkan_topik(konten):
    p = _pemilik()
    _tulis(konten, p, _data(p, TEMPLATE))
    assert pq.pertanyaan_untuk(TEMPLATE, "campuran") == ("a?", "b?", "c?")
    assert pq.tindak_lanjut_untuk(TEMPLATE) == "Coba gambar."


def test_template_tanpa_entri_jatuh_ke_topik_lalu_umum(konten):
    p = _pemilik()
    assert pq.pertanyaan_untuk(TEMPLATE, "campuran") == pq.PERTANYAAN_TOPIK[p]
    assert pq.tindak_lanjut_untuk(TEMPLATE) is None
    assert pq.pertanyaan_untuk("tidak-ada", "pola-bilangan") == pq.PERTANYAAN_TOPIK["pola-bilangan"]
    assert pq.pertanyaan_untuk("tidak-ada", "tidak-ada") == pq.PERTANYAAN_UMUM


def _rusak():
    p = _pemilik()
    lain = next(t for t in topics.daftar_topik() if t not in (p, "campuran"))
    lain_tid = next(t for t in topics.registri() if topics.pemilik_template(t) == lain)
    bagus = _data(p, TEMPLATE)["template"][TEMPLATE]
    return [
        _data(p, TEMPLATE, status="tinjau"),
        _data(p, TEMPLATE, versi_format=2),
        _data("topik-lain", TEMPLATE),
        _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "pertanyaan": ["a?", "b?"]}}),
        _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "pertanyaan": ["a?", "b?", "tentang Kunci"]}}),
        _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "tindak_lanjut": "cek malrule"}}),
        _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "tindak_lanjut": ""}}),
        _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "pertanyaan": ["x" * 121, "b?", "c?"]}}),
        _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "tindak_lanjut": "x" * 201}}),
        _data(p, TEMPLATE, template={lain_tid: bagus}),
    ]


def test_berkas_tidak_sah_dilewati_tanpa_error(konten):
    p = _pemilik()
    for isi in _rusak():
        _tulis(konten, p, isi)
        assert pq.galat_berkas(), isi
        assert pq.tindak_lanjut_untuk(TEMPLATE) is None
        assert pq.pertanyaan_untuk(TEMPLATE, p) == pq.PERTANYAAN_TOPIK[p]


def test_berkas_bukan_json_dilewati(konten):
    (konten / "x.json").write_text("{rusak", encoding="utf-8")
    pq._muat.cache_clear()
    assert pq._muat() == {}
    assert "x.json" in pq.galat_berkas()


def test_kata_terlarang_hanya_kata_utuh(konten):
    p = _pemilik()
    bagus = _data(p, TEMPLATE)["template"][TEMPLATE]
    isi = _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "tindak_lanjut": "Cek kunci pas, bukan kodean."}})
    assert pq.validasi_berkas(isi, p)  # "kunci" kata utuh
    isi = _data(p, TEMPLATE, template={TEMPLATE: {**bagus, "tindak_lanjut": "Gunakan kodean sendiri."}})
    assert pq.validasi_berkas(isi, p) == []


def test_render_guru_memuat_tindak_lanjut_dan_catatan_template(konten):
    p = _pemilik()
    _tulis(konten, p, _data(p, TEMPLATE))
    html = pq.render(TEMPLATE, "campuran", peran="guru")
    assert "data-pancingan-guru" in html and html.count("<li>") == 3
    assert "Bila masih belum jelas: Coba gambar." in html
    assert "pertanyaan untuk soal jenis ini, belum ditinjau reviewer" in html
    assert pq.CATATAN_DRAF not in html


def test_render_fallback_memakai_catatan_topik_tanpa_tindak_lanjut(konten):
    html = pq.render("tidak-ada", "pola-bilangan", peran="guru")
    assert pq.CATATAN_DRAF in html and "Bila masih belum jelas" not in html


@pytest.mark.parametrize("peran", ["murid", "admin", ""])
def test_render_selain_guru_kosong(konten, peran):
    p = _pemilik()
    _tulis(konten, p, _data(p, TEMPLATE))
    assert pq.render(TEMPLATE, p, peran=peran) == ""


def test_render_meloloskan_html_dengan_escape(konten):
    p = _pemilik()
    bagus = _data(p, TEMPLATE)["template"][TEMPLATE]
    _tulis(konten, p, _data(p, TEMPLATE, template={TEMPLATE: {
        "pertanyaan": ["<b>a</b>?", "b?", "c?"], "tindak_lanjut": "<i>x</i>"}}))
    html = pq.render(TEMPLATE, p, peran="guru")
    assert "<b>a" not in html and "&lt;b&gt;a" in html
    assert "<i>x" not in html and "&lt;i&gt;x" in html
    assert bagus  # entri dasar tetap sah

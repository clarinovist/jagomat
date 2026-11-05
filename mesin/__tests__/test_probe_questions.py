"""Pertanyaan pancingan saat Jagomat tidak punya dugaan ("Belum yakin"), blok B 5 Nov 2026.

Hanya di permukaan guru, tidak mengubah diagnosis, dan tidak pernah sampai ke murid.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
import probe_questions as pq  # noqa: E402
import reports  # noqa: E402
import share_links  # noqa: E402
import teacher_session_pages  # noqa: E402
import topics  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


@pytest.fixture()
def konten_kosong(tmp_path, monkeypatch):
    monkeypatch.setattr(pq, "DIREKTORI", tmp_path)
    pq._muat.cache_clear()
    yield tmp_path
    pq._muat.cache_clear()


def test_tiap_topik_punya_tiga_pertanyaan_pendek_tanpa_kunci():
    for topik in topics.daftar_topik():
        daftar = pq.pertanyaan_untuk("template-tidak-dikenal", topik)
        assert len(daftar) == 3, topik
        for teks in daftar:
            assert teks.strip() and len(teks.split()) <= 25, (topik, teks)
            assert "kunci" not in teks.lower() and "jawaban yang benar" not in teks.lower()


def test_template_dikenal_memakai_topik_pemiliknya_bukan_topik_sesi(konten_kosong):
    template = "luas_kotak_satuan"
    pemilik = topics.pemilik_template(template)
    assert pemilik
    assert pq.pertanyaan_untuk(template, "campuran") == pq.PERTANYAAN_TOPIK[pemilik]


def test_topik_dan_template_asing_jatuh_ke_pertanyaan_umum():
    assert pq.pertanyaan_untuk("tidak-ada", "tidak-ada") == pq.PERTANYAAN_UMUM
    assert pq.pertanyaan_untuk("", "") == pq.PERTANYAAN_UMUM


def test_render_hanya_untuk_guru():
    assert pq.render("tidak-ada", "pola-bilangan", peran="murid") == ""
    assert pq.render("tidak-ada", "pola-bilangan", peran="") == ""
    html = pq.render("tidak-ada", "pola-bilangan", peran="guru")
    assert "data-pancingan-guru" in html and html.count("<li>") == 3
    assert "Draf" in html


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "pancingan.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _sesi_dengan_jawaban(kon, jawaban, cara, *, nama="Anak Pancingan", pemilik="guru"):
    anak = database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)
    sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=1)
    b = database.isi_sesi(kon, sesi)[0]
    database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban, cara)
    reports.diagnosa_murid(kon, sesi)
    database.tandai_selesai(kon, sesi)
    return anak, sesi


def test_jawaban_salah_di_luar_pola_menampilkan_pancingan(db):
    with database.buka(db) as kon:
        _anak, sesi = _sesi_dengan_jawaban(kon, "123456789", "cara yang tidak terduga")
        b = database.isi_sesi(kon, sesi)[0]
        assert not b["benar"] and b["kode_usulan"] is None  # Belum yakin
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
    assert "data-pancingan-guru" in html
    assert "Tanyakan ini ke anak" in html


def test_jawaban_benar_atau_berkode_tidak_menampilkan_pancingan(db):
    with database.buka(db) as kon:
        _anak, sesi = _sesi_dengan_jawaban(kon, "", "")  # kosong: tidak ada yang dipancing
        html_kosong = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        anak2, sesi2 = _sesi_dengan_jawaban(kon, "x", "Cara sintetis", nama="Anak Dua")
        b = database.isi_sesi(kon, sesi2)[0]
        jid = database.simpan_jawaban(kon, b["sesi_soal_id"], b["kunci"], "Cara benar")
        database.simpan_diagnosis(kon, jid, True, None, None)
        html_benar = teacher_session_pages.halaman_sesi_stitch(kon, sesi2).decode()
        anak3, sesi3 = _sesi_dengan_jawaban(kon, "x", "Cara sintetis", nama="Anak Tiga")
        b3 = database.isi_sesi(kon, sesi3)[0]
        jid3 = database.simpan_jawaban(kon, b3["sesi_soal_id"], "7", "Cara sintetis")
        database.simpan_diagnosis(kon, jid3, False, "K", "K", "sintetis.malrule")
        html_kode = teacher_session_pages.halaman_sesi_stitch(kon, sesi3).decode()
    assert "data-pancingan-guru" not in html_kosong
    assert "data-pancingan-guru" not in html_benar
    assert "data-pancingan-guru" not in html_kode


def test_http_murid_dan_tautan_tidak_pernah_memuat_pancingan(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    try:
        with server.buka() as kon:
            anak, sesi = _sesi_dengan_jawaban(kon, "123456789", "cara aneh", nama="feby")
            aktif = database.buat_sesi(kon, anak, 78, jumlah_soal=1)
            token = share_links.buat(kon, aktif)
        kode, isi, _ = server.minta("/sesi/" + str(sesi), auth=("guru", SANDI_GURU))
        assert kode == 200 and "data-pancingan-guru" in isi
        for jalur in ("/murid/", "/murid/kerjakan/" + str(aktif), "/murid/hasil/" + str(sesi)):
            kode, isi, _ = server.minta(jalur, auth=("feby", SANDI_MURID))
            assert kode == 200, (jalur, kode)
            assert "data-pancingan-guru" not in isi and "Tanyakan ini ke anak" not in isi
        kode, isi, _ = server.minta("/mulai/" + token)
        assert kode == 200 and "data-pancingan-guru" not in isi
    finally:
        server.berhenti()

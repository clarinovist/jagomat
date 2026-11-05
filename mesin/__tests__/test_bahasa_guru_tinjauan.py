"""Palang bahasa halaman tinjauan guru (docs/glosarium-guru.md, 5 Nov 2026).

Istilah internal tidak boleh muncul di teks yang dibaca guru. Diperiksa pada
teks terlihat (tag dibuang), bukan atribut/nama field.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
import reports  # noqa: E402
import teacher_session_pages  # noqa: E402

ISTILAH_INTERNAL = (
    "provenance", "malrule", "reducer", "outcome", "snapshot", "probe ",
    "prompt", "server", "fixture", "payload", "restatement", "transkripsi",
    "mandiri", "butir", "usulan mesin",
)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "bahasa.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _teks_terlihat(html: str) -> str:
    tanpa_skrip = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", tanpa_skrip)


def test_halaman_tinjauan_bebas_istilah_internal(db):
    with database.buka(db) as kon:
        anak = database.tambah_siswa(kon, "Anak Bahasa", "P3", pemilik="guru")
        sesi = database.buat_sesi(kon, anak, 71, jumlah_soal=3)
        for i, b in enumerate(database.isi_sesi(kon, sesi)):
            if i == 0:
                database.simpan_jawaban(kon, b["sesi_soal_id"], "123456789", "cara tidak terduga")
            elif i == 1:
                database.simpan_jawaban(kon, b["sesi_soal_id"], b["kunci"], "cara anak")
            else:
                database.simpan_jawaban(kon, b["sesi_soal_id"], "", "")
        reports.diagnosa_murid(kon, sesi)
        database.tandai_selesai(kon, sesi)
        html = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
    teks = _teks_terlihat(html).lower()
    ditemukan = [kata for kata in ISTILAH_INTERNAL if kata in teks]
    assert not ditemukan, ditemukan

"""Bingkai baru tidak menulis ulang bank/riwayat atau memakai cache sumber lain."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import sqlite3

import pytest

import database
import llm
import question_views as views
import story_frames as frames
import teacher_print_pages
from templates import REGISTRI


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "bingkai-sintetis.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon


def _soal():
    return replace(REGISTRI["kpk_dua_bilangan"](a=6, b=8), level="P5")


def _sesi(kon, anak, seed, soal):
    return database.buat_sesi_dari_urutan(
        kon, anak, seed, (soal.template_id,), topik="teori-bilangan", level="P5",
        soal_terpilih=(soal,),
    )


def _bank(kon):
    return {t: [tuple(r) for r in kon.execute("SELECT * FROM " + t + " ORDER BY id")]
            for t in ("soal", "malrule")}


def test_sesi_lama_baru_dan_cetak_ulang_tetap_exact(db, monkeypatch):
    anak = database.tambah_siswa(db, "Fixture Bingkai", "P5", pemilik="guru")
    soal = _soal()
    monkeypatch.setenv("OSN_BANK_KALIMAT", "0")
    lama = _sesi(db, anak, 1, soal)
    baris_lama = dict(database.isi_sesi(db, lama)[0])
    bank_awal = _bank(db)
    cetak_lama = teacher_print_pages.halaman_lembar(db, lama, True)
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    baru = _sesi(db, anak, 2, soal)
    baris_baru = dict(database.isi_sesi(db, baru)[0])
    assert baris_baru["soal_id"] == baris_lama["soal_id"]
    assert baris_baru["teks_soal"] != baris_lama["teks_soal"]
    assert baris_baru["fingerprint_matematis"] == baris_lama["fingerprint_matematis"]
    assert _bank(db) == bank_awal
    cetak_baru = teacher_print_pages.halaman_lembar(db, baru, True)
    # Bahkan bank rusak/nonaktif tidak dipakai reader snapshot dan warisan.
    monkeypatch.setenv("OSN_BANK_KALIMAT", "0")
    monkeypatch.setattr(frames, "BANK", {})
    assert teacher_print_pages.halaman_lembar(db, lama, True) == cetak_lama
    assert teacher_print_pages.halaman_lembar(db, baru, True) == cetak_baru
    assert dict(database.isi_sesi(db, lama)[0]) == baris_lama
    assert dict(database.isi_sesi(db, baru)[0]) == baris_baru
    assert _bank(db) == bank_awal
    warisan = {"template_id": soal.template_id, "parameter": json.dumps(soal.parameter),
               "level": soal.level, "cerita": "", "kunci": soal.kunci}
    assert views.soal_dari_baris(warisan).teks == soal.teks


def test_bank_rusak_menggulung_seluruh_sesi(db, monkeypatch):
    anak = database.tambah_siswa(db, "Fixture Atomik", "P5", pemilik="guru")
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    rusak = dict(frames.BANK)
    pertama, *lain = rusak["kpk_dua_bilangan"]
    rusak["kpk_dua_bilangan"] = (replace(pertama, pola="Bocor {kunci}"), *lain)
    monkeypatch.setattr(frames, "BANK", rusak)
    sebelum = tuple(db.iterdump())
    with pytest.raises(ValueError, match="placeholder"):
        # Butir pertama sudah disimpan sebelum butir kedua ditolak.
        murni = replace(REGISTRI["keterbagian"](d=3, a=24, b=25, c=10, jawab=0), level="P5")
        database.buat_sesi_dari_urutan(db, anak, 3, (murni.template_id, _soal().template_id),
                                     topik="teori-bilangan", level="P5", soal_terpilih=(murni, _soal()))
    assert tuple(db.iterdump()) == sebelum


def test_b2_snapshot_sumber_beda_tidak_berbagi_cache(db, monkeypatch):
    llm.ensure_table(db)
    monkeypatch.setattr(llm, "aktif", lambda: True)
    monkeypatch.setenv("OSN_BANK_KALIMAT", "0")
    soal = _soal()
    lama = views.penyajian_dari_soal(soal)
    sumber_lama = replace(soal, penyajian=lama)
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    baru = views.penyajian_dari_soal(soal)
    sumber_baru = replace(soal, teks=baru.teks_soal, penyajian=baru)
    panggilan = []

    def panggil(prompt):
        panggilan.append(prompt)
        return sumber_lama.teks if len(panggilan) == 1 else sumber_baru.teks

    monkeypatch.setattr(llm, "_panggil", panggil)
    assert llm.bungkus(db, sumber_lama) == sumber_lama.teks
    assert llm.bungkus(db, sumber_baru) == sumber_baru.teks
    assert len(panggilan) == 2
    assert llm.bungkus(db, sumber_baru) == sumber_baru.teks
    assert len(panggilan) == 2
    assert db.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0] == 2


def test_pg_optin_mempertahankan_pilihan_dan_kunci(db, monkeypatch):
    from choice_store import daftar_pilihan
    anak = database.tambah_siswa(db, "Fixture PG Bingkai", "P5", pemilik="guru")
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    sesi = database.buat_sesi(db, anak, 42, topik="kombinatorik", level="P5", format_jawaban="pilihan_ganda")
    pilihan = daftar_pilihan(db, sesi)
    terbungkus = 0
    for b in database.isi_sesi(db, sesi):
        p = json.loads(b["parameter"])
        s = replace(REGISTRI[b["template_id"]](**p), level=b["level"])
        expected = frames.untuk_snapshot_baru(s)
        if expected is not None:
            assert b["teks_soal"] == expected.teks
            terbungkus += 1
        assert sum(o.nilai == b["kunci"] for o in pilihan[b["sesi_soal_id"]].opsi) == 1
    assert terbungkus >= 2
    awal = teacher_print_pages.halaman_lembar(db, sesi, True)
    monkeypatch.setenv("OSN_BANK_KALIMAT", "0")
    assert teacher_print_pages.halaman_lembar(db, sesi, True) == awal


def test_kunci_cache_tanpa_snapshot_tetap_kompatibel():
    p = {"a": 6, "b": 8}
    payload = {"template_id": "kpk_dua_bilangan", "parameter": p, "latar": "pasar",
               "versi_prompt": llm.VERSI_PROMPT, "model": "model-sintetis"}
    expected = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert llm.kunci_cache(p, "model-sintetis", "kpk_dua_bilangan", "pasar") == expected

"""Sakelar OSN_BILANGAN_SEKOLAH: mati = perilaku aplikasi IDENTIK dengan sebelum topik ada.

Pembaca histori (registri, label, kartu, inventaris) mengenal ID baru; yang
ditolak saat mati adalah PEMBUATAN soal dan penawaran topik. Sakelar dibaca
tiap panggilan (env-only, pola OSN_DASAR_LENGKAP), jadi kasus proses-baru
dijalankan lewat subprocess.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import assistant_catalog
import basic_numbers_versions as basic
import generator
import question_context
import school_numbers_versions as versi
import topics
from baseline_bilangan_sekolah import (DAFTAR_LATIHAN_BASELINE, SIDIK_BASELINE,
                                       sidik, sidik_terukur, ukur)
from choice_generation import buat_lembar_pilihan

TOPIK = "bilangan-sekolah"
TID = "nilai_tempat_besar"
SEMUA = (TID, "urutkan_bilangan", "tambah_kurang_bersusun", "kali_bagi_sekolah",
         "kalimat_matematika")  # Tahap A + B
NAMA = "OSN_BILANGAN_SEKOLAH"
# Topik Matematika Awal (bawaan menyala) ikut terdaftar; baseline "sebelum topik" di berkas ini
# hanya berlaku dengan sakelarnya dimatikan, dan isinya dikeluarkan dari hitungan pembaca.
NAMA_AWAL = "OSN_MATEMATIKA_AWAL"
TOPIK_AWAL = "matematika-awal"
SEMUA_AWAL = ("kenali_bentuk",)
AKAR_MESIN = Path(__file__).resolve().parents[1]
FOLDER_TEST = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def sakelar_mati(monkeypatch):
    monkeypatch.delenv(NAMA, raising=False)
    monkeypatch.setenv(NAMA_AWAL, "0")
    monkeypatch.delenv("OSN_MATERI_DASAR", raising=False)
    monkeypatch.delenv("OSN_DASAR_LENGKAP", raising=False)


# ── nilai sakelar ────────────────────────────────────────────────────────

@pytest.mark.parametrize("nilai,aktif", [(None, False), ("0", False), ("1", True), (" 1 ", True)])
def test_nilai_sakelar(nilai, aktif, monkeypatch):
    if nilai is not None:
        monkeypatch.setenv(NAMA, nilai)
    assert versi.bilangan_sekolah_aktif() is aktif


@pytest.mark.parametrize("nilai", ["", "true", "2", "-1", "on", "00", "yes"])
def test_nilai_tidak_sah_ditolak_keras(nilai, monkeypatch):
    monkeypatch.setenv(NAMA, nilai)
    with pytest.raises(ValueError, match=NAMA):
        versi.bilangan_sekolah_aktif()
    with pytest.raises(ValueError, match=NAMA):
        question_context.daftar_topik_latihan()
    with pytest.raises(ValueError, match=NAMA):
        generator.buat_lembar(0, level="P3", topik=TOPIK)


def test_sakelar_bukan_bagian_registri_admin():
    import sakelar_registry
    teks = Path(sakelar_registry.__file__).read_text(encoding="utf-8")
    assert NAMA not in teks


# ── sakelar mati: pembaca mengenal, pembuat menolak ──────────────────────

def test_mati_pembaca_tetap_mengenal_topik_dan_id():
    from rumus import kartu_untuk
    from template_labels import nama_tipe_soal
    from templates import REGISTRI
    from visual_inventory import inventaris_template
    assert TOPIK in topics.daftar_topik()
    inventaris = {r["template_id"] for r in inventaris_template()}
    for tid in SEMUA:
        assert tid in REGISTRI and tid in topics.registri()
        assert topics.pemilik_template(tid) == TOPIK
        assert tid in inventaris
        assert kartu_untuk(tid) is not None
        assert nama_tipe_soal(tid) != tid


def _harus_ditolak(fungsi, *args, **kwargs):
    try:
        fungsi(*args, **kwargs)
    except ValueError as galat:
        assert "belum dibuka" in str(galat), galat
        return
    raise AssertionError("pembuatan seharusnya ditolak: " + fungsi.__name__)


def periksa_pembuatan_ditolak():
    """Invarian sakelar mati; dipakai langsung dan di mutation."""
    gabungan = topics.gabungan([TOPIK, "pola-bilangan"])
    for level in ("P3", "P4", "P5"):
        _harus_ditolak(generator.buat_lembar, 0, level=level, topik=TOPIK)
        for tid in SEMUA:
            _harus_ditolak(generator.buat_lembar, 0, urutan=(tid,) * 3, level=level, topik=TOPIK)
        _harus_ditolak(buat_lembar_pilihan, 0, level=level, topik=TOPIK)
    for tid in SEMUA:
        _harus_ditolak(generator.buat_lembar, 0, urutan=(tid,), level="P3", topik=gabungan)


def periksa_topik_tidak_ditawarkan():
    assert TOPIK not in question_context.daftar_topik_latihan(), "topik bocor ke Latihan manual"
    try:
        question_context.pastikan_materi_dibuka([TOPIK])
    except ValueError:
        return
    raise AssertionError("topik bocor: palang materi tidak menolak")


def test_mati_lembar_ditolak_semua_jalur():
    periksa_pembuatan_ditolak()


def test_mati_buat_soal_satu_soal_tidak_digate_seperti_bilangan_dasar():
    """Audit dan sapu kontrak memakai buat_soal; pembuat sesi lewat buat_lembar (digate)."""
    assert generator.buat_soal(TID, 1, "P3", TOPIK).template_id == TID


def test_mati_palang_materi_dan_template():
    with pytest.raises(ValueError, match="belum dibuka"):
        question_context.pastikan_materi_dibuka([TOPIK])
    with pytest.raises(ValueError, match="belum dibuka"):
        question_context.pastikan_materi_dibuka(["pola-bilangan", TOPIK])
    question_context.pastikan_materi_dibuka(["pola-bilangan"])
    for tid in SEMUA:
        assert versi.template_dibuka(tid) is False
        assert basic.template_dibuka(tid) is False
        with pytest.raises(ValueError, match="belum dibuka"):
            basic.pastikan_template_dibuka([tid])
        with pytest.raises(ValueError, match="belum dibuka"):
            versi.pastikan_template_dibuka(["pola-bilangan", tid])
    assert versi.TEMPLATE_BARU == frozenset(SEMUA)
    assert versi.template_dibuka("tambah_dasar") is True
    assert versi.topik_dibuka("pola-bilangan") is True
    assert versi.topik_dibuka(TOPIK) is False


def test_mati_gabungan_lewat_palang_materi_ditolak_dan_gabungan_lain_tetap():
    paket = topics.gabungan(["pola-bilangan", "statistika"])
    assert paket.komposisi_untuk("P4")
    question_context.pastikan_materi_dibuka(["pola-bilangan", "statistika"])


def test_mati_identitas_registri_campuran_dan_siklus_sama_dengan_sebelumnya():
    assert sidik_terukur() == SIDIK_BASELINE


def test_mati_registri_hanya_bertambah_lima_template_pembaca():
    import json as _json
    from baseline_bilangan_sekolah import sidik as _sidik
    # Registri lama (sebelum topik) = registri sekarang tanpa lima template Bilangan Sekolah.
    sekarang = sorted(topics.registri())
    lama = [t for t in sekarang if t not in SEMUA + SEMUA_AWAL]
    assert len(sekarang) == len(lama) + len(SEMUA) + len(SEMUA_AWAL)
    assert _sidik(lama) == "84403c14c5da72645600"
    assert [t for t in topics.daftar_topik() if t not in (TOPIK, TOPIK_AWAL)] == [
        "aritmatika-lanjut", "aritmetika-dasar", "berhitung-sekolah", "bilangan-dasar",
        "campuran", "geometri-datar", "geometri-ruang", "kombinatorik", "logika",
        "pengukuran", "pola-bilangan", "statistika", "teori-bilangan"]
    assert _json.loads(_json.dumps(lama)) == lama


def test_mati_penawaran_dan_pendamping_tidak_memuat_topik():
    periksa_topik_tidak_ditawarkan()
    ids = {t.id for t in assistant_catalog.buat_katalog(untuk_penawaran=True).template}
    assert not ids & set(SEMUA)
    topik = {t.id for t in assistant_catalog.buat_katalog(untuk_penawaran=True).topik}
    assert TOPIK not in topik


def test_mati_pembuat_lembar_lain_tidak_berubah_dan_bilangan_dasar_aman(monkeypatch):
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    lembar = generator.buat_lembar(3, level="P1", topik="bilangan-dasar")
    assert {s.template_id for s in lembar.soal} == {"tambah_dasar"}
    assert basic.template_dibuka("kurang_dasar") is False
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    assert basic.template_dibuka("kurang_dasar") is True
    assert basic.template_dibuka(TID) is False


# ── sakelar hidup ────────────────────────────────────────────────────────

@pytest.fixture
def hidup(monkeypatch):
    monkeypatch.setenv(NAMA, "1")


def test_hidup_topik_ditawarkan_hanya_di_latihan_manual(hidup):
    assert versi.template_dibuka(TID) and versi.topik_dibuka(TOPIK)
    daftar = question_context.daftar_topik_latihan()
    assert TOPIK in daftar
    assert [t for t in daftar if t != TOPIK] == DAFTAR_LATIHAN_BASELINE
    question_context.pastikan_materi_dibuka([TOPIK])
    question_context.validasi_pilihan([TOPIK], "P4")


def test_hidup_lembar_dan_pilihan_ganda_dibuat(hidup):
    for level in ("P3", "P4", "P5"):
        lembar = generator.buat_lembar(11, level=level, topik=TOPIK)
        assert {s.template_id for s in lembar.soal} == set(SEMUA)
        pg = buat_lembar_pilihan(11, level=level, topik=TOPIK)
        assert len(pg.soal) == len(lembar.soal)
    assert generator.buat_soal(TID, 5, "P3", TOPIK).template_id == TID


def test_hidup_guru_boleh_menggabungkan_manual(hidup):
    paket = topics.gabungan([TOPIK, "pola-bilangan"])
    lembar = generator.buat_lembar(4, level="P3", topik=paket)
    assert TID in {s.template_id for s in lembar.soal}
    assert paket.hanya_manual is False  # paket ad-hoc milik guru, bukan topik terdaftar


def test_hidup_identitas_registri_campuran_dan_siklus_tetap(hidup):
    ukuran = sidik_terukur()
    for kunci, nilai in SIDIK_BASELINE.items():
        if kunci == "daftar_topik_latihan":
            continue  # tambahan sah: satu topik di Latihan manual (diuji terpisah)
        assert ukuran[kunci] == nilai, kunci


def test_hidup_penawaran_pendamping_tetap_tidak_memuat_topik(hidup):
    ids = {t.id for t in assistant_catalog.buat_katalog(untuk_penawaran=True).template}
    assert not ids & set(SEMUA)
    audit = {t.id for t in assistant_catalog.buat_katalog(untuk_penawaran=False).template}
    assert set(SEMUA) <= audit, "audit registri utuh tetap mengenal ID"


# ── proses terpisah (tidak ada ketergantungan saat impor) ────────────────

_KODE = r"""
import json, os, sys
sys.path.insert(0, %(akar)r); sys.path.insert(0, %(uji)r)
for k, v in {"OSN_PBKDF2_ITERASI": "1000", "OSN_MATEMATIKA_VERSI": "2",
             "OSN_TEORI_BILANGAN_VERSI": "2", "OSN_KATALOG_VERSI": "1"}.items():
    os.environ.setdefault(k, v)
import baseline_bilangan_sekolah as b
import generator, question_context
hasil = {"sidik": b.sidik_terukur()}
try:
    generator.buat_lembar(0, level="P3", topik="bilangan-sekolah")
    hasil["lembar"] = "dibuat"
except ValueError as galat:
    hasil["lembar"] = str(galat)
hasil["latihan"] = "bilangan-sekolah" in question_context.daftar_topik_latihan()
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(nilai):
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSN_BILANGAN")}
    env[NAMA_AWAL] = "0"
    if nilai is not None:
        env[NAMA] = nilai
    kode = _KODE % {"akar": str(AKAR_MESIN), "uji": str(FOLDER_TEST)}
    hasil = subprocess.run([sys.executable, "-c", kode], env=env, capture_output=True,
                           text=True, timeout=180)
    return hasil


@pytest.mark.parametrize("nilai", [None, "0"])
def test_proses_baru_mati(nilai):
    hasil = _proses(nilai)
    assert hasil.returncode == 0, hasil.stderr
    data = json.loads(hasil.stdout)
    assert data["sidik"] == SIDIK_BASELINE
    assert data["lembar"] == "Materi ini belum dibuka."
    assert data["latihan"] is False


def test_proses_baru_hidup():
    hasil = _proses("1")
    assert hasil.returncode == 0, hasil.stderr
    data = json.loads(hasil.stdout)
    assert data["lembar"] == "dibuat" and data["latihan"] is True
    for kunci, nilai in SIDIK_BASELINE.items():
        if kunci != "daftar_topik_latihan":
            assert data["sidik"][kunci] == nilai, kunci


def test_proses_baru_nilai_tidak_sah_gagal_keras():
    hasil = _proses("2")
    assert hasil.returncode != 0
    assert NAMA in hasil.stderr


# ── mutation: palang generator dan palang materi ─────────────────────────
# Mutasi lewat jalur yang dipanggil tes (monkeypatch memulihkan). Tes merah
# karena ASERSI penolakan gagal, bukan karena impor atau fixture rusak.

def test_mutation_palang_generator_dimatikan(monkeypatch):
    periksa_pembuatan_ditolak()  # kondisi sehat: hijau
    monkeypatch.setattr(generator, "pastikan_template_dibuka", lambda urutan: None)
    monkeypatch.setenv(NAMA, "0")
    with pytest.raises(AssertionError, match="seharusnya ditolak"):
        periksa_pembuatan_ditolak()


def test_mutation_palang_materi_dimatikan(monkeypatch):
    periksa_topik_tidak_ditawarkan()  # kondisi sehat: hijau
    monkeypatch.setattr(versi, "topik_dibuka", lambda topik_id: True)
    with pytest.raises(AssertionError, match="bocor"):
        periksa_topik_tidak_ditawarkan()


def test_mutation_template_selalu_terbuka(monkeypatch):
    monkeypatch.setattr(versi, "template_dibuka", lambda template_id: True)
    with pytest.raises(AssertionError, match="seharusnya ditolak"):
        periksa_pembuatan_ditolak()

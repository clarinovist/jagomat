"""Sakelar OSN_MATEMATIKA_AWAL: bawaan 1; mati = perilaku aplikasi IDENTIK dengan sebelum topik ada.

Beda dari OSN_BILANGAN_SEKOLAH (bawaan 0): sakelar ini menyala sendiri kecuali
dimatikan, jadi identitas "perilaku lama" hanya berlaku dengan OSN_MATEMATIKA_AWAL=0
yang dipasang tes. Pembaca histori (registri, label, kartu, inventaris) selalu
mengenal topik; yang ditolak saat mati adalah PEMBUATAN soal dan penawaran topik.
Sakelar dibaca tiap panggilan (env-only), jadi kasus proses-baru lewat subprocess.

Topik ini memuat P3 ke atas, jadi `question_context.topik_dasar` TIDAK lagi menyembunyikannya
(bedanya dengan saat ia hanya P1/P2): sakelar ini satu-satunya palang pembuatan. Tes di sini
memasang OSN_MATERI_DASAR=1 untuk baseline lama dan menguji kedua nilai gerbang itu eksplisit,
supaya "sakelar mati menolak" tidak lulus hampa karena gerbang lain.
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
import matematika_awal_versions as versi
import question_context
import topics
from baseline_matematika_awal import (DAFTAR_LATIHAN_BASELINE, JENIS_PER_LEVEL,
                                      JUMLAH_REGISTRI_LAMA, LEVEL_AWAL, LEVEL_JENIS,
                                      SIDIK_BASELINE, SIDIK_KONTEKS_LAMA,
                                      SIDIK_REGISTRI_LAMA, TEMPLATE_AWAL, TOPIK_LAMA,
                                      konteks_lama, sidik, sidik_terukur)
from choice_generation import buat_lembar_pilihan

TOPIK = "matematika-awal"
SEMUA = TEMPLATE_AWAL  # sembilan belas jenis, daftar eksplisit di baseline_matematika_awal
NAMA = "OSN_MATEMATIKA_AWAL"
AKAR_MESIN = Path(__file__).resolve().parents[1]
FOLDER_TEST = Path(__file__).resolve().parent
LEVEL = LEVEL_AWAL


@pytest.fixture(autouse=True)
def lingkungan(monkeypatch):
    """Kasus terkuat: gerbang dasar terbuka, Bilangan Sekolah mati; sakelar diuji per tes."""
    monkeypatch.delenv(NAMA, raising=False)
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    monkeypatch.delenv("OSN_DASAR_LENGKAP", raising=False)
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "0")


@pytest.fixture
def mati(monkeypatch):
    monkeypatch.setenv(NAMA, "0")


# ── nilai sakelar ────────────────────────────────────────────────────────

@pytest.mark.parametrize("nilai,aktif", [
    (None, True), ("1", True), (" 1 ", True), ("0", False), (" 0 ", False)])
def test_nilai_sakelar_bawaan_satu(nilai, aktif, monkeypatch):
    if nilai is not None:
        monkeypatch.setenv(NAMA, nilai)
    assert versi.matematika_awal_aktif() is aktif


@pytest.mark.parametrize("nilai", ["", "true", "2", "-1", "on", "00", "yes", "off", " "])
def test_nilai_tidak_sah_ditolak_keras(nilai, monkeypatch):
    monkeypatch.setenv(NAMA, nilai)
    with pytest.raises(ValueError, match=NAMA):
        versi.matematika_awal_aktif()
    with pytest.raises(ValueError, match=NAMA):
        question_context.daftar_topik_latihan()
    with pytest.raises(ValueError, match=NAMA):
        generator.buat_lembar(0, level="P1", topik=TOPIK)
    with pytest.raises(ValueError, match=NAMA):
        basic.template_dibuka("kenali_bentuk")


def test_sakelar_bukan_bagian_registri_admin_dan_dibaca_tiap_panggilan(monkeypatch):
    import sakelar_registry
    assert NAMA not in Path(sakelar_registry.__file__).read_text(encoding="utf-8")
    assert versi.matematika_awal_aktif() is True
    monkeypatch.setenv(NAMA, "0")
    assert versi.matematika_awal_aktif() is False
    monkeypatch.setenv(NAMA, "1")
    assert versi.matematika_awal_aktif() is True


def test_template_baru_sama_persis_dengan_template_topik():
    """Jenis yang lupa didaftarkan di sakelar akan lolos palang: dikunci dua arah di sini."""
    assert versi.TEMPLATE_BARU == frozenset(topics.ambil(TOPIK).templates) == frozenset(SEMUA)
    assert len(SEMUA) == 24 and len(versi.TEMPLATE_BARU) == 24
    for tid in topics.ambil(TOPIK).templates:
        assert topics.pemilik_template(tid) == TOPIK


# ── sakelar mati: pembaca mengenal, pembuat menolak ──────────────────────

def test_mati_pembaca_tetap_mengenal_topik_dan_id(mati):
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
    assert {(k.template_id, k.profil_parameter) for k in question_context.daftar_konteks()
            } >= {(tid, lv) for tid in SEMUA for lv in LEVEL_JENIS[tid]}


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
    for level in LEVEL:
        _harus_ditolak(generator.buat_lembar, 0, level=level, topik=TOPIK)
        for tid in sorted(JENIS_PER_LEVEL[level]):
            _harus_ditolak(generator.buat_lembar, 0, urutan=(tid,) * 3, level=level, topik=TOPIK)
        _harus_ditolak(buat_lembar_pilihan, 0, level=level, topik=TOPIK)
    for tid in SEMUA:
        level = LEVEL_JENIS[tid][0]
        _harus_ditolak(generator.buat_lembar, 0, urutan=(tid,), level=level, topik=gabungan)
        _harus_ditolak(generator.buat_lembar, 0, urutan=(tid,), level="P3", topik="pola-bilangan")


def periksa_topik_tidak_ditawarkan():
    assert TOPIK not in question_context.daftar_topik_latihan(), "topik bocor ke Latihan manual"
    try:
        question_context.pastikan_materi_dibuka([TOPIK])
    except ValueError:
        return
    raise AssertionError("topik bocor: palang materi tidak menolak")


def test_mati_lembar_ditolak_semua_jalur(mati):
    periksa_pembuatan_ditolak()


def test_mati_buat_soal_satu_soal_tidak_digate_seperti_preseden(mati):
    """Audit dan sapu kontrak memakai buat_soal; pembuat sesi lewat buat_lembar (digate)."""
    for tid in SEMUA:
        level = LEVEL_JENIS[tid][0]
        assert generator.buat_soal(tid, 1, level, TOPIK).template_id == tid


def test_mati_palang_materi_dan_template(mati):
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
    assert versi.template_dibuka("tambah_dasar") is True
    assert versi.template_dibuka("nilai_tempat_besar") is True
    assert versi.topik_dibuka("pola-bilangan") is True
    assert versi.topik_dibuka(TOPIK) is False


@pytest.mark.parametrize("materi_dasar", ["0", "1"])
def test_mati_identitas_campuran_siklus_dan_penawaran_sama_dengan_sebelumnya(
        mati, monkeypatch, materi_dasar):
    monkeypatch.setenv("OSN_MATERI_DASAR", materi_dasar)
    assert sidik_terukur() == SIDIK_BASELINE[materi_dasar]
    assert question_context.daftar_topik_latihan() == DAFTAR_LATIHAN_BASELINE[materi_dasar]


def test_mati_registri_dan_pembaca_hanya_bertambah_isi_topik_baru(mati):
    sekarang = sorted(topics.registri())
    lama = [t for t in sekarang if t not in SEMUA]
    assert len(sekarang) == JUMLAH_REGISTRI_LAMA + len(SEMUA)
    assert sidik(lama) == SIDIK_REGISTRI_LAMA
    assert [t for t in topics.daftar_topik() if t != TOPIK] == TOPIK_LAMA
    assert sidik(konteks_lama()) == SIDIK_KONTEKS_LAMA
    assert json.loads(json.dumps(lama)) == lama


def test_mati_penawaran_dan_pendamping_tidak_memuat_topik(mati):
    periksa_topik_tidak_ditawarkan()
    katalog = assistant_catalog.buat_katalog(untuk_penawaran=True)
    assert not {t.id for t in katalog.template} & set(SEMUA)
    assert TOPIK not in {t.id for t in katalog.topik}


def test_mati_pembuat_lembar_lain_tidak_berubah(mati, monkeypatch):
    lembar = generator.buat_lembar(3, level="P1", topik="bilangan-dasar")
    assert {s.template_id for s in lembar.soal} == {"tambah_dasar"}
    assert basic.template_dibuka("kurang_dasar") is False
    monkeypatch.setenv("OSN_DASAR_LENGKAP", "1")
    assert basic.template_dibuka("kurang_dasar") is True
    assert basic.template_dibuka("kenali_bentuk") is False


# ── sakelar hidup (bawaan) ───────────────────────────────────────────────

def test_bawaan_hidup_topik_ditawarkan_hanya_di_latihan_manual():
    assert versi.template_dibuka("kenali_bentuk") and versi.topik_dibuka(TOPIK)
    daftar = question_context.daftar_topik_latihan()
    assert TOPIK in daftar
    assert [t for t in daftar if t != TOPIK] == DAFTAR_LATIHAN_BASELINE["1"]
    question_context.pastikan_materi_dibuka([TOPIK])
    for level in LEVEL:
        question_context.validasi_pilihan([TOPIK], level)


def test_bawaan_hidup_lembar_dan_pilihan_ganda_dibuat():
    for level in LEVEL:
        lembar = generator.buat_lembar(11, level=level, topik=TOPIK)
        assert {s.template_id for s in lembar.soal} == JENIS_PER_LEVEL[level]
        pg = buat_lembar_pilihan(11, level=level, topik=TOPIK)
        assert len(pg.soal) == len(lembar.soal)
    for tid in SEMUA:
        level = LEVEL_JENIS[tid][-1]
        assert generator.buat_soal(tid, 5, level, TOPIK).template_id == tid


def test_bawaan_hidup_guru_boleh_menggabungkan_manual():
    paket = topics.gabungan([TOPIK, "bilangan-dasar"])
    lembar = generator.buat_lembar(4, level="P1", topik=paket)
    assert "kenali_bentuk" in {s.template_id for s in lembar.soal}
    assert paket.hanya_manual is False  # paket ad-hoc milik guru, bukan topik terdaftar


def test_bawaan_hidup_identitas_campuran_dan_siklus_tetap():
    ukuran = sidik_terukur()
    for kunci, nilai in SIDIK_BASELINE["1"].items():
        if kunci in ("daftar_topik_latihan", "katalog_penawaran"):
            continue  # penawaran Pendamping diuji terpisah; Latihan manual bertambah satu topik
        assert ukuran[kunci] == nilai, kunci
    # katalog penawaran Pendamping tidak boleh berubah walau sakelar hidup (palang manual-saja)
    assert ukuran["katalog_penawaran"] == SIDIK_BASELINE["1"]["katalog_penawaran"]


def test_bawaan_hidup_gerbang_dasar_tidak_lagi_menutup_topik(monkeypatch):
    """Topik memuat P3+, jadi bukan "topik dasar": OSN_MATERI_DASAR=0 tidak menyembunyikannya."""
    monkeypatch.setenv("OSN_MATERI_DASAR", "0")
    assert question_context.topik_dasar(TOPIK) is False
    assert TOPIK in question_context.daftar_topik_latihan()
    question_context.pastikan_materi_dibuka([TOPIK])
    assert len(generator.buat_lembar(2, level="P3", topik=TOPIK).soal) == 10


@pytest.mark.parametrize("materi_dasar", ["0", "1"])
def test_mati_menolak_dengan_gerbang_dasar_terbuka_maupun_tertutup(mati, monkeypatch, materi_dasar):
    """Sakelar mati menolak lewat palangnya sendiri, bukan karena gerbang lain (tidak hampa)."""
    monkeypatch.setenv("OSN_MATERI_DASAR", materi_dasar)
    periksa_pembuatan_ditolak()
    periksa_topik_tidak_ditawarkan()


# ── proses terpisah (tidak ada ketergantungan saat impor) ────────────────

_KODE = r"""
import json, os, sys
sys.path.insert(0, %(akar)r); sys.path.insert(0, %(uji)r)
for k, v in {"OSN_PBKDF2_ITERASI": "1000", "OSN_MATEMATIKA_VERSI": "2",
             "OSN_TEORI_BILANGAN_VERSI": "2", "OSN_KATALOG_VERSI": "1"}.items():
    os.environ.setdefault(k, v)
import baseline_matematika_awal as b
import generator, question_context
hasil = {"sidik": b.sidik_terukur()}
try:
    generator.buat_lembar(0, level="P1", topik="matematika-awal")
    hasil["lembar"] = "dibuat"
except ValueError as galat:
    hasil["lembar"] = str(galat)
hasil["latihan"] = "matematika-awal" in question_context.daftar_topik_latihan()
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(nilai):
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSN_MATEMATIKA_AWAL")}
    env.update({"OSN_MATERI_DASAR": "1", "OSN_BILANGAN_SEKOLAH": "0"})
    if nilai is not None:
        env[NAMA] = nilai
    kode = _KODE % {"akar": str(AKAR_MESIN), "uji": str(FOLDER_TEST)}
    return subprocess.run([sys.executable, "-c", kode], env=env, capture_output=True,
                          text=True, timeout=180)


def test_proses_baru_mati():
    hasil = _proses("0")
    assert hasil.returncode == 0, hasil.stderr
    data = json.loads(hasil.stdout)
    assert data["sidik"] == SIDIK_BASELINE["1"]
    assert data["lembar"] == "Materi ini belum dibuka."
    assert data["latihan"] is False


@pytest.mark.parametrize("nilai", [None, "1"])
def test_proses_baru_hidup_termasuk_bawaan(nilai):
    hasil = _proses(nilai)
    assert hasil.returncode == 0, hasil.stderr
    data = json.loads(hasil.stdout)
    assert data["lembar"] == "dibuat" and data["latihan"] is True
    for kunci, nilai_baseline in SIDIK_BASELINE["1"].items():
        if kunci != "daftar_topik_latihan":
            assert data["sidik"][kunci] == nilai_baseline, kunci


def test_proses_baru_nilai_tidak_sah_gagal_keras():
    hasil = _proses("2")
    assert hasil.returncode != 0
    assert NAMA in hasil.stderr


# ── mutation: palang generator, palang materi, daftar jenis ──────────────
# Mutasi lewat jalur yang dipanggil tes (monkeypatch memulihkan). Tes merah
# karena ASERSI penolakan gagal, bukan karena impor atau fixture rusak.

def test_mutation_palang_generator_dimatikan(monkeypatch):
    monkeypatch.setenv(NAMA, "0")
    periksa_pembuatan_ditolak()  # kondisi sehat: hijau
    monkeypatch.setattr(generator, "pastikan_template_dibuka", lambda urutan: None)
    with pytest.raises(AssertionError, match="seharusnya ditolak"):
        periksa_pembuatan_ditolak()


def test_mutation_palang_materi_dimatikan(monkeypatch):
    monkeypatch.setenv(NAMA, "0")
    periksa_topik_tidak_ditawarkan()  # kondisi sehat: hijau
    monkeypatch.setattr(versi, "topik_dibuka", lambda topik_id: True)
    with pytest.raises(AssertionError, match="bocor"):
        periksa_topik_tidak_ditawarkan()


def test_mutation_template_selalu_terbuka(monkeypatch):
    monkeypatch.setenv(NAMA, "0")
    monkeypatch.setattr(versi, "template_dibuka", lambda template_id: True)
    with pytest.raises(AssertionError, match="seharusnya ditolak"):
        periksa_pembuatan_ditolak()


def test_mutation_template_baru_dikosongkan(monkeypatch):
    monkeypatch.setenv(NAMA, "0")
    monkeypatch.setattr(versi, "TEMPLATE_BARU", frozenset())
    with pytest.raises(AssertionError, match="seharusnya ditolak"):
        periksa_pembuatan_ditolak()

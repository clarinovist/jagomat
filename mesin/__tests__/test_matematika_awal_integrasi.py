"""Matematika Awal: integrasi sembilan belas jenis di satu topik (P1-P6) (lembar, render, PG, determinisme, palang).

Tes per jenis (domain, solver teks, malrule) ada di `test_matematika_awal_<jenis>.py`; berkas ini
memeriksa sambungannya: pendaftaran di registri bersama, sapuan seed x level x jenis lewat
generator dan render seperti jalur nyata, lembar sepuluh soal, pilihan ganda untuk SELURUH domain
tiap jenis, determinisme lintas proses, dan bahwa topik tetap manual-saja serta tertutup sakelar.

Daftar jenis dan level dikunci dengan `==` HANYA untuk milik topik ini (baseline_matematika_awal);
registri global tetap superset.
"""
from __future__ import annotations

from dataclasses import replace
from html import unescape
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import generator
import kurikulum_cp
import kurikulum_katalog
import kurikulum_kelas
import kurikulum_kelas_hitung as hitung
import matematika_awal_versions
import multiple_choice
import question_context
import render
import rumus
import template_labels
import topics
import visual_inventory
from baseline_matematika_awal import (JENIS_PER_LEVEL, LEVEL_AWAL, LEVEL_JENIS,
                                      TEMPLATE_AWAL)
from choice_generation import buat_lembar_pilihan, kandidat, kebijakan_soal
from templates import REGISTRI

TOPIK = "matematika-awal"
AKAR_MESIN = Path(__file__).resolve().parents[1]
SEED_SAPUAN = range(25)
SEED_LEMBAR = range(12)
LEMBAR_PANJANG = 10
ISTILAH_GURU = re.compile(r"malrule|diagnosis|kode intervensi|template_id|hipotesis", re.I)
# (kelas, nomor bab, jenis) bab yang dulu "Belum ada soal" dan kini diisi topik ini (semua soal teks).
BAB_TERISI = (
    (1, 4, "kenali_bentuk"), (1, 7, "ukur_satuan_tak_baku"), (1, 8, "baca_diagram_gambar"),
    (2, 3, "kenali_bentuk"), (2, 4, "pola_posisi"), (2, 5, "pecahan_setengah"),
    (2, 6, "waktu_berat_awal"), (2, 8, "turus_gambar_awal"), (3, 3, "ukur_konversi_awal"),
    (5, 7, "bandingkan_ciri_bangun"), (6, 4, "peluang_dasar"),
)
# Gelombang 1 (21 Nov 2026): (kelas, nomor bab, jenis, kecocokan pelatih, status bab). Bab dengan jenis
# berkecocokan "ada" menjadi "ada"; tiga bab tetap "sebagian" karena sub-materinya belum tertutup
# (K4 B5 tangram/lebih dari satu cara, K5 B4 keliling bangun lain, K6 B1 hasil bilangan campur).
BAB_GELOMBANG_1 = (
    (1, 1, "bilang_benda_awal", "ada", "ada"), (1, 6, "tambah_kurang_20", "ada", "ada"),
    (2, 2, "tambah_kurang_100", "ada", "ada"), (3, 4, "unsur_bangun_datar", "ada", "ada"),
    (4, 2, "pecahan_senilai_desimal", "ada", "ada"), (4, 4, "luas_petak_volume_kubus", "ada", "ada"),
    (4, 5, "ciri_komposisi_bangun", "sebagian", "sebagian"),
    (5, 4, "keliling_gabungan", "sebagian", "sebagian"),
    (6, 1, "pecahan_bilangan_asli_desimal", "sebagian", "sebagian"),
)
# Bab data tanpa jenis baru: pelatih statistika punya jenis untuk semua sub-materi di level kelasnya,
# tetapi gambarnya (SVG) hanya muncul bila OSN_VISUAL_KELUARGA=statistika (bawaan kosong, belum aktif di
# produksi), dan mode teks membocorkan jawaban ("Apel = 5 turus"). Jadi tetap "sebagian" sampai flag aktif.
BAB_TANPA_JENIS_BARU = {(3, 5): ("turus", "piktogram", "diagram"), (4, 6): ("piktogram", "diagram")}
BAB_ADA_SEMUA = {(1, 1), (1, 6), (2, 2), (3, 4), (4, 2), (4, 4)}
PASANGAN = tuple((tid, level) for tid in TEMPLATE_AWAL for level in LEVEL_JENIS[tid])


def _paket():
    return topics.ambil(TOPIK)


def _polos(teks: str) -> str:
    """Huruf kecil tanpa spasi dan titik ribuan: kunci "3000" muncul sebagai "3.000" di pembahasan."""
    return teks.lower().replace(" ", "").replace(".", "")


def _soal_domain(tid: str, parameter: dict, level: str):
    return replace(REGISTRI[tid](**parameter), level=level)


# ── pendaftaran bersama ──────────────────────────────────────────────────

def test_sembilan_belas_jenis_terdaftar_dengan_level_eksplisit():
    paket = _paket()
    assert set(paket.templates) == set(TEMPLATE_AWAL) and len(TEMPLATE_AWAL) == 19
    assert matematika_awal_versions.TEMPLATE_BARU == frozenset(TEMPLATE_AWAL)
    assert tuple(paket.komposisi) == LEVEL_AWAL
    assert set(paket.komposisi) == {"P1", "P2", "P3", "P4", "P5", "P6"}
    for tid in TEMPLATE_AWAL:
        assert tid in REGISTRI and tid in topics.registri()
        assert topics.pemilik_template(tid) == TOPIK
        assert {lv for lv in paket.komposisi if tid in paket.komposisi[lv]} == set(LEVEL_JENIS[tid])
    for level in LEVEL_AWAL:
        assert set(paket.komposisi[level]) == JENIS_PER_LEVEL[level]


@pytest.mark.parametrize("tid", TEMPLATE_AWAL)
def test_label_kartu_rumus_dan_inventaris_visual_lengkap(tid):
    assert template_labels.nama_tipe_soal(tid) != tid
    kartu = rumus.kartu_untuk(tid)
    assert kartu is not None
    assert kartu.judul.strip() and len(kartu.inti) > 40 and kartu.contoh.strip()
    assert not ISTILAH_GURU.search(kartu.inti + kartu.contoh)
    baris = [r for r in visual_inventory.inventaris_template() if r["template_id"] == tid]
    assert baris, "inventaris visual tidak memuat jenis ini"


def test_pancingan_json_memuat_semua_jenis():
    berkas = AKAR_MESIN / "konten" / "pancingan" / "matematika-awal.json"
    data = json.loads(berkas.read_text(encoding="utf-8"))
    assert set(data["template"]) == set(TEMPLATE_AWAL)
    for isi in data["template"].values():
        assert len(isi["pertanyaan"]) == 3 and isi["tindak_lanjut"].strip()


# ── sapuan seed x level x jenis ──────────────────────────────────────────

@pytest.mark.parametrize("tid,level", PASANGAN)
def test_sapuan_seed_parameter_soal_dan_render(tid, level):
    paket = _paket()
    for seed in SEED_SAPUAN:
        parameter = paket.parameter_untuk(tid, random.Random(seed), level)
        langsung = REGISTRI[tid](**parameter)
        lewat_generator = generator.buat_soal(tid, seed, level, TOPIK)
        assert langsung.kunci.strip() and langsung.teks.strip() and langsung.pembahasan.strip()
        assert lewat_generator.level == level and lewat_generator.template_id == tid
        assert any(m.kode == "K" for m in lewat_generator.malrule), (tid, level, seed, "tanpa jalur K")
        assert not ISTILAH_GURU.search(lewat_generator.teks + lewat_generator.pembahasan)
        html = render._kartu_soal(1, lewat_generator, paket)
        assert html and "None" not in html, (tid, level, seed)
        assert lewat_generator.teks.split("\n")[0] in unescape(html), (tid, level, seed)


@pytest.mark.parametrize("tid,level", PASANGAN)
def test_pembahasan_menyebut_kunci_dan_bukan_pengulang_kunci(tid, level):
    for seed in SEED_SAPUAN:
        soal = generator.buat_soal(tid, seed, level, TOPIK)
        assert len(soal.pembahasan) > 40, (tid, level, seed, soal.pembahasan)
        assert soal.pembahasan.strip() != soal.kunci
        assert _polos(soal.kunci) in _polos(soal.pembahasan), (tid, level, seed, soal.pembahasan)


# ── lembar ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL_AWAL)
def test_lembar_sepuluh_soal_sah_deterministik_dan_tanpa_kembar(level):
    for seed in SEED_LEMBAR:
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK)
        ulang = generator.buat_lembar(seed, level=level, topik=TOPIK)
        assert len(lembar.soal) == LEMBAR_PANJANG and lembar.level == level
        assert {s.template_id for s in lembar.soal} == JENIS_PER_LEVEL[level]
        tanda = [s.tanda_tangan for s in lembar.soal]
        assert len(set(tanda)) == LEMBAR_PANJANG, (level, seed, "soal kembar dalam lembar")
        assert [(s.tanda_tangan, s.teks, s.kunci, s.pembahasan) for s in lembar.soal] == [
            (s.tanda_tangan, s.teks, s.kunci, s.pembahasan) for s in ulang.soal]
        assert all(s.kunci.strip() and s.pembahasan.strip() for s in lembar.soal)
        html = render.lembar_soal(list(lembar.soal), topik_paket=_paket())
        assert html.count('class="bagian"') == 1


def test_lembar_p4_sah_sejak_gelombang_1_dan_profil_p4_diterima():
    lembar = generator.buat_lembar(0, level="P4", topik=TOPIK)
    assert {s.template_id for s in lembar.soal} == JENIS_PER_LEVEL["P4"] and len(lembar.soal) == 10
    question_context.validasi_pilihan([TOPIK], "P4")
    # Level di luar LEVEL tetap ditolak sebagai profil.
    with pytest.raises(ValueError):
        question_context.validasi_pilihan([TOPIK], "P9")


# ── pilihan ganda ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tid,level", PASANGAN)
def test_pilihan_ganda_seluruh_domain_pengecoh_cukup_dan_berbeda_nilai(tid, level):
    paket = _paket()
    jumlah = 0
    for parameter in paket.domain_parameter(tid, level):
        soal = _soal_domain(tid, parameter, level)
        kebijakan, jenis, pengecoh = kandidat(soal)
        wajib = 2 if kebijakan == "tiga-v1" else 3
        assert len(pengecoh) == wajib, (tid, parameter, kebijakan)
        nilai = {multiple_choice.nilai_semantis(x, jenis) for x in pengecoh}
        benar = multiple_choice.nilai_semantis(soal.kunci, jenis)
        assert len(nilai) == len(pengecoh) >= 2 and benar not in nilai, (tid, parameter, pengecoh)
        assert kebijakan_soal(soal)[1] == jenis
        jumlah += 1
    assert jumlah == len(paket.domain_parameter(tid, level)) > 0


@pytest.mark.parametrize("level", LEVEL_AWAL)
def test_pilihan_ganda_lembar_dibuat_untuk_banyak_seed(level):
    for seed in range(40):
        lembar = buat_lembar_pilihan(seed, level=level, topik=TOPIK)
        assert len(lembar.soal) == LEMBAR_PANJANG
        assert {s.template_id for s in lembar.soal} == JENIS_PER_LEVEL[level]


# ── determinisme lintas proses (semua level) ─────────────────────────────

_KODE = r"""
import json, os, sys
sys.path.insert(0, %(akar)r)
for k, v in {"OSN_PBKDF2_ITERASI": "1000", "OSN_MATEMATIKA_VERSI": "2",
             "OSN_TEORI_BILANGAN_VERSI": "2", "OSN_KATALOG_VERSI": "1"}.items():
    os.environ.setdefault(k, v)
import generator
hasil = []
for level in %(level)r:
    for seed in range(15):
        for s in generator.buat_lembar(seed, level=level, topik="matematika-awal").soal:
            hasil.append([s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                          [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
print(json.dumps(hasil))
"""


def _proses(hash_seed: str):
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSN_MATEMATIKA_AWAL")}
    env["PYTHONHASHSEED"] = hash_seed
    kode = _KODE % {"akar": str(AKAR_MESIN), "level": LEVEL_AWAL}
    hasil = subprocess.run([sys.executable, "-c", kode], env=env, capture_output=True,
                           text=True, timeout=180)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_semua_level_dengan_hashseed_berbeda():
    a, b = _proses("1"), _proses("random")
    assert a == b
    assert len(a) == len(LEVEL_AWAL) * 15 * LEMBAR_PANJANG


# ── palang manual-saja dan sakelar untuk level P3+ ───────────────────────

def test_topik_tetap_manual_saja_walau_kini_memuat_level_p3_ke_atas():
    paket = _paket()
    assert paket.hanya_manual is True
    assert TOPIK not in topics.daftar_topik_siklus()
    campuran = topics.ambil("campuran")
    for level in LEVEL_AWAL:
        assert not set(TEMPLATE_AWAL) & set(campuran.komposisi.get(level, ()))
        assert not set(TEMPLATE_AWAL) & set(campuran.komposisi_untuk(level))
    assert all(topics.template_hanya_manual(tid) for tid in TEMPLATE_AWAL)
    # Bukan lagi topik dasar: gerbang OSN_MATERI_DASAR tidak menyembunyikannya (P3+ ada).
    assert question_context.topik_dasar(TOPIK) is False


@pytest.mark.parametrize("level", LEVEL_AWAL)
def test_sakelar_mati_menolak_semua_level(level, monkeypatch):
    monkeypatch.setenv("OSN_MATEMATIKA_AWAL", "0")
    for materi_dasar in ("0", "1"):
        monkeypatch.setenv("OSN_MATERI_DASAR", materi_dasar)
        with pytest.raises(ValueError, match="belum dibuka"):
            generator.buat_lembar(0, level=level, topik=TOPIK)
        with pytest.raises(ValueError, match="belum dibuka"):
            buat_lembar_pilihan(0, level=level, topik=TOPIK)
    assert TOPIK not in question_context.daftar_topik_latihan()


# ── kurikulum: katalog, peta CP, dan bab ─────────────────────────────────

def test_setiap_jenis_punya_grup_katalog_dan_peta_cp():
    entri = next(e for e in kurikulum_katalog.KATALOG if e.topik_id == TOPIK)
    grup = {pola for _kode, _nama, pola_grup in entri.grup for pola in pola_grup}
    assert grup == set(TEMPLATE_AWAL)
    for kode, _nama, _pola in entri.grup:
        peta = kurikulum_cp.CP_PER_GRUP[(TOPIK, kode)]
        assert peta, kode
        assert all(kurikulum_cp.butir(cid) and k in kurikulum_cp.KECOCOKAN for cid, k in peta)
    # kenali_bentuk dipakai bab kelas 1-2 (fase A) dan bab fase B.
    assert {cid for cid, _ in kurikulum_cp.CP_PER_GRUP[(TOPIK, "kenali_bentuk")]} == {
        "A.geometri.1", "B.geometri.1"}


@pytest.mark.parametrize("kelas,nomor,tid", BAB_TERISI)
def test_bab_yang_dulu_belum_ada_soal_kini_terisi_di_level_kelasnya(kelas, nomor, tid):
    _, bab = hitung.cari_bab(kelas, nomor)
    ringkasan = hitung.ringkasan_bab(bab, kelas, {})
    assert (TOPIK, tid) in ringkasan.template, (kelas, nomor)
    assert ringkasan.status == hitung.STATUS_SEBAGIAN  # semua soal teks tanpa gambar
    assert ringkasan.variasi.total > 0 and not ringkasan.variasi.galat and not ringkasan.variasi.tertutup
    pelatih = [p for p in ringkasan.pelatih if p.topik_id == TOPIK and tid in p.template]
    assert pelatih and pelatih[0].tersedia and pelatih[0].kecocokan == "sebagian"


@pytest.mark.parametrize("kelas,nomor,tid,kecocokan,status", BAB_GELOMBANG_1)
def test_bab_gelombang_1_status_mengikuti_kecocokan_jenis_baru(kelas, nomor, tid, kecocokan, status):
    _, bab = hitung.cari_bab(kelas, nomor)
    ringkasan = hitung.ringkasan_bab(bab, kelas, {})
    assert (TOPIK, tid) in ringkasan.template, (kelas, nomor)
    assert ringkasan.status == status, (kelas, nomor, [(p.kode, p.kecocokan) for p in ringkasan.pelatih])
    pelatih = [p for p in ringkasan.pelatih if p.topik_id == TOPIK and tid in p.template]
    assert pelatih and pelatih[0].tersedia and pelatih[0].kecocokan == kecocokan
    # Pelatih lama bab itu boleh tertutup sakelarnya (bilangan-dasar); jenis baru ini tidak.
    assert ringkasan.variasi.total > 0 and not ringkasan.variasi.galat and tid not in ringkasan.variasi.tertutup


@pytest.mark.parametrize("kelas,nomor", sorted(BAB_TANPA_JENIS_BARU))
def test_bab_data_tetap_sebagian_walau_semua_pelatihnya_tersedia_di_level_kelas(kelas, nomor):
    _, bab = hitung.cari_bab(kelas, nomor)
    ringkasan = hitung.ringkasan_bab(bab, kelas, {})
    # Jenis tersedia untuk tiap sub-materi, tetapi kecocokan tetap "sebagian" (gambar bergantung flag visual).
    assert {p.kode for p in ringkasan.pelatih if p.tersedia} == set(BAB_TANPA_JENIS_BARU[(kelas, nomor)])
    assert all(p.tersedia for p in ringkasan.pelatih)
    assert all(p.kecocokan == "sebagian" for p in ringkasan.pelatih)
    assert ringkasan.status == hitung.STATUS_SEBAGIAN


def test_hitungan_status_bab_dua_puluh_satu_ada_sembilan_belas_sebagian_nol_belum():
    status = [hitung.ringkasan_bab(b, k.kelas, {}).status for k in kurikulum_kelas.KELAS for b in k.bab]
    assert len(status) == 40
    assert status.count(hitung.STATUS_ADA) == 21
    assert status.count(hitung.STATUS_SEBAGIAN) == 19
    assert status.count(hitung.STATUS_BELUM) == 0
    ada_baru = {(k.kelas, b.nomor) for k in kurikulum_kelas.KELAS for b in k.bab
                if hitung.ringkasan_bab(b, k.kelas, {}).status == hitung.STATUS_ADA} & BAB_ADA_SEMUA
    assert ada_baru == BAB_ADA_SEMUA


def test_tidak_ada_bab_belum_ada_soal_dan_pelatih_lama_bab_k2_b4_tetap():
    for k in kurikulum_kelas.KELAS:
        for bab in k.bab:
            assert hitung.ringkasan_bab(bab, k.kelas, {}).status != hitung.STATUS_BELUM, (k.kelas, bab.nomor)
    _, bab = hitung.cari_bab(2, 4)
    assert ("pola-bilangan", "siklus", "sebagian") in bab.pelatih  # pelatih lama tetap

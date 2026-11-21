"""Matematika Awal, jenis baca_jam_awal (P2): domain, solver teks, malrule, PG, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (tanpa gambar), lihat
`jam_solver_helpers`: letak jarum dibaca lewat regex dan jam dihitung dengan rumus sendiri.
Jenis lama `waktu_berat_awal` (hanya teks, jam penuh) dikunci byte-identik lewat sidik jari yang
dihitung SEBELUM jenis baru ditulis. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru;
yang dijaga: bukan kunci, tidak kembar, selalu ada jalur K.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

import pytest

import awal_baca_jam_awal as jenis
import awal_waktu_berat_awal as jenis_lama
import diagnosis
import generator
import matematika_awal_versions as versi
import kurikulum_cp
import kurikulum_katalog
import render
import rumus
import template_labels
import topics
from choice_generation import kandidat, kebijakan_soal
from jam_solver_helpers import solver_dari_teks
from multiple_choice import nilai_semantis
from templates import REGISTRI

TOPIK = "matematika-awal"
TID = "baca_jam_awal"
LEVEL = ("P2",)
VARIAN = ("baca_penuh", "baca_setengah", "jam_kemudian", "kegiatan_selesai")
SEED = range(200)
AKAR_MESIN = Path(__file__).resolve().parents[1]
UKURAN_DOMAIN = {"baca_penuh": 12, "baca_setengah": 12, "jam_kemudian": 44, "kegiatan_selesai": 176}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)
# Sidik jari domain, 200 undian seed tetap, dan isi soal `waktu_berat_awal` (dihitung sebelum perubahan).
SIDIK_WAKTU_BERAT = "fdd37f43884816f1fd6e2d435105a469cb8715a8b55047595bac7eb4f34c72c9"


def _soal(p: dict):
    return jenis.baca_jam_awal(**p)


def _domain() -> tuple:
    return jenis.domain_parameter("P2")


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


def _hasil_jam(jam: int, lama: int) -> int:
    return (jam + lama) % 12 or 12


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == jenis.baca_jam_awal.__name__
    assert jenis.LEVEL == LEVEL and jenis.VARIAN == VARIAN
    for level in ("P1", "P3", "P6", "", None):
        with pytest.raises(ValueError):
            jenis.domain_parameter(level)
        with pytest.raises(ValueError):
            jenis.parameter(random.Random(0), level)


def test_jenis_lama_waktu_berat_awal_byte_identik():
    """Domain P2 dan 200 undian seed tetap serta isi soal tidak berubah."""
    def ringkas(s):
        return [s.template_id, s.parameter, s.teks, s.kunci, s.pembahasan, s.bagian,
                [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]]
    h = hashlib.sha256()
    for p in jenis_lama.domain_parameter("P2"):
        h.update(json.dumps(["P2", p, ringkas(jenis_lama.waktu_berat_awal(**p))],
                            sort_keys=True, ensure_ascii=False).encode())
    for seed in SEED:
        p = jenis_lama.parameter(random.Random(seed), "P2")
        h.update(json.dumps(["P2", seed, p, ringkas(jenis_lama.waktu_berat_awal(**p))],
                            sort_keys=True, ensure_ascii=False).encode())
    assert len(jenis_lama.domain_parameter("P2")) == 615
    assert h.hexdigest() == SIDIK_WAKTU_BERAT


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat():
    domain = _domain()
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain) == 244
    assert len({_soal(p).tanda_tangan for p in domain}) == len(domain)


def test_domain_dibangun_cepat_dan_urut_per_varian():
    awal = time.monotonic()
    domain = _domain()
    assert time.monotonic() - awal < 5
    urutan = [p["varian"] for p in domain]
    assert urutan == sorted(urutan, key=VARIAN.index), "domain harus urut menurut VARIAN"


def test_domain_dict_baru_setiap_panggilan_dan_sampler_murni():
    a = _domain()
    a[-1]["jam"] = 99
    a[-1]["varian"] = "rusak"
    b = _domain()
    assert b[-1]["varian"] == "kegiatan_selesai" and b[-1]["jam"] != 99
    p = jenis.parameter(random.Random(0), "P2")
    q = jenis.parameter(random.Random(0), "P2")
    assert p == q and p is not q


def test_domain_rentang_jam_lama_dan_kegiatan_tercakup():
    domain = _domain()
    baca = [p for p in domain if p["varian"] in ("baca_penuh", "baca_setengah")]
    assert {p["jam"] for p in baca} == set(range(1, 13)), "jam 12 harus ada pada dua varian baca"
    hitung = [p for p in domain if p["varian"] in ("jam_kemudian", "kegiatan_selesai")]
    assert {p["jam"] for p in hitung} == set(range(1, 12)), "jam mulai 12 dikeluarkan (kunci = lama)"
    lama = {p.get("tambah", p.get("lama")) for p in hitung}
    assert lama == {1, 2, 3, 4}
    assert {p["kegiatan"] for p in domain if p["varian"] == "kegiatan_selesai"} == set(range(4))
    assert max(_hasil_jam(p["jam"], p.get("tambah", p.get("lama"))) for p in hitung) == 12
    assert any(p["jam"] + p.get("tambah", p.get("lama")) > 12 for p in hitung), "harus ada yang melewati 12"


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian = set()
    for seed in SEED:
        p = jenis.parameter(random.Random(seed), "P2")
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
    assert varian == set(VARIAN)


def test_sebaran_varian_pada_sampel_2000_hampir_seragam():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(2000):
        hitung[jenis.parameter(random.Random(seed), "P2")["varian"]] += 1
    assert all(400 <= n <= 600 for n in hitung.values()), hitung


# ── kunci lawan solver teks (seluruh domain) ─────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID
        assert re.fullmatch(r"\d{1,2}(\.30)?", soal.kunci)
        assert (".30" in soal.kunci) == (p["varian"] == "baca_setengah")


def test_sampel_seed_kunci_sama_dengan_solver_teks():
    for seed in SEED:
        soal = _soal(jenis.parameter(random.Random(seed), "P2"))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_solver_tidak_meloloskan_kalimat_jarum_yang_ambigu_atau_salah():
    tanya = "Pukul berapa jam ini? Tulis angka jamnya."
    with pytest.raises(AssertionError):
        solver_dari_teks(f"Jarum pendek menunjuk angka 3.\n{tanya}")
    with pytest.raises(AssertionError):
        solver_dari_teks(f"Jarum pendek menunjuk angka 3 dan jarum panjang menunjuk angka 6.\n{tanya}")
    with pytest.raises(AssertionError):  # jarum pendek harus di antara dua angka yang berurutan
        solver_dari_teks("Jarum pendek ada di antara angka 2 dan 4, jarum panjang menunjuk angka 6.\n"
                         "Pukul berapa jam ini? Tulis jam, lalu titik, lalu menitnya.")
    with pytest.raises(AssertionError):
        solver_dari_teks(f"Jarum pendek menunjuk angka 3 dan jarum panjang menunjuk angka 12.\n{tanya}\nTambahan.")


def test_teks_contoh_tangan_dan_lipat_12():
    f = jenis.baca_jam_awal
    assert f("baca_penuh", jam=3).teks == (
        "Jarum pendek menunjuk angka 3 dan jarum panjang menunjuk angka 12.\n"
        "Pukul berapa jam ini? Tulis angka jamnya.")
    setengah = f("baca_setengah", jam=2)
    assert setengah.teks == ("Jarum pendek ada di antara angka 2 dan 3, jarum panjang menunjuk angka 6.\n"
                             "Pukul berapa jam ini? Tulis jam, lalu titik, lalu menitnya.")
    assert setengah.kunci == "2.30"
    dua_belas = f("baca_setengah", jam=12)
    assert "di antara angka 12 dan 1," in dua_belas.teks and dua_belas.kunci == "12.30"
    sebelas = f("baca_setengah", jam=11)
    assert "di antara angka 11 dan 12," in sebelas.teks and sebelas.kunci == "11.30"
    kemudian = f("jam_kemudian", jam=11, tambah=3)
    assert kemudian.teks == ("Sekarang jarum pendek menunjuk angka 11 dan jarum panjang menunjuk angka 12.\n"
                             "3 jam lagi, pukul berapa? Tulis angka jamnya.")
    assert kemudian.kunci == "2"
    selesai = f("kegiatan_selesai", kegiatan=0, jam=9, lama=4)
    assert selesai.teks == (
        "Sari mulai membaca cerita ketika jarum pendek menunjuk angka 9 dan jarum panjang menunjuk angka 12.\n"
        "Sari membaca cerita selama 4 jam. Pukul berapa Sari selesai? Tulis angka jamnya.")
    assert selesai.kunci == "1"
    assert f("baca_penuh", jam=12).kunci == "12"
    assert f("jam_kemudian", jam=8, tambah=4).kunci == "12"


def test_petunjuk_menulis_tanpa_angka_dan_tanpa_contoh_waktu():
    """Contoh seperti '2.30' sama dengan kunci untuk satu jam: petunjuk tidak boleh memuat angka."""
    for p in _domain():
        pertanyaan = _soal(p).teks.split("\n")[-1]
        petunjuk = pertanyaan.split("? ")[-1]
        if p["varian"] in ("baca_penuh", "baca_setengah"):
            assert not re.search(r"\d", pertanyaan), pertanyaan
        assert not re.search(r"\d\.\d", petunjuk), petunjuk


def test_teks_tanpa_gambar_pertanyaan_di_baris_terakhir_dan_satu_kunci():
    for p in _domain()[::7]:
        soal = _soal(p)
        assert soal.teks.count("?") == 1 and soal.teks.split("\n")[-1].endswith(".")
        assert not re.search(r"Perhatikan gambar", soal.teks)
        assert soal.teks.split("\n")[0].endswith(".")


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        kunci = _norm(soal.kunci)
        jawaban = [_norm(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)
        assert len(soal.malrule) >= 3, p
        assert all(len(m.jawaban) <= 5 and nilai_semantis(m.jawaban, "angka") > 0 for m in soal.malrule)


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


def test_malrule_baca_penuh_jarum_tertukar_menit_dan_lebih_kurang_satu():
    m = _malrule(dict(varian="baca_penuh", jam=3))
    assert (m["jarum_tertukar"].jawaban, m["jarum_tertukar"].kode) == ("12", "K")
    assert (m["angka_jarum_jadi_menit"].jawaban, m["angka_jarum_jadi_menit"].kode) == ("3.12", "K")
    assert (m["lebih_satu"].jawaban, m["lebih_satu"].kode) == ("4", "H")
    assert (m["kurang_satu"].jawaban, m["kurang_satu"].kode) == ("2", "H")
    dua_belas = _malrule(dict(varian="baca_penuh", jam=12))
    assert "jarum_tertukar" not in dua_belas, "jarum tertukar = kunci pada jam 12, dibuang saringan"
    assert dua_belas["angka_jarum_jadi_menit"].jawaban == "12.12"
    assert (dua_belas["lebih_satu"].jawaban, dua_belas["kurang_satu"].jawaban) == ("1", "11")
    satu = _malrule(dict(varian="baca_penuh", jam=1))
    assert satu["jarum_tertukar"].jawaban == "12" and "kurang_satu" not in satu, "kurang satu = 12 kembar K"


def test_malrule_baca_setengah_jam_sesudahnya_menit_lupa_menit_dan_tertukar():
    m = _malrule(dict(varian="baca_setengah", jam=2))
    assert (m["jam_sesudahnya"].jawaban, m["jam_sesudahnya"].kode) == ("3.30", "K")
    assert m["angka_jarum_jadi_menit"].jawaban == "2.6" and m["angka_jarum_jadi_menit"].kode == "K"
    assert m["lupa_menit"].jawaban == "2" and m["jarum_tertukar"].jawaban == "6"
    dua_belas = _malrule(dict(varian="baca_setengah", jam=12))
    assert dua_belas["jam_sesudahnya"].jawaban == "1.30"
    enam = _malrule(dict(varian="baca_setengah", jam=6))
    assert "jarum_tertukar" not in enam and enam["lupa_menit"].jawaban == "6"


@pytest.mark.parametrize("varian, isi", [
    ("jam_kemudian", dict(jam=5, tambah=2)),
    ("kegiatan_selesai", dict(kegiatan=2, jam=5, lama=2)),
])
def test_malrule_hitung_jam_awal_lama_mundur_dan_lebih_kurang_satu(varian, isi):
    m = _malrule({"varian": varian, **isi})
    assert m["jam_awal"].jawaban == "5" and m["jam_awal"].kode == "K"
    assert m["hitung_mundur"].jawaban == "3" and m["hitung_mundur"].kode == "K"
    assert m["lebih_satu"].jawaban == "8" and m["lebih_satu"].kode == "H"
    assert m["kurang_satu"].jawaban == "6" and m["kurang_satu"].kode == "H"
    assert m["lama_saja"].jawaban == "2"
    assert "lupa_kembali_ke_satu" not in m, "5 + 2 tidak melewati 12"


def test_lupa_kembali_ke_satu_hanya_bila_melewati_12_dan_batas_100():
    for p in _domain():
        if p["varian"] not in ("jam_kemudian", "kegiatan_selesai"):
            continue
        lama = p.get("tambah", p.get("lama"))
        m = _malrule(p)
        assert ("lupa_kembali_ke_satu" in m) == (p["jam"] + lama > 12), p
        if p["jam"] + lama > 12:
            assert m["lupa_kembali_ke_satu"].jawaban == str(p["jam"] + lama)
            assert m["lupa_kembali_ke_satu"].kode == "K"
    contoh = _malrule(dict(varian="jam_kemudian", jam=11, tambah=3))
    assert contoh["lupa_kembali_ke_satu"].jawaban == "14"
    assert contoh["hitung_mundur"].jawaban == "8"
    assert contoh["jam_awal"].jawaban == "11" and contoh["lama_saja"].jawaban == "3"


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_langkah():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40 and soal.pembahasan.strip() != soal.kunci
        if p["varian"] in ("jam_kemudian", "kegiatan_selesai"):
            lama = p.get("tambah", p.get("lama"))
            assert ("kembali ke angka 1" in soal.pembahasan) == (p["jam"] + lama > 12)
            assert f"Setelah {lama} langkah" in soal.pembahasan


def test_pembahasan_contoh_melewati_12_menyebut_langkah_satu_per_satu():
    soal = jenis.baca_jam_awal("jam_kemudian", jam=11, tambah=3)
    assert "Maju satu jam tiap langkah: 12, 1, 2." in soal.pembahasan
    assert "Setelah angka 12, jam kembali ke angka 1." in soal.pembahasan
    setengah = jenis.baca_jam_awal("baca_setengah", jam=12).pembahasan
    assert "belum sampai 1" in setengah and "pukul 12.30" in setengah


# ── kartu rumus, label, katalog, pancingan, sakelar ──────────────────────

def test_kartu_rumus_label_katalog_dan_cp_terdaftar():
    kartu = rumus.kartu_untuk(TID)
    assert kartu is not None and kartu.judul == "Membaca jam jarum"
    for kata in ("jarum pendek", "jarum panjang", "angka 12", "angka 6", "setengah jam"):
        assert kata in kartu.inti
    assert kartu.contoh.strip() and not TERLARANG.search(kartu.inti + kartu.contoh)
    assert template_labels.NAMA_TIPE_SOAL[TID] == "Membaca jam jarum"
    grup = [g for entri in kurikulum_katalog.KATALOG if entri.topik_id == TOPIK for g in entri.grup]
    assert (TID, "Membaca jam jarum", (TID,)) in [tuple(g) for g in grup]
    assert (TOPIK, TID) in kurikulum_cp.CP_PER_GRUP


def test_pancingan_dan_template_baru_terdaftar():
    berkas = AKAR_MESIN / "konten" / "pancingan" / "matematika-awal.json"
    isi = json.loads(berkas.read_text(encoding="utf-8"))["template"][TID]
    assert len(isi["pertanyaan"]) == 3 and isi["tindak_lanjut"].strip()
    assert TID in versi.TEMPLATE_BARU
    assert TID in topics.ambil(TOPIK).templates and TID in REGISTRI
    assert topics.pemilik_template(TID) == TOPIK


def test_komposisi_topik_memuat_jenis_di_p2_saja_dan_hanya_manual():
    paket = topics.ambil(TOPIK)
    assert TID in paket.komposisi["P2"]
    for level in ("P1", "P3", "P4", "P5", "P6"):
        assert TID not in paket.komposisi[level]
        with pytest.raises(ValueError, match="tidak tersedia untuk level"):
            generator.buat_soal(TID, 0, level, TOPIK)
    assert paket.hanya_manual is True


# ── pilihan ganda ────────────────────────────────────────────────────────

def test_pilihan_ganda_seluruh_domain_tiga_opsi_pengecoh_cukup_dan_berbeda():
    for p in _domain():
        soal = _soal(p)
        kebijakan, jenis_kunci, pengecoh = kandidat(soal)
        assert (kebijakan, jenis_kunci) == ("tiga-v1", "angka") and len(pengecoh) == 2, p
        semantik = {nilai_semantis(x, "angka") for x in pengecoh} | {nilai_semantis(soal.kunci, "angka")}
        assert len(semantik) == 3, p
        assert kebijakan_soal(soal) == (kebijakan, jenis_kunci)


def test_jawaban_tertulis_dibandingkan_dengan_kunci_setengah_jam():
    soal = jenis.baca_jam_awal("baca_setengah", jam=2)
    assert diagnosis.setara("2.30", soal.kunci, soal=soal)
    assert diagnosis.setara("2,30", soal.kunci, soal=soal)
    assert diagnosis.setara(" 2.30 ", soal.kunci, soal=soal)
    assert not diagnosis.setara("3.30", soal.kunci, soal=soal)
    assert not diagnosis.setara("2", soal.kunci, soal=soal)


# ── lembar cetak memakai bentuk TEKS yang bisa dijawab ───────────────────

def test_lembar_cetak_memakai_teks_lengkap_walau_flag_visual_menyala(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    lihat = set()
    for seed in range(150):
        lembar = generator.buat_lembar(seed, level="P2", topik=TOPIK)
        html = render.lembar_soal(list(lembar.soal), topik_paket=topics.ambil(TOPIK))
        assert "<svg" not in html
        for soal in lembar.soal:
            if soal.template_id != TID:
                continue
            lihat.add(soal.parameter["varian"])
            assert soal.penyajian is None
            assert solver_dari_teks(soal.teks) == soal.kunci
            assert soal.teks.split("\n")[0].split(" menunjuk")[0].split(" ada ")[0][:20] in html or "Jarum" in html
            assert "Perhatikan gambar jam" not in html
    assert lihat == set(VARIAN)


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("varian, isi", [
    ("tidak_ada", dict(jam=3)), (None, dict(jam=3)), (["baca_penuh"], dict(jam=3)),
    ("baca_penuh", dict(jam=0)), ("baca_penuh", dict(jam=13)), ("baca_penuh", dict(jam=-1)),
    ("baca_penuh", dict(jam=True)), ("baca_penuh", dict(jam=3.0)), ("baca_penuh", dict(jam="3")),
    ("baca_penuh", dict(jam=None)), ("baca_penuh", {}),
    ("baca_penuh", dict(jam=3, menit=0)), ("baca_penuh", dict(jam=3, tambah=1)),
    ("baca_setengah", dict(jam=0)), ("baca_setengah", dict(jam=13)), ("baca_setengah", dict(jam=2, menit=30)),
    ("jam_kemudian", dict(jam=12, tambah=1)),   # jam mulai 12 dikeluarkan
    ("jam_kemudian", dict(jam=3, tambah=0)), ("jam_kemudian", dict(jam=3, tambah=5)),
    ("jam_kemudian", dict(jam=3, tambah=True)), ("jam_kemudian", dict(jam=3)),
    ("jam_kemudian", dict(jam=3, tambah=2, lama=2)), ("jam_kemudian", dict(jam=3, lama=2)),
    ("kegiatan_selesai", dict(kegiatan=0, jam=12, lama=1)),
    ("kegiatan_selesai", dict(kegiatan=4, jam=3, lama=1)), ("kegiatan_selesai", dict(kegiatan=-1, jam=3, lama=1)),
    ("kegiatan_selesai", dict(kegiatan=True, jam=3, lama=1)),
    ("kegiatan_selesai", dict(kegiatan=0, jam=3, lama=5)), ("kegiatan_selesai", dict(kegiatan=0, jam=3, lama=0)),
    ("kegiatan_selesai", dict(kegiatan=0, jam=3)), ("kegiatan_selesai", dict(kegiatan=0, jam=3, tambah=1)),
])
def test_parameter_tidak_sah_ditolak(varian, isi):
    with pytest.raises(ValueError, match="di luar domain"):
        jenis.baca_jam_awal(varian, **isi)


def test_contoh_sah_dari_tabel_penolakan_memang_diterima():
    assert _soal({"varian": "baca_penuh", "jam": 12}).kunci == "12"
    assert _soal({"varian": "baca_setengah", "jam": 1}).kunci == "1.30"
    assert _soal({"varian": "jam_kemudian", "jam": 11, "tambah": 4}).kunci == "3"
    assert _soal({"varian": "kegiatan_selesai", "kegiatan": 3, "jam": 11, "lama": 1}).kunci == "12"


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_baca_jam_awal as jenis
hasil = []
for seed in range(200):
    p = jenis.parameter(random.Random(seed), "P2")
    s = jenis.baca_jam_awal(**p)
    hasil.append([p, s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                  [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    import templates
    jalur = [str(Path(jenis.__file__).resolve().parent),
             str(Path(templates.__file__).resolve().parent)]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE, json.dumps(jalur)],
                           env=env, capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c and len(a) == len(SEED)

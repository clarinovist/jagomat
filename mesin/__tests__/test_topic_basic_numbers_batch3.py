"""Bilangan dasar batch 2 tahap 2 (6 Nov 2026): nilai_tempat dan bandingkan_bilangan.

Domain dan solver ditulis ulang secara terpisah dari kode aplikasi. Malrule
adalah hipotesis untuk ditinjau guru; test mengunci definisi yang dipilih.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import basic_numbers_versions as versi
import database
import generator
import topics
from diagnosis import diagnosa, setara
from http_test_kit import SANDI_GURU  # noqa: F401  (memastikan kit uji termuat)

TOPIK = "bilangan-dasar"
TEMPAT = "nilai_tempat"
BANDING = "bandingkan_bilangan"
LEVEL = ("P1", "P2")
AKAR_MESIN = Path(__file__).resolve().parents[1]
KATA_TERLARANG = re.compile(r"malrule|diagnos|miskonsepsi|hipotesis|kunci|\b[KH]\b", re.I)
PERSAMAAN = re.compile(r"(\d+) ([+−]) (\d+) = (\d+)")


def _paket():
    return topics.ambil(TOPIK)


# ── nilai_tempat ────────────────────────────────────────────────────────

def _domain_tempat(level):
    """Dirakit dari digit, bukan dari rentang milik aplikasi."""
    hasil = set()
    if level == "P1":
        hasil |= {("tanya_satuan", 10 + s) for s in range(1, 10)}
        hasil |= {("susun", 10 + s) for s in range(0, 10)} | {("susun", 20)}
    else:
        for p in range(2, 10):
            for s in range(0, 10):
                hasil |= {(b, 10 * p + s) for b in ("tanya_satuan", "tanya_puluhan", "susun")}
        hasil -= {(b, 20) for b in ("tanya_satuan", "tanya_puluhan", "susun")}
    return hasil


def _solusi_tempat(teks):
    """Selesaikan dari teks soal (bukan dari parameter)."""
    if m := re.fullmatch(r"Bilangan (\d+) terdiri dari (\d+) puluhan dan \.\.\. satuan\.", teks):
        return int(m.group(1)) - 10 * int(m.group(2))
    if m := re.fullmatch(r"Bilangan (\d+) terdiri dari \.\.\. puluhan dan (\d+) satuan\.", teks):
        return (int(m.group(1)) - int(m.group(2))) // 10
    m = re.fullmatch(r"(\d+) puluhan dan (\d+) satuan membentuk bilangan \.\.\.", teks)
    assert m, teks
    return 10 * int(m.group(1)) + int(m.group(2))


@pytest.mark.parametrize("level,jumlah", (("P1", 20), ("P2", 237)))
def test_domain_dan_solver_tempat(level, jumlah):
    from topic_basic_numbers import domain_parameter
    domain = domain_parameter(TEMPAT, level)
    kunci = {(p["bentuk"], p["bilangan"]) for p in domain}
    assert len(domain) == len(kunci) == jumlah
    assert kunci == _domain_tempat(level)
    fungsi = _paket().templates[TEMPAT]
    for p in domain:
        assert set(p) == {"bentuk", "bilangan"}
        json.dumps(p)
        soal = fungsi(**p)
        assert soal.parameter == p and soal.bagian == "D"
        assert soal.kunci == str(_solusi_tempat(soal.teks)), soal.teks


def test_guard_p1_tanpa_tanya_puluhan():
    """Di P1 banyak puluhan selalu 1 (degeneratif): bentuk itu tidak boleh keluar."""
    from topic_basic_numbers import domain_parameter
    assert {p["bentuk"] for p in domain_parameter(TEMPAT, "P1")} == {"tanya_satuan", "susun"}
    paket = _paket()
    for seed in range(500):
        assert paket.parameter_untuk(TEMPAT, random.Random(seed), "P1")["bentuk"] != "tanya_puluhan"


@pytest.mark.parametrize("bentuk,bilangan", (
    ("tanya_puluhan", 14), ("tanya_satuan", 10), ("tanya_satuan", 20), ("susun", 9), ("susun", 21 + 80),
    ("diagonal", 33), ("susun", True), ("susun", 33.0), ("susun", "33"), ("tanya_satuan", None),
))
def test_parameter_tempat_tidak_sah(bentuk, bilangan):
    with pytest.raises(ValueError, match="domain"):
        _paket().templates[TEMPAT](bentuk=bentuk, bilangan=bilangan)


def _harapan_tempat(bentuk, n):
    p, s = n // 10, n % 10
    if bentuk == "susun":
        kunci = n
        kandidat = [("susun_dibalik", 10 * s + p, "K"), ("susun_dijumlah", p + s, "K"),
                    ("puluhan_meleset", n + 10, "H")]
    else:
        kunci = s if bentuk == "tanya_satuan" else p
        tertukar = p if bentuk == "tanya_satuan" else s
        kandidat = [("puluhan_satuan_tertukar", tertukar, "K"), ("nilai_bukan_banyak", 10 * p, "K"),
                    ("bilangan_utuh", n, "K")]
    hasil, terpakai = {}, {kunci}
    for nama, nilai, kode in kandidat:
        if nilai not in terpakai:
            terpakai.add(nilai)
            hasil["nilai_tempat." + nama] = (str(nilai), kode)
    return hasil


@pytest.mark.parametrize("level", LEVEL)
def test_malrule_tempat_seluruh_domain_cukup_untuk_pg(level):
    fungsi = _paket().templates[TEMPAT]
    for bentuk, n in sorted(_domain_tempat(level)):
        soal = fungsi(bentuk=bentuk, bilangan=n)
        aktual = {m.id: (m.jawaban, m.kode) for m in soal.malrule}
        assert aktual == _harapan_tempat(bentuk, n), (bentuk, n, aktual)
        assert len({m.jawaban for m in soal.malrule}) == len(soal.malrule)
        assert all(m.jawaban != soal.kunci and len(m.alasan.split()) >= 8 for m in soal.malrule)
        # Kebijakan PG tiga opsi butuh dua pengecoh pada SETIAP butir domain.
        assert len(soal.malrule) >= 2 and any(m.kode == "K" for m in soal.malrule), (bentuk, n)


def _periksa_pembahasan(soal):
    pb = soal.pembahasan
    assert not KATA_TERLARANG.search(pb), pb
    assert 30 <= len(pb) <= 200 and pb.endswith(".") and "..." not in pb, pb
    for a, op, b, c in PERSAMAAN.findall(pb):
        assert (int(a) + int(b) if op == "+" else int(a) - int(b)) == int(c), pb
    return pb


@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_tempat(level):
    fungsi = _paket().templates[TEMPAT]
    for bentuk, n in sorted(_domain_tempat(level)):
        soal = fungsi(bentuk=bentuk, bilangan=n)
        pb = _periksa_pembahasan(soal)
        p, s = n // 10, n % 10
        assert PERSAMAAN.findall(pb), pb
        assert f"{10 * p} + {s} = {n}" in pb
        if bentuk == "susun":
            assert pb.endswith(f"Jadi bilangannya {n}.")
        else:
            assert f"{n} = {p} puluhan dan {s} satuan" in pb


# ── bandingkan_bilangan ─────────────────────────────────────────────────

def _simbol(a, b):
    return "<" if a < b else ">" if a > b else "="


def _jenis_pasangan(a, b):
    if a == b:
        return "sama"
    if min(a, b) < 10 or max(a, b) > 99:
        return "lain"
    if a // 10 == b // 10:
        return "sama_puluhan"
    if a == 10 * (b % 10) + b // 10:
        return "dibalik"
    return "beda_puluhan"


@pytest.mark.parametrize("level,jumlah", (("P1", 218), ("P2", 695)))
def test_domain_bandingkan_pedagogis(level, jumlah):
    from topic_basic_numbers import domain_parameter
    domain = domain_parameter(BANDING, level)
    pasangan = {(p["a"], p["b"]) for p in domain}
    assert len(domain) == len(pasangan) == jumlah
    assert all(set(p) == {"a", "b"} and type(p["a"]) is int and type(p["b"]) is int for p in domain)
    batas_bawah, batas_atas = (1, 20) if level == "P1" else (10, 100)
    assert all(batas_bawah <= x <= batas_atas for pr in pasangan for x in pr)
    # Dua arah: setiap pasangan punya kebalikannya, jadi < dan > seimbang.
    assert all((b, a) in pasangan for a, b in pasangan)
    simbol = Counter(_simbol(a, b) for a, b in pasangan)
    assert simbol["<"] == simbol[">"]
    porsi = simbol["="] / len(pasangan)
    assert 0.05 <= porsi <= 0.15, porsi
    assert {a for a, b in pasangan if a == b} == set(range(batas_bawah, batas_atas + 1))
    jenis = Counter(_jenis_pasangan(a, b) for a, b in pasangan)
    assert jenis["sama"] and jenis["sama_puluhan"] and jenis["beda_puluhan"]
    if level == "P2":
        # Semua pasangan angka dibalik (12/21 ... 89/98) wajib ada, dua arah.
        dibalik = {(10 * p + s, 10 * s + p) for p in range(1, 10) for s in range(1, 10) if p != s}
        assert dibalik <= pasangan and jenis["dibalik"] == len(dibalik)
        assert (35, 53) in pasangan and (53, 35) in pasangan and (100, 99) in pasangan
    else:
        assert jenis["dibalik"] == 0  # bilangan <= 20: tidak ada pasangan dibalik


def test_guard_porsi_sama_dengan_di_domain_tidak_nol():
    """Mutation: bila '=' dibuang dari domain, porsi turun ke 0 dan guard merah."""
    from topic_basic_numbers import domain_parameter
    for level in LEVEL:
        porsi = sum(p["a"] == p["b"] for p in domain_parameter(BANDING, level)) / len(domain_parameter(BANDING, level))
        assert 0.05 <= porsi <= 0.15


@pytest.mark.parametrize("a,b", ((0, 1), (1, 40), (21, 29), (101, 100), (9, 10 + 90), (True, 3), (3.0, 4),
                                ("3", 4), (None, 4), (-1, 2)))
def test_parameter_bandingkan_tidak_sah(a, b):
    with pytest.raises(ValueError, match="domain"):
        _paket().templates[BANDING](a=a, b=b)


def _harapan_banding(a, b):
    kunci = _simbol(a, b)
    if kunci == "=":
        return {BANDING + ".sama_dikira_kurang": ("<", "K"), BANDING + ".sama_dikira_lebih": (">", "K")}
    kandidat = []
    if min(a, b) >= 10 and a // 10 != b // 10:
        kandidat.append(("banding_satuan", _simbol(a % 10, b % 10)))
    kandidat.append(("arah_terbalik", ">" if kunci == "<" else "<"))
    hasil, terpakai = {}, {kunci}
    for nama, nilai in kandidat:
        if nilai not in terpakai:
            terpakai.add(nilai)
            hasil[BANDING + "." + nama] = (nilai, "K")
    return hasil


@pytest.mark.parametrize("level", LEVEL)
def test_soal_dan_malrule_bandingkan_seluruh_domain(level):
    from topic_basic_numbers import domain_parameter
    fungsi = _paket().templates[BANDING]
    for p in domain_parameter(BANDING, level):
        a, b = p["a"], p["b"]
        soal = fungsi(a=a, b=b)
        assert soal.teks == f"Isi dengan <, >, atau =: {a} ... {b}" and soal.bagian == "E"
        assert soal.kunci == _simbol(a, b) and soal.parameter == p
        aktual = {m.id: (m.jawaban, m.kode) for m in soal.malrule}
        assert aktual == _harapan_banding(a, b), (a, b, aktual)
        assert soal.malrule and all(m.jawaban != soal.kunci and len(m.alasan.split()) >= 8 for m in soal.malrule)
        assert len({m.jawaban for m in soal.malrule}) == len(soal.malrule)


def test_prioritas_banding_satuan_atas_arah_terbalik_dan_kunci_sama():
    fungsi = _paket().templates[BANDING]
    s = fungsi(a=35, b=53)  # satuan 5 > 3: '>' sama dengan arah terbalik; yang spesifik menang
    assert [(m.id, m.jawaban) for m in s.malrule] == [(BANDING + ".banding_satuan", ">")]
    s = fungsi(a=38, b=41)  # satuan 8 > 1 = arah terbalik juga
    assert [m.id for m in s.malrule] == [BANDING + ".banding_satuan"]
    s = fungsi(a=50, b=100)  # satuan sama -> '=' , lain dari kunci dan dari arah terbalik
    assert [(m.id, m.jawaban) for m in s.malrule] == [(BANDING + ".banding_satuan", "="),
                                                      (BANDING + ".arah_terbalik", ">")]
    s = fungsi(a=34, b=34)
    assert [(m.id, m.jawaban) for m in s.malrule] == [(BANDING + ".sama_dikira_kurang", "<"),
                                                      (BANDING + ".sama_dikira_lebih", ">")]
    assert [m.id for m in fungsi(a=7, b=12).malrule] == [BANDING + ".arah_terbalik"]  # satu angka: tak ada puluhan


@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_bandingkan(level):
    from topic_basic_numbers import domain_parameter
    fungsi = _paket().templates[BANDING]
    for p in domain_parameter(BANDING, level):
        a, b = p["a"], p["b"]
        soal = fungsi(a=a, b=b)
        pb = soal.pembahasan
        assert not KATA_TERLARANG.search(pb) and 15 <= len(pb) <= 200, pb
        assert pb.endswith(f"{a} {soal.kunci} {b}."), pb
        assert pb.count(".") <= 3
        if a == b:
            assert "sama besar" in pb
        elif min(a, b) >= 10 and a // 10 != b // 10:
            assert pb.startswith("Bandingkan puluhannya dulu") and f"{a // 10} puluhan" in pb
        elif min(a, b) >= 10:
            assert pb.startswith("Puluhannya sama") and "satuannya" in pb
        arti = "lebih kecil dari" if a < b else "lebih besar dari"
        if a != b:
            assert f"{a} {arti} {b}" in pb


@pytest.mark.parametrize("jawab,kunci,hasil", (
    ("<", "<", True), (" < ", "<", True), ("＜", "<", True), (">", ">", True), ("=", "=", True),
    (" = ", "=", True), ("<", ">", False), (">", "<", False), ("=", "<", False), ("<", "=", False),
))
def test_jawaban_isian_simbol_setara(jawab, kunci, hasil):
    assert setara(jawab, kunci) is hasil
    soal = _paket().templates[BANDING](a=35, b=53)
    assert setara(jawab, kunci, soal=soal) is hasil


def test_diagnosis_simbol_memakai_malrule_tersimpan():
    soal = _paket().templates[BANDING](a=35, b=53)
    malrule = [{"malrule_id": m.id, "jawaban": m.jawaban, "kode": m.kode, "alasan": m.alasan} for m in soal.malrule]
    benar = diagnosa(soal.kunci, " < ", "puluhan dulu", "", False, malrule, soal=soal)
    assert benar.benar is True
    salah = diagnosa(soal.kunci, ">", "satuan 5 lebih besar", "", False, malrule, soal=soal)
    assert (salah.benar, salah.kode, salah.malrule_id) == (False, "K", BANDING + ".banding_satuan")
    taktahu = diagnosa(soal.kunci, "=", "sama", "", False, malrule, soal=soal)
    assert taktahu.benar is False and taktahu.kode is None


@pytest.mark.parametrize("tid", (TEMPAT, BANDING))
@pytest.mark.parametrize("level", LEVEL)
def test_seed_0_sampai_24_kunci_solver_dan_malrule(tid, level):
    paket = _paket()
    domain = _domain_tempat(level)
    for seed in range(25):
        soal = generator.buat_soal(tid, seed, level, TOPIK)
        assert soal == generator.buat_soal(tid, seed, level, TOPIK) and soal.level == level
        if tid == TEMPAT:
            assert (soal.parameter["bentuk"], soal.parameter["bilangan"]) in domain
            assert soal.kunci == str(_solusi_tempat(soal.teks))
        else:
            a, b = soal.parameter["a"], soal.parameter["b"]
            assert soal.kunci == _simbol(a, b)
        assert soal.malrule and all(m.jawaban != soal.kunci for m in soal.malrule)
        assert soal.parameter == paket.parameter_untuk(tid, random.Random(seed), level)


@pytest.mark.parametrize("level", LEVEL)
def test_pg_seluruh_domain_nilai_tempat_dan_bandingkan(level):
    from choice_generation import pilihan_soal
    from topic_basic_numbers import domain_parameter
    paket = _paket()
    for p in domain_parameter(TEMPAT, level):
        soal = replace(paket.templates[TEMPAT](**p), level=level)
        pilihan = pilihan_soal(soal, 1, "a" * 64, 0, 1)
        assert len(pilihan.opsi) == 3
        assert {o.nilai for o in pilihan.opsi} == {soal.kunci, *(m.jawaban for m in soal.malrule[:2])}
    for p in domain_parameter(BANDING, level):
        soal = replace(paket.templates[BANDING](**p), level=level)
        pilihan = pilihan_soal(soal, 1, "a" * 64, 0, 1)
        assert len(pilihan.opsi) == 3
        assert {o.nilai for o in pilihan.opsi} == {"<", ">", "="}
        assert sum(o.nilai == soal.kunci for o in pilihan.opsi) == 1


def test_urutan_opsi_simbol_deterministik_dan_bervariasi_antar_seed():
    from choice_generation import pilihan_soal
    soal = replace(_paket().templates[BANDING](a=35, b=53), level="P2")
    urutan = {s: tuple(o.nilai for o in pilihan_soal(soal, 1, "a" * 64, s, 1).opsi) for s in range(30)}
    assert urutan == {s: tuple(o.nilai for o in pilihan_soal(soal, 1, "a" * 64, s, 1).opsi) for s in range(30)}
    assert len(set(urutan.values())) >= 4  # enam permutasi mungkin; tidak selalu satu urutan
    assert all(sorted(v) == ["<", "=", ">"] for v in urutan.values())


@pytest.mark.parametrize("level", LEVEL)
def test_pg_lembar_campuran_tidak_mengganti_slot_dan_tanpa_kembar(level, monkeypatch):
    """Dengan sakelar hidup (writer campuran), lembar PG = lembar isian untuk kedua jenis baru."""
    from choice_generation import buat_lembar_pilihan
    monkeypatch.setattr(versi, "dasar_lengkap_aktif", lambda: True)
    paket = replace(_paket(), komposisi_writer=None)
    monkeypatch.setitem(topics.PAKET, TOPIK, paket)
    for seed in range(60):
        isian = generator.buat_lembar(seed, level=level, topik=paket, jumlah_soal=30)
        pg = buat_lembar_pilihan(seed, level=level, topik=paket, jumlah_soal=30)
        baru = [s for s in isian.soal if s.template_id in (TEMPAT, BANDING)]
        assert len(baru) == 12 and len({s.tanda_tangan for s in isian.soal if s.template_id in (TEMPAT, BANDING)}) == 12
        assert [s.tanda_tangan for s in pg.soal if s.template_id in (TEMPAT, BANDING)] == [s.tanda_tangan for s in baru]


def test_semantik_simbol_menolak_nilai_lain():
    from multiple_choice import nilai_semantis
    assert nilai_semantis(" ＜ ", "simbol_perbandingan") == "<"
    for salah in ("<=", "a", "", "<>", "1"):
        with pytest.raises(ValueError):
            nilai_semantis(salah, "simbol_perbandingan")
    # jenis lain tidak terpengaruh
    assert nilai_semantis("12", "angka") == 12
    with pytest.raises(ValueError):
        nilai_semantis("<", "angka")


def test_kebijakan_pg_per_template_dasar():
    from choice_generation import kebijakan_soal
    contoh = {
        "tambah_dasar": {"a": 1, "b": 2}, "kurang_dasar": {"a": 3, "b": 1},
        "bilangan_hilang": {"bentuk": "tambah_akhir", "tampak": 1, "hasil": 3},
        TEMPAT: {"bentuk": "susun", "bilangan": 14}, BANDING: {"a": 3, "b": 4},
    }
    for tid, parameter in contoh.items():
        harapan = ("tiga-v1", "simbol_perbandingan" if tid == BANDING else "angka")
        assert kebijakan_soal(_paket().templates[tid](**parameter)) == harapan, tid


# ── render dan escape (sakelar dibuka hanya untuk membuat riwayat sintetis) ──

def _buat_sesi_sintetis(kon, siswa, monkeypatch, format_jawaban):
    """Sesi campuran dibuat dengan sakelar hidup (writer campuran) hanya selama pembuatan."""
    with monkeypatch.context() as m:
        m.setenv("OSN_MATERI_DASAR", "1")
        m.setattr(versi, "dasar_lengkap_aktif", lambda: True)
        m.setitem(topics.PAKET, TOPIK, replace(_paket(), komposisi_writer=None))
        sesi = database.buat_sesi(kon, siswa, 5, topik=TOPIK, level="P2", format_jawaban=format_jawaban)
    jenis = {r[0] for r in kon.execute(
        "SELECT so.template_id FROM sesi_soal ss JOIN soal so ON so.id = ss.soal_id WHERE ss.sesi_id = ?", (sesi,))}
    assert BANDING in jenis and TEMPAT in jenis
    return sesi


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "banding.db"
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon, database.tambah_siswa(kon, "Sintetis", pemilik="guru")


def test_render_isian_murid_guru_dan_cetak_meng_escape_simbol(db, monkeypatch):
    import student_pages
    import worksheets
    kon, siswa = db
    sesi = _buat_sesi_sintetis(kon, siswa, monkeypatch, "isian")
    halaman = student_pages.halaman_kerja_baru(kon, siswa, sesi).decode()
    assert "Isi dengan &lt;, &gt;, atau =" in halaman and "Isi dengan <" not in halaman
    assert 'type="text"' in halaman
    butir = database.isi_sesi(kon, sesi)
    banding = [b for b in butir if b["template_id"] == BANDING]
    assert banding and all(b["kunci"] in ("<", ">", "=") for b in banding)
    soal = tuple(generator.buat_soal(BANDING, s, "P2", TOPIK) for s in (0, 1, 2))
    cetak = worksheets.lembar_soal(soal, "Sintetis", "2026-11-06", topik_paket=_paket())
    guru = worksheets.lembar_penilaian(soal, "Sintetis", "2026-11-06", 0, topik_paket=_paket())
    assert "Isi dengan &lt;, &gt;, atau =" in cetak and "Isi dengan <" not in cetak
    peta = {"<": "&lt;", ">": "&gt;", "=": "="}
    for s in soal:  # kunci dan jawaban salah tercatat di-escape pada lembar penilaian guru
        assert "Kunci: " + peta[s.kunci] + "<" in guru
        assert "<b>" + peta[s.malrule[0].jawaban] + "</b>" in guru
    assert "Kunci: <" not in guru and "<b><</b>" not in guru
    for s in soal:  # pembahasan ikut di-escape bila memuat tanda
        assert s.pembahasan.endswith(s.kunci + " " + str(s.parameter["b"]) + ".")


def test_render_pg_murid_cetak_dan_guru_meng_escape_opsi(db, monkeypatch):
    import choice_pages
    import student_pages
    kon, siswa = db
    sesi = _buat_sesi_sintetis(kon, siswa, monkeypatch, "pilihan_ganda")
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    halaman = student_pages.halaman_kerja_baru(kon, siswa, sesi).decode()
    assert re.search(r"[ABC]\. &lt;", halaman) and re.search(r"[ABC]\. &gt;", halaman)
    assert 'name="opsi_' in halaman and "Isi dengan &lt;, &gt;, atau =" in halaman
    for untuk_guru in (False, True):
        cetak = choice_pages.lembar_pilihan(kon, sesi, untuk_guru=untuk_guru)
        cetak = cetak.decode() if isinstance(cetak, bytes) else cetak
        assert re.search(r"[ABC]\. &lt;", cetak) and re.search(r"[ABC]\. &gt;", cetak)
        assert "Isi dengan <" not in cetak and "Isi dengan &lt;, &gt;, atau =" in cetak
        assert ("Kunci:" in cetak) is untuk_guru


# ── sakelar, determinisme ───────────────────────────────────────────────

def test_sakelar_mati_tidak_membuat_jenis_tahap_2():
    with pytest.raises(ValueError, match="belum dibuka"):
        generator.buat_lembar(0, urutan=(TEMPAT, BANDING), level="P2", topik=TOPIK)
    for level in LEVEL:
        for seed in range(30):
            ids = {s.template_id for s in generator.buat_lembar(seed, level=level, topik=TOPIK).soal}
            assert ids == {"tambah_dasar"}


def test_determinisme_lintas_hashseed_tahap_2():
    skrip = (
        "import json, generator\n"
        "from dataclasses import asdict\n"
        "print(json.dumps([asdict(generator.buat_soal(t, s, lv, 'bilangan-dasar'))\n"
        "  for t in ('nilai_tempat', 'bandingkan_bilangan') for lv in ('P1', 'P2') for s in range(50)],\n"
        "  sort_keys=True))\n"
    )
    keluaran = []
    for hashseed in ("1", "997"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        keluaran.append(subprocess.check_output([sys.executable, "-c", skrip], cwd=AKAR_MESIN, env=env))
    assert keluaran[0] == keluaran[1] and len(json.loads(keluaran[0])) == 200


def test_jawaban_isian_simbol_tersimpan_utuh_dan_tidak_di_escape(db, monkeypatch):
    import students
    kon, siswa = db
    sesi = _buat_sesi_sintetis(kon, siswa, monkeypatch, "isian")
    butir = [b for b in database.isi_sesi(kon, sesi) if b["template_id"] == BANDING]
    sid = butir[0]["sesi_soal_id"]
    data = {f"jwb_{b['sesi_soal_id']}": s for b, s in zip(butir, ("<", ">"))}
    assert students.simpan_jawaban_murid(kon, siswa, sesi, data) is not None
    tersimpan = {r[0]: r[1] for r in kon.execute(
        "SELECT sesi_soal_id, jawaban FROM jawaban WHERE sesi_soal_id IN (%s)" % ",".join(str(b["sesi_soal_id"]) for b in butir))}
    assert tersimpan[sid] == "<" and "&lt;" not in tersimpan.values()
    assert tersimpan[butir[1]["sesi_soal_id"]] == ">"


# ── Self-review 6 Nov 2026 (pengganti ulasan guru atas keputusan pemilik) ──

@pytest.mark.parametrize("level", LEVEL)
def test_alasan_nilai_bukan_banyak_menyebut_angka_soal(level):
    """Alasan untuk guru memakai angka soal itu sendiri, bukan contoh 40 yang lepas konteks."""
    paket = topics.ambil(TOPIK)
    for p in paket.domain_parameter(TEMPAT, level):
        soal = paket.templates[TEMPAT](**p)
        for m in soal.malrule:
            if m.id == "nilai_tempat.nilai_bukan_banyak":
                assert "misalnya 40" not in m.alasan
                assert m.jawaban in m.alasan
                ditanya = "satuan" if p["bentuk"] == "tanya_satuan" else "puluhan"
                assert f"banyak {ditanya}" in m.alasan


def test_pembahasan_satu_digit_memakai_urutan_membilang():
    """Kelas 1: bilangan satu digit dibandingkan lewat urutan membilang, bukan sekadar disebut."""
    paket = topics.ambil(TOPIK)
    satu_digit = [p for p in paket.domain_parameter(BANDING, "P1")
                  if max(p["a"], p["b"]) < 10 and p["a"] != p["b"]]
    assert satu_digit
    for p in satu_digit:
        pembahasan = paket.templates[BANDING](**p).pembahasan
        kecil, besar = sorted((p["a"], p["b"]))
        assert "membilang" in pembahasan
        assert f"{kecil} disebut lebih dulu daripada {besar}" in pembahasan

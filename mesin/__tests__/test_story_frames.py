"""Bank kalimat offline: allowlist, parameter publik, determinisme dan batas klaim."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import story_frames as bank
import topics
from templates import REGISTRI


@pytest.mark.parametrize("tid,level", (
    ("kpk_dua_bilangan", "P5"), ("kpk_dua_bilangan", "P6"),
    ("aturan_kali", "P5"), ("jabat_tangan", "P5"),
))
def test_bank_tidak_mengubah_soal_dan_seluruh_bingkai_terjangkau(tid, level):
    paket = topics.ambil(topics.pemilik_template(tid))
    terlihat = set()
    for seed in range(600):
        p = paket.parameter_untuk(tid, random.Random(seed), level)
        soal = REGISTRI[tid](**p)
        sebelum = asdict(soal)
        for nomor in range(len(bank.BANK[tid])):
            hasil = bank.kalimat_baru(tid, level, p, nomor=nomor)
            assert hasil is not None and hasil.bank_versi == bank.VERSI_BANK
            terlihat.add(hasil.bingkai_id)
            assert Counter(re.findall(r"\d+", hasil.teks)) == Counter(map(str, p.values()))
            assert "{" not in hasil.teks and "}" not in hasil.teks
        assert asdict(soal) == sebelum
        assert bank.kalimat_baru(tid, level, p) == bank.kalimat_baru(tid, level, dict(reversed(list(p.items()))))
    assert terlihat == {b.id for b in bank.BANK[tid]}


@pytest.mark.parametrize("tid,p,level,expected", (
    ("kpk_dua_bilangan", {"a": 6, "b": 8}, "P5", 24),
    ("kpk_dua_bilangan", {"a": 12, "b": 12}, "P6", 12),
    ("aturan_kali", {"m": 3, "n": 4}, "P5", 12),
    ("jabat_tangan", {"n": 5}, "P5", 10),
))
def test_contoh_semua_bingkai_memuat_asumsi_operasi(tid, p, level, expected):
    # Pemeriksaan mekanis atas istilah hanya pelengkap, bukan solver bahasa.
    if tid == "kpk_dua_bilangan":
        kunci = next(i for i in range(1, p["a"] * p["b"] + 1) if i % p["a"] == i % p["b"] == 0)
    elif tid == "aturan_kali":
        kunci = len([(a, b) for a in range(p["m"]) for b in range(p["n"])])
    else:
        kunci = len([(a, b) for a in range(p["n"]) for b in range(a + 1, p["n"])])
    assert kunci == expected == int(REGISTRI[tid](**p).kunci)
    for nomor in range(len(bank.BANK[tid])):
        teks = bank.kalimat_baru(tid, level, p, nomor=nomor).teks
        if tid == "kpk_dua_bilangan":
            assert "menit" in teks and "bersamaan" in teks
            assert any(kata in teks for kata in ("pertama", "berikutnya"))
        elif tid == "aturan_kali":
            assert "satu" in teks and any(kata in teks for kata in ("Semua", "semua", "Setiap", "setiap"))
        else:
            assert "jabat" in teks and any(kata in teks for kata in ("pasangan", "orang lain", "orang lainnya"))


@pytest.mark.parametrize("tid", ("keterbagian", "sisa_pembagian", "banyak_prima", "operasi_berkurung", "asing"))
def test_hitung_murni_dan_template_asing_tidak_dibungkus(tid):
    assert bank.kalimat_baru(tid, "P5", {}) is None


def test_pemilih_default_memakai_seluruh_bingkai():
    for tid, level in (("kpk_dua_bilangan", "P5"), ("aturan_kali", "P5"), ("jabat_tangan", "P5")):
        paket = topics.ambil(topics.pemilik_template(tid))
        terlihat = {bank.kalimat_baru(tid, level, paket.parameter_untuk(tid, random.Random(seed), level)).bingkai_id
                    for seed in range(600)}
        assert terlihat == {b.id for b in bank.BANK[tid]}, "pemilih default runtuh"


def test_mutation_pemilih_konstan_ditangkap(monkeypatch):
    class Tetap:
        def hexdigest(self):
            return "0" * 64
    monkeypatch.setattr(bank.hashlib, "sha256", lambda *a: Tetap())
    with pytest.raises(AssertionError, match="pemilih default runtuh"):
        test_pemilih_default_memakai_seluruh_bingkai()


def test_level_di_luar_allowlist_tidak_dibungkus():
    assert bank.kalimat_baru("aturan_kali", "P6", {"m": 3, "n": 4}) is None


@pytest.mark.parametrize("p", (
    {"m": 3, "n": 4, "kunci": 12}, {"m": 3, "n": 4, "malrule": []},
    {"m": 3}, {"m": True, "n": 4}, {"m": 0, "n": 4}, {"m": "3", "n": 4},
))
def test_parameter_rahasia_dan_invalid_ditolak(p):
    with pytest.raises(ValueError, match="parameter publik"):
        bank.kalimat_baru("aturan_kali", "P5", p)


@pytest.mark.parametrize("pola", (
    "Ada {m} dan {kunci}.", "Ada {m} saja.", "Ada {m} {n} {n}.",
    "Ada {m} {n}, jawabannya 12.", "<b>{m}</b> {n}", "{m.__class__} {n}",
    "{m!r} {n}", "{m:02} {n}", "{m {n}",
))
def test_mutation_pola_invalid_ditolak(pola):
    rusak = dict(bank.BANK)
    awal = rusak["aturan_kali"]
    rusak["aturan_kali"] = (replace(awal[0], pola=pola), *awal[1:])
    with pytest.raises(ValueError):
        bank.validasi_bank(rusak)
    bank.validasi_bank(bank.BANK)


def test_mutation_allowlist_dan_id_duplikat_ditolak():
    with pytest.raises(ValueError, match="allowlist"):
        bank.validasi_bank({**bank.BANK, "keterbagian": bank.BANK["aturan_kali"]})
    rusak = dict(bank.BANK)
    rusak["aturan_kali"] = (rusak["aturan_kali"][0],) * 6
    with pytest.raises(ValueError, match="duplikat"):
        bank.validasi_bank(rusak)


def test_mutation_bank_allowlist_hilang_gagal_tertutup(monkeypatch):
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    monkeypatch.setattr(bank, "BANK", {})
    from question_views import penyajian_dari_soal
    soal = replace(REGISTRI["aturan_kali"](m=3, n=4), level="P5")
    with pytest.raises(ValueError, match="allowlist"):
        penyajian_dari_soal(soal)


def test_bank_deterministik_antar_proses():
    perintah = (
        "import json; from dataclasses import asdict; from story_frames import kalimat_baru; "
        "print(json.dumps(asdict(kalimat_baru('kpk_dua_bilangan','P5',{'a':6,'b':8})),sort_keys=True))"
    )
    hasil = [subprocess.check_output(
        [sys.executable, "-B", "-c", perintah], cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONDONTWRITEBYTECODE="1"),
    ) for seed in (1, 97)]
    assert hasil[0] == hasil[1]


def test_ekspor_manifest_konten_dan_tidak_menimpa(tmp_path):
    import importlib.util
    import hashlib
    import json
    path = Path(__file__).resolve().parents[2] / "scripts/story_frames_preview.py"
    spec = importlib.util.spec_from_file_location("preview_bingkai_uji", path)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    folder = tmp_path / "preview"
    manifest = modul.ekspor(folder)
    data = json.dumps(manifest["bank"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert manifest["konten_sha256"] == hashlib.sha256(data.encode()).hexdigest()
    assert manifest["bank_versi"] == bank.VERSI_BANK
    assert len(manifest["contoh"]) == 18
    assert len(manifest["source_sha"]) == 40
    assert (folder / "tinjauan.html").is_file()
    awal = (folder / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        modul.ekspor(folder)
    assert (folder / "manifest.json").read_bytes() == awal


def test_default_tidak_mengubah_snapshot_aplikasi(monkeypatch):
    from generator import buat_soal
    from question_views import penyajian_dari_soal
    monkeypatch.delenv("OSN_BANK_KALIMAT", raising=False)
    soal = buat_soal("kpk_dua_bilangan", 1, "P5", "teori-bilangan")
    assert penyajian_dari_soal(soal).teks_soal == soal.teks


@pytest.mark.parametrize("tid,p", (
    ("kpk_dua_bilangan", {"a": 6, "b": 8}),
    ("aturan_kali", {"m": 3, "n": 4}),
    ("jabat_tangan", {"n": 5}),
))
def test_optin_snapshot_baru_memakai_bank_tanpa_ubah_soal(monkeypatch, tid, p):
    from question_views import penyajian_dari_soal
    from visual_contract import fingerprint_matematis
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    soal = replace(REGISTRI[tid](**p), level="P5")
    awal = asdict(soal)
    hasil = penyajian_dari_soal(soal)
    assert hasil.teks_soal == bank.kalimat_baru(tid, "P5", p).teks
    assert hasil.teks_soal != soal.teks
    assert hasil.fingerprint_matematis == fingerprint_matematis(1, tid, "P5", p)
    assert (hasil.penyajian_versi, hasil.renderer_versi, hasil.asal_teks, hasil.mode_representasi) == (1, 1, "bawaan", "teks-v1")
    assert asdict(soal) == awal


def test_optin_tidak_membungkus_kpk_perintah_murni(monkeypatch):
    from question_views import penyajian_dari_soal
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    soal = replace(REGISTRI["kpk_dua_bilangan"](a=6, b=9), level="P5")
    assert soal.teks == "Berapa KPK dari 6 dan 9?"
    assert penyajian_dari_soal(soal).teks_soal == soal.teks


def test_optin_kpk_bentuk_canonical_baru_tidak_dianggap_cerita_disetujui(monkeypatch):
    from question_views import penyajian_dari_soal
    asli = REGISTRI["kpk_dua_bilangan"]
    monkeypatch.setitem(REGISTRI, "kpk_dua_bilangan", lambda **p: replace(asli(**p), teks="Tentukan KPK kedua bilangan."))
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    soal = replace(REGISTRI["kpk_dua_bilangan"](a=6, b=9), level="P5")
    assert penyajian_dari_soal(soal).teks_soal == soal.teks


def test_optin_tidak_menimpa_teks_kustom_dan_visual(monkeypatch):
    import question_views as q
    monkeypatch.setenv("OSN_BANK_KALIMAT", "1")
    soal = replace(REGISTRI["aturan_kali"](m=3, n=4), level="P5")
    kustom = replace(soal, teks="Teks snapshot pilihan guru")
    assert q.penyajian_dari_soal(kustom).teks_soal == kustom.teks
    # Descriptor sah dari proyektor existing; injeksikan ke template allowlist
    # untuk membuktikan visual didahulukan, bukan gagal akibat fixture rusak.
    from topic_combinatorics_visual import proyeksi_kombinatorik
    proyeksi = proyeksi_kombinatorik("jalur_petak", {"b": 3, "k": 4})
    assert proyeksi is not None
    monkeypatch.setattr(q, "_proyeksi_visual_aktif", lambda s: proyeksi)
    monkeypatch.setattr(bank, "kalimat_baru", lambda *a, **k: pytest.fail("bank dipakai untuk visual"))
    hasil = q.penyajian_dari_soal(soal)
    assert hasil.teks_soal == proyeksi[0] and hasil.status_visual == "siap"


@pytest.mark.parametrize("nilai", ("", "true", "2", "yes"))
def test_optin_invalid_ditolak(monkeypatch, nilai):
    from question_views import penyajian_dari_soal
    monkeypatch.setenv("OSN_BANK_KALIMAT", nilai)
    soal = replace(REGISTRI["aturan_kali"](m=3, n=4), level="P5")
    with pytest.raises(ValueError, match="OSN_BANK_KALIMAT"):
        penyajian_dari_soal(soal)

"""Kontrak publik pilihan 3–5: replay, bentuk ketat, dan tanpa penanda kunci."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from choice_contract import OpsiJawaban, PilihanButir, deserialisasi, fingerprint, serialisasi
from multiple_choice import buat_pilihan, nilai_semantis, pilihan_tertanam, validasi_kebenaran


def contoh(kebijakan="empat-v1", **tambahan):
    arg = dict(sesi_soal_id=7, fingerprint_pertanyaan="a" * 64,
               kebijakan=kebijakan, jenis="angka", kunci="24",
               pengecoh=("12", "23", "48") if kebijakan == "empat-v1" else ("12", "23"),
               seed=35, identitas="P3|soal(angka=12)|nomor=1")
    arg.update(tambahan)
    return buat_pilihan(**arg)


@pytest.mark.parametrize("kebijakan,jumlah", [("tiga-v1", 3), ("empat-v1", 4)])
def test_snapshot_jumlah_tetap_replay_dan_id_netral(kebijakan, jumlah):
    p = contoh(kebijakan)
    assert len(p.opsi) == jumlah
    assert [o.id for o in p.opsi] == [f"opsi_{i}" for i in range(1, jumlah + 1)]
    assert sum(o.nilai == "24" for o in p.opsi) == 1
    assert deserialisasi(serialisasi(p), fingerprint(p), sesi_soal_id=7,
                         fingerprint_pertanyaan="a" * 64) == p
    with pytest.raises(FrozenInstanceError):
        p.kebijakan = "tiga-v1"
    with pytest.raises(FrozenInstanceError):
        p.opsi[0].teks = "baru"
    assert set(json.loads(serialisasi(p))) == {
        "versi", "sesi_soal_id", "fingerprint_pertanyaan", "kebijakan", "opsi"}
    assert all(set(o) == {"id", "label", "nilai", "teks"}
               for o in json.loads(serialisasi(p))["opsi"])


@pytest.mark.parametrize("ubah", [
    {"pengecoh": ("12", "23")}, {"pengecoh": ("12", "23", "48", "49")},
    {"pengecoh": ("12", "12", "48")}, {"pengecoh": ("24", "23", "48")},
    {"pengecoh": ("24,0", "23", "48")}, {"pengecoh": ("48/2", "23", "48")},
    {"kunci": "1/2", "pengecoh": ("50%", "2/3", "3/4")},
    {"pengecoh": ("12", "12,0", "48")}, {"pengecoh": ["12", "23", "48"]},
    {"kebijakan": "asing"}, {"kebijakan": "tertanam-lima-v1"},
    {"seed": True}, {"identitas": ""}, {"jenis": "asing"},
])
def test_pembentukan_menolak_kandidat_tidak_sah_tanpa_fallback(ubah):
    with pytest.raises(ValueError):
        contoh(**ubah)


@pytest.mark.parametrize("a,b,jenis", [
    ("1/2", "0,5", "angka"), ("2/4", "50%", "angka"),
    ("−2", "-2", "angka"), ("27,31", "27, 31", "daftar_bulat"),
    ("1/2, 25%", "0,5, 1/4", "urutan_bilangan"),
    ("1:100", "2:200", "rasio"), ("SENIN", "Senin", "kategori"),
])
def test_kesetaraan_memakai_konteks_bukan_tebakan_koma(a, b, jenis):
    assert nilai_semantis(a, jenis) == nilai_semantis(b, jenis)


def test_daftar_berurutan_dan_skalar_tidak_dicampur():
    assert nilai_semantis("27,31", "angka") != nilai_semantis("27,31", "daftar_bulat")
    assert nilai_semantis("27,31", "daftar_bulat") != nilai_semantis("31,27", "daftar_bulat")
    with pytest.raises(ValueError, match="Jumlah bagian"):
        contoh(jenis="daftar_bulat", kunci="1, 2", pengecoh=("1, 3", "2, 3", "1, 2, 3"))


@pytest.mark.parametrize("teks,jenis", [
    ("1/0", "angka"), ("1 cm", "angka"), ("nan", "angka"),
    ("14.70", "jam"), ("24.00", "jam"), ("1:0", "rasio"),
    ("-1 jam 2 menit", "durasi"), ("1 jam 60 menit", "durasi"),
    ("3", "daftar_bulat"), ("1,,2", "daftar_bulat"), ("9", "kategori"),
])
def test_nilai_tidak_dikenal_gagal_tertutup(teks, jenis):
    with pytest.raises(ValueError):
        nilai_semantis(teks, jenis)


def test_kunci_tidak_ada_ditolak_oleh_validator():
    with pytest.raises(ValueError, match="tepat satu"):
        validasi_kebenaran(contoh(), "999", "angka")


def test_opsi_tertanam_tidak_mengacak_label_asal():
    teks = tuple(f"Pernyataan {i}" for i in range(5))
    p = pilihan_tertanam(sesi_soal_id=7, fingerprint_pertanyaan="a" * 64,
                         teks_opsi=teks, kunci="D")
    assert tuple(o.label for o in p.opsi) == tuple("ABCDE")
    assert tuple(o.nilai for o in p.opsi) == tuple("ABCDE")
    assert tuple(o.teks for o in p.opsi) == teks
    # Kunci tidak memengaruhi payload publik maupun sidiknya.
    q = pilihan_tertanam(sesi_soal_id=7, fingerprint_pertanyaan="a" * 64,
                         teks_opsi=teks, kunci="A")
    assert p == q
    assert fingerprint(p) == fingerprint(q)
    with pytest.raises(ValueError):
        pilihan_tertanam(sesi_soal_id=7, fingerprint_pertanyaan="a" * 64,
                         teks_opsi=teks[:4], kunci="D")


@pytest.mark.parametrize("kolom,nilai", [
    ("versi", 2), ("versi", True), ("sesi_soal_id", True),
    ("sesi_soal_id", 0), ("fingerprint_pertanyaan", "a"),
    ("kebijakan", "dua-v1"), ("kebijakan", []), ("opsi", []),
])
def test_objek_kontrak_menolak_tipe_dan_versi_asing(kolom, nilai):
    with pytest.raises(ValueError):
        replace(contoh(), **{kolom: nilai})


@pytest.mark.parametrize("perubahan", [
    {"id": "kunci"}, {"label": "Z"}, {"nilai": ""}, {"teks": ""},
    {"nilai": " 24"}, {"teks": "x\x00y"}, {"teks": "x" * 4001},
])
def test_isi_opsi_tidak_sah_ditolak(perubahan):
    p = contoh()
    with pytest.raises(ValueError):
        replace(p, opsi=(replace(p.opsi[0], **perubahan), *p.opsi[1:]))


def test_snapshot_mengikat_butir_pertanyaan_dan_isi():
    p = contoh()
    for sid, sidik in [(8, "a" * 64), (7, "b" * 64), (True, "a" * 64)]:
        with pytest.raises(ValueError, match="tidak cocok"):
            deserialisasi(serialisasi(p), fingerprint(p), sesi_soal_id=sid,
                          fingerprint_pertanyaan=sidik)
    with pytest.raises(ValueError, match="berubah"):
        deserialisasi(serialisasi(p).replace('"24"', '"25"'), fingerprint(p),
                      sesi_soal_id=7, fingerprint_pertanyaan="a" * 64)


@pytest.mark.parametrize("rusak", [
    lambda d: dict(d, kunci="24"),
    lambda d: dict(d, opsi=[dict(d["opsi"][0], benar=True), *d["opsi"][1:]]),
    lambda d: dict(d, opsi=[dict(d["opsi"][0], malrule_id="rahasia"), *d["opsi"][1:]]),
    lambda d: dict(d, opsi={}), lambda d: dict(d, versi=99), lambda d: [],
])
def test_reader_tolak_field_rahasia_meski_sidik_dihitung_ulang(rusak):
    t = json.dumps(rusak(json.loads(serialisasi(contoh()))), sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError):
        deserialisasi(t, hashlib.sha256(t.encode()).hexdigest(), sesi_soal_id=7,
                      fingerprint_pertanyaan="a" * 64)


@pytest.mark.parametrize("teks", ["{", '{"versi":1,"versi":1}', 'NaN', '[' * 2000,
                                    '"' + 'x' * 32001 + '"'])
def test_reader_tolak_json_rusak_duplikat_dan_besar(teks):
    with pytest.raises(ValueError):
        deserialisasi(teks, "a" * 64, sesi_soal_id=7, fingerprint_pertanyaan="a" * 64)


def test_resolver_kosong_dan_id_asing():
    p = contoh()
    assert p.nilai_untuk("") == ""
    for o in p.opsi:
        assert p.nilai_untuk(o.id) == o.nilai
    for asing in ("A", "opsi_5", "24", None):
        with pytest.raises(ValueError):
            p.nilai_untuk(asing)


def test_determinisme_lintas_hashseed_dan_tidak_mengubah_rng_global():
    import random
    sebelum = random.getstate()
    contoh()
    assert random.getstate() == sebelum
    skrip = '''from multiple_choice import buat_pilihan
from choice_contract import serialisasi
p=buat_pilihan(sesi_soal_id=7,fingerprint_pertanyaan="a"*64,kebijakan="empat-v1",jenis="angka",kunci="24",pengecoh=("12","23","48"),seed=35,identitas="uji")
print(serialisasi(p))
'''
    hasil = []
    for seed in ("1", "97"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        hasil.append(subprocess.check_output([sys.executable, "-B", "-c", skrip],
                     cwd=Path(__file__).resolve().parents[1], env=env))
    assert hasil[0] == hasil[1]
    posisi = {next(i for i, o in enumerate(contoh(seed=s).opsi) if o.nilai == "24") for s in range(50)}
    assert posisi == {0, 1, 2, 3}


def test_reader_publik_tidak_mengimpor_generator_atau_diagnosis():
    skrip = '''import sys
import choice_contract
assert not {"templates", "generator", "diagnosis", "multiple_choice"} & set(sys.modules)
'''
    subprocess.run([sys.executable, "-B", "-c", skrip], check=True,
                   cwd=Path(__file__).resolve().parents[1])

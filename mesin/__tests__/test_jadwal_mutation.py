"""Mutation guard jadwal Paket Belajar pada SALINAN repo terisolasi (bukan workspace).

Menonaktifkan satu guard lalu menjalankan tes yang menjaganya: hasil harus MERAH karena asersi. Kontrol:
tanpa mutasi, tes yang sama hijau di salinan yang sama. Guard kuota berlapis (store + trigger) dimutasi
bersama supaya tidak tertutup lapis lain.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AKAR = Path(__file__).resolve().parents[2]
S = "mesin/__tests__/test_jadwal_store.py::"
STORE = "mesin/jadwal_store.py"
SKEMA = "mesin/schema_jadwal.py"

KASUS = (
    ("kuota-store-dan-trigger",
     ((STORE, '''            if _isi_kelompok(kon, kid) >= kelompok["kuota"]:
                raise jd.JadwalPenuh()
''', ""),
      (SKEMA, '''DDL += _trigger(
    "jadwal_penempatan_kuota", "jadwal_penempatan", "INSERT",
    "NEW.kelompok_id IS NOT NULL AND (SELECT COUNT(*) FROM jadwal_penempatan "
    "WHERE kelompok_id=NEW.kelompok_id) >= (SELECT kuota FROM jadwal_kelompok WHERE id=NEW.kelompok_id)",
    "kelompok penuh")
''', ""),),
     (S + "test_tempatkan_mini_sampai_kuota_penuh",)),
    ("anak-trigger",
     ((SKEMA, '''DDL += _trigger(
    "jadwal_penempatan_anak", "jadwal_penempatan", "INSERT",
    "EXISTS(SELECT 1 FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
    "JOIN kelas_order n ON n.id=NEW.order_id WHERE o.siswa_id=n.siswa_id)",
    "anak sudah punya penempatan")
''', ""),),
     (S + "test_anak_tidak_bisa_punya_dua_penempatan",)),
    ("hanya-order-aktif",
     ((STORE, '''    if ks.status_dari(order, ks.fakta_order(kon, order_id), kini) != dasar.STATUS_AKTIF:
''', "    if False:\n"),),
     (S + "test_hanya_order_aktif_yang_bisa_ditempatkan",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("jadwal-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path, sasaran):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *sasaran, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=240)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    sasaran = sorted({t for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_jadwal_menangkap_mutasi(salinan, nama, suntingan, sasaran):
    asli = {}
    try:
        for rel, lama, baru in suntingan:
            berkas = salinan / rel
            sumber = asli.setdefault(rel, berkas.read_text(encoding="utf-8"))
            terkini = berkas.read_text(encoding="utf-8")
            assert terkini.count(lama) == 1, "%s: pola mutasi harus unik di %s" % (nama, rel)
            berkas.write_text(terkini.replace(lama, baru), encoding="utf-8")
            assert sumber != berkas.read_text(encoding="utf-8")
        hasil = _jalankan(salinan, sasaran)
    finally:
        for rel, sumber in asli.items():
            (salinan / rel).write_text(sumber, encoding="utf-8")
    keluaran = hasil.stdout + hasil.stderr
    assert hasil.returncode == 1, keluaran
    assert re.search(r"\b\d+ failed", keluaran), keluaran
    assert not re.search(r"\b\d+ error", keluaran), keluaran

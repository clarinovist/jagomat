"""Mutation guard harga aktif kelas pada SALINAN repo terisolasi (bukan workspace).

Pola sama dengan test_harga_mutation.py: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU
di salinan yang sama. Salinan tidak memuat .venv, cadangan, *.db, atau *.json.
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
T = "mesin/__tests__/test_kelas_harga_aktif.py::"
RINCIAN, STORE = "mesin/kelas_rincian.py", "mesin/kelas_store.py"
KATALOG = "mesin/paket_belajar_katalog.py"
BACA_HARGA = "    harga_paket = harga.harga_aktif(kon, kode_paket)\n"
KARTU_HARGA = "        paket_kartu = katalog.paket_dengan_harga(paket.kode, rincian.harga_dasar)\n"
TAGIHAN_TERSIMPAN = 'ks.rincian_dari_baris(order["paket"], tagihan), tagihan["kode_unik"],'
TAGIHAN_HARGA_AKTIF = ('katalog.hitung_rincian(order["paket"], deposit_aktif=False, '
                       'harga_paket=harga_mutasi.harga_aktif(kon, order["paket"])), tagihan["kode_unik"],')

KASUS = (
    ("I-rincian-abaikan-harga-aktif",
     ((RINCIAN, BACA_HARGA, "    harga_paket = None\n"),),
     (T + "test_kartu_menampilkan_harga_aktif_dan_rincian_seragam",
      T + "test_tagihan_baru_memakai_harga_mini_aktif")),
    ("II-kartu-abaikan-harga-aktif",
     ((STORE, KARTU_HARGA, "        paket_kartu = paket\n"),),
     (T + "test_kartu_menampilkan_harga_aktif_dan_rincian_seragam",)),
    ("III-halaman-tagihan-pakai-harga-aktif",
     ((STORE, "import kelas_status as ks\n", "import kelas_status as ks\nimport harga as harga_mutasi\n"),
      (STORE, TAGIHAN_TERSIMPAN, TAGIHAN_HARGA_AKTIF)),
     (T + "test_halaman_tagihan_menampilkan_harga_tersimpan",
      T + "test_harga_diubah_setelah_tagihan_tidak_mengubah_tagihan_lama")),
    ("IV-galat-skema-harga-ditelan",
     ((RINCIAN, BACA_HARGA, "    try:\n        harga_paket = harga.harga_aktif(kon, kode_paket)\n"
                            "    except ValueError:\n        harga_paket = None\n"),),
     (T + "test_buat_tagihan_gagal_tertutup_saat_skema_harga_rusak",
      T + "test_kartu_gagal_tertutup_saat_skema_harga_rusak")),
    ("V-harga-paket-tak-valid-diterima",
     ((KATALOG, "    if type(nilai) is not int or nilai <= 0:\n", "    if False:\n"),),
     (T + "test_hitung_rincian_menolak_harga_paket_bukan_bilangan_bulat_positif",)),
    ("VI-nominal-nol-setelah-deposit-diterima",
     ((KATALOG, "    if nominal <= 0:\n", "    if False:\n"),),
     (T + "test_hitung_rincian_menolak_nominal_tidak_positif_setelah_deposit",)),
)
KONTROL = tuple(sorted({t for _, _, ts in KASUS for t in ts}))


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("kelas-harga-mutasi") / "repo"
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
    hasil = _jalankan(salinan, KONTROL)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_harga_kelas_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

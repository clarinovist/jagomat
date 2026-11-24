"""Mutation guard penghapusan laporan orang tua pada keluarga: SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya; hasil harus MERAH karena asersi
(bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di salinan yang sama. Pola mutasi harus unik.
Mutasi yang setara secara perilaku (urutan tautan/laporan dibalik, DELETE tautan eksplisit dilepas) TIDAK dimasukkan:
FK komposit `tautan_laporan` -> `laporan_ortu` ON DELETE CASCADE (foreign_keys ON di `database.buka`) membuat
keduanya tak berbeda hasil; DELETE eksplisit dipertahankan sebagai pertahanan berlapis. Guard `if not siswa_ids` juga
setara (SQLite menerima `IN ()` = tanpa baris).
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
FD = "mesin/family_deletion.py"
U = "mesin/__tests__/test_laporan_ortu_family_deletion.py::"
BUNDLE = U + "test_bundle_hasil_menghapus_laporan_dan_tautan_anak_target_saja"
RUTE = U + "test_tautan_lama_setelah_penghapusan_dijawab_sama_dengan_token_tak_dikenal"
UNIT = U + "test_hapus_laporan_ortu_target_saja_dan_tanpa_siswa_tidak_error"
TANPA_TABEL = U + "test_hapus_laporan_ortu_tanpa_tabel_dilewati_per_tabel"
KASUS = (
    ("a-panggilan-dilepas",
     ((FD, "        _hapus_laporan_ortu(kon, siswa_ids)\n", "        pass\n"),),
     (BUNDLE, RUTE)),
    ("b-filter-siswa-laporan-dilepas",
     ((FD, 'kon.execute("DELETE FROM laporan_ortu WHERE siswa_id IN (%s)" % q, siswa_ids)',
       'kon.execute("DELETE FROM laporan_ortu")'),),
     (BUNDLE, UNIT)),
    ("c-filter-siswa-tautan-dilepas",
     ((FD, 'kon.execute("DELETE FROM tautan_laporan WHERE siswa_id IN (%s)" % q, siswa_ids)',
       'kon.execute("DELETE FROM tautan_laporan")'),),
     (BUNDLE, UNIT)),
    ("d-cek-tabel-tautan-dilepas",
     ((FD, '    if _tabel(kon, "tautan_laporan"):\n', "    if True:\n"),),
     (TANPA_TABEL, U + "test_bundle_hasil_tanpa_tabel_laporan_ortu_tetap_berhasil")),
    ("e-cek-tabel-laporan-dilepas",
     ((FD, '    if _tabel(kon, "laporan_ortu"):\n', "    if True:\n"),),
     (TANPA_TABEL, U + "test_bundle_hasil_tanpa_tabel_laporan_ortu_tetap_berhasil")),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("laporan-ortu-hapus-mutasi") / "repo"
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
def test_guard_hapus_laporan_ortu_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

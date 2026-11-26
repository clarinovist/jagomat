"""Mutation guard pemicu penerbitan otomatis Peta (`peta_otomatis`) di titik lunas dan halaman orang tua.

Pada SALINAN repo terisolasi, tiap kasus menonaktifkan satu pemicu atau guard lalu menjalankan tes yang menjaganya; hasil
harus MERAH karena asersi (bukan import atau fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus HIJAU di salinan
yang sama. Pola mutasi harus unik di berkasnya (count == 1). Salinan tidak memuat `.venv`, cadangan, `*.db`, atau
`*.json`. Mutasi 5a hanya tertangkap oleh (d): guard status di kumpulkan membuat akun lain tidak pernah sampai ke pemicu,
jadi (e) baru tertangkap oleh 5b (guard status dan akun dilepas bersama). Tiap kasus = satu param (`-k` bisa dipakai).
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
T = "mesin/__tests__/test_peta_otomatis_hook.py::"
ODATA = "mesin/orang_tua_data.py"
VH = "mesin/admin_verifikasi_http.py"
ALUR = "mesin/pesanan_alur.py"
MODUL = "mesin/peta_otomatis.py"
PEMICU_TRANSFER = "    if setuju:\n        peta_otomatis.setelah_lunas(order_id)  # ledger sudah commit; galat pemicu tidak menggagalkan persetujuan\n"
PEMICU_QRIS = "    _setelah_lunas(order_id, hasil)\n"
PASTIKAN = "    peta_otomatis.pastikan_untuk_siswa(kon, id_akun, siswa_id, sekarang)\n"
GUARD_KUMPULKAN = "    if status != pesanan_dasar.STATUS_SUDAH_DIBAYAR:\n        return\n"
COMMIT = "    _commit_bila_menggantung(kon)\n"
GUARD_INTI_STATUS = '    if order["status"] != d.STATUS_SUDAH_DIBAYAR:\n        return None\n'
GUARD_INTI_LUNAS = ('    return (purna_ringkas["terpasang"] is True and purna_ringkas["lunas"] is True\n'
                    '            and purna_ringkas["direfund"] is False and purna_ringkas["ditahan"] is False)\n')
PENANDA = '"oleh_sistem": peta_otomatis.oleh_sistem(kon, siswa_id)}'
KASUS = (
    ("1-pemicu-transfer-dilepas", ((VH, PEMICU_TRANSFER, ""),),
     (T + "test_transfer_disetujui_menerbitkan_laporan_oleh_sistem_dan_purna",
      T + "test_pemicu_transfer_gagal_tidak_menggagalkan_persetujuan")),
    ("2-pemicu-qris-dilepas", ((ALUR, PEMICU_QRIS, ""),),
     (T + "test_status_qris_lunas_menerbitkan_laporan_oleh_sistem",
      T + "test_pemicu_qris_gagal_tidak_menggagalkan_pembayaran")),
    ("3-pastikan-kumpulkan-dilepas", ((ODATA, PASTIKAN, ""),),
     (T + "test_kumpulkan_order_lunas_menerbitkan_laporan_sekali_dan_idempoten",
      T + "test_penilaian_cek_menggantung_tetap_tersimpan_setelah_kumpulkan")),
    ("4-guard-lunas-kumpulkan-dan-inti-dilepas",
     ((ODATA, GUARD_KUMPULKAN + COMMIT, COMMIT),
      (MODUL, GUARD_INTI_STATUS, ""),
      (MODUL, GUARD_INTI_LUNAS, '    return (purna_ringkas["terpasang"] is True)\n')),
     (T + "test_order_belum_lunas_tidak_menerbitkan_laporan",)),
    ("4a-guard-status-kumpulkan-saja-dilepas", ((ODATA, GUARD_KUMPULKAN + COMMIT, COMMIT),),
     (T + "test_order_belum_lunas_tidak_menerbitkan_laporan",)),
    ("5a-akun-pastikan-ditukar", ((ODATA, PASTIKAN, '    peta_otomatis.pastikan_untuk_siswa(kon, "akun_" + "0" * 32, siswa_id, sekarang)\n'),),
     (T + "test_kumpulkan_order_lunas_menerbitkan_laporan_sekali_dan_idempoten",)),
    ("5b-akun-pastikan-kosong-dan-guard-status-dilepas",
     ((ODATA, GUARD_KUMPULKAN + COMMIT, COMMIT),
      (ODATA, PASTIKAN, "    peta_otomatis.pastikan_untuk_siswa(kon, None, siswa_id, sekarang)\n")),
     (T + "test_kumpulkan_akun_atau_anak_lain_tanpa_efek",)),
    ("6-commit-sebelum-pastikan-dilepas", ((ODATA, COMMIT + PASTIKAN, PASTIKAN),),
     (T + "test_penilaian_cek_menggantung_tetap_tersimpan_setelah_kumpulkan",)),
    ("7-penanda-sistem-dipaksa-benar", ((ODATA, PENANDA, '"oleh_sistem": True}'),),
     (T + "test_laporan_guru_terbit_tetap_dan_penanda_sistem_salah",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("peta-otomatis-hook-mutasi") / "repo"
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
def test_guard_pemicu_penerbitan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

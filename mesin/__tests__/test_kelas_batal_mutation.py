"""Mutation guard batal/pulih/unggah tagihan kelas pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu penjaga di salinan lalu menjalankan tes yang menjaganya: hasil harus MERAH karena asersi
(bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus HIJAU di salinan yang sama.
Pola mutasi harus unik di berkasnya. Salinan tidak memuat .venv, cadangan, *.db, atau *.json.
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
B = "mesin/__tests__/test_kelas_batal.py::"
U = "mesin/__tests__/test_kelas_unggah_order.py::"
S = "mesin/__tests__/test_schema_tagihan_catatan.py::"
K = "mesin/__tests__/test_kelas_batal_konsumen.py::"
KELAS_BATAL = "mesin/kelas_batal.py"
KELAS_RINCIAN = "mesin/kelas_rincian.py"
KELAS_STATUS = "mesin/kelas_status.py"
ADMIN_SEMUA = "mesin/admin_pembayaran_semua.py"
SKEMA = "mesin/schema_tagihan_catatan.py"
TANPA_TAGIHAN_AKUN = "test_paket_tanpa_tagihan_terbuka_identik_dengan_milik_akun_lain_tanpa_catatan"
DUA_AKUN = "test_dua_akun_memakai_kode_paket_sama_hanya_tagihan_pemiliknya_yang_dibatalkan"
ANAK_LAIN = "test_anak_lain_pada_akun_sama_identik_dengan_tanpa_tagihan"
UNGGAH_AKUN = "test_akun_lain_identik_dengan_tanpa_tagihan_tanpa_tulis"
UNGGAH_ANAK = "test_anak_lain_pada_akun_sama_identik_dengan_tanpa_tagihan"
UNGGAH_DIBATALKAN = "test_tagihan_dibatalkan_menolak_bukti"

# Satu titik pencarian tagihan terbuka (`kelas_status.order_terbuka_siswa`) dipakai batal DAN unggah; mutasinya dipasang di sana.
KASUS = (
    ("K1-akun-pencarian-tagihan-dilepas",
     ((KELAS_STATUS, 'WHERE akun_id=? AND siswa_id=? "', "WHERE ?<>'' AND siswa_id=? \""),),
     (B + TANPA_TAGIHAN_AKUN, B + DUA_AKUN, U + UNGGAH_AKUN)),
    ("K2-anak-pencarian-tagihan-dilepas",
     ((KELAS_STATUS, 'WHERE akun_id=? AND siswa_id=? "', 'WHERE akun_id=? AND ?>0 "'),),
     (B + ANAK_LAIN, U + UNGGAH_ANAK)),
    ("B3-trigger-batal-saat-ada-bukti-dilepas",
     ((SKEMA, '_BATAL_ADA_BUKTI = "EXISTS(SELECT 1 FROM kelas_bukti WHERE order_id=NEW.order_id)"',
       '_BATAL_ADA_BUKTI = "0"'),),
     (S + "test_batal_ditolak_bila_tagihan_sudah_punya_bukti",)),
    ("B4-deposit-pulih-tanpa-cek-deposit-aktif",
     ((KELAS_RINCIAN, "    aktif = deposit_aktif(kon, akun_id, siswa_id, kini) == deposit_order", "    aktif = True"),),
     (B + "test_deposit_sudah_dipakai_tagihan_lain_dan_lunas_menolak_pulih_tanpa_tulis",)),
    ("B5-deposit-pulih-tanpa-cek-dipegang-lain",
     ((KELAS_RINCIAN, "    return aktif and not _deposit_dipegang_lain(kon, akun_id, siswa_id, kode_paket, deposit_order, kini)",
       "    return aktif"),),
     (B + "test_deposit_masih_dipegang_tagihan_terbuka_lain_menolak_pulih",)),
    ("B6-deposit-pulih-tanpa-penjaga-di-pemanggil",
     ((KELAS_BATAL, "    if deposit is not None and not kelas_rincian.deposit_masih_tersedia(",
       "    if False and not kelas_rincian.deposit_masih_tersedia("),),
     (B + "test_deposit_sudah_dipakai_tagihan_lain_dan_lunas_menolak_pulih_tanpa_tulis",
      B + "test_deposit_masih_dipegang_tagihan_terbuka_lain_menolak_pulih")),
    ("C1-dibatalkan-dihitung-terbuka",
     ((KELAS_STATUS, "        if status in k.STATUS_TERBUKA:\n            yield order, fakta, status",
       "        if status in k.STATUS_TERBUKA + (k.STATUS_DIBATALKAN,):\n            yield order, fakta, status"),),
     (K + "test_pengingat_belum_dibayar_mengabaikan_tagihan_batal_dan_menampilkan_yang_terbuka",
      K + "test_pengingat_kosong_bila_satu_satunya_tagihan_dibatalkan",
      U + UNGGAH_DIBATALKAN)),
    ("C2-kelompok-ditolak-tanpa-dibatalkan",
     ((ADMIN_SEMUA, '    "ditolak": (S_DITOLAK, S_KEDALUWARSA, S_DIBATALKAN),', '    "ditolak": (S_DITOLAK, S_KEDALUWARSA),'),),
     (K + "test_semua_pembayaran_menghitung_tagihan_batal_di_kelompok_ditolak_bukan_belum_bayar",)),
)
KONTROL = tuple(sorted({t for _, _, ts in KASUS for t in ts}))


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("batal-mutasi") / "repo"
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
def test_guard_batal_tagihan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

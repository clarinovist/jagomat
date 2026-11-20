"""Mutation guard tiga perbaikan LOW tinjauan keamanan 20 Nov (refund + sandi ulang) pada SALINAN terisolasi.

L1 refund lintas tabel (`pesanan_refund_aturan`), L2 status turunan ditegakkan server, L3 pembatas sandi ulang
(`admin_http._reauth`). Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes penjaganya: hasil
harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di salinan
yang sama. Pola mutasi harus unik di berkasnya. Pola salinan sama dengan test_admin_pesanan_mutation.py.
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
A = "mesin/__tests__/test_pesanan_refund_aturan.py::"
R = "mesin/__tests__/test_admin_reauth_pembatas.py::"
ATURAN, TRANSFER, ADMIN = "mesin/pesanan_refund_aturan.py", "mesin/pesanan_transfer.py", "mesin/admin_http.py"
BLOKIR = ("    if laju_masuk.sedang_diblokir(principal.id_akun, RUANG_REAUTH, sekarang):\n"
          "        return False\n")
TABEL_KEDUA = '    tabel = ("pesanan_refund", "transfer_refund") if tb.terpasang(kon) else ("pesanan_refund",)\n'
STATUS = "    if st.status_dari_db(kon, st.dict_order(baris), kini) not in d.STATUS_BISA_REFUND:\n"

KASUS = (
    ("L1-cek-lintas-tabel-hanya-satu-tabel",
     ((ATURAN, TABEL_KEDUA, '    tabel = ("pesanan_refund",)\n'),),
     (A + "test_replay_identik_setelah_receipt_menyusul_sudah_ada_tanpa_baris_di_tabel_lain",)),
    ("L1-jalur-transfer-tanpa-cek-lintas-tabel",
     ((TRANSFER, "    if ra.refund_sudah_ada(kon, operasi_id, isi):\n        return False\n", ""),),
     (A + "test_refund_jalur_penyedia_lalu_catat_transfer_langsung_ditolak_tanpa_baris_ganda",)),
    ("L1-konflik-isi-beda-dilewati",
     ((ATURAN, "    if any(b[0] != operasi_id or b[1:] != isi for b in ada):\n", "    if False:\n"),),
     (A + "test_isi_beda_setelah_receipt_menyusul_konflik_tanpa_baris_di_tabel_lain",)),
    ("L2-cek-status-server-dinonaktifkan",
     ((ATURAN, STATUS, "    if False:\n"),),
     (A + "test_periksa_layak_refund_menolak_status_di_luar_allowlist",
      A + "test_periksa_layak_refund_menolak_direfund_dan_menerima_dua_status_layak")),
    ("L2-allowlist-status-dilonggarkan-ke-semua-status",
     ((ATURAN, STATUS, STATUS.replace("d.STATUS_BISA_REFUND", "d.STATUS_TURUNAN")),),
     (A + "test_periksa_layak_refund_menolak_status_di_luar_allowlist",)),
    ("L3-pembatas-dilewati",
     ((ADMIN, BLOKIR, ""),),
     (R + "test_percobaan_keenam_ditolak_walau_sandi_benar_dan_pbkdf2_tidak_dijalankan",
      R + "test_http_refund_ditolak_403_tanpa_efek_setelah_lima_sandi_ulang_gagal")),
    ("L3-kegagalan-tidak-dicatat",
     ((ADMIN, "        laju_masuk.catat_gagal(principal.id_akun, RUANG_REAUTH, sekarang)\n", "        pass\n"),),
     (R + "test_percobaan_keenam_ditolak_walau_sandi_benar_dan_pbkdf2_tidak_dijalankan",)),
    ("L3-sukses-tidak-mereset-hitungan",
     ((ADMIN, "        laju_masuk.catat_berhasil(principal.id_akun, RUANG_REAUTH)\n", "        pass\n"),),
     (R + "test_sukses_mengosongkan_hitungan_gagal",)),
    ("L3-kunci-global-bukan-per-akun",
     ((ADMIN, "laju_masuk.sedang_diblokir(principal.id_akun, RUANG_REAUTH, sekarang)",
       "laju_masuk.sedang_diblokir(RUANG_REAUTH, RUANG_REAUTH, sekarang)"),
      (ADMIN, "laju_masuk.catat_gagal(principal.id_akun, RUANG_REAUTH, sekarang)",
       "laju_masuk.catat_gagal(RUANG_REAUTH, RUANG_REAUTH, sekarang)")),
     (R + "test_akun_admin_lain_tidak_terpengaruh",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("admin-pesanan-keamanan-mutasi") / "repo"
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
    sasaran = sorted({t.split("::")[0] for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_keamanan_pesanan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

"""Mutation guard aturan catatan Guru laporan Peta pada SALINAN repo terisolasi (bukan workspace).

Pola sama dengan `test_peta_laporan_guru_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan
tes yang menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama
HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya (count == 1). Tiap kasus = satu param (`-k`).
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
U = "mesin/__tests__/test_peta_laporan_catatan.py::"
W = "mesin/__tests__/test_peta_laporan_catatan_http.py::"
TOKO = "mesin/peta_laporan_store.py"
HTTP = "mesin/peta_laporan_guru_http.py"
HAL = "mesin/peta_laporan_guru_pages.py"
UNIT_KONTAK = (U + "test_kontak_ditolak_dengan_kode_kontak", U + "test_prioritas_kode_panjang_lalu_kontrol_lalu_kontak_lalu_istilah")
KASUS = (
    ("a-kategori-kontak-dilepas",
     ((TOKO, "    if _POLA_DIGIT_KONTAK.search(bentuk) or _POLA_TEL.search(bentuk) or any(p in bentuk for p in _PENANDA_KONTAK):\n        return CATATAN_KONTAK\n",
       "    if False:\n        return CATATAN_KONTAK\n"),),
     UNIT_KONTAK + (W + "test_catatan_berisi_kontak_atau_istilah_internal_ditolak_400_pesan_tepat_tanpa_efek_dan_teks_dipertahankan",)),
    ("b-digit-berurutan-dilepas",
     ((TOKO, "_POLA_DIGIT_KONTAK.search(bentuk) or ", ""),),
     (U + "test_kontak_ditolak_dengan_kode_kontak", U + "test_batas_sembilan_digit_tepat")),
    ("c-batas-digit-jadi-sepuluh",
     ((TOKO, "_MIN_DIGIT_KONTAK = 9   #", "_MIN_DIGIT_KONTAK = 10   #"),),
     (U + "test_batas_sembilan_digit_tepat", U + "test_kontak_ditolak_dengan_kode_kontak")),
    ("d-digit-diselingi-pemisah-dilepas",
     ((TOKO, 'r"\\d(?:[\\s.\\-', 'r"\\d(?:[\\-'),),
     (U + "test_kontak_ditolak_dengan_kode_kontak",)),
    ("e-tel-dilepas",
     ((TOKO, "or _POLA_TEL.search(bentuk) ", ""),),
     (U + "test_kontak_ditolak_dengan_kode_kontak",)),
    ("f-penanda-tautan-dilepas",
     ((TOKO, 'any(p in bentuk for p in _PENANDA_KONTAK)', "False"),),
     (U + "test_kontak_ditolak_dengan_kode_kontak",)),
    ("g-kategori-istilah-internal-dilepas",
     ((TOKO, "    if any(istilah in rapat for istilah in _ISTILAH_INTERNAL):\n", "    if False:\n"),),
     (U + "test_istilah_internal_ditolak_dengan_kode_istilah_internal",
      W + "test_catatan_berisi_kontak_atau_istilah_internal_ditolak_400_pesan_tepat_tanpa_efek_dan_teks_dipertahankan")),
    ("h-spasi-istilah-tidak-dirapatkan",
     ((TOKO, 'rapat = " ".join(bentuk.split())', "rapat = bentuk"),),
     (U + "test_istilah_internal_ditolak_dengan_kode_istilah_internal",)),
    ("i-kategori-kontrol-dilepas",
     ((TOKO, '    if any(unicodedata.category(c) == "Cc" and c not in _KONTROL_BOLEH for c in catatan):\n',
       "    if False:\n"),),
     (U + "test_karakter_kontrol_selain_newline_dan_tab_ditolak", W + "test_pesan_panjang_dan_kontrol_tetap_pesan_lama")),
    ("j-kategori-panjang-dilepas",
     ((TOKO, "    if len(catatan) > BATAS_CATATAN:\n        return CATATAN_PANJANG\n", ""),),
     (U + "test_batas_panjang_2000_boleh_2001_ditolak", W + "test_pesan_panjang_dan_kontrol_tetap_pesan_lama",
      "mesin/__tests__/test_peta_laporan_guru_http.py::test_catatan_2000_karakter_boleh_2001_ditolak_400_tanpa_efek")),
    ("k-normalisasi-nfkc-dilepas",
     ((TOKO, 'unicodedata.normalize("NFKC", tanpa_format).casefold()', "tanpa_format.casefold()"),),
     (U + "test_kontak_ditolak_dengan_kode_kontak", U + "test_istilah_internal_ditolak_dengan_kode_istilah_internal")),
    ("l-karakter-lebar-nol-tidak-dibuang",
     ((TOKO, 'if unicodedata.category(c) != "Cf")', "if True)"),),
     (U + "test_kontak_ditolak_dengan_kode_kontak", U + "test_istilah_internal_ditolak_dengan_kode_istilah_internal")),
    ("m-huruf-besar-tidak-dilipat",
     ((TOKO, 'tanpa_format).casefold()', 'tanpa_format)'),),
     (U + "test_kontak_ditolak_dengan_kode_kontak", U + "test_istilah_internal_ditolak_dengan_kode_istilah_internal")),
    ("n-simpan-catatan-tidak-memakai-periksa",
     ((TOKO, '    kode = periksa_catatan(catatan)\n    if kode is not None:\n        raise ValueError("catatan tidak sah: %s" % kode)\n', ""),),
     (U + "test_simpan_catatan_menolak_catatan_tak_sah_tanpa_mengubah_dan_tanpa_membocorkan_isi",)),
    ("o-store-terbitkan-tidak-memeriksa-ulang",
     ((TOKO, '    if periksa_catatan(laporan["catatan"]) is not None:\n        raise ValueError("catatan tersimpan tidak sah; ubah dulu sebelum terbit")\n', ""),),
     (U + "test_terbitkan_memeriksa_ulang_catatan_lama_dan_tidak_menerbitkan",)),
    ("p-http-catatan-sah-tidak-memakai-periksa",
     ((HTTP, "    kode = toko.periksa_catatan(catatan)\n    return None if kode is None else", "    return None if True else"),),
     (W + "test_catatan_berisi_kontak_atau_istilah_internal_ditolak_400_pesan_tepat_tanpa_efek_dan_teks_dipertahankan",
      W + "test_pesan_panjang_dan_kontrol_tetap_pesan_lama")),
    ("q-http-terbit-tidak-memeriksa-ulang",
     ((HTTP, 'return PESAN_CATATAN_TERSIMPAN if toko.periksa_catatan(laporan["catatan"]) is not None else None', "return None"),),
     (W + "test_terbit_memeriksa_ulang_catatan_tersimpan_lama_409_tanpa_efek_lalu_berhasil_setelah_diperbaiki",)),
    ("r-http-terbit-tidak-memanggil-pemeriksa-draf",
     ((HTTP, "        pesan = _pesan_draf_belum_layak(laporan)\n", "        pesan = None\n"),),
     (W + "test_terbit_memeriksa_ulang_catatan_tersimpan_lama_409_tanpa_efek_lalu_berhasil_setelah_diperbaiki",)),
    ("s-petunjuk-pembaca-catatan-dilepas",
     ((HAL, "        f'<p class=\"sub\">{_e(PETUNJUK_CATATAN)}</p>'\n", ""),),
     (W + "test_petunjuk_siapa_pembaca_catatan_tampil_di_bawah_kolom_catatan",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("peta-catatan-mutasi") / "repo"
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
def test_guard_catatan_guru_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

"""Mutation guard blok Peta Kemampuan di halaman orang tua (D1-3) pada SALINAN repo terisolasi (bukan workspace).

Pola sama dengan `test_orang_tua_mutation.py`: tiap kasus menonaktifkan SATU guard di salinan lalu menjalankan tes
renderer, data, dan HTTP; hasil harus MERAH karena asersi dan tes yang menjaga guard itu HARUS ada di daftar gagal
(bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di salinan yang sama. Pola mutasi harus unik
di berkasnya. Salinan tidak memuat `.venv`, cadangan, `*.db`, atau `*.json`.
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
BERKAS_TES = tuple("mesin/__tests__/test_peta_laporan_ortu_%s.py" % nama for nama in ("pages", "data", "http"))
P = "test_peta_laporan_ortu_pages.py::"
D = "test_peta_laporan_ortu_data.py::"
H = "test_peta_laporan_ortu_http.py::"
HALAMAN, DATA, STORE = "mesin/peta_laporan_ortu_pages.py", "mesin/orang_tua_data.py", "mesin/peta_laporan_store.py"
ORTU = "mesin/orang_tua_pages.py"
_SQL_TERBIT = 'WHERE siswa_id = ? AND diterbitkan IS NOT NULL",'
_SELECT = '"SELECT isi, catatan, diterbitkan FROM peta_laporan ' + _SQL_TERBIT
_KEMBALI = 'return {"isi": isi, "catatan": baris[1], "diterbitkan": baris[2]}'
_PAKSA_LUNAS = "peta=peta_terbit(kon, siswa_id, pesanan_dasar.STATUS_SUDAH_DIBAYAR),"

KASUS = (
    ("M1-syarat-terbit-dilucuti",
     ((STORE, _SQL_TERBIT, 'WHERE siswa_id = ?",'),),
     (D + "test_draf_tidak_mengisi_peta_walau_sudah_dibayar", H + "test_draf_tidak_tampil_walau_lunas")),
    ("M2-syarat-sudah-dibayar-dilucuti",
     ((DATA, "    if status != pesanan_dasar.STATUS_SUDAH_DIBAYAR:\n        return None\n    try:\n        return peta_laporan_store",
       "    if False:\n        return None\n    try:\n        return peta_laporan_store"),),
     (D + "test_status_selain_sudah_dibayar_tidak_membaca_laporan_sama_sekali",
      H + "test_terbit_tetapi_belum_bayar_tidak_tampil", H + "test_terbit_tetapi_direfund_tidak_tampil")),
    ("M2b-kumpulkan-memaksa-lunas",
     ((DATA, "peta=peta_terbit(kon, siswa_id, status),", _PAKSA_LUNAS),),
     (D + "test_kumpulkan_mengisi_field_peta_hanya_saat_lunas", H + "test_terbit_tetapi_belum_bayar_tidak_tampil")),
    ("M3-catatan-tidak-di-escape",
     ((HALAMAN, '"<p>" + _e(p).replace("\\n", "<br>") + "</p>"', '"<p>" + p.replace("\\n", "<br>") + "</p>"'),),
     (P + "test_catatan_html_dan_skrip_tampil_ter_escape",
      H + "test_catatan_html_dan_skrip_tampil_ter_escape_di_halaman")),
    ("M4a-nama-guru-bocor-dari-renderer",
     ((HALAMAN, '_bagian_kepala(isi, peta["diterbitkan"], oleh_sistem)', '_bagian_kepala(isi, peta["diterbitkan"], oleh_sistem) + str(peta.get("guru", ""))'),),
     (P + "test_tanpa_nama_guru_akun_kontak_atau_kata_terlarang_walau_ada_kunci_tambahan",)),
    ("M4b-nama-guru-bocor-dari-store-ke-halaman",
     ((STORE, _SELECT, _SELECT.replace("diterbitkan FROM", "diterbitkan, guru FROM")),
      (STORE, _KEMBALI, _KEMBALI[:-1] + ', "guru": baris[3]}'),
      (HALAMAN, '_bagian_kepala(isi, peta["diterbitkan"], oleh_sistem)', '_bagian_kepala(isi, peta["diterbitkan"], oleh_sistem) + str(peta.get("guru", ""))')),
     (D + "test_terbit_dan_sudah_dibayar_mengisi_peta_tanpa_akun_guru",
      H + "test_tanpa_kata_terlarang_nama_guru_dan_kontak_pada_halaman_dengan_peta")),
    ("M5a-meter-max-salah",
     ((HALAMAN, 'max="{total}" value="{benar}"', 'max="{benar}" value="{benar}"'),),
     (P + "test_penguasaan_per_materi_satu_baris_dan_meter_nilai_maks_benar", P + "test_meter_batas_nilai")),
    ("M5b-meter-value-salah",
     ((HALAMAN, 'max="{total}" value="{benar}"', 'max="{total}" value="{total}"'),),
     (P + "test_penguasaan_per_materi_satu_baris_dan_meter_nilai_maks_benar", H + "test_terbit_dan_lunas_menampilkan_blok_lengkap")),
    ("M6a-galat-isi-rusak-tidak-ditangkap",
     ((DATA, "except (ValueError, sqlite3.Error) as galat:\n        _LOG.warning(\"laporan peta",
       "except sqlite3.Error as galat:\n        _LOG.warning(\"laporan peta"),),
     (D + "test_isi_rusak_menjadi_none_dan_log_tanpa_data", H + "test_isi_rusak_menyembunyikan_blok_tanpa_500_dan_log_tanpa_data")),
    ("M6b-galat-sqlite-tidak-ditangkap",
     ((DATA, "except (ValueError, sqlite3.Error) as galat:\n        _LOG.warning(\"laporan peta",
       "except ValueError as galat:\n        _LOG.warning(\"laporan peta"),),
     (D + "test_tabel_hilang_menjadi_none_bukan_galat", H + "test_tabel_peta_hilang_halaman_tetap_200_tanpa_blok")),
    ("M7-kepemilikan-anak-lain",
     ((DATA, "return peta_laporan_store.terbit_terakhir(kon, siswa_id)", "return peta_laporan_store.terbit_terakhir(kon, siswa_id + 1)"),),
     (D + "test_laporan_anak_lain_tidak_pernah_terbaca", H + "test_anak_keluarga_lain_tidak_pernah_muncul")),
    ("M8-urutan-blok-dipindah",
     ((ORTU, " + peta_laporan_ortu_pages.blok_peta(data.peta)\n        + _blok_harian", "\n        + _blok_harian"),
      (ORTU, "+ _blok_pin(ada_pin, pin_terbuka)", "+ peta_laporan_ortu_pages.blok_peta(data.peta) + _blok_pin(ada_pin, pin_terbuka)")),
     (H + "test_urutan_blok_cek_pesanan_peta_laporan",)),
    ("M9-blok-tidak-dirender",
     ((ORTU, "peta_laporan_ortu_pages.blok_peta(data.peta)", '""'),),
     (H + "test_terbit_dan_lunas_menampilkan_blok_lengkap",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("peta-ortu-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"), PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *BERKAS_TES, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=240)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    hasil = _jalankan(salinan)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,wajib_gagal", KASUS, ids=[k[0] for k in KASUS])
def test_guard_peta_ortu_menangkap_mutasi(salinan, nama, suntingan, wajib_gagal):
    asli = {}
    try:
        for rel, lama, baru in suntingan:
            berkas = salinan / rel
            asli.setdefault(rel, berkas.read_text(encoding="utf-8"))
            terkini = berkas.read_text(encoding="utf-8")
            assert terkini.count(lama) == 1, "%s: pola mutasi harus unik di %s" % (nama, rel)
            berkas.write_text(terkini.replace(lama, baru), encoding="utf-8")
        hasil = _jalankan(salinan)
    finally:
        for rel, sumber in asli.items():
            (salinan / rel).write_text(sumber, encoding="utf-8")
    keluaran = hasil.stdout + hasil.stderr
    assert hasil.returncode == 1, keluaran
    assert re.search(r"\b\d+ failed", keluaran), keluaran
    assert not re.search(r"\b\d+ error", keluaran), keluaran
    gagal = re.findall(r"^FAILED \S*?(test_peta_laporan_ortu_\w+\.py::\w+)", keluaran, flags=re.M)
    for tes in wajib_gagal:
        assert any(g == tes or g.startswith(tes) for g in gagal), "%s: %s tidak merah; gagal=%s" % (nama, tes, gagal)

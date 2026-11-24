"""Mutation guard kartu "Data cek untuk laporan" admin (D1) pada SALINAN repo terisolasi (bukan workspace).

Meniru `test_admin_pesanan_purna_mutation.py`: tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang
menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama harus
HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya (count == 1). Salinan tidak memuat `.venv`, cadangan,
`*.db`, atau `*.json` (tanpa data/sandi nyata).
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
R = "mesin/__tests__/test_cek_ringkasan_admin.py::"
G = "mesin/__tests__/test_admin_pesanan_cek_pages.py::"
H = "mesin/__tests__/test_admin_pesanan_cek_http.py::"
BACA, HALAMAN, ORDER, HTTP = (
    "mesin/cek_ringkasan_admin.py", "mesin/admin_pesanan_cek_pages.py", "mesin/pesanan_admin_order.py",
    "mesin/admin_pesanan_http.py")

KASUS = (
    ("a-kunci-siswa-id-dilepas",
     ((BACA, "      AND siswa_id = :siswa_id\n      AND id_akun", "      AND id_akun"),),
     (R + "test_cek_milik_siswa_lain_tidak_terbaca",)),
    ("b-kunci-id-akun-dilepas",
     ((BACA, "      AND id_akun = :id_akun\"\"\"", '      AND 1 = 1"""'),),
     (R + "test_cek_milik_akun_lain_tidak_terbaca", H + "test_cek_milik_akun_lain_tidak_terbaca")),
    ("c-kunci-cek-id-dilepas",
     ((BACA, "    WHERE id = :cek_id\n      AND siswa_id", "    WHERE siswa_id"),),
     (R + "test_cek_id_salah_untuk_siswa_dan_akun_yang_benar_tidak_terbaca",)),
    ("d-allowlist-kunci-bocor-id-sesi",
     ((BACA, '        "per_materi": per_materi, "bahan": bahan, "hari_tersisa": hari,\n',
       '        "per_materi": per_materi, "bahan": bahan, "hari_tersisa": hari, "sesi_id": row["sesi_id"],\n'),),
     (R + "test_daftar_kunci_hasil_persis", R + "test_cek_belum_selesai_tanpa_skor_dan_tanpa_per_materi")),
    ("e-pembaca-memanggil-diagnosa-murid",
     ((BACA, '    baris = kon.execute(_SQL_PER_SOAL, {"sesi_id": sesi_id}).fetchall()\n',
       '    from reports import diagnosa_murid\n    diagnosa_murid(kon, sesi_id)\n'
       '    baris = kon.execute(_SQL_PER_SOAL, {"sesi_id": sesi_id}).fetchall()\n'),),
     (R + "test_membaca_tidak_menulis_apa_pun", R + "test_jawaban_belum_dinilai_tidak_diberi_diagnosis_oleh_pembaca")),
    ("f1-retensi-salah-hitung",
     ((BACA, "timedelta(days=RETENSI_SELESAI_HARI)", "timedelta(days=RETENSI_SELESAI_HARI + 1)"),),
     (R + "test_hari_tersisa_dari_selesai_dengan_retensi_tiga_puluh_hari",)),
    ("f2-retensi-bisa-negatif",
     ((BACA, "    return max(0, (kedaluwarsa - waktu_baku(sekarang)).days)\n",
       "    return (kedaluwarsa - waktu_baku(sekarang)).days\n"),),
     (R + "test_hari_tersisa_dari_selesai_dengan_retensi_tiga_puluh_hari",)),
    ("f3-retensi-dibulatkan-ke-atas",
     ((BACA, "    return max(0, (kedaluwarsa - waktu_baku(sekarang)).days)\n",
       "    return max(0, -((waktu_baku(sekarang) - kedaluwarsa) // timedelta(days=1)))\n"),),
     (R + "test_hari_tersisa_dari_selesai_dengan_retensi_tiga_puluh_hari",)),
    ("g-gate-lunas-dilepas",
     ((ORDER, "    return status == d.STATUS_SUDAH_DIBAYAR\n", "    return True\n"),),
     (G + "test_gerbang_kartu_cek_hanya_untuk_status_sudah_dibayar",
      H + "test_order_belum_lunas_tanpa_kartu_dan_tanpa_baca_data_cek",
      H + "test_order_perlu_diperiksa_tanpa_kartu_walau_lunas_di_ledger")),
    ("h1-escape-materi-dilepas",
     ((HALAMAN, '(e(b["materi"]), b["benar"]', '(b["materi"], b["benar"]'),),
     (G + "test_semua_nilai_di_escape",)),
    ("h2-escape-hasil-dilepas",
     ((HALAMAN, '    return e("Skor %s dari 100 · %s" % (cek["skor"], cek["kategori"]))\n',
       '    return "Skor %s dari 100 · %s" % (cek["skor"], cek["kategori"])\n'),),
     (G + "test_semua_nilai_di_escape",)),
    ("h3-escape-daftar-topik-dilepas",
     ((HALAMAN, '    return e(", ".join(nama)) if nama else _STRIP\n', '    return ", ".join(nama) if nama else _STRIP\n'),),
     (G + "test_semua_nilai_di_escape",)),
    ("i-koneksi-baca-tanpa-query-only",
     ((HTTP, '            kon.execute("PRAGMA query_only = ON")\n', ""),),
     (H + "test_pembaca_dipanggil_dengan_tiga_kunci_dari_ledger_dan_koneksi_query_only",)),
    ("j-galat-baca-menjadi-500",
     ((HTTP, "_GALAT_CEK = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError, ValueError, LookupError)",
       "_GALAT_CEK = (admin_store.StoreBelumSiap, pesanan.PesananError)"),),
     (H + "test_db_belajar_tak_terbaca_pesan_tanpa_500_traceback_atau_isi_galat",
      H + "test_tabel_cek_hilang_di_db_belajar_nyata_pesan_tanpa_500")),
    ("k-kunci-akun-dari-ledger-tertukar",
     ((ORDER, 'return None if baris is None else (baris["siswa_id"], baris["cek_id"], baris["akun_id"])',
       'return None if baris is None else (baris["cek_id"], baris["siswa_id"], baris["akun_id"])'),),
     (H + "test_kunci_cek_dari_ledger_urutan_siswa_cek_akun_dan_none_bila_order_tak_ada",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("admin-pesanan-cek-mutasi") / "repo"
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
def test_guard_cek_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

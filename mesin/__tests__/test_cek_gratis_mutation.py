"""Mutation guard cek gratis pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya:
hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi,
tes yang sama harus HIJAU di salinan yang sama, sehingga merah memang akibat mutasi.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
TES = "mesin/__tests__/"
T_MULAI = TES + "test_cek_gratis.py::"
T_HASIL = TES + "test_cek_gratis_hasil.py::"
T_SAPU = TES + "test_cek_gratis_sapu.py::"
CEK, SAPU, SKEMA = "mesin/cek_gratis.py", "mesin/cek_gratis_sapu.py", "mesin/schema_cek.py"
SISIP_SETELAH_SESI = '        _simpan_baris(kon, id_akun, siswa_id, sesi_id, waktu)\n    except sqlite3.IntegrityError:'
SISIP_BARU = '        _simpan_baris(kon, id_akun, siswa_id, sesi_id, waktu)\n%s\n    except sqlite3.IntegrityError:'
UNIQUE_LAMA = "siswa_id           INTEGER NOT NULL UNIQUE REFERENCES"

KASUS = (
    ("M1-setuju-dinonaktifkan",
     ((CEK, "    if setuju is not True:", "    if False:"),),
     (T_MULAI + "test_mulai_tanpa_setuju_tidak_menulis_apa_pun",)),
    ("M2-kepemilikan-dilewati",
     ((CEK, "    if not database.siswa_milik(kon, siswa_id, pemilik):", "    if False:"),),
     (T_MULAI + "test_mulai_bukan_pemilik_ditolak_tanpa_efek_samping",)),
    ("M3a-unique-dihilangkan",
     ((SKEMA, UNIQUE_LAMA, "siswa_id           INTEGER NOT NULL REFERENCES"),),
     (T_MULAI + "test_unique_siswa_di_basis_data",)),
    ("M3b-unique-dan-idempotensi-dihilangkan",
     ((SKEMA, UNIQUE_LAMA, "siswa_id           INTEGER NOT NULL REFERENCES"),
      (CEK, "    if ada is not None:\n        return _hasil_mulai(ada, id_akun, baru=False)\n", "")),
     (T_MULAI + "test_mulai_dua_kali_idempoten_tanpa_sesi_kedua",)),
    ("M4-skor-untuk-sesi-belum-selesai",
     ((CEK, "      AND s.selesai IS NOT NULL AND s.dibatalkan IS NULL\n    ORDER BY c.id",
       "      AND s.dibatalkan IS NULL\n    ORDER BY c.id"),),
     (T_HASIL + "test_sesi_belum_selesai_tidak_menghasilkan_skor",)),
    ("M5-sapuan-tanpa-guard-daftar-kosong",
     ((SAPU, "if type(akun_hidup) not in (set, frozenset) or not akun_hidup:",
       "if type(akun_hidup) not in (set, frozenset):"),),
     (T_SAPU + "test_daftar_akun_kosong_atau_tidak_sah_ditolak_tanpa_menghapus",)),
    ("M6-sapuan-ikut-menghapus-turunan",
     ((SAPU, '"UPDATE cek_gratis SET sesi_id = NULL, bahan_dihapus_pada = ? WHERE id = ?",',
       '"DELETE FROM cek_gratis WHERE ? IS NOT NULL AND id = ?",'),),
     (T_SAPU + "test_selesai_lebih_30_hari_menghapus_bahan_tetapi_turunan_tetap",)),
    ("M7a-baca-hasil-tanpa-filter-akun",
     ((CEK, "WHERE id_akun = ? ORDER BY id DESC LIMIT 1", "WHERE ? IS NOT NULL ORDER BY id DESC LIMIT 1"),),
     (T_HASIL + "test_baca_hasil_hanya_milik_akun_pemanggil",)),
    ("M7b-baca-hasil-memuat-kunci",
     ((CEK, '    return {"status": "selesai", "skor": baris["skor"],',
       '    return {"status": "selesai", "kunci": "7", "skor": baris["skor"],'),),
     (T_HASIL + "test_baca_hasil_hanya_kunci_tetap_tanpa_kunci_jawaban_atau_id",)),
    ("M8a-tingkat-siswa-diubah",
     ((CEK, SISIP_SETELAH_SESI,
       SISIP_BARU % '        kon.execute("UPDATE siswa SET tingkat = \'P3\' WHERE id = ?", (siswa_id,))'),),
     (T_MULAI + "test_cek_tidak_mengubah_tingkat_dan_tidak_menulis_bukti_siklus",)),
    ("M8b-tujuan-sesi-bukan-bebas",
     ((CEK, SISIP_SETELAH_SESI,
       SISIP_BARU % '        kon.execute("UPDATE sesi SET tujuan = \'penguatan\' WHERE id = ?", (sesi_id,))'),),
     (T_MULAI + "test_cek_tidak_mengubah_tingkat_dan_tidak_menulis_bukti_siklus",)),
    ("M8c-bukti-siklus-ditulis",
     ((CEK, SISIP_SETELAH_SESI,
       SISIP_BARU % ('        kon.execute("INSERT INTO kejadian_belajar(siswa_id, sesi_id, jenis) '
                     'VALUES (?, ?, \'cek\')", (siswa_id, sesi_id))')),),
     (T_MULAI + "test_cek_tidak_mengubah_tingkat_dan_tidak_menulis_bukti_siklus",)),
    ("M9-postkondisi-15-soal-dilewati",
     ((CEK, "            or jumlah != JUMLAH_SOAL):", "            ):"),),
     (T_MULAI + "test_komposisi_tidak_lengkap_gagal_tanpa_baris",)),
    ("M10-sesi-berbukti-dipaksa-hapus",
     ((SAPU, "    except sqlite3.IntegrityError:\n        kon.execute(\"ROLLBACK TO \" + _SAVEPOINT_SESI)",
       "    except ZeroDivisionError:\n        kon.execute(\"ROLLBACK TO \" + _SAVEPOINT_SESI)"),),
     (T_SAPU + "test_sesi_cek_yang_dikonfirmasi_guru_tidak_dihapus_dan_tidak_menggagalkan_sapuan",)),
    ("M11-sapuan-tanpa-cek-foreign-key",
     ((SAPU, 'if kon.execute("PRAGMA foreign_keys").fetchone()[0] != 1:', "if False:"),),
     (T_SAPU + "test_sapuan_menolak_koneksi_tanpa_foreign_key_aktif",)),
    ("M12-cek-id-akun-lain-untuk-anak-yang-sama",
     ((CEK, '    if baris["id_akun"] != id_akun:', "    if False:"),),
     (T_MULAI + "test_mulai_id_akun_lain_untuk_anak_yang_sudah_punya_cek_ditolak",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("cek-mutasi") / "repo"
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    return akar


def _jalankan(akar: Path, sasaran):
    env = dict(os.environ, PYTHONPATH=str(akar / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *sasaran, "-q", "-W", "error", "-p", "no:cacheprovider"],
        cwd=akar, env=env, text=True, capture_output=True, timeout=180)


def test_kontrol_tanpa_mutasi_hijau_di_salinan(salinan):
    sasaran = sorted({t.split("::")[0] for _, _, ts in KASUS for t in ts})
    hasil = _jalankan(salinan, sasaran)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_cek_gratis_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

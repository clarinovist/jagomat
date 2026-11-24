"""Mutation guard laporan Peta untuk orang tua (D1-1: skema, store, snapshot, hapus keluarga, probe) pada SALINAN repo.

Meniru `test_admin_pesanan_cek_mutation.py`: tiap kasus menonaktifkan SATU guard (atau satu lapis guard) di salinan
terisolasi lalu menjalankan tes yang menjaganya; hasil harus MERAH karena asersi (bukan import/fixture rusak). Kontrol:
tanpa mutasi, tes yang sama HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya (count == 1). Salinan tidak
memuat `.venv`, cadangan, `*.db`, atau `*.json` (tanpa data/sandi nyata).

Guard DB (trigger/UNIQUE/CHECK/CASCADE) dan guard store punya tes sendiri-sendiri: tes SQL langsung menangkap mutasi skema
walau store masih memeriksa, tes store menangkap mutasi store walau trigger masih menolak (IntegrityError bukan ValueError).
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
S = "mesin/__tests__/test_peta_laporan_store.py::"
N = "mesin/__tests__/test_peta_laporan_snapshot.py::"
F = "mesin/__tests__/test_peta_laporan_family_deletion.py::"
P = "mesin/__tests__/test_peta_laporan_probe.py::"
SKEMA, STORE, SNAP = "mesin/schema_peta_laporan.py", "mesin/peta_laporan_store.py", "mesin/peta_laporan_snapshot.py"
HAPUS, DEPLOY = "mesin/family_deletion.py", "scripts/deploy.py"
_SQL_UPDATE_CATATAN = '"UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ? AND diterbitkan IS NULL"'

KASUS = (
    # --- skema: tiap trigger/constraint berdiri sendiri (tes SQL langsung) ---
    ("a1-trigger-terbit-tetap-mati",
     ((SKEMA, "WHEN OLD.diterbitkan IS NOT NULL\nBEGIN", "WHEN 0\nBEGIN"),),
     (S + "test_laporan_terbit_tidak_bisa_di_update_sama_sekali",)),
    ("a2-trigger-isi-tetap-mati",
     ((SKEMA, "BEGIN SELECT RAISE(ABORT, 'isi laporan peta tidak dapat diubah'); END;", "BEGIN SELECT 1; END;"),),
     (S + "test_isi_siswa_guru_dibuat_id_draf_tidak_pernah_berubah",)),
    ("a3-isi-boleh-berubah",
     ((SKEMA, "NEW.isi IS NOT OLD.isi", "0"),),
     (S + "test_isi_siswa_guru_dibuat_id_draf_tidak_pernah_berubah",)),
    ("a4-guru-boleh-berubah",
     ((SKEMA, "NEW.guru IS NOT OLD.guru", "0"),),
     (S + "test_isi_siswa_guru_dibuat_id_draf_tidak_pernah_berubah",)),
    ("a5-dibuat-boleh-berubah",
     ((SKEMA, "NEW.dibuat IS NOT OLD.dibuat", "0"),),
     (S + "test_isi_siswa_guru_dibuat_id_draf_tidak_pernah_berubah",)),
    ("b1-trigger-terbit-butuh-catatan-mati",
     ((SKEMA, "BEGIN SELECT RAISE(ABORT, 'laporan peta tidak dapat terbit tanpa catatan'); END;",
       "BEGIN SELECT 1; END;"),),
     (S + "test_trigger_terbit_tanpa_catatan_ditolak_walau_lewat_sql",)),
    ("b2-catatan-hanya-spasi-dianggap-isi",
     ((SKEMA, "trim(NEW.catatan, ' ' || char(9, 10, 13))", "trim(NEW.catatan)"),),
     (S + "test_trigger_terbit_tanpa_catatan_ditolak_walau_lewat_sql",)),
    ("c-insert-langsung-terbit-boleh",
     ((SKEMA, "BEGIN SELECT RAISE(ABORT, 'laporan peta harus dibuat sebagai draf'); END;", "BEGIN SELECT 1; END;"),),
     (S + "test_baris_baru_tidak_boleh_langsung_terbit",)),
    ("d-unique-siswa-dilepas",
     ((SKEMA, "INTEGER NOT NULL UNIQUE REFERENCES", "INTEGER NOT NULL REFERENCES"),),
     (S + "test_unique_satu_laporan_per_anak_walau_lewat_sql",)),
    ("e-check-panjang-catatan-dilepas",
     ((SKEMA, "CHECK (length(catatan) <= 2000)", ""),),
     (S + "test_check_panjang_catatan_isi_dan_guru",)),
    ("f-check-kolom-terbit-bersama-dilepas",
     ((SKEMA, "    CHECK ((diterbitkan IS NULL) = (diterbitkan_oleh IS NULL)),\n", ""),),
     (S + "test_check_kolom_terbit_terisi_bersama",)),
    ("g-cascade-siswa-dilepas",
     ((SKEMA, "REFERENCES siswa(id) ON DELETE CASCADE", "REFERENCES siswa(id)"),),
     (S + "test_hapus_siswa_menghapus_laporan_draf_dan_terbit",)),
    ("h-trigger-delete-memblokir-penghapusan-anak",
     ((SKEMA, "CREATE TRIGGER IF NOT EXISTS peta_laporan_insert_draf",
       "CREATE TRIGGER IF NOT EXISTS peta_laporan_tahan BEFORE DELETE ON peta_laporan "
       "BEGIN SELECT RAISE(ABORT, 'x'); END;\nCREATE TRIGGER IF NOT EXISTS peta_laporan_insert_draf"),),
     (S + "test_tidak_ada_trigger_delete_yang_memblokir", S + "test_hapus_siswa_menghapus_laporan_draf_dan_terbit",
      F + "test_bundle_hasil_menghapus_laporan_peta_draf_dan_terbit_anak_target_saja")),
    # --- store ---
    ("i-draf-kedua-lolos-pemeriksaan",
     ((STORE, 'if kon.execute("SELECT 1 FROM peta_laporan WHERE siswa_id = ?", (siswa_id,)).fetchone() is not None:',
       "if False:"),),
     (S + "test_draf_kedua_untuk_anak_yang_sama_ditolak", S + "test_draf_kedua_setelah_terbit_juga_ditolak")),
    ("j-buat-draf-tanpa-periksa-isi",
     ((STORE, "isi_bersih = periksa_isi(isi)", "isi_bersih = isi"),),
     (S + "test_buat_draf_menolak_isi_di_luar_allowlist",)),
    ("k-batas-catatan-store-dilepas",
     ((STORE, "if type(catatan) is not str or len(catatan) > BATAS_CATATAN:", "if type(catatan) is not str:"),),
     (S + "test_simpan_catatan_batas_dua_ribu_karakter",)),
    ("l-catatan-laporan-terbit-bisa-diubah-store",
     ((STORE, _SQL_UPDATE_CATATAN, '"UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ?"'),),
     (S + "test_simpan_catatan_pada_laporan_terbit_ditolak_dan_tidak_berubah",)),
    ("m-terbit-tanpa-catatan-lolos-store",
     ((STORE, 'if not laporan["catatan"].strip(_SPASI):', "if False:"),),
     (S + "test_terbit_butuh_catatan_tidak_kosong",)),
    ("n-terbit-kedua-kali-lolos",
     ((STORE, 'if laporan is None or laporan["diterbitkan"] is not None:', "if laporan is None:"),
      (STORE, "WHERE siswa_id = ? AND diterbitkan IS NULL\"\"\",\n        (waktu, akun, siswa_id),",
       "WHERE siswa_id = ?\"\"\",\n        (waktu, akun, siswa_id),")),
     (S + "test_terbit_kedua_kali_ditolak_dan_tidak_mengubah_penerbit_atau_waktu",)),
    ("o-hapus-laporan-terbit-lolos",
     ((STORE, 'if laporan["diterbitkan"] is not None:\n        raise ValueError("laporan terbit tidak dihapus")\n',
       ""),
      (STORE, '"DELETE FROM peta_laporan WHERE siswa_id = ? AND diterbitkan IS NULL"',
       '"DELETE FROM peta_laporan WHERE siswa_id = ?"')),
     (S + "test_hapus_draf_tidak_menghapus_laporan_terbit",)),
    ("p-terbit-terakhir-menampilkan-draf",
     ((STORE, "WHERE siswa_id = ? AND diterbitkan IS NOT NULL", "WHERE siswa_id = ?"),),
     (S + "test_terbit_terakhir_menyembunyikan_draf",)),
    ("q-terbit-terakhir-membocorkan-guru",
     ((STORE, "SELECT isi, catatan, diterbitkan FROM", "SELECT isi, catatan, diterbitkan, guru FROM"),
      (STORE, 'return {"isi": isi, "catatan": baris[1], "diterbitkan": baris[2]}',
       'return {"isi": isi, "catatan": baris[1], "diterbitkan": baris[2], "guru": baris[3]}')),
     (S + "test_terbit_terakhir_hanya_isi_catatan_dan_waktu_tanpa_akun_guru",)),
    ("r-ambil-tanpa-periksa-isi",
     ((STORE, 'laporan["isi"] = periksa_isi(json.loads(laporan["isi"]))', 'laporan["isi"] = json.loads(laporan["isi"])'),),
     (S + "test_baris_dengan_isi_di_luar_allowlist_ditolak_saat_dibaca",
      S + "test_draf_dengan_isi_rusak_tidak_bisa_diterbitkan")),
    ("s-terbit-terakhir-tanpa-periksa-isi",
     ((STORE, "isi = periksa_isi(json.loads(baris[0]))", "isi = json.loads(baris[0])"),),
     (S + "test_baris_dengan_isi_di_luar_allowlist_ditolak_saat_dibaca",)),
    ("t-waktu-bukan-epoch-lolos",
     ((STORE, "if type(sekarang) is not int:", "if False:"),),
     (S + "test_waktu_harus_epoch_bulat",)),
    ("u-akun-guru-tak-sah-lolos",
     ((STORE, "if type(guru) is not str or not 1 <= len(guru) <= BATAS_GURU:", "if False:"),),
     (S + "test_buat_draf_menolak_akun_guru_tak_sah",)),
    # --- snapshot ---
    ("v1-bahan-tak-ada-diterima",
     ((SNAP, 'ringkasan["bahan"] != BAHAN_ADA or', "False or"),),
     (N + "test_bahan_selain_ada_ditolak",)),
    ("v2-per-materi-kosong-diterima-pembangun",
     ((SNAP, ' or not ringkasan["per_materi"]', ""),),
     (N + "test_bahan_ada_tapi_per_materi_kosong_ditolak",)),
    ("v3-skor-kosong-diterima-pembangun",
     ((SNAP, ' or ringkasan["skor"] is None', ""),),
     (N + "test_cek_belum_selesai_tanpa_skor_ditolak",)),
    ("w-kunci-ringkasan-tak-dicek",
     ((SNAP, " or set(ringkasan) != set(KUNCI_HASIL)", ""),),
     (N + "test_ringkasan_dengan_kunci_asing_atau_kurang_ditolak",)),
    ("x1-periksa-isi-kunci-asing-lolos",
     ((SNAP, " or set(isi) != set(KUNCI_ISI)", ""),),
     (N + "test_periksa_isi_menolak_kunci_asing", N + "test_periksa_isi_menolak_kunci_kurang")),
    ("x2-isi-bocor-kunci-dan-periksa-lunak",
     ((SNAP, " or set(isi) != set(KUNCI_ISI)", ""),
      (SNAP, '        "ringkasan_perlu": _nama_awam(ringkasan["ringkasan_perlu"]),\n    }\n    return periksa_isi(isi)',
       '        "ringkasan_perlu": _nama_awam(ringkasan["ringkasan_perlu"]),\n'
       '        "hari_tersisa": ringkasan["hari_tersisa"],\n    }\n    return isi')),
     (N + "test_kunci_isi_persis_dan_versi_satu",)),
    ("y1-perlu-dilatih-tanpa-batas-tiga",
     ((SNAP, "urut[:MAKS_DILATIH]", "urut"),),
     (N + "test_perlu_dilatih_urut_rasio_terendah_lalu_nama_maksimal_tiga",)),
    ("y2-perlu-dilatih-urut-nama-saja",
     ((SNAP, 'key=lambda m: (Fraction(m["benar"], m["total"]), m["materi"])', 'key=lambda m: m["materi"]'),),
     (N + "test_perlu_dilatih_urut_rasio_terendah_lalu_nama_maksimal_tiga",)),
    ("y3-perlu-dilatih-memuat-materi-penuh",
     ((SNAP, ' and m["benar"] < m["total"]', ""),),
     (N + "test_perlu_dilatih_kosong_bila_semua_materi_benar_semua",)),
    ("y4-perlu-dilatih-tanpa-tiebreak-nama",
     ((SNAP, 'key=lambda m: (Fraction(m["benar"], m["total"]), m["materi"])', 'key=lambda m: Fraction(m["benar"], m["total"])'),),
     (N + "test_perlu_dilatih_rasio_sama_beda_total_diurut_nama",)),
    ("z1-benar-boleh-melebihi-total",
     ((SNAP, '_int(butir["benar"], 0, total, "benar")', '_int(butir["benar"], 0, MAKS_SOAL, "benar")'),),
     (N + "test_periksa_isi_menolak_butir_per_materi_salah",)),
    ("z2-teks-tak-tercetak-lolos",
     ((SNAP, " or not nilai.isprintable()", ""),),
     (N + "test_periksa_isi_menolak_tipe_dan_batas_salah",)),
    ("z3-nama-resmi-lama-tak-dipetakan",
     ((SNAP, "return [topik_awam.dari_nama_lama(nama) for nama in daftar]", "return list(daftar)"),),
     (N + "test_nama_resmi_lama_di_kuat_dan_perlu_dipetakan_ke_label_awam",)),
    ("z4-isi-nyata-memuat-nama-anak-via-kelas-teks",
     ((SNAP, '"kategori": ringkasan["kategori"],', '"kategori": ringkasan["kategori"] + " " + str(ringkasan.get("nama", "")),'),),
     (N + "test_isi_menyalin_nilai_yang_diizinkan_saja",)),
    # --- penghapusan keluarga ---
    ("fa-hapus-keluarga-tak-memanggil-hapus-peta",
     ((HAPUS, "        _hapus_peta_laporan(kon, siswa_ids)\n", ""),),
     (F + "test_bundle_hasil_menghapus_laporan_peta_draf_dan_terbit_anak_target_saja",)),
    ("fb-hapus-peta-menyapu-keluarga-lain",
     ((HAPUS, 'kon.execute("DELETE FROM peta_laporan WHERE siswa_id IN (%s)" % q, siswa_ids)',
       'kon.execute("DELETE FROM peta_laporan")'),),
     (F + "test_bundle_hasil_menghapus_laporan_peta_draf_dan_terbit_anak_target_saja",
      F + "test_hapus_peta_laporan_target_saja_dan_tanpa_siswa_tidak_error")),
    ("fc-hapus-peta-gagal-tanpa-tabel",
     ((HAPUS, 'if not siswa_ids or not _tabel(kon, "peta_laporan"):', "if not siswa_ids:"),),
     (F + "test_bundle_hasil_tanpa_tabel_laporan_peta_tetap_berhasil",)),
    # --- probe deploy ---
    ("pa-probe-peta-tak-memeriksa-tabel-ada",
     ((DEPLOY, "if aktual and sumber.is_file():", "if False:"),),
     (P + "test_trigger_hilang_menggagalkan_probe", P + "test_kolom_berubah_menggagalkan_probe")),
    ("pb-probe-peta-menolak-tabel-belum-ada",
     ((DEPLOY, "if aktual and sumber.is_file():", "if sumber.is_file():"),),
     (P + "test_tabel_belum_ada_lulus_karena_preflight_sebelum_migrasi",)),
    ("pc-probe-peta-gagal-di-image-lama",
     ((DEPLOY, "if aktual and sumber.is_file():", "if aktual:"),),
     (P + "test_image_lama_tanpa_modul_skema_tidak_memeriksa_tabel_tambahan",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("peta-laporan-mutasi") / "repo"
    ignore = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json")
    shutil.copytree(AKAR / "mesin", akar / "mesin", ignore=ignore)
    shutil.copytree(AKAR / "scripts", akar / "scripts", ignore=ignore)
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
def test_guard_peta_laporan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

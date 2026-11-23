"""Mutation guard pendaftaran akun anak (F2a) pada salinan source terisolasi.

Tiap kasus mematikan satu guard di salinan, memastikan tes terkait MERAH karena perilaku (bukan import/fixture
rusak), lalu memulihkan dan memastikan HIJAU. Workspace asli tidak disentuh.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
BERKAS_TES = ("test_registration_anak.py", "test_registration_anak_http.py", "test_daftar_anak_gate.py",
              "http_test_kit.py")

KASUS = (
    ("pemilik_koordinator", "admin_registration.py",
     "pemilik = alias if mode_anak is None else _koordinator_antrean(kon, akun, mode_anak)",
     "pemilik = alias",
     "test_registration_anak.py", "test_sukses_akun_murid_siswa_milik_koordinator_dan_semua_tulisan"),
    ("gabung_bukan_baris_baru", "admin_registration.py",
     "return kon.execute('INSERT INTO siswa(nama,tingkat,pemilik) VALUES(?,?,?)',\n"
     "                               (calon, tingkat, pemilik)).lastrowid",
     "kon.execute('INSERT OR IGNORE INTO siswa(nama,tingkat,pemilik) VALUES(?,?,?)', (nama, tingkat, pemilik))\n"
     "            return kon.execute('SELECT id FROM siswa WHERE nama=? AND pemilik=?', (nama, pemilik)).fetchone()[0]",
     "test_registration_anak.py", "test_dua_pendaftar_nama_lengkap_sama_menjadi_dua_siswa_berbeda"),
    ("pembeda_integrity_error", "admin_registration.py",
     "        except sqlite3.IntegrityError:\n            dicoba.append(calon)",
     "        except sqlite3.IntegrityError:\n            raise",
     "test_registration_anak.py", "test_integrity_error_unik_nama_pemilik_mencoba_pembeda_berikutnya"),
    ("fail_closed_saga", "admin_registration.py",
     "    if not sah:\n        raise AntreanBelumSiap(PESAN_ANTREAN_BELUM_SIAP)\n    return nama",
     "    return nama or 'koordinator-jagomat'",
     "test_registration_anak.py", "test_lembaga_antrean_tidak_ada_ditolak_tanpa_menulis_apa_pun"),
    ("fail_closed_http", "daftar_anak_gate.py",
     "        return Keadaan(BELUM_SIAP)", "        return Keadaan(LAMA)",
     "test_registration_anak_http.py", "test_sakelar_hidup_tanpa_lembaga_antrean_ditolak_jujur_tanpa_menulis"),
    ("sakelar_gate", "daftar_anak_gate.py",
     "    if not aktif():\n        return Keadaan(LAMA)", "    if False:\n        return Keadaan(LAMA)",
     "test_registration_anak_http.py", "test_sakelar_mati_get_dan_post_tetap_alur_akun_guru"),
    ("persetujuan_tidak_ditulis", "admin_registration.py",
     "        daftar_anak_store.catat_persetujuan(kon, siswa_id, kini)", "        pass",
     "test_registration_anak.py", "test_sukses_akun_murid_siswa_milik_koordinator_dan_semua_tulisan"),
    ("pin_tidak_ditulis", "admin_registration.py",
     "        if hash_pin is not None:\n            pin_orang_tua_store.simpan_hash(kon, siswa_id, hash_pin, kini)",
     "        if False:\n            pin_orang_tua_store.simpan_hash(kon, siswa_id, hash_pin, kini)",
     "test_registration_anak.py", "test_sukses_akun_murid_siswa_milik_koordinator_dan_semua_tulisan"),
    ("receipt_anak_ditolak_pembaca", "admin_registration.py",
     "KODE_HASIL_SAH = frozenset((KODE_GURU, KODE_ANAK))", "KODE_HASIL_SAH = frozenset((KODE_GURU,))",
     "test_registration_anak.py", "test_pembaca_lain_sehat_setelah_pendaftaran_anak_dan_guru_baru_bisa_daftar"),
    ("recompute_profil_sidik", "admin_registration.py",
     "                            lama['profil_sidik'] = _sidik_profil_registrasi(kon, siswa_id, token_form)",
     "                            pass",
     "test_registration_anak.py", "test_crash_setelah_intent_lalu_keluarga_lain_mengambil_nama_pemulihan_tetap_jalan"),
)


@pytest.mark.parametrize("nama,berkas,lama,baru,tes_berkas,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_guard_anak_merah_lalu_pulih(tmp_path, nama, berkas, lama, baru, tes_berkas, tes):
    sumber = tmp_path / "mesin"
    sumber.mkdir()
    for f in (AKAR / "mesin").glob("*.py"):
        shutil.copy2(f, sumber / f.name)
    for nama_tes in BERKAS_TES:
        shutil.copy2(Path(__file__).with_name(nama_tes), tmp_path / nama_tes)
    for sub in ("aset",):
        if (AKAR / "mesin" / sub).exists():
            os.symlink(AKAR / "mesin" / sub, sumber / sub)
    target = sumber / berkas
    asli = target.read_text()
    assert asli.count(lama) == 1, "anchor mutasi tidak ditemukan tepat satu kali"
    cmd = [sys.executable, "-B", "-m", "pytest", tes_berkas, "-k", tes, "-q", "-W", "error", "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(sumber), "OSN_PBKDF2_ITERASI": "1000",
           "PYTHONDONTWRITEBYTECODE": "1"}

    def jalankan():
        return subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)

    hijau_awal = jalankan()
    assert hijau_awal.returncode == 0, hijau_awal.stdout + hijau_awal.stderr
    target.write_text(asli.replace(lama, baru))
    merah = jalankan()
    # Merah karena perilaku: tes terpilih gagal (assert/DID NOT RAISE/galat saga), bukan galat koleksi atau setup.
    assert merah.returncode == 1 and " failed" in merah.stdout and " error" not in merah.stdout, (
        merah.stdout + merah.stderr)
    assert "ImportError" not in merah.stdout and "SyntaxError" not in merah.stdout and "fixture" not in merah.stdout
    target.write_text(asli)
    hijau = jalankan()
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

"""Mutation guard cek di sesi anak (F2b) pada salinan source terisolasi.

Tiap kasus mematikan satu guard di salinan (satu atau beberapa penggantian), memastikan tes terkait MERAH karena
perilaku (bukan import/fixture rusak), lalu memulihkan dan memastikan HIJAU. Workspace asli tidak disentuh.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
BERKAS_TES = ("test_cek_murid_http.py", "cek_murid_kit.py", "http_test_kit.py", "cek_gratis_kit.py", "cek_anak_kit.py")
TES_SISWA = "test_id_dari_query_atau_form_diabaikan_atau_ditolak_anak_lain_tidak_tersentuh"

# (nama, berkas, [(lama, baru), ...], tes)
KASUS = (
    ("siswa_dari_query", "cek_murid_http.py", [
        ("        tujuan = _jalankan(principal)", "        tujuan = _jalankan(principal, penangan.path)"),
        ("def _jalankan(principal):", "def _jalankan(principal, path=''):"),
        ("        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)",
         "        import urllib.parse as _u\n"
         "        _q = _u.parse_qs(_u.urlparse(path).query).get('siswa')\n"
         "        siswa_id = int(_q[0]) if _q else students.siswa_dari_akun(kon, principal.pengguna)"),
    ], TES_SISWA),
    ("id_akun_bukan_milik_murid", "cek_murid_http.py", [
        ("cek_murid.mulai(kon, principal.id_akun, siswa_id, _sekarang())",
         "cek_murid.mulai(kon, 'akun_' + 'a1' * 16, siswa_id, _sekarang())"),
    ], "test_mulai_membuat_cek_untuk_akun_murid_dan_mengalihkan_ke_tautan_anak"),
    ("lewati_cek_persetujuan", "cek_murid.py", [
        ("    if not persetujuan_sah(kon, siswa_id):\n        raise cek_gratis.CekPersetujuanDiperlukan",
         "    if False:\n        raise cek_gratis.CekPersetujuanDiperlukan"),
    ], "test_tanpa_persetujuan_ditolak_404_tanpa_menulis"),
    ("versi_notice_tidak_dicocokkan", "cek_murid.py", [
        ("    return ada is not None and ada[0] == VERSI_NOTICE", "    return ada is not None"),
    ], "test_versi_notice_persetujuan_beda_ditolak_tanpa_menulis"),
    ("gerbang_sakelar_anak_mati", "cek_murid.py", [
        ("    return daftar_anak_gate.aktif() and funnel_flag.funnel_aktif()", "    return funnel_flag.funnel_aktif()"),
    ], "test_sakelar_anak_mati_kartu_tidak_tampil_dan_post_identik_dengan_jalur_asing"),
    ("gerbang_funnel_mati", "cek_murid.py", [
        ("    return daftar_anak_gate.aktif() and funnel_flag.funnel_aktif()", "    return daftar_anak_gate.aktif()"),
    ], "test_funnel_mati_kartu_tidak_tampil_dan_post_identik_dengan_jalur_asing"),
    ("body_tidak_dikosongkan", "cek_murid_http.py", [
        ("    if tubuh.strip():\n        penangan._tolak_isian()\n        return False", "    if False:\n        return False"),
    ], TES_SISWA),
    ("cek_akun_lain_diambil_alih", "cek_murid.py", [
        ("    if baris[\"id_akun\"] != id_akun:\n        return None", "    if False:\n        return None"),
    ], "test_cek_milik_akun_lain_untuk_anak_sama_tidak_diambil_alih"),
    ("sesi_cek_tidak_disembunyikan", "student_pages.py", [
        ("daftar = [s for s in data[\"sesi\"] if s[\"id\"] not in sembunyikan_sesi]", "daftar = data[\"sesi\"]"),
    ], "test_cek_anak_tidak_muncul_sebagai_latihan_biasa_di_beranda"),
    ("kartu_tetap_setelah_dikumpulkan", "cek_murid.py", [
        ("baris[\"sesi_ada\"] is None or baris[\"selesai\"] is not None \\\n            or baris[\"dibatalkan\"] is not None",
         "baris[\"sesi_ada\"] is None or baris[\"dibatalkan\"] is not None"),
    ], "test_mulai_setelah_selesai_kembali_ke_beranda_tanpa_cek_kedua"),
)


@pytest.mark.parametrize("nama,berkas,ganti,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_guard_cek_murid_merah_lalu_pulih(tmp_path, nama, berkas, ganti, tes):
    sumber = tmp_path / "mesin"
    sumber.mkdir()
    for f in (AKAR / "mesin").glob("*.py"):
        shutil.copy2(f, sumber / f.name)
    for nama_tes in BERKAS_TES:
        shutil.copy2(Path(__file__).with_name(nama_tes), tmp_path / nama_tes)
    if (AKAR / "mesin" / "aset").exists():
        os.symlink(AKAR / "mesin" / "aset", sumber / "aset")
    target = sumber / berkas
    asli = target.read_text()
    for lama, _baru in ganti:
        assert asli.count(lama) == 1, "anchor mutasi tidak ditemukan tepat satu kali: " + lama
    cmd = [sys.executable, "-B", "-m", "pytest", "test_cek_murid_http.py", "-k", tes, "-q", "-W", "error",
           "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(sumber), "OSN_PBKDF2_ITERASI": "1000",
           "PYTHONDONTWRITEBYTECODE": "1"}

    def jalankan():
        return subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)

    hijau_awal = jalankan()
    assert hijau_awal.returncode == 0, hijau_awal.stdout + hijau_awal.stderr
    mutan = asli
    for lama, baru in ganti:
        mutan = mutan.replace(lama, baru)
    target.write_text(mutan)
    merah = jalankan()
    assert merah.returncode == 1 and " failed" in merah.stdout and " error" not in merah.stdout, (
        merah.stdout + merah.stderr)
    assert "ImportError" not in merah.stdout and "SyntaxError" not in merah.stdout and "NameError" not in merah.stdout
    target.write_text(asli)
    hijau = jalankan()
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

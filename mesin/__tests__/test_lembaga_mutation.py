"""Mutation guard Lembaga les (jalur Kritis) pada salinan source terisolasi: mutasi -> MERAH, pulih -> HIJAU.

Setiap kasus mematikan satu palang (sandi admin, CSRF, aksi tinjauan, ikatan target, konfirmasi nama)
lalu membuktikan tes negatif yang relevan gagal. Dalam salinan bermutasi yang sama, tes jalur sukses
(`SEHAT`) harus tetap hijau, jadi merahnya karena palang yang dimatikan, bukan karena salinan rusak.
Sumber asli dipulihkan dan tes negatif yang sama harus lulus.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
HTTP = "admin_lembaga_http.py"
UJI = "test_admin_lembaga.py"
SEHAT = "test_tambah_dan_lepas_anggota"
POST_AMAN = "        _akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)\n"
KASUS = [
    # (a) cek sandi admin di jalur bersama (_token_final)
    ("admin_http.py", 'if not _reauth(principal, data.pop("reauth", "")):',
     'if not _reauth(principal, data.pop("reauth", "")) and False:',
     "test_tanpa_sandi_admin_ditolak_403_tanpa_efek", "failed"),
    ("admin_http.py", 'if not _reauth(principal, data.pop("reauth", "")):',
     'if not _reauth(principal, data.pop("reauth", "")) and False:',
     "test_sandi_salah_ditolak_403_tanpa_efek", "failed"),
    # (b) semua cek (CSRF + tinjauan + sandi) dimatikan langsung di handler lembaga
    (HTTP, POST_AMAN,
     "        data.pop('csrf', None); data.pop('tinjauan', None); data.pop('reauth', None)\n"
     "        tinjauan = {'data': {'target_id': int(data.get('lembaga_id') or 0), 'akun': data.get('guru')}}\n",
     "test_tanpa_sandi_admin_ditolak_403_tanpa_efek", "failed"),
    (HTTP, POST_AMAN,
     "        data.pop('csrf', None); data.pop('tinjauan', None); data.pop('reauth', None)\n"
     "        tinjauan = {'data': {'target_id': int(data.get('lembaga_id') or 0), 'akun': data.get('guru')}}\n",
     "test_sandi_salah_ditolak_403_tanpa_efek", "failed"),
    # (c) CSRF dan aksi tinjauan
    ("admin_http.py", '_cek_csrf(akun, token_sesi, data.pop("csrf", None))\n    token = data.pop("tinjauan", None)',
     'data.pop("csrf", None)\n    token = data.pop("tinjauan", None)',
     "test_csrf_hilang_atau_palsu_ditolak_tanpa_efek", "failed"),
    ("admin_http.py", 'if tinjauan["aksi"] != aksi:', "if False:",
     "test_tinjauan_aksi_lain_ditolak_tanpa_efek", "failed"),
    # (d) ikatan target di dalam tinjauan
    (HTTP, 'if meta.get("target_id") != lembaga_id or (guru is not None and meta.get("akun") != guru):',
     "if False:", "test_tinjauan_lembaga_lain_atau_guru_lain_ditolak_tanpa_efek", "failed"),
    # (e) konfirmasi ketik nama divalidasi di server
    (HTTP, "if konfirmasi != nama:", "if False:",
     "test_bubarkan_nama_salah_ditolak_400_tanpa_efek", "failed"),
]


def _pytest(target, node):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-W", "error", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=180, cwd=str(target.parent),
    )


@pytest.mark.parametrize("modul,lama,baru,uji,marker", KASUS)
def test_mutasi_palang_lembaga(tmp_path, modul, lama, baru, uji, marker):
    target = tmp_path / "mesin"
    target.mkdir()
    for sumber in AKAR.glob("*.py"):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / "__tests__", target / "__tests__", ignore=shutil.ignore_patterns("__pycache__"))
    p = target / modul
    teks = p.read_text()
    assert teks.count(lama) == 1, "pola mutasi tidak unik: %r" % lama
    p.write_text(teks.replace(lama, baru, 1))
    node = str(target / "__tests__" / UJI) + "::" + uji
    merah = _pytest(target, node)
    assert merah.returncode == 1, merah.stdout + merah.stderr
    assert marker in merah.stdout, merah.stdout
    sehat = _pytest(target, str(target / "__tests__" / UJI) + "::" + SEHAT)
    assert sehat.returncode == 0, "salinan bermutasi rusak, bukan palang yang diuji:\n" + sehat.stdout
    p.write_text(teks)
    hijau = _pytest(target, node)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

"""Mutation guard Lembaga les (jalur Kritis) pada salinan source terisolasi: mutasi -> MERAH, pulih -> HIJAU.

Setiap kasus mematikan satu palang (sandi admin, CSRF, aksi tinjauan, ikatan target, konfirmasi nama)
lalu membuktikan tes negatif yang relevan gagal. Dalam salinan bermutasi yang sama, tes jalur sukses
(`SEHAT`) harus tetap hijau, jadi merahnya karena palang yang dimatikan, bukan karena salinan rusak.
Sumber asli dipulihkan dan tes negatif yang sama harus lulus.

Guard F1 (lepas anggota mengembalikan anak ke pemilik lembaga, cek sesi berjalan, pembeda nama kembar)
punya tabel kasus sendiri (`KASUS_F1`) pada berkas tes store dan HTTP admin.
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
POST_AMAN = "        akun, tinjauan, _token = h._token_final(penangan, principal, data, aksi)\n"
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
     "        tinjauan = {'data': {'target_id': int(data.get('lembaga_id') or 0), 'akun': data.get('guru')}}\n"
     "        akun = {'pengguna': 'mutan'}\n",
     "test_tanpa_sandi_admin_ditolak_403_tanpa_efek", "failed"),
    (HTTP, POST_AMAN,
     "        data.pop('csrf', None); data.pop('tinjauan', None); data.pop('reauth', None)\n"
     "        tinjauan = {'data': {'target_id': int(data.get('lembaga_id') or 0), 'akun': data.get('guru')}}\n"
     "        akun = {'pengguna': 'mutan'}\n",
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


def _salin_dan_mutasi(tmp_path, modul, lama, baru):
    """Salinan terisolasi mesin/ dengan satu mutasi; kembalikan (target, path modul, teks asli)."""
    target = tmp_path / "mesin"
    target.mkdir()
    for sumber in AKAR.glob("*.py"):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / "__tests__", target / "__tests__", ignore=shutil.ignore_patterns("__pycache__"))
    p = target / modul
    teks = p.read_text()
    assert teks.count(lama) == 1, "pola mutasi tidak unik: %r" % lama
    p.write_text(teks.replace(lama, baru, 1))
    return target, p, teks


def _buktikan_merah_sehat_hijau(target, p, teks, berkas, uji, sehat, marker):
    node = str(target / "__tests__" / berkas) + "::" + uji
    merah = _pytest(target, node)
    assert merah.returncode == 1, merah.stdout + merah.stderr
    assert marker in merah.stdout, merah.stdout
    ok = _pytest(target, str(target / "__tests__" / berkas) + "::" + sehat)
    assert ok.returncode == 0, "salinan bermutasi rusak, bukan palang yang diuji:\n" + ok.stdout
    p.write_text(teks)
    hijau = _pytest(target, node)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr


@pytest.mark.parametrize("modul,lama,baru,uji,marker", KASUS)
def test_mutasi_palang_lembaga(tmp_path, modul, lama, baru, uji, marker):
    target, p, teks = _salin_dan_mutasi(tmp_path, modul, lama, baru)
    _buktikan_merah_sehat_hijau(target, p, teks, UJI, uji, SEHAT, marker)


# --- F1: lepas anggota mengembalikan anak, cek sesi berjalan, pembeda nama kembar -------------

STORE = "lembaga_store.py"
UJI_STORE = "test_lembaga.py"
SEHAT_STORE = "test_pindah_sukses_menulis_satu_ubahan_dan_satu_jejak"
# (i) pemindahan anak di lepas_anggota dimatikan (keanggotaan tetap terhapus).
PINDAH_LEPAS = (
    '        _tulis_pindah(kon, lembaga_id=int(lembaga["id"]), siswa_id=siswa_id,\n'
    "                      dari=guru, ke=pemilik, nama_baru=nama_baru, oleh=oleh)\n"
)
# (ii) cek sesi berjalan di lepas_anggota dimatikan.
CEK_SESI_LEPAS = '    if any(_sesi_berjalan(kon, int(a["id"])) for a in anak):\n'
# (iii) pembeda dimatikan: nama asli selalu dipakai walau bentrok.
CEK_PEMBEDA = "        if calon.casefold() not in pesanan and not _nama_terpakai(kon, calon, pemilik):\n"
KASUS_F1 = [
    (PINDAH_LEPAS, "        pass\n", UJI_STORE, "test_lepas_memindah_semua_anak_ke_pemilik_dengan_jejak_per_anak", SEHAT_STORE),
    (PINDAH_LEPAS, "        pass\n", UJI, "test_lepas_sukses_memindah_semua_anak_ke_pemilik_dengan_jejak_oleh_admin", SEHAT),
    (CEK_SESI_LEPAS, "    if False:\n", UJI_STORE,
     "test_lepas_ditolak_selagi_ada_anak_dengan_sesi_berjalan_tanpa_efek", SEHAT_STORE),
    (CEK_SESI_LEPAS, "    if False:\n", UJI_STORE,
     "test_lepas_ditolak_selagi_operasi_foto_belum_selesai", SEHAT_STORE),
    (CEK_SESI_LEPAS, "    if False:\n", UJI,
     "test_lepas_ditolak_saat_sesi_berjalan_dengan_pesan_ramah_tanpa_efek", SEHAT),
    (CEK_PEMBEDA, "        if True:\n", UJI_STORE,
     "test_pindah_dengan_nama_bentrok_berhasil_dan_nama_diberi_pembeda", SEHAT_STORE),
    (CEK_PEMBEDA, "        if True:\n", UJI_STORE,
     "test_lepas_memindah_semua_anak_ke_pemilik_dengan_jejak_per_anak", SEHAT_STORE),
    (CEK_PEMBEDA, "        if True:\n", UJI,
     "test_lepas_sukses_memindah_semua_anak_ke_pemilik_dengan_jejak_oleh_admin", SEHAT),
]


@pytest.mark.parametrize("lama,baru,berkas,uji,sehat", KASUS_F1)
def test_mutasi_guard_lepas_dan_pembeda_nama(tmp_path, lama, baru, berkas, uji, sehat):
    target, p, teks = _salin_dan_mutasi(tmp_path, STORE, lama, baru)
    _buktikan_merah_sehat_hijau(target, p, teks, berkas, uji, sehat, "failed")

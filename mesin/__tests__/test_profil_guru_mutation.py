"""Mutation guard profil guru pada salinan source terisolasi: mutasi -> MERAH, pulih -> HIJAU."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
PG = "profil_guru_settings.py"
HTTP = "admin_profil_guru_http.py"
GUARD_POST_ASAL = (
    "    principal = h._principal_admin(penangan)\n"
    "    if principal is None:\n"
    "        h._tidak_ada(penangan)\n"
    "        return True\n"
    "    try:\n"
    "        if pg.baca(h._path_admin()) is None:"
)
KASUS = [
    # (a) guard admin-saja pada POST (HTTP) dan pada penulis domain
    (HTTP, GUARD_POST_ASAL, GUARD_POST_ASAL.replace("h._principal_admin(penangan)", "penangan._principal()"),
     "test_profil_guru_http.py", "test_anon_guru_murid_404_identik_get_dan_post_tanpa_menyentuh_domain",
     "domain profil guru dipanggil sebelum guard admin"),
    (PG, "with admin_launch_service.kunci_principal(path_auth, principal):",
     "with __import__('contextlib').nullcontext():",
     "test_profil_guru_settings.py", "test_hanya_admin_hidup_boleh_menulis", "DID NOT RAISE"),
    # (b) filter proyeksi publik tampil=1
    (PG, '"SELECT * FROM profil_guru WHERE tampil=1 ORDER BY urutan,id"',
     '"SELECT * FROM profil_guru ORDER BY urutan,id"',
     "test_profil_guru_settings.py", "test_reader_publik_hanya_tampil_urut_dan_tanpa_kolom_lain", "assert"),
    (PG, '"SELECT * FROM profil_guru WHERE tampil=1 ORDER BY urutan,id"',
     '"SELECT * FROM profil_guru ORDER BY urutan,id"',
     "test_profil_guru_public.py", "test_profil_tampil_dirender_dan_yang_tersembunyi_tidak", "Tersembunyi"),
    # (c) validasi dan escape nama
    (PG, 'if "<" in bersih or ">" in bersih:', "if False:",
     "test_profil_guru_settings.py", "test_nama_tak_sah_ditolak_tanpa_tulis", "DID NOT RAISE"),
    ("funnel_pages.py", 'f\'<li><b>{_e(str(g.get("nama", "")))}</b>\'', 'f\'<li><b>{str(g.get("nama", ""))}</b>\'',
     "test_profil_guru_public.py", "test_escape_langsung_pada_sumber_data_renderer", "assert"),
    ("admin_profil_guru_pages.py", "% (e(profil.nama), status, ringkas, forms))", "% (profil.nama, status, ringkas, forms))",
     "test_profil_guru_http.py", "test_nama_di_escape_dan_konfirmasi_hapus_menyebut_konsekuensi", "assert"),
    # guard tambahan
    (PG, "if lama.revisi != revisi or sidik_profil(lama) != sidik_awal:", "if False:",
     "test_profil_guru_settings.py", "test_ubah_revisi_atau_sidik_basi_ditolak_tanpa_perubahan", "DID NOT RAISE"),
    (PG, "    except _GALAT_BACA:\n        return ()", "    except OSError:\n        return ()",
     "test_profil_guru_settings.py", "test_reader_publik_dan_admin_fail_closed_tanpa_tulis", "StoreBelumSiap"),
    ("admin_http.py", 'if not _reauth(principal, data.pop("reauth", "")):', "if False:",
     "test_profil_guru_http.py", "test_csrf_tinjauan_dan_reauth_wajib_tanpa_tulis", "== 403"),
    ("funnel_http.py", "    dukungan = _dukungan()\n    if not funnel_flag.funnel_aktif():",
     "    _profil_guru()\n    dukungan = _dukungan()\n    if not funnel_flag.funnel_aktif():",
     "test_profil_guru_public.py", "test_sakelar_mati_tidak_membaca_database", "profil guru dibaca"),
]


def _pytest(target, node):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-W", "error", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(target.parent),
    )


@pytest.mark.parametrize("modul,lama,baru,berkas,test,marker", KASUS)
def test_mutasi_guard_profil_guru(tmp_path, modul, lama, baru, berkas, test, marker):
    target = tmp_path / "mesin"
    target.mkdir()
    for sumber in AKAR.glob("*.py"):
        shutil.copyfile(sumber, target / sumber.name)
    shutil.copytree(AKAR / "__tests__", target / "__tests__", ignore=shutil.ignore_patterns("__pycache__"))
    p = target / modul
    teks = p.read_text()
    assert teks.count(lama) == 1, "pola mutasi tidak unik: %r" % lama
    p.write_text(teks.replace(lama, baru, 1))
    node = str(target / "__tests__" / berkas) + "::" + test
    merah = _pytest(target, node)
    assert merah.returncode == 1, merah.stdout + merah.stderr
    assert marker in merah.stdout, merah.stdout
    p.write_text(teks)
    hijau = _pytest(target, node)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

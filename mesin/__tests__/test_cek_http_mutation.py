"""Mutation guard HTTP cek gratis (Fase 2b) pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil
harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama
harus HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya.
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
H = "mesin/__tests__/test_cek_http.py::"
HH = "mesin/__tests__/test_cek_http_hasil.py::"
HTTP, PAGES, REG = "mesin/cek_http.py", "mesin/cek_pages.py", "mesin/registration_http.py"
JEBOL = '    if not funnel_flag.funnel_aktif():\n        %s'
IMPOR_PRINCIPAL = "from kontak_http import _alihkan, _baca_form, _principal_guru\n"

KASUS = (
    ("H1a-sakelar-dilewati-get",
     ((HTTP, JEBOL % "_belum_dibuka(penangan)", JEBOL.replace("not funnel_flag.funnel_aktif()", "False") % "_belum_dibuka(penangan)"),),
     (H + "test_sakelar_mati_get_halaman_belum_dibuka_tanpa_form_dan_tanpa_efek",)),
    ("H1b-sakelar-dilewati-post",
     ((HTTP, JEBOL % "return False", JEBOL.replace("not funnel_flag.funnel_aktif()", "False") % "return False"),),
     (H + "test_sakelar_mati_post_diperlakukan_rute_tak_dikenal_tanpa_efek",)),
    ("H2-setuju-dipaksa-benar",
     ((HTTP, '    setuju = data.get("setuju") == "1"', "    setuju = True"),),
     (H + "test_tanpa_setuju_satu_tidak_ada_sesi_dan_baris",)),
    ("H3a-token-mulai-tidak-divalidasi",
     ((HTTP, '    if not token_sah(principal, penangan._ambil_token(), AKSI_MULAI, data["token"]):',
       "    if False:"),),
     (H + "test_token_salah_ditolak_tanpa_efek", H + "test_token_akun_lain_tidak_berlaku")),
    ("H3b-token-tautan-tidak-divalidasi",
     ((HTTP, '    if not token_sah(principal, penangan._ambil_token(), AKSI_TAUTAN, data["token"]):',
       "    if False:"),),
     (HH + "test_tautan_token_salah_ditolak", HH + "test_tautan_token_mulai_tidak_berlaku_untuk_tautan")),
    ("H4-peran-admin-lolos",
     ((HTTP, IMPOR_PRINCIPAL,
       "from kontak_http import _alihkan, _baca_form\n\n\n"
       "def _principal_guru(penangan):\n    return penangan._principal()\n\n\n"),),
     (H + "test_admin_404_identik_rute_tak_dikenal_get_dan_post",
      H + "test_admin_tidak_bisa_memakai_token_guru")),
    ("H5-pembatas-laju-dibuang",
     ((HTTP, "        if len(waktu) >= BATAS_PERMULAAN_PER_HARI:", "        if False:"),),
     (H + "test_permulaan_ke_sebelas_dari_ip_sama_ditolak_tanpa_efek",)),
    ("H6a-policy-perlu-dibuang",
     ((HTTP, "    if not policy_http.perlu(principal):", "    if True:"),),
     (H + "test_gerbang_persetujuan_mengarahkan_tanpa_efek",)),
    ("H6b-registrasi-gerbang-persetujuan-dibuang",
     ((REG, "    if policy_http.perlu(akun_baru):", "    if False:"),),
     (HH + "test_daftar_jalur_cek_tetap_lewat_gerbang_persetujuan",)),
    ("H7a-hasil-selesai-dirender-saat-belum-selesai",
     ((PAGES, '    if hasil["status"] == "selesai":\n        isi += _blok_selesai(hasil, token_pesan)',
       '    if hasil["status"] in ("selesai", "belum_selesai"):\n        isi += _blok_selesai(hasil, token_pesan)'),),
     (HH + "test_belum_selesai_html_tanpa_angka_skor_atau_ringkasan",)),
    ("H7b-kerangka-terkunci-membocorkan-data",
     ((PAGES, '    "Penguasaan per materi",', '    "Penguasaan per materi: Pola Bilangan 4 dari 5",'),),
     (HH + "test_kerangka_terkunci_identik_untuk_hasil_berbeda_dan_tanpa_data",
      HH + "test_selesai_tanpa_angka_per_materi_kunci_jawaban_atau_peringkat")),
    ("H8-id-akun-diambil-dari-form",
     ((HTTP, 'KUNCI_MULAI = frozenset({"token", "setuju"})',
       'KUNCI_MULAI = frozenset({"token", "setuju", "id_akun"})'),
      (HTTP, "        nama = _jalankan_mulai(principal, setuju)",
       '        nama = _jalankan_mulai(principal, setuju, data.get("id_akun"))'),
      (HTTP, "def _jalankan_mulai(principal, setuju: bool):",
       "def _jalankan_mulai(principal, setuju: bool, id_form=None):"),
      (HTTP, 'cek_gratis.mulai(kon, principal.id_akun, anak["id"]',
       'cek_gratis.mulai(kon, id_form or principal.id_akun, anak["id"]')),
     (H + "test_id_akun_form_tidak_mengalihkan_cek_ke_akun_lain", H + "test_field_asing_ditolak_tanpa_efek")),
    ("H9-cek-akun-tanpa-filter-id-akun",
     ((HTTP, "           WHERE c.id_akun = ? ORDER BY c.id DESC LIMIT 1\"\"\",\n        (id_akun,),",
       "           WHERE ? IS NOT NULL ORDER BY c.id DESC LIMIT 1\"\"\",\n        (id_akun,),"),),
     (HH + "test_tautan_akun_lain_tidak_menyentuh_cek_orang", H + "test_dua_akun_cek_milik_sendiri_dan_tanpa_kebocoran")),
    ("H10-redirect-jalur-cek-dihapus",
     ((REG, '    if jalur_cek:\n        tujuan_daftar = "/cek-kemampuan/mulai"', "    if False:\n        tujuan_daftar = \"/cek-kemampuan/mulai\""),),
     (HH + "test_daftar_jalur_cek_diarahkan_ke_mulai_dan_alur_penuh_dengan_cookie",)),
    ("H11-redirect-jalur-biasa-ikut-berubah",
     ((REG, '    if jalur_cek:\n        tujuan_daftar = "/cek-kemampuan/mulai"', '    if True:\n        tujuan_daftar = "/cek-kemampuan/mulai"'),),
     (HH + "test_daftar_jalur_biasa_tujuan_tidak_berubah",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("cek-http-mutasi") / "repo"
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
def test_guard_http_cek_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

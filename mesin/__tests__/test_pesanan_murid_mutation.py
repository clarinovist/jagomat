"""Mutation guard pesanan dari akun anak (F2c) pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil harus MERAH
karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama HIJAU di salinan yang
sama. Pola mutasi harus unik di berkasnya. Salinan tanpa `.venv`, cadangan, `*.db`, `*.json`.
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
T = "mesin/__tests__/test_pesanan_murid_http.py::"
MURID, HTTP, ALUR, HALAMAN, TRF = (
    "mesin/pesanan_murid_http.py", "mesin/pesanan_http.py", "mesin/pesanan_alur.py",
    "mesin/pesanan_permukaan.py", "mesin/pesanan_transfer_http.py")

KASUS = (
    ("R1-gerbang-sakelar-get-dilewati",
     ((MURID, "    if not daftar_anak_gate.aktif():\n        return False\n    principal = _pembeli(penangan)\n"
       "    if principal is None:\n        return False\n    return pesanan_http.layani_get",
       "    principal = _pembeli(penangan)\n    if principal is None:\n        return False\n"
       "    return pesanan_http.layani_get"),),
     (T + "test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal",)),
    ("R2-gerbang-sakelar-post-dilewati",
     ((MURID, "    if not daftar_anak_gate.aktif():\n        return False\n    principal = _pembeli(penangan)\n"
       "    if principal is None:\n        return False\n    kanonik",
       "    principal = _pembeli(penangan)\n    if principal is None:\n        return False\n    kanonik"),),
     (T + "test_sakelar_mati_semua_rute_sama_dengan_jalur_murid_tak_dikenal",)),
    ("R3a-peran-bukan-murid-lolos-saja",
     ((HTTP, "    if principal is None or principal.peran != permukaan.PERAN_MURID:\n        return None\n    return principal",
       "    return principal"),),
     (T + "test_guru_bernama_sama_dengan_siswa_tetap_tidak_dilayani_di_rute_murid",)),
    ("R3b-peran-dan-tautan-siswa-tidak-diperiksa",
     ((HTTP, "    if principal is None or principal.peran != permukaan.PERAN_MURID:\n        return None\n    return principal",
       "    return principal"),
      (MURID, "    return None if siswa_id is None else principal", "    return principal")),
     (T + "test_guru_dan_admin_tidak_dilayani_di_rute_murid",)),
    ("R4-anak-bukan-dari-sesi-anak-pertama-di-db",
     ((ALUR, "        siswa_id = students.siswa_dari_akun(kon, principal.pengguna)\n        if siswa_id is None:\n            return None\n        return kon.execute",
       '        siswa_id = kon.execute("SELECT MIN(id) FROM siswa").fetchone()[0]\n        if siswa_id is None:\n            return None\n        return kon.execute'),),
     (T + "test_dua_murid_memesan_masing_masing_untuk_anak_sendiri", T + "test_pesan_membuat_order_untuk_akun_dan_anak_sesi_nominal_konstanta")),
    ("R5-pembeli-dari-kueri",
     ((MURID, "    return None if siswa_id is None else principal",
       "    import dataclasses, urllib.parse\n"
       "    kueri = urllib.parse.parse_qs(urllib.parse.urlparse(penangan.path).query)\n"
       '    return None if siswa_id is None else dataclasses.replace(principal, id_akun=kueri.get("akun", [principal.id_akun])[0])'),),
     (T + "test_kueri_tidak_menentukan_anak_atau_akun",)),
    ("R6a-anak-dan-akun-dari-form-transfer",
     ((TRF, "    if data is None or set(data) != KUNCI_FORM:\n        penangan._tolak_isian()",
       '    if data is None or not {"token"} <= set(data) <= {"token", "id_akun", "siswa_id", "rupiah"}:\n        penangan._tolak_isian()'),),
     (T + "test_nominal_id_akun_dan_anak_dari_form_ditolak_tanpa_efek",)),
    ("R6b-anak-dan-akun-dari-form-qris",
     ((HTTP, "    if data is None or set(data) != KUNCI_FORM:\n        penangan._tolak_isian()",
       '    if data is None or not {"token"} <= set(data) <= {"token", "id_akun", "siswa_id", "rupiah"}:\n        penangan._tolak_isian()'),
      (HTTP, "    aksi = AKSI_RUTE[jalur]\n",
       '    aksi = AKSI_RUTE[jalur]\n    import dataclasses\n'
       '    principal = dataclasses.replace(principal, id_akun=data.get("id_akun", principal.id_akun))\n')),
     (T + "test_qris_form_asing_dan_token_salah_ditolak_tanpa_efek",)),
    ("R7-cek-selesai-dilewati",
     ((ALUR, "    if not selesai:\n        raise PesananCekBelumSelesai()", "    if False:\n        raise PesananCekBelumSelesai()"),),
     (T + "test_cek_belum_selesai_ditolak_pesan_sama_dengan_guru_tanpa_efek",)),
    ("R8-kontak-dilewati",
     ((ALUR, 'kontak is not None and bool(kontak.get("wa"))', "True"),),
     (T + "test_tanpa_kontak_ditolak_pesan_sama_dengan_guru_tanpa_tautan_kontak",)),
    ("R9-gerbang-pembayaran-dilewati",
     ((HTTP, "    if not pesanan.baca_gerbang(admin_store.BAWAAN, runtime.kesiapan):\n        return None\n", ""),),
     (T + "test_sakelar_hidup_gerbang_pembayaran_tertutup_halaman_jujur_dan_post_404",
      T + "test_transfer_saja_tidak_pernah_menghubungi_provider_pembayaran")),
    ("R10a-token-form-tidak-divalidasi-transfer",
     ((TRF, '    if not dasar.token_sah(principal, penangan._ambil_token(), aksi, data["token"]):', "    if False:"),),
     (T + "test_token_milik_murid_lain_ditolak_tanpa_efek",)),
    ("R10b-token-form-tidak-divalidasi-qris",
     ((HTTP, '    if not token_sah(principal, penangan._ambil_token(), aksi, data["token"]):', "    if False:"),),
     (T + "test_qris_form_asing_dan_token_salah_ditolak_tanpa_efek",)),
    ("R11-sesi-murid-dianggap-berubah-setelah-aksi",
     ((HTTP, "        return principal_murid(penangan) == principal", "        return False"),),
     (T + "test_pesan_membuat_order_untuk_akun_dan_anak_sesi_nominal_konstanta",
      T + "test_tagihan_dan_unggah_bukti_tercatat_atas_akun_murid")),
    ("R12-rute-murid-bocor-ke-alamat-guru",
     ((HALAMAN, "    return RUTE_MURID if peran == PERAN_MURID else RUTE_GURU", "    return RUTE_GURU"),),
     (T + "test_titik_masuk_tanpa_pesanan_menampilkan_kartu_pesan_dengan_rute_murid",
      T + "test_tagihan_dan_unggah_bukti_tercatat_atas_akun_murid")),
    ("R13-404-order-orang-lain-berbeda-dari-jalur-tak-dikenal",
     ((HTTP, '        penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), 404)\n        return',
       '        penangan._kirim(halaman_pesan_murid("404", "<h1>Pesanan orang lain</h1>"), 404)\n        return'),),
     (T + "test_murid_b_tidak_bisa_menyentuh_pesanan_a_404_identik_tanpa_efek",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("pesanan-murid-mutasi") / "repo"
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
    hasil = _jalankan(salinan, [T.rstrip(":")])
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr


@pytest.mark.parametrize("nama,suntingan,sasaran", KASUS, ids=[k[0] for k in KASUS])
def test_guard_pesanan_murid_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

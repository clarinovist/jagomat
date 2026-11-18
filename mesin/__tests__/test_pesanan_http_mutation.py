"""Mutation guard HTTP pesanan (Fase 3c-3) pada SALINAN repo terisolasi (bukan workspace).

Tiap kasus menonaktifkan satu guard di salinan lalu menjalankan tes yang menjaganya: hasil
harus MERAH karena asersi (bukan import/fixture rusak). Kontrol: tanpa mutasi, tes yang sama
harus HIJAU di salinan yang sama. Pola mutasi harus unik di berkasnya. Salinan tidak memuat
`.venv`, cadangan, `*.db`, atau `*.json` (tanpa data/sandi nyata).
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
G = "mesin/__tests__/test_pesanan_http.py::"
A = "mesin/__tests__/test_pesanan_http_alur.py::"
HTTP, ALUR, CEK = "mesin/pesanan_http.py", "mesin/pesanan_alur.py", "mesin/cek_http.py"

KASUS = (
    ("Q1-gerbang-dilewati",
     ((HTTP, "    if not pesanan.baca_gerbang(admin_store.BAWAAN, runtime.kesiapan):\n        return None\n", ""),),
     (G + "test_salah_satu_syarat_gerbang_hilang_semua_tertutup_fail_closed",)),
    ("Q2a-nominal-bukan-konstanta",
     ((ALUR, '    return {**keadaan.order, "kedaluwarsa"', '    return {**keadaan.order, "rupiah": 1000, "kedaluwarsa"'),),
     (A + "test_pesan_sukses_satu_order_nominal_konstanta_create_sekali_dan_prg",)),
    ("Q2b-whitelist-form-longgar-nominal-masuk",
     ((HTTP, "    if data is None or set(data) != KUNCI_FORM:\n        penangan._tolak_isian()",
       '    if data is None or not set(data) <= (KUNCI_FORM | {"rupiah", "nominal", "harga"}):\n        penangan._tolak_isian()'),),
     (G + "test_field_asing_ditolak_400_tanpa_efek", A + "test_nominal_dan_harga_dari_form_ditolak_dan_tidak_dipakai")),
    ("Q3a-cek-selesai-tidak-diperiksa",
     ((ALUR, "    if not selesai:\n        raise PesananCekBelumSelesai()", "    if False:\n        raise PesananCekBelumSelesai()"),),
     (A + "test_cek_belum_selesai_tidak_bisa_memesan", A + "test_tanpa_cek_sama_sekali_tidak_bisa_memesan")),
    ("Q3b-cek-terbaru-akun-bukan-cek-anak",
     ((ALUR, 'hasil = cek_gratis.hasil_siswa(kon, principal.id_akun, baris["id"])',
       "hasil = cek_gratis.baca_hasil(kon, principal.id_akun)"),),
     (A + "test_cek_milik_anak_lain_akun_yang_sama_tidak_dipakai",)),
    ("Q4-prasyarat-whatsapp-dilewati",
     ((ALUR, 'kontak is not None and bool(kontak.get("wa"))', "True"),),
     (A + "test_tanpa_whatsapp_tidak_ada_order_dan_tautan_kontak",)),
    ("Q5-token-form-tidak-divalidasi",
     ((HTTP, '    if not token_sah(principal, penangan._ambil_token(), aksi, data["token"]):', "    if False:"),),
     (G + "test_token_salah_ditolak_tanpa_efek", G + "test_token_aksi_lain_tidak_berlaku_lintas_aksi",
      G + "test_token_kontak_tidak_berlaku", G + "test_token_milik_akun_lain_ditolak")),
    ("Q6a-admin-peran-lain-lolos",
     ((HTTP, "from kontak_http import _alihkan, _baca_form, _principal_guru\n",
       "from kontak_http import _alihkan, _baca_form\n\n\n"
       "def _principal_guru(penangan):\n    return penangan._principal()\n\n\n"),),
     (G + "test_admin_get_404_identik_rute_tak_dikenal", G + "test_admin_post_404_identik_rute_tak_dikenal_tanpa_efek")),
    ("Q6b-kepemilikan-anak-tanpa-filter-pemilik",
     ((CEK, '"SELECT id, nama FROM siswa WHERE pemilik = ? ORDER BY id LIMIT 1", (pengguna,)',
       '"SELECT id, nama FROM siswa WHERE ? IS NOT NULL ORDER BY id LIMIT 1", (pengguna,)'),),
     (G + "test_dua_akun_terpisah_tidak_saling_lihat_order",)),
    ("Q7-lunas-tanpa-verifikasi-provider",
     ((ALUR, '{"order_id": order_id, "transaction_id": hasil.transaksi_id},',
       '{"order_id": order_id, "transaction_id": hasil.transaksi_id, "transaction_status": "settlement", '
       '"status_code": "200", "gross_amount": "49000.00", "merchant_id": keadaan.order["merchant"], '
       '"currency": "IDR", "payment_type": "qris", "fraud_status": "accept"},'),),
     (A + "test_create_dicatat_sebagai_pengamatan_tanpa_karangan_dan_tanpa_receipt",
      A + "test_halaman_status_belum_bayar_qr_same_origin_tanpa_data_sensitif")),
    ("Q8a-qr-tanpa-syarat-status",
     ((ALUR, "    qr = url_qr(hasil.data, keadaan.order, keadaan.transaksi, config) if belum else None",
       '    qr = config.base_url + "/v2/qris/" + (keadaan.transaksi or "x") + "/qr-code"'),),
     (A + "test_qr_404_setelah_lunas", A + "test_qr_404_tanpa_transaksi", A + "test_qr_404_setelah_kedaluwarsa_lokal",
      A + "test_qr_404_bila_status_provider_tidak_cocok_order")),
    ("Q8b-qr-transaksi-bukan-transaksi-jendela",
     ((ALUR, '    if (data.get("transaction_id") != transaksi_jendela\n            or provider_modul',
       "    if (False\n            or provider_modul"),),
     (A + "test_qr_404_bila_status_provider_tidak_cocok_order",)),
    ("Q9-pembatas-laju-dibuang",
     ((HTTP, "        if any(len(aktif.get(k, ())) >= maks for k, maks in batas.items()):", "        if False:"),),
     (G + "test_laju_per_akun_lewat_batas_429_tanpa_efek", G + "test_laju_per_ip_berlaku_lintas_akun",
      G + "test_laju_get_status_tidak_memblokir_halaman_hanya_pemeriksaan_provider")),
    ("Q10-id-akun-dari-form",
     ((HTTP, "    if data is None or set(data) != KUNCI_FORM:\n        penangan._tolak_isian()",
       '    if data is None or not {"token"} <= set(data) <= {"token", "id_akun"}:\n        penangan._tolak_isian()'),
      (HTTP, "    aksi = AKSI_RUTE[jalur]\n",
       '    aksi = AKSI_RUTE[jalur]\n    import dataclasses\n'
       '    principal = dataclasses.replace(principal, id_akun=data.get("id_akun", principal.id_akun))\n')),
     (G + "test_id_akun_dari_form_ditolak_dan_tidak_dipakai",)),
    ("Q11-post-saat-gerbang-tertutup-membuat-order",
     ((HTTP, "    runtime = _runtime_bila_terbuka(penangan)\n    if runtime is None:\n        return False\n",
       "    runtime = _runtime(penangan)\n    if runtime is None:\n        return False\n"),),
     (G + "test_salah_satu_syarat_gerbang_hilang_semua_tertutup_fail_closed",)),
    ("Q12-sinyal-mati-transaksi-lama-dipakai-jendela-baru",
     ((ALUR, "    if transaksi is None:\n        return False\n    return kon.execute(", "    return kon.execute("),
      (ALUR, "AND sumber='status' AND transaksi_id=? \"", "AND sumber='status' AND (transaksi_id=? OR 1=1) \""),),
     (A + "test_sinyal_mati_transaksi_lama_tidak_membuka_jendela_baru",)),
)


@pytest.fixture(scope="module")
def salinan(tmp_path_factory):
    akar = tmp_path_factory.mktemp("pesanan-http-mutasi") / "repo"
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
def test_guard_http_pesanan_menangkap_mutasi(salinan, nama, suntingan, sasaran):
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

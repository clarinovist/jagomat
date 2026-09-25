"""Mutation source terisolasi: regression nyata merah, pulihkan lalu hijau.

Tidak memodifikasi checkout/DB pengguna; tmp_path pytest memiliki semua salinan.
Output subprocess hanya assertion sintetis, tidak ada credential atau jaringan.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]

KASUS = [
    ("checkout_runtime", "subscription_http.py", "if penangan.server.server_address[0] not in ('127.0.0.1', '::1'):", "if False:",
     "test_subscription_http.py::test_runtime_nonloopback_ditolak", "AssertionError"),
    ("checkout_https", "subscription_http.py", "if not penangan._di_https() and host not in ('127.0.0.1', 'localhost', '::1'):", "if False:",
     "test_subscription_http.py::test_post_http_host_nonloopback_ditolak", "AssertionError"),
    ("checkout_csrf", "subscription_http.py", "if not hmac.compare_digest(signature, harap):", "if False:",
     "test_subscription_http.py::test_form_tidak_sah_tanpa_invoice_atau_jaringan[palsu]", "AssertionError"),
    ("checkout_owner_recheck", "subscription_service.py", "if cek_sesi is not None:\n            cek_sesi()", "if False:\n            cek_sesi()",
     "test_subscription_service.py::test_sesi_stale_setelah_provider_tidak_boleh_grant", "DID NOT RAISE"),
    ("checkout_no_get_write", "subscription_http.py", "('settlement_terdeteksi' if hasil.status == 'lunas' else hasil.status)", "('lunas' if hasil.status == 'lunas' else hasil.status)",
     "test_subscription_http.py::test_alur_quote_pending_qr_lunas_replay_dan_get_readonly", "AssertionError"),
    ("checkout_qr_status", "subscription_http.py", "if hasil.status != 'pending' or not hasil.qr", "if not hasil.qr",
     "test_subscription_http.py::test_status_lunas_dengan_qr_tetap_menolak_gambar", "AssertionError"),
    ("midtrans_pending_bind", "midtrans_contract.py", 'data.get("transaction_status") == "pending" and data.get("status_code") == "201"', 'data.get("status_code") == "201"',
     "test_midtrans_contract.py::test_status_pending_memberi_qr_dari_transaksi_terikat", "AssertionError"),
    ("sandbox_config", "midtrans_sandbox.py", 'config.lingkungan != "sandbox"', 'False',
     "test_midtrans_sandbox.py::test_produksi_ditolak_sebelum_socket", "DID NOT RAISE"),
    ("sandbox_payload", "midtrans_sandbox.py", 'if req != kanonis:', 'if False:',
     "test_midtrans_sandbox.py::test_create_tambahan_ditolak_sebelum_socket[kontak]", "DID NOT RAISE"),
    ("sandbox_host", "midtrans_sandbox.py", 'HTTPSConnection(HOST,', 'HTTPSConnection("api.midtrans.com",',
     "test_midtrans_sandbox.py::test_query_settlement_tls_host_timeout_dan_close", "AssertionError"),
    ("sandbox_options", "midtrans_sandbox.py", 'or allow_redirects is not False', '',
     "test_midtrans_sandbox.py::test_opsi_tidak_aman_ditolak[10-True]", "DID NOT RAISE"),
    ("sandbox_tls", "midtrans_sandbox.py", 'ssl.create_default_context()', 'ssl._create_unverified_context()',
     "test_midtrans_sandbox.py::test_query_settlement_tls_host_timeout_dan_close", "AssertionError"),
    ("sandbox_redirect", "midtrans_sandbox.py", 'if respons.status != 200:', 'if False:',
     "test_midtrans_sandbox.py::test_error_redirect_tanpa_read_retry_atau_grant[302]", "AssertionError"),
    ("sandbox_size", "midtrans_sandbox.py", 'if len(data) > batas:', 'if False:',
     "test_midtrans_sandbox.py::test_baca_bounded_meski_tanpa_content_length", "respons terlalu besar harus ditolak adapter"),
    ("sandbox_truncated", "midtrans_sandbox.py", 'if panjang is not None and len(data) != int(panjang):', 'if False:',
     "test_midtrans_sandbox.py::test_content_length_terpotong_tidak_dianggap_utuh", "respons terpotong harus ditolak adapter"),
    ("sandbox_deadline", "midtrans_sandbox.py", 'if sisa <= 0:', 'if False:',
     "test_midtrans_sandbox.py::test_deadline_memutus_stream_lambat", "AssertionError"),
    ("sandbox_secret", "midtrans_sandbox.py", 'raise m.KontrakTidakSah("penutupan koneksi sandbox gagal") from None', 'raise',
     "test_midtrans_sandbox.py::test_exception_tidak_bocor_dan_tidak_retry[close]", "OSError"),
    ("registration_switch", "subscription_registration.py", '    sakelar.wajib("fondasi")', '',
     "test_subscription_registration.py::test_off_sebelum_akun_dibuat", "StoreBelumSiap"),
    ("service_receipt", "subscription_service.py", ' or r["hasil_id"] != akun_id', '',
     "test_subscription_service.py::test_receipt_akun_lain_ditolak", "DID NOT RAISE"),
    ("service_principal", "subscription_service.py", 'or auth.revisi_auth(akun) != principal.revisi_auth', '',
     "test_subscription_service.py::test_identitas_receipt_dan_cutoff_tolak_tanpa_efek[stale]", "DID NOT RAISE"),
    ("service_profile", "subscription_service.py", 'if row and row[0] == akun["pengguna"] else None', 'if row else None',
     "test_subscription_service.py::test_profile_owner_dan_tanpa_login", "DID NOT RAISE"),
    ("service_switch", "subscription_service.py", '    sakelar.wajib("rekonsiliasi")\n    d.waktu(sekarang)\n    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):\n        inv = _invoice_terjaga(path_admin, kon, akun, invoice_id)\n        if inv["merchant"] != config.merchant or sekarang < inv["dibuat"]:', '    d.waktu(sekarang)\n    with _keluarga(path_db, path_auth, principal) as (kon, akun, _):\n        inv = _invoice_terjaga(path_admin, kon, akun, invoice_id)\n        if inv["merchant"] != config.merchant or sekarang < inv["dibuat"]:',
     "test_subscription_service.py::test_default_off_tidak_membaca_file_atau_transport", "StoreBelumSiap"),
    ("intent", "subscription_store.py", '        if kon.execute("SELECT 1 FROM langganan_rekonsiliasi WHERE operasi_id=?", (operasi_id,)).fetchone():\n            return False', '',
     "test_subscription_service.py::test_intent_crash_retry_hanya_query", "ledger langganan duplikat"),
    ("receipt", "subscription_store.py", "if lama is not None:\n            if (lama[\"invoice_id\"]", "if False:\n            if (lama[\"invoice_id\"]",
     "test_subscription_store.py::test_receipt_grant_replay_concurrency_restart", "ledger langganan duplikat"),
    ("grant", "subscription_store.py", 'if hasil == "grant":', 'if False:',
     "test_subscription_store.py::test_receipt_grant_replay_concurrency_restart", "receipt ledger tidak sah"),
    ("settlement", "subscription.py", 'bukti.terverifikasi is True and bukti.status == "settlement"', 'bukti.terverifikasi is True',
     "test_subscription_store.py::test_binding_bukti_tidak_cocok_tanpa_efek", "DID NOT RAISE"),
    ("nominal", "subscription.py", 'and type(bukti.rupiah) is int and bukti.rupiah == invoice["rupiah"]', '',
     "test_subscription_store.py::test_binding_bukti_tidak_cocok_tanpa_efek", "DID NOT RAISE"),
    ("owner", "subscription.py", 'and bukti.akun_id == akun_id == invoice["akun_id"]', '',
     "test_subscription_store.py::test_binding_bukti_tidak_cocok_tanpa_efek", "DID NOT RAISE"),
    ("profil", "subscription_store.py", 'if not callable(pemilik_profil) or any(pemilik_profil(p) != akun_id for p in profil):', 'if False:',
     "test_subscription_recovery.py::test_profil_asing_ditolak_sebelum_ledger", "DID NOT RAISE"),
    ("switch", "subscription.py", 'if getattr(self, nama) is not True:', 'if False:',
     "test_midtrans_contract.py::test_default_off_tidak_memanggil_transport", "DID NOT RAISE"),
    ("midtrans_settlement", "midtrans_contract.py", 'data.get("transaction_status") == "settlement" and data.get("status_code") == "200"', 'data.get("status_code") == "200"',
     "test_midtrans_contract.py::test_http200_saja_bukan_lunas", "AssertionError"),
    ("midtrans_nominal", "midtrans_contract.py", 'or nominal_provider(data.get("gross_amount")) != invoice["rupiah"]', '',
     "test_midtrans_contract.py::test_binding_nominal_order_currency_channel_merchant", "AssertionError"),
    ("link_grant", "subscription_store.py", 'or g["profil_json"] != inv["profil_json"]', '',
     "test_subscription_recovery.py::test_reader_menolak_link_grant_rusak", "DID NOT RAISE"),
    ("receipt_unique", "subscription_schema.py", "PRIMARY KEY(provider,transaksi_id)", "CHECK(length(transaksi_id)>0)",
     "test_subscription_mutation_guards.py::test_unique_receipt_sumber_sql", "DID NOT RAISE"),
    ("grant_unique", "subscription_schema.py", "UNIQUE(akun_id,urutan),\n    UNIQUE(provider,transaksi_id),", "UNIQUE(provider,transaksi_id),",
     "test_subscription_mutation_guards.py::test_unique_grant_periode_sql", "DID NOT RAISE"),
]


@pytest.mark.parametrize("nama,modul,lama,baru,test,pesan", KASUS, ids=[k[0] for k in KASUS])
def test_guard_merah_lalu_hijau(tmp_path, nama, modul, lama, baru, test, pesan):
    mesin = tmp_path / "mesin"
    tes = mesin / "__tests__"
    tes.mkdir(parents=True)
    for p in AKAR.glob("*.py"):
        shutil.copy2(p, mesin / p.name)
    # Dependensi test helper hanya source sintetis, bukan seluruh workspace.
    for nama_test in ("conftest.py", "test_subscription.py", "test_subscription_store.py",
                      "test_midtrans_contract.py", "test_midtrans_sandbox.py", "test_subscription_http.py", "http_test_kit.py", "test_subscription_recovery.py",
                      "test_subscription_mutation_guards.py", "test_admin_backup.py",
                      "test_profile_release_probe.py", "test_release_image.py", "test_subscription_service.py", "test_subscription_registration.py"):
        shutil.copy2(AKAR / "__tests__" / nama_test, tes / nama_test)
    p = mesin / modul
    asli = p.read_text()
    assert asli.count(lama) == 1
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(mesin)}
    argv = [sys.executable, "-B", "-m", "pytest", str(tes / test), "-q", "-W", "error", "-p", "no:cacheprovider"]
    p.write_text(asli.replace(lama, baru))
    merah = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert merah.returncode == 1, merah.stdout + merah.stderr
    assert pesan in merah.stdout, merah.stdout + merah.stderr
    assert "ImportError" not in merah.stdout and "ModuleNotFoundError" not in merah.stdout
    p.write_text(asli)
    hijau = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

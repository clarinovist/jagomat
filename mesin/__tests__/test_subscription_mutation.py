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
                      "test_midtrans_contract.py", "test_subscription_recovery.py",
                      "test_subscription_mutation_guards.py", "test_admin_backup.py",
                      "test_profile_release_probe.py", "test_release_image.py"):
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

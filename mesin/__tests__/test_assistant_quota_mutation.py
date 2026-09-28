"""Mutation guard kuota di salinan sementara; merah assertion domain lalu pulih."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

MODUL = (
    "assistant_entitlement.py", "assistant_quota_schema.py", "assistant_quota_store.py",
    "subscription.py", "subscription_packages.py", "subscription_package_schema.py",
    "subscription_package_store.py", "subscription_store.py", "subscription_schema.py",
    "admin_store.py", "admin_contracts.py", "admin_launch_schema.py",
)
KASUS = (
    ("atomic_reserve", "assistant_quota_store.py", 'kon.execute("BEGIN IMMEDIATE")',
     'kon.execute("SELECT 1")', "test_dua_tab_unit_terakhir_hanya_satu_atomic", "AssertionError"),
    ("replay", "assistant_quota_store.py", 'return Reservasi(False, row["status"], ikatan)',
     'return Reservasi(True, row["status"], ikatan)',
     "test_replay_restart_tidak_outbound_atau_charge_ganda", "AssertionError"),
    ("binding", "assistant_quota_store.py", 'if row is None or _ikatan(row) != ikatan:',
     'if row is None:', "test_binding_operasi_harus_exact_tanpa_efek", "DID NOT RAISE"),
    ("trial_nonrepeat", "assistant_entitlement.py", 'batas_trial = paket.akhir_coba(snapshot.trial_mulai)',
     'batas_trial = paket.akhir_coba(snapshot.transisi_mulai)',
     "test_trial_tepat_deadline_prepay_dan_tidak_diulang", "AssertionError"),
    ("sumber_ledger", "assistant_quota_store.py", 'if sumber is not None and sumber[0] != hak.entitlement_sidik:',
     'if False:', "test_trial_beku_tidak_direset_bahkan_lintas_fitur or test_satu_grant_snapshot_bergeser", "DID NOT RAISE"),
    ("hash_pemakaian", "assistant_entitlement.py", 'or re.fullmatch(r"[0-9a-f]{64}", item.jendela_id) is None',
     'or False', "test_hash_pemakaian_nonhex_failclosed_bukan_jatah_utuh", "AssertionError"),
    ("account_shared", "assistant_quota_store.py", 'pemakaian=_pemakaian(kon, akun_id), penegakan=True',
     'pemakaian=(), penegakan=True', "test_kuota_akun_dipakai_bersama_lintas_profil", "DID NOT RAISE"),
    ("unknown", "assistant_quota_store.py", 'and status != "unknown" and not rekonsiliasi:',
     'and False:', "test_unknown_tetap_reserved_bukan_release_atau_retry_otomatis", "DID NOT RAISE"),
    ("hasil_durable", "assistant_quota_store.py", 'if hasil_valid_tersimpan is not True:',
     'if False:', "test_release_known_no_output_dan_finalisasi_perlu_hasil_tersimpan", "DID NOT RAISE"),
    ("release_bukti", "assistant_quota_store.py", 'if tanpa_output_terbukti is not True:',
     'if False:', "test_release_known_no_output_dan_finalisasi_perlu_hasil_tersimpan", "DID NOT RAISE"),
)


@pytest.mark.parametrize("nama,modul,lama,baru,tes,pesan", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_kuota_merah_dan_pulih(tmp_path, nama, modul, lama, baru, tes, pesan):
    akar = Path(__file__).resolve().parents[1]
    for berkas in MODUL:
        shutil.copy2(akar / berkas, tmp_path / berkas)
    for berkas in ("test_assistant_entitlement_domain.py", "test_assistant_quota_store.py"):
        shutil.copy2(Path(__file__).with_name(berkas), tmp_path / berkas)
    target = tmp_path / modul
    asli = target.read_text()
    # Replay reserve dan lookup sama-sama harus false; matikan hanya guard reserve.
    jumlah = 2 if nama == "replay" else 1
    assert asli.count(lama) == jumlah
    argv = [sys.executable, "-B", "-m", "pytest", "test_assistant_entitlement_domain.py",
            "test_assistant_quota_store.py", "-k", tes, "-q", "-W", "error", "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(tmp_path)}
    target.write_text(asli.replace(lama, baru, 1))
    merah = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert merah.returncode == 1 and pesan in merah.stdout, merah.stdout + merah.stderr
    assert "ImportError" not in merah.stdout and "ModuleNotFoundError" not in merah.stdout
    assert "OperationalError" not in merah.stdout and "IntegrityError" not in merah.stdout
    target.write_text(asli)
    hijau = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

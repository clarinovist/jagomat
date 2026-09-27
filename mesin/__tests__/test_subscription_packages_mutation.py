"""Mutasi guard finansial paket v2 di salinan temp, bukan source/data pengguna."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KASUS = (
    ("jatah_promo", "periode_dibayar < (3 if bulan == 1 else 1)", "periode_dibayar < 99",
     "test_promo_tepat_jatah_periode_dibayar", "AssertionError"),
    ("eligibility", "promo = peserta_promo and periode_dibayar", "promo = True and periode_dibayar",
     "test_harga_normal_promo_tambahan_profil", "AssertionError"),
    ("nominal", "(jumlah_profil - 1) *", "0 *",
     "test_harga_normal_promo_tambahan_profil", "AssertionError"),
    ("tipe_bilangan", "type(nilai) is not int or not minimum <= nilai <= maksimum", "not minimum <= nilai <= maksimum",
     "test_input_harga_tidak_sah_ditolak", "DID NOT RAISE"),
    ("versi", "if versi != VERSI:", "if False:",
     "test_input_harga_tidak_sah_ditolak", "DID NOT RAISE"),
    ("refund_deadline", "diajukan_pada < akhir else", "diajukan_pada <= akhir else",
     "test_refund_tahunan_deadline_eksklusif", "AssertionError"),
    ("kuota_paket", "paket.kuota)", "PAKET[1].kuota)",
     "test_kuota_perbulan_bukan_sekaligus_tahunan", "AssertionError"),
    ("trial_deadline", "mulai <= sekarang < akhir else None", "mulai <= sekarang <= akhir else None",
     "test_trial_tepat30hari_bukan_bulan_kalender", "AssertionError"),
)


@pytest.mark.parametrize("nama,lama,baru,tes,pesan", KASUS, ids=[k[0] for k in KASUS])
def test_guard_paket_merah_dan_pulih(tmp_path, nama, lama, baru, tes, pesan):
    akar = Path(__file__).resolve().parents[1]
    for modul in ("subscription_packages.py", "subscription.py"):
        shutil.copy2(akar / modul, tmp_path / modul)
    shutil.copy2(Path(__file__).with_name("test_subscription_packages.py"), tmp_path / "test_paket.py")
    target = tmp_path / "subscription_packages.py"
    asli = target.read_text()
    assert asli.count(lama) == 1
    argv = [sys.executable, "-B", "-m", "pytest", "test_paket.py", "-k", tes,
            "-q", "-W", "error", "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(tmp_path)}
    target.write_text(asli.replace(lama, baru))
    merah = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=25)
    assert merah.returncode == 1 and pesan in merah.stdout, merah.stdout + merah.stderr
    assert "ImportError" not in merah.stdout and "ModuleNotFoundError" not in merah.stdout
    target.write_text(asli)
    hijau = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=25)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

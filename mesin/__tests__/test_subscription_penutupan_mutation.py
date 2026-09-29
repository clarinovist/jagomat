"""Mutasi guard penutupan tagihan di salinan temp; bukan source/data pengguna."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
KASUS = (
    ("kedaluwarsa", "if sekarang < inv[\"kedaluwarsa\"]:", "if False:",
     "test_tutup_wajib_kedaluwarsa_tanpa_efek", "DID NOT RAISE"),
    ("receipt_nol", "if kon.execute(\"SELECT 1 FROM langganan_receipt WHERE invoice_id=?\", (invoice_id,)).fetchone():",
     "if False:",
     "test_tutup_wajib_tanpa_receipt", "DID NOT RAISE"),
    ("penerimaan_penutupan",
     " AND NOT EXISTS(SELECT 1 FROM penutupan_tagihan p WHERE p.invoice_id=i.invoice_id ",
     " AND NOT EXISTS(SELECT 1 FROM penutupan_tagihan p WHERE p.invoice_id=i.invoice_id AND 1=0 ",
     "test_regresi_guard_lama_menahan_lalu_penutupan_beraudit_diterima", "KonflikLangganan"),
    ("guard_receipt_terlambat",
     "AND NOT EXISTS(SELECT 1 FROM langganan_receipt r WHERE r.invoice_id=i.invoice_id)",
     "AND 1=1",
     "test_receipt_terlambat_membatalkan_penutupan_untuk_adopsi", "DID NOT RAISE"),
)


@pytest.mark.parametrize("nama,lama,baru,tes,pesan", KASUS, ids=[k[0] for k in KASUS])
def test_guard_penutupan_merah_dan_pulih(tmp_path, nama, lama, baru, tes, pesan):
    sumber = tmp_path / "mesin"
    sumber.mkdir()
    for f in (AKAR / "mesin").glob("*.py"):
        shutil.copy2(f, sumber / f.name)
    tests = tmp_path / "uji"
    tests.mkdir()
    for f in (AKAR / "mesin" / "__tests__").glob("*.py"):
        shutil.copy2(f, tests / f.name)
    target = sumber / "subscription_store.py"
    asli = target.read_text()
    assert asli.count(lama) == 1
    argv = [sys.executable, "-B", "-m", "pytest", str(tests / "test_subscription_penutupan.py"),
            "-k", tes, "-q", "-W", "error", "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(sumber) + os.pathsep + str(tests),
           "OSN_PBKDF2_ITERASI": "1000", "PYTHONDONTWRITEBYTECODE": "1"}
    def run():
        return subprocess.run(argv, cwd=str(tmp_path), env=env, capture_output=True,
                              text=True, timeout=60)
    target.write_text(asli.replace(lama, baru))
    merah = run()
    assert merah.returncode == 1 and pesan in merah.stdout, merah.stdout + merah.stderr
    assert "ImportError" not in merah.stdout and "ModuleNotFoundError" not in merah.stdout
    target.write_text(asli)
    hijau = run()
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

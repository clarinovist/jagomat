"""Mutation guard integrasi kuota Pendamping pada salinan source terisolasi."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

KASUS = (
    ("enforcement_dual_gate", "assistant_entitlement_runtime.py",
     'return admin_subscription.sakelar_runtime(admin_store.BAWAAN).penegakan is True',
     'return True', "test_enforcement_on_storage_absen_fail_closed_tanpa_membuat_db"),
    ("bypass_admission", "assistant_service.py", "def _cadangkan_kuota(account_id: str, request_id: str, sekarang: int):\n    \"\"\"Satu pintu reservasi layanan sebelum outbound Pendamping.\"\"\"\n    return entitlement.reservasi(",
     "def _cadangkan_kuota(account_id: str, request_id: str, sekarang: int):\n    return None\n    # guard dinonaktifkan\n    entitlement.reservasi(",
     "test_service_reserve_sebelum_provider_dan_finalize_setelah_simpan"),
    ("finalisasi_durable", "assistant_service.py", "def _finalisasi_kuota(ikatan, sekarang: int) -> None:\n    \"\"\"Finalisasi hanya dipanggil sesudah transaksi chat berhasil commit.\"\"\"\n    entitlement.finalisasi(ikatan, sekarang=sekarang)",
     "def _finalisasi_kuota(ikatan, sekarang: int) -> None:\n    return None",
     "test_service_reserve_sebelum_provider_dan_finalize_setelah_simpan"),
)


@pytest.mark.parametrize("nama,modul,lama,baru,tes", KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_runtime_merah_dan_pulih(tmp_path, nama, modul, lama, baru, tes):
    akar = Path(__file__).resolve().parents[1]
    for p in akar.glob("*.py"):
        shutil.copy2(p, tmp_path / p.name)
    sumber_test = (
        "test_assistant_entitlement_runtime.py"
        if nama == "enforcement_dual_gate" else "test_assistant_quota_runtime.py"
    )
    shutil.copy2(Path(__file__).with_name(sumber_test), tmp_path / "test_runtime.py")
    if nama == "enforcement_dual_gate":
        # Fixture HTTP hanya dibutuhkan test lain yang dideseleksi.
        isi_test = (tmp_path / "test_runtime.py").read_text().replace(
            "from test_assistant_inline_http import server\n", ""
        )
        (tmp_path / "test_runtime.py").write_text(isi_test)
    target = tmp_path / modul
    asli = target.read_text()
    assert asli.count(lama) == 1
    argv = [sys.executable, "-B", "-m", "pytest", "test_runtime.py", "-k", tes,
            "-q", "-W", "error", "-p", "no:cacheprovider"]
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(tmp_path),
           "PYTHONDONTWRITEBYTECODE": "1", "OSN_PBKDF2_ITERASI": "1000"}
    target.write_text(asli.replace(lama, baru))
    merah = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert merah.returncode == 1 and "AssertionError" in merah.stdout, merah.stdout + merah.stderr
    target.write_text(asli)
    hijau = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr

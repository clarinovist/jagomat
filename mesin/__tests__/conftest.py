"""Setelan pytest bersama untuk seluruh __tests__/.

Dimuat pytest sebelum modul test apa pun (termasuk http_test_kit) diimpor,
jadi env var yang disetel di sini pasti terbaca auth.py dan sessions.py saat
impor.

PBKDF2 600.000 iterasi (~0,2 detik per hash) adalah pilihan keamanan yang
tepat untuk produksi, tetapi mubazir bila diulang pada tiap setup test —
yang diverifikasi di sini adalah logika palang, bukan kecepatan hash.
Iterasinya diturunkan lewat OSN_PBKDF2_ITERASI; angkanya ikut tersimpan di
berkas sandi uji dan diverifikasi dengan nilai yang sama, sehingga jalur
kodenya identik dengan produksi.
"""

import os
import tempfile

import pytest

os.environ.setdefault("OSN_PBKDF2_ITERASI", "1000")

# Suite fitur menguji matematika terkoreksi secara eksplisit, termasuk data
# yang dibuat saat collection. Test rollout menghapus/mengganti env ini untuk
# menguji default image jembatan dan override warisan. Tidak masuk image app.
os.environ.setdefault("OSN_MATEMATIKA_VERSI", "2")


@pytest.fixture(autouse=True)
def storage_ai_sintetis(monkeypatch):
    """Setiap test memakai ledger AI privat sendiri; tidak pernah /data/nyata."""
    import sys
    from pathlib import Path

    mesin = str(Path(__file__).resolve().parent.parent)
    if mesin not in sys.path:
        sys.path.insert(0, mesin)
    import ai_store

    with tempfile.TemporaryDirectory(prefix="osn-ai-test-") as direktori:
        path = Path(direktori) / "ai-control.db"
        monkeypatch.setenv("AI_BERKAS_DB", str(path))
        ai_store.siapkan(path, sekarang=1)
        yield

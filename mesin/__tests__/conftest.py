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
import sys
from pathlib import Path

import pytest

# Scoped test juga harus dapat mengimpor modul aplikasi saat collection,
# bukan bergantung file test lain lebih dulu menambah sys.path.
_AKAR_MESIN = str(Path(__file__).resolve().parent.parent)
if _AKAR_MESIN not in sys.path:
    sys.path.insert(0, _AKAR_MESIN)

os.environ.setdefault("OSN_PBKDF2_ITERASI", "1000")
# Epoch sintetis stabil untuk fixture; test missing/restore menggantinya eksplisit.
os.environ.setdefault('SENSOR_CONSENT_EPOCH', '0123456789abcdef0123456789abcdef')

# Suite fitur menguji matematika terkoreksi secara eksplisit, termasuk data
# yang dibuat saat collection. Test rollout menghapus/mengganti env ini untuk
# menguji default image jembatan dan override warisan. Tidak masuk image app.
os.environ.setdefault("OSN_MATEMATIKA_VERSI", "2")
# Suite domain menguji writer batch baru; tes recovery menghapus override ini.
os.environ.setdefault("OSN_TEORI_BILANGAN_VERSI", "2")
# Suite warisan mengunci rekonstruksi lama. Suite test_catalog_* dan baseline
# generik menguji writer2 eksplisit; test default menghapus override ini.
os.environ.setdefault("OSN_KATALOG_VERSI", "1")


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


@pytest.fixture(autouse=True)
def jurnal_status_guru_sintetis(monkeypatch):
    """Setiap test memakai jurnal status guru privat sendiri; tidak pernah /data."""
    with tempfile.TemporaryDirectory(prefix="osn-jurnal-guru-test-") as direktori:
        path = Path(direktori) / "guru-status-jurnal.db"
        monkeypatch.setenv("GURU_STATUS_JURNAL_DB", str(path))
        yield


@pytest.fixture(autouse=True)
def jadwal_private_sintetis(monkeypatch):
    """Setiap test memakai DB jadwal private sendiri; tidak pernah /data."""
    with tempfile.TemporaryDirectory(prefix="osn-jadwal-private-test-") as direktori:
        path = Path(direktori) / "jadwal-private.db"
        monkeypatch.setenv("JADWAL_PRIVATE_DB", str(path))
        yield


@pytest.fixture(autouse=True)
def isolasi_pembatas_laju():
    """Pembatas laju menyimpan state global; test tidak boleh mewarisi hitungan.

    Tanpa ini, rangkaian test login dengan sandi salah bisa menyentuh batas
    5 percobaan dan membuat test berikutnya menerima 429 secara misterius —
    pelajaran dari `test_teacher_home.py` pada seleksi CI cepat.
    """
    import laju_masuk
    import sessions

    laju_masuk._reset()
    sessions._reset_rate_limit()
    yield
    laju_masuk._reset()
    sessions._reset_rate_limit()


@pytest.fixture(autouse=True)
def cache_sinyal_nav_bersih():
    """Cache badge sidebar admin (admin_sinyal_cache) berstatus global proses; kosongkan antar-test."""
    import admin_sinyal_cache

    admin_sinyal_cache.kosongkan()
    yield
    admin_sinyal_cache.kosongkan()


# Berkas yang menguji permukaan kode anak lewat HTTP. Gerbang KODE_ANAK_AKTIF mati di kode rilis, jadi berkas-berkas
# ini dinyalakan di sini supaya tesnya tetap menguji fitur yang menyala. Berkas gerbang sendiri (test_guru_tautan_gerbang)
# SENGAJA tidak termasuk: ia harus membuktikan keadaan mati. Berkas lain tidak menyentuh permukaan ini.
BERKAS_GERBANG_KODE_ANAK_NYALA = frozenset({
    "test_guru_tautan_http",
    "test_guru_tautan_http_oracle",
    "test_guru_jadwal_http",
    "test_orang_tua_tautan_http",
    "test_orang_tua_tautan_putusan",
    "test_orang_tua_tautan_guru",
    "test_admin_kode_anak_http",
})


@pytest.fixture(autouse=True)
def gerbang_kode_anak_menyala_untuk_berkas_tautan(request, monkeypatch):
    """Nyalakan KODE_ANAK_AKTIF hanya untuk berkas di BERKAS_GERBANG_KODE_ANAK_NYALA; berkas lain tetap memakai default mati."""
    modul = getattr(request, "module", None)
    nama_berkas = modul.__name__.rsplit(".", 1)[-1] if modul is not None else ""
    if nama_berkas in BERKAS_GERBANG_KODE_ANAK_NYALA:
        import guru_tautan_aturan

        monkeypatch.setattr(guru_tautan_aturan, "KODE_ANAK_AKTIF", True)
    yield

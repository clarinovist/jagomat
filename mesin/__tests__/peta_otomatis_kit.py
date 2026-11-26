"""Kit tes: mematikan penerbitan laporan Peta otomatis untuk berkas tes yang memeriksa keadaan SEBELUM laporan terbit.

Sejak Peta otomatis (26 Nov 2026) pemicu setelah lunas (`peta_otomatis.setelah_lunas`) dan halaman orang tua
(`peta_otomatis.pastikan_untuk_siswa`) menerbitkan laporan langsung. Tes jalur Guru, kartu admin "terlambat", dan kartu
purna butuh order lunas TANPA laporan terbit; berkas itu mengimpor fixture ini (autouse). Perilaku pemicu diuji di
test_peta_otomatis*.py.
"""
import pytest


@pytest.fixture(autouse=True)
def tanpa_terbit_otomatis(monkeypatch):
    import peta_otomatis
    monkeypatch.setattr(peta_otomatis, "setelah_lunas", lambda *a, **k: None)
    monkeypatch.setattr(peta_otomatis, "pastikan_untuk_siswa", lambda *a, **k: peta_otomatis.GAGAL)

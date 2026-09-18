"""Pengunci label estimasi durasi pada pilihan jumlah soal (feedback no.3).

Filia: "aku kasi durasi 1 jam tapi soale tetep 10" — akar kebingungannya:
durasi & jumlah soal terasa sambung-menyambung di UI tapi sebenarnya dua
aturan terpisah. Fix kecil yang menutup kesalahpahaman: tiap opsi jumlah
soal menuliskan estimasi waktunya secara eksplisit (±3 menit per soal),
dan "200 soal (1 jam)"-style klaim tidak boleh kembali.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import teacher_pages  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _html_dashboard(db, peran="guru"):
    """Halaman anak: strip buat sesi + history kini di /anak/<id>."""
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Bilal", pemilik="ortu" if peran == "guru" else "")
        siswa = database.daftar_siswa(kon)[0]
        return teacher_pages.halaman_anak(
            kon, siswa, peran=peran,
            pengguna="ortu" if peran == "guru" else "",
        ).decode()


def test_opsi_jumlah_soal_memuat_estimasi_durasi(db):
    html = _html_dashboard(db)
    # tiap opsi memakai pola "<n> soal (± <m> menit)"
    for n, menit in ((10, 30), (15, 45), (20, 60), (25, 75), (30, 90)):
        opsi = f"{n} soal (± {menit} mnt)"
        assert opsi in html, f"opsi {n} hilang estimasinya"


def test_klaim_satu_jam_tidak_nempel_di_angka_dua_puluh(db):
    """Klaim "20 soal (1 jam)" yang dulu menyesatkan (asumsi 3 mnt/soal)
    tidak dikembalikan mentah-mentah — estimasi kini konsisten 3 mnt/soal."""
    html = _html_dashboard(db)
    assert "20 soal (1 jam)" not in html


def test_opsi_default_tetap_ada(db):
    html = _html_dashboard(db)
    assert 'option value="" selected' in html
    assert '<option value="" selected>Sesuai topik</option>' in html
    assert 'memakai jumlah bawaan topik' in html

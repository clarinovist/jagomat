"""Menu pengguna dropdown di topbar semua halaman pengelola.

Keluhan: kanan atas pasca-login cuma teks polos ("Akun & Siswa", "Keluar")
— tidak terlihat seperti menu. Sekarang setiap halaman guru/admin memuat
<details class="menu-pengguna"> CSS-only: nama + badge peran sebagai
gemboknya, isinya tautan sesuai peran dan tombol keluar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import auth  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

SANDI_A = "sandi-ortu-a-1234567"
SANDI_ADMIN = "sandi-pengelola-9999"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        a = database.tambah_siswa(kon, "BimaA", "P3", pemilik="ortu-a")
        sesi_a = database.buat_sesi(kon, a, seed=7)
    auth.tambah_akun("ortu-a", SANDI_A, "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("pengelola", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI)
    yield s, a, sesi_a
    s.berhenti()


def test_menu_pengguna_di_semua_halaman_guru(server):
    s, a, sesi_a = server
    for jalur in ("/", f"/sesi/{sesi_a}", f"/laporan/{a}", "/akun"):
        kode, isi, _ = s.minta(jalur, auth=("ortu-a", SANDI_A))
        assert kode == 200, f"{jalur} gagal"
        assert '<details class="menu-pengguna">' in isi, (
            f"{jalur} tidak memuat menu pengguna"
        )
        assert "<summary>ortu-a" in isi, f"{jalur} tidak menampilkan nama"
        assert 'action="/keluar"' in isi, f"{jalur} tidak memuat pintu keluar"
        assert 'href="/akun"' in isi, f"{jalur} tidak memuat pintu akun"


def test_menu_guru_tanpa_item_admin(server):
    s, _, _ = server
    _, isi, _ = s.minta("/", auth=("ortu-a", SANDI_A))
    assert "Dashboard admin" not in isi
    assert "Ganti sandi" not in isi


def test_menu_admin_di_panel_dan_halaman_baca(server):
    s, a, sesi_a = server
    for jalur in ("/admin", f"/sesi/{sesi_a}", f"/laporan/{a}"):
        kode, isi, _ = s.minta(jalur, auth=("pengelola", SANDI_ADMIN))
        assert kode == 200, f"{jalur} gagal"
        assert '<details class="menu-pengguna">' in isi
        assert "<summary>pengelola" in isi
        assert 'action="/keluar"' in isi
        assert 'href="/admin"' in isi, f"{jalur} tanpa pintu dashboard admin"
        assert "Ganti sandi" in isi, f"{jalur} tanpa pintu ganti sandi"


def test_menu_admin_tanpa_item_guru(server):
    s, _, _ = server
    _, isi, _ = s.minta("/admin", auth=("pengelola", SANDI_ADMIN))
    assert 'href="/akun">Akun' not in isi, "admin jangan diberi pintu keluarga"


def test_css_menu_pengguna_tersedia():
    import teacher_style

    for kelas in ("menu-pengguna", "menu-isi", "menu-pisah"):
        assert f".{kelas}" in teacher_style.GAYA_GURU


def test_aksi_akun_kembali_ke_section_asal(server):
    """POST /akun tanpa field section: peta aksi->section menentukan di
    section mana hasilnya tampil — aksi anak_baru kembali ke section siswa."""
    s, _, _ = server
    kode, isi, _ = s.minta(
        "/akun",
        auth=("ortu-a", SANDI_A),
        data={"aksi": "anak_baru", "nama": "Rara", "profil_parameter": "P3",
              "sandi_anak": "sandi-rara-12345"},
    )
    assert kode == 200
    assert "Rara" in isi, "pesan sukses tidak tampil"
    assert "Tambah anak" in isi, "hasil aksi tidak kembali ke section siswa"
    assert "Ganti sandi" not in isi

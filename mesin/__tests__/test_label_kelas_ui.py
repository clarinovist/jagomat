"""Label kelas ramah pengguna tanpa mengubah kode internal P3–P6."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import account_pages  # noqa: E402
import database  # noqa: E402
import landing  # noqa: E402
import reports  # noqa: E402
import student_pages  # noqa: E402
import teacher_pages  # noqa: E402
from templates import label_kelas  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _badan(html: str) -> str:
    """Buang CSS agar pencarian hanya memeriksa teks/markup halaman."""
    return html.split("</style>", 1)[-1]


def test_label_kelas_menerjemahkan_level_resmi_dan_menjaga_data_lama():
    assert [label_kelas(level) for level in ("P3", "P4", "P5", "P6")] == [
        "Kelas 3", "Kelas 4", "Kelas 5", "Kelas 6",
    ]
    assert label_kelas("tingkat-lama") == "tingkat-lama"


def test_form_akun_memisahkan_kelas_dan_profil(db):
    with database.buka(db) as kon:
        database.tambah_siswa(kon, "Alya", "P5", pemilik="ortu")
        isi = _badan(account_pages.halaman_akun(
            kon, pengguna="ortu", peran="guru", section="siswa",
        ).decode())

    assert '<option value="P3">Profil P3</option>' in isi
    assert '<option value="5">Kelas 5</option>' in isi
    assert '<option value="" selected>Kelas belum diisi</option>' in isi
    assert ">P3</option>" not in isi
    assert ">P5</option>" not in isi
    assert "<th>Tingkat</th>" not in isi
    assert "<label>Tingkat</label>" not in isi


def test_dashboard_dan_halaman_anak_menampilkan_kelas(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Alya", "P5", pemilik="ortu")
        database.buat_sesi(kon, siswa_id, seed=11, level="P5", topik="statistika")
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
        dashboard = _badan(teacher_pages.halaman_utama_stitch(
            kon, pemilik="ortu", peran="guru",
        ).decode())
        anak = _badan(teacher_pages.halaman_anak(
            kon, siswa, pengguna="ortu", peran="guru",
        ).decode())

    for isi in (dashboard, anak):
        assert "Kelas belum diisi" in isi
        assert ">P5<" not in isi
        assert "(P5)" not in isi


def test_halaman_murid_menampilkan_profil_netral_bukan_kelas_sekolah(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Alya", "P5")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=11, level="P5", topik="statistika",
        )
        daftar = _badan(student_pages.halaman_daftar_sesi_baru(
            kon, siswa_id, "Alya",
        ).decode())
        halaman_kerja = student_pages.halaman_kerja_baru(kon, siswa_id, sesi_id)
    assert halaman_kerja is not None
    kerja = _badan(halaman_kerja.decode())

    for isi in (daftar, kerja):
        assert "Profil P5" in isi
        assert "level P5" not in isi


def test_landing_dan_kebijakan_memakai_istilah_kelas():
    for halaman in (landing.halaman_landing(), landing.halaman_kebijakan()):
        isi = _badan(halaman.decode())
        assert "P3" not in isi
        assert "P4" not in isi
        assert "P5" not in isi
        assert "P6" not in isi
    assert "Kelas 3–6 SD" in _badan(landing.halaman_landing().decode())
    assert "kelas sekolahnya (kelas 3–6)" in _badan(
        landing.halaman_kebijakan().decode()
    )


def test_detail_sesi_guru_dan_cetak_memakai_label_kelas(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Alya", "P5")
        sesi_id = database.buat_sesi(
            kon, siswa_id, seed=11, level="P5", topik="statistika",
        )
        halaman = (
            teacher_pages.halaman_konfirmasi_hapus(kon, sesi_id),
            teacher_pages.halaman_sesi_cetak(kon, sesi_id),
            teacher_pages.halaman_sesi_lampiran(kon, sesi_id),
            teacher_pages.halaman_sesi_stitch(kon, sesi_id),
        )

    for hasil in halaman:
        assert hasil is not None
        isi = _badan(hasil.decode())
        assert "Profil P5" in isi
        assert ">P5<" not in isi
        assert "&middot; P5 &middot;" not in isi


def test_ringkasan_actual_report_tidak_memakai_istilah_level_internal(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Alya", "P5")
        isi = _badan(reports.halaman_laporan(kon, siswa_id).decode())

    ringkasan = isi.split('<div class="kartu ringkasan-laporan">', 1)[1].split(
        "</div>", 1
    )[0]
    assert "level berikutnya" not in ringkasan.lower()
    assert ">P5<" not in ringkasan
    assert "Buka rencana di profil anak" in ringkasan
    assert '<section class="kartu laporan-resume"' in isi


def test_laporan_menampilkan_kelas_sebagai_metadata_topik(db):
    with database.buka(db) as kon:
        siswa_id = database.tambah_siswa(kon, "Alya", "P5")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=11, level="P5", topik="statistika")
        database.tandai_selesai(kon, sesi_id)
        isi = _badan(reports.halaman_laporan(kon, siswa_id, section="riwayat").decode())

    assert '<small>Profil P5</small>' in isi
    assert '<th scope="col">Topik</th>' in isi
    assert 'data-label="Level"' not in isi

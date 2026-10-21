"""Teks permukaan guru memakai istilah netral "pendamping", bukan "orang tua".

Pivot ke guru les in-house: halaman yang dilihat guru tidak boleh bernada
orang tua, tetapi juga tidak mengklaim peran lain. "Pendamping" sudah menjadi
istilah produk ("Ruang pendamping").
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import reports  # noqa: E402
import teacher_corrections  # noqa: E402
import teacher_pages  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402

LARANGAN = (
    "Orang Tua / Guru",
    "RUANG ORANG TUA",
    "orang tua/guru",
    "Untuk orang tua.",
    "Orang tua mulai kesal",
)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    with uji.buka() as kon:
        siswa_id = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="guru")
        sesi_id = database.buat_sesi(kon, siswa_id, seed=812, level="P3", jumlah_soal=2)
        for butir in database.isi_sesi(kon, sesi_id):
            database.simpan_jawaban(kon, butir["sesi_soal_id"], jawaban="999", cara="")
        reports.diagnosa_murid(kon, sesi_id)
        database.tandai_selesai(kon, sesi_id)
    yield uji, siswa_id, sesi_id
    uji.berhenti()


def _ambil(uji, jalur):
    kode, isi, _ = uji.minta(jalur, auth=("guru", SANDI_GURU))
    assert kode == 200
    return isi


def _tanpa_larangan(isi):
    ditemukan = [teks for teks in LARANGAN if teks in isi]
    assert ditemukan == []


def test_topbar_guru_memakai_label_pendamping():
    for ringkas in (False, True):
        topbar = teacher_pages._topbar_stitch("keluarga-a", "guru", ringkas=ringkas)
        assert "Orang Tua / Guru" not in topbar
        assert ">Pendamping</span>" in topbar


def test_label_penilaian_kosong_memakai_pendamping():
    assert teacher_corrections.label_penilaian("") == "Perlu penilaian pendamping"
    assert teacher_corrections.label_penilaian(None) == "Perlu penilaian pendamping"


def test_beranda_guru_tanpa_bahasa_orang_tua(server):
    uji, _, _ = server
    isi = _ambil(uji, "/guru")
    _tanpa_larangan(isi)
    assert "RUANG PENDAMPING" in isi


def test_halaman_sesi_tanpa_bahasa_orang_tua(server):
    uji, _, sesi_id = server
    isi = _ambil(uji, f"/sesi/{sesi_id}")
    _tanpa_larangan(isi)
    assert "Untuk pendamping. Dengarkan cara anak" in isi


def test_sesi_siap_memakai_giliran_pendamping(tmp_path, monkeypatch):
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            siswa_id = database.tambah_siswa(kon, "Anak Siap", "P3", pemilik="guru")
            putaran_id = database.buat_putaran_fokus(kon, siswa_id, "P3")
            sesi_id = database.buat_sesi(kon, siswa_id, seed=812, level="P3", jumlah_soal=1)
            kon.execute(
                "UPDATE sesi SET tujuan = 'pemetaan', putaran_id = ? WHERE id = ?",
                (putaran_id, sesi_id),
            )
        isi = _ambil(uji, f"/sesi/{sesi_id}")
    finally:
        uji.berhenti()
    assert "Pemetaan · giliran pendamping" in isi
    _tanpa_larangan(isi)


def test_panduan_saat_sulit_netral(server):
    uji, siswa_id, _ = server
    isi = _ambil(uji, f"/anak/{siswa_id}?section=rencana")
    _tanpa_larangan(isi)
    assert "Pendamping mulai kesal" in isi

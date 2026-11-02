"""Tautan lembar persiapan guru: label jelas, tetap ada saat pilot aktif."""
from __future__ import annotations

import pytest

import database
import learning_cycle_ui
from http_test_kit import SANDI_GURU, ServerUji
from skill_pilot import LANGSUNG
from skill_pilot_service import revisi

LABEL = "Cetak catatan persiapan guru"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak tautan", "P3", pemilik="guru")
        pilot = database.tambah_siswa(kon, "Anak pilot", "P3", pemilik="guru")
    yield s, anak, pilot
    s.berhenti()


def _isi(hasil):
    kode, isi, _ = hasil
    assert kode == 200
    return isi.decode() if isinstance(isi, bytes) else isi


def _mulai_pilot(s, siswa):
    """Pilot nyata lewat rute guru, bukan sisipan baris tabel."""
    with s.buka() as kon:
        data = {
            "aksi": "mulai",
            "revisi": revisi(kon, siswa),
            "tuntutan": LANGSUNG,
            "profil": "P3",
            "representasi": "geometri_datar-v1",
        }
    kode, isi, _ = s.minta(
        "/siklus/%d/pilot" % siswa, auth=("guru", SANDI_GURU), data=data
    )
    assert kode == 200, isi


def test_beranda_guru_tanpa_pilot_satu_tautan_berlabel_baru(server):
    s, anak, _ = server
    halaman = _isi(
        s.minta("/anak/%d?section=rencana" % anak, auth=("guru", SANDI_GURU))
    )
    assert halaman.count('href="/anak/%d/persiapan"' % anak) == 1
    assert LABEL in halaman
    assert "Cetak persiapan sesi" not in halaman


def test_beranda_guru_dengan_pilot_tetap_satu_tautan_berlabel_baru(server):
    s, _, pilot = server
    _mulai_pilot(s, pilot)
    halaman = _isi(
        s.minta("/anak/%d?section=rencana" % pilot, auth=("guru", SANDI_GURU))
    )
    assert halaman.count('href="/anak/%d/persiapan"' % pilot) == 1
    assert LABEL in halaman
    assert "Cetak persiapan sesi" not in halaman


def test_kartu_rencana_tanpa_tautan_untuk_admin_dan_tanpa_peran(server):
    s, anak, pilot = server
    _mulai_pilot(s, pilot)
    for siswa_id in (anak, pilot):
        with s.buka() as kon:
            siswa = kon.execute(
                "SELECT * FROM siswa WHERE id = ?", (siswa_id,)
            ).fetchone()
            for peran in ("admin", None):
                hasil = learning_cycle_ui.kartu_rencana(
                    kon, siswa_id, siswa=siswa, peran=peran
                )
                assert 'class="kartu-rencana-st"' in hasil
                assert "/persiapan" not in hasil
                assert LABEL not in hasil
                # Pemanggil lain memakai siswa=None: tetap tanpa tautan, tanpa error.
                tanpa_siswa = learning_cycle_ui.kartu_rencana(kon, siswa_id, peran=peran)
                assert "/persiapan" not in tanpa_siswa


def test_halaman_persiapan_anak_pilot_tanpa_form_script_dan_istilah_internal(server):
    s, _, pilot = server
    _mulai_pilot(s, pilot)
    halaman = _isi(
        s.minta("/anak/%d/persiapan" % pilot, auth=("guru", SANDI_GURU))
    )
    assert "Untuk guru" in halaman
    assert "<form" not in halaman
    assert "<script" not in halaman
    assert LANGSUNG not in halaman
    assert 'href="/anak/%d/persiapan"' % pilot not in halaman

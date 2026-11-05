"""Satu alur per sesi (blok D, 5 Nov 2026): tinjauan terkonfirmasi menautkan tab
Perkembangan (satu-satunya pintu masuk laporan orang tua), dan lembar persiapan menyebut
langkah sesudah sesi. Tidak menyentuh laporan orang tua atau bukti belajar."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database  # noqa: E402
import session_prep  # noqa: E402
import teacher_session_pages  # noqa: E402


def _sesi_terkonfirmasi(kon, nama="Anak Alur", pemilik="guru"):
    anak = database.tambah_siswa(kon, nama, pemilik=pemilik)
    sesi = database.buat_sesi(kon, anak, 77, jumlah_soal=3, topik="logika")
    for b in database.isi_sesi(kon, sesi):
        jid = database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban="RAHASIA_JWB_X", cara="hitung")
        database.simpan_diagnosis(kon, jid, benar=False, kode_usulan="K", kode_final="K", alasan="RAHASIA_ALASAN_X")
    database.tandai_selesai(kon, sesi)
    database.konfirmasi_hasil(kon, sesi, "guru", dilewati=set())
    return anak, sesi


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "alur.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def test_hasil_dikonfirmasi_menautkan_laporan_ortu_hanya_untuk_guru(db):
    with database.buka(db) as kon:
        anak, sesi = _sesi_terkonfirmasi(kon)
        html_guru = teacher_session_pages.halaman_sesi_stitch(kon, sesi).decode()
        html_admin = teacher_session_pages.halaman_sesi_stitch(kon, sesi, peran="admin").decode()
        anak2 = database.tambah_siswa(kon, "Anak Belum", pemilik="guru")
        sesi2 = database.buat_sesi(kon, anak2, 78, jumlah_soal=1)
        b = database.isi_sesi(kon, sesi2)[0]
        database.simpan_jawaban(kon, b["sesi_soal_id"], "1", "cara")
        database.tandai_selesai(kon, sesi2)
        html_belum = teacher_session_pages.halaman_sesi_stitch(kon, sesi2).decode()
    assert f'href="/anak/{anak}?section=perkembangan"' in html_guru and "Siapkan laporan untuk orang tua" in html_guru
    assert "/laporan-ortu" not in html_guru  # bukan pintu masuk kedua
    assert "Snapshot" not in html_guru
    assert "Siapkan laporan untuk orang tua" not in html_admin
    assert "Siapkan laporan untuk orang tua" not in html_belum


def test_lembar_persiapan_menyebut_langkah_setelah_sesi(db):
    with database.buka(db) as kon:
        anak, _ = _sesi_terkonfirmasi(kon)
        siswa = kon.execute("SELECT * FROM siswa WHERE id=?", (anak,)).fetchone()
        html = session_prep.halaman_persiapan(kon, siswa, peran="guru").decode()
    assert "Setelah sesi" in html and "Tinjau hasil" in html

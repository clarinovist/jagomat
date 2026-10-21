"""Isi jawaban dari lembar cetak tanpa AI: halaman guru tidak boleh berbahasa AI.

Pilot tatap muka memakai foto lembar sebagai bukti, tetapi gurulah yang
mengetik isinya. Saat pembacaan AI tidak dipakai, teks "bacaan AI", tombol
baca ulang, dan kunci jawaban tidak boleh muncul di halaman konfirmasi.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import attachments  # noqa: E402
import database  # noqa: E402
import llm  # noqa: E402
from http_test_kit import SANDI_GURU, ServerUji  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "uji.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


def _lampiran(kon, nama="AnakManual", pemilik=""):
    sid = database.tambah_siswa(kon, nama, pemilik=pemilik)
    sesi_id = database.buat_sesi(kon, sid, seed=7)
    return sesi_id, database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")


def _kunci_pertama(kon, sesi_id):
    return database.isi_sesi(kon, sesi_id)[0]["kunci"]


def test_mode_manual_tidak_memakai_bahasa_ai(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
    assert "Isi jawaban dari lembar" in html
    assert "bacaan AI" not in html
    assert "Coba baca ulang" not in html
    assert "/baca-ulang" not in html
    assert "Jawaban belum terbaca" not in html


def test_mode_manual_tidak_menampilkan_kunci_sebelum_diisi(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
    assert 'class="kunci"' not in html
    assert "kunci:" not in html


def test_mode_manual_membuka_semua_kartu_soal(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
        jumlah = len(database.isi_sesi(kon, sesi_id))
    kartu = re.findall(r'<details class="kartu-st soal-lampiran"( open)?>', html)
    assert len(kartu) == jumlah
    assert all(kartu)


def test_mode_manual_tetap_punya_form_terapkan_dengan_field_per_soal(db):
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        html = attachments.halaman_konfirmasi(kon, lid, ai_aktif=False).decode()
        butir = database.isi_sesi(kon, sesi_id)
    assert f'action="/lampiran/{lid}/terapkan"' in html
    for b in butir:
        ssid = b["sesi_soal_id"]
        assert f'name="jwb_{ssid}"' in html
        assert f'name="cara_{ssid}"' in html
        assert f'name="blm_{ssid}"' in html


def test_mode_ai_bawaan_tidak_berubah(db):
    """Pemanggil lama tanpa argumen tetap melihat halaman bacaan AI."""
    with database.buka(db) as kon:
        sesi_id, lid = _lampiran(kon)
        html = attachments.halaman_konfirmasi(kon, lid).decode()
        kunci = _kunci_pertama(kon, sesi_id)
    assert "Konfirmasi bacaan AI" in html
    assert "Coba baca ulang dengan AI" in html
    assert f"kunci: {kunci}" in html


def test_ai_pembacaan_aktif_mengikuti_kunci_vision(monkeypatch):
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "", "model": ""})
    assert attachments.ai_pembacaan_aktif() is False
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "kunci-sintetis", "model": ""})
    assert attachments.ai_pembacaan_aktif() is True


def test_pesan_upload_tanpa_ai_tidak_menyebut_ai(db, monkeypatch):
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "", "model": ""})
    with database.buka(db) as kon:
        sesi_id, _ = _lampiran(kon)
        hasil_json, pesan = attachments._ekstraksi_untuk(kon, sesi_id, b"\xff\xd8\xff\xe0isi")
    assert hasil_json == ""
    assert "AI" not in pesan
    assert "Isi jawaban" in pesan


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    yield s
    s.berhenti()


def _buat_lampiran_http(server, tmp_path, monkeypatch):
    akar = tmp_path / "lampiran-http"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakHttpManual", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        (akar / str(sesi_id)).mkdir(parents=True, exist_ok=True)
        (akar / str(sesi_id) / "l.jpg").write_bytes(b"\xff\xd8\xff\xe0isi")
        return database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")


def test_http_guru_tanpa_kunci_vision_melihat_halaman_manual(server, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "", "model": ""})
    lid = _buat_lampiran_http(server, tmp_path, monkeypatch)
    kode, isi, _ = server.minta(f"/lampiran/{lid}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Isi jawaban dari lembar" in isi
    assert "bacaan AI" not in isi
    assert "Coba baca ulang" not in isi


def test_http_guru_dengan_kunci_vision_tetap_melihat_halaman_ai(server, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "kunci-sintetis", "model": ""})
    lid = _buat_lampiran_http(server, tmp_path, monkeypatch)
    kode, isi, _ = server.minta(f"/lampiran/{lid}", auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "Konfirmasi bacaan AI" in isi
    assert "Coba baca ulang dengan AI" in isi


def test_http_terapkan_manual_menyimpan_jawaban_dan_menandai_selesai(server, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "", "model": ""})
    lid = _buat_lampiran_http(server, tmp_path, monkeypatch)
    with server.buka() as kon:
        sesi_id = database.ambil_lampiran(kon, lid)["sesi_id"]
        butir = database.isi_sesi(kon, sesi_id)
    data = {f"jwb_{b['sesi_soal_id']}": "7" for b in butir}
    kode, isi, _ = server.minta(f"/lampiran/{lid}/terapkan",
                                auth=("guru", SANDI_GURU), data=data)
    assert kode == 200
    assert "bacaan AI" not in isi
    with server.buka() as kon:
        tersimpan = kon.execute(
            "SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id "
            "WHERE ss.sesi_id=?", (sesi_id,)).fetchone()[0]
        arsip = kon.execute("SELECT sumber FROM pengiriman_sesi WHERE sesi_id=?",
                            (sesi_id,)).fetchone()
        selesai = kon.execute("SELECT selesai FROM sesi WHERE id=?", (sesi_id,)).fetchone()[0]
    assert tersimpan == len(butir)
    assert arsip["sumber"] == "foto"
    assert selesai


def test_http_lampiran_guru_lain_404_tanpa_efek(server, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "konfigurasi_vision",
                        lambda: {"base_url": "", "api_key": "", "model": ""})
    akar = tmp_path / "lampiran-http"
    monkeypatch.setenv("OSN_DIREKTORI_LAMPIRAN", str(akar))
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, "AnakOrangLain", pemilik="pendamping-lain")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
        lid = database.simpan_lampiran(kon, sesi_id, "l.jpg", hasil_json="")
        butir = database.isi_sesi(kon, sesi_id)
    kode, _, _ = server.minta(f"/lampiran/{lid}", auth=("guru", SANDI_GURU))
    assert kode == 404
    data = {f"jwb_{b['sesi_soal_id']}": "7" for b in butir}
    kode, _, _ = server.minta(f"/lampiran/{lid}/terapkan",
                              auth=("guru", SANDI_GURU), data=data)
    assert kode == 404
    with server.buka() as kon:
        n = kon.execute(
            "SELECT COUNT(*) FROM jawaban j JOIN sesi_soal ss ON ss.id=j.sesi_soal_id "
            "WHERE ss.sesi_id=?", (sesi_id,)).fetchone()[0]
    assert n == 0

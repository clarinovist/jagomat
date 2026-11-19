"""Halaman admin baca-saja `/admin/cek-topik` (topik Cek Kemampuan per kelas). Data sintetis."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_cek_topik_pages as ui  # noqa: E402
import admin_pages  # noqa: E402
import auth  # noqa: E402
import cek_gratis_skor as skor  # noqa: E402
import question_context  # noqa: E402
import topics  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _login, _minta, server,  # noqa: F401
)
from http_test_kit import SANDI_MURID  # noqa: E402

RUTE = "/admin/cek-topik"


def _baris_kelas(isi: str, kelas: int) -> str:
    awal = isi.index('<th scope="row">Kelas %d' % kelas)
    return isi[awal:isi.index("</tr>", awal)]


def test_admin_melihat_topik_tiap_kelas_dari_konstanta(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, header = _minta(server, RUTE, cookie=token)
    assert kode == 200 and "<script" not in isi
    assert header["Cache-Control"] == "no-store"
    for kelas, daftar in skor.TOPIK_PER_KELAS.items():
        baris = _baris_kelas(isi, kelas)
        for topik_id in daftar:
            assert topics.ambil(topik_id).nama in baris
        assert "<td>%s</td>" % ui.soal_per_topik(kelas) in baris
    for kelas in (1, 2):
        assert topics.ambil(skor.TOPIK_DASAR).nama in _baris_kelas(isi, kelas)
    assert "<td>5</td>" in _baris_kelas(isi, 4)
    assert "<td>15</td>" in _baris_kelas(isi, 1)


def test_mengubah_konstanta_mengubah_halaman(server, monkeypatch):
    baru = dict(skor.TOPIK_PER_KELAS)
    baru[4] = ("statistika",)
    monkeypatch.setattr(skor, "TOPIK_PER_KELAS", baru)
    token = _login(server, "Admin-C", SANDI_ADMIN)
    isi = _minta(server, RUTE, cookie=token)[1]
    baris = _baris_kelas(isi, 4)
    assert topics.ambil("statistika").nama in baris
    assert topics.ambil("pengukuran").nama not in baris
    assert "<td>15</td>" in baris


def test_contoh_jenis_soal_milik_topik_di_level_kelas():
    contoh = ui.contoh_template("pengukuran", 4)
    assert 0 < len(contoh) <= ui.MAKS_CONTOH_PER_TOPIK
    assert len(set(contoh)) == len(contoh)
    assert set(contoh) <= set(topics.ambil("pengukuran").templates)
    assert ui.contoh_template("pengukuran", 1) == ()


def test_404_identik_untuk_anonim_guru_dan_murid_tanpa_efek_samping(server):
    acuan = _minta(server, "/admin/tidak-ada")[:2]
    assert acuan[0] == 404
    anonim = _minta(server, RUTE)[:2]
    guru = _minta(server, RUTE, auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    murid = _minta(server, RUTE, auth_basic=("feby", SANDI_MURID))[:2]
    assert anonim == guru == murid == acuan
    token = _login(server, "Admin-C", SANDI_ADMIN)
    with server.buka() as kon:
        sebelum = tuple(kon.iterdump())
    sandi = auth.BERKAS_SANDI.read_bytes()
    assert _minta(server, RUTE, cookie=token)[0] == 200
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum
    assert auth.BERKAS_SANDI.read_bytes() == sandi


def test_query_asing_404(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    assert _minta(server, RUTE + "?x=1", cookie=token)[0] == 404


@pytest.mark.parametrize("aktif", [True, False])
def test_status_flag_materi_dasar_mengikuti(server, monkeypatch, aktif):
    monkeypatch.setattr(question_context, "materi_dasar_aktif", lambda: aktif)
    token = _login(server, "Admin-C", SANDI_ADMIN)
    isi = _minta(server, RUTE, cookie=token)[1]
    for kelas in (1, 2):
        baris = _baris_kelas(isi, kelas)
        assert (ui.STATUS_AKTIF in baris) is aktif
        assert ("belum tersedia" in baris) is (not aktif)
    assert "Materi dasar" not in _baris_kelas(isi, 3)


def test_menu_memuat_entri_di_grup_layanan(server):
    assert ("cek-topik", "Topik Cek Kemampuan", "/admin/cek-topik") in admin_pages.SECTION
    assert "cek-topik" in dict(admin_pages.GRUP_SECTION)["Layanan"]
    token = _login(server, "Admin-C", SANDI_ADMIN)
    assert 'href="/admin/cek-topik"' in _minta(server, "/admin", cookie=token)[1]

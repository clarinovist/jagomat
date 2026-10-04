"""Regresi tab ke-4 Perkembangan: satu base URL, guard, dan fallback aman."""
from __future__ import annotations

import database
import profile_history
import report_navigation as N
import pytest

from http_test_kit import SANDI_GURU, ServerUji


@pytest.fixture()
def server_tab(tmp_path, monkeypatch):
    srv = ServerUji(tmp_path, monkeypatch)
    with srv.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Tab", "P3", pemilik="guru")
    yield srv, anak
    srv.berhenti()


def _siswa(server):
    with server.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Tab", "P3", pemilik="guru")
        asing = database.tambah_siswa(kon, "Anak Lain", "P3", pemilik="lain")
    return anak, asing


def test_tab_perkembangan_satu_base_url_dan_aktif(server_tab):
    server, anak = server_tab
    kode, isi, _ = server.minta(
        f"/anak/{anak}?section=perkembangan", auth=("guru", SANDI_GURU))
    assert kode == 200
    nav = isi.split('class="profil-tabs-st"', 1)[1].split("</nav>", 1)[0]
    assert f'href="/anak/{anak}?section=perkembangan" aria-current="page"' in nav
    assert "/laporan/" not in nav
    assert 'id="judul-profil"' in isi
    assert 'id="konten-laporan"' in isi
    assert "Ringkasan perkembangan" in isi


def test_tab_perkembangan_guard_asing_identik_dan_murid_diblokir(server_tab):
    server, anak = server_tab
    with server.buka() as kon:
        asing = database.tambah_siswa(kon, "Asing Tab", "P3", pemilik="lain")
        sebelum = tuple(kon.iterdump())
    a = server.minta(
        f"/anak/{asing}?section=perkembangan", auth=("guru", SANDI_GURU))
    b = server.minta("/anak/999999?section=perkembangan", auth=("guru", SANDI_GURU))
    assert a[0] == b[0] == 404 and a[1] == b[1]
    m = server.minta(
        f"/anak/{anak}?section=perkembangan", auth=("feby", "sandi-feby-12345"))
    assert m[0] in (401, 403) and "konten-laporan" not in m[1]
    with server.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum


def test_tab_perkembangan_query_tak_sah_fallback_aman(server_tab):
    server, anak = server_tab
    kode, isi, _ = server.minta(
        "/anak/%d?section=perkembangan&bagian=penguasaan&materi=<script>&halaman=nan&status=asing"
        % anak, auth=("guru", SANDI_GURU))
    assert kode == 200
    assert "<script>" not in isi
    assert 'id="konten-laporan"' in isi


def test_url_kanonis_tab_dan_alias_lama_ke_tab():
    assert N.tautan_tab(7) == "/anak/7?section=perkembangan"
    assert N.tautan_tab(7, "penguasaan", materi="x") == \
        "/anak/7?section=perkembangan&bagian=penguasaan&materi=x"
    assert "html" not in N.url_laporan(7, "penguasaan", materi="<b>")
    assert N.tujuan_alias_lama(7, "section=riwayat") == "/anak/7?section=riwayat"
    assert "section=perkembangan" in N.tujuan_alias_lama(
        7, "section=penguasaan&tampilan=konteks")
    assert profile_history.parse_filter("section=perkembangan").section == \
        "perkembangan"

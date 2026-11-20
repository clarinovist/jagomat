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
import topik_awam  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _login, _minta, server,  # noqa: F401
)
from http_test_kit import SANDI_MURID  # noqa: E402

RUTE = "/admin/cek-topik"


def _kartu_kelas(isi: str, kelas: int) -> str:
    awal = isi.index('<section class="admin-kartu admin-topik-kelas"><div class="admin-topik-kepala"><h3>Kelas %d</h3>' % kelas)
    return isi[awal:isi.index("</section>", awal)]


def _bagian_tampak(kartu: str) -> str:
    """Isi kartu di luar <details> 'Rincian teknis' (yang terlihat tanpa membuka rincian)."""
    return kartu[:kartu.index('<details class="admin-lipat-kecil">')]


def _rincian(kartu: str) -> str:
    return kartu[kartu.index('<details class="admin-lipat-kecil">'):]


def _ringkasan(isi: str, kelas: int) -> str:
    awal = isi.index('<li class="admin-topik-ringkas"><strong>Kelas %d</strong>' % kelas)
    return isi[awal:isi.index("</li>", awal)]


def test_admin_melihat_topik_tiap_kelas_dengan_nama_ramah_dan_id_di_rincian(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, header = _minta(server, RUTE, cookie=token)
    assert kode == 200 and "<script" not in isi
    assert header["Cache-Control"] == "no-store"
    for kelas, daftar in skor.TOPIK_PER_KELAS.items():
        kartu = _kartu_kelas(isi, kelas)
        for topik_id in daftar:
            assert topik_awam.nama(topik_id) in _bagian_tampak(kartu)  # nama ramah dari sumber yang ada
            assert "<code>%s</code>" % topik_id not in _bagian_tampak(kartu)
            assert "<code>%s</code>" % topik_id in _rincian(kartu)
            assert topics.ambil(topik_id).nama in _rincian(kartu)  # nama resmi tetap tersedia
        assert '<span class="admin-badge">%s soal</span>' % ui.soal_per_topik(kelas) in _bagian_tampak(kartu)
    for kelas in (1, 2):
        assert topik_awam.nama(skor.TOPIK_DASAR) in _bagian_tampak(_kartu_kelas(isi, kelas))
    assert "5 soal</span>" in _bagian_tampak(_kartu_kelas(isi, 4))
    assert "15 soal</span>" in _bagian_tampak(_kartu_kelas(isi, 1))
    assert "Topik diubah lewat rilis, bukan dari sini." in isi


def test_ringkasan_per_kelas_memuat_jumlah_topik_dan_pil_status(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    isi = _minta(server, RUTE, cookie=token)[1]
    for kelas in ui.KELAS_CEK:
        ringkas = _ringkasan(isi, kelas)
        assert "%d topik" % len(ui.topik_kelas(kelas)) in ringkas
        assert 'class="admin-badge' in ringkas


def test_nama_topik_tidak_dikarang_dan_jatuh_ke_nama_resmi_lalu_id(monkeypatch):
    for kelas in ui.KELAS_CEK:
        for topik_id in ui.topik_kelas(kelas):
            assert ui.nama_ramah(topik_id) == topik_awam.NAMA_AWAM[topik_id]
    monkeypatch.delitem(topik_awam.NAMA_AWAM, "statistika")
    assert ui.nama_ramah("statistika") == topics.ambil("statistika").nama
    assert ui.nama_ramah("topik-tak-dikenal") == "topik-tak-dikenal"


def test_mengubah_konstanta_mengubah_halaman(server, monkeypatch):
    baru = dict(skor.TOPIK_PER_KELAS)
    baru[4] = ("statistika",)
    monkeypatch.setattr(skor, "TOPIK_PER_KELAS", baru)
    token = _login(server, "Admin-C", SANDI_ADMIN)
    isi = _minta(server, RUTE, cookie=token)[1]
    kartu = _kartu_kelas(isi, 4)
    assert topik_awam.nama("statistika") in _bagian_tampak(kartu)
    assert topik_awam.nama("pengukuran") not in kartu
    assert "15 soal</span>" in _bagian_tampak(kartu)
    assert "1 topik" in _ringkasan(isi, 4)


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
        for bagian in (_ringkasan(isi, kelas), _kartu_kelas(isi, kelas)):
            assert (ui.LABEL_AKTIF in bagian) is aktif
            assert (ui.LABEL_BELUM_TERSEDIA in bagian) is (not aktif)
        assert ('admin-badge bien">Aktif' in _ringkasan(isi, kelas)) is aktif
    # Kelas 3-6 tidak bergantung pada sakelar materi dasar.
    assert ui.LABEL_AKTIF in _ringkasan(isi, 3) and ui.LABEL_BELUM_TERSEDIA not in _kartu_kelas(isi, 3)


def test_menu_memuat_entri_di_grup_layanan(server):
    assert ("cek-topik", "Topik Cek Kemampuan", "/admin/cek-topik") in admin_pages.SECTION
    assert "cek-topik" in dict(admin_pages.GRUP_SECTION)["Penjualan"]
    token = _login(server, "Admin-C", SANDI_ADMIN)
    assert 'href="/admin/cek-topik"' in _minta(server, "/admin", cookie=token)[1]

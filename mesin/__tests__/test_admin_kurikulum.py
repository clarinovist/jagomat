"""Halaman admin baca-saja `/admin/kurikulum` (peta kurikulum). Data sintetis."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_kurikulum_pages as ui  # noqa: E402
import kurikulum_cp as cp  # noqa: E402
import kurikulum_katalog as kat  # noqa: E402
from admin_komponen import e  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _login, _minta, server,  # noqa: F401
)

RUTE = "/admin/kurikulum"
POLA_NAV = re.compile(r'<nav class="admin-nav admin-menu"[^>]*>(.*?)</nav>', re.S)


def _bagian(isi: str, awal: str, akhir: str) -> str:
    mulai = isi.index(awal)
    return isi[mulai:isi.index(akhir, mulai)] if akhir in isi[mulai:] else isi[mulai:]


def test_anonim_dan_guru_404_identik_tanpa_isi(server):
    acuan = _minta(server, "/admin/tidak-ada")[:2]
    anonim = _minta(server, RUTE)[:2]
    guru = _minta(server, RUTE, auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    assert anonim == guru == acuan and acuan[0] == 404
    assert cp.STATUS_PEMETAAN not in anonim[1]


def test_admin_melihat_ringkasan_celah_dan_tab_aktif(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, header = _minta(server, RUTE, cookie=token)
    assert kode == 200 and "<script" not in isi and header["Cache-Control"] == "no-store"
    assert e(cp.STATUS_PEMETAAN) in isi
    for b in cp.butir_tanpa_grup():
        if b.fase in ui.FASE_SD:
            assert "<code>%s</code>" % b.id in isi
    for entri in kat.KATALOG:
        assert e(ui._nama_topik(entri.topik_id)) in isi
    assert '<a class="admin-tab" href="%s" aria-current="page">Peta kurikulum</a>' % RUTE in isi


def test_query_apa_pun_404(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    assert _minta(server, RUTE + "?x=1", cookie=token)[0] == 404


def test_cek_topik_memuat_bar_tab_dengan_topik_cek_aktif(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    isi = _minta(server, "/admin/cek-topik", cookie=token)[1]
    assert '<a class="admin-tab" href="/admin/cek-topik" aria-current="page">Topik cek</a>' in isi
    assert '<a class="admin-tab" href="%s">Peta kurikulum</a>' % RUTE in isi


def test_menu_menyorot_topik_cek_dan_jumlah_butir_tetap(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    menu = POLA_NAV.search(_minta(server, RUTE, cookie=token)[1]).group(1)
    assert '<a href="/admin/cek-topik" aria-current="page">' in menu
    assert "/admin/kurikulum" not in menu


def test_setiap_grup_katalog_tepat_sekali_di_bagian_topik():
    bagian = ui.halaman().split("<h2>Topik dan grup soal</h2>")[1]
    for entri in kat.KATALOG:
        blok = bagian[bagian.index("<summary>%s " % e(ui._nama_topik(entri.topik_id))):]
        blok = blok[:blok.index("</details>")]
        for kode, nama, _pola in entri.grup:
            kepala = '<p class="kurikulum-kepala">%s <code>%s</code></p>' % (e(nama), e(kode))
            assert blok.count(kepala) == 1, (entri.topik_id, kode)
        assert blok.count("<li>") == len(entri.grup)


def test_setiap_butir_capaian_ada_di_bagian_fase():
    isi = ui.halaman()
    bagian = isi.split("<h2>Butir CP per fase</h2>")[1].split("<h2>Topik dan grup soal</h2>")[0]
    for b in cp.CAPAIAN:
        assert bagian.count("<code>%s</code>" % b.id) == 1
    assert ui.TANPA_SOAL in bagian

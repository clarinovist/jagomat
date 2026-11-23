"""Menu admin baru (redesign Fase B): grup, rute lama, tab Guru & pemakaian, dan Pengaturan layanan satu halaman.

Data SINTETIS. DB sakelar diarahkan ke tmp_path. Rute lama tidak boleh 404 untuk admin, dan tetap 404 identik
untuk non-admin; halaman Pengaturan layanan menampilkan tiap kendali tepat sekali.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_pages  # noqa: E402
import admin_store  # noqa: E402
import feature_switch as fs  # noqa: E402
import support_settings as dukungan  # noqa: E402
from admin_transfer_kit import TAK_ADA, login_admin, minta_admin  # noqa: E402
from cek_http_kit import AKUN_ADMIN  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import NOMOR, minta_mentah, server, tertutup, transfer, keluarga, jam  # noqa: E402,F401

PENGATURAN = "/admin/sakelar"
REKENING = "/admin/pesanan/rekening"
POLA_NAV = re.compile(r'<nav class="admin-nav admin-menu"[^>]*>(.*?)</nav>', re.S)
BATAS_BUTIR_INTI = 12

# Rute admin yang lama dan baru: (jalur, status langsung). 303 diikuti sekali dan harus berakhir 200.
RUTE_ADMIN = (
    ("/admin", 200),
    ("/admin?section=perhatian", 200),
    ("/admin?section=keluarga", 200),
    ("/admin?section=siswa", 200),
    ("/admin?section=pendaftaran", 303),
    ("/admin?section=langganan", 200),
    ("/admin?section=kpi", 200),
    ("/admin?section=riwayat", 200),
    ("/admin?section=operasional", 303),
    ("/admin?section=operasional&dukungan=tersimpan", 303),
    (PENGATURAN, 200),
    ("/admin/pemakaian", 200),
    ("/admin/profil-guru", 200),
    (REKENING, 200),
    ("/admin/pesanan", 200),
    ("/admin/cek-topik", 200),
    ("/admin/lembaga", 200),
    ("/admin/riset", 200),
    ("/admin/ai", 200),
)


@pytest.fixture(autouse=True)
def _db_sakelar_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv(fs.ENV_BERKAS_DB, str(tmp_path / "sakelar.db"))
    for nama in fs.NAMA_SAKELAR:
        monkeypatch.delenv(nama, raising=False)
    fs.bersihkan_cache()
    yield
    fs.bersihkan_cache()


@pytest.fixture()
def admin(transfer):
    return login_admin(transfer)


def _menu(isi: str) -> str:
    return POLA_NAV.search(isi).group(1)


def _utama(isi: str) -> str:
    return isi.split('<main id="konten-admin"', 1)[1].split("</main>", 1)[0]


# --- rute lama tetap sah ---------------------------------------------------------------

@pytest.mark.parametrize("jalur,status", RUTE_ADMIN)
def test_rute_admin_lama_dan_baru_tidak_404_dan_redirect_berakhir_200(transfer, admin, jalur, status):
    kode, _isi, tajuk = minta_admin(transfer, jalur, admin)
    assert kode == status, jalur
    if kode == 303:
        assert minta_admin(transfer, tajuk["Location"].split("#")[0], admin)[0] == 200  # peramban tak mengirim fragmen


@pytest.mark.parametrize("jalur,_status", RUTE_ADMIN)
@pytest.mark.parametrize("akun", [None, ("guru", SANDI_GURU), ("feby", SANDI_MURID)], ids=["anonim", "guru", "murid"])
def test_rute_admin_tetap_404_identik_untuk_non_admin_tanpa_redirect(transfer, jalur, _status, akun):
    acuan = minta_mentah(transfer, TAK_ADA, akun)
    kode, isi, tajuk = minta_mentah(transfer, jalur, akun)
    assert (kode, isi) == (acuan[0], acuan[1]) and kode == 404
    assert "Location" not in tajuk


def test_operasional_lama_dialihkan_303_ke_pengaturan_tanpa_fragmen_dan_dukungan_dibawa(transfer, admin):
    kode, _isi, tajuk = minta_admin(transfer, "/admin?section=operasional", admin)
    assert kode == 303 and tajuk["Location"] == PENGATURAN and "#" not in tajuk["Location"]
    _kode, _isi, tajuk = minta_admin(transfer, "/admin?section=operasional&dukungan=tersimpan", admin)
    assert tajuk["Location"] == PENGATURAN + "?dukungan=tersimpan"
    # Nilai asing tidak dibawa (sama seperti dulu: diabaikan), kunci asing tetap 404 seperti rute /admin lain.
    assert minta_admin(transfer, "/admin?section=operasional&dukungan=aneh", admin)[2]["Location"] == PENGATURAN
    assert minta_admin(transfer, "/admin?section=operasional&x=1", admin)[0] == 404


def test_post_ke_rute_operasional_lama_tidak_dialihkan(transfer, admin):
    """Hanya GET yang dialihkan: POST ke /admin tidak pernah mendapat 303 ke Pengaturan layanan."""
    _kode, _isi, tajuk = minta_admin(transfer, "/admin?section=operasional", admin, {"x": "1"})
    assert tajuk.get("Location") != PENGATURAN


# --- menu ------------------------------------------------------------------------------

def test_menu_inti_tidak_lebih_dari_dua_belas_butir_di_luar_lainnya():
    inti = [sid for grup, daftar in admin_pages.GRUP_SECTION if grup != admin_pages.GRUP_LAINNYA for sid in daftar]
    assert len(inti) <= BATAS_BUTIR_INTI
    html = admin_pages.halaman_admin("ringkasan", "", pengguna="Pengelola").decode()
    menu = _menu(html)
    di_luar_lainnya = menu.split('<li class="admin-nav-grup admin-nav-lainnya">', 1)[0]
    assert di_luar_lainnya.count("<a href=") == len(inti)


def test_grup_lainnya_berisi_tiga_butir_dan_dua_bertanda_akan_dimatikan():
    assert dict(admin_pages.GRUP_SECTION)[admin_pages.GRUP_LAINNYA] == ("langganan", "kpi", "ai")
    html = admin_pages.halaman_admin("ringkasan", "", pengguna="Pengelola").decode()
    lainnya = _menu(html).split('<li class="admin-nav-grup admin-nav-lainnya">', 1)[1]
    assert lainnya.count('<span class="admin-nav-tanda">akan dimatikan</span>') == 2
    assert "<summary" in lainnya and "Lainnya (3)" in lainnya


@pytest.mark.parametrize("section,terbuka", [
    ("ringkasan", False), ("keluarga", False), ("operasional", False), ("pemakaian", False),
    ("pendaftaran", False), ("langganan", True), ("kpi", True), ("ai", True),
])
def test_lainnya_terlipat_dan_terbuka_otomatis_bila_section_aktif_di_dalamnya(section, terbuka):
    html = admin_pages.halaman_admin(section, "", pengguna="Pengelola").decode()
    for nav in re.findall(r'<nav\b[^>]*>(.*?)</nav>', html, re.S):
        assert ("<details open>" in nav) is terbuka
        assert nav.count("<details>") == (0 if terbuka else 1)


def test_riset_konsumen_sementara_di_grup_pengguna():
    # Sementara selama wawancara mulai 23 Nov 2026 (plan redesign-admin E4): pindah ke Lainnya sesudahnya.
    assert "riset" in dict(admin_pages.GRUP_SECTION)["Pengguna"]
    assert "riset" not in dict(admin_pages.GRUP_SECTION)[admin_pages.GRUP_LAINNYA]


def test_titik_perhatian_menempel_di_pengaturan_layanan_bukan_butir_lain():
    from admin_antrean_pages import SinyalNav
    html = admin_pages.halaman_admin("ringkasan", "", pengguna="Pengelola",
                                     sinyal=SinyalNav(total=1, operasional_perhatian=True)).decode()
    menu = _menu(html)
    butir = re.search(r'<li><a href="/admin/sakelar">.*?</a></li>', menu, re.S).group(0)
    assert "Pengaturan layanan" in butir and 'aria-label="Perlu perhatian"' in butir
    assert menu.count('aria-label="Perlu perhatian"') == 1


def test_badge_transfer_menunggu_menempel_di_pesanan_dan_transfer():
    from admin_antrean_pages import SinyalNav
    html = admin_pages.halaman_admin("ringkasan", "", pengguna="Pengelola",
                                     sinyal=SinyalNav(total=2, transfer_menunggu=2)).decode()
    butir = re.search(r'<li><a href="/admin/pesanan">.*?</a></li>', _menu(html), re.S).group(0)
    assert "Pesanan &amp; transfer" in butir and "2<span" in butir


def test_butir_rekening_menaut_ke_anchor_pengaturan_dan_aktif_di_halaman_ubah_rekening(transfer, admin):
    butir = admin_pages.halaman_admin("ringkasan", "", pengguna="P").decode()
    assert 'href="/admin/sakelar#rekening"' in _menu(butir)
    halaman = minta_admin(transfer, REKENING, admin)[1]
    assert '<a href="/admin/sakelar#rekening" aria-current="page">' in _menu(halaman)


# --- tab Guru & pemakaian ---------------------------------------------------------------

@pytest.mark.parametrize("jalur,tab_aktif,tab_lain", [
    ("/admin/pemakaian", "/admin/pemakaian", "/admin/profil-guru"),
    ("/admin/profil-guru", "/admin/profil-guru", "/admin/pemakaian"),
])
def test_tab_guru_dan_pemakaian_di_kedua_halaman_dengan_butir_menu_aktif(transfer, admin, jalur, tab_aktif, tab_lain):
    isi = minta_admin(transfer, jalur, admin)[1]
    utama = _utama(isi)
    assert utama.count('class="admin-tab-baris"') == 1
    assert utama.count('aria-current="page"') == 1
    assert re.search(r'<a class="admin-tab" href="%s" aria-current="page">' % tab_aktif, utama)
    assert re.search(r'<a class="admin-tab" href="%s">' % tab_lain, utama)
    menu = _menu(isi)
    assert '<a href="/admin/pemakaian" aria-current="page">' in menu and "Guru &amp; pemakaian" in menu
    assert menu.count('aria-current="page"') == 1


# --- Pengaturan layanan: satu halaman, tiap kendali sekali --------------------------------

def test_pengaturan_layanan_urutan_bagian_dan_menu_aktif(transfer, admin):
    kode, isi, _t = minta_admin(transfer, PENGATURAN, admin)
    assert kode == 200
    utama = _utama(isi)
    urutan = [utama.index(t) for t in ('id="ringkasan"', 'id="sakelar"', 'id="pembayaran"', 'id="rekening"',
                                       'id="pendaftaran"', 'id="kesehatan"', 'id="kesiapan"', 'id="dukungan"')]
    assert urutan == sorted(urutan)
    assert '<h1 id="judul-admin">Pengaturan layanan</h1>' in isi
    assert '<a href="/admin/sakelar" aria-current="page">' in _menu(isi)
    for sid in ("ringkasan", "sakelar", "pembayaran", "rekening", "pendaftaran", "kesehatan", "kesiapan", "dukungan"):
        assert utama.count('id="%s"' % sid) == 1, sid
    for sid in ("ringkasan", "penjualan", "belajar", "pendaftaran", "kesehatan"):
        assert 'href="#%s"' % sid in utama, sid
    assert 'id="ai"' not in utama and 'href="#ai"' not in utama


def test_kendali_pembayaran_dan_sakelar_masing_masing_sekali_dan_tidak_ada_form_rekening(transfer, admin):
    dukungan.migrasikan(admin_store.BAWAAN, sekarang=2)  # tanpa skema dukungan kartunya "belum siap" tanpa form
    utama = _utama(minta_admin(transfer, PENGATURAN, admin)[1])
    # Dua kendali pembayaran berbeda (transfer rekening = sakelar fitur; tahap Midtrans = rute layanan): sekali masing-masing.
    assert utama.count('action="/admin/layanan/pembayaran"') == 1
    assert utama.count('action="/admin/layanan/dukungan"') == 1
    assert utama.count("<h3>Pembayaran transfer rekening</h3>") == 1  # satu kartu; ringkasan/checklist hanya menautkan
    assert len(re.findall(r'<form[^>]*action="/admin/sakelar"', utama)) == len(fs.NAMA_SAKELAR)  # satu form per sakelar
    assert 'action="/admin/pesanan/rekening"' not in utama  # form berkata sandi tetap hanya di rutenya
    assert utama.count('>Ubah rekening</a>') == 1  # satu tautan ubah di kartu rekening (checklist menautkan terpisah)
    assert "Ubah rekening" in utama


def test_kartu_rekening_menampilkan_nomor_ter_mask_tanpa_nomor_lengkap(transfer, admin):
    utama = _utama(minta_admin(transfer, PENGATURAN, admin)[1])
    kartu = utama.split('id="rekening"', 1)[1].split("</section>", 1)[0]
    assert NOMOR[-4:] in kartu and "*" * (len(NOMOR) - 4) in kartu
    assert NOMOR not in utama and NOMOR not in minta_admin(transfer, PENGATURAN, admin)[1]
    assert "Revisi" in kartu and "<form" not in kartu


def test_baris_ai_tidak_ada_lagi_di_pengaturan_layanan(transfer, admin):
    utama = _utama(minta_admin(transfer, PENGATURAN, admin)[1])
    assert "AI: tidak dipakai" not in utama and "admin-ai-tile" not in utama
    assert 'href="/admin/ai"' not in utama and 'id="ai"' not in utama


def test_tautan_antrean_ke_kesiapan_mendarat_di_bagian_kesiapan(transfer, admin):
    import admin_antrean
    jalur, _, fragmen = admin_antrean.JALUR_KESIAPAN.partition("#")
    assert jalur == PENGATURAN and fragmen == "kesiapan"
    kode, isi, _t = minta_admin(transfer, jalur, admin)
    assert kode == 200 and 'id="%s"' % fragmen in isi


def test_pengaturan_basic_auth_baca_saja_tanpa_form_bagian_lain_tampil(transfer):
    kode, isi, _t = minta_mentah(transfer, PENGATURAN, AKUN_ADMIN)
    assert kode == 200
    utama = _utama(isi)
    assert 'name="reauth"' not in utama and 'name="tinjauan"' not in utama
    for sid in ("ringkasan", "sakelar", "rekening", "pendaftaran", "kesehatan", "kesiapan", "dukungan"):
        assert 'id="%s"' % sid in utama
    assert "<form" not in utama and "<button" not in utama


def test_rekening_belum_dipasang_menjadi_kartu_galat_tanpa_membuang_bagian_lain(tertutup):
    admin = login_admin(tertutup)  # skema rekening belum dimigrasikan di fixture ini
    kode, isi, _t = minta_admin(tertutup, PENGATURAN, admin)
    assert kode == 200
    utama = _utama(isi)
    assert 'id="rekening" role="alert"' in utama and 'id="kesiapan"' in utama and 'id="sakelar"' in utama

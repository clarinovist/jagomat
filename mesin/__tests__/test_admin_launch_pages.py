"""Markup daftar langganan admin: kontrak form tetap, tampilan mengikuti redesain."""
import admin_launch_pages as ui


def _rows():
    return [
        dict(akun_id="akun_a", alias="Edi<x>", mulai=1790000000, peserta_promo=False, asal="transisi"),
        dict(akun_id="akun_b", alias="Lion", mulai=1790086400, peserta_promo=True, asal="transisi"),
    ]


def test_daftar_langganan_kontrak_form_cari_tetap():
    isi = ui.daftar_langganan(_rows(), 2, halaman=1, cari="", csrf="csrf<1>")

    assert isi.count("<form") == 1
    assert '<form class="admin-form-cari" method="post" action="/admin/layanan/cari">' in isi
    assert '<input type="hidden" name="csrf" value="csrf&lt;1&gt;">' in isi
    assert '<input name="cari" maxlength="80" value="">' in isi.replace(' placeholder="Cari akun orang tua"', "")
    assert "<script" not in isi


def test_daftar_langganan_tabel_pill_dan_angka_tercatat():
    isi = ui.daftar_langganan(_rows(), 2, halaman=1, cari="", csrf="x")

    assert isi.count('<th scope="col"') == 4
    assert '<div class="admin-stat"><h2>Keluarga tercatat</h2><div><strong>2</strong></div></div>' in isi
    assert 'href="/admin?section=langganan&amp;id=akun_a"' in isi
    assert "Edi&lt;x&gt;" in isi and "Edi<x>" not in isi
    assert '<span class="admin-badge bien">Ya</span>' in isi
    assert '<span class="admin-badge">Tidak</span>' in isi
    assert "2 tercatat · Halaman 1" in isi
    assert "Diurutkan menurut nama" not in isi
    assert "Panel ini tidak mengaktifkan paywall." in isi


def test_daftar_langganan_tanpa_csrf_tidak_menampilkan_form_cari():
    isi = ui.daftar_langganan(_rows(), 2, halaman=1, cari="", csrf="")

    assert "<form" not in isi


def test_daftar_langganan_pager_post_saat_mencari_dan_tidak_membocorkan_ke_url():
    isi = ui.daftar_langganan(_rows(), 60, halaman=1, cari="rahasia", csrf="c")

    assert 'name="halaman" value="2"' in isi
    assert "cari=" not in isi.replace('name="cari"', "")
    kandidat = [dict(akun_id="akun_z", alias="Siska")]
    dengan = ui.daftar_langganan(_rows(), 2, halaman=1, cari="si", csrf="c", kandidat=kandidat, forms={"akun_z": "<b>aksi</b>"})
    assert "Belum terdaftar di langganan · 1" in dengan and "<b>aksi</b>" in dengan

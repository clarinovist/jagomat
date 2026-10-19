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


import re

import product_analytics as pa


def _laporan(manfaat):
    metrik = (
        pa.Metrik("aktivasi", 3, 5, 60, "Di bawah target", False),
        pa.Metrik("retensi", 1, 5, 25, "Di bawah target", False),
        manfaat,
        pa.Metrik("organik", 0, 0, 20, "Belum ada eksperimen", False),
    )
    return pa.Laporan(metrik, 5, 5, 0, 0, (), True)


def _kpi(laporan):
    return ui.halaman_kpi(
        None if laporan is None else {"koleksi": True}, laporan, None,
        {"dicabut": 0, "kedaluwarsa": 0, "pendaftaran": None}, bulan="2026-10",
    )


def test_kpi_tanpa_respons_menampilkan_strip_bukan_nol_dan_bilah_kosong():
    isi = _kpi(None)

    hero = isi.split('aria-labelledby="h-kpi-manfaat"', 1)[1].split("</section>", 1)[0]
    assert '<strong class="admin-angka admin-redup">—</strong>' in hero
    assert "0.0%" not in hero and "0%</strong>" not in hero
    assert 'role="img" aria-label="Belum ada respons; target 70 persen"' in hero
    assert '<span style="width' not in hero
    assert "Respons</span><strong>0 / 0</strong>" in hero
    assert "Target ≥ 70%" in hero
    assert "Belum ada eksperimen" in isi  # keadaan kosong dipertahankan
    assert isi.index("h-kpi-manfaat") < isi.index("Hasil belum ditampilkan agar tidak terbaca sebagai 0%")


def test_kpi_dengan_respons_mengisi_bilah_sesuai_persentase():
    isi = _kpi(_laporan(pa.Metrik("manfaat", 8, 10, 70, "Memenuhi target", False, 10, 12)))

    hero = isi.split('aria-labelledby="h-kpi-manfaat"', 1)[1].split("</section>", 1)[0]
    assert '<strong class="admin-angka">80.0%</strong>' in hero
    assert 'aria-label="Hasil 80.0 persen; target 70 persen"' in hero
    assert '<span style="width:80.00%"></span><i style="left:70%"></i>' in hero
    assert "Respons</span><strong>10 / 12</strong>" in hero
    assert "Memenuhi target" in hero
    assert "Hasil belum ditampilkan agar tidak terbaca sebagai 0%" not in isi


def test_kpi_tiga_metrik_lain_dan_biaya_tetap_ada_di_grid():
    isi = _kpi(None)
    grid = isi.split('<div class="admin-grid-kpi">', 1)[1]

    for judul in ("Berhasil mencoba", "Memakai kembali", "Tumbuh organik", "Biaya · 2026-10"):
        assert judul in grid
    assert "Merasa terbantu" not in grid
    assert re.search(r'<h2 id="h-kpi-manfaat">Merasa terbantu</h2>', isi)

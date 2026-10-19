"""Filter lanjutan Keluarga/Siswa: kategori, aktivitas, kondisi lainnya; data sintetis."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re

import pytest

import admin_daftar_pages as D
import admin_queries as q
from test_admin_pages import _keluarga, _siswa
from test_admin_queries import _akun, _isi_anomali, db  # noqa: F401

PANEL_BUKA = '<details class="admin-filter-lanjutan" open>'
PANEL_TUTUP = '<details class="admin-filter-lanjutan">'
WIB = timezone(timedelta(hours=7))


def _nama(hasil):
    return {item.pengguna for item in hasil.item}


def test_kategori_menyaring_sesuai_kolom_tabel(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())
    for kategori in ("orang_tua", "pemilik_tanpa_akun"):
        hasil = q.daftar_keluarga(db, konteks, kategori=kategori, per_halaman=100)
        assert hasil.total and all(item.kategori == kategori for item in hasil.item)
    semua = q.daftar_keluarga(db, konteks, per_halaman=100)
    assert q.daftar_keluarga(db, konteks, kategori="semua", per_halaman=100).total == semua.total


def test_aktivitas_menyaring_dan_belum_pernah_berarti_kosong(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())
    kini = datetime(2026, 9, 15, 12, tzinfo=WIB)
    ada = lambda **kw: q.daftar_keluarga(db, konteks, per_halaman=100, sekarang_wib=kini, **kw)
    assert "keluarga-a" in _nama(ada(aktivitas="7_hari"))
    assert "keluarga-b" not in _nama(ada(aktivitas="30_hari"))
    kosong = ada(aktivitas="belum_pernah")
    assert kosong.total and all(item.aktivitas_terakhir is None for item in kosong.item)
    lama = q.daftar_keluarga(
        db, konteks, aktivitas="7_hari", per_halaman=100,
        sekarang_wib=datetime(2026, 10, 30, tzinfo=WIB),
    )
    assert "keluarga-a" not in _nama(lama)


def test_kategori_dan_aktivitas_berpadu_dengan_status_dan_menolak_nilai_asing(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())
    gabung = q.daftar_keluarga(
        db, konteks, kategori="orang_tua", status="normal", aktivitas="belum_pernah", per_halaman=100
    )
    assert all(i.kategori == "orang_tua" and not i.status and i.aktivitas_terakhir is None for i in gabung.item)
    for kw in ({"kategori": "asing"}, {"aktivitas": "kemarin"}):
        with pytest.raises(q.InputQueryTidakSah):
            q.daftar_keluarga(db, konteks, **kw)


def test_panel_keluarga_tanpa_select_lama_dan_chip_membawa_filter():
    isi = D.render_keluarga(replace(_keluarga(), kategori="orang_tua", aktivitas="7_hari"), csrf="sintetis")
    assert '<select form="form-cari-keluarga" name="kategori">' in isi and '<select form="form-cari-keluarga" name="aktivitas">' in isi
    assert 'name="status">' not in isi and 'name="memiliki_anak">' not in isi
    assert '<input type="hidden" name="status" value="semua">' in isi
    assert PANEL_BUKA in isi and 'Terapkan</button>' in isi
    chips = re.findall(r'class="admin-chip"[^>]*href="([^"]+)"', isi)
    assert chips and all("kategori=orang_tua" in h and "aktivitas=7_hari" in h for h in chips)
    assert PANEL_TUTUP in D.render_keluarga(_keluarga(), csrf="sintetis")


def test_panel_siswa_kondisi_lainnya_hanya_tiga_pilihan():
    isi = D.render_siswa(_siswa(), (), csrf="sintetis")
    pilihan = re.search(r'Kondisi lainnya<select form="form-cari-siswa" name="status">(.*?)</select>', isi).group(1)
    assert re.findall(r'value="([^"]*)"', pilihan) == [
        "semua", "owner_empty", "legacy_login_unverified", "legacy_same_name_ambiguous",
    ]
    assert PANEL_TUTUP in isi


@pytest.mark.parametrize("chip", D.STATUS_DARI_CHIP_SISWA)
def test_siswa_nilai_chip_tidak_tertimpa_saat_terapkan(chip):
    isi = D.render_siswa(replace(_siswa(), status=chip), (), csrf="sintetis")
    pilihan = re.search(r'Kondisi lainnya<select form="form-cari-siswa" name="status">(.*?)</select>', isi).group(1)
    assert '<option value="%s" selected>Sesuai chip di atas</option>' % chip in pilihan
    assert '>Semua<' not in pilihan


def test_siswa_kondisi_lainnya_aktif_membuka_panel():
    isi = D.render_siswa(replace(_siswa(), status="owner_empty"), (), csrf="sintetis")
    assert PANEL_BUKA in isi and 'value="owner_empty" selected' in isi


def test_pencarian_pindah_ke_baris_judul_dan_panel_tetap_di_bawah_header():
    import admin_pages as P
    for render, nama in ((lambda: D.render_keluarga(_keluarga(), csrf="x"), "keluarga"),
                         (lambda: D.render_siswa(_siswa(), (), csrf="x"), "siswa")):
        halaman = P.halaman_admin(nama, render(), pengguna="Demo").decode()
        kepala = halaman.split("</header>", 2)[1] if halaman.count("</header>") > 1 else halaman
        header = re.search(r'<header class="admin-kepala admin-kepala-aksi">.*?</header>', halaman, re.S).group(0)
        assert 'name="cari"' in header and "form-cari-" + nama in header
        utama = halaman.split('<main id="konten-admin"', 1)[1]
        assert 'name="cari"' not in utama and "<!--" not in halaman
        assert utama.index("Filter lanjutan") < utama.index("admin-chip-baris")
        assert "admin-bar-atas" not in halaman


def test_buat_akun_ikut_grup_pencarian_di_header_keluarga():
    import admin_pages as P
    halaman = P.halaman_admin("keluarga", D.render_keluarga(_keluarga(), csrf="x"), pengguna="Demo").decode()
    header = re.search(r'<header class="admin-kepala admin-kepala-aksi">.*?</header>', halaman, re.S).group(0)
    assert "Buat akun orang tua" in header and 'class="admin-grup-cari"' in header

"""Fase D (D1 Keluarga, D2 Siswa): kolom, chip, pil netral, akun lama di <details>; data sintetis."""
import re
from dataclasses import replace
from datetime import datetime

import pytest

import admin_daftar_pages as D
import admin_labels as L
import admin_queries as q
from test_admin_http_c import (  # noqa: F401
    SANDI_ADMIN, _hidden, _login, _minta, server,
)
from test_admin_pages import _keluarga, _siswa
from test_admin_queries import _akun, _isi_anomali, db  # noqa: F401

SEKARANG = datetime(2026, 9, 16, 12, tzinfo=L.WIB)


def _nav_chip(isi):
    return re.search(r'<nav class="admin-chip-baris" aria-label="Filter cepat">(.*?)</nav>', isi, re.S).group(1)


def _label_chip(isi):
    return re.findall(r'<a class="admin-chip"[^>]*>([^<]+)(?:<span class="admin-cnt">\d+</span>)?</a>', _nav_chip(isi))


def _form_get(isi):
    return re.findall(r'<form[^>]*method="get"', isi)


@pytest.mark.parametrize("nilai,teks", [
    ("2026-09-16 08:00:00", "Hari ini"),
    ("2026-09-15 23:59:00", "Kemarin"),
    ("2026-09-14 09:00:00", "2 hari lalu"),
    ("2026-08-26 09:00:00", "3 minggu lalu"),
    ("2026-06-01 09:00:00", "3 bulan lalu"),
    ("2024-09-01 09:00:00", "2 tahun lalu"),
    ("2026-09-17 09:00:00", "Hari ini"),  # jam mendatang tidak boleh negatif
    (None, "Belum pernah"),
    ("", "Belum pernah"),
    ("bukan-tanggal", "Belum pernah"),
])
def test_relatif_memakai_hari_kalender_wib(nilai, teks):
    assert L.relatif(nilai, SEKARANG) == teks


def test_judul_hari_hari_ini_kemarin_atau_tanggal_wib():
    assert L.judul_hari("2026-09-16 01:00:00", SEKARANG) == "Hari ini"
    assert L.judul_hari("2026-09-15 23:00:00", SEKARANG) == "Kemarin"
    assert L.judul_hari("2026-09-01 10:00:00", SEKARANG) == "1 Sep 2026"
    assert L.judul_hari("2026-09-16T20:00:00Z", datetime(2026, 9, 17, 12, tzinfo=L.WIB)) == "Hari ini"


def test_keluarga_lima_kolom_dengan_kategori_manusiawi_dan_sesi_di_baris_kecil():
    isi = D.render_keluarga(_keluarga(), csrf="x", sekarang=SEKARANG)
    kolom = re.findall(r'<th scope="col"[^>]*>([^<]+)</th>', isi)
    assert kolom == ["Keluarga", "Siswa", "Aktivitas terakhir", "Kondisi", "Tindakan"]
    assert '<span class="admin-sel-sub">Orang tua · 3 sesi</span>' in isi  # sesi tidak hilang
    assert '<span class="admin-sel-sub">Belum punya pemilik · 0 sesi</span>' in isi
    assert '<span title="13 Sep 2026, 09.00 WIB">3 hari lalu</span>' in isi
    assert '<span class="admin-redup">Belum pernah</span>' in isi
    assert isi.count(">Buka</a>") == 1 and "Kelola akun" not in isi and "Lihat detail" not in isi
    assert 'href="/admin?section=keluarga&amp;id=akun_guru_demo"' in isi


@pytest.mark.parametrize("kategori,label", [
    ("orang_tua", "Orang tua"), ("pengelola", "Akun pengelola"),
    ("pemilik_tanpa_akun", "Belum punya akun"), ("pemilik_kosong", "Belum punya pemilik"),
])
def test_label_kategori_keluarga_manusiawi(kategori, label):
    assert D.LABEL_KATEGORI[kategori] == label


def test_keluarga_chip_sama_di_mode_cari_dan_pencarian_tetap_post():
    umum = D.render_keluarga(_keluarga(), csrf="sintetis", sekarang=SEKARANG)
    cari = D.render_keluarga(_keluarga(cari="rahasia"), csrf="sintetis", sekarang=SEKARANG)
    urutan = ["Semua", "Perlu perhatian", "Belum ada siswa", "Normal"]
    assert _label_chip(umum) == _label_chip(cari) == urutan
    assert 'class="admin-form-cari" method="post" action="/admin">' in cari
    for isi in (umum, cari):
        assert not _form_get(isi)  # tidak ada form GET, jadi tidak ada input pencarian di GET
        assert isi.count('<input name="cari"') == 1  # pager POST hanya membawa hidden, bukan input pencarian lain
        assert "?cari=" not in isi and "&amp;cari=" not in isi
        assert not re.search(r'href="[^"]*cari=', isi)  # tautan chip tidak membawa kata kunci
    assert "rahasia" not in "".join(re.findall(r'href="([^"]*)"', cari))


def test_keluarga_buat_akun_tautan_sekunder_kecil_tanpa_tombol_utama():
    isi = D.render_keluarga(_keluarga(), csrf="x", sekarang=SEKARANG)
    assert '<a class="admin-tautan admin-tautan-kecil" href="/admin/tinjau?aksi=account_teacher_create">Buat akun orang tua</a>' in isi
    assert "admin-tombol\" href" not in isi
    baca_saja = D.render_keluarga(_keluarga(), csrf="x", tampilkan_aksi=False, sekarang=SEKARANG)
    assert "Buat akun orang tua" not in baca_saja


def test_keluarga_filter_lanjutan_di_details_dan_kontrak_hidden_tidak_berubah():
    isi = D.render_keluarga(_keluarga(), csrf="x", sekarang=SEKARANG)
    assert '<details class="admin-filter-lanjutan">' in isi
    assert '<input type="hidden" name="status" value="semua">' in isi
    assert 'name="status">' not in isi  # select kondisi hanya saat mencari (kontrak form POST)
    assert 'name="status">' in D.render_keluarga(_keluarga(cari="x"), csrf="x", sekarang=SEKARANG)


def _siswa_dengan(status, login=None):
    dasar = _siswa().item[0]
    return replace(_siswa(), item=(replace(dasar, status=status, login_pengguna=login),))


def test_siswa_tanpa_login_pil_netral_bukan_peringatan():
    isi = D.render_siswa(_siswa_dengan(("student_without_login",)), (), csrf="x")
    assert '<th scope="col">Cara masuk</th>' in isi and ">Login<" not in isi
    assert '<span class="admin-badge">QR / tautan HP</span>' in isi
    assert '<span class="admin-badge">Tanpa login</span>' in isi
    # Pil kondisi tanpa login tidak boleh bergaya perhatian; hanya status lain yang boleh.
    baris = isi[isi.index("<tbody>"):]
    assert "Tanpa login</span>" in baris and 'perhatian">Belum ada login tertaut' not in baris
    assert "Siswa tanpa login itu normal: anak masuk lewat QR atau tautan dari guru." in isi
    assert "Level soal" in isi and "Profil parameter" not in isi


def test_siswa_dengan_login_pil_punya_login_dan_nama_login_tetap_terlihat():
    isi = D.render_siswa(_siswa_dengan((), login="login<x>"), (), csrf="x")
    assert '<span class="admin-badge">Punya login</span><span class="admin-sel-sub">login&lt;x&gt;</span>' in isi
    assert "QR / tautan HP" not in isi[isi.index("<tbody>"):]


def test_siswa_status_peringatan_lain_tetap_bergaya_perhatian():
    isi = D.render_siswa(_siswa_dengan(("owner_without_account", "student_without_login")), (), csrf="x")
    assert '<span class="admin-badge perhatian">Pemilik tanpa akun</span>' in isi
    assert '<span class="admin-badge">Tanpa login</span>' in isi


def test_siswa_chip_tanpa_login_netral_dengan_nilai_status_lama_dan_stabil_saat_cari():
    umum = D.render_siswa(_siswa(), (), csrf="sintetis")
    cari = D.render_siswa(_siswa(cari="Ari"), (), csrf="sintetis")
    urutan = ["Semua", "Perlu perhatian", "Tanpa login", "Pemilik tanpa akun", "Normal"]
    assert _label_chip(umum) == _label_chip(cari) == urutan
    assert "status=student_without_login" in umum  # tautan antrean Fase A tetap jalan
    assert "Belum ada login tertaut</a>" not in umum
    for isi in (umum, cari):
        assert not _form_get(isi) and isi.count('<input name="cari"') == 1
        assert not re.search(r'href="[^"]*cari=', isi)
    assert 'class="admin-form-cari admin-form-siswa" method="post"' in cari


def test_siswa_akun_lama_dikumpulkan_dalam_details_dengan_hitungan_dan_tautan_filter():
    facet = (("semua", 9), ("owner_empty", 2), ("legacy_login_unverified", 1), ("legacy_same_name_ambiguous", 4))
    isi = D.render_siswa(replace(_siswa(), jumlah_facet=facet, tingkat="P4"), (), csrf="x")
    detail = re.search(r'<details class="admin-rincian admin-akun-lama">(.*?)</details>', isi, re.S).group(1)
    assert "Akun lama yang perlu dicocokkan (7)" in detail
    for kode in D.KONDISI_LAINNYA_SISWA:
        assert "status=%s" % kode in detail and L.LABEL_STATUS[kode] in detail
    assert "owner_empty" not in _nav_chip(isi)  # tidak ada chip kondisi lama di baris chip utama
    assert "tingkat=P4" in detail  # filter lain dipertahankan
    assert '<details class="admin-rincian admin-akun-lama"' in isi and " open" not in isi.split("admin-akun-lama")[1][:3]


def test_siswa_akun_lama_terbuka_bila_difilter_dan_catatan_kecocokan_nama_di_details():
    isi = D.render_siswa(replace(_siswa(), status="legacy_login_unverified"), (), csrf="x")
    assert '<details class="admin-rincian admin-akun-lama" open>' in isi
    assert 'aria-current="true" href="/admin?section=siswa&amp;status=legacy_login_unverified"' in isi
    catatan = re.search(r'<details class="admin-rincian admin-kartu-catatan">(.*?)</details>', isi, re.S).group(1)
    assert "kecocokan nama" in catatan and "periksa sebelum membuat akun baru" in catatan
    assert "periksa sebelum membuat akun baru" not in isi.replace(catatan, "")


def test_siswa_tombol_buka_satu_label_dan_tujuan_sama():
    for status in ((), ("owner_without_account",)):
        isi = D.render_siswa(_siswa_dengan(status), (), csrf="x")
        assert isi.count(">Buka</a>") == 1 and ">Tinjau</a>" not in isi
        assert 'href="/admin?section=siswa&amp;id=7"' in isi


def test_facet_siswa_memuat_hitungan_kondisi_akun_lama(db):
    _isi_anomali(db)
    hasil = q.daftar_siswa(db, q.buat_konteks(db, _akun()), per_halaman=100)
    facet = dict(hasil.jumlah_facet)
    for kode in q.KONDISI_AKUN_LAMA:
        assert facet[kode] == sum(kode in item.status for item in hasil.item)
    assert any(facet[kode] for kode in q.KONDISI_AKUN_LAMA)


def _buat_orang_tua(server, token):
    _, review, _ = _minta(server, "/admin/tinjau?aksi=account_teacher_create", cookie=token)
    _minta(
        server, "/admin/akun", cookie=token,
        data={
            "aksi": "account_teacher_create", "csrf": _hidden(review, "csrf"),
            "tinjauan": _hidden(review, "tinjauan"), "alias": "Audit-D",
            "sandi_baru": "sandi-sintetis-d", "reauth": SANDI_ADMIN,
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )


def test_http_riwayat_dikelompokkan_per_hari_rentang_get_dan_tanpa_alias(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _buat_orang_tua(server, token)
    kode, isi, _ = _minta(server, "/admin?section=riwayat", cookie=token)
    assert kode == 200 and "<h3>Hari ini</h3>" in isi
    assert "Pengelola melakukan <strong>buat orang tua</strong> pada akun baru." in isi
    assert "Filter cepat aksi" not in isi and "Audit-D" not in isi and "sandi-sintetis-d" not in isi
    tautan = re.findall(r'<a class="admin-chip" href="([^"]+)">Hari ini</a>', isi)
    assert len(tautan) == 1
    kode, hasil, _ = _minta(server, tautan[0].replace("&amp;", "&"), cookie=token)
    assert kode == 200 and "<h3>Hari ini</h3>" in hasil
    kode, lampau, _ = _minta(server, "/admin?section=riwayat&mulai=2020-01-01&selesai=2020-01-02", cookie=token)
    assert kode == 200 and "Belum ada tindakan admin." in lampau


def test_http_keluarga_dan_siswa_memakai_kolom_dan_pil_baru(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, keluarga, _ = _minta(server, "/admin?section=keluarga", cookie=token)
    assert kode == 200 and keluarga.count('<th scope="col"') == 5 and ">Buka</a>" in keluarga
    kode, siswa, _ = _minta(server, "/admin?section=siswa", cookie=token)
    assert kode == 200 and "Cara masuk" in siswa and "Siswa tanpa login itu normal" in siswa
    assert "Profil parameter" not in siswa


def test_semua_jenis_target_riwayat_punya_label_manusiawi():
    import admin_contracts
    import admin_riwayat_pages as rw
    assert set(admin_contracts.JENIS_TARGET.values()) <= set(rw.LABEL_TARGET)

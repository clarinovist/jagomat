"""Kontrak renderer murni pusat kendali admin readonly."""

from dataclasses import asdict, replace
from pathlib import Path

import admin_pages as pages
import admin_queries as q
import admin_style


PENGGUNA_BERBAHAYA = 'admin"><script>RAHASIA-XSS</script>'


def _ringkasan():
    return q.RingkasanAdmin(
        2,
        3,
        2,
        4,
        2,
        4,
        1,
        (
            q.HitungPerhatian("student_without_login", 1),
            q.HitungPerhatian("orphan_login", 1),
        ),
        (
            q.LoginBermasalah(
                "akun_login_yatim", "login-yatim", 999, "orphan_login", 0
            ),
        ),
        (
            q.AktivitasSesi(
                9, 7, "Ari <b>", "keluarga&aman", "P4",
                "2026-09-13", "2026-09-13 09:00:00", False,
            ),
            q.AktivitasSesi(
                8, 6, "Bela", "keluarga-b", "P3",
                "2026-09-12", "2026-09-12 09:00:00", True,
            ),
        ),
    )


def _keluarga(cari=""):
    return q.HalamanKeluarga(
        (
            q.KeluargaRingkas(
                "akun_guru_demo", "keluarga<script>", "orang_tua",
                2, 3, "2026-09-13 09:00:00", (),
            ),
            q.KeluargaRingkas(
                None, "", "pemilik_kosong", 1, 0, None, ("owner_empty",),
            ),
        ),
        52,
        1,
        25,
        3,
        cari,
        "semua",
        "semua",
    )


def _siswa(cari=""):
    return q.HalamanSiswa(
        (
            q.SiswaRingkas(
                7, "Ari & <B>", "P4", "keluarga<script>",
                "akun_guru_demo", "orang_tua", None, None,
                3, "2026-09-13 09:00:00", ("student_without_login",),
            ),
        ),
        51,
        1,
        25,
        3,
        cari,
        "",
        "semua",
        "",
    )


def test_frame_enam_menu_privasi_dan_fallback_section():
    isi = pages.render_ringkasan(_ringkasan())
    html = pages.halaman_admin(
        "section-asing", isi, pengguna=PENGGUNA_BERBAHAYA
    ).decode()

    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="id">' in html
    assert '<main id="konten-admin" aria-labelledby="judul-admin">' in html
    assert '<aside class="admin-sidebar">' in html
    assert '<details class="admin-nav-mobile">' in html
    assert '<strong>Ringkasan</strong>' in html
    assert 'aria-label="Bagian panel pengelola"' in html
    navigasi = html.split('<nav class="admin-nav"', 1)[1].split("</nav>", 1)[0]
    assert navigasi.count('aria-current="page"') == 1
    assert '<a href="/admin" aria-current="page">Ringkasan</a>' in navigasi
    for label in (
        "Ringkasan", "Keluarga", "Siswa", "Pendaftaran", "AI", "Riwayat admin"
    ):
        assert label in html
    for label_grup in ("Data pengguna", "Layanan", "Analitik", "Sistem"):
        assert label_grup in navigasi
    assert 'href="/admin/ai"' in html
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in html
    assert '<meta name="referrer" content="no-referrer">' in html
    assert "https://" not in html
    assert "<script" not in html
    assert "onload=" not in html
    assert "onclick=" not in html
    assert PENGGUNA_BERBAHAYA not in html
    assert "&lt;script&gt;RAHASIA-XSS&lt;/script&gt;" in html


def test_ringkasan_tidak_menyebut_progres_dan_escape_nama():
    isi = pages.render_ringkasan(_ringkasan())

    assert "Ari <b>" not in isi
    assert "Ari &lt;b&gt;" in isi
    assert "keluarga&amp;aman" in isi
    assert "Dibatalkan" in isi
    assert "tidak menyatakan anak sedang online, sudah belajar, atau lulus" in isi
    assert '<details class="admin-kartu admin-catatan admin-definisi">' in isi
    assert isi.index("Prioritas saat ini") < isi.index('aria-label="Jumlah administratif"')
    assert 'href="/anak/7"' in isi
    assert 'href="/sesi/9"' in isi


def test_ringkasan_hierarki_dengan_cta_dan_angka_dari_proyeksi():
    isi = pages.render_ringkasan(
        _ringkasan(), status_layanan={"Pendaftaran": "ditutup", "AI": "belum siap"},
        jumlah_antrean=31, operasi_belum_pasti=2, operasi_tertunda=3,
    )
    assert isi.index('Antrean keputusan') < isi.index('Kondisi layanan')
    assert isi.index('Kondisi layanan') < isi.index('aria-label="Jumlah administratif"')
    assert isi.index('aria-label="Jumlah administratif"') < isi.index('Aktivitas sesi terbaru')
    assert '33</strong> temuan tercatat' in isi
    assert '31</strong>' in isi  # Total proyeksi, bukan panjang halaman 25 item.
    assert '2 belum pasti · 3 menunggu hasil' in isi
    assert 'Prioritas 1' in isi and 'Prioritas 2' in isi
    assert 'href="/admin?section=siswa&amp;status=student_without_login"' in isi
    assert 'href="/admin?section=perhatian"' in isi
    assert 'href="#login-perlu-perhatian"' in isi
    assert 'Akses cepat' in isi
    assert 'Aktivitas 7 hari' in isi and 'Seluruh catatan sesi: <strong>4</strong>' in isi
    assert 'Satu siswa atau operasi dapat muncul pada lebih dari satu temuan' in isi
    assert 'Semua normal' not in isi and 'Data contoh' not in isi


def test_ringkasan_kosong_tidak_mengarang_kasus_atau_panel_login():
    data = replace(_ringkasan(), perhatian=(), login_bermasalah=(), aktivitas_terbaru=())
    isi = pages.render_ringkasan(data, jumlah_antrean=0)
    assert '0</strong> temuan tercatat' in isi
    assert 'Tidak ada kondisi administratif yang perlu perhatian' in isi
    assert 'Belum ada aktivitas sesi' in isi
    assert 'id="login-perlu-perhatian"' not in isi
    assert 'Prioritas 1' not in isi
    assert 'Kondisi layanan' in isi and 'belum tersedia' in isi


def test_ringkasan_sumber_tidak_tersedia_bukan_nol_dan_semua_kode_tercakup():
    data = replace(_ringkasan(), perhatian=(
        q.HitungPerhatian('owner_empty', 2),
        q.HitungPerhatian('owner_without_account', 3),
        q.HitungPerhatian('legacy_same_name_ambiguous', 4),
    ))
    isi = pages.render_ringkasan(data, status_layanan={'AI': '<belum siap>'})
    assert '9</strong> temuan tercatat' in isi
    assert 'Jumlah antrean layanan belum tersedia' in isi
    assert '5</strong>' in isi and '4</strong>' in isi
    assert 'Pemilik siswa kosong' in isi and 'Pemilik tidak memiliki akun' in isi
    assert 'Nama warisan cocok ke beberapa siswa' in isi
    assert '&lt;belum siap&gt;' in isi and '<belum siap>' not in isi
    assert 'Semua normal' not in isi


def test_ringkasan_fallback_operasi_dan_login_yatim_punya_jalur_valid():
    data = replace(_ringkasan(), perhatian=(q.HitungPerhatian('orphan_login', 1),))
    isi = pages.render_ringkasan(data, operasi_belum_pasti=2, operasi_tertunda=1)
    assert '4</strong> temuan tercatat' in isi
    assert 'Jumlah antrean layanan belum tersedia' in isi
    assert 'href="/admin?section=riwayat"' in isi
    assert 'href="#login-perlu-perhatian"' in isi
    assert 'id="login-perlu-perhatian"' in isi
    assert '2 belum pasti · 1 menunggu hasil' in isi
    assert 'href="/admin?section=perhatian"' not in isi


def test_sidebar_dan_kartu_memakai_design_system_tanpa_js_baru():
    import design_tokens as T
    isi = pages.halaman_admin('ringkasan', '', pengguna='Pengelola Demo').decode()
    assert 'Pusat kendali' in isi
    assert 'admin-brand-mark' in isi
    assert 'admin-antrean' in admin_style.GAYA_ADMIN
    assert T.FONT_BODY in admin_style.GAYA_ADMIN
    assert T.FONT_HEADLINE in admin_style.GAYA_ADMIN
    assert 'overflow-x: hidden' not in admin_style.GAYA_ADMIN
    # Palang specificity: aturan kartu umum tidak menimpa judul di navy.
    assert '.admin-kartu.admin-prioritas h2 {' in admin_style.GAYA_ADMIN
    assert '.admin-prioritas .admin-antrean-item h3 {' in admin_style.GAYA_ADMIN
    assert '<script' not in isi


def test_daftar_keluarga_search_post_dan_pagination_post_tidak_ke_url():
    isi = pages.render_keluarga(_keluarga(cari="cari%rahasia<&"), csrf="csrf-sintetis")

    assert '<form class="admin-form-cari" method="post" action="/admin">' in isi
    assert 'name="cari"' in isi
    assert "?cari=" not in isi
    assert 'method="post"' in isi
    assert isi.count('name="cari" value="cari%rahasia&lt;&amp;"') == 1
    assert "keluarga<script>" not in isi
    assert "keluarga&lt;script&gt;" in isi
    assert 'id=tidak-tersedia' not in isi
    assert "Pemilik kosong" in isi


def test_daftar_siswa_escape_label_filter_dan_tanpa_tombol_mutasi():
    keluarga = _keluarga().item
    isi = pages.render_siswa(_siswa(cari="Ari<&"), keluarga, csrf="csrf-sintetis")

    assert '<form class="admin-form-cari admin-form-siswa" method="post"' in isi
    assert "Ari &amp; &lt;B&gt;" in isi
    assert "keluarga&lt;script&gt;" in isi
    assert 'href="/admin?section=siswa&amp;id=7"' in isi
    assert "Siswa belum punya login eksplisit" in isi
    for terlarang in (
        "Hapus", "Reset sandi", "Buat akun", "Simpan", "Ubah kelas",
        'type="password"', "confirm(", "onsubmit=",
    ):
        assert terlarang not in isi


def test_detail_menyebut_keluarga_dan_hanya_tautan_existing():
    siswa = _siswa()
    detail_keluarga = q.DetailKeluarga(_keluarga().item[0], siswa)
    detail_siswa = q.DetailSiswa(
        siswa.item[0],
        (q.SesiRingkas(9, "2026-09-13", "2026-09-13 09:00:00", "P4", False),),
    )

    html_keluarga = pages.render_detail_keluarga(detail_keluarga)
    html_siswa = pages.render_detail_siswa(detail_siswa)

    assert "keluarga&lt;script&gt;" in html_keluarga
    assert "Ari &amp; &lt;B&gt;" in html_keluarga
    assert "keluarga&lt;script&gt;" in html_siswa
    assert 'href="/anak/7"' in html_siswa
    assert 'href="/laporan/7"' in html_siswa
    assert 'href="/sesi/9"' in html_siswa
    assert "bukan status belajar atau kelulusan" in html_siswa
    assert '<form' not in html_keluarga
    assert '<form' not in html_siswa


def test_tindakan_tanpa_target_tidak_menyediakan_form_reset():
    """Panel aktif tidak lagi memiliki dropdown target kosong versi lama."""
    isi = pages.form_tindakan_akun("", "guru", "csrf-sintetis", {})
    assert "<form" not in isi
    assert 'name="sandi_baru"' not in isi
    assert '<button' not in isi
    admin = pages.form_tindakan_akun("admin-demo", "admin", "csrf", {
        "account_password_reset": "token-sintetis",
    })
    assert "hanya dapat dibaca" in admin and "<form" not in admin


def test_kelola_akun_satu_pintu_dan_konfirmasi_login_eksplisit():
    daftar = pages.render_keluarga(_keluarga(), csrf='sintetis')
    assert daftar.count('Kelola akun') == 1
    assert daftar.count('href="/admin?section=keluarga&amp;id=akun_guru_demo"') == 1
    detail = pages.render_detail_keluarga(q.DetailKeluarga(_keluarga().item[0], _siswa()))
    assert 'Tinjau penghapusan login' in detail
    assert 'Data siswa dan riwayat tetap tersimpan' in detail
    form = pages.form_tindakan_akun('keluarga<script>', 'guru', 'csrf', {'account_login_delete': 'token'})
    assert 'Hapus akun login orang tua' in form
    assert 'Akun login murid tidak ikut dihapus' in form
    assert 'keluarga&lt;script&gt;' in form
    assert 'name="konfirmasi" value="1" required' in form
    assert 'data-konfirmasi-login=' in form
    assert 'Batal' in form
    assert 'action="/admin/akun"' in form


def test_css_scoped_memakai_token_dan_responsif():
    css = admin_style.GAYA_ADMIN
    sumber = Path(admin_style.__file__).read_text(encoding="utf-8")

    assert "body.admin-readonly" in css
    assert "@media (max-width: 56rem)" in css
    assert "@media (max-width: 32rem)" in css
    assert "min-height: 44px" in css
    assert ":focus-visible" in css
    assert "overflow-x: auto" in css
    assert "#" not in sumber
    assert "url(" not in css
    assert "@import" not in css


def test_renderer_hanya_menerima_dto_tanpa_credential_field():
    objek = [
        _ringkasan(),
        _keluarga(),
        _siswa(),
    ]
    gabung = repr([asdict(item) for item in objek])
    html = (
        pages.render_ringkasan(objek[0])
        + pages.render_keluarga(objek[1])
        + pages.render_siswa(objek[2], objek[1].item)
    )
    for nama in ("password", "sandi", "garam", "kunci", "token", "credential"):
        assert nama not in gabung.casefold()
        assert nama not in html.casefold()

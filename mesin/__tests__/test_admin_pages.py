"""Kontrak renderer murni pusat kendali admin readonly."""

from dataclasses import asdict, replace
from pathlib import Path

import admin_pages as pages
import admin_queries as q
import admin_style
from admin_antrean_pages import AntreanAdmin, ItemAntrean, SinyalNav


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
    assert '<main id="konten-admin" tabindex="-1" aria-labelledby="judul-admin">' in html
    assert '<aside class="admin-sidebar">' in html
    assert '<details class="admin-nav-mobile">' in html
    assert '<strong>Ringkasan</strong>' in html
    assert 'aria-label="Bagian panel pengelola"' in html
    navigasi = html.split('<nav class="admin-nav admin-menu"', 1)[1].split("</nav>", 1)[0]
    assert navigasi.count('aria-current="page"') == 1
    assert '<a href="/admin" aria-current="page"><svg' in navigasi
    assert '<span class="admin-nav-label-menu">Ringkasan</span></a>' in navigasi
    for label in (
        "Ringkasan", "Keluarga", "Siswa", "Pendaftaran", "AI", "Riwayat admin"
    ):
        assert label in html
    for label_grup in ("Pengguna", "Layanan", "Analitik", "Sistem"):
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
    assert isi.index("Perlu ditangani") < isi.index('aria-label="Jumlah administratif"')
    assert 'href="/anak/7?section=riwayat"' in isi
    assert 'href="/sesi/9"' in isi


ANTREAN_DEMO = AntreanAdmin(
    item=(
        ItemAntrean("mendesak", "Pembayaran perlu diperiksa", "menunggu pemeriksaan sejak 26 Sep 2026.",
                    "/admin?section=perhatian", "Periksa invoice", "Invoice", "inv_87e4…6dfec9", 23),
        ItemAntrean("penting", "Backup belum terverifikasi", "Belum ada cutoff.",
                    "/admin?section=operasional", "Buka operasional"),
        ItemAntrean("tinjau", "Ari <b> belum punya login", "Keluarga keluarga&aman.",
                    "/admin?section=siswa&id=7", "Tinjau siswa"),
    ),
    total=3, mendesak=1,
)


def test_ringkasan_hierarki_dengan_cta_dan_angka_dari_proyeksi():
    isi = pages.render_ringkasan(
        _ringkasan(), status_layanan={"Pendaftaran": "ditutup", "AI": "belum siap"}, antrean=ANTREAN_DEMO,
    )
    assert isi.index('Perlu ditangani') < isi.index('Kondisi layanan')
    assert isi.index('Kondisi layanan') < isi.index('aria-label="Jumlah administratif"')
    assert isi.index('aria-label="Jumlah administratif"') < isi.index('Aktivitas sesi terbaru')
    assert isi.count('<li class="admin-antrean-item">') == 3
    assert isi.index('Mendesak') < isi.index('Penting') < isi.index('Tinjau<')
    assert '<code class="admin-ref">inv_87e4…6dfec9</code>' in isi
    assert '<span class="admin-umur admin-umur-mendesak">23 hari</span>' in isi
    assert 'Umur tidak tersedia' in isi
    assert 'Penanggung jawab' not in isi and 'Belum ditugaskan' not in isi
    assert 'type="search"' not in isi and 'Lihat semua' not in isi
    # Hanya item paling mendesak yang solid; sisanya outline.
    assert isi.count('class="admin-tombol"') == 1
    assert isi.count('class="admin-antrean-cta"') == 2
    assert 'class="admin-tombol" href="/admin?section=perhatian">Periksa invoice' in isi
    assert 'href="/admin?section=siswa&amp;id=7"' in isi
    assert 'Ari &lt;b&gt; belum punya login' in isi and 'Ari <b> belum' not in isi
    assert 'Kondisi layanan' in isi and 'Ditutup' in isi and 'Belum siap' in isi
    assert 'Akses cepat' not in isi
    assert 'Sesi 7 hari terakhir' in isi and 'Seluruh catatan sesi: <strong>4</strong>' in isi
    assert 'Semua normal' not in isi and 'Data contoh' not in isi


def test_ringkasan_antrean_memotong_dan_menyebut_sisa():
    banyak = AntreanAdmin(item=ANTREAN_DEMO.item, total=57, mendesak=1)
    isi = pages.render_ringkasan(_ringkasan(), antrean=banyak)
    assert 'dan 54 lainnya' in isi


def test_ringkasan_kosong_tidak_mengarang_kasus_atau_panel_login():
    data = replace(_ringkasan(), perhatian=(), login_bermasalah=(), aktivitas_terbaru=())
    isi = pages.render_ringkasan(data, antrean=AntreanAdmin())
    assert 'Tidak ada kondisi administratif yang perlu perhatian' in isi
    assert 'Belum ada aktivitas sesi' in isi
    assert 'id="login-perlu-perhatian"' not in isi
    assert 'Prioritas 1' not in isi
    assert 'Kondisi layanan' in isi and 'Belum tersedia' in isi


def test_ringkasan_layanan_nada_dan_escape_dan_sumber_hilang():
    isi = pages.render_ringkasan(
        _ringkasan(), status_layanan={'AI': '<belum siap>', 'Backup': ('belum terverifikasi', 'perhatian'),
                                      'Pendaftaran': ('dibuka', 'baik'), 'X': ('y', 'asing')},
        antrean=AntreanAdmin(layanan_tersedia=False),
    )
    assert '&lt;belum siap&gt;' in isi and '<belum siap>' not in isi
    assert 'admin-layanan-perhatian' in isi and 'admin-layanan-baik' in isi
    assert isi.count('admin-layanan-netral') == 2  # nada asing jatuh ke netral
    assert 'Jumlah antrean layanan belum tersedia' in isi


def test_ringkasan_bagian_lama_tetap_ada_sampai_diputuskan():
    isi = pages.render_ringkasan(_ringkasan(), antrean=ANTREAN_DEMO)
    assert 'id="login-perlu-perhatian"' in isi
    assert '<details class="admin-kartu admin-catatan admin-definisi">' in isi
    assert 'href="/admin?section=operasional">Buka operasional' in isi
    assert 'Maksimal 10 catatan' in isi


def test_nav_badge_titik_dan_label_persis_mockup():
    isi = pages.halaman_admin('ringkasan', '', pengguna='Pengelola',
                              sinyal=SinyalNav(total=4, mendesak=1, operasional_perhatian=True)).decode()
    for label in ('Ringkasan', 'Keluarga', 'Siswa', 'Pendaftaran', 'Langganan &amp; invoice',
                  'KPI uji coba', 'Riset konsumen', 'Operasional', 'AI', 'Riwayat admin'):
        assert '<span class="admin-nav-label-menu">%s</span>' % label in isi
    assert isi.count('<svg') >= 20  # ikon per menu, desktop + seluler
    assert 'admin-nav-badge">4<span class="admin-sr"> hal menunggu keputusan' in isi
    assert 'role="img" aria-label="Perlu perhatian"' in isi
    # Toggle seluler membawa badge jumlah item mendesak.
    toggle = isi.split('<details class="admin-nav-mobile">', 1)[1].split('</summary>', 1)[0]
    assert 'admin-nav-badge-mendesak">1<' in toggle
    tanpa = pages.halaman_admin('ringkasan', '', pengguna='Pengelola').decode()
    assert 'admin-nav-badge"' not in tanpa and 'Perlu perhatian' not in tanpa


def test_nav_tanpa_mendesak_tidak_menampilkan_badge_toggle():
    isi = pages.halaman_admin('ringkasan', '', pengguna='P', sinyal=SinyalNav(total=2, mendesak=0)).decode()
    toggle = isi.split('<details class="admin-nav-mobile">', 1)[1].split('</summary>', 1)[0]
    assert 'admin-nav-badge' not in toggle


def test_sidebar_dan_kartu_memakai_design_system_tanpa_js_baru():
    import design_tokens as T
    isi = pages.halaman_admin('ringkasan', '', pengguna='Pengelola Demo').decode()
    assert 'class="admin-alis">Pusat kendali' not in isi
    assert '/aset/mark-sederhana.svg' in isi
    assert 'admin-brand-mark' not in isi
    assert 'admin-antrean' in admin_style.GAYA_ADMIN
    assert T.FONT_LAYAR in admin_style.GAYA_ADMIN
    assert 'overflow-x: hidden' not in admin_style.GAYA_ADMIN
    # Palang specificity: judul prioritas tetap memakai aturan komponennya.
    assert '.admin-kartu.admin-prioritas h2 {' in admin_style.GAYA_ADMIN
    assert '.admin-prioritas .admin-antrean-item h3 {' in admin_style.GAYA_ADMIN
    assert '<script' not in isi


def test_daftar_keluarga_search_post_dan_pagination_post_tidak_ke_url():
    isi = pages.render_keluarga(_keluarga(cari="cari%rahasia<&"), csrf="csrf-sintetis")

    assert 'class="admin-form-cari" method="post" action="/admin">' in isi
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

    assert 'class="admin-form-cari admin-form-siswa" method="post"' in isi
    assert "Ari &amp; &lt;B&gt;" in isi
    assert "keluarga&lt;script&gt;" in isi
    assert 'href="/admin?section=siswa&amp;id=7"' in isi
    assert "Belum ada login tertaut" in isi
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
    assert 'href="/anak/7?section=rencana"' in html_siswa
    assert 'href="/anak/7?section=perkembangan"' in html_siswa
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
    assert "@media (max-width: 51.25rem)" in css
    assert "@media (max-width: 32rem)" in css
    assert "min-height: 44px" in css
    assert ":focus-visible" in css
    assert "overflow-x: auto" in css
    assert "@media screen and (prefers-color-scheme: dark)" in css
    assert "color-scheme: dark" in css
    assert "var(--admin-latar)" in css
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


def _riwayat_contoh():
    from admin_history_store import EntriRiwayat, HalamanRiwayat

    entri = EntriRiwayat(
        "op_1", "admin-demo", "account_password_reset", "akun", "akun_1",
        None, "ok", None, None, None, "ok", 1759488000, (),
    )
    return HalamanRiwayat((entri,), 1, 1, 25, 1)


def test_riwayat_chip_aksi_cepat_tombol_sekunder_dan_lolos_xss():
    isi = pages.render_riwayat(
        _riwayat_contoh(),
        filter_data={"aksi": "account_password_reset", "actor_id": 'jahat"><script>'},
    )
    assert isi.count('class="admin-chip"') == 10
    assert isi.count('aria-current="true"') == 1
    assert 'aria-current="true" href="/admin?section=riwayat' in isi
    assert 'Reset sandi</a>' in isi
    assert '<script>' not in isi
    assert '%3Cscript%3E' in isi
    assert 'class="admin-tombol admin-tombol-sekunder">Saring riwayat<' in isi


def test_riwayat_chip_semua_aksi_aktif_tanpa_filter():
    isi = pages.render_riwayat(_riwayat_contoh(), filter_data={})
    assert isi.count('aria-current="true"') == 1
    assert '>Semua aksi</a>' in isi


def test_chip_daftar_menampilkan_hitungan_facet_dan_chip_normal():
    facet = (
        ("semua", 8), ("perlu_perhatian", 3), ("student_without_login", 1),
        ("owner_without_account", 2), ("normal", 5),
    )
    from dataclasses import replace
    isi = pages.render_siswa(replace(_siswa(), cari="", jumlah_facet=facet), (), csrf="x")

    for label, jumlah in (
        ("Semua", 8), ("Perlu perhatian", 3), ("Belum ada login tertaut", 1),
        ("Pemilik tanpa akun", 2), ("Normal", 5),
    ):
        assert '%s<span class="admin-cnt">%d</span></a>' % (label, jumlah) in isi
    assert "status=normal" in isi and "status=perlu_perhatian" in isi


def test_chip_keluarga_membawa_hitungan_dan_normal():
    from dataclasses import replace
    facet = (("semua", 7), ("perlu_perhatian", 2), ("tanpa_siswa", 1), ("normal", 4))
    isi = pages.render_keluarga(replace(_keluarga(), cari="", jumlah_facet=facet), csrf="x")

    for label, jumlah in (("Semua", 7), ("Perlu perhatian", 2), ("Belum memiliki siswa", 1), ("Normal", 4)):
        assert '%s<span class="admin-cnt">%d</span></a>' % (label, jumlah) in isi


def test_tabel_siswa_avatar_tindakan_dan_scope_kolom():
    isi = pages.render_siswa(_siswa(), (), csrf="x")

    assert isi.count('<th scope="col"') == 7
    assert '<span class="admin-avatar" aria-hidden="true">A</span>' in isi
    assert '>Tinjau</a>' in isi  # siswa berstatus perhatian
    assert 'class="admin-redup">Belum diisi</span>' in isi
    assert "Diurutkan menurut nama." in isi
    normal = q.SiswaRingkas(8, "Budi", "P3", "p", "a", "orang_tua", None, "budi", 0, None, (), 4)
    from dataclasses import replace
    halaman = pages.render_siswa(replace(_siswa(), item=(normal,)), (), csrf="x")
    assert '>Buka</a>' in halaman and '<span class="admin-badge">Normal</span>' in halaman
    assert "Kelas 4" in halaman


def test_keluarga_nama_bukan_tautan_kedua_dan_tanpa_id_tetap_strip():
    kosong = q.KeluargaRingkas(None, "pemilik-x", "pemilik_tanpa_akun", 1, 0, None, ("owner_without_account",))
    from dataclasses import replace
    isi = pages.render_keluarga(replace(_keluarga(), item=(kosong,)), csrf="x")
    assert "<td>—</td>" in isi
    assert 'admin-sel-nama"><span class="admin-avatar" aria-hidden="true">p</span>pemilik-x' in isi


def _status_pendaftaran(dibuka=True, kode="closed_maintenance"):
    import admin_registration as reg
    return reg.StatusPendaftaran(True, dibuka, kode, 3)


def test_pendaftaran_kontrak_form_tidak_berubah():
    isi = pages.render_pendaftaran(_status_pendaftaran(), csrf="csrf<x>", token="tok")

    assert '<form class="admin-form-bagian" method="post" action="/admin/pendaftaran">' in isi
    assert isi.count('<form') == 1
    for tersembunyi in (
        '<input type="hidden" name="aksi" value="registration_config_update">',
        '<input type="hidden" name="csrf" value="csrf&lt;x&gt;">',
        '<input type="hidden" name="tinjauan" value="tok">',
    ):
        assert tersembunyi in isi
    assert 'name="dibuka" value="1" checked' in isi
    assert '<option value="closed_maintenance" selected>' in isi
    assert 'name="reauth" required autocomplete="current-password"' in isi
    assert 'name="judul"' not in isi and '<textarea' not in isi and '<script' not in isi
    assert 'Diminta untuk setiap perubahan pengaturan.' in isi


def test_pendaftaran_status_teks_dan_pratinjau_mengikuti_keadaan():
    buka = pages.render_pendaftaran(_status_pendaftaran(True, "closed_standard"), csrf="c", token="t")
    tutup = pages.render_pendaftaran(_status_pendaftaran(False, "closed_maintenance"), csrf="c", token="t")

    assert "Pendaftaran dibuka</h2>" in buka and "admin-titik-netral" not in buka
    assert "pesan ini belum tampil" in buka
    assert '<div class="admin-pratinjau"><strong>Pendaftaran baru sedang ditutup</strong>' in buka
    assert "Pendaftaran ditutup</h2>" in tutup and "admin-titik-netral" in tutup
    assert 'name="dibuka" value="1" checked' not in tutup
    assert '<div class="admin-pratinjau"><strong>Pendaftaran sementara ditutup untuk pemeliharaan</strong>' in tutup
    assert "Pesan tersimpan. Pratinjau diperbarui setelah pengaturan disimpan." in tutup


def test_riwayat_tab_jenis_dan_kartu_tabel_di_tiga_tampilan():
    import admin_riwayat_pages as rw
    from admin_history_store import HalamanRiwayat

    tindakan = pages.render_riwayat(_riwayat_contoh(), filter_data={})
    kosong = HalamanRiwayat((), 0, 1, 25, 1)
    ai = pages.render_riwayat_ai(kosong, filter_data={"aksi": "ai_synthetic_test"})
    batch = pages.render_audit_batch(kosong, filter_data={"status": "partial"})

    for isi, aktif in ((tindakan, "Tindakan akun dan siswa"), (ai, "Riwayat AI"), (batch, "Riwayat batch")):
        assert 'role="group" aria-label="Jenis riwayat"' in isi
        assert isi.count('aria-current="page"') == 1
        assert 'aria-current="page">%s</a>' % aktif in isi
        assert '<th scope="col"' in isi and "ID ditampilkan lengkap" in isi
        assert 'method="get" action="/admin"' in isi
    assert "1 hasil" in tindakan and "0 hasil" in ai
    assert 'name="sumber" value="ai"' in ai and 'name="sumber" value="batch"' in batch
    assert 'name="status"' in batch and 'name="status"' not in tindakan
    assert '<option value="partial" selected>' in batch
    sekunder = 'class="admin-tombol admin-tombol-sekunder">'
    assert sekunder + 'Saring riwayat<' in ai and sekunder + 'Saring batch<' in batch
    assert rw.nav_riwayat(None).count("aria-current") == 0


def test_riwayat_id_pelaku_lengkap_tanpa_elipsis_dan_catatan_tetap():
    isi = pages.render_riwayat(_riwayat_contoh(), filter_data={})

    assert "admin-demo" in isi and "…" not in isi
    assert "Riwayat dimulai saat fitur aktif; bukan semua aktivitas belajar." in isi
    assert "Tidak ada kejadian lama yang direka ulang." in isi

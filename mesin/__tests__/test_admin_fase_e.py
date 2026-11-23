"""Fase E redesain admin: pendaftaran di Pengaturan layanan, notice 'akan dimatikan', subjudul, sapu istilah."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import admin_pages
import admin_riwayat_pages
import admin_store
from http_test_kit import SANDI_GURU, SANDI_MURID
from test_admin_http_c import server, _minta, _login, _hidden, SANDI_ADMIN  # noqa: F401

NOTICE = "Akan dimatikan (keputusan Pemilik 20 Nov 2026)."
JANGAN_ADA = ("Profil parameter", "profil parameter", "Pagu", "pagu ", "sintetis", "Kendali penghentian",
              "Gerbang pembayaran")


def test_get_section_pendaftaran_redirect_ke_pengaturan_layanan(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, kepala = _minta(server, "/admin?section=pendaftaran", cookie=token)
    assert kode == 303 and kepala["Location"] == "/admin/sakelar#pendaftaran" and isi == ""
    assert kepala["Cache-Control"] == "no-store"


def test_section_pendaftaran_non_admin_tetap_404_identik(server):
    acuan = _minta(server, "/admin?section=asing")[0:2]
    for akun in (None, ("guru", SANDI_GURU), ("feby", SANDI_MURID)):
        hasil = _minta(server, "/admin?section=pendaftaran", auth_basic=akun)[0:2]
        assert hasil == acuan and hasil[0] == 404


def test_pengaturan_layanan_memuat_bagian_pendaftaran_dengan_form_lama(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, _ = _minta(server, "/admin/sakelar", cookie=token)
    assert kode == 200 and 'id="pendaftaran"' in isi and 'href="#pendaftaran"' in isi
    bagian = isi.split('id="pendaftaran"', 1)[1].split("</section>", 1)[0]
    assert "Pendaftaran mandiri: dibuka" in bagian
    assert '<form class="admin-form-bagian" method="post" action="/admin/pendaftaran">' in bagian
    for nama in ("aksi", "csrf", "tinjauan", "dibuka", "pesan_kode", "reauth"):
        assert 'name="%s"' % nama in bagian
    assert "<details><summary>Pratinjau saat ditutup" in bagian
    # urutan: sakelar fitur + rekening (Penjualan dan pembayaran), fitur belajar, lalu pendaftaran
    assert isi.index('id="sakelar"') < isi.index('id="rekening"') < isi.index('id="pendaftaran"')
    assert '<details class="admin-aksi-ubah"><summary class="admin-tombol">Ubah pengaturan pendaftaran…</summary>' in isi


def test_pendaftaran_ditutup_lewat_pengaturan_layanan_prg_ke_halaman_yang_sama(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    panel = _minta(server, "/admin/sakelar", cookie=token)[1].split('id="pendaftaran"', 1)[1]
    kode, _, kepala = _minta(
        server, "/admin/pendaftaran", cookie=token,
        data={"aksi": "registration_config_update", "csrf": _hidden(panel, "csrf"),
              "tinjauan": _hidden(panel, "tinjauan"), "pesan_kode": "closed_maintenance", "reauth": SANDI_ADMIN},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"})
    assert kode == 303
    lokasi = kepala["Location"]
    assert lokasi == "/admin/sakelar?hasil=pendaftaran_tersimpan#pendaftaran"
    kode, isi, _ = _minta(server, lokasi.split("#")[0], cookie=token)
    assert kode == 200 and "Pengaturan pendaftaran mandiri tersimpan." in isi
    assert "Pendaftaran mandiri: ditutup" in isi
    assert '<option value="closed_maintenance" selected>' in isi


def test_hasil_asing_di_pengaturan_layanan_tetap_ditolak(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    assert _minta(server, "/admin/sakelar?hasil=<script>", cookie=token)[0] == 404


def test_pendaftaran_ikut_menyorot_menu_pengaturan_layanan():
    html = admin_pages.halaman_admin("pendaftaran", "", pengguna="Pengelola").decode()
    assert html.count('aria-current="page"') >= 1
    assert 'href="/admin/sakelar" aria-current="page"' in html


def test_notice_akan_dimatikan_di_halaman_ai_dan_kpi(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    for jalur in ("/admin/ai", "/admin?section=kpi"):
        kode, isi, _ = _minta(server, jalur, cookie=token)
        assert kode == 200 and NOTICE in isi, jalur
        assert "jangan membuat pengaturan baru di sini" in isi
        utama = isi.split('<main id="konten-admin"', 1)[1].split(">", 1)[1]
        assert utama.startswith('<p class="admin-kartu admin-catatan" role="note">' + NOTICE), jalur  # paling atas


def test_langganan_subjudul_model_lama_tanpa_ubah_aksi(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, isi, _ = _minta(server, "/admin?section=langganan", cookie=token)
    assert kode == 200
    assert "Model berlangganan lama. Akan jadi baca-saja lalu pensiun setelah langganan aktif terakhir habis." in isi


def test_ai_dan_riwayat_memakai_istilah_baru(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    isi = _minta(server, "/admin/ai", cookie=token)[1]
    teks = re.sub(r"<[^>]+>", " ", isi.split('<main id="konten-admin"', 1)[1])  # teks tampil saja, bukan kelas CSS
    for baru in ("Batas global", "Batas harian (USD)", "Batas permintaan per akun per hari",
                 "Hentikan AI", "Tes koneksi", "Kirim tes koneksi"):
        assert baru in isi, baru
    for lama in JANGAN_ADA:
        assert lama not in teks, lama
    assert admin_riwayat_pages.LABEL_AKSI_AI["ai_synthetic_test"] == "Tes koneksi AI"


def test_label_riwayat_level_soal_akun_lama():
    assert admin_riwayat_pages.LABEL_AKSI["student_level_update"] == "Ubah level soal (akun lama)"

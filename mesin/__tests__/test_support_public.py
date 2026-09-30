"""Kontrak DTO minimum konfigurasi dukungan pada halaman publik."""

import admin_store
import auth
import support_settings as dukungan
from test_admin_http_c import _minta, server


NOMOR = "082137111988"


def _pasang(server):
    dukungan.migrasikan(admin_store.BAWAAN, sekarang=2)
    return dukungan.baca(admin_store.BAWAAN)


def test_footer_faq_lupa_sandi_dan_privasi_memakai_satu_dto(server):
    cfg = _pasang(server)
    assert cfg is not None
    proyeksi = dukungan.proyeksi_publik(cfg)
    for path in ("/", "/lupa-sandi", "/kebijakan-privasi"):
        kode, body, _ = _minta(server, path)
        assert kode == 200
        assert proyeksi.whatsapp_label in body
        assert proyeksi.whatsapp_url in body
        assert proyeksi.jam_layanan_label in body
        assert "maksimal 1 hari kerja" in body
        assert "maksimal 3 hari kerja" in body
        assert "08xx" not in body
    landing = _minta(server, "/")[1]
    assert landing.count(proyeksi.whatsapp_url) >= 2  # FAQ + footer.


def test_url_whatsapp_tidak_mengandung_identitas_keluarga(server):
    cfg = _pasang(server)
    proyeksi = dukungan.proyeksi_publik(cfg)
    for path, auth_basic in (("/", None), ("/lupa-sandi", None),
                             ("/kebijakan-privasi", None)):
        body = _minta(server, path, auth_basic=auth_basic)[1]
        assert proyeksi.whatsapp_url in body
        assert "Anak C" not in body and "Ortu-C" not in body
        assert "text=" not in body and "Nama%20anak" not in body
    assert "text=" not in proyeksi.whatsapp_url and "?" not in proyeksi.whatsapp_url


def test_reader_hilang_rusak_menyembunyikan_link_dan_janji_operasional(server):
    # Fixture HTTP belum memasang schema dukungan secara default.
    for path in ("/", "/lupa-sandi", "/kebijakan-privasi"):
        kode, body, _ = _minta(server, path)
        assert kode == 200
        assert "wa.me" not in body and "08xx" not in body
        assert "Dukungan pengguna belum tersedia" in body
        assert "maksimal 1 hari kerja" not in body

    dukungan.migrasikan(admin_store.BAWAAN, sekarang=2)
    with admin_store._transaksi(admin_store.BAWAAN) as kon:
        kon.execute("PRAGMA ignore_check_constraints=ON")
        kon.execute("UPDATE dukungan_konfigurasi SET whatsapp_digits='08xx-xxxx-xxxx'")
    for path in ("/", "/lupa-sandi", "/kebijakan-privasi"):
        body = _minta(server, path)[1]
        assert "wa.me" not in body and "08xx" not in body
        assert "Dukungan pengguna belum tersedia" in body


def test_halaman_publik_tidak_membawa_data_akun_ke_reader(server, monkeypatch):
    _pasang(server)
    asli = dukungan.baca_publik
    panggilan = []
    def baca(path):
        panggilan.append(path)
        return asli(path)
    monkeypatch.setattr(dukungan, "baca_publik", baca)
    auth_sebelum = auth.BERKAS_SANDI.read_bytes()
    for path in ("/", "/lupa-sandi", "/kebijakan-privasi"):
        assert _minta(server, path)[0] == 200
    assert len(panggilan) == 3
    assert auth.BERKAS_SANDI.read_bytes() == auth_sebelum

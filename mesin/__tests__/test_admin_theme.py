"""Kontrak HTTP pemilih tema admin: sesi cookie, CSRF, dan cookie privat."""
from __future__ import annotations

import http.cookies
import re

import auth
from http_test_kit import ServerUji
from test_admin_http_c import _login, _minta

SANDI_ADMIN = "sandi-admin-tema-123"


def _server(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("Admin-Tema", SANDI_ADMIN, "admin")
    return server


def _csrf_tema(html):
    blok = html.split('class="admin-tema"', 1)[1].split('</form>', 1)[0]
    cocok = re.search(r'name="token_tema" value="([^"]+)"', blok)
    assert cocok
    return cocok.group(1)


def test_tema_disimpan_per_browser_dan_diterapkan_ke_seluruh_admin(tmp_path, monkeypatch):
    server = _server(tmp_path, monkeypatch)
    try:
        sesi = _login(server, "Admin-Tema", SANDI_ADMIN)
        kode, html, header = _minta(server, "/admin", cookie=sesi)
        assert kode == 200 and 'data-tema="sistem"' in html
        csrf = _csrf_tema(html)

        kode, _, header = _minta(
            server, "/admin/tema", cookie=sesi,
            data={"token_tema": csrf, "tema": "gelap"},
            headers={"X-Forwarded-Proto": "https"},
        )
        assert kode == 303 and header["Location"] == "/admin"
        cookie = http.cookies.SimpleCookie(header["Set-Cookie"])["jagomat_admin_tema"]
        assert cookie.value == "gelap"
        assert cookie["path"] == "/admin"
        assert cookie["httponly"] and cookie["secure"] and cookie["samesite"] == "Lax"
        assert int(cookie["max-age"]) == 31536000

        gabung = "osn_sesi=%s; jagomat_admin_tema=gelap" % sesi
        for jalur in ("/admin", "/admin/riset", "/admin/ai"):
            kode, html, header = _minta(server, jalur, headers={"Cookie": gabung})
            assert kode == 200
            assert 'data-tema="gelap"' in html
            assert 'name="tema" value="gelap" aria-pressed="true"' in html
            assert header.get("Vary") == "Cookie"
    finally:
        server.berhenti()


def test_tema_invalid_dan_csrf_salah_ditolak_tanpa_cookie(tmp_path, monkeypatch):
    server = _server(tmp_path, monkeypatch)
    try:
        sesi = _login(server, "Admin-Tema", SANDI_ADMIN)
        _, html, _ = _minta(server, "/admin", cookie=sesi)
        csrf = _csrf_tema(html)
        invalid = _minta(server, "/admin/tema", cookie=sesi, data={"token_tema": csrf, "tema": "otomatis-gelap"})
        csrf_salah = _minta(server, "/admin/tema", cookie=sesi, data={"token_tema": "salah", "tema": "terang"})
        for respons in (invalid, csrf_salah):
            assert respons[0] in (400, 403)
            assert "Set-Cookie" not in respons[2]
    finally:
        server.berhenti()


def test_basic_auth_tidak_boleh_menetapkan_preferensi_browser(tmp_path, monkeypatch):
    server = _server(tmp_path, monkeypatch)
    try:
        kode, html, _ = _minta(server, "/admin", auth_basic=("Admin-Tema", SANDI_ADMIN))
        assert kode == 200
        assert 'class="admin-tema"' not in html
        kode, _, header = _minta(
            server, "/admin/tema", auth_basic=("Admin-Tema", SANDI_ADMIN),
            data={"token_tema": "x", "tema": "gelap"},
        )
        assert kode == 403
        assert "Set-Cookie" not in header
    finally:
        server.berhenti()


def test_cookie_tema_tidak_sah_fail_closed_ke_sistem(tmp_path, monkeypatch):
    server = _server(tmp_path, monkeypatch)
    try:
        sesi = _login(server, "Admin-Tema", SANDI_ADMIN)
        kode, html, _ = _minta(
            server, "/admin", headers={"Cookie": "osn_sesi=%s; jagomat_admin_tema=ungu" % sesi}
        )
        assert kode == 200
        assert 'data-tema="sistem"' in html
        assert 'name="tema" value="sistem" aria-pressed="true"' in html
    finally:
        server.berhenti()

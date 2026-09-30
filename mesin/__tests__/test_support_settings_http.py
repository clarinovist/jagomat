"""Regresi HTTP pengaturan dukungan dan proyeksi publik."""
import pytest

import admin_operations
import admin_store
import auth
import support_settings as dukungan
from test_admin_http_c import (
    SANDI_ADMIN, SANDI_ORANG_TUA, _hidden, _login, _minta, server,
)
from http_test_kit import SANDI_GURU, SANDI_MURID


NOMOR = "082137111988"


@pytest.fixture(autouse=True)
def schema_dukungan(server):
    dukungan.migrasikan(admin_store.BAWAAN, sekarang=2)


def _form(server, token):
    kode, body, _ = _minta(server, "/admin?section=operasional", cookie=token)
    assert kode == 200
    return body, dict(
        csrf_dukungan=_hidden(body, "csrf_dukungan"),
        tinjauan_dukungan=_hidden(body, "tinjauan_dukungan"),
        reauth=SANDI_ADMIN,
        whatsapp="0821 3711 1988",
        jam_layanan="weekday_0900_1700_wib",
        sla_respons="2",
        sla_status="4",
        konfirmasi="1",
    )


def _jumlah_audit():
    with admin_store.buka_baca() as kon:
        return kon.execute("SELECT COUNT(*) FROM dukungan_audit").fetchone()[0]


def test_admin_operasional_menampilkan_status_dan_form_dukungan(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    body, form = _form(server, token)
    assert "Dukungan pengguna" in body
    assert "Siap" in body
    assert "0821 3711 1988" in body
    assert "Senin–Jumat, 09.00–17.00 WIB" in body
    assert 'name="whatsapp"' in body and 'inputmode="numeric"' in body
    assert 'name="jam_layanan"' in body
    assert 'name="sla_respons"' in body and 'name="sla_status"' in body
    assert 'name="reauth"' in body and 'class="admin-tombol"' in body
    assert set(form) == {"csrf_dukungan", "tinjauan_dukungan", "reauth", "whatsapp", "jam_layanan", "sla_respons", "sla_status", "konfirmasi"}


def test_http_dukungan_csrf_signed_reauth_revisi_collision_replay(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _body, form = _form(server, token)
    _body, form_stale = _form(server, token)
    awal = admin_store.BAWAAN.read_bytes()
    for ubah, status in (
        ({"csrf_dukungan": "rusak"}, 403),
        ({"tinjauan_dukungan": "rusak"}, 403),
        ({"reauth": "salah"}, 403),
        ({"konfirmasi": "0"}, 400),
        ({"whatsapp": "08xx-xxxx-xxxx"}, 400),
    ):
        assert _minta(server, "/admin/layanan/dukungan", cookie=token, data={**form, **ubah})[0] == status
        assert admin_store.BAWAAN.read_bytes() == awal
    for _ in range(2):
        kode, _isi, header = _minta(server, "/admin/layanan/dukungan", cookie=token, data=form)
        assert kode == 303
        assert "dukungan=tersimpan" in header["Location"]
    assert _jumlah_audit() == 1

    # Snapshot form kedua dari revisi lama mempunyai operasi berbeda: stale 409.
    assert _minta(server, "/admin/layanan/dukungan", cookie=token,
                  data=form_stale)[0] == 409
    assert _jumlah_audit() == 1

    # Operation ID sama tetapi isi berbeda merupakan collision, bukan replay.
    assert _minta(server, "/admin/layanan/dukungan", cookie=token,
                  data={**form, "sla_status": "5"})[0] == 409
    assert _jumlah_audit() == 1


def test_http_dukungan_csrf_wajib(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _body, form = _form(server, token)
    assert _minta(server, "/admin/layanan/dukungan", cookie=token,
                  data={**form, "csrf_dukungan": "rusak"})[0] == 403
    assert _jumlah_audit() == 0


def test_http_dukungan_signature_wajib(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _body, form = _form(server, token)
    signed = form["tinjauan_dukungan"]
    form["tinjauan_dukungan"] = signed[:-1] + ("A" if signed[-1] != "A" else "B")
    assert _minta(server, "/admin/layanan/dukungan", cookie=token, data=form)[0] == 403
    assert _jumlah_audit() == 0


def test_http_dukungan_reauth_wajib(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _body, form = _form(server, token)
    assert _minta(server, "/admin/layanan/dukungan", cookie=token,
                  data={**form, "reauth": "salah"})[0] == 403
    assert _jumlah_audit() == 0


def test_stale_admin_principal_ditolak_tanpa_tulis(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _body, form = _form(server, token)
    auth.naikkan_revisi_auth(auth.cari_akun("Admin-C")["id_akun"])
    awal = admin_store.BAWAAN.read_bytes()
    assert _minta(server, "/admin/layanan/dukungan", cookie=token, data=form)[0] == 404
    assert admin_store.BAWAAN.read_bytes() == awal


def test_anon_guru_murid_404_identik_tanpa_read_write(server, monkeypatch):
    def tolak(*a, **kw):
        pytest.fail("service dukungan dipanggil sebelum guard")
    monkeypatch.setattr(dukungan, "baca", tolak)
    monkeypatch.setattr(dukungan, "ubah", tolak)
    awal = admin_store.BAWAAN.read_bytes()
    for path, data in (("/admin?section=operasional", None), ("/admin/layanan/dukungan", {})):
        respons = [
            _minta(server, path, data=data)[:2],
            _minta(server, path, data=data, auth_basic=("guru", SANDI_GURU))[:2],
            _minta(server, path, data=data, auth_basic=("feby", SANDI_MURID))[:2],
        ]
        assert respons[0] == respons[1] == respons[2]
        assert respons[0][0] == 404
    assert admin_store.BAWAAN.read_bytes() == awal


def test_feedback_sukses_diumumkan_dan_config_hilang_fail_closed(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _body, form = _form(server, token)
    assert _minta(server, "/admin/layanan/dukungan", cookie=token, data=form)[0] == 303
    body = _minta(server, "/admin?section=operasional&dukungan=tersimpan", cookie=token)[1]
    assert 'role="status"' in body and "Pengaturan dukungan tersimpan" in body

    import sqlite3
    with sqlite3.connect(admin_store.BAWAAN) as kon:
        kon.execute("DROP TRIGGER dukungan_config_tolak_delete")
        kon.execute("DELETE FROM dukungan_konfigurasi")
    body = _minta(server, "/admin?section=operasional", cookie=token)[1]
    assert "Dukungan pengguna" in body and "Belum siap" in body
    assert "08xx" not in body and "wa.me" not in body

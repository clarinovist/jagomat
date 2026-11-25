"""Tab "Akun guru" admin lewat HTTP nyata: daftar, kelola, tinjauan aksi, dan aksi end-to-end (butir QA #5, 25 Nov 2026; data sintetis)."""
import re

import pytest

import admin_registration as reg
import admin_store
import auth
import database
import lembaga_store
from test_admin_http_c import SANDI_ADMIN, SANDI_ORANG_TUA, _hidden, _login, _minta, server  # noqa: F401

ORIGIN = {"Sec-Fetch-Site": "same-origin"}
GURU_BARU = "bu-mandiri"


def _id(nama):
    return auth.cari_akun(nama)["id_akun"]


@pytest.fixture()
def isi_guru(server):
    """Guru buatan admin (Ortu-C, punya anak), guru mandiri (receipt publik), dan satu pemilik lembaga."""
    reg.daftar_publik(admin_store.BAWAAN, auth.BERKAS_SANDI, database.BAWAAN, operasi_id="op-" + "a" * 28,
                      alias=GURU_BARU, sandi="sandi-guru-mandiri-1", token_form="b" * 64, sekarang=1_800_000_000)
    auth.tambah_akun("Koordinator-C", "sandi-koordinator-c-123", "guru")
    with server.buka() as kon:
        lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="Koordinator-C")
    return server


def _post(server, token, data):
    return _minta(server, "/admin/akun", cookie=token, data=data, headers={"Origin": server.alamat, **ORIGIN})


def test_daftar_menampilkan_guru_dengan_asal_dan_lembaga_tanpa_kredensial(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    kode, isi, _ = _minta(isi_guru, "/admin?section=guru", cookie=token)
    assert kode == 200
    for harap in (GURU_BARU, "Daftar sendiri", "Ortu-C", "Koordinator-C", "Jagomat", "Koordinator", "Belum masuk lembaga",
                  'href="/admin?section=guru&amp;id=' + _id(GURU_BARU)):
        assert harap in isi, harap
    for rahasia in ("sandi-guru-mandiri-1", SANDI_ORANG_TUA, "garam", "pbkdf2", SANDI_ADMIN):
        assert rahasia not in isi


def test_filter_status_dan_nilai_asing_ditolak(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    _, isi, _ = _minta(isi_guru, "/admin?section=guru&status=mandiri", cookie=token)
    tabel = isi.split("Daftar guru", 1)[1]
    assert GURU_BARU in tabel and "Koordinator-C" not in tabel
    _, isi, _ = _minta(isi_guru, "/admin?section=guru&status=di_lembaga", cookie=token)
    tabel = isi.split("Daftar guru", 1)[1]
    assert "Koordinator-C" in tabel and GURU_BARU not in tabel
    assert _minta(isi_guru, "/admin?section=guru&status=aneh", cookie=token)[0] == 404


def test_kelola_menautkan_aksi_dan_menyembunyikan_hapus_untuk_guru_di_lembaga(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    _, isi, _ = _minta(isi_guru, "/admin?section=guru&id=" + _id(GURU_BARU), cookie=token)
    for aksi in ("account_password_reset", "account_session_revoke", "account_login_delete"):
        assert "aksi=%s&amp;id=%s&amp;dari=guru" % (aksi, _id(GURU_BARU)) in isi
    assert "Tambah ke lembaga" in isi
    _, isi, _ = _minta(isi_guru, "/admin?section=guru&id=" + _id("Koordinator-C"), cookie=token)
    assert "account_password_reset" in isi and "account_login_delete" not in isi and "masih pemilik" in isi


@pytest.mark.parametrize("nama", ["Admin-C", "tidak-ada"])
def test_kelola_target_bukan_guru_atau_tak_ada_404(isi_guru, nama):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    id_ = _id(nama) if nama == "Admin-C" else "akun_" + "f" * 32
    assert _minta(isi_guru, "/admin?section=guru&id=" + id_, cookie=token)[0] == 404


def test_tinjauan_dari_guru_menampilkan_form_dengan_token_dan_tanpa_efek(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, isi, _ = _minta(isi_guru, "/admin/tinjau?aksi=account_password_reset&id=%s&dari=guru" % _id(GURU_BARU),
                          cookie=token)
    assert kode == 200 and "Setel ulang sandi" in isi and 'name="tinjauan"' in isi and 'name="csrf"' in isi
    assert "Identitas guru" in isi and "Kembali ke daftar guru" in isi
    assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_tinjauan_dari_guru_menolak_target_salah_aksi_salah_dan_hapus_untuk_pemilik_lembaga(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    dasar = "/admin/tinjau?aksi=%s&id=%s&dari=guru"
    assert _minta(isi_guru, dasar % ("account_password_reset", _id("Admin-C")), cookie=token)[0] == 404
    assert _minta(isi_guru, dasar % ("account_password_reset", "akun_" + "f" * 32), cookie=token)[0] == 404
    assert _minta(isi_guru, dasar % ("student_delete", _id(GURU_BARU)), cookie=token)[0] == 404
    kode, isi, _ = _minta(isi_guru, dasar % ("account_login_delete", _id("Koordinator-C")), cookie=token)
    assert kode == 200 and 'name="tinjauan"' not in isi and "masih pemilik" in isi


def test_reset_sandi_end_to_end_dari_tab_guru_menampilkan_akses_sekali_dan_login_baru_berlaku(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    _, review, _ = _minta(isi_guru, "/admin/tinjau?aksi=account_password_reset&id=%s&dari=guru" % _id(GURU_BARU),
                          cookie=token)
    data = {"aksi": "account_password_reset", "csrf": _hidden(review, "csrf"), "tinjauan": _hidden(review, "tinjauan"),
            "sandi_baru": "sandi-baru-mandiri-123", "reauth": SANDI_ADMIN, "verifikasi_independen": "1"}
    kode, isi, _ = _post(isi_guru, token, data)
    assert kode == 200 and "Simpan akses sekarang" in isi       # akses ditampilkan sekali, bukan lewat redirect
    assert 'href="/admin?section=guru">Selesai' in isi
    assert auth.periksa_peran(GURU_BARU, "sandi-baru-mandiri-123", "guru")
    assert not auth.periksa_peran(GURU_BARU, "sandi-guru-mandiri-1", "guru")


def test_reset_tanpa_reauth_atau_tanpa_verifikasi_ditolak_tanpa_efek(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    _, review, _ = _minta(isi_guru, "/admin/tinjau?aksi=account_password_reset&id=%s&dari=guru" % _id(GURU_BARU),
                          cookie=token)
    dasar = {"aksi": "account_password_reset", "csrf": _hidden(review, "csrf"), "tinjauan": _hidden(review, "tinjauan"),
             "sandi_baru": "sandi-baru-mandiri-123", "reauth": SANDI_ADMIN, "verifikasi_independen": "1"}
    sebelum = auth.BERKAS_SANDI.read_bytes()
    for ubah in ({"reauth": "salah-total-123"}, {"verifikasi_independen": "0"}):
        kode, _, _ = _post(isi_guru, token, {**dasar, **ubah})
        assert kode in (400, 403)
        assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_hapus_login_guru_mandiri_end_to_end_dan_pemilik_lembaga_tetap_ditolak_server(isi_guru):
    token = _login(isi_guru, "Admin-C", SANDI_ADMIN)
    _, review, _ = _minta(isi_guru, "/admin/tinjau?aksi=account_login_delete&id=%s&dari=guru" % _id(GURU_BARU),
                          cookie=token)
    data = {"aksi": "account_login_delete", "csrf": _hidden(review, "csrf"), "tinjauan": _hidden(review, "tinjauan"),
            "reauth": SANDI_ADMIN, "konfirmasi": "1"}
    kode, _, header = _post(isi_guru, token, data)
    assert kode == 303 and header["Location"] == "/admin?section=guru"
    assert auth.cari_akun(GURU_BARU) is None
    # Token untuk pemilik lembaga lewat jalur lama (keluarga): POST tetap ditolak di server.
    _, review2, _ = _minta(isi_guru, "/admin/tinjau?aksi=account_login_delete&id=" + _id("Koordinator-C"), cookie=token)
    kode, _, _ = _post(isi_guru, token, {**data, "csrf": _hidden(review2, "csrf"), "tinjauan": _hidden(review2, "tinjauan")})
    assert kode in (400, 403, 409)
    assert auth.cari_akun("Koordinator-C") is not None

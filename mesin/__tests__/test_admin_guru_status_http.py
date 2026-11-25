"""Nonaktifkan / aktifkan guru lewat HTTP nyata: cookie lama dan Basic ditolak, sandi ulang, CSRF, koordinator, tombstone (25 Nov 2026; sintetis)."""
import pytest

import auth
import lembaga_store
from test_admin_http_c import SANDI_ADMIN, SANDI_ORANG_TUA, _hidden, _login, _minta, server  # noqa: F401

ORIGIN = {"Sec-Fetch-Site": "same-origin"}
GURU = "Ortu-C"
KOORD = "Koordinator-C"
NONAKTIFKAN = "/admin/guru/nonaktifkan"
AKTIFKAN = "/admin/guru/aktifkan"


def _id(nama):
    return auth.cari_akun(nama)["id_akun"]


@pytest.fixture()
def isi(server):
    auth.tambah_akun(KOORD, "sandi-koordinator-c-123", "guru")
    with server.buka() as kon:
        lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik=KOORD)
    return server


def _post(server, token, rute, data):
    return _minta(server, rute, cookie=token, data=data, headers={"Origin": server.alamat, **ORIGIN})


def _form(server, token, rute, nama):
    kode, halaman, _ = _minta(server, "%s?id=%s" % (rute, _id(nama)), cookie=token)
    assert kode == 200, kode
    return {"csrf": _hidden(halaman, "csrf"), "tinjauan": _hidden(halaman, "tinjauan"), "id": _id(nama),
            "reauth": SANDI_ADMIN}


def _admin(server):
    return _login(server, "Admin-C", SANDI_ADMIN)


def _nonaktifkan(server, token=None, nama=GURU):
    token = token or _admin(server)
    return _post(server, token, NONAKTIFKAN, _form(server, token, NONAKTIFKAN, nama))


def test_halaman_konfirmasi_menampilkan_form_tanpa_efek(isi):
    token = _admin(isi)
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, halaman, _ = _minta(isi, "%s?id=%s" % (NONAKTIFKAN, _id(GURU)), cookie=token)
    assert kode == 200 and 'name="tinjauan"' in halaman and 'name="reauth"' in halaman and "Nonaktifkan akun" in halaman
    for rahasia in (SANDI_ORANG_TUA, SANDI_ADMIN, "garam", "pbkdf2"):
        assert rahasia not in halaman
    assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_nonaktifkan_mengunci_cookie_lama_basic_dan_login_baru(isi):
    cookie_guru = _login(isi, GURU, SANDI_ORANG_TUA)
    assert _minta(isi, "/akun", cookie=cookie_guru)[0] == 200
    kode, _, header = _nonaktifkan(isi)
    assert kode == 303 and header["Location"] == "/admin?section=guru&id=" + _id(GURU)
    assert auth.cari_akun(GURU)["dinonaktifkan"] is True
    assert _minta(isi, "/akun", cookie=cookie_guru)[0] in (303, 401)
    assert _minta(isi, "/akun", auth_basic=(GURU, SANDI_ORANG_TUA))[0] == 401
    _, _, header = _minta(isi, "/masuk", data={"nama": GURU, "sandi": SANDI_ORANG_TUA})
    assert "osn_sesi" not in header.get("Set-Cookie", "")


def test_daftar_dan_detail_menampilkan_status_nonaktif_dan_chip(isi):
    token = _admin(isi)
    _nonaktifkan(isi, token)
    _, semua, _ = _minta(isi, "/admin?section=guru", cookie=token)
    assert "Ortu-C" not in semua.split("Daftar guru", 1)[1] and "Nonaktif" in semua
    _, daftar, _ = _minta(isi, "/admin?section=guru&status=nonaktif", cookie=token)
    assert "Ortu-C" in daftar.split("Daftar guru", 1)[1]
    _, detail, _ = _minta(isi, "/admin?section=guru&id=" + _id(GURU), cookie=token)
    assert "Akun nonaktif" in detail and "Aktifkan kembali" in detail and "Admin-C" in detail
    assert "account_password_reset" not in detail and NONAKTIFKAN not in detail


def test_aktifkan_kembali_membuka_login_tapi_cookie_lama_tetap_mati(isi):
    cookie_guru = _login(isi, GURU, SANDI_ORANG_TUA)
    token = _admin(isi)
    _nonaktifkan(isi, token)
    kode, _, header = _post(isi, token, AKTIFKAN, _form(isi, token, AKTIFKAN, GURU))
    assert kode == 303 and header["Location"] == "/admin?section=guru&id=" + _id(GURU)
    akun = auth.cari_akun(GURU)
    assert "dinonaktifkan" not in akun and "nonaktif_admin" not in akun
    assert _minta(isi, "/akun", auth_basic=(GURU, SANDI_ORANG_TUA))[0] == 200
    assert _minta(isi, "/akun", cookie=cookie_guru)[0] in (303, 401)
    assert _minta(isi, "/akun", cookie=_login(isi, GURU, SANDI_ORANG_TUA))[0] == 200


def test_koordinator_lembaga_tidak_bisa_dinonaktifkan(isi):
    token = _admin(isi)
    kode, halaman, _ = _minta(isi, "%s?id=%s" % (NONAKTIFKAN, _id(KOORD)), cookie=token)
    assert kode == 200 and 'name="tinjauan"' not in halaman and "pemilik lembaga" in halaman
    _, detail, _ = _minta(isi, "/admin?section=guru&id=" + _id(KOORD), cookie=token)
    assert NONAKTIFKAN not in detail and "masih pemilik lembaga" in detail
    # Token sah milik guru lain dengan id koordinator dipalsukan: ditolak, tanpa efek.
    form = _form(isi, token, NONAKTIFKAN, GURU)
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _post(isi, token, NONAKTIFKAN, {**form, "id": _id(KOORD)})
    assert kode == 400 and auth.BERKAS_SANDI.read_bytes() == sebelum


def test_sandi_ulang_salah_csrf_salah_dan_field_asing_ditolak_tanpa_efek(isi):
    token = _admin(isi)
    form = _form(isi, token, NONAKTIFKAN, GURU)
    sebelum = auth.BERKAS_SANDI.read_bytes()
    for ubah in ({"reauth": "salah-total-123"}, {"csrf": "x" * 20}, {"tinjauan": "x.y"}, {"asing": "1"}):
        kode, _, _ = _post(isi, token, NONAKTIFKAN, {**form, **ubah})
        assert kode in (400, 403), ubah
        assert auth.BERKAS_SANDI.read_bytes() == sebelum
    form.pop("reauth")
    assert _post(isi, token, NONAKTIFKAN, form)[0] in (400, 403)
    assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_non_admin_dan_anonim_mendapat_404_atau_tolak_identik_tanpa_efek(isi):
    cookie_guru = _login(isi, GURU, SANDI_ORANG_TUA)
    sebelum = auth.BERKAS_SANDI.read_bytes()
    url = "%s?id=%s" % (NONAKTIFKAN, _id(KOORD))
    acuan = _minta(isi, "/admin/guru/tidak-ada", cookie=cookie_guru)
    got = _minta(isi, url, cookie=cookie_guru)
    assert got[0] == acuan[0] == 404 and got[1] == acuan[1]
    assert _minta(isi, url)[0] in (401, 404)
    assert _post(isi, cookie_guru, NONAKTIFKAN, {"id": _id(GURU)})[0] == 404
    assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_target_admin_murid_tak_dikenal_dan_id_tak_sah_404(isi):
    token = _admin(isi)
    for id_ in (_id("Admin-C"), "akun_" + "f" * 32, "bukan-id", ""):
        assert _minta(isi, "%s?id=%s" % (NONAKTIFKAN, id_), cookie=token)[0] == 404, id_
    assert _minta(isi, NONAKTIFKAN, cookie=token)[0] == 404
    assert _minta(isi, "%s?id=%s&x=1" % (NONAKTIFKAN, _id(GURU)), cookie=token)[0] == 404


def test_tombstone_tidak_bisa_diaktifkan_lewat_rute(isi):
    from json_storage import transaksi_json
    with transaksi_json(auth.BERKAS_SANDI) as tujuan:
        mentah, akun, _ = auth._baca_akun_untuk_tulis(tujuan)
        next(a for a in akun if a["pengguna"] == GURU)["dinonaktifkan"] = True  # bentuk tombstone: tanpa marka
        auth._tulis_akun_atomik(auth._bungkus_akun(mentah, akun), tujuan)
    token = _admin(isi)
    sebelum = auth.BERKAS_SANDI.read_bytes()
    assert _minta(isi, "%s?id=%s" % (AKTIFKAN, _id(GURU)), cookie=token)[0] == 404
    assert _minta(isi, "/admin?section=guru&id=" + _id(GURU), cookie=token)[0] == 404
    assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_token_basi_setelah_nonaktif_tidak_menulis_lagi(isi):
    token = _admin(isi)
    form = _form(isi, token, NONAKTIFKAN, GURU)
    assert _post(isi, token, NONAKTIFKAN, form)[0] == 303
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _post(isi, token, NONAKTIFKAN, form)
    assert kode == 400 and auth.BERKAS_SANDI.read_bytes() == sebelum


def test_aktifkan_guru_aktif_ditolak(isi):
    token = _admin(isi)
    assert _minta(isi, "%s?id=%s" % (AKTIFKAN, _id(GURU)), cookie=token)[0] == 404

"""Nonaktifkan / aktifkan guru lewat HTTP nyata: cookie lama dan Basic ditolak, sandi ulang, CSRF, koordinator, tombstone (25 Nov 2026; sintetis)."""
import logging
import sqlite3

import pytest

import auth
import guru_status_jurnal as J
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
    assert "Tindakan ini bisa dibatalkan" in halaman and "dihapus permanen" not in halaman
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


def _aktifkan(server, token, nama=GURU):
    return _post(server, token, AKTIFKAN, _form(server, token, AKTIFKAN, nama))


def _riwayat_guru(server, token, query=""):
    return _minta(server, "/admin?section=riwayat&sumber=guru" + query, cookie=token)


def test_riwayat_status_guru_memuat_nonaktifkan_lalu_aktifkan_tanpa_rahasia(isi):
    # Arrange
    token = _admin(isi)
    _nonaktifkan(isi, token)
    assert _aktifkan(isi, token)[0] == 303

    # Act
    kode, halaman, _ = _riwayat_guru(isi, token)

    # Assert
    assert kode == 200 and "<strong>Nonaktifkan</strong>" in halaman and "<strong>Aktifkan</strong>" in halaman
    assert halaman.index("<strong>Aktifkan</strong>") < halaman.index("<strong>Nonaktifkan</strong>")
    assert GURU in halaman and _id(GURU) in halaman
    for rahasia in (SANDI_ORANG_TUA, SANDI_ADMIN, "pbkdf2", "garam"):
        assert rahasia not in halaman


def test_riwayat_status_guru_filter_id_hanya_menampilkan_guru_itu(isi):
    # Arrange
    token = _admin(isi)
    auth.tambah_akun("Guru-F", "sandi-guru-f-http-c-123", "guru")
    _nonaktifkan(isi, token, nama="Guru-F")
    _nonaktifkan(isi, token)

    # Act
    kode, halaman, _ = _riwayat_guru(isi, token, "&id=" + _id(GURU))

    # Assert
    assert kode == 200 and GURU in halaman and "Guru-F" not in halaman


def test_riwayat_status_guru_id_tak_sah_ditolak_404(isi):
    token = _admin(isi)
    kode, _, _ = _riwayat_guru(isi, token, "&id=bukan-id")
    assert kode == 404


def test_riwayat_status_guru_anonim_dan_nonadmin_404_identik_rute_tak_dikenal(isi):
    # Arrange and Act
    rute_tak_dikenal = _minta(isi, "/admin/tidak-dikenal-uji")[0:2]
    anonim = _minta(isi, "/admin?section=riwayat&sumber=guru")[0:2]
    guru = _minta(isi, "/admin?section=riwayat&sumber=guru", auth_basic=(GURU, SANDI_ORANG_TUA))[0:2]

    # Assert
    assert anonim == guru == rute_tak_dikenal and anonim[0] == 404


def test_jurnal_gagal_tulis_tidak_membatalkan_nonaktifkan_dan_log_tanpa_identitas(isi, monkeypatch, caplog):
    # Arrange
    def _gagal(*_args, **_kwargs):
        raise sqlite3.OperationalError("gagal menulis untuk %s %s" % (GURU, _id(GURU)))

    monkeypatch.setattr(J, "catat", _gagal)
    token = _admin(isi)

    # Act
    with caplog.at_level(logging.ERROR):
        kode, _, _ = _nonaktifkan(isi, token)

    # Assert
    assert kode == 303
    assert auth.cari_akun(GURU)["dinonaktifkan"] is True
    assert "OperationalError" in caplog.text
    assert GURU not in caplog.text and _id(GURU) not in caplog.text and _id("Admin-C") not in caplog.text


def test_nonaktifkan_yang_ditolak_tidak_menulis_jurnal(isi):
    # Arrange
    token = _admin(isi)
    form = _form(isi, token, NONAKTIFKAN, GURU)

    # Act
    kode, _, _ = _post(isi, token, NONAKTIFKAN, {**form, "id": _id(KOORD)})

    # Assert
    assert kode == 400 and J.daftar().total == 0
    assert _nonaktifkan(isi, token)[0] == 303
    assert J.daftar().total == 1


def test_detail_guru_menautkan_jurnal_status(isi):
    token = _admin(isi)
    _, detail, _ = _minta(isi, "/admin?section=guru&id=" + _id(GURU), cookie=token)
    assert "Lihat jurnal status" in detail
    assert "section=riwayat&amp;sumber=guru&amp;id=" + _id(GURU) in detail


def test_riwayat_status_guru_akun_hilang_tampil_sebagai_tidak_ditemukan(isi):
    # Arrange
    token = _admin(isi)
    id_hilang = "akun_" + "d" * 32
    J.catat(J.AKSI_NONAKTIFKAN, id_hilang, _id("Admin-C"), 1_700_000_000, 2)

    # Act
    kode, halaman, _ = _riwayat_guru(isi, token)

    # Assert
    assert kode == 200 and "Akun tidak ditemukan" in halaman and id_hilang in halaman


def test_jurnal_tidak_terbaca_menampilkan_pesan_tetap_tanpa_detail(isi, monkeypatch):
    # Arrange
    def _rusak(**_kwargs):
        raise J.GalatJurnal("detail internal /data/rahasia")

    monkeypatch.setattr(J, "daftar", _rusak)
    token = _admin(isi)

    # Act
    kode, halaman, _ = _riwayat_guru(isi, token)

    # Assert
    assert kode == 503 and "Jurnal status guru tidak bisa dibaca." in halaman
    assert "detail internal" not in halaman and "/data/rahasia" not in halaman

def test_nonaktifkan_guru_pemilik_lembaga_ditolak_tanpa_kunci_dan_tanpa_jurnal(isi):
    # Arrange: form dibuat saat GURU belum memiliki lembaga; kepemilikan lembaga menyusul
    token = _admin(isi)
    form = _form(isi, token, NONAKTIFKAN, GURU)
    with isi.buka() as kon:
        lembaga_store.buat_lembaga(kon, nama="Lembaga-Uji", pemilik=GURU)

    # Act
    kode, halaman, _ = _post(isi, token, NONAKTIFKAN, form)

    # Assert
    assert kode == 400 and "pemilik lembaga" in halaman
    assert auth.cari_akun(GURU).get("dinonaktifkan") is not True
    assert J.daftar().total == 0

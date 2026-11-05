"""Admin `/admin/lembaga`: buat lembaga, tambah/lepas anggota, CSRF, 404 non-admin.

Data sintetis. Semua POST memakai cookie admin + token CSRF; aksi gagal tidak
boleh menulis apa pun ke DB lembaga maupun berkas akun.
"""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import lembaga_store as L  # noqa: E402
from http_test_kit import SANDI_MURID  # noqa: E402
from test_admin_http_c import (  # noqa: E402
    SANDI_ADMIN, SANDI_ORANG_TUA, _hidden, _login, _minta, server,  # noqa: F401
)

LINTAS = {"Sec-Fetch-Site": "cross-site", "Origin": "http://situs-lain.invalid"}


@pytest.fixture()
def data(server):
    for nama in ("pemilik-x", "guru-x1", "guru-x2", "guru-bebas"):
        auth.tambah_akun(nama, SANDI_ORANG_TUA + nama, "guru")
    auth.tambah_akun("admin-kedua", SANDI_ADMIN + "2", "admin")
    server.token = _login(server, "Admin-C", SANDI_ADMIN)
    return server


def _csrf(server):
    _, isi, _ = _minta(server, "/admin/lembaga", cookie=server.token)
    return _hidden(isi, "csrf")


def _post(server, jalur, form, *, token=None, headers=None):
    pakai = {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}
    pakai.update(headers or {})
    return _minta(server, jalur, raw=urllib.parse.urlencode(form).encode(),
                  cookie=token if token is not None else server.token, headers=pakai)


def _keadaan(server):
    with server.buka() as kon:
        baris = tuple(
            tuple(tuple(r) for r in kon.execute(sql))
            for sql in ("SELECT id,nama,pemilik FROM lembaga ORDER BY id",
                        "SELECT lembaga_id,guru FROM anggota_lembaga ORDER BY guru"))
    return baris, auth.BERKAS_SANDI.read_bytes()


def _buat(server, nama="Les Admin", pemilik="pemilik-x", **kw):
    return _post(server, "/admin/lembaga/buat",
                 {"csrf": _csrf(server), "nama": nama, "pemilik": pemilik}, **kw)


def _id_lembaga(server):
    with server.buka() as kon:
        return L.lembaga_milik(kon, "pemilik-x")["id"]


def test_halaman_admin_memuat_form_dan_tautan_nav(data):
    kode, isi, tajuk = _minta(data, "/admin/lembaga", cookie=data.token)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    assert 'href="/admin/lembaga"' in isi
    assert 'action="/admin/lembaga/buat"' in isi
    # Satu-satunya skrip: konfirmasi() tombol destruktif admin yang sudah disetujui.
    import admin_pages
    assert admin_pages.SKRIP_KONFIRMASI_LOGIN in isi
    assert 'src="' not in isi.lower().split("<script", 1)[-1].split("</script>", 1)[0]
    # Pilihan pemilik: hanya akun guru; admin dan murid tidak ditawarkan.
    for nama in ("pemilik-x", "guru-x1", "guru-bebas"):
        assert 'value="%s"' % nama in isi
    for nama in ("Admin-C", "admin-kedua", "feby"):
        assert 'value="%s"' % nama not in isi


def test_nav_admin_lembaga_ada_di_semua_halaman_admin(data):
    assert 'href="/admin/lembaga"' in _minta(data, "/admin", cookie=data.token)[1]


def test_non_admin_404_identik_dengan_rute_admin_lain(data):
    acuan = _minta(data, "/admin/tidak-ada")[:2]
    assert acuan[0] == 404
    anonim = _minta(data, "/admin/lembaga")[:2]
    guru = _minta(data, "/admin/lembaga", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    murid = _minta(data, "/admin/lembaga", auth_basic=("feby", SANDI_MURID))[:2]
    assert anonim == guru == murid == acuan
    for jalur in ("/admin/lembaga/buat", "/admin/lembaga/anggota", "/admin/lembaga/lepas"):
        anonim = _minta(data, jalur, raw=b"a=b")[:2]
        guru = _minta(data, jalur, raw=b"a=b", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
        assert anonim == guru == acuan
    assert _minta(data, "/admin/lembaga?x=1", cookie=data.token)[0] == 404


def test_get_tanpa_efek_samping(data):
    sebelum = _keadaan(data)
    assert _minta(data, "/admin/lembaga", cookie=data.token)[0] == 200
    assert _keadaan(data) == sebelum


def test_buat_lembaga_sukses_lalu_pemilik_tidak_lagi_ditawarkan(data):
    kode, _, tajuk = _buat(data)
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(data)[0][0] == ((1, "Les Admin", "pemilik-x"),)
    _, isi, _ = _minta(data, "/admin/lembaga", cookie=data.token)
    assert "Les Admin" in isi
    pilihan = isi.split('action="/admin/lembaga/buat"', 1)[1].split("</form>", 1)[0]
    assert 'value="pemilik-x"' not in pilihan and 'value="guru-x1"' in pilihan


@pytest.mark.parametrize("pemilik", ["Admin-C", "admin-kedua", "feby", "tidak-ada", ""])
def test_pemilik_harus_akun_guru_yang_ada(data, pemilik):
    sebelum = _keadaan(data)
    kode, _, _ = _buat(data, pemilik=pemilik)
    assert kode == 400
    assert _keadaan(data) == sebelum


@pytest.mark.parametrize("nama", ["", "   ", "x" * 81])
def test_nama_lembaga_tidak_sah_ditolak(data, nama):
    sebelum = _keadaan(data)
    assert _buat(data, nama=nama)[0] == 400
    assert _keadaan(data) == sebelum


def test_pemilik_ganda_dan_anggota_jadi_pemilik_ditolak_409(data):
    assert _buat(data)[0] == 303
    lid = _id_lembaga(data)
    assert _post(data, "/admin/lembaga/anggota",
                 {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})[0] == 303
    sebelum = _keadaan(data)
    assert _buat(data, nama="Dua", pemilik="pemilik-x")[0] == 409
    assert _buat(data, nama="Dua", pemilik="guru-x1")[0] == 409
    assert _keadaan(data) == sebelum


def test_tambah_dan_lepas_anggota(data):
    _buat(data)
    lid = _id_lembaga(data)
    kode, _, tajuk = _post(data, "/admin/lembaga/anggota",
                           {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(data)[0][1] == ((lid, "guru-x1"),)
    _, isi, _ = _minta(data, "/admin/lembaga", cookie=data.token)
    assert 'action="/admin/lembaga/lepas"' in isi
    kode, _, _ = _post(data, "/admin/lembaga/lepas",
                       {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})
    assert kode == 303 and _keadaan(data)[0][1] == ()


@pytest.mark.parametrize("guru", ["Admin-C", "admin-kedua", "feby", "tidak-ada", "pemilik-x", ""])
def test_anggota_harus_guru_yang_ada_dan_bukan_pemilik(data, guru):
    _buat(data)
    lid = _id_lembaga(data)
    sebelum = _keadaan(data)
    kode, _, _ = _post(data, "/admin/lembaga/anggota",
                       {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": guru})
    assert kode in (400, 409)
    assert _keadaan(data) == sebelum


def test_anggota_tidak_boleh_masuk_dua_lembaga(data):
    _buat(data)
    lid = _id_lembaga(data)
    assert _buat(data, nama="Les Dua", pemilik="guru-x2")[0] == 303
    _post(data, "/admin/lembaga/anggota",
          {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})
    sebelum = _keadaan(data)
    with data.buka() as kon:
        lid2 = L.lembaga_milik(kon, "guru-x2")["id"]
    assert _post(data, "/admin/lembaga/anggota",
                 {"csrf": _csrf(data), "lembaga_id": str(lid2), "guru": "guru-x1"})[0] == 409
    assert _keadaan(data) == sebelum


def test_lepas_anggota_bukan_anggota_409_tanpa_efek(data):
    _buat(data)
    lid = _id_lembaga(data)
    sebelum = _keadaan(data)
    kode, _, _ = _post(data, "/admin/lembaga/lepas",
                       {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})
    assert kode == 409
    assert _keadaan(data) == sebelum


@pytest.mark.parametrize("jalur,form", [
    ("/admin/lembaga/buat", {"nama": "Les", "pemilik": "pemilik-x"}),
    ("/admin/lembaga/anggota", {"lembaga_id": "1", "guru": "guru-x1"}),
    ("/admin/lembaga/lepas", {"lembaga_id": "1", "guru": "guru-x1"}),
])
def test_csrf_hilang_atau_palsu_ditolak_tanpa_efek(data, jalur, form):
    _buat(data)
    sebelum = _keadaan(data)
    assert _post(data, jalur, form)[0] == 403
    assert _post(data, jalur, {"csrf": "palsu", **form})[0] == 403
    assert _keadaan(data) == sebelum


def test_csrf_dari_sesi_lain_ditolak(data):
    token_lain = _login(data, "admin-kedua", SANDI_ADMIN + "2")
    _, isi, _ = _minta(data, "/admin/lembaga", cookie=token_lain)
    csrf_lain = _hidden(isi, "csrf")
    sebelum = _keadaan(data)
    kode, _, _ = _post(data, "/admin/lembaga/buat",
                       {"csrf": csrf_lain, "nama": "Les", "pemilik": "pemilik-x"})
    assert kode == 403
    assert _keadaan(data) == sebelum


def test_post_lintas_situs_ditolak_tanpa_efek(data):
    csrf = _csrf(data)
    sebelum = _keadaan(data)
    kode, _, _ = _post(data, "/admin/lembaga/buat",
                       {"csrf": csrf, "nama": "Les", "pemilik": "pemilik-x"},
                       headers=LINTAS)
    assert kode == 403
    assert _keadaan(data) == sebelum


def test_post_dengan_field_asing_atau_ganda_ditolak(data):
    csrf = _csrf(data)
    sebelum = _keadaan(data)
    dasar = {"csrf": csrf, "nama": "Les", "pemilik": "pemilik-x"}
    assert _post(data, "/admin/lembaga/buat", {**dasar, "asing": "1"})[0] == 400
    kode, _, _ = _minta(
        data, "/admin/lembaga/buat", cookie=data.token,
        raw=(urllib.parse.urlencode(dasar) + "&nama=lain").encode(),
        headers={"Origin": data.alamat, "Sec-Fetch-Site": "same-origin"})
    assert kode == 400
    assert _keadaan(data) == sebelum


def test_basic_admin_tidak_mendapat_form_dan_post_ditolak(data):
    kode, isi, _ = _minta(data, "/admin/lembaga", auth_basic=("Admin-C", SANDI_ADMIN))
    assert kode == 200 and 'action="/admin/lembaga/buat"' not in isi
    sebelum = _keadaan(data)
    kode, _, _ = _minta(
        data, "/admin/lembaga/buat", auth_basic=("Admin-C", SANDI_ADMIN),
        raw=b"nama=Les&pemilik=pemilik-x&csrf=x",
        headers={"Origin": data.alamat, "Sec-Fetch-Site": "same-origin"})
    assert kode == 403
    assert _keadaan(data) == sebelum


def test_halaman_admin_tanpa_data_anak(data):
    with data.buka() as kon:
        database.tambah_siswa(kon, "Anak Rahasia Admin", "P3", pemilik="guru-x1")
    _buat(data)
    lid = _id_lembaga(data)
    _post(data, "/admin/lembaga/anggota",
          {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})
    _, isi, _ = _minta(data, "/admin/lembaga", cookie=data.token)
    assert "guru-x1" in isi and "Anak Rahasia Admin" not in isi


# --- hapus login guru yang masih terikat lembaga -----------------------------------

def _hapus_login(server, nama):
    import admin_store
    target = auth.cari_akun(nama)
    _, review, _ = _minta(
        server, "/admin/tinjau?aksi=account_login_delete&id=" + target["id_akun"],
        cookie=server.token)
    return _minta(server, "/admin/akun", cookie=server.token, data={
        "aksi": "account_login_delete", "csrf": _hidden(review, "csrf"),
        "tinjauan": _hidden(review, "tinjauan"), "reauth": SANDI_ADMIN,
        "konfirmasi": "1",
    }, headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"})


@pytest.mark.parametrize("peran_di_lembaga", ["pemilik", "anggota"])
def test_hapus_login_guru_ditahan_selama_terikat_lembaga(data, peran_di_lembaga):
    import admin_store
    with data.buka() as kon:
        if peran_di_lembaga == "pemilik":
            L.buat_lembaga(kon, nama="Les Tahan", pemilik="guru-x1")
        else:
            lid = L.buat_lembaga(kon, nama="Les Tahan", pemilik="pemilik-x")
            L.tambah_anggota(kon, lembaga_id=lid, guru="guru-x1")
        sebelum_db = tuple(kon.iterdump())
    sebelum = (auth.BERKAS_SANDI.read_bytes(), admin_store.BAWAAN.read_bytes())
    kode, isi, _ = _hapus_login(data, "guru-x1")
    assert kode == 409
    assert "masih pemilik/anggota lembaga Les Tahan" in isi
    assert "Lepaskan atau bubarkan lembaganya dulu." in isi
    assert (auth.BERKAS_SANDI.read_bytes(), admin_store.BAWAAN.read_bytes()) == sebelum
    assert auth.cari_akun("guru-x1") is not None
    with data.buka() as kon:
        assert tuple(kon.iterdump()) == sebelum_db
    assert admin_store.daftar_riwayat(admin_store.BAWAAN, aksi="account_login_delete").total == 0


def test_hapus_login_guru_diizinkan_setelah_dilepas(data):
    _buat(data, pemilik="guru-x1")
    lid = _id_lembaga_milik(data, "guru-x1")
    assert _post(data, "/admin/lembaga/bubarkan",
                 {"csrf": _csrf(data), "lembaga_id": str(lid)})[0] == 303
    assert _hapus_login(data, "guru-x1")[0] == 303
    assert auth.cari_akun("guru-x1") is None


def _id_lembaga_milik(server, pemilik):
    with server.buka() as kon:
        return L.lembaga_milik(kon, pemilik)["id"]


# --- bubarkan lembaga ------------------------------------------------------------------

def test_bubarkan_menghapus_lembaga_dan_anggota_anak_dan_jejak_tetap(data):
    _buat(data)
    lid = _id_lembaga(data)
    _post(data, "/admin/lembaga/anggota",
          {"csrf": _csrf(data), "lembaga_id": str(lid), "guru": "guru-x1"})
    with data.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Bubar", "P3", pemilik="guru-x1")
        kon.execute("INSERT INTO pindah_siswa(siswa_id,lembaga_id,dari,ke,oleh)"
                    " VALUES (?,?,?,?,?)", (anak, lid, "pemilik-x", "guru-x1", "pemilik-x"))
    _, isi, _ = _minta(data, "/admin/lembaga", cookie=data.token)
    assert 'action="/admin/lembaga/bubarkan"' in isi and "data-konfirmasi=" in isi
    kode, _, tajuk = _post(data, "/admin/lembaga/bubarkan",
                           {"csrf": _csrf(data), "lembaga_id": str(lid)})
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(data)[0] == ((), ())
    with data.buka() as kon:
        assert kon.execute("SELECT pemilik FROM siswa WHERE id=?", (anak,)).fetchone()[0] == "guru-x1"
        assert kon.execute("SELECT lembaga_id FROM pindah_siswa").fetchone()[0] == lid
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("lid", ["999", "0", "abc", ""])
def test_bubarkan_lembaga_tak_ada_atau_id_salah_tanpa_efek(data, lid):
    _buat(data)
    sebelum = _keadaan(data)
    assert _post(data, "/admin/lembaga/bubarkan",
                 {"csrf": _csrf(data), "lembaga_id": lid})[0] in (400, 409)
    assert _keadaan(data) == sebelum


def test_bubarkan_csrf_lintas_situs_dan_non_admin(data):
    _buat(data)
    lid = _id_lembaga(data)
    sebelum = _keadaan(data)
    assert _post(data, "/admin/lembaga/bubarkan", {"lembaga_id": str(lid)})[0] == 403
    assert _post(data, "/admin/lembaga/bubarkan",
                 {"csrf": _csrf(data), "lembaga_id": str(lid)}, headers=LINTAS)[0] == 403
    acuan = _minta(data, "/admin/tidak-ada")[:2]
    assert _minta(data, "/admin/lembaga/bubarkan", raw=b"a=b")[:2] == acuan
    assert _minta(data, "/admin/lembaga/bubarkan", raw=b"a=b",
                  auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2] == acuan
    assert _keadaan(data) == sebelum

"""HTTP admin profil guru peninjau: akses, CSRF, tinjauan, reauth, revisi, validasi, tampilan."""
from __future__ import annotations

import html
import re

import pytest

import admin_store
import auth
import funnel_http
import profil_guru_settings as pg
from http_test_kit import SANDI_GURU, SANDI_MURID
from test_admin_http_c import SANDI_ADMIN, _login, _minta, server  # noqa: F401

RUTE = "/admin/profil-guru"
AKSI = {"tambah": RUTE + "/tambah", "ubah": RUTE + "/ubah", "hapus": RUTE + "/hapus"}
ISIAN = dict(nama="Guru Contoh", latar="S1 Pendidikan Matematika (contoh)",
             lama_mengajar="5 tahun (contoh)", urutan="1")


def _siap():
    pg.migrasikan(admin_store.BAWAAN, sekarang=2)


def _bentuk(body, aksi, indeks=0):
    """Nilai input hidden dari form ke-`indeks` yang beraksi `aksi`."""
    blok = re.findall(r'<form[^>]*action="%s"[^>]*>(.*?)</form>' % re.escape(AKSI[aksi]), body, re.S)
    assert len(blok) > indeks, (aksi, indeks)
    return {n: html.unescape(v) for n, v in re.findall(r'type="hidden" name="(\w+)" value="([^"]*)"', blok[indeks])}


def _isi(server, token, aksi, indeks=0, **timpa):
    body = _minta(server, RUTE, cookie=token)[1]
    return {**_bentuk(body, aksi, indeks), "reauth": SANDI_ADMIN, **timpa}


def _kirim(server, token, aksi, data):
    return _minta(server, AKSI[aksi], cookie=token, data=data)


def _tambah(server, token, **timpa):
    data = {**_isi(server, token, "tambah"), **ISIAN, **timpa}
    kode = _kirim(server, token, "tambah", data)[0]
    assert kode == 303
    return data


def _jumlah(tabel):
    with admin_store.buka_baca() as kon:
        return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


@pytest.fixture()
def admin(server):  # noqa: F811
    return _login(server, "Admin-C", SANDI_ADMIN)


# --- navigasi, status penyimpanan ----------------------------------------------

def test_nav_admin_profil_guru_satu_butir_dengan_pemakaian_dan_tab(server, admin):
    body = _minta(server, "/admin", cookie=admin)[1]
    nav = body.split('<nav class="admin-nav admin-menu"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/admin/pemakaian"' in nav and "Guru &amp; pemakaian" in nav
    assert 'href="/admin/profil-guru"' not in nav  # tidak lagi butir menu sendiri
    halaman = _minta(server, RUTE, cookie=admin)[1]
    menu = halaman.split('<nav class="admin-nav admin-menu"', 1)[1].split("</nav>", 1)[0]
    assert '<a href="/admin/pemakaian" aria-current="page">' in menu  # butir menu aktif di halaman profil
    assert '<a class="admin-tab" href="/admin/profil-guru" aria-current="page">Profil guru peninjau</a>' in halaman
    assert '<a class="admin-tab" href="/admin/pemakaian">Pemakaian</a>' in halaman


def test_penyimpanan_belum_siap_tampil_pesan_dan_post_ditolak_tanpa_tulis(server, admin):
    kode, body, header = _minta(server, RUTE, cookie=admin)
    assert kode == 200
    assert "Penyimpanan profil guru belum disiapkan oleh pengelola rilis" in body
    assert "/admin/profil-guru/" not in body
    awal = admin_store.BAWAAN.read_bytes()
    for aksi in AKSI:
        kode, body, _ = _kirim(server, admin, aksi, {"csrf": "x", "tinjauan": "y", "reauth": SANDI_ADMIN})
        assert kode == 503 and "belum disiapkan oleh pengelola rilis" in body
    assert admin_store.BAWAAN.read_bytes() == awal


def test_halaman_kosong_menampilkan_form_tambah_tanpa_centang_bawaan(server, admin):
    _siap()
    kode, body, header = _minta(server, RUTE, cookie=admin)
    assert kode == 200
    assert "Belum ada profil guru" in body
    form = re.search(r'<form[^>]*action="%s"[^>]*>(.*?)</form>' % re.escape(AKSI["tambah"]), body, re.S).group(1)
    assert 'name="tampil"' in form and "checked" not in form
    assert 'name="reauth"' in form and 'name="csrf"' in form and 'name="tinjauan"' in form
    assert header["Cache-Control"] == "no-store" and "noindex" in header["X-Robots-Tag"]
    for terlarang in ("email", "telepon", "foto", "kontak"):
        assert 'name="%s"' % terlarang not in body


def test_feedback_menyebut_ttl_dari_konstanta_tunggal(server, admin):
    _siap()
    body = _minta(server, RUTE + "?status=tersimpan", cookie=admin)[1]
    assert "paling lambat setelah %d detik" % funnel_http.TTL_PROFIL_DETIK in body
    assert "langsung dipakai halaman publik" not in body


def test_query_whitelist_dan_feedback_hanya_dari_kamus(server, admin):
    _siap()
    assert _minta(server, RUTE + "?x=1", cookie=admin)[0] == 404
    assert _minta(server, RUTE + "?status=a&status=b", cookie=admin)[0] == 404
    assert "Profil guru tersimpan" in _minta(server, RUTE + "?status=tersimpan", cookie=admin)[1]
    liar = _minta(server, RUTE + "?status=%3Cscript%3E", cookie=admin)[1]
    assert "&lt;script&gt;" not in liar and "<script>alert" not in liar and 'role="status"' not in liar


# --- akses ----------------------------------------------------------------------

def test_anon_guru_murid_404_identik_get_dan_post_tanpa_menyentuh_domain(server, monkeypatch):
    _siap()

    def tolak(*a, **kw):
        pytest.fail("domain profil guru dipanggil sebelum guard admin")
    for nama in ("baca", "tambah", "ubah", "hapus"):
        monkeypatch.setattr(pg, nama, tolak)
    awal = admin_store.BAWAAN.read_bytes()
    for jalur, data in [(RUTE, None)] + [(AKSI[a], {}) for a in AKSI]:
        respons = [
            _minta(server, jalur, data=data)[:2],
            _minta(server, jalur, data=data, auth_basic=("guru", SANDI_GURU))[:2],
            _minta(server, jalur, data=data, auth_basic=("feby", SANDI_MURID))[:2],
        ]
        assert respons[0] == respons[1] == respons[2], jalur
        assert respons[0][0] == 404, jalur
    assert admin_store.BAWAAN.read_bytes() == awal


def test_admin_dengan_sesi_basic_hanya_baca_dan_post_ditolak(server):
    _siap()
    kode, body, _ = _minta(server, RUTE, auth_basic=("Admin-C", SANDI_ADMIN))
    if kode == 200:
        assert "/admin/profil-guru/" not in body
    kode, _body, _ = _minta(server, AKSI["tambah"], auth_basic=("Admin-C", SANDI_ADMIN),
                            data={**ISIAN, "csrf": "x", "tinjauan": "y", "reauth": SANDI_ADMIN})
    assert kode in (403, 404) and _jumlah("profil_guru") == 0


def test_principal_basi_ditolak_404_tanpa_tulis(server, admin):
    _siap()
    data = {**_isi(server, admin, "tambah"), **ISIAN}
    auth.naikkan_revisi_auth(auth.cari_akun("Admin-C")["id_akun"])
    awal = admin_store.BAWAAN.read_bytes()
    assert _kirim(server, admin, "tambah", data)[0] == 404
    assert admin_store.BAWAAN.read_bytes() == awal


# --- guard tulis ---------------------------------------------------------------------

@pytest.mark.parametrize("timpa,status", [
    ({"csrf": "palsu"}, 403),
    ({"tinjauan": "palsu"}, 403),
    ({"reauth": "sandi-salah"}, 403),
    ({"reauth": ""}, 403),
])
def test_csrf_tinjauan_dan_reauth_wajib_tanpa_tulis(server, admin, timpa, status):
    _siap()
    data = {**_isi(server, admin, "tambah"), **ISIAN, **timpa}
    awal = admin_store.BAWAAN.read_bytes()
    assert _kirim(server, admin, "tambah", data)[0] == status
    assert admin_store.BAWAAN.read_bytes() == awal


def test_csrf_hilang_ditolak(server, admin):
    _siap()
    data = {**_isi(server, admin, "tambah"), **ISIAN}
    del data["csrf"]
    assert _kirim(server, admin, "tambah", data)[0] == 403
    assert _jumlah("profil_guru") == 0


def test_tinjauan_aksi_lain_tidak_boleh_dipakai_ulang(server, admin):
    _siap()
    _tambah(server, admin)
    token_tambah = _isi(server, admin, "tambah")["tinjauan"]
    form_hapus = _isi(server, admin, "hapus", tinjauan=token_tambah)
    assert _kirim(server, admin, "hapus", form_hapus)[0] == 403
    assert _jumlah("profil_guru") == 1


def test_isian_asing_dan_checkbox_aneh_ditolak(server, admin):
    _siap()
    for timpa in ({"email": "guru@contoh.test"}, {"tampil": "ya"}, {"id": "9"}):
        data = {**_isi(server, admin, "tambah"), **ISIAN, **timpa}
        assert _kirim(server, admin, "tambah", data)[0] == 400, timpa
    data = {**_isi(server, admin, "tambah"), **ISIAN}
    del data["latar"]
    assert _kirim(server, admin, "tambah", data)[0] == 400
    assert _jumlah("profil_guru") == 0


def test_hapus_dengan_isian_asing_ditolak(server, admin):
    _siap()
    _tambah(server, admin)
    assert _kirim(server, admin, "hapus", {**_isi(server, admin, "hapus"), "nama": "x"})[0] == 400
    assert _jumlah("profil_guru") == 1


# --- validasi ------------------------------------------------------------------------

@pytest.mark.parametrize("timpa,pesan", [
    ({"nama": "Guru <b>Contoh</b>"}, "tanda &lt; atau &gt;"),
    ({"nama": "x" * 81}, "maksimal 80"),
    ({"nama": "   "}, "wajib diisi"),
    ({"latar": "y" * 161}, "maksimal 160"),
    ({"lama_mengajar": "z" * 61}, "maksimal 60"),
    ({"urutan": "abc"}, "Urutan"),
    ({"urutan": "0"}, "Urutan"),
    ({"urutan": "100"}, "Urutan"),
])
def test_validasi_menolak_dengan_pesan_jelas_tanpa_memantulkan_isian(server, admin, timpa, pesan):
    _siap()
    data = {**_isi(server, admin, "tambah"), **ISIAN, **timpa}
    kode, body, _ = _kirim(server, admin, "tambah", data)
    assert kode == 400 and pesan in body
    assert "<b>" not in body
    assert _jumlah("profil_guru") == 0


def test_batas_enam_baris_lewat_http(server, admin):
    _siap()
    for i in range(5):
        _tambah(server, admin, nama="Guru Contoh %d" % i, urutan=str(i + 1))
    form_ketujuh = {**_isi(server, admin, "tambah"), **ISIAN, "nama": "Guru Contoh Ketujuh"}
    _tambah(server, admin, nama="Guru Contoh Keenam", urutan="6")
    body = _minta(server, RUTE, cookie=admin)[1]
    assert "Daftar penuh" in body and AKSI["tambah"] not in body
    kode, isi, _ = _kirim(server, admin, "tambah", form_ketujuh)
    assert kode == 400 and "maksimal 6" in isi
    assert _jumlah("profil_guru") == 6


# --- alur tulis penuh ----------------------------------------------------------------

def test_tambah_ubah_hapus_end_to_end_dan_dampak_publik(server, admin, monkeypatch):
    monkeypatch.setenv("FUNNEL_AKTIF", "1")
    _siap()
    _tambah(server, admin)                                   # tampil tidak dicentang
    assert pg.baca_publik(admin_store.BAWAAN) == ()
    assert "Tersembunyi" in _minta(server, RUTE, cookie=admin)[1]

    form = _isi(server, admin, "ubah", **{**ISIAN, "nama": "Guru Contoh Baru", "tampil": "1"})
    kode, _body, header = _kirim(server, admin, "ubah", form)
    assert kode == 303 and "status=tersimpan" in header["Location"]
    publik = _minta(server, "/paket-coba")[1]
    assert "Guru Contoh Baru" in publik and "S1 Pendidikan Matematika (contoh)" in publik
    funnel_http._reset_cache_profil()   # cache TTL: hapus di bawah harus terlihat segera

    body = _minta(server, RUTE, cookie=admin)[1]
    assert "Tampil di halaman publik" in body and "checked" in body
    kode, _body, header = _kirim(server, admin, "hapus", _isi(server, admin, "hapus"))
    assert kode == 303 and "status=dihapus" in header["Location"]
    assert "Guru Contoh Baru" not in _minta(server, "/paket-coba")[1]
    assert _jumlah("profil_guru") == 0 and _jumlah("profil_guru_audit") == 3


def test_replay_identik_idempoten_payload_berubah_konflik_dan_basi_konflik(server, admin):
    _siap()
    data = _tambah(server, admin)
    assert _kirim(server, admin, "tambah", data)[0] == 303      # replay identik: tanpa baris ganda
    assert _jumlah("profil_guru") == 1 and _jumlah("profil_guru_audit") == 1
    assert _kirim(server, admin, "tambah", {**data, "nama": "Guru Contoh Lain"})[0] == 409
    assert _jumlah("profil_guru") == 1

    form_a = _isi(server, admin, "ubah", **{**ISIAN, "nama": "Guru Contoh A"})
    form_b = _isi(server, admin, "ubah", **{**ISIAN, "nama": "Guru Contoh B"})
    assert _kirim(server, admin, "ubah", form_a)[0] == 303
    assert _kirim(server, admin, "ubah", form_b)[0] == 409       # snapshot revisi lama
    assert _kirim(server, admin, "ubah", {**form_a, "nama": "Guru Contoh Z"})[0] == 409
    assert pg.baca(admin_store.BAWAAN)[0].nama == "Guru Contoh A"


def test_hapus_basi_ditolak_dan_hapus_replay_aman(server, admin):
    _siap()
    _tambah(server, admin)
    form_hapus = _isi(server, admin, "hapus")
    form_ubah = _isi(server, admin, "ubah", **{**ISIAN, "nama": "Guru Contoh Baru"})
    assert _kirim(server, admin, "ubah", form_ubah)[0] == 303
    assert _kirim(server, admin, "hapus", form_hapus)[0] == 409  # revisi sudah naik
    assert _jumlah("profil_guru") == 1
    segar = _isi(server, admin, "hapus")
    assert _kirim(server, admin, "hapus", segar)[0] == 303
    assert _kirim(server, admin, "hapus", segar)[0] == 303       # replay setelah terhapus
    assert _jumlah("profil_guru") == 0


# --- tampilan ------------------------------------------------------------------------

def test_nama_di_escape_dan_konfirmasi_hapus_menyebut_konsekuensi(server, admin):
    _siap()
    _tambah(server, admin, nama='Guru "Contoh" & Rekan', tampil="1")
    body = _minta(server, RUTE, cookie=admin)[1]
    assert "Guru &quot;Contoh&quot; &amp; Rekan" in body
    assert 'Guru "Contoh" & Rekan' not in body
    konfirmasi = re.search(r'action="%s" data-konfirmasi="([^"]*)"' % re.escape(AKSI["hapus"]), body).group(1)
    teks = html.unescape(konfirmasi)
    assert "hilang dari halaman publik" in teks and "tidak dapat dibatalkan" in teks
    assert "Jejak audit tetap tersimpan" in teks and 'Guru "Contoh" & Rekan' in teks


def test_konfirmasi_hapus_untuk_profil_tersembunyi_tidak_menyebut_hilang_dari_publik(server, admin):
    _siap()
    _tambah(server, admin)
    body = _minta(server, RUTE, cookie=admin)[1]
    konfirmasi = html.unescape(re.search(r'action="%s" data-konfirmasi="([^"]*)"' % re.escape(AKSI["hapus"]), body).group(1))
    assert "tidak sedang tampil" in konfirmasi and "hilang dari halaman publik" not in konfirmasi


# --- pemetaan galat POST -----------------------------------------------------------------

@pytest.mark.parametrize("galat", [KeyError("kunci"), IndexError("indeks")])
def test_keyerror_dan_indexerror_internal_menjadi_400_bukan_404(server, admin, monkeypatch, galat):
    _siap()
    data = {**_isi(server, admin, "tambah"), **ISIAN}

    def meledak(*a, **kw):
        raise galat
    monkeypatch.setattr(pg, "tambah", meledak)
    kode, body, _ = _kirim(server, admin, "tambah", data)
    assert kode == 400 and "Isian profil guru tidak sah." in body


def test_lookuperror_murni_dari_principal_hidup_tetap_404_identik(server, admin, monkeypatch):
    _siap()
    anon = _minta(server, AKSI["tambah"], data={})
    data = {**_isi(server, admin, "tambah"), **ISIAN}

    def akun_hilang(*a, **kw):
        raise LookupError("resource tidak ditemukan")
    monkeypatch.setattr(pg, "tambah", akun_hilang)
    kode, body, _ = _kirim(server, admin, "tambah", data)
    assert kode == 404 and (kode, body) == anon[:2]

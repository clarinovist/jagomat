"""Admin `/admin/lembaga`: buat lembaga, tambah/lepas anggota, bubarkan; CSRF, tinjauan, sandi admin.

Data sintetis. Semua POST memakai cookie admin + CSRF + tinjauan per aksi + sandi admin (jalur Kritis,
keputusan Pemilik 20 Nov 2026). Aksi gagal tidak boleh mengubah DB lembaga maupun berkas akun.
Token form selalu diambil dari <form> yang tepat (aksi + lembaga + guru), bukan token pertama di halaman.
"""
from __future__ import annotations

import re
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
BUAT, ANGGOTA, LEPAS, BUBARKAN = (
    "/admin/lembaga/buat", "/admin/lembaga/anggota", "/admin/lembaga/lepas", "/admin/lembaga/bubarkan")
JALUR_TULIS = (BUAT, ANGGOTA, LEPAS, BUBARKAN)


@pytest.fixture()
def data(server):
    for nama in ("pemilik-x", "guru-x1", "guru-x2", "guru-bebas"):
        auth.tambah_akun(nama, SANDI_ORANG_TUA + nama, "guru")
    auth.tambah_akun("admin-kedua", SANDI_ADMIN + "2", "admin")
    server.token = _login(server, "Admin-C", SANDI_ADMIN)
    return server


def _halaman(server, token=None):
    kode, isi, _ = _minta(server, "/admin/lembaga", cookie=token or server.token)
    assert kode == 200
    return isi


def _blok(isi, jalur, *penanda):
    """<form> pertama dengan action `jalur` yang memuat semua `penanda`."""
    for blok in re.findall(r"<form\b.*?</form>", isi, re.S):
        if 'action="%s"' % jalur in blok and all(p in blok for p in penanda):
            return blok
    raise AssertionError("form %s %r tidak ada" % (jalur, penanda))


def _tersembunyi(blok):
    return dict(re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)"', blok))


def _sah(server, jalur, *, lid=None, guru=None, nama="Les Admin", pemilik="guru-bebas",
         nama_konfirmasi=None, token=None):
    """Isian POST lengkap dan sah, dengan token dari form yang sesuai di halaman."""
    isi = _halaman(server, token)
    penanda = ()
    if lid is not None:
        penanda += ('name="lembaga_id" value="%d"' % lid,)
    if jalur == LEPAS:
        penanda += ('name="guru" value="%s"' % guru,)
    form = {**_tersembunyi(_blok(isi, jalur, *penanda)), "reauth": SANDI_ADMIN}
    if jalur == BUAT:
        form.update(nama=nama, pemilik=pemilik)
    elif jalur == ANGGOTA:
        form["guru"] = guru
    elif jalur == BUBARKAN:
        form["konfirmasi_nama"] = nama_konfirmasi if nama_konfirmasi is not None else _nama(server, lid)
    return form


def _nama(server, lid):
    with server.buka() as kon:
        return next(b["nama"] for b, _ in L.daftar_lembaga(kon) if b["id"] == lid)


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
    return _post(server, BUAT, _sah(server, BUAT, nama=nama, pemilik=pemilik), **kw)


def _id_lembaga(server):
    return _id_lembaga_milik(server, "pemilik-x")


def _id_lembaga_milik(server, pemilik):
    with server.buka() as kon:
        return L.lembaga_milik(kon, pemilik)["id"]


@pytest.fixture()
def siap(data):
    """Dua lembaga: Les Satu (pemilik-x, anggota guru-x1) dan Les Dua (guru-x2); guru-bebas calon."""
    with data.buka() as kon:
        satu = L.buat_lembaga(kon, nama="Les Satu", pemilik="pemilik-x")
        L.tambah_anggota(kon, lembaga_id=satu, guru="guru-x1")
        dua = L.buat_lembaga(kon, nama="Les Dua", pemilik="guru-x2")
    data.satu, data.dua = satu, dua
    return data


def _form_aksi(server, jalur, *, token=None):
    """Isian sah untuk `jalur` terhadap Les Satu."""
    if jalur == BUAT:
        return _sah(server, BUAT, token=token)
    if jalur == LEPAS:
        return _sah(server, LEPAS, lid=server.satu, guru="guru-x1", token=token)
    if jalur == ANGGOTA:
        return _sah(server, ANGGOTA, lid=server.satu, guru="guru-bebas", token=token)
    return _sah(server, BUBARKAN, lid=server.satu, token=token)


def test_halaman_admin_memuat_form_dan_tautan_nav(data):
    kode, isi, tajuk = _minta(data, "/admin/lembaga", cookie=data.token)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    assert 'href="/admin/lembaga"' in isi
    assert 'action="/admin/lembaga/buat"' in isi
    assert '<details class="admin-kartu admin-lembaga-buat"' in isi
    # Satu-satunya skrip: konfirmasi() tombol destruktif admin yang sudah disetujui.
    import admin_pages
    assert admin_pages.SKRIP_KONFIRMASI_LOGIN in isi
    assert 'src="' not in isi.lower().split("<script", 1)[-1].split("</script>", 1)[0]
    # Pilihan pemilik: hanya akun guru; admin dan murid tidak ditawarkan.
    for nama in ("pemilik-x", "guru-x1", "guru-bebas"):
        assert 'value="%s"' % nama in isi
    for nama in ("Admin-C", "admin-kedua", "feby"):
        assert 'value="%s"' % nama not in isi


def test_setiap_form_tulis_membawa_csrf_tinjauan_dan_sandi(siap):
    isi = _halaman(siap)
    forms = [b for b in re.findall(r"<form\b.*?</form>", isi, re.S) if 'action="/admin/lembaga/' in b]
    assert {re.search(r'action="([^"]+)"', b).group(1) for b in forms} == set(JALUR_TULIS)
    for blok in forms:
        assert 'name="csrf"' in blok and 'name="tinjauan"' in blok
        assert 'type="password" name="reauth"' in blok and "required" in blok


def test_kartu_ringkas_dengan_panel_kelola_tertutup_dan_satu_select_guru(siap):
    isi = _halaman(siap)
    kartu = [k for k in isi.split('<section class="admin-kartu admin-lembaga">')[1:]]
    assert len(kartu) == 2
    satu = next(k for k in kartu if "Les Satu" in k)
    assert "Pemilik les: pemilik-x · 1 guru" in satu
    assert '<li class="admin-badge">guru-x1</li>' in satu
    # Panel kelola dan zona bahaya tertutup bawaan (tanpa atribut open).
    assert '<details class="admin-lembaga-kelola">' in satu
    assert '<details class="admin-lembaga-bahaya">' in satu
    assert " open" not in satu.split("<summary>Kelola</summary>")[0].rsplit("<details", 1)[-1]
    # Satu select guru (Tambah) per kartu; Lepas memakai input tersembunyi, bukan select.
    assert satu.count('<select name="guru"') == 1
    assert 'name="konfirmasi_nama"' in satu


def test_nav_admin_lembaga_ada_di_semua_halaman_admin(data):
    assert 'href="/admin/lembaga"' in _minta(data, "/admin", cookie=data.token)[1]


def test_non_admin_404_identik_dengan_rute_admin_lain(data):
    acuan = _minta(data, "/admin/tidak-ada")[:2]
    assert acuan[0] == 404
    anonim = _minta(data, "/admin/lembaga")[:2]
    guru = _minta(data, "/admin/lembaga", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
    murid = _minta(data, "/admin/lembaga", auth_basic=("feby", SANDI_MURID))[:2]
    assert anonim == guru == murid == acuan
    for jalur in JALUR_TULIS:
        anonim = _minta(data, jalur, raw=b"a=b")[:2]
        guru = _minta(data, jalur, raw=b"a=b", auth_basic=("Ortu-C", SANDI_ORANG_TUA))[:2]
        assert anonim == guru == acuan
    assert _minta(data, "/admin/lembaga?x=1", cookie=data.token)[0] == 404


def test_get_tanpa_efek_samping(data):
    sebelum = _keadaan(data)
    assert _minta(data, "/admin/lembaga", cookie=data.token)[0] == 200
    assert _keadaan(data) == sebelum


# --- jalur sukses -----------------------------------------------------------------------

def test_buat_lembaga_sukses_lalu_pemilik_tidak_lagi_ditawarkan(data):
    kode, _, tajuk = _buat(data)
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(data)[0][0] == ((1, "Les Admin", "pemilik-x"),)
    isi = _halaman(data)
    assert "Les Admin" in isi
    pilihan = isi.split('action="/admin/lembaga/buat"', 1)[1].split("</form>", 1)[0]
    assert 'value="pemilik-x"' not in pilihan and 'value="guru-x1"' in pilihan


def test_tambah_dan_lepas_anggota(data):
    _buat(data)
    lid = _id_lembaga(data)
    kode, _, tajuk = _post(data, ANGGOTA, _sah(data, ANGGOTA, lid=lid, guru="guru-x1"))
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(data)[0][1] == ((lid, "guru-x1"),)
    assert 'action="/admin/lembaga/lepas"' in _halaman(data)
    kode, _, _ = _post(data, LEPAS, _sah(data, LEPAS, lid=lid, guru="guru-x1"))
    assert kode == 303 and _keadaan(data)[0][1] == ()


# --- lepas anggota: anak kembali ke pemilik lembaga ---------------------------------------

def _tambah_anak(server, nama, pemilik):
    with server.buka() as kon:
        return database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)


def _keadaan_anak(server):
    with server.buka() as kon:
        return tuple(
            tuple(tuple(r) for r in kon.execute(sql))
            for sql in ("SELECT id,nama,pemilik FROM siswa ORDER BY id",
                        "SELECT siswa_id,lembaga_id,dari,ke,oleh FROM pindah_siswa ORDER BY id"))


def _teks_konfirmasi(isi, guru):
    blok = _blok(isi, LEPAS, 'name="guru" value="%s"' % guru)
    return re.search(r'data-konfirmasi="([^"]*)"', blok).group(1)


def test_konfirmasi_lepas_menyebut_jumlah_anak_yang_kembali_ke_pemilik_les(siap):
    for nama in ("Anak Satu", "Anak Dua", "Anak Tiga"):
        _tambah_anak(siap, nama, "guru-x1")
    teks = _teks_konfirmasi(_halaman(siap), "guru-x1")
    assert teks == "Lepas guru-x1 dari lembaga? 3 anak akan kembali ke antrean lembaga (pemilik les)."
    assert "tetap milik gurunya" not in teks


def test_konfirmasi_lepas_tanpa_anak_tidak_menyebut_jumlah(siap):
    assert _teks_konfirmasi(_halaman(siap), "guru-x1") == "Lepas guru-x1 dari lembaga?"


def test_lepas_sukses_memindah_semua_anak_ke_pemilik_dengan_jejak_oleh_admin(siap):
    satu = _tambah_anak(siap, "Anak Satu", "guru-x1")
    kembar = _tambah_anak(siap, "Anak Kembar", "guru-x1")
    lama = _tambah_anak(siap, "Anak Kembar", "pemilik-x")
    lain = _tambah_anak(siap, "Anak Lain", "guru-x2")
    kode, _, tajuk = _post(siap, LEPAS, _sah(siap, LEPAS, lid=siap.satu, guru="guru-x1"))
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(siap)[0][1] == ()
    anak, jejak = _keadaan_anak(siap)
    punyaku = {satu, kembar, lama, lain}
    assert {a[0]: a[1:] for a in anak if a[0] in punyaku} == {
        satu: ("Anak Satu", "pemilik-x"), kembar: ("Anak Kembar (2)", "pemilik-x"),
        lama: ("Anak Kembar", "pemilik-x"), lain: ("Anak Lain", "guru-x2")}
    assert jejak == tuple((s, siap.satu, "guru-x1", "pemilik-x", "Admin-C") for s in (satu, kembar))


@pytest.mark.parametrize("kolom", ["mulai", "selesai"])
def test_lepas_ditolak_saat_sesi_berjalan_dengan_pesan_ramah_tanpa_efek(siap, kolom):
    bersih = _tambah_anak(siap, "Anak Bersih", "guru-x1")
    berjalan = _tambah_anak(siap, "Anak Berjalan", "guru-x1")
    with siap.buka() as kon:
        sesi = database.buat_sesi(kon, berjalan, seed=1, jumlah_soal=1)
        kon.execute("UPDATE sesi SET %s='2026-11-01 08:00:00' WHERE id=?" % kolom, (sesi,))
    form = _sah(siap, LEPAS, lid=siap.satu, guru="guru-x1")
    sebelum = (_keadaan(siap), _keadaan_anak(siap))
    kode, isi, _ = _post(siap, LEPAS, form)
    assert kode == 409
    assert "sesi yang sedang berjalan" in isi and "Selesaikan dan konfirmasi" in isi
    assert "Muat ulang halaman" not in isi
    assert (_keadaan(siap), _keadaan_anak(siap)) == sebelum
    # Setelah sesi dikonfirmasi, form yang sama boleh dipakai ulang.
    with siap.buka() as kon:
        kon.execute("UPDATE sesi SET dikonfirmasi_guru='guru-x1' WHERE id=?", (sesi,))
    assert _post(siap, LEPAS, form)[0] == 303
    assert {a[0]: a[2] for a in _keadaan_anak(siap)[0] if a[0] in (bersih, berjalan)} == {
        bersih: "pemilik-x", berjalan: "pemilik-x"}


def test_lepas_ditolak_bila_pembeda_nama_habis_dengan_pesan_ramah_tanpa_efek(siap):
    _tambah_anak(siap, "Anak Kembar", "guru-x1")
    _tambah_anak(siap, "Anak Kembar", "pemilik-x")
    for urut in range(2, L.BATAS_PEMBEDA + 1):
        _tambah_anak(siap, "Anak Kembar (%d)" % urut, "pemilik-x")
    sebelum = (_keadaan(siap), _keadaan_anak(siap))
    kode, isi, _ = _post(siap, LEPAS, _sah(siap, LEPAS, lid=siap.satu, guru="guru-x1"))
    assert kode == 409 and "nomor pembeda habis" in isi
    assert (_keadaan(siap), _keadaan_anak(siap)) == sebelum


def test_bubarkan_dengan_nama_persis_dan_sandi_berhasil(siap):
    kode, _, tajuk = _post(siap, BUBARKAN, _sah(siap, BUBARKAN, lid=siap.satu))
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(siap)[0] == (((siap.dua, "Les Dua", "guru-x2"),), ())


# --- sandi admin, tinjauan, CSRF: tolak tanpa efek samping --------------------------------

@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_tanpa_sandi_admin_ditolak_403_tanpa_efek(siap, jalur):
    form = _form_aksi(siap, jalur)
    sebelum = _keadaan(siap)
    form.pop("reauth")
    assert _post(siap, jalur, form)[0] == 403
    form["reauth"] = ""
    assert _post(siap, jalur, form)[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_sandi_salah_ditolak_403_tanpa_efek(siap, jalur):
    form = _form_aksi(siap, jalur)
    sebelum = _keadaan(siap)
    for salah in ("sandi-salah", SANDI_ADMIN + "x", SANDI_ADMIN + "2", SANDI_ORANG_TUA + "pemilik-x"):
        assert _post(siap, jalur, {**form, "reauth": salah})[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_csrf_hilang_atau_palsu_ditolak_tanpa_efek(siap, jalur):
    form = _form_aksi(siap, jalur)
    sebelum = _keadaan(siap)
    tanpa = {k: v for k, v in form.items() if k != "csrf"}
    assert _post(siap, jalur, tanpa)[0] == 403
    assert _post(siap, jalur, {**form, "csrf": "palsu"})[0] == 403
    assert _post(siap, jalur, {**form, "csrf": form["tinjauan"]})[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_tinjauan_hilang_palsu_atau_rusak_ditolak_tanpa_efek(siap, jalur):
    form = _form_aksi(siap, jalur)
    sebelum = _keadaan(siap)
    tanpa = {k: v for k, v in form.items() if k != "tinjauan"}
    assert _post(siap, jalur, tanpa)[0] == 403
    assert _post(siap, jalur, {**form, "tinjauan": "palsu"})[0] == 403
    badan, _, tanda = form["tinjauan"].partition(".")
    assert _post(siap, jalur, {**form, "tinjauan": badan + "." + tanda[::-1]})[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_tinjauan_aksi_lain_ditolak_tanpa_efek(siap, jalur):
    """Tinjauan aksi A tidak boleh dipakai di rute aksi B (terikat aksi)."""
    sebelum = _keadaan(siap)
    for lain in JALUR_TULIS:
        if lain == jalur:
            continue
        form = {**_form_aksi(siap, jalur), "tinjauan": _form_aksi(siap, lain)["tinjauan"]}
        assert _post(siap, jalur, form)[0] == 403
    assert _keadaan(siap) == sebelum


def test_tinjauan_lembaga_lain_atau_guru_lain_ditolak_tanpa_efek(siap):
    """Token terikat target: lembaga 1 tidak boleh dipakai untuk lembaga 2, lepas guru A tidak untuk guru B."""
    with siap.buka() as kon:
        L.tambah_anggota(kon, lembaga_id=siap.dua, guru="guru-bebas")
    sebelum = _keadaan(siap)
    token_satu = _sah(siap, BUBARKAN, lid=siap.satu)["tinjauan"]
    assert _post(siap, BUBARKAN, {**_sah(siap, BUBARKAN, lid=siap.dua), "tinjauan": token_satu})[0] == 403
    assert _post(siap, BUBARKAN, {**_sah(siap, BUBARKAN, lid=siap.dua), "lembaga_id": str(siap.satu)})[0] == 403
    lepas_satu = _sah(siap, LEPAS, lid=siap.satu, guru="guru-x1")
    assert _post(siap, LEPAS, {**lepas_satu, "lembaga_id": str(siap.dua), "guru": "guru-bebas"})[0] == 403
    assert _post(siap, LEPAS, {**lepas_satu, "guru": "guru-bebas"})[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_tinjauan_dan_csrf_dari_sesi_lain_ditolak(siap, jalur):
    token_lain = _login(siap, "admin-kedua", SANDI_ADMIN + "2")
    form_lain = _form_aksi(siap, jalur, token=token_lain)
    sebelum = _keadaan(siap)
    # Sandi admin pertama benar, tetapi token milik sesi admin lain.
    assert _post(siap, jalur, {**form_lain, "reauth": SANDI_ADMIN})[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_post_lintas_situs_ditolak_tanpa_efek(siap, jalur):
    form = _form_aksi(siap, jalur)
    sebelum = _keadaan(siap)
    assert _post(siap, jalur, form, headers=LINTAS)[0] == 403
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("jalur", JALUR_TULIS)
def test_post_dengan_field_asing_atau_ganda_ditolak_tanpa_efek(siap, jalur):
    form = _form_aksi(siap, jalur)
    sebelum = _keadaan(siap)
    assert _post(siap, jalur, {**form, "asing": "1"})[0] == 400
    ganda = urllib.parse.urlencode(form) + "&reauth=" + urllib.parse.quote(SANDI_ADMIN)
    kode, _, _ = _minta(siap, jalur, cookie=siap.token, raw=ganda.encode(),
                        headers={"Origin": siap.alamat, "Sec-Fetch-Site": "same-origin"})
    assert kode == 400
    assert _keadaan(siap) == sebelum


def test_basic_admin_tidak_mendapat_form_dan_post_ditolak(siap):
    kode, isi, _ = _minta(siap, "/admin/lembaga", auth_basic=("Admin-C", SANDI_ADMIN))
    assert kode == 200 and 'action="/admin/lembaga/' not in isi and "Les Satu" in isi
    sebelum = _keadaan(siap)
    form = _form_aksi(siap, BUAT)
    for jalur in JALUR_TULIS:
        kode, _, _ = _minta(
            siap, jalur, auth_basic=("Admin-C", SANDI_ADMIN),
            raw=urllib.parse.urlencode(form).encode(),
            headers={"Origin": siap.alamat, "Sec-Fetch-Site": "same-origin"})
        assert kode == 403
    assert _keadaan(siap) == sebelum


# --- bubarkan: konfirmasi nama divalidasi di server ---------------------------------------

@pytest.mark.parametrize("ketikan", ["", "Les", "les satu", "LES SATU", "Les Satu ", " Les Satu", "Les Dua", "Les  Satu"])
def test_bubarkan_nama_salah_ditolak_400_tanpa_efek(siap, ketikan):
    form = _sah(siap, BUBARKAN, lid=siap.satu, nama_konfirmasi=ketikan)
    sebelum = _keadaan(siap)
    kode, isi, _ = _post(siap, BUBARKAN, form)
    assert kode == 400 and "tidak cocok" in isi
    assert _keadaan(siap) == sebelum


def test_bubarkan_tanpa_field_nama_ditolak_tanpa_efek(siap):
    form = _sah(siap, BUBARKAN, lid=siap.satu)
    form.pop("konfirmasi_nama")
    sebelum = _keadaan(siap)
    assert _post(siap, BUBARKAN, form)[0] == 400
    assert _keadaan(siap) == sebelum


def test_bubarkan_menghapus_lembaga_anggota_anak_dan_jejak_tetap(data):
    _buat(data)
    lid = _id_lembaga(data)
    _post(data, ANGGOTA, _sah(data, ANGGOTA, lid=lid, guru="guru-x1"))
    with data.buka() as kon:
        anak = database.tambah_siswa(kon, "Anak Bubar", "P3", pemilik="guru-x1")
        kon.execute("INSERT INTO pindah_siswa(siswa_id,lembaga_id,dari,ke,oleh)"
                    " VALUES (?,?,?,?,?)", (anak, lid, "pemilik-x", "guru-x1", "pemilik-x"))
    isi = _halaman(data)
    assert 'action="/admin/lembaga/bubarkan"' in isi and "data-konfirmasi=" in isi
    kode, _, tajuk = _post(data, BUBARKAN, _sah(data, BUBARKAN, lid=lid))
    assert kode == 303 and tajuk["Location"] == "/admin/lembaga"
    assert _keadaan(data)[0] == ((), ())
    with data.buka() as kon:
        assert kon.execute("SELECT pemilik FROM siswa WHERE id=?", (anak,)).fetchone()[0] == "guru-x1"
        assert kon.execute("SELECT lembaga_id FROM pindah_siswa").fetchone()[0] == lid
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


def test_bubarkan_lembaga_yang_sudah_hilang_409_tanpa_efek(siap):
    form = _sah(siap, BUBARKAN, lid=siap.satu)
    assert _post(siap, BUBARKAN, form)[0] == 303
    sebelum = _keadaan(siap)
    assert _post(siap, BUBARKAN, form)[0] == 409
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("lid", ["999", "0", "abc", ""])
def test_bubarkan_id_tidak_sah_atau_tidak_cocok_tinjauan_tanpa_efek(siap, lid):
    form = {**_sah(siap, BUBARKAN, lid=siap.satu), "lembaga_id": lid}
    sebelum = _keadaan(siap)
    assert _post(siap, BUBARKAN, form)[0] in (400, 403)
    assert _keadaan(siap) == sebelum


# --- aturan domain tetap berlaku di belakang reauth ---------------------------------------

@pytest.mark.parametrize("pemilik", ["Admin-C", "admin-kedua", "feby", "tidak-ada", ""])
def test_pemilik_harus_akun_guru_yang_ada(data, pemilik):
    sebelum = _keadaan(data)
    assert _buat(data, pemilik=pemilik)[0] == 400
    assert _keadaan(data) == sebelum


@pytest.mark.parametrize("nama", ["", "   ", "x" * 81])
def test_nama_lembaga_tidak_sah_ditolak(data, nama):
    sebelum = _keadaan(data)
    assert _buat(data, nama=nama)[0] == 400
    assert _keadaan(data) == sebelum


def test_pemilik_ganda_dan_anggota_jadi_pemilik_ditolak_409(siap):
    form_buat = _sah(siap, BUAT)
    sebelum = _keadaan(siap)
    assert _post(siap, BUAT, {**form_buat, "pemilik": "pemilik-x"})[0] == 409
    assert _post(siap, BUAT, {**form_buat, "pemilik": "guru-x1"})[0] == 409
    assert _keadaan(siap) == sebelum


@pytest.mark.parametrize("guru", ["Admin-C", "admin-kedua", "feby", "tidak-ada", "pemilik-x", ""])
def test_anggota_harus_guru_yang_ada_dan_bukan_pemilik(siap, guru):
    form = {**_sah(siap, ANGGOTA, lid=siap.satu, guru="guru-bebas"), "guru": guru}
    sebelum = _keadaan(siap)
    assert _post(siap, ANGGOTA, form)[0] in (400, 409)
    assert _keadaan(siap) == sebelum


def test_anggota_tidak_boleh_masuk_dua_lembaga(siap):
    form = _sah(siap, ANGGOTA, lid=siap.dua, guru="guru-bebas")
    sebelum = _keadaan(siap)
    assert _post(siap, ANGGOTA, {**form, "guru": "guru-x1"})[0] == 409
    assert _keadaan(siap) == sebelum


def test_lepas_anggota_yang_sudah_lepas_409_tanpa_efek(siap):
    form = _sah(siap, LEPAS, lid=siap.satu, guru="guru-x1")
    assert _post(siap, LEPAS, form)[0] == 303
    sebelum = _keadaan(siap)
    assert _post(siap, LEPAS, form)[0] == 409
    assert _keadaan(siap) == sebelum


def test_halaman_admin_tanpa_data_anak(data):
    with data.buka() as kon:
        database.tambah_siswa(kon, "Anak Rahasia Admin", "P3", pemilik="guru-x1")
    _buat(data)
    lid = _id_lembaga(data)
    _post(data, ANGGOTA, _sah(data, ANGGOTA, lid=lid, guru="guru-x1"))
    isi = _halaman(data)
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
    assert _post(data, BUBARKAN, _sah(data, BUBARKAN, lid=lid))[0] == 303
    assert _hapus_login(data, "guru-x1")[0] == 303
    assert auth.cari_akun("guru-x1") is None


# Butir QA #5 (25 Nov 2026): "Tambah guru" hanya mengikat guru yang sudah ada; admin perlu jalan ke pembuatan akun guru.
def test_form_tambah_guru_menaut_ke_buat_akun_guru_baik_ada_calon_maupun_kosong():
    import admin_lembaga_pages as P
    token = P.TokenLembaga(csrf="c", buat="b", tambah={1: "tinjauan"})
    tautan = 'href="/admin/tinjau?aksi=account_teacher_create">Buat akun guru baru</a>'
    assert tautan in P._form_tambah(token, 1, ["guru-a"])
    kosong = P._form_tambah(token, 1, [])
    assert "Semua guru sudah terikat pada lembaga." in kosong and tautan in kosong
    assert P._form_tambah(P.TokenLembaga(csrf="c", buat="b"), 1, ["guru-a"]) == ""

"""Edit pemetaan CP per grup di `/admin/kurikulum/cp` (3c): guard POST admin, konflik revisi, fallback DB rusak.

Data SINTETIS. DB kurikulum diarahkan ke tmp_path; grup target dan revisi hanya dari tinjauan bertanda tangan.
"""
from __future__ import annotations

import html
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_http  # noqa: E402
import admin_kurikulum_cp_http as cp_http  # noqa: E402
import admin_kurikulum_cp_pages as ui  # noqa: E402
import admin_security  # noqa: E402
import auth  # noqa: E402
import kurikulum_cp as cp  # noqa: E402
import kurikulum_override as ko  # noqa: E402
from admin_transfer_kit import LINTAS_SITUS, id_admin, login_admin, minta_admin  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import jam, keluarga, minta_mentah, server, tertutup  # noqa: E402,F401

HALAMAN_EDIT = "/admin/kurikulum/cp"
HALAMAN_PETA = "/admin/kurikulum/cp-detail"
KEMBALIKAN = HALAMAN_EDIT + "/kembalikan"
TAK_ADA = "/admin/tidak-ada"
GRUP = ("bilangan-dasar", "nilai_tempat")
GRUP_LAIN = ("bilangan-dasar", "membandingkan")
BAWAAN = (("A.bilangan.2", "sebagian"), ("A.bilangan.4", "sebagian"))
AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
POLA_SELECT = re.compile(r'<select name="((?:butir|cocok)_\d+)">(.*?)</select>', re.S)
POLA_HIDDEN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)"')
POLA_FORM = re.compile(r'<form[^>]*action="(/admin/kurikulum/cp[^"]*)"[^>]*>(.*?)</form>', re.S)
DIR_RENDER = Path(tempfile.gettempdir()) / "jagomat-render"


@pytest.fixture(autouse=True)
def _db_kurikulum_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv(ko.ENV_BERKAS_DB, str(tmp_path / "kurikulum.db"))
    ko.bersihkan_cache()
    yield
    ko.bersihkan_cache()


@pytest.fixture()
def admin(tertutup):
    return login_admin(tertutup)


def _db() -> Path:
    return ko._path_db(None)


def _item(kunci=GRUP):
    ko.bersihkan_cache()
    return next(i for i in ko.daftar_cp() if (i.topik_id, i.grup_kode) == kunci)


def _audit():
    if not _db().exists():
        return []
    with sqlite3.connect(_db()) as kon:
        kon.row_factory = sqlite3.Row
        return [dict(r) for r in kon.execute("SELECT * FROM audit_kurikulum ORDER BY id")]


def _stempel():
    """(nilai efektif + revisi semua grup, audit); dibaca segar, tanpa membuat berkas."""
    ko.bersihkan_cache()
    return [(i.efektif, i.revisi) for i in ko.daftar_cp()], _audit()


def _grup(kunci=GRUP) -> str:
    return "%s/%s" % kunci


def _token(cookie, kunci=GRUP, revisi=0, aksi=ui.AKSI_UBAH_CP, target=None):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": target or _grup(kunci), "target_revisi": revisi})}


def _baris(pasangan=()):
    """12 baris tetap: pasangan terisi dari atas, sisanya butir kosong."""
    data = {}
    for no in range(1, ko.MAKS_PASANGAN_CP + 1):
        butir, cocok = pasangan[no - 1] if no <= len(pasangan) else ("", "sebagian")
        data["butir_%d" % no], data["cocok_%d" % no] = butir, cocok
    return data


def _kirim(server, cookie, pasangan, *, kunci=GRUP, revisi=0, ganti=None, hapus=(), ekstra=None,
           headers=None, aksi=ui.AKSI_UBAH_CP, jalur=HALAMAN_EDIT, target=None, isi=None):
    data = {**_token(cookie, kunci, revisi, aksi, target), **(_baris(pasangan) if isi is None else isi),
            **(ekstra or {}), **(ganti or {})}
    for nama in hapus:
        data.pop(nama, None)
    return minta_mentah(server, jalur, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def _kembalikan(server, cookie, *, kunci=GRUP, revisi=1, ganti=None, ekstra=None, aksi=ui.AKSI_KEMBALIKAN_CP):
    data = {**_token(cookie, kunci, revisi, aksi), **(ekstra or {}), **(ganti or {})}
    return minta_mentah(server, KEMBALIKAN, None, data, {"Cookie": "osn_sesi=" + cookie})


def _edit(server, cookie, kunci=GRUP, tambah=""):
    return minta_admin(server, "%s?grup=%s%s" % (HALAMAN_EDIT, quote(_grup(kunci), safe=""), tambah), cookie)


def _badan(isi: str) -> str:
    """Isi halaman tanpa blok CSS bingkai (yang memuat kata seperti name="reauth")."""
    return isi.rsplit("</style>", 1)[-1]


def _form_ubah(isi: str) -> dict:
    """Field form Simpan persis seperti peramban mengirimnya: hidden + opsi terpilih tiap select."""
    badan = next(b for aksi, b in POLA_FORM.findall(isi) if aksi == HALAMAN_EDIT)
    data = {k: html.unescape(v) for k, v in POLA_HIDDEN.findall(badan)}
    for nama, opsi in POLA_SELECT.findall(badan):
        terpilih = re.search(r'<option value="([^"]*)" selected>', opsi)
        data[nama] = html.unescape(terpilih.group(1)) if terpilih else re.search(r'value="([^"]*)"', opsi).group(1)
    return data


def _ubah_geometri(server, cookie, **kw):
    return _kirim(server, cookie, (("A.geometri.1", "penuh"),) + BAWAAN, **kw)


# --- akses ----------------------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_menyentuh_db(tertutup, admin, akun, monkeypatch):
    def gagal(*_a, **_k):
        raise AssertionError("DB kurikulum tidak boleh disentuh")

    acuan_get = minta_mentah(tertutup, TAK_ADA, akun)
    acuan_post = minta_mentah(tertutup, TAK_ADA, akun, {"x": "1"})
    with monkeypatch.context() as ctx:
        for nama in ("daftar_cp", "riwayat_cp", "ubah_cp", "kembalikan_cp"):
            ctx.setattr(ko, nama, gagal)
        alamat = "%s?grup=%s" % (HALAMAN_EDIT, quote(_grup(), safe=""))
        assert minta_mentah(tertutup, alamat, akun)[:2] == acuan_get[:2]
        for jalur in (HALAMAN_EDIT, KEMBALIKAN):
            assert minta_mentah(tertutup, jalur, akun, {})[:2] == acuan_post[:2]
            assert minta_mentah(tertutup, jalur, akun, _token(admin))[:2] == acuan_post[:2]
    assert acuan_get[0] == acuan_post[0] == 404
    assert not _db().exists()


@pytest.mark.parametrize("query", [
    "", "?grup=", "?grup=bilangan-dasar", "?grup=bilangan-dasar/tidak_ada", "?grup=asing/nilai_tempat",
    "?grup=bilangan-dasar%2Fnilai_tempat%2F", "?grup=BILANGAN-DASAR%2Fnilai_tempat",
    "?grup=bilangan-dasar%2Fnilai_tempat&x=1", "?x=1",
    "?grup=bilangan-dasar%2Fnilai_tempat&grup=bilangan-dasar%2Fnilai_tempat",
    "?grup=bilangan-dasar%2Fnilai_tempat&hasil=sembarang",
    "?grup=bilangan-dasar%2Fnilai_tempat&hasil=tersimpan&hasil=tersimpan",
])
def test_query_tak_sah_404_identik(tertutup, admin, query):
    acuan = minta_admin(tertutup, TAK_ADA, admin)
    kode, isi, _t = minta_admin(tertutup, HALAMAN_EDIT + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


# --- tampilan -------------------------------------------------------------------------------

def test_halaman_edit_memuat_judul_pola_nilai_efektif_dan_form_dua_belas_baris(tertutup, admin, tmp_path):
    kode, isi, tajuk = _edit(tertutup, admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store" and "<script" not in _badan(isi)
    assert "<h2>Bilangan Dasar · Nilai tempat puluhan dan satuan <code>nilai_tempat</code></h2>" in isi
    assert "Template pola grup: <code>nilai_tempat</code>" in isi
    assert "bawaan kode" in isi
    form = _form_ubah(isi)
    assert {"csrf", "tinjauan", "butir_1", "butir_12", "cocok_1", "cocok_12"} <= set(form)
    assert len([k for k in form if k.startswith("butir_")]) == ko.MAKS_PASANGAN_CP
    assert (form["butir_1"], form["cocok_1"]) == BAWAAN[0] and (form["butir_2"], form["cocok_2"]) == BAWAAN[1]
    assert form["butir_3"] == "" and form["cocok_3"] == "sebagian"
    assert isi.count("<optgroup") == 12 * len({(b.fase, b.elemen) for b in cp.CAPAIAN})
    assert 'name="reauth"' in _badan(isi) and 'action="%s"' % KEMBALIKAN not in isi  # sumber bawaan: tanpa kembalikan
    assert SANDI_ADMIN not in isi and str(tmp_path) not in isi and "kurikulum.db" not in isi
    assert not _db().exists()


def test_opsi_butir_memuat_85_butir_dengan_teks_dipotong_dan_aman():
    isi = ui.halaman_edit(_item(), nama_topik="T", nama_grup="G", pola=("p1",), riwayat=(),
                          token_ubah=("c", "t"), token_kembalikan=None)
    baris = re.search(r'<select name="butir_1">(.*?)</select>', isi, re.S).group(1)
    opsi = re.findall(r'<option value="([^"]*)"[^>]*>(.*?)</option>', baris)
    assert len(opsi) == len(cp.CAPAIAN) + 1 and opsi[0][0] == ""
    assert all(len(html.unescape(teks).split(" — ", 1)[-1]) <= ui.MAKS_TEKS_OPSI for _v, teks in opsi[1:])


def test_halaman_basic_auth_baca_saja_tanpa_form_dan_post_403(tertutup):
    kode, isi, _t = minta_mentah(tertutup, "%s?grup=%s" % (HALAMAN_EDIT, quote(_grup(), safe="")), AKUN_ADMIN)
    assert kode == 200 and not POLA_FORM.findall(_badan(isi)) and "baca-saja" in isi.lower()
    assert 'name="tinjauan"' not in _badan(isi)
    assert minta_mentah(tertutup, HALAMAN_EDIT, AKUN_ADMIN, _token("sesi-sintetis") | _baris(BAWAAN))[0] == 403
    assert not _db().exists()


def test_banner_hasil_hanya_dari_kode_dikenal(tertutup, admin):
    assert 'role="status"' in _edit(tertutup, admin, tambah="&hasil=tersimpan")[1]
    assert 'role="status"' in _edit(tertutup, admin, tambah="&hasil=dikembalikan")[1]
    assert 'role="status"' not in _badan(_edit(tertutup, admin)[1])


# --- ubah -----------------------------------------------------------------------------------

def test_ubah_sah_menyimpan_audit_satu_redirect_banner_dan_peta_ikut_berubah(tertutup, admin):
    peta_sebelum = minta_admin(tertutup, HALAMAN_PETA, admin)[1]
    assert "<code>A.geometri.1</code>" in peta_sebelum.split("<h2>Butir CP per fase</h2>")[0]  # masih celah SD
    assert "Grup dengan pemetaan diubah admin</dt><dd>0" in peta_sebelum
    kode, isi, tajuk = _ubah_geometri(tertutup, admin)
    assert (kode, isi) == (303, "")
    assert tajuk["Location"] == "%s?grup=%s&hasil=tersimpan" % (HALAMAN_EDIT, quote(_grup(), safe=""))
    item = _item()
    assert item.efektif == BAWAAN + (("A.geometri.1", "penuh"),) and item.sumber == "admin" and item.revisi == 1
    audit = _audit()
    assert len(audit) == 1 and audit[0]["kunci"] == _grup() and audit[0]["actor_id"] == id_admin()
    kode, halaman, _t = minta_admin(tertutup, tajuk["Location"], admin)
    assert kode == 200 and "tersimpan dan langsung berlaku" in halaman
    assert "diubah admin, revisi 1" in halaman and "Kembalikan ke bawaan" in halaman
    assert id_admin() in halaman and "<code>A.geometri.1</code>" in halaman  # riwayat + nilai efektif
    peta = minta_admin(tertutup, HALAMAN_PETA, admin)[1]
    assert "diubah admin, revisi 1" in peta and "Grup dengan pemetaan diubah admin</dt><dd>1" in peta
    celah = peta.split("<h2>Butir CP per fase</h2>")[0]
    assert "<code>A.geometri.1</code>" not in celah and "<code>A.pengukuran.1</code>" in celah
    assert "5 butir" in celah and "6 butir" in peta_sebelum.split("<h2>Butir CP per fase</h2>")[0]


def test_form_dari_halaman_dapat_dikirim_apa_adanya_dua_puluh_tujuh_field(tertutup, admin):
    form = _form_ubah(_edit(tertutup, admin)[1])
    form["butir_3"], form["cocok_3"] = "A.geometri.1", "prasyarat"
    assert len(form) + 1 == cp_http.MAKS_FIELD_CP  # + reauth
    kode, _i, tajuk = minta_admin(tertutup, HALAMAN_EDIT, admin, {**form, "reauth": SANDI_ADMIN})
    assert kode == 303 and tajuk["Location"].endswith("hasil=tersimpan")
    assert ("A.geometri.1", "prasyarat") in _item().efektif


def test_mengosongkan_semua_baris_menjadikan_grup_di_luar_cp(tertutup, admin):
    assert _kirim(tertutup, admin, ())[0] == 303
    assert _item().efektif == () and _item().sumber == "admin"


def test_isi_sama_dengan_bawaan_tidak_membuat_revisi_atau_audit(tertutup, admin):
    assert _kirim(tertutup, admin, BAWAAN)[0] == 303
    assert _item().revisi == 0 and _audit() == []


# --- guard ----------------------------------------------------------------------------------

@pytest.mark.parametrize("kasus", ["tanpa_csrf", "csrf_salah", "tinjauan_palsu", "tanpa_tinjauan",
                                   "reauth_salah", "tanpa_reauth"])
def test_token_cacat_403_tanpa_mengubah_store(tertutup, admin, kasus):
    ganti, hapus = {
        "tanpa_csrf": ({}, ("csrf",)), "csrf_salah": ({"csrf": "rusak"}, ()),
        "tinjauan_palsu": ({"tinjauan": "palsu.palsu"}, ()), "tanpa_tinjauan": ({}, ("tinjauan",)),
        "reauth_salah": ({"reauth": "salah-sandi"}, ()), "tanpa_reauth": ({}, ("reauth",)),
    }[kasus]
    assert _ubah_geometri(tertutup, admin, ganti=ganti, hapus=hapus)[0] == 403
    assert not _db().exists()


def test_tinjauan_aksi_lain_sesi_lain_atau_basic_auth_ditolak(tertutup, admin):
    assert _ubah_geometri(tertutup, admin, aksi=ui.AKSI_KEMBALIKAN_CP)[0] == 403
    assert _ubah_geometri(tertutup, admin, aksi="ubah_sakelar")[0] == 403
    assert _kembalikan(tertutup, admin, aksi=ui.AKSI_UBAH_CP)[0] == 403
    asing = {**_token("sesi-lain-sintetis"), **_baris((("A.geometri.1", "penuh"),))}
    assert minta_admin(tertutup, HALAMAN_EDIT, admin, asing)[0] == 403
    assert not _db().exists()


def test_permintaan_lintas_situs_403_tanpa_efek(tertutup, admin):
    assert _ubah_geometri(tertutup, admin, headers=LINTAS_SITUS)[0] == 403
    assert not _db().exists()


@pytest.mark.parametrize("ekstra", [{"target_id": _grup(GRUP_LAIN)}, {"grup": _grup(GRUP_LAIN)},
                                    {"topik_id": "bilangan-dasar"}, {"revisi": "9"}, {"butir_13": "A.geometri.1"},
                                    {"aksi": "x", "nama": "y"}])
def test_target_dan_revisi_tak_bisa_diganti_lewat_field_form(tertutup, admin, ekstra):
    kode, _i, _t = _ubah_geometri(tertutup, admin, ekstra=ekstra)
    assert kode == 400
    assert not _db().exists()


def test_field_asing_menggantikan_satu_baris_ditolak_tanpa_bergantung_pada_batas_field(tertutup, admin):
    """27 field persis (jumlah sah) tetapi himpunan namanya salah: hanya `wajib_field` yang menolak."""
    data = _baris(BAWAAN)
    del data["cocok_12"]
    data["target_id"] = _grup(GRUP_LAIN)
    assert len(data) + 3 == cp_http.MAKS_FIELD_CP
    assert _kirim(tertutup, admin, (), isi=data)[0] == 400
    assert _item(GRUP).revisi == 0 and _item(GRUP_LAIN).revisi == 0 and _audit() == []


def test_tinjauan_grup_x_dengan_field_grup_y_tidak_mengubah_keduanya(tertutup, admin):
    kode, _i, _t = _ubah_geometri(tertutup, admin, ekstra={"target_id": _grup(GRUP_LAIN)})
    assert kode == 400
    assert _item(GRUP).revisi == 0 and _item(GRUP_LAIN).revisi == 0 and _audit() == []


def test_target_hanya_dari_tinjauan_bukan_dari_field_baris(tertutup, admin):
    """Tinjauan grup X mengubah X saja, tidak pernah grup lain."""
    assert _ubah_geometri(tertutup, admin)[0] == 303
    assert _item(GRUP).revisi == 1 and _item(GRUP_LAIN).revisi == 0 and _item(GRUP_LAIN).efektif == (
        cp.CP_PER_GRUP[GRUP_LAIN])


@pytest.mark.parametrize("target,revisi", [("asing/grup", 0), ("bilangan-dasar", 0), ("bilangan-dasar/", 0),
                                           ("/nilai_tempat", 0), (_grup(), -1)])
def test_isi_tinjauan_tak_sah_400_bukan_500(tertutup, admin, target, revisi):
    kode, _i, _t = _kirim(tertutup, admin, BAWAAN[:1], revisi=revisi, target=target)
    assert kode == 400
    assert not _db().exists()


# --- konflik --------------------------------------------------------------------------------

def test_dua_tinjauan_revisi_sama_yang_kedua_409_dan_store_memuat_hasil_pertama(tertutup, admin):
    pertama = _token(admin, GRUP, 0)
    kedua = _token(admin, GRUP, 0)
    kirim = lambda token, pasangan: minta_mentah(  # noqa: E731
        tertutup, HALAMAN_EDIT, None, {**token, **_baris(pasangan)}, {"Cookie": "osn_sesi=" + admin})
    assert kirim(pertama, (("A.geometri.1", "penuh"),))[0] == 303
    sebelum = _stempel()
    kode, isi, _t = kirim(kedua, (("A.geometri.4", "penuh"),))
    assert kode == 409 and "Buka ulang" in isi and "Traceback" not in isi
    assert _stempel() == sebelum and _item().efektif == (("A.geometri.1", "penuh"),)


def test_kirim_ulang_form_sama_setelah_sukses_409_tanpa_ubah_ulang(tertutup, admin):
    form = _form_ubah(_edit(tertutup, admin)[1])
    form["butir_3"], form["cocok_3"] = "A.geometri.1", "penuh"
    assert minta_admin(tertutup, HALAMAN_EDIT, admin, {**form, "reauth": SANDI_ADMIN})[0] == 303
    sebelum = _stempel()
    assert minta_admin(tertutup, HALAMAN_EDIT, admin, {**form, "reauth": SANDI_ADMIN})[0] == 409
    assert _stempel() == sebelum


# --- isian tak sah --------------------------------------------------------------------------

@pytest.mark.parametrize("isi", [
    (("Z.asing.1", "penuh"),),
    (("A.geometri.1", "asing"),),
    (("A.geometri.1", "penuh"), ("A.geometri.1", "sebagian")),
    (("A.geometri.1", ""),),
], ids=["butir_asing", "kecocokan_asing", "butir_ganda", "kecocokan_kosong_pada_butir_terisi"])
def test_isian_tak_sah_400_dan_store_tidak_berubah(tertutup, admin, isi):
    kode, teks, _t = _kirim(tertutup, admin, isi)
    assert kode == 400 and "tidak sah" in teks and "Traceback" not in teks
    assert not _db().exists()


def test_kecocokan_asing_pada_baris_kosong_tetap_ditolak(tertutup, admin):
    data = _baris(BAWAAN)
    data["cocok_5"] = "asing"
    assert _kirim(tertutup, admin, (), isi=data)[0] == 400
    assert not _db().exists()


def test_baris_kurang_atau_butir_ketiga_belas_ditolak(tertutup, admin):
    data = _baris(BAWAAN)
    del data["cocok_12"]
    assert _kirim(tertutup, admin, (), isi=data)[0] == 400
    assert not _db().exists()


# --- kembalikan -----------------------------------------------------------------------------

def test_kembalikan_ke_bawaan_revisi_naik_dan_audit_tercatat(tertutup, admin):
    assert _ubah_geometri(tertutup, admin)[0] == 303
    kode, isi, tajuk = _kembalikan(tertutup, admin, revisi=1)
    assert (kode, isi) == (303, "") and tajuk["Location"].endswith("hasil=dikembalikan")
    item = _item()
    assert item.efektif == BAWAAN and item.sumber == "bawaan" and item.revisi == 2
    assert len(_audit()) == 2 and _audit()[1]["revisi"] == 2
    halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert "dikembalikan ke bawaan kode" in halaman and 'action="%s"' % KEMBALIKAN not in halaman
    assert halaman.count("Revisi 2") == 1 and halaman.count("Revisi 1") == 1  # riwayat terbaru dulu


def test_kembalikan_dengan_field_asing_atau_revisi_basi_ditolak(tertutup, admin):
    assert _ubah_geometri(tertutup, admin)[0] == 303
    sebelum = _stempel()
    assert _kembalikan(tertutup, admin, revisi=1, ekstra={"target_id": _grup(GRUP_LAIN)})[0] == 400
    assert _kembalikan(tertutup, admin, revisi=0)[0] == 409
    assert _kembalikan(tertutup, admin, revisi=1, ganti={"reauth": "salah"})[0] == 403
    assert _stempel() == sebelum


def test_kembalikan_form_ada_hanya_bila_sumber_admin(tertutup, admin):
    assert 'action="%s"' % KEMBALIKAN not in _edit(tertutup, admin)[1]
    assert _ubah_geometri(tertutup, admin)[0] == 303
    isi = _edit(tertutup, admin)[1]
    form = next(b for aksi, b in POLA_FORM.findall(isi) if aksi == KEMBALIKAN)
    assert 'name="reauth"' in form and "butir_1" not in form
    data = {k: html.unescape(v) for k, v in POLA_HIDDEN.findall(form)}
    assert minta_admin(tertutup, KEMBALIKAN, admin, {**data, "reauth": SANDI_ADMIN})[0] == 303
    assert _item().efektif == BAWAAN


# --- DB rusak -------------------------------------------------------------------------------

def test_db_rusak_get_tetap_200_dengan_bawaan_dan_post_503_tanpa_path(tertutup, admin, tmp_path):
    _db().write_bytes(b"bukan sqlite sama sekali")
    ko.bersihkan_cache()
    for alamat in (HALAMAN_PETA,):
        assert minta_admin(tertutup, alamat, admin)[0] == 200
    kode, isi, _t = _edit(tertutup, admin)
    assert kode == 200 and "bawaan kode" in isi and _form_ubah(isi)["butir_1"] == BAWAAN[0][0]
    kode, isi, _t = _ubah_geometri(tertutup, admin)
    assert kode == 503 and str(tmp_path) not in isi and "kurikulum.db" not in isi and "Traceback" not in isi
    assert _db().read_bytes() == b"bukan sqlite sama sekali"
    assert _kembalikan(tertutup, admin, revisi=0)[0] in (409, 503) and _db().read_bytes() == b"bukan sqlite sama sekali"


def test_skema_db_asing_post_503_dan_berkas_tak_berubah(tertutup, admin):
    with sqlite3.connect(_db()) as kon:
        kon.execute("PRAGMA user_version = 99")
    kode, _i, _t = _ubah_geometri(tertutup, admin)
    assert kode == 503
    with sqlite3.connect(_db()) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 99


# --- render ---------------------------------------------------------------------------------

def test_simpan_render_halaman_edit_dan_peta_untuk_ditinjau(tertutup, admin):
    assert _ubah_geometri(tertutup, admin)[0] == 303
    DIR_RENDER.mkdir(parents=True, exist_ok=True)
    (DIR_RENDER / "kurikulum-cp-edit.html").write_text(_edit(tertutup, admin, tambah="&hasil=tersimpan")[1], "utf-8")
    (DIR_RENDER / "kurikulum-admin2.html").write_text(minta_admin(tertutup, HALAMAN_PETA, admin)[1], "utf-8")

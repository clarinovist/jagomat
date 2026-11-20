"""Edit label awam topik di `/admin/kurikulum/label` (3d): guard POST admin, konflik revisi, fallback DB rusak.

Data SINTETIS. DB kurikulum diarahkan ke tmp_path; topik target dan revisi hanya dari tinjauan bertanda tangan.
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
import admin_kurikulum_label_pages as ui  # noqa: E402
import admin_security  # noqa: E402
import auth  # noqa: E402
import kurikulum_override as ko  # noqa: E402
import topics  # noqa: E402
import topik_awam  # noqa: E402
from admin_transfer_kit import LINTAS_SITUS, id_admin, login_admin, minta_admin  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import jam, keluarga, minta_mentah, server, tertutup  # noqa: E402,F401

HALAMAN_EDIT = "/admin/kurikulum/label"
HALAMAN_PETA = "/admin/kurikulum/cp-detail"
KEMBALIKAN = HALAMAN_EDIT + "/kembalikan"
TAK_ADA = "/admin/tidak-ada"
TOPIK = "aritmetika-dasar"
TOPIK_LAIN = "statistika"
BAWAAN = "Aritmetika dasar"
BARU = "Hitung dasar"
AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
POLA_HIDDEN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)"')
POLA_FORM = re.compile(r'<form[^>]*action="(/admin/kurikulum/label[^"]*)"[^>]*>(.*?)</form>', re.S)
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


def _item(topik=TOPIK):
    ko.bersihkan_cache()
    return next(i for i in ko.daftar_label() if i.topik_id == topik)


def _audit():
    if not _db().exists():
        return []
    with sqlite3.connect(_db()) as kon:
        kon.row_factory = sqlite3.Row
        return [dict(r) for r in kon.execute("SELECT * FROM audit_kurikulum ORDER BY id")]


def _stempel():
    """(label efektif + revisi semua topik, audit); dibaca segar, tanpa membuat berkas."""
    ko.bersihkan_cache()
    return [(i.efektif, i.revisi) for i in ko.daftar_label()], _audit()


def _token(cookie, topik=TOPIK, revisi=0, aksi=ui.AKSI_UBAH_LABEL, target=None):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": target or topik, "target_revisi": revisi})}


def _kirim(server, cookie, label=BARU, *, topik=TOPIK, revisi=0, ganti=None, hapus=(), ekstra=None,
           headers=None, aksi=ui.AKSI_UBAH_LABEL, jalur=HALAMAN_EDIT, target=None):
    data = {**_token(cookie, topik, revisi, aksi, target), "label": label, **(ekstra or {}), **(ganti or {})}
    for nama in hapus:
        data.pop(nama, None)
    return minta_mentah(server, jalur, None, data, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def _kembalikan(server, cookie, *, topik=TOPIK, revisi=1, ganti=None, ekstra=None, aksi=ui.AKSI_KEMBALIKAN_LABEL):
    data = {**_token(cookie, topik, revisi, aksi), **(ekstra or {}), **(ganti or {})}
    return minta_mentah(server, KEMBALIKAN, None, data, {"Cookie": "osn_sesi=" + cookie})


def _edit(server, cookie, topik=TOPIK, tambah=""):
    return minta_admin(server, "%s?topik=%s%s" % (HALAMAN_EDIT, quote(topik, safe=""), tambah), cookie)


def _badan(isi: str) -> str:
    """Isi halaman tanpa blok CSS bingkai (yang memuat kata seperti name="reauth")."""
    return isi.rsplit("</style>", 1)[-1]


def _form_ubah(isi: str) -> dict:
    """Field form Simpan persis seperti peramban mengirimnya: hidden + nilai input teks."""
    badan = next(b for aksi, b in POLA_FORM.findall(isi) if aksi == HALAMAN_EDIT)
    data = {k: html.unescape(v) for k, v in POLA_HIDDEN.findall(badan)}
    data["label"] = html.unescape(re.search(r'<input type="text" name="label" value="([^"]*)"', badan).group(1))
    return data


# --- akses ----------------------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_menyentuh_db(tertutup, admin, akun, monkeypatch):
    def gagal(*_a, **_k):
        raise AssertionError("DB kurikulum tidak boleh disentuh")

    acuan_get = minta_mentah(tertutup, TAK_ADA, akun)
    acuan_post = minta_mentah(tertutup, TAK_ADA, akun, {"x": "1"})
    with monkeypatch.context() as ctx:
        for nama in ("daftar_label", "riwayat_label", "ubah_label", "kembalikan_label"):
            ctx.setattr(ko, nama, gagal)
        alamat = "%s?topik=%s" % (HALAMAN_EDIT, TOPIK)
        assert minta_mentah(tertutup, alamat, akun)[:2] == acuan_get[:2]
        for jalur in (HALAMAN_EDIT, KEMBALIKAN):
            assert minta_mentah(tertutup, jalur, akun, {})[:2] == acuan_post[:2]
            assert minta_mentah(tertutup, jalur, akun, _token(admin))[:2] == acuan_post[:2]
    assert acuan_get[0] == acuan_post[0] == 404
    assert not _db().exists()


@pytest.mark.parametrize("query", [
    "", "?topik=", "?topik=kombinatorik", "?topik=asing", "?topik=aritmetika-dasar%2F", "?topik=ARITMETIKA-DASAR",
    "?topik=aritmetika-dasar&x=1", "?x=1", "?topik=aritmetika-dasar&topik=aritmetika-dasar",
    "?topik=aritmetika-dasar&hasil=sembarang", "?topik=aritmetika-dasar&hasil=tersimpan&hasil=tersimpan",
])
def test_query_tak_sah_404_identik(tertutup, admin, query):
    acuan = minta_admin(tertutup, TAK_ADA, admin)
    kode, isi, _t = minta_admin(tertutup, HALAMAN_EDIT + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


# --- tampilan -------------------------------------------------------------------------------

def test_halaman_edit_memuat_bawaan_efektif_catatan_dan_form_sandi(tertutup, admin, tmp_path):
    kode, isi, tajuk = _edit(tertutup, admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store" and "<script" not in _badan(isi)
    assert "<h2>%s <code>%s</code></h2>" % (topics.ambil(TOPIK).nama, TOPIK) in isi
    assert "<dt>Bawaan kode</dt><dd>%s</dd>" % BAWAAN in isi and "<dt>Efektif sekarang</dt><dd>%s</dd>" % BAWAAN in isi
    assert "Label baru berlaku untuk hasil cek yang dinilai setelah ini; hasil lama tetap memakai label lama." in isi
    assert 'aria-current="page"' in isi and "Detail CP" in isi
    form = _form_ubah(isi)
    assert set(form) == {"csrf", "tinjauan", "label"} and form["label"] == BAWAAN
    assert 'maxlength="40"' in isi and 'name="reauth"' in _badan(isi)
    assert 'action="%s"' % KEMBALIKAN not in isi and "bawaan kode" in isi  # sumber bawaan: tanpa kembalikan
    assert SANDI_ADMIN not in isi and str(tmp_path) not in isi and "kurikulum.db" not in isi
    assert not _db().exists()


def test_halaman_basic_auth_baca_saja_tanpa_form_dan_post_403(tertutup):
    kode, isi, _t = minta_mentah(tertutup, "%s?topik=%s" % (HALAMAN_EDIT, TOPIK), AKUN_ADMIN)
    assert kode == 200 and not POLA_FORM.findall(_badan(isi)) and "baca-saja" in isi.lower()
    assert 'name="tinjauan"' not in _badan(isi)
    assert minta_mentah(tertutup, HALAMAN_EDIT, AKUN_ADMIN, _token("sesi-sintetis") | {"label": BARU})[0] == 403
    assert not _db().exists()


def test_banner_hasil_hanya_dari_kode_dikenal(tertutup, admin):
    assert 'role="status"' in _edit(tertutup, admin, tambah="&hasil=tersimpan")[1]
    assert 'role="status"' in _edit(tertutup, admin, tambah="&hasil=dikembalikan")[1]
    assert 'role="status"' not in _badan(_edit(tertutup, admin)[1])


def test_detail_cp_menautkan_ubah_label_hanya_untuk_topik_berlabel(tertutup, admin):
    isi = minta_admin(tertutup, HALAMAN_PETA, admin)[1]
    assert 'href="%s?topik=%s"' % (HALAMAN_EDIT, TOPIK) in isi
    assert isi.count(">Ubah label</a>") == len(topik_awam.NAMA_AWAM)
    assert 'aria-current="page">Detail CP' in isi


# --- ubah -----------------------------------------------------------------------------------

def test_ubah_sah_menyimpan_audit_satu_redirect_banner_dan_label_langsung_berlaku(tertutup, admin):
    kode, isi, tajuk = _kirim(tertutup, admin)
    assert (kode, isi) == (303, "")
    assert tajuk["Location"] == "%s?topik=%s&hasil=tersimpan" % (HALAMAN_EDIT, TOPIK)
    item = _item()
    assert (item.efektif, item.sumber, item.revisi, item.bawaan) == (BARU, "admin", 1, BAWAAN)
    audit = _audit()
    assert len(audit) == 1 and audit[0]["kunci"] == TOPIK and audit[0]["jenis"] == "label"
    assert audit[0]["actor_id"] == id_admin()
    assert topik_awam.nama(TOPIK) == BARU  # pembaca saat request, tanpa restart
    kode, halaman, _t = minta_admin(tertutup, tajuk["Location"], admin)
    assert kode == 200 and "langsung berlaku untuk hasil cek berikutnya" in halaman
    assert "diubah admin, revisi 1" in halaman and "Kembalikan ke bawaan" in halaman
    assert id_admin() in halaman and "%s → %s" % (BAWAAN, BARU) in halaman  # riwayat
    peta = minta_admin(tertutup, HALAMAN_PETA, admin)[1]
    assert "Label awam: %s" % BARU in peta


def test_form_dari_halaman_dapat_dikirim_apa_adanya(tertutup, admin):
    form = _form_ubah(_edit(tertutup, admin)[1])
    form["label"] = "  Hitung dasar  "
    kode, _i, tajuk = minta_admin(tertutup, HALAMAN_EDIT, admin, {**form, "reauth": SANDI_ADMIN})
    assert kode == 303 and tajuk["Location"].endswith("hasil=tersimpan")
    assert _item().efektif == BARU  # dipangkas


def test_label_dengan_markup_disimpan_utuh_dan_di_escape_saat_tampil(tertutup, admin):
    assert _kirim(tertutup, admin, "<i>&\"'")[0] == 303
    isi = _edit(tertutup, admin)[1]
    assert "<i>" not in _badan(isi) and "&lt;i&gt;" in isi
    assert _form_ubah(isi)["label"] == "<i>&\"'"


def test_label_sama_dengan_bawaan_tidak_membuat_revisi_atau_audit(tertutup, admin):
    assert _kirim(tertutup, admin, BAWAAN)[0] == 303
    assert _item().revisi == 0 and _audit() == []


def test_label_bawaan_topik_lain_beda_huruf_boleh_untuk_topik_sendiri(tertutup, admin):
    assert _kirim(tertutup, admin, "ARITMETIKA DASAR")[0] == 303
    assert _item().efektif == "ARITMETIKA DASAR"


# --- guard ----------------------------------------------------------------------------------

@pytest.mark.parametrize("kasus", ["tanpa_csrf", "csrf_salah", "tinjauan_palsu", "tanpa_tinjauan",
                                   "reauth_salah", "tanpa_reauth"])
def test_token_cacat_403_tanpa_mengubah_store(tertutup, admin, kasus):
    ganti, hapus = {
        "tanpa_csrf": ({}, ("csrf",)), "csrf_salah": ({"csrf": "rusak"}, ()),
        "tinjauan_palsu": ({"tinjauan": "palsu.palsu"}, ()), "tanpa_tinjauan": ({}, ("tinjauan",)),
        "reauth_salah": ({"reauth": "salah-sandi"}, ()), "tanpa_reauth": ({}, ("reauth",)),
    }[kasus]
    assert _kirim(tertutup, admin, ganti=ganti, hapus=hapus)[0] == 403
    assert not _db().exists()


def test_tinjauan_aksi_lain_sesi_lain_atau_basic_auth_ditolak(tertutup, admin):
    assert _kirim(tertutup, admin, aksi=ui.AKSI_KEMBALIKAN_LABEL)[0] == 403
    assert _kirim(tertutup, admin, aksi="ubah_cp_kurikulum")[0] == 403
    assert _kirim(tertutup, admin, aksi="ubah_sakelar")[0] == 403
    assert _kembalikan(tertutup, admin, aksi=ui.AKSI_UBAH_LABEL)[0] == 403
    assert _kembalikan(tertutup, admin, aksi="kembalikan_cp_kurikulum")[0] == 403
    asing = {**_token("sesi-lain-sintetis"), "label": BARU}
    assert minta_admin(tertutup, HALAMAN_EDIT, admin, asing)[0] == 403
    assert not _db().exists()


def test_permintaan_lintas_situs_403_tanpa_efek(tertutup, admin):
    assert _kirim(tertutup, admin, headers=LINTAS_SITUS)[0] == 403
    assert not _db().exists()


@pytest.mark.parametrize("ekstra", [{"target_id": TOPIK_LAIN}, {"topik": TOPIK_LAIN}, {"topik_id": TOPIK_LAIN},
                                    {"revisi": "9"}, {"aksi": "x", "nama": "y"}])
def test_target_dan_revisi_tak_bisa_diganti_lewat_field_form(tertutup, admin, ekstra):
    assert _kirim(tertutup, admin, ekstra=ekstra)[0] == 400
    assert not _db().exists()


def test_field_label_hilang_atau_diganti_nama_lain_ditolak(tertutup, admin):
    assert _kirim(tertutup, admin, hapus=("label",))[0] == 400
    assert _kirim(tertutup, admin, hapus=("label",), ekstra={"nama": BARU})[0] == 400
    assert not _db().exists()


def test_tinjauan_topik_x_dengan_field_topik_y_tidak_mengubah_keduanya(tertutup, admin):
    assert _kirim(tertutup, admin, ekstra={"topik_id": TOPIK_LAIN})[0] == 400
    assert _item(TOPIK).revisi == 0 and _item(TOPIK_LAIN).revisi == 0 and _audit() == []


def test_target_hanya_dari_tinjauan_bukan_dari_field(tertutup, admin):
    assert _kirim(tertutup, admin)[0] == 303
    assert _item(TOPIK).revisi == 1 and _item(TOPIK_LAIN).revisi == 0
    assert _item(TOPIK_LAIN).efektif == topik_awam.NAMA_AWAM[TOPIK_LAIN]


@pytest.mark.parametrize("target,revisi", [("asing", 0), ("kombinatorik", 0), (" ", 0), (TOPIK + "/x", 0),
                                           (TOPIK, -1)])
def test_isi_tinjauan_tak_sah_400_bukan_500(tertutup, admin, target, revisi):
    assert _kirim(tertutup, admin, revisi=revisi, target=target)[0] == 400
    assert not _db().exists()


# --- konflik --------------------------------------------------------------------------------

def test_dua_tinjauan_revisi_sama_yang_kedua_409_dan_store_memuat_hasil_pertama(tertutup, admin):
    pertama, kedua = _token(admin, TOPIK, 0), _token(admin, TOPIK, 0)
    kirim = lambda token, label: minta_mentah(  # noqa: E731
        tertutup, HALAMAN_EDIT, None, {**token, "label": label}, {"Cookie": "osn_sesi=" + admin})
    assert kirim(pertama, BARU)[0] == 303
    sebelum = _stempel()
    kode, isi, _t = kirim(kedua, "Label lain")
    assert kode == 409 and "Buka ulang" in isi and "Traceback" not in isi
    assert _stempel() == sebelum and _item().efektif == BARU


def test_kirim_ulang_form_sama_setelah_sukses_409_tanpa_ubah_ulang(tertutup, admin):
    form = _form_ubah(_edit(tertutup, admin)[1])
    form["label"] = BARU
    assert minta_admin(tertutup, HALAMAN_EDIT, admin, {**form, "reauth": SANDI_ADMIN})[0] == 303
    sebelum = _stempel()
    assert minta_admin(tertutup, HALAMAN_EDIT, admin, {**form, "reauth": SANDI_ADMIN})[0] == 409
    assert _stempel() == sebelum


# --- isian tak sah --------------------------------------------------------------------------

@pytest.mark.parametrize("label", [
    "", "   ", "x" * 41, "Hitung\x00dasar", "Hitung\ndasar",
    "statistika", "  STATISTIKA ",           # duplikat label efektif topik lain (casefold)
    "Aritmetika Dasar",                       # nama resmi topik ini yang dipetakan dari_nama_lama
    "Pola Bilangan",                          # nama resmi topik lain yang dipetakan dari_nama_lama
], ids=["kosong", "spasi", "41_karakter", "nul", "newline", "duplikat", "duplikat_casefold_spasi",
        "nama_resmi_sendiri", "nama_resmi_lain"])
def test_label_tak_sah_400_dengan_copy_jelas_dan_store_tidak_berubah(tertutup, admin, label):
    kode, teks, _t = _kirim(tertutup, admin, label)
    assert kode == 400 and "Label tidak sah" in teks and "1-40 karakter" in teks and "Traceback" not in teks
    assert not _db().exists()


def test_label_empat_puluh_karakter_sah(tertutup, admin):
    assert _kirim(tertutup, admin, "x" * 40)[0] == 303
    assert _item().efektif == "x" * 40


def test_duplikat_terhadap_override_topik_lain_ditolak_tanpa_efek(tertutup, admin):
    assert _kirim(tertutup, admin, BARU)[0] == 303
    sebelum = _stempel()
    assert _kirim(tertutup, admin, "hitung DASAR", topik=TOPIK_LAIN)[0] == 400
    assert _stempel() == sebelum


def test_label_bawaan_topik_yang_sudah_dilepas_boleh_dipakai_topik_lain(tertutup, admin):
    assert _kirim(tertutup, admin, BARU)[0] == 303  # "Aritmetika dasar" kini bebas
    assert _kirim(tertutup, admin, BAWAAN, topik=TOPIK_LAIN)[0] == 303
    assert topik_awam.nama(TOPIK_LAIN) == BAWAAN


# --- kembalikan -----------------------------------------------------------------------------

def test_kembalikan_ke_bawaan_revisi_naik_dan_audit_tercatat(tertutup, admin):
    assert _kirim(tertutup, admin)[0] == 303
    kode, isi, tajuk = _kembalikan(tertutup, admin, revisi=1)
    assert (kode, isi) == (303, "") and tajuk["Location"].endswith("hasil=dikembalikan")
    item = _item()
    assert (item.efektif, item.sumber, item.revisi) == (BAWAAN, "bawaan", 2)
    assert len(_audit()) == 2 and _audit()[1]["revisi"] == 2
    assert topik_awam.nama(TOPIK) == BAWAAN
    halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert "dikembalikan ke bawaan kode" in halaman and 'action="%s"' % KEMBALIKAN not in halaman
    assert halaman.count("Revisi 2") == 1 and halaman.count("Revisi 1") == 1  # riwayat terbaru dulu


def test_kembalikan_dengan_field_asing_atau_revisi_basi_ditolak(tertutup, admin):
    assert _kirim(tertutup, admin)[0] == 303
    sebelum = _stempel()
    assert _kembalikan(tertutup, admin, revisi=1, ekstra={"target_id": TOPIK_LAIN})[0] == 400
    assert _kembalikan(tertutup, admin, revisi=1, ekstra={"label": BARU})[0] == 400
    assert _kembalikan(tertutup, admin, revisi=0)[0] == 409
    assert _kembalikan(tertutup, admin, revisi=1, ganti={"reauth": "salah"})[0] == 403
    assert _stempel() == sebelum


def test_kembalikan_ditolak_bila_label_bawaan_dipakai_topik_lain(tertutup, admin):
    assert _kirim(tertutup, admin, BARU)[0] == 303
    assert _kirim(tertutup, admin, BAWAAN, topik=TOPIK_LAIN)[0] == 303
    sebelum = _stempel()
    kode, teks, _t = _kembalikan(tertutup, admin, revisi=1)
    assert kode == 400 and "Label tidak sah" in teks
    assert _stempel() == sebelum


def test_kembalikan_form_ada_hanya_bila_sumber_admin(tertutup, admin):
    assert 'action="%s"' % KEMBALIKAN not in _edit(tertutup, admin)[1]
    assert _kirim(tertutup, admin)[0] == 303
    isi = _edit(tertutup, admin)[1]
    form = next(b for aksi, b in POLA_FORM.findall(isi) if aksi == KEMBALIKAN)
    assert 'name="reauth"' in form and 'name="label"' not in form
    data = {k: html.unescape(v) for k, v in POLA_HIDDEN.findall(form)}
    assert minta_admin(tertutup, KEMBALIKAN, admin, {**data, "reauth": SANDI_ADMIN})[0] == 303
    assert _item().efektif == BAWAAN


# --- DB rusak -------------------------------------------------------------------------------

def test_db_rusak_get_tetap_200_dengan_bawaan_dan_post_503_tanpa_path(tertutup, admin, tmp_path):
    _db().write_bytes(b"bukan sqlite sama sekali")
    ko.bersihkan_cache()
    assert minta_admin(tertutup, HALAMAN_PETA, admin)[0] == 200
    kode, isi, _t = _edit(tertutup, admin)
    assert kode == 200 and "bawaan kode" in isi and _form_ubah(isi)["label"] == BAWAAN
    kode, isi, _t = _kirim(tertutup, admin)
    assert kode == 503 and str(tmp_path) not in isi and "kurikulum.db" not in isi and "Traceback" not in isi
    assert _db().read_bytes() == b"bukan sqlite sama sekali"
    assert _kembalikan(tertutup, admin, revisi=0)[0] in (400, 409, 503)
    assert _db().read_bytes() == b"bukan sqlite sama sekali"


def test_skema_db_asing_post_503_dan_berkas_tak_berubah(tertutup, admin):
    with sqlite3.connect(_db()) as kon:
        kon.execute("PRAGMA user_version = 99")
    assert _kirim(tertutup, admin)[0] == 503
    with sqlite3.connect(_db()) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 99


# --- render ---------------------------------------------------------------------------------

def test_simpan_render_halaman_edit_untuk_ditinjau(tertutup, admin):
    assert _kirim(tertutup, admin)[0] == 303
    DIR_RENDER.mkdir(parents=True, exist_ok=True)
    (DIR_RENDER / "kurikulum-label-edit.html").write_text(
        _edit(tertutup, admin, tambah="&hasil=tersimpan")[1], "utf-8")
    (DIR_RENDER / "kurikulum-label-detail-cp.html").write_text(
        minta_admin(tertutup, HALAMAN_PETA, admin)[1], "utf-8")

"""Cetakan soal berpola di `/admin/kurikulum/cetakan*` (C2, manual): akses, alur, guard POST, 400/409/503.

Data SINTETIS. DB cetakan diarahkan ke tmp_path; target (kelas/bab atau id/revisi) hanya dari tinjauan bertanda tangan.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_kurikulum_cetakan_http as http_cetakan  # noqa: E402
import admin_kurikulum_cetakan_pages as ui  # noqa: E402
import cetakan_pola as pola  # noqa: E402
import cetakan_store as store  # noqa: E402
from admin_transfer_kit import LINTAS_SITUS, id_admin, login_admin, minta_admin  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from cetakan_admin_kit import (  # noqa: E402
    AKSI_RUTE, BAB_ADA, BAB_BELUM, JUDUL, TAK_ADA, aktifkan_langsung, buat_langsung, daftar_halaman, formulir, isi_sah,
    isi_tak_layak, kirim, kirim_buat, kirim_pindah, kirim_ubah, segar, semua_action, stempel, token,
)
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from pesanan_transfer_http_kit import jam, keluarga, minta_mentah, server, tertutup  # noqa: E402,F401

AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
SEMUA_POST = (ui.RUTE_BARU, ui.RUTE_UBAH, ui.RUTE_SETUJUI, ui.RUTE_NONAKTIFKAN, ui.RUTE_AKTIFKAN)
POLA_ID_REDIRECT = re.compile(r"[?&]id=(\d+)&hasil=(\w+)$")


@pytest.fixture(autouse=True)
def _db_cetakan_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv(store.ENV_BERKAS_DB, str(tmp_path / "cetakan.db"))
    store.bersihkan_cache()
    yield
    store.bersihkan_cache()


@pytest.fixture()
def admin(tertutup):
    return login_admin(tertutup)


def _db() -> Path:
    return store._path_db(None)


def _alamat_periksa(id_cetakan: int, tambah: str = "") -> str:
    return "%s?id=%d%s" % (ui.RUTE_PERIKSA, id_cetakan, tambah)


def _alamat_daftar(bab=BAB_ADA) -> str:
    return "%s?kelas=%d&bab=%d" % (ui.RUTE, *bab)


def _badan(isi: str) -> str:
    """Isi halaman tanpa blok CSS bingkai (yang memuat kata seperti name="reauth")."""
    return isi.rsplit("</style>", 1)[-1]


def _id_dari(tajuk) -> int:
    return int(POLA_ID_REDIRECT.search(tajuk["Location"]).group(1))


def _siapkan(server, admin, aksi) -> dict:
    """Keadaan awal + argumen kirim untuk satu aksi: draf (ubah/setujui), aktif (nonaktifkan), nonaktif (aktifkan)."""
    if aksi == ui.AKSI_BUAT:
        return {"target": "%d/%d" % BAB_ADA, "revisi": 0, "isi": isi_sah()}
    item = buat_langsung()
    if aksi in (ui.AKSI_NONAKTIFKAN, ui.AKSI_AKTIFKAN):
        item = aktifkan_langsung(item)
    if aksi == ui.AKSI_AKTIFKAN:
        item = store.nonaktifkan(item.id, actor_id="admin-sintetis", revisi_diharapkan=item.revisi)
    return {"target": item.id, "revisi": item.revisi, "isi": isi_sah() if aksi == ui.AKSI_UBAH else {}}


def _kirim_siap(server, admin, aksi, **kw):
    keadaan = _siapkan(server, admin, aksi)
    return keadaan, kirim(server, admin, aksi, keadaan["target"], keadaan["revisi"], keadaan["isi"], **kw)


# --- akses ----------------------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_menyentuh_store(tertutup, admin, akun, monkeypatch):
    item = buat_langsung()

    def gagal(*_a, **_k):
        raise AssertionError("store cetakan tidak boleh disentuh")

    acuan_get = minta_mentah(tertutup, TAK_ADA, akun)
    acuan_post = minta_mentah(tertutup, TAK_ADA, akun, {"x": "1"})
    sebelum = stempel(_db())
    with monkeypatch.context() as ctx:
        for nama in ("daftar", "ambil", "riwayat", "buat_draf", "ubah_draf", "setujui", "nonaktifkan",
                     "aktifkan_kembali"):
            ctx.setattr(store, nama, gagal)
        for alamat in (_alamat_daftar(), "%s?kelas=3&bab=1" % ui.RUTE_BARU, _alamat_periksa(item.id)):
            assert minta_mentah(tertutup, alamat, akun)[:2] == acuan_get[:2]
        for jalur in SEMUA_POST:
            assert minta_mentah(tertutup, jalur, akun, {})[:2] == acuan_post[:2]
            assert minta_mentah(tertutup, jalur, akun, token(admin, "buat_cetakan_soal", "3/1", 0))[:2] == acuan_post[:2]
    assert acuan_get[0] == acuan_post[0] == 404
    assert stempel(_db()) == sebelum


@pytest.mark.parametrize("query", [
    "", "?kelas=3", "?bab=1", "?kelas=3&bab=99", "?kelas=9&bab=1", "?kelas=03&bab=1", "?kelas=-3&bab=1",
    "?kelas=3&bab=1&x=1", "?kelas=3&kelas=3&bab=1", "?kelas=abc&bab=1", "?kelas=3&bab=%EF%BC%91",
])
@pytest.mark.parametrize("jalur", [ui.RUTE, ui.RUTE_BARU])
def test_query_bab_tak_sah_404_identik(tertutup, admin, jalur, query):
    acuan = minta_admin(tertutup, TAK_ADA, admin)
    kode, isi, _t = minta_admin(tertutup, jalur + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


@pytest.mark.parametrize("query", [
    "", "?id=", "?id=0", "?id=01", "?id=abc", "?id=999", "?id=1&hasil=sembarang", "?id=1&x=1", "?id=1&id=1",
    "?id=-1", "?id=1&hasil=tersimpan&hasil=tersimpan",
])
def test_query_periksa_tak_sah_404_identik(tertutup, admin, query):
    buat_langsung()
    acuan = minta_admin(tertutup, TAK_ADA, admin)
    kode, isi, _t = minta_admin(tertutup, ui.RUTE_PERIKSA + query, admin)
    assert (kode, isi) == acuan[:2] and kode == 404


# --- tampilan -------------------------------------------------------------------------------

def test_daftar_bab_memuat_judul_sub_materi_status_dan_tautan(tertutup, admin):
    kode, kosong, tajuk = minta_admin(tertutup, _alamat_daftar(), admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store" and "<script" not in _badan(kosong)
    assert "Kelas 3 · Bab 1" in kosong and "Belum ada cetakan untuk bab ini." in kosong
    assert 'href="%s?kelas=3&amp;bab=1"' % ui.RUTE_BARU in kosong and 'href="/admin/kurikulum"' in kosong
    draf = buat_langsung()
    nonaktif = store.nonaktifkan(
        aktifkan_langsung(buat_langsung(judul="Cetakan kedua")).id, actor_id="a", revisi_diharapkan=2)
    isi = minta_admin(tertutup, _alamat_daftar(), admin)[1]
    assert JUDUL in isi and "Cetakan kedua" in isi
    assert "Draf · Ditulis manual · revisi 1" in isi and "Nonaktif · Ditulis manual" in isi
    assert 'href="%s"' % _alamat_periksa(draf.id).replace("&", "&amp;") in isi and nonaktif.status == "nonaktif"
    assert "Belum ada cetakan" not in isi and not minta_admin(tertutup, _alamat_daftar(BAB_BELUM), admin)[1].count(JUDUL)


def test_form_baru_kosong_dengan_placeholder_dan_tanpa_kelas_bab_di_form(tertutup, admin):
    kode, isi, _t = minta_admin(tertutup, "%s?kelas=3&bab=1" % ui.RUTE_BARU, admin)
    assert kode == 200
    field = formulir(isi, ui.RUTE_BARU)
    assert set(field) - {"csrf", "tinjauan", "reauth"} == set(ui.FIELD_BUAT) and len(field) == 25
    assert field["judul"] == "" and field["kunci"] == "" and field["nama"] == "tidak" and field["reauth"] == ""
    assert 'placeholder="a + b"' in isi and "kelereng" in isi  # contoh hanya di placeholder
    assert "kelas" not in field and "bab" not in field and not _db().exists()


def test_periksa_draf_memuat_sepuluh_contoh_kunci_hitungan_mesin_dan_form_aksi(tertutup, admin):
    item = buat_langsung()
    kode, isi, tajuk = minta_admin(tertutup, _alamat_periksa(item.id), admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    contoh = re.findall(r'<li><div class="kur-soal"><p>(.*?)</p></div><p class="kur-kunci"><strong>Kunci jawaban:'
                        r'</strong> (\d+)</p>', isi)
    assert len(contoh) == pola.BANYAK_CONTOH == 10
    for teks, kunci in contoh:
        a, b = map(int, re.search(r"punya (\d+) kelereng\. Ia diberi (\d+) kelereng", teks).groups())
        assert int(kunci) == a + b and 10 <= a <= 50 and 1 <= b <= 40 and a + b <= 99
    assert "Pembahasan: " in isi and "Lolos uji kelayakan" in isi and "Draf · Ditulis manual" in isi
    assert semua_action(isi) == [ui.RUTE_UBAH, ui.RUTE_SETUJUI]
    field = formulir(isi, ui.RUTE_UBAH)
    assert field["judul"] == JUDUL and field["kunci"] == "a + b" and field["nama"] == "ya"
    assert (field["var_1_nama"], field["var_1_min"], field["var_1_max"]) == ("a", "10", "50")
    assert field["syarat_1"] == "a + b <= 99" and field["reauth"] == "" and SANDI_ADMIN not in isi


def test_periksa_menampilkan_alasan_bila_tak_layak_dan_riwayat(tertutup, admin):
    assert kirim_buat(tertutup, admin, isi_tak_layak())[0] == 303
    isi = minta_admin(tertutup, _alamat_periksa(1), admin)[1]
    assert "Belum lolos uji kelayakan" in isi and "25 soal unik" in isi
    assert "Revisi 1 · dibuat" in isi and "<code>%s</code>" % id_admin() in isi


def test_kunci_di_contoh_memakai_titik_ribuan_bila_besar(tertutup, admin):
    item = buat_langsung({
        "kelas": 3, "bab": 1, "judul": "Kali besar", "teks": "{a} kali {b} berapa?",
        "variabel": {"a": [100, 900], "b": [100, 900]}, "nama": False, "syarat": [], "kunci": "a * b"})
    isi = minta_admin(tertutup, _alamat_periksa(item.id), admin)[1]
    assert re.search(r"Kunci jawaban:</strong> \d{2,3}\.\d{3}</p>", isi) and ". " not in "".join(
        re.findall(r"Kunci jawaban:</strong> ([\d.]+)", isi))


def test_status_aktif_dan_nonaktif_menampilkan_aksi_yang_sesuai(tertutup, admin):
    item = aktifkan_langsung(buat_langsung())
    assert semua_action(minta_admin(tertutup, _alamat_periksa(item.id), admin)[1]) == [ui.RUTE_NONAKTIFKAN]
    store.nonaktifkan(item.id, actor_id="a", revisi_diharapkan=item.revisi)
    assert semua_action(minta_admin(tertutup, _alamat_periksa(item.id), admin)[1]) == [ui.RUTE_AKTIFKAN]


def test_basic_auth_baca_saja_tanpa_form_dan_post_403(tertutup):
    item = buat_langsung()
    kode, isi, _t = minta_mentah(tertutup, _alamat_periksa(item.id), AKUN_ADMIN)
    assert kode == 200 and not semua_action(isi) and "baca-saja" in isi.lower()
    kode, isi, _t = minta_mentah(tertutup, "%s?kelas=3&bab=1" % ui.RUTE_BARU, AKUN_ADMIN)
    assert kode == 200 and not semua_action(isi)
    sebelum = stempel(_db())
    assert minta_mentah(tertutup, ui.RUTE_UBAH, AKUN_ADMIN, {**token("sesi-sintetis", ui.AKSI_UBAH, item.id, 1),
                                                           **isi_sah()})[0] == 403
    assert stempel(_db()) == sebelum


def test_banner_hasil_hanya_dari_kode_dikenal(tertutup, admin):
    item = buat_langsung()
    for kode_hasil in ui.KODE_HASIL:
        assert 'role="status"' in minta_admin(tertutup, _alamat_periksa(item.id, "&hasil=" + kode_hasil), admin)[1]
    assert 'role="status"' not in _badan(minta_admin(tertutup, _alamat_periksa(item.id), admin)[1])


# --- alur sukses ----------------------------------------------------------------------------

def test_alur_buat_ubah_setujui_nonaktifkan_aktifkan_kembali(tertutup, admin):
    kode, isi, tajuk = kirim_buat(tertutup, admin)
    assert (kode, isi) == (303, "")
    item_id = _id_dari(tajuk)
    assert tajuk["Location"] == "%s?id=%d&hasil=dibuat" % (ui.RUTE_PERIKSA, item_id)
    item = segar(item_id)
    assert (item.status, item.sumber, item.revisi, item.kelas, item.bab) == ("draf", "manual", 1, 3, 1)
    halaman = minta_admin(tertutup, tajuk["Location"], admin)[1]
    assert "Cetakan draf tersimpan" in halaman and _badan(halaman).count("kur-kunci") == 10

    ubah = kirim_ubah(tertutup, admin, item_id, 1, isi_sah(kunci="a + b + 1", syarat_1="a + b <= 98"))
    assert ubah[0] == 303 and ubah[2]["Location"].endswith("hasil=tersimpan")
    item = segar(item_id)
    assert item.revisi == 2 and item.cetakan.kunci == "a + b + 1" and item.cetakan.syarat == ("a + b <= 98",)
    halaman = minta_admin(tertutup, ubah[2]["Location"], admin)[1]
    for teks, kunci in re.findall(r'<p>(.*?)</p></div><p class="kur-kunci"><strong>Kunci jawaban:</strong> (\d+)',
                                  halaman):
        a, b = map(int, re.search(r"punya (\d+) kelereng\. Ia diberi (\d+) kelereng", teks).groups())
        assert int(kunci) == a + b + 1  # contoh dihitung ulang dari isi terbaru

    setuju = kirim_pindah(tertutup, admin, ui.AKSI_SETUJUI, item_id, 2)
    assert setuju[0] == 303 and setuju[2]["Location"].endswith("hasil=disetujui")
    assert (segar(item_id).status, segar(item_id).revisi) == ("aktif", 3)
    assert store.aktif_untuk_bab(*BAB_ADA)[0].id == item_id

    mati = kirim_pindah(tertutup, admin, ui.AKSI_NONAKTIFKAN, item_id, 3)
    assert mati[0] == 303 and mati[2]["Location"].endswith("hasil=dinonaktifkan")
    assert segar(item_id).status == "nonaktif" and store.aktif_untuk_bab(*BAB_ADA) == ()

    hidup = kirim_pindah(tertutup, admin, ui.AKSI_AKTIFKAN, item_id, 4)
    assert hidup[0] == 303 and hidup[2]["Location"].endswith("hasil=diaktifkan")
    assert (segar(item_id).status, segar(item_id).revisi) == ("aktif", 5)
    _baris, audit = stempel(_db())
    assert [a[2] for a in audit] == ["buat", "ubah", "setujui", "nonaktifkan", "aktifkan"]
    assert {a[6] for a in audit} == {id_admin()}  # actor dari principal


def test_form_dari_halaman_dapat_dikirim_apa_adanya_dua_puluh_lima_field(tertutup, admin):
    field = formulir(minta_admin(tertutup, "%s?kelas=3&bab=1" % ui.RUTE_BARU, admin)[1], ui.RUTE_BARU)
    field.update(isi_sah())
    field["reauth"] = SANDI_ADMIN
    assert len(field) + 0 == http_cetakan.MAKS_FIELD_CETAKAN
    kode, _i, tajuk = minta_admin(tertutup, ui.RUTE_BARU, admin, field)
    assert kode == 303 and tajuk["Location"].endswith("hasil=dibuat")
    ubah = formulir(minta_admin(tertutup, tajuk["Location"], admin)[1], ui.RUTE_UBAH)
    ubah.update(judul="Judul dari form halaman", reauth=SANDI_ADMIN)
    assert len(ubah) == http_cetakan.MAKS_FIELD_CETAKAN
    assert minta_admin(tertutup, ui.RUTE_UBAH, admin, ubah)[0] == 303
    assert segar(1).cetakan.judul == "Judul dari form halaman" and segar(1).revisi == 2


def test_textarea_dengan_pindah_baris_dilipat_jadi_spasi(tertutup, admin):
    isi = isi_sah(teks="{nama} punya {a} kelereng.\r\nIa diberi {b} kelereng lagi.\nBerapa sekarang?")
    assert kirim_buat(tertutup, admin, isi)[0] == 303
    assert segar(1).cetakan.teks == "{nama} punya {a} kelereng. Ia diberi {b} kelereng lagi. Berapa sekarang?"


def test_target_buat_hanya_dari_tinjauan(tertutup, admin):
    assert kirim_buat(tertutup, admin, bab=BAB_BELUM)[0] == 303
    item = segar(1)
    assert (item.kelas, item.bab) == BAB_BELUM


# --- guard ----------------------------------------------------------------------------------

AKSI_SEMUA = [ui.AKSI_BUAT, ui.AKSI_UBAH, ui.AKSI_SETUJUI, ui.AKSI_NONAKTIFKAN, ui.AKSI_AKTIFKAN]


@pytest.mark.parametrize("aksi", AKSI_SEMUA)
@pytest.mark.parametrize("kasus", ["tanpa_csrf", "csrf_salah", "tinjauan_palsu", "tanpa_tinjauan",
                                   "reauth_salah", "tanpa_reauth", "reauth_kosong"])
def test_token_cacat_403_tanpa_mengubah_store(tertutup, admin, aksi, kasus):
    ganti, hapus = {
        "tanpa_csrf": ({}, ("csrf",)), "csrf_salah": ({"csrf": "rusak"}, ()),
        "tinjauan_palsu": ({"tinjauan": "palsu.palsu"}, ()), "tanpa_tinjauan": ({}, ("tinjauan",)),
        "reauth_salah": ({"reauth": "salah-sandi"}, ()), "tanpa_reauth": ({}, ("reauth",)),
        "reauth_kosong": ({"reauth": ""}, ()),
    }[kasus]
    keadaan = _siapkan(tertutup, admin, aksi)
    sebelum = stempel(_db())
    assert kirim(tertutup, admin, aksi, keadaan["target"], keadaan["revisi"], keadaan["isi"],
                 ganti=ganti, hapus=hapus)[0] == 403
    assert stempel(_db()) == sebelum


@pytest.mark.parametrize("aksi", AKSI_SEMUA)
def test_tinjauan_aksi_lain_sesi_lain_dan_lintas_situs_ditolak(tertutup, admin, aksi):
    keadaan = _siapkan(tertutup, admin, aksi)
    sebelum = stempel(_db())
    lain = next(a for a in AKSI_SEMUA if a != aksi)
    for percobaan in (
        dict(token_aksi=lain), dict(token_aksi="ubah_sakelar"), dict(headers=LINTAS_SITUS),
    ):
        assert kirim(tertutup, admin, aksi, keadaan["target"], keadaan["revisi"], keadaan["isi"],
                     **percobaan)[0] == 403
    asing = {**token("sesi-lain-sintetis", aksi, keadaan["target"], keadaan["revisi"]), **keadaan["isi"]}
    assert minta_admin(tertutup, AKSI_RUTE[aksi], admin, asing)[0] == 403
    assert stempel(_db()) == sebelum


@pytest.mark.parametrize("aksi", AKSI_SEMUA)
@pytest.mark.parametrize("ekstra", [{"id": "2"}, {"kelas": "4", "bab": "2"}, {"target_id": "2"},
                                    {"revisi": "9"}, {"aksi2": "x"}, {"cetakan_id": "1"}])
def test_field_asing_ditolak_400_dan_id_kelas_bab_di_form_diabaikan(tertutup, admin, aksi, ekstra):
    keadaan = _siapkan(tertutup, admin, aksi)
    lain = buat_langsung(judul="Cetakan lain yang tak boleh berubah", bab=BAB_BELUM)
    sebelum = stempel(_db())
    assert kirim(tertutup, admin, aksi, keadaan["target"], keadaan["revisi"], keadaan["isi"], ekstra=ekstra)[0] == 400
    assert stempel(_db()) == sebelum and segar(lain.id).revisi == 1


@pytest.mark.parametrize("aksi", [ui.AKSI_BUAT, ui.AKSI_UBAH])
@pytest.mark.parametrize("hapus", ["judul", "var_4_max", "syarat_5", "nama", "pembahasan"])
def test_field_kurang_ditolak_400(tertutup, admin, aksi, hapus):
    keadaan = _siapkan(tertutup, admin, aksi)
    sebelum = stempel(_db())
    assert kirim(tertutup, admin, aksi, keadaan["target"], keadaan["revisi"], keadaan["isi"], hapus=(hapus,))[0] == 400
    assert stempel(_db()) == sebelum


def test_field_asing_pengganti_satu_field_ditolak_walau_jumlah_field_sah(tertutup, admin):
    """25 field persis (jumlah sah) tetapi himpunan namanya salah: hanya `wajib_field` yang menolak."""
    isi = isi_sah()
    del isi["syarat_5"]
    isi["kelas"] = "4"
    kode = kirim_buat(tertutup, admin, isi)[0]
    assert kode == 400 and stempel(_db()) == ((), ()) and not _db().exists()


def test_batas_field_cetakan_eksplisit_26_field_ditolak_sebelum_token_diperiksa(tertutup, admin):
    """Di bawah batas token buruk = 403; melampaui batas = 400 (format) sebelum token disentuh."""
    rusak = {"csrf": "rusak"}
    assert kirim_buat(tertutup, admin, ganti=rusak)[0] == 403
    assert kirim_buat(tertutup, admin, ganti=rusak, ekstra={"tambahan": "x"})[0] == 400
    assert not _db().exists()


def test_konstanta_batas_field_cetakan_dua_puluh_dua_isian_ditambah_tiga_token():
    assert http_cetakan.MAKS_FIELD_CETAKAN == 25


def test_batas_field_global_tidak_naik_untuk_aksi_lain():
    import admin_pesanan_aksi as aksi
    assert aksi.MAKS_FIELD == 8


def test_tinjauan_item_a_hanya_mengubah_a_bukan_b(tertutup, admin):
    a, b = buat_langsung(), buat_langsung(judul="Cetakan B")
    assert kirim_ubah(tertutup, admin, a.id, a.revisi, isi_sah(judul="A diubah"))[0] == 303
    assert segar(a.id).cetakan.judul == "A diubah" and segar(b.id).cetakan.judul == "Cetakan B"
    assert segar(b.id).revisi == 1


@pytest.mark.parametrize("target,revisi", [("asing", 0), (0, 1), (-1, 1), ("1", 1), (1, 0), (1, -1)])
def test_isi_tinjauan_tak_sah_ditolak_bukan_500(tertutup, admin, target, revisi):
    buat_langsung()
    for aksi in (ui.AKSI_UBAH, ui.AKSI_SETUJUI, ui.AKSI_NONAKTIFKAN, ui.AKSI_AKTIFKAN):
        isi = isi_sah() if aksi == ui.AKSI_UBAH else {}
        kode = kirim(tertutup, admin, aksi, target, revisi, isi)[0]
        assert kode == 400, (aksi, target, revisi)
    assert segar(1).revisi == 1


@pytest.mark.parametrize("target,revisi", [("3", 0), ("3/", 0), ("/1", 0), ("3/1/1", 0), ("9/1", 0), ("3/99", 0),
                                           (5, 0), ("3/1", 1), ("03/1", 0)])
def test_target_buat_tinjauan_tak_sah_400(tertutup, admin, target, revisi):
    assert kirim(tertutup, admin, ui.AKSI_BUAT, target, revisi, isi_sah())[0] == 400
    assert not _db().exists()


# --- konflik --------------------------------------------------------------------------------

def test_dua_tinjauan_revisi_sama_yang_kedua_409_dan_store_memuat_hasil_pertama(tertutup, admin):
    item = buat_langsung()
    assert kirim_ubah(tertutup, admin, item.id, 1, isi_sah(judul="Pertama"))[0] == 303
    sebelum = stempel(_db())
    kode, isi, _t = kirim_ubah(tertutup, admin, item.id, 1, isi_sah(judul="Kedua"))
    assert kode == 409 and "Buka ulang" in isi and "Traceback" not in isi
    assert stempel(_db()) == sebelum and segar(item.id).cetakan.judul == "Pertama"


@pytest.mark.parametrize("aksi", [ui.AKSI_SETUJUI, ui.AKSI_NONAKTIFKAN, ui.AKSI_AKTIFKAN])
def test_aksi_pindah_dengan_revisi_basi_409(tertutup, admin, aksi):
    keadaan = _siapkan(tertutup, admin, aksi)
    sebelum = stempel(_db())
    assert kirim_pindah(tertutup, admin, aksi, keadaan["target"], keadaan["revisi"] - 1)[0] in (400, 409)
    kode = kirim_pindah(tertutup, admin, aksi, keadaan["target"], keadaan["revisi"] + 5)[0]
    assert kode == 409 and stempel(_db()) == sebelum


def test_kirim_ulang_aksi_sama_setelah_sukses_409_tanpa_ubah_ulang(tertutup, admin):
    item = buat_langsung()
    assert kirim_pindah(tertutup, admin, ui.AKSI_SETUJUI, item.id, 1)[0] == 303
    sebelum = stempel(_db())
    assert kirim_pindah(tertutup, admin, ui.AKSI_SETUJUI, item.id, 1)[0] == 409
    assert stempel(_db()) == sebelum


# --- isi tak sah: 400 dirender ulang --------------------------------------------------------

@pytest.mark.parametrize("ganti,pesan", [
    ({"kunci": "abs(a)"}, "kunci"),
    ({"kunci": "a +"}, "kunci"),
    ({"teks": "{nama} punya {z} kelereng {a} {b}"}, "placeholder"),
    ({"var_3_nama": "c"}, "belum lengkap"),
    ({"var_3_nama": "a", "var_3_min": "1", "var_3_max": "2"}, "dipakai lebih dari satu"),
    ({"var_1_min": "1,5"}, "hanya angka"),
    ({"var_1_min": "-1"}, "hanya angka"),
    ({"var_1_max": "٣"}, "hanya angka"),
    ({"var_1_max": "99999999999"}, "hanya angka"),
    ({"var_1_min": "60"}, "min <= max"),
    ({"nama": "mungkin"}, "ya atau tidak"),
    ({"judul": ""}, "judul"),
    ({"syarat_2": "a"}, "syarat"),
    ({"var_1_nama": "A"}, "satu huruf kecil"),
], ids=lambda x: x if isinstance(x, str) else "")
def test_isi_tak_sah_buat_400_input_dipertahankan_tanpa_baris_tersimpan(tertutup, admin, ganti, pesan):
    isi = isi_sah(**ganti)
    kode, halaman, tajuk = kirim_buat(tertutup, admin, isi)
    assert kode == 400 and "Location" not in tajuk and 'role="alert"' in halaman
    assert pesan in html.unescape(halaman) and "Traceback" not in halaman
    assert not _db().exists()
    field = formulir(halaman, ui.RUTE_BARU)
    assert field["reauth"] == "" and SANDI_ADMIN not in halaman
    for nama, nilai in isi.items():
        if nama != "nama":  # select: nilai di luar pilihan tak bisa ditampilkan
            assert field[nama] == nilai  # nilai yang diketik dipertahankan


def test_halaman_400_buat_punya_token_baru_yang_bisa_dikirim_ulang_setelah_diperbaiki(tertutup, admin):
    isi = isi_sah(kunci="abs(a)")
    _k, halaman, _t = kirim_buat(tertutup, admin, isi)
    field = formulir(halaman, ui.RUTE_BARU)
    field.update(kunci="a + b", reauth=SANDI_ADMIN)
    kode, _i, tajuk = minta_admin(tertutup, ui.RUTE_BARU, admin, field)
    assert kode == 303 and segar(_id_dari(tajuk)).cetakan.kunci == "a + b"


def test_isi_tak_sah_ubah_400_stempel_tak_berubah_contoh_dari_isi_tersimpan(tertutup, admin):
    item = buat_langsung()
    sebelum = stempel(_db())
    isi = isi_sah(kunci="a ** 2", judul="Judul ketikan")
    kode, halaman, _t = kirim_ubah(tertutup, admin, item.id, 1, isi)
    assert kode == 400 and stempel(_db()) == sebelum and 'role="alert"' in halaman
    field = formulir(halaman, ui.RUTE_UBAH)
    assert field["kunci"] == "a ** 2" and field["judul"] == "Judul ketikan" and field["reauth"] == ""
    assert _badan(halaman).count("kur-kunci") == 10 and "a + b" in halaman  # contoh dan pola = isi TERSIMPAN
    assert SANDI_ADMIN not in halaman


def test_token_halaman_400_ubah_terikat_revisi_yang_diajukan_bukan_baca_ulang(tertutup, admin):
    item = buat_langsung()
    assert kirim_ubah(tertutup, admin, item.id, 1, isi_sah(judul="Sudah berubah"))[0] == 303  # revisi 2
    _k, halaman, _t = kirim_ubah(tertutup, admin, item.id, 1, isi_sah(kunci="a ** 2"))  # token revisi 1, isi buruk
    assert _k == 400
    field = formulir(halaman, ui.RUTE_UBAH)
    field.update(kunci="a + b", reauth=SANDI_ADMIN)
    assert minta_admin(tertutup, ui.RUTE_UBAH, admin, field)[0] == 409  # tidak diam-diam menimpa revisi 2
    assert segar(item.id).cetakan.judul == "Sudah berubah"


def test_ubah_pada_cetakan_aktif_400_status_tak_berubah(tertutup, admin):
    item = aktifkan_langsung(buat_langsung())
    sebelum = stempel(_db())
    kode, halaman, _t = kirim_ubah(tertutup, admin, item.id, item.revisi, isi_sah(judul="Tak boleh"))
    assert kode == 400 and "draf" in halaman and stempel(_db()) == sebelum


def test_setujui_gagal_uji_kelayakan_400_dengan_alasan_dan_tetap_draf(tertutup, admin):
    kode, _i, tajuk = kirim_buat(tertutup, admin, isi_tak_layak())
    assert kode == 303
    sebelum = stempel(_db())
    kode, halaman, _t = kirim_pindah(tertutup, admin, ui.AKSI_SETUJUI, _id_dari(tajuk), 1)
    assert kode == 400 and "Uji kelayakan gagal" in halaman and "25 soal unik" in halaman
    assert segar(1).status == "draf" and stempel(_db()) == sebelum
    assert store.aktif_untuk_bab(*BAB_ADA) == ()
    assert semua_action(halaman) == [ui.RUTE_UBAH, ui.RUTE_SETUJUI]  # token baru: aksi bisa dicoba lagi


def test_setujui_pada_cetakan_aktif_dan_aktifkan_pada_cetakan_aktif_400(tertutup, admin):
    item = aktifkan_langsung(buat_langsung())
    sebelum = stempel(_db())
    for aksi in (ui.AKSI_SETUJUI, ui.AKSI_AKTIFKAN):
        kode, halaman, _t = kirim_pindah(tertutup, admin, aksi, item.id, item.revisi)
        assert kode == 400 and "Hanya cetakan berstatus" in halaman
    assert kirim_pindah(tertutup, admin, ui.AKSI_NONAKTIFKAN, buat_langsung().id, 1)[0] == 400
    assert segar(item.id).status == "aktif" and stempel(_db())[1][: len(sebelum[1])] == sebelum[1]


# --- DB rusak -------------------------------------------------------------------------------

def test_db_rusak_post_503_tanpa_path_dan_berkas_tak_berubah(tertutup, admin, tmp_path):
    _db().write_bytes(b"bukan sqlite sama sekali")
    store.bersihkan_cache()
    kasus = [
        kirim_buat(tertutup, admin),
        kirim_ubah(tertutup, admin, 1, 1),
        kirim_pindah(tertutup, admin, ui.AKSI_SETUJUI, 1, 1),
        kirim_pindah(tertutup, admin, ui.AKSI_NONAKTIFKAN, 1, 1),
        kirim_pindah(tertutup, admin, ui.AKSI_AKTIFKAN, 1, 1),
    ]
    for kode, isi, _t in kasus:
        assert kode == 503 and str(tmp_path) not in isi and "cetakan.db" not in isi and "Traceback" not in isi
    assert _db().read_bytes() == b"bukan sqlite sama sekali"


def test_db_rusak_get_daftar_tetap_200_kosong_dan_periksa_404(tertutup, admin):
    _db().write_bytes(b"bukan sqlite sama sekali")
    store.bersihkan_cache()
    kode, isi, _t = minta_admin(tertutup, _alamat_daftar(), admin)
    assert kode == 200 and "Belum ada cetakan untuk bab ini." in isi
    assert minta_admin(tertutup, _alamat_periksa(1), admin)[0] == 404
    assert minta_admin(tertutup, "%s?kelas=3&bab=1" % ui.RUTE_BARU, admin)[0] == 200


def test_skema_db_asing_post_503_dan_berkas_tak_berubah(tertutup, admin):
    import sqlite3
    with sqlite3.connect(_db()) as kon:
        kon.execute("PRAGMA user_version = 99")
    assert kirim_buat(tertutup, admin)[0] == 503
    with sqlite3.connect(_db()) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 99
        assert kon.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == 0


def test_baris_cetakan_hilang_dari_store_post_aksi_503(tertutup, admin):
    """Berkas ada tetapi id dari tinjauan tak ada (mis. berkas diganti): 503 jujur, bukan 500 atau 404."""
    buat_langsung()
    assert kirim_pindah(tertutup, admin, ui.AKSI_SETUJUI, 77, 1)[0] == 503
    assert kirim_ubah(tertutup, admin, 77, 1)[0] == 503


def test_judul_dari_form_tampil_di_halaman_daftar_setelah_dibuat(tertutup, admin):
    assert kirim_buat(tertutup, admin, isi_sah(judul="Judul unik cek daftar"))[0] == 303
    assert "Judul unik cek daftar" in daftar_halaman(tertutup, admin, _alamat_daftar())[1] and JUDUL not in (
        daftar_halaman(tertutup, admin, _alamat_daftar())[1])

"""Layar admin Harga (/admin/harga): lihat dan ubah harga Private dan Mini Class. Data SINTETIS.

Aturan a-i dari brief: non-admin 404 identik, tinjauan + CSRF + sandi ulang, produk hanya dari tinjauan,
validasi nilai ketat, konflik 409, PRG + whitelist hasil, skema belum/rusak, dan efek ke tagihan baru.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_harga_http  # noqa: E402
import admin_http  # noqa: E402
import admin_security  # noqa: E402
import admin_store  # noqa: E402
import auth  # noqa: E402
import harga  # noqa: E402
import harga_validasi  # noqa: E402
import laju_masuk  # noqa: E402
import pesanan  # noqa: E402
import schema_harga  # noqa: E402
from admin_pesanan_kit import TAK_ADA, id_admin, login_admin, minta_admin  # noqa: E402
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID  # noqa: E402
from kelas_kit import siapkan_db_kelas, tagih  # noqa: E402
from pesanan_transfer_http_kit import jam, keluarga, minta_mentah, server, tertutup  # noqa: E402,F401

RUTE = "/admin/harga"
AKSI = "ubah_harga"
SEKARANG = "2026-11-25T08:00:00"
PRIVATE_AWAL, MINI_AWAL = 640_000, 300_000
PRIVATE_BARU, MINI_BARU = 700_000, 320_000
AKUN_GURU = ("guru", SANDI_GURU)
AKUN_MURID = ("feby", SANDI_MURID)
LINTAS_SITUS = {"Sec-Fetch-Site": "cross-site"}
POLA_WAKTU = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


@pytest.fixture(autouse=True)
def _laju_bersih():
    laju_masuk._reset()
    yield
    laju_masuk._reset()


@pytest.fixture()
def admin(tertutup):
    return login_admin(tertutup)


@pytest.fixture()
def harga_terpasang(tertutup):
    schema_harga.migrasikan(admin_store.BAWAAN)
    return tertutup


def _snapshot():
    """(harga_produk, harga_riwayat) mentah; None bila tabel harga_* belum dipasang."""
    kon = sqlite3.connect(admin_store.BAWAAN)
    try:
        if not schema_harga.struktur(kon):
            return None
        produk = kon.execute("SELECT kode, rupiah, diubah, diubah_oleh FROM harga_produk ORDER BY kode").fetchall()
        riwayat = kon.execute("SELECT id, kode, lama, baru, oleh, waktu FROM harga_riwayat ORDER BY id").fetchall()
        return produk, riwayat
    finally:
        kon.close()


def _token(cookie, kode, lama, *, aksi=AKSI, sekarang=None):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie), "reauth": SANDI_ADMIN,
            "tinjauan": admin_security.buat_tinjauan(
                akun, cookie, aksi, {"target_id": kode, "target_revisi": lama}, sekarang=sekarang)}


def _formulir(cookie, kode, lama, baru, *, aksi=AKSI, sekarang=None):
    return {**_token(cookie, kode, lama, aksi=aksi, sekarang=sekarang), "kode": kode, "harga_baru": baru}


def _kirim_data(server, cookie, data, *, ganti=None, hapus=(), headers=None):
    isi = {**data, **(ganti or {})}
    for kunci in hapus:
        isi.pop(kunci, None)
    return minta_mentah(server, RUTE, None, isi, {"Cookie": "osn_sesi=" + cookie, **(headers or {})})


def _kirim(server, cookie, kode, lama, baru, *, aksi=AKSI, ganti=None, hapus=(), headers=None):
    data = _formulir(cookie, kode, lama, baru, aksi=aksi)
    return _kirim_data(server, cookie, data, ganti=ganti, hapus=hapus, headers=headers)


def _ubah_langsung(kode, lama, baru, waktu=SEKARANG):
    return harga.ubah_harga(admin_store.BAWAAN, kode, baru, lama, id_admin(), waktu)


# --- a. akses ----------------------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_GURU, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_nonadmin_404_identik_rute_tak_dikenal_tanpa_menyentuh_db(tertutup, admin, akun, monkeypatch):
    acuan_get = minta_mentah(tertutup, TAK_ADA, akun)
    acuan_post = minta_mentah(tertutup, TAK_ADA, akun, {"x": "1"})
    assert acuan_get[0] == acuan_post[0] == 404

    def gagal(*_a, **_k):
        raise AssertionError("DB harga tidak boleh disentuh")

    monkeypatch.setattr(admin_store, "buka_baca", gagal)
    monkeypatch.setattr(harga, "ubah_harga", gagal)
    assert minta_mentah(tertutup, RUTE, akun)[:2] == acuan_get[:2]
    assert minta_mentah(tertutup, RUTE, akun, {"x": "1"})[:2] == acuan_post[:2]
    assert minta_mentah(tertutup, RUTE, akun, {"kode": "private", "harga_baru": "700000"})[:2] == acuan_post[:2]


# --- tampilan ----------------------------------------------------------------------------------

def test_halaman_admin_menampilkan_produk_dan_form_hanya_untuk_private_mini(harga_terpasang, admin):
    kode, isi, tajuk = minta_admin(harga_terpasang, RUTE, admin)
    assert kode == 200 and tajuk["Cache-Control"] == "no-store"
    for teks in ("Private", "Mini Class", "Peta Kemampuan", "Latihan Harian", "Bulanan", "Tahunan",
                 "Belum bisa diatur", "Rp640.000", "Rp300.000", "Rp591.000", "Rp251.000", "nilai awal"):
        assert teks in isi, teks
    assert isi.count('name="harga_baru"') == 2
    assert 'value="peta"' not in isi and 'type="number"' not in isi and 'inputmode="numeric"' in isi
    assert SANDI_ADMIN not in isi and str(admin_store.BAWAAN) not in isi


def test_teks_tegas_tagihan_baru_dan_rentang_tampil(harga_terpasang, admin):
    isi = minta_admin(harga_terpasang, RUTE, admin)[1]
    assert "Harga baru berlaku untuk tagihan BARU. Tagihan yang sudah dibuat tetap pada harga yang tersimpan." in isi
    for teks in ("Rp10.000", "Rp9.000.000", "Rp1.000"):
        assert teks in isi, teks


def test_pengaturan_layanan_menautkan_halaman_harga(harga_terpasang, admin):
    assert 'href="/admin/harga"' in minta_admin(harga_terpasang, "/admin/sakelar", admin)[1]


@pytest.mark.parametrize("query", ["?hasil=sembarang", "?x=1", "?hasil=", "?hasil=tersimpan&hasil=tersimpan"])
def test_query_tak_sah_404_identik(harga_terpasang, admin, query):
    acuan = minta_admin(harga_terpasang, TAK_ADA, admin)
    assert acuan[0] == 404
    assert minta_admin(harga_terpasang, RUTE + query, admin)[:2] == acuan[:2]


# --- b/f. ubah sukses, PRG, satu riwayat -------------------------------------------------------

def test_ubah_harga_private_sukses_prg_dan_tepat_satu_riwayat(harga_terpasang, admin):
    kode, _isi, tajuk = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, PRIVATE_BARU)
    assert kode == 303 and tajuk["Location"] == RUTE + "?hasil=tersimpan"
    produk, riwayat = _snapshot()
    assert [(r[0], r[1]) for r in produk] == [("private", PRIVATE_BARU)]
    assert len(riwayat) == 1
    _id, kode_r, lama, baru, oleh, waktu = riwayat[0]
    # lama = harga efektif sebelumnya (nilai awal karena ini perubahan pertama; lihat harga.py).
    assert (kode_r, lama, baru, oleh) == ("private", PRIVATE_AWAL, PRIVATE_BARU, id_admin())
    assert POLA_WAKTU.fullmatch(waktu)


def test_hasil_tersimpan_tampil_setelah_prg(harga_terpasang, admin):
    _kirim(harga_terpasang, admin, "mini", MINI_AWAL, MINI_BARU)
    kode, isi, _t = minta_admin(harga_terpasang, RUTE + "?hasil=tersimpan", admin)
    assert kode == 200 and 'role="status"' in isi and "Harga tersimpan" in isi
    assert "Rp320.000" in isi and "diubah admin" in isi


# --- b. tinjauan, CSRF, sandi, asal ------------------------------------------------------------

@pytest.mark.parametrize(
    "ganti, hapus, headers",
    [
        ({}, ("csrf",), None),
        ({"csrf": "salah"}, (), None),
        ({}, ("tinjauan",), None),
        ({"tinjauan": "rusak.rusak"}, (), None),
        ({"reauth": "salah"}, (), None),
        ({"reauth": ""}, (), None),
        ({}, (), LINTAS_SITUS),
    ],
    ids=["tanpa_csrf", "csrf_salah", "tanpa_tinjauan", "tinjauan_rusak", "sandi_salah", "sandi_kosong", "asal_beda"],
)
def test_pagar_csrf_tinjauan_sandi_dan_asal_menolak_tanpa_tulis(harga_terpasang, admin, ganti, hapus, headers):
    sebelum = _snapshot()
    kode, _isi, _t = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, PRIVATE_BARU,
                            ganti=ganti, hapus=hapus, headers=headers)
    assert kode == 403
    assert _snapshot() == sebelum


def test_tinjauan_kedaluwarsa_menolak_tanpa_tulis(harga_terpasang, admin):
    sebelum = _snapshot()
    data = _formulir(admin, "private", PRIVATE_AWAL, PRIVATE_BARU, sekarang=int(time.time()) - 5000)
    assert _kirim_data(harga_terpasang, admin, data)[0] == 403
    assert _snapshot() == sebelum


def test_tinjauan_aksi_lain_menolak_tanpa_tulis(harga_terpasang, admin):
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, PRIVATE_BARU, aksi="ubah_sakelar")[0] == 403
    assert _snapshot() == sebelum


# --- c. produk tidak dipercaya dari form -------------------------------------------------------

@pytest.mark.parametrize("kode_form", ["peta", "harian", "mini"])
def test_kode_form_berbeda_dari_tinjauan_ditolak_tanpa_tulis(harga_terpasang, admin, kode_form):
    sebelum = _snapshot()
    data = _formulir(admin, "private", PRIVATE_AWAL, PRIVATE_BARU)
    data["kode"] = kode_form
    assert _kirim_data(harga_terpasang, admin, data)[0] == 400
    assert _snapshot() == sebelum


def test_tinjauan_sah_untuk_peta_ditolak_tanpa_tulis(harga_terpasang, admin):
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "peta", 49_000, 50_000)[0] == 400
    assert _snapshot() == sebelum


def test_tinjauan_mini_dengan_harga_lama_private_ditolak_409_tanpa_tulis(harga_terpasang, admin):
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "mini", PRIVATE_AWAL, MINI_BARU)[0] == 409
    assert _snapshot() == sebelum


def test_perintah_http_menolak_peta_dan_harian_sebelum_validator():
    """Penjaga di jalur HTTP: tinjauan sah sekalipun untuk Peta/Harian tetap ditolak sebelum harga dibaca."""
    for kode in ("peta", "harian"):
        tinjauan = {"data": {"target_id": kode, "target_revisi": 49_000}}
        with pytest.raises(ValueError):
            admin_harga_http._perintah(tinjauan, {"kode": kode})


# --- d. nilai harga ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "nilai",
    ["", " 700000", "700000 ", "+700000", "-700000", "700000.0", "7e5", "700,000", "700.000", "700_000",
     "٧٠٠٠٠٠", "70000000000000000", "700500", "7000", "9000001"],
    ids=["kosong", "spasi_depan", "spasi_belakang", "plus", "minus", "desimal", "notasi", "koma", "titik",
         "garis_bawah", "digit_arab", "panjang", "kelipatan", "di_bawah_rentang", "di_atas_kelipatan"],
)
def test_nilai_harga_tidak_sah_ditolak_tanpa_tulis(harga_terpasang, admin, nilai):
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, nilai)[0] == 400
    assert _snapshot() == sebelum


def test_pesan_validator_ditampilkan_setelah_escape(harga_terpasang, admin, monkeypatch):
    def galat(*_a, **_k):
        raise ValueError("<b>x</b>")

    monkeypatch.setattr(harga_validasi, "validasi_harga", galat)
    kode, isi, _t = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, PRIVATE_BARU)
    assert kode == 400 and "&lt;b&gt;x&lt;/b&gt;" in isi and "<b>x</b>" not in isi


def test_validasi_pra_menolak_sebelum_ubah_harga_dipanggil(harga_terpasang, admin, monkeypatch):
    def ubah_tak_boleh(*_a, **_k):
        raise AssertionError("ubah_harga tidak boleh dipanggil untuk nilai yang tidak lolos validasi")

    monkeypatch.setattr(harga, "ubah_harga", ubah_tak_boleh)
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, "700500")[0] == 400
    assert _snapshot() == sebelum


# --- guard salah ketik: selisih lebih dari 2x atau kurang dari separuh butuh konfirmasi eksplisit ------

@pytest.mark.parametrize("baru", ["64000", "50000", "1300000", "1400000"], ids=["sepersepuluh", "kurang-separuh", "tepat-lebih-2x", "2x-lebih"])
def test_selisih_besar_tanpa_konfirmasi_ditolak_tanpa_tulis(harga_terpasang, admin, baru):
    # 320000 = tepat separuh (boleh); 320001 dst. di bawah separuh ditolak; 1280000 = tepat 2x (boleh).
    sebelum = _snapshot()
    kode, isi, _ = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, baru)
    assert kode == 400 and "konfirmasi" in isi.lower()
    assert _snapshot() == sebelum


@pytest.mark.parametrize("baru", ["320000", "1280000", "700000"], ids=["tepat-separuh", "tepat-2x", "wajar"])
def test_selisih_di_batas_atau_wajar_tidak_butuh_konfirmasi(harga_terpasang, admin, baru):
    # Private 320000 dan 1280000 harus lolos validator domain (pita/nominal); bila tidak, ganti ke produk Mini.
    kode = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, baru)[0]
    assert kode in (303, 302)


def test_selisih_besar_dengan_konfirmasi_ya_diterima(harga_terpasang, admin):
    kode = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, "1400000", ganti={"konfirmasi_selisih": "ya"})[0]
    assert kode in (303, 302)
    assert _snapshot()[0][0][1] == 1_400_000


@pytest.mark.parametrize("nilai", ["1", "on", "", "YA", "ya "], ids=["1", "on", "kosong", "kapital", "spasi"])
def test_konfirmasi_selisih_nilai_selain_ya_ditolak(harga_terpasang, admin, nilai):
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, "1400000", ganti={"konfirmasi_selisih": nilai})[0] == 400
    assert _snapshot() == sebelum


def test_field_asing_tetap_ditolak_walau_ada_konfirmasi(harga_terpasang, admin):
    sebelum = _snapshot()
    kode = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, "700000",
                  ganti={"konfirmasi_selisih": "ya", "admin_id": "x"})[0]
    assert kode == 400
    assert _snapshot() == sebelum


def test_form_memuat_kotak_konfirmasi_selisih(harga_terpasang, admin):
    kode, isi, _ = minta_mentah(harga_terpasang, RUTE, None, None, {"Cookie": "osn_sesi=" + admin})
    assert kode == 200 and isi.count('name="konfirmasi_selisih"') == 2  # satu per produk yang bisa diubah


def test_harga_sama_dengan_harga_aktif_ditolak_tanpa_riwayat_palsu(harga_terpasang, admin):
    sebelum = _snapshot()
    kode, isi, _ = _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, str(PRIVATE_AWAL))
    assert kode == 400 and "sama dengan harga aktif" in isi
    assert _snapshot() == sebelum


# --- e. konflik dan kirim ulang ----------------------------------------------------------------

def test_harga_aktif_berubah_antara_tampil_dan_kirim_409_tanpa_tulis(harga_terpasang, admin):
    _ubah_langsung("private", PRIVATE_AWAL, 650_000)
    sebelum = _snapshot()
    assert _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, PRIVATE_BARU)[0] == 409
    assert _snapshot() == sebelum


def test_kirim_ulang_form_sukses_409_dan_tetap_satu_riwayat(harga_terpasang, admin):
    data = _formulir(admin, "private", PRIVATE_AWAL, PRIVATE_BARU)
    assert _kirim_data(harga_terpasang, admin, data)[0] == 303
    assert _kirim_data(harga_terpasang, admin, data)[0] == 409
    _produk, riwayat = _snapshot()
    assert len(riwayat) == 1


# --- g. skema belum/rusak ----------------------------------------------------------------------

def test_skema_belum_dipasang_baca_saja_dan_post_409_tanpa_tulis(tertutup, admin):
    assert _snapshot() is None
    kode, isi, _t = minta_admin(tertutup, RUTE, admin)
    assert kode == 200 and "Pengaturan harga belum dipasang di server ini" in isi
    assert 'name="harga_baru"' not in isi and 'action="/admin/harga"' not in isi
    assert _kirim(tertutup, admin, "private", PRIVATE_AWAL, PRIVATE_BARU)[0] == 409
    assert _snapshot() is None


def test_skema_rusak_503_tanpa_detail_dan_tanpa_tulis(harga_terpasang, admin):
    kon = sqlite3.connect(admin_store.BAWAAN)
    try:
        kon.execute("DROP TRIGGER harga_riwayat_tolak_update")
        kon.commit()
    finally:
        kon.close()
    sebelum = _snapshot()
    kode, isi, _t = minta_admin(harga_terpasang, RUTE, admin)
    assert kode == 503
    assert "harga_riwayat" not in isi and str(admin_store.BAWAAN) not in isi and "sqlite" not in isi.lower()
    assert _kirim(harga_terpasang, admin, "private", PRIVATE_AWAL, PRIVATE_BARU)[0] == 503
    assert _snapshot() == sebelum


# --- riwayat -----------------------------------------------------------------------------------

def test_riwayat_terbaru_dulu_dan_maks_50(harga_terpasang, admin):
    harga_kini = PRIVATE_AWAL
    for i in range(51):
        baru = PRIVATE_AWAL + 10_000 if harga_kini == PRIVATE_AWAL else PRIVATE_AWAL
        _ubah_langsung("private", harga_kini, baru, "2026-11-25T08:00:%02d" % i)
        harga_kini = baru
    isi = minta_admin(harga_terpasang, RUTE, admin)[1]
    assert "2026-11-25T08:00:50" in isi and "2026-11-25T08:00:01" in isi
    assert "2026-11-25T08:00:00" not in isi
    assert isi.index("2026-11-25T08:00:50") < isi.index("2026-11-25T08:00:01")


# --- i. efek ke tagihan baru -------------------------------------------------------------------

def test_tagihan_baru_memakai_harga_baru_dan_tagihan_lama_tetap(harga_terpasang, admin):
    path = admin_store.BAWAAN
    siapkan_db_kelas(path.parent)
    with pesanan.buka(path, tulis_data=True) as kon:
        lama = tagih(kon, 1, "mini")
    assert lama.rincian.harga_dasar == MINI_AWAL
    assert _kirim(harga_terpasang, admin, "mini", MINI_AWAL, MINI_BARU)[0] == 303
    with pesanan.buka(path, tulis_data=True) as kon:
        baru = tagih(kon, 2, "mini")
        tetap = tagih(kon, 1, "mini")
    assert baru.rincian.harga_dasar == MINI_BARU
    assert tetap.rincian.harga_dasar == MINI_AWAL

"""Gerbang KODE_ANAK_AKTIF mati: ketiga permukaan kode anak tidak ada lewat HTTP (Fase 3b-6).

Berkas ini TIDAK termasuk BERKAS_GERBANG_KODE_ANAK_NYALA di conftest.py; gerbang diatur sendiri lewat monkeypatch
(nilai bawaan kode kini True sejak c25453b, jadi keadaan mati selalu dipatok eksplisit). Tiap kasus
dibuktikan dengan kontrol positif (gerbang dinyalakan lewat monkeypatch dan permukaan ada), lalu keadaan mati. Token
form diambil saat gerbang menyala karena form tidak dirender saat mati; token HMAC itu tetap sah setelahnya. Penolakan
mati harus identik byte demi byte dengan rute tak dikenal atau 404 kepemilikan, dan tidak membuat `guru-tautan.db`.
Data sepenuhnya sintetis di tmp_path.
"""
from __future__ import annotations

import html
import http.cookies
import re
from types import SimpleNamespace

import pytest

import admin_kode_anak_pages as akp
import admin_store
import auth
import database
import guru_tautan_aturan as aturan
import jadwal_store as js
import kelas_store as store
import pin_orang_tua_store as pin_store
import tirai_orang_tua as tirai
from cek_http_kit import AKUN_ADMIN, AKUN_A, ambil_token, minta_mentah, server  # noqa: F401
from guru_tautan_kit import (
    ADMIN, JALUR_TAUTAN, JAM_KELOMPOK, KINI, KODE, LOKASI, baris_tabel, siapkan_db_tautan, siapkan_kelompok_dan_order,
)
from harian_kit import jam  # noqa: F401
from http_test_kit import ServerUji
from orang_tua_kode_kit import RUTE, RUTE_KODE, form_kode, login, req

KELOMPOK_TIDAK_ADA = "klp_" + "0" * 32
TANGGAL_KELOMPOK_LAIN = "2026-11-27"
LOGIN_GURU_LAIN = "guru-lain-gerbang"
SANDI_GURU_LAIN = "sandi-guru-lain-gerbang-123"
RUTE_DETAIL_ADMIN = "/admin/kelas/verifikasi"
RUTE_TAK_ADA_ADMIN = "/admin/tidak-ada"
RUTE_ORTU_TAK_ADA = RUTE + "/tidak-ada"
RUTE_ORTU_TAUTAN = RUTE + "/tautan"
NAMA_MURID = "raka-gerbang"
SANDI_MURID = "sandi-raka-gerbang-123"
PIN = "4821"
FRAGMEN_KARTU = "Kode anak untuk guru"
FRAGMEN_FORM_KODE_ORTU = f'action="{RUTE_KODE}"'
FRAGMEN_JUDUL_BAGIAN_GURU = 'aria-label="Permintaan kode anak"'
POLA_FORM_TAUTAN_GURU = re.compile(r'action="/guru/kelas/klp_[0-9a-f]{32}/tautan"')
POLA_FORM_TEMA = re.compile(r'<form class="admin-tema".*?</form>', re.S)
POLA_FORM_ADMIN = re.compile(r'<form method="post" action="/admin/kelas/kode-anak"([^>]*)>(.*?)</form>', re.S)
POLA_ISIAN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)">')
FRAGMEN_FORM_ADMIN = f'action="{akp.RUTE_KODE}"'


# --- pembantu ---------------------------------------------------------------------------------

def _gerbang(monkeypatch, nyala: bool) -> None:
    monkeypatch.setattr(aturan, "KODE_ANAK_AKTIF", nyala)


def _respons(hasil) -> tuple:
    """Status, Content-Type, Content-Length, dan badan: bagian yang harus identik untuk penolakan."""
    kode, isi, tajuk = hasil
    kecil = {nama.lower(): nilai for nama, nilai in tajuk.items()}
    return kode, kecil.get("content-type"), kecil.get("content-length"), isi


def _tanpa_tema(hasil) -> tuple:
    """Badan tanpa formulir tema admin, yang ditandatangani per respons dan karena itu berbeda antar-permintaan."""
    kode, ctype, clen, isi = _respons(hasil)
    return kode, ctype, clen, POLA_FORM_TEMA.sub("", isi)


def _kelompok_guru_lain(server) -> str:
    """Kelompok Mini milik guru lain. Guru A yang mengajukan ke sini harus dijawab 404 identik."""
    auth.tambah_akun(LOGIN_GURU_LAIN, SANDI_GURU_LAIN, "guru")
    guru_lain = auth.cari_akun(LOGIN_GURU_LAIN)["id_akun"]
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelompok = js.buat_kelompok(kon, ADMIN, nama="Mini Lain", lokasi=LOKASI, guru_id=guru_lain,
                                    kuota=5, tanggal=TANGGAL_KELOMPOK_LAIN, jam=JAM_KELOMPOK, sekarang=KINI)
        kon.commit()
    return kelompok


# --- guru -------------------------------------------------------------------------------------

def _get_guru(server, kelompok_id: str) -> str:
    kode, isi, _tajuk = minta_mentah(server, f"/guru/kelas/{kelompok_id}", AKUN_A)
    assert kode == 200, kode
    return isi


def _token_guru(server, kelompok_id: str, monkeypatch) -> str:
    """Token form tautan diambil saat gerbang menyala, karena form tidak dirender ketika mati."""
    _gerbang(monkeypatch, True)
    token = ambil_token(server, AKUN_A, f"/guru/kelas/{kelompok_id}")
    _gerbang(monkeypatch, False)
    return token


def _post_guru(server, kelompok_id: str, token: str):
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), AKUN_A,
                        data={"kode": KODE, "token": token})


def test_gerbang_bawaan_menyala_di_kode_rilis_dan_dibaca_saat_panggilan(monkeypatch):
    """Commit rilis menyalakan gerbang; `kode_anak_aktif()` membaca konstanta saat panggilan, bukan saat impor."""
    assert aturan.KODE_ANAK_AKTIF is True
    assert aturan.kode_anak_aktif() is True
    monkeypatch.setattr(aturan, "KODE_ANAK_AKTIF", False)
    assert aturan.kode_anak_aktif() is False


def test_guru_detail_tanpa_form_tautan_saat_gerbang_mati(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    _gerbang(monkeypatch, True)
    menyala = _get_guru(server, kondisi.kelompok_id)
    _gerbang(monkeypatch, False)
    mati = _get_guru(server, kondisi.kelompok_id)

    assert FRAGMEN_JUDUL_BAGIAN_GURU in menyala and POLA_FORM_TAUTAN_GURU.search(menyala), "kontrol: permukaan ada"
    assert FRAGMEN_JUDUL_BAGIAN_GURU not in mati
    assert POLA_FORM_TAUTAN_GURU.search(mati) is None
    assert not db.exists(), "gerbang mati tidak boleh membuat guru-tautan.db"


def test_guru_post_saat_gerbang_mati_identik_404_tanpa_berkas(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    kelompok_lain = _kelompok_guru_lain(server)
    token = _token_guru(server, kondisi.kelompok_id, monkeypatch)

    milik = _post_guru(server, kondisi.kelompok_id, token)
    tak_ada = _post_guru(server, KELOMPOK_TIDAK_ADA, token)
    milik_guru_lain = _post_guru(server, kelompok_lain, token)

    assert milik[0] == 404
    assert _respons(milik) == _respons(tak_ada) == _respons(milik_guru_lain)
    assert not db.exists(), "gerbang mati tidak boleh membuat guru-tautan.db"

    _gerbang(monkeypatch, True)
    kontrol = _post_guru(server, kondisi.kelompok_id, token)
    assert kontrol[0] == 400, "kontrol: dengan gerbang menyala, kode belum ada, jadi gagal generik bukan 404"
    assert db.exists()


# --- orang tua --------------------------------------------------------------------------------

@pytest.fixture
def ortu(tmp_path, monkeypatch):
    server_ortu = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    berkas = siapkan_db_tautan(tmp_path, monkeypatch)
    tirai._reset()
    with server_ortu.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak Gerbang", "P4", pemilik="koordinator-sintetis")
        pin_store.simpan(kon, siswa, PIN, 1_800_000_000)
    auth.tambah_akun_dan_principal(NAMA_MURID, SANDI_MURID, "murid", siswa_id=siswa)
    yield SimpleNamespace(server=server_ortu, berkas=berkas)
    tirai._reset()
    server_ortu.berhenti()


def _buka_tirai(ortu) -> str:
    cookie = login(ortu.server, NAMA_MURID, SANDI_MURID)
    kode, _isi, _tajuk = req(ortu.server, RUTE + "/pin", data={"pin": PIN}, cookie=cookie)
    assert kode == 303, kode
    return cookie


def test_orang_tua_gerbang_mati_kartu_hilang_dan_post_identik_rute_tak_dikenal(ortu, monkeypatch):
    cookie = _buka_tirai(ortu)
    _gerbang(monkeypatch, True)
    menyala = req(ortu.server, RUTE, cookie=cookie)[1]
    token = form_kode(menyala, "buat").get("token")
    _gerbang(monkeypatch, False)
    mati = req(ortu.server, RUTE, cookie=cookie)[1]

    assert FRAGMEN_KARTU in menyala and token, "kontrol: kartu dan form buat ada saat menyala"
    assert FRAGMEN_KARTU not in mati
    assert FRAGMEN_FORM_KODE_ORTU not in mati

    data = {"tindakan": "buat", "token": token}
    kode_post = req(ortu.server, RUTE_KODE, data=data, cookie=cookie)
    kode_tak_ada = req(ortu.server, RUTE_ORTU_TAK_ADA, data=data, cookie=cookie)
    tautan_post = req(ortu.server, RUTE_ORTU_TAUTAN, data=data, cookie=cookie)
    tautan_tak_ada = req(ortu.server, RUTE_ORTU_TAK_ADA, data=data, cookie=cookie)

    # Rute murid tak dikenal dengan sesi cookie dijawab 401 di permukaan ini, bukan 404 (lihat test_orang_tua_tautan_http).
    assert kode_post[0] == tautan_post[0] == 401
    assert _respons(kode_post) == _respons(kode_tak_ada)
    assert _respons(tautan_post) == _respons(tautan_tak_ada)
    assert not ortu.berkas.exists(), "gerbang mati tidak boleh membuat guru-tautan.db"

    _gerbang(monkeypatch, True)
    kontrol = req(ortu.server, RUTE_KODE, data=data, cookie=cookie)
    assert kontrol[0] == 200, "kontrol: dengan gerbang menyala, buat kode berhasil"
    assert ortu.berkas.exists()


# --- admin ------------------------------------------------------------------------------------

def _cookie_admin(server) -> dict:
    kode, _isi, tajuk = minta_mentah(server, "/masuk", None, {"nama": AKUN_ADMIN[0], "sandi": AKUN_ADMIN[1]})
    assert kode == 303, kode
    return {"Cookie": "osn_sesi=" + http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value}


def _order_anak(siswa_id: int) -> str:
    with store.buka(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT id FROM kelas_order WHERE siswa_id=?", (siswa_id,)).fetchone()[0]


def _detail_admin(server, order_id: str, cookie: dict) -> str:
    kode, isi, _tajuk = minta_mentah(server, RUTE_DETAIL_ADMIN + "?order=" + order_id, None, None, cookie)
    assert kode == 200, kode
    return isi


def _form_admin_buat(isi: str) -> dict:
    for _atribut, badan in POLA_FORM_ADMIN.findall(isi):
        isian = {nama: html.unescape(nilai) for nama, nilai in POLA_ISIAN.findall(badan)}
        if isian.get("tindakan") == "buat":
            return isian
    return {}


def test_admin_gerbang_mati_blok_hilang_dan_post_identik_rute_tak_dikenal(server, jam, tmp_path, monkeypatch):
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    order = _order_anak(kondisi.siswa_id)
    cookie = _cookie_admin(server)
    _gerbang(monkeypatch, True)
    menyala = _detail_admin(server, order, cookie)
    data = _form_admin_buat(menyala)
    _gerbang(monkeypatch, False)
    mati = _detail_admin(server, order, cookie)

    assert FRAGMEN_FORM_ADMIN in menyala and data.get("token"), "kontrol: blok dan form buat ada saat menyala"
    assert FRAGMEN_FORM_ADMIN not in mati

    kode_post = minta_mentah(server, akp.RUTE_KODE, None, data, cookie)
    kode_tak_ada = minta_mentah(server, RUTE_TAK_ADA_ADMIN, None, data, cookie)

    assert kode_post[0] == 404
    assert _tanpa_tema(kode_post) == _tanpa_tema(kode_tak_ada)
    assert not db.exists(), "gerbang mati tidak boleh membuat guru-tautan.db"

    _gerbang(monkeypatch, True)
    kontrol = minta_mentah(server, akp.RUTE_KODE, None, data, cookie)
    assert kontrol[0] == 200, "kontrol: dengan gerbang menyala, buat kode berhasil"
    assert baris_tabel(db, "kode_anak") == 1

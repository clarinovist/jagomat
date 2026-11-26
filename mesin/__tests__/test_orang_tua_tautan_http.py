"""Kode anak di halaman orang tua (`/murid/orang-tua/kode`, kartu di `/murid/orang-tua`) lewat HTTP nyata.

Gerbang ditegakkan server: sakelar DAFTAR_AKUN_ANAK dan PAKET_BELAJAR, PIN terpasang, tirai terbuka untuk sesi cookie,
token form domain `kode-anak-form-v1:` dengan aksi `kode:<tindakan>`. Kode tampil sekali (no-store, tanpa redirect).
Data sepenuhnya sintetis di tmp_path. Positive control dulu: token dan gerbang yang sah harus berhasil, supaya setiap
tes penolakan membuktikan sesuatu.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import auth
import database
import form_token
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_kode as kode
import orang_tua_tautan_http as tautan_http
import orang_tua_tautan_pages as halaman_kode
import pin_orang_tua_store as pin_store
import sessions
import tirai_aksi
import tirai_orang_tua as tirai
from guru_tautan_kit import baris_tabel
from http_test_kit import SANDI_GURU, ServerUji
from orang_tua_kode_kit import KODE_TAMPIL, RUTE, RUTE_KODE, form_kode as _form_kode, login as _login, req as _req

RUTE_PIN_ATUR = RUTE + "/pin/atur"
SANDI_A = "sandi-raka-sintetis"
SANDI_B = "sandi-dina-sintetis"
PIN_A = "4821"
PIN_B = "1357"
NAMA_A = "Raka Sintetis"
NAMA_B = "Dina Sintetis"
NAMA_GURU = "guru"  # akun guru bawaan ServerUji (sandi SANDI_GURU)
NAMA_PENGELOLA = "pengelola-orang-tua-m"
SANDI_PENGELOLA = "sandi-pengelola-sintetis-123"
SQL_KODE_TERAKHIR = "SELECT akun_id, oleh, peran FROM kode_anak ORDER BY id DESC LIMIT 1"
SQL_CABUT_TERAKHIR = "SELECT oleh, peran FROM kode_cabut ORDER BY id DESC LIMIT 1"
FRAGMEN_KARTU = "Kode anak untuk guru"
TANGGAL_KODE = re.compile(r"Kode aktif sejak \d{1,2} [A-Za-z]+ 20\d\d pukul")
# Daftar terlarang halaman orang tua (sama dengan test_orang_tua_http.KATA_TERLARANG_ORTU).
KATA_TERLARANG_ORTU = (
    "kunci", "malrule", "diagnos", "kode_final", "kode_usulan", "pembahasan", "jawaban benar", "tel:", "wa.me",
)


class Dunia:
    pass


@pytest.fixture
def dunia(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    monkeypatch.setenv(dasar.ENV_DB, str(tmp_path / "guru-tautan-uji.db"))
    tirai._reset()
    d = Dunia()
    d.server, d.monkeypatch, d.berkas = server, monkeypatch, tmp_path / "guru-tautan-uji.db"
    with server.buka() as kon:
        d.a = database.tambah_siswa(kon, NAMA_A, "P4", pemilik="koordinator-sintetis")
        d.b = database.tambah_siswa(kon, NAMA_B, "P3", pemilik="koordinator-sintetis")
    d.akun_a = auth.tambah_akun_dan_principal("raka-m", SANDI_A, "murid", siswa_id=d.a)
    d.akun_b = auth.tambah_akun_dan_principal("dina-m", SANDI_B, "murid", siswa_id=d.b)
    yield d
    tirai._reset()
    server.berhenti()


def _pasang_pin(d, siswa, pin):
    with d.server.buka() as kon:
        pin_store.simpan(kon, siswa, pin, 1_800_000_000)


def _buka_tirai(d, nama="raka-m", sandi=SANDI_A, pin=PIN_A):
    cookie = _login(d.server, nama, sandi)
    kode_status, _, _ = _req(d.server, RUTE + "/pin", data={"pin": pin}, cookie=cookie)
    assert kode_status == 303
    return cookie


def _kirim(d, cookie, tindakan, **tambahan):
    """POST `/murid/orang-tua/kode` dengan token tindakan dari halaman yang baru dirender."""
    isi = _req(d.server, RUTE, cookie=cookie)[1]
    masukan = _form_kode(isi, tindakan)
    data = {"tindakan": tindakan, "token": masukan["token"], **tambahan}
    if tindakan != "buat":
        data.setdefault("konfirmasi", "1")
    if "kode_id" in masukan:
        data.setdefault("kode_id", masukan["kode_id"])
    return _req(d.server, RUTE_KODE, data=data, cookie=cookie)


def _token_langsung(cookie, tindakan, domain=tautan_http.DOMAIN_TOKEN_KODE):
    """Token sah tanpa melalui halaman (untuk tes yang memang menguji gerbang sebelum halaman bisa dirender)."""
    principal = sessions.ambil_principal(cookie)
    return form_token.buat_token(principal, cookie, domain=domain, aksi="kode:" + tindakan)


def _kode_di_berkas(d) -> int:
    return baris_tabel(d.berkas, "kode_anak") or 0


def _data_berkas(d) -> tuple:
    return tuple(baris_tabel(d.berkas, t) for t in ("kode_anak", "kode_cabut", "permintaan", "putusan"))


# --- positive control dan gerbang -------------------------------------------------------------

def test_positive_control_buat_dengan_pin_tirai_dan_token_sah_menampilkan_kode_sekali(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)

    kode_status, isi, header = _kirim(dunia, cookie, "buat")

    assert kode_status == 200
    assert header.get("Cache-Control") == "no-store" and "Location" not in header
    tampil = KODE_TAMPIL.findall(isi)
    assert len(tampil) == 1
    assert _kode_di_berkas(dunia) == 1
    assert dasar.cari_kode_aktif(aturan.hash_kode(tampil[0].replace("-", ""))) is not None
    assert _data_berkas(dunia)[0] == 1


def test_sakelar_mati_post_identik_rute_tak_dikenal_dan_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    dunia.monkeypatch.delenv("DAFTAR_AKUN_ANAK")
    data = {"tindakan": "buat", "token": "1.x"}

    hasil = _req(dunia.server, RUTE_KODE, data=data, cookie=cookie)
    asing = _req(dunia.server, "/murid/tidak-ada", data=data, cookie=cookie)

    # Rute murid tak dikenal dengan sesi cookie dijawab 401 di permukaan ini (bukan 404); tes mengunci bentuk yang sama.
    assert hasil[0] == asing[0] == 401 and hasil[:2] == asing[:2]
    assert not dunia.berkas.exists()


def test_paket_belajar_mati_post_identik_rute_tak_dikenal_dan_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    dunia.monkeypatch.delenv("PAKET_BELAJAR")
    data = {"tindakan": "buat", "token": "1.x"}

    hasil = _req(dunia.server, RUTE_KODE, data=data, cookie=cookie)
    asing = _req(dunia.server, "/murid/tidak-ada", data=data, cookie=cookie)

    assert hasil[:2] == asing[:2]
    assert not dunia.berkas.exists()


def test_tanpa_pin_post_ditolak_403_tanpa_efek(dunia):
    cookie = _login(dunia.server, "raka-m", SANDI_A)
    token = _token_langsung(cookie, "buat")

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)

    assert kode_status == 403
    assert "Pasang PIN" in isi and KODE_TAMPIL.search(isi) is None
    assert not dunia.berkas.exists()


def test_tirai_tertutup_post_ditolak_403_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _login(dunia.server, "raka-m", SANDI_A)
    token = _token_langsung(cookie, "buat")

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)

    assert kode_status == tirai_aksi.KODE_TERTUTUP
    assert tirai_aksi.COPY_TERTUTUP in isi
    assert not dunia.berkas.exists()


def test_basic_tanpa_cookie_tidak_bisa_membuat_kode(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    token = form_token.buat_token(dunia.akun_a, None, domain=tautan_http.DOMAIN_TOKEN_KODE, aksi="kode:buat")

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token},
                               basic=("raka-m", SANDI_A))

    assert kode_status == tirai_aksi.KODE_TERTUTUP
    assert tirai_aksi.COPY_TERTUTUP in isi
    assert not dunia.berkas.exists()


def test_anonim_post_ditolak_401_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": "1.x"})

    assert kode_status == 401 and "Perlu masuk" in isi
    assert not dunia.berkas.exists()


@pytest.mark.parametrize("varian", ["token_salah", "aksi_lain", "domain_guru", "bentuk_rusak"])
def test_token_salah_aksi_lain_atau_domain_lain_ditolak_403_tanpa_efek(dunia, varian):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    if varian == "token_salah":
        token = "1.0000"
    elif varian == "aksi_lain":
        token = _token_langsung(cookie, "cabut")
    elif varian == "domain_guru":
        token = _token_langsung(cookie, "buat", domain=b"tautan-guru-form-v1:")
    else:
        token = "bukan-token-sama-sekalié"
    sebelum = _data_berkas(dunia)

    kode_status, _, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)

    assert kode_status == 403
    assert _data_berkas(dunia) == sebelum


def test_token_sah_tetapi_tindakan_berbeda_ditolak_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    token_buat = _token_langsung(cookie, "buat")

    kode_status, _, _ = _req(dunia.server, RUTE_KODE,
                             data={"tindakan": "ganti", "konfirmasi": "1", "kode_id": "1", "token": token_buat}, cookie=cookie)

    assert kode_status == 403
    assert not dunia.berkas.exists()


def test_form_tidak_sah_ditolak_400_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    token = _token_langsung(cookie, "buat")

    kode_status, _, _ = _req(dunia.server, RUTE_KODE,
                             data={"tindakan": "buat", "kode_id": "1", "token": token}, cookie=cookie)

    assert kode_status == 400
    assert not dunia.berkas.exists()


def test_siswa_id_palsu_dari_form_ditolak_dan_anak_lain_tidak_tersentuh(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    _pasang_pin(dunia, dunia.b, PIN_B)
    cookie_a = _buka_tirai(dunia)
    token = _token_langsung(cookie_a, "buat")

    kode_status, _, _ = _req(dunia.server, RUTE_KODE,
                             data={"tindakan": "buat", "token": token, "siswa_id": str(dunia.b)}, cookie=cookie_a)

    assert kode_status == 400
    assert not dunia.berkas.exists()
    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie_a)
    assert kode_status == 200 and KODE_TAMPIL.search(isi)
    assert kode.kode_aktif(dunia.akun_b.id_akun, dunia.b) is None
    assert kode.kode_aktif(dunia.akun_a.id_akun, dunia.a) is not None


def test_murid_lain_hanya_memengaruhi_anaknya_sendiri(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    _pasang_pin(dunia, dunia.b, PIN_B)
    cookie_a = _buka_tirai(dunia)
    cookie_b = _buka_tirai(dunia, "dina-m", SANDI_B, PIN_B)
    token_a = _token_langsung(cookie_a, "buat")

    kode_status, _, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token_a}, cookie=cookie_b)
    assert kode_status == 403 and not dunia.berkas.exists()

    kode_status, isi, _ = _kirim(dunia, cookie_b, "buat")
    assert kode_status == 200
    assert dasar.cari_kode_aktif(aturan.hash_kode(KODE_TAMPIL.findall(isi)[0].replace("-", ""))) is not None
    assert kode.kode_aktif(dunia.akun_b.id_akun, dunia.b) is not None
    assert kode.kode_aktif(dunia.akun_a.id_akun, dunia.a) is None


# --- buat, ganti, cabut -----------------------------------------------------------------------

def test_buat_menampilkan_kode_sekali_lalu_halaman_hanya_memuat_tanggal_dan_peran(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)

    kode_status, isi, _ = _kirim(dunia, cookie, "buat")
    kode_tampil = KODE_TAMPIL.findall(isi)[0]
    halaman = _req(dunia.server, RUTE, cookie=cookie)[1]

    assert kode_status == 200 and "Catat sekarang" in isi
    assert kode_tampil not in halaman
    assert kode_tampil.replace("-", "") not in halaman
    assert TANGGAL_KODE.search(halaman) and "dibuat oleh Ayah/Bunda" in halaman
    assert "akun_" not in halaman
    kartu = halaman.split('id="ortu-kode-guru"')[1].split("</section>")[0].lower()
    assert not [kata for kata in KATA_TERLARANG_ORTU if kata in kartu]


def test_kirim_ulang_buat_persis_sama_tidak_membuat_kode_kedua(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    isi = _req(dunia.server, RUTE, cookie=cookie)[1]
    token = _form_kode(isi, "buat")["token"]
    sukses = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)
    sebelum = _data_berkas(dunia)

    ulang = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)

    assert sukses[0] == 200 and ulang[0] == 409
    assert KODE_TAMPIL.search(ulang[1]) is None
    assert _data_berkas(dunia) == sebelum


def test_ganti_mematikan_kode_lama_dan_kirim_ulang_tidak_mengubah_apa_pun(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    kode_lama = KODE_TAMPIL.findall(_kirim(dunia, cookie, "buat")[1])[0]
    isi = _req(dunia.server, RUTE, cookie=cookie)[1]
    form = _form_kode(isi, "ganti")
    data = {"tindakan": "ganti", "konfirmasi": "1", "kode_id": form["kode_id"], "token": form["token"]}
    sukses = _req(dunia.server, RUTE_KODE, data=data, cookie=cookie)
    sebelum = _data_berkas(dunia)

    ulang = _req(dunia.server, RUTE_KODE, data=data, cookie=cookie)

    assert sukses[0] == 200
    kode_baru = KODE_TAMPIL.findall(sukses[1])[0]
    assert kode_baru != kode_lama
    assert kode_lama not in _req(dunia.server, RUTE, cookie=cookie)[1]
    assert dasar.cari_kode_aktif(aturan.hash_kode(kode_lama.replace("-", ""))) is None
    assert ulang[0] == 409 and KODE_TAMPIL.search(ulang[1]) is None
    assert _data_berkas(dunia) == sebelum
    assert sebelum[1] == 1


def test_dua_tab_ganti_dengan_kode_id_sama_yang_kedua_basi_tanpa_efek(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    _kirim(dunia, cookie, "buat")
    tab_satu = _form_kode(_req(dunia.server, RUTE, cookie=cookie)[1], "ganti")
    tab_dua = _form_kode(_req(dunia.server, RUTE, cookie=cookie)[1], "ganti")
    _req(dunia.server, RUTE_KODE, data={"tindakan": "ganti", "konfirmasi": "1", "kode_id": tab_satu["kode_id"],
                                        "token": tab_satu["token"]}, cookie=cookie)
    sebelum = _data_berkas(dunia)

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE,
                               data={"tindakan": "ganti", "konfirmasi": "1", "kode_id": tab_dua["kode_id"],
                                     "token": tab_dua["token"]}, cookie=cookie)

    assert kode_status == 409 and KODE_TAMPIL.search(isi) is None
    assert _data_berkas(dunia) == sebelum


def test_cabut_lalu_kirim_ulang_tidak_mencabut_kedua_kali(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    _kirim(dunia, cookie, "buat")
    isi = _req(dunia.server, RUTE, cookie=cookie)[1]
    form = _form_kode(isi, "cabut")
    data = {"tindakan": "cabut", "konfirmasi": "1", "kode_id": form["kode_id"], "token": form["token"]}

    pertama = _req(dunia.server, RUTE_KODE, data=data, cookie=cookie)
    kedua = _req(dunia.server, RUTE_KODE, data=data, cookie=cookie)

    assert pertama[0] == 200 and KODE_TAMPIL.search(pertama[1]) is None
    assert kedua[0] == 409
    assert baris_tabel(dunia.berkas, "kode_cabut") == 1
    assert "Belum ada kode aktif" in _req(dunia.server, RUTE, cookie=cookie)[1]


def test_ganti_dengan_kode_id_tidak_sah_ditolak_400(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    _kirim(dunia, cookie, "buat")
    token = _form_kode(_req(dunia.server, RUTE, cookie=cookie)[1], "ganti")["token"]

    for kode_id in ("abc", "0", "-1", ""):
        kode_status, _, _ = _req(dunia.server, RUTE_KODE,
                                 data={"tindakan": "ganti", "konfirmasi": "1", "kode_id": kode_id, "token": token}, cookie=cookie)
        assert kode_status == 400, kode_id
    assert baris_tabel(dunia.berkas, "kode_anak") == 1


def test_anak_dihapus_buat_dan_ganti_ditolak_cabut_tetap_bisa(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    _kirim(dunia, cookie, "buat")
    with dunia.server.buka() as kon:
        kon.execute("UPDATE siswa SET nama = ? WHERE id = ?", ("Dihapus-sintetis", dunia.a))
        kon.commit()
    sebelum = _data_berkas(dunia)
    isi = _req(dunia.server, RUTE, cookie=cookie)[1]
    form_ganti = _form_kode(isi, "ganti")

    ganti = _req(dunia.server, RUTE_KODE,
                 data={"tindakan": "ganti", "konfirmasi": "1", "kode_id": form_ganti["kode_id"], "token": form_ganti["token"]},
                 cookie=cookie)
    assert ganti[0] == 409 and halaman_kode.TEKS_ANAK in ganti[1] and KODE_TAMPIL.search(ganti[1]) is None
    assert _data_berkas(dunia) == sebelum

    cabut = _req(dunia.server, RUTE_KODE,
                 data={"tindakan": "cabut", "konfirmasi": "1", "kode_id": form_ganti["kode_id"],
                       "token": _form_kode(isi, "cabut")["token"]}, cookie=cookie)
    assert cabut[0] == 200
    assert baris_tabel(dunia.berkas, "kode_cabut") == 1

    buat = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": _token_langsung(cookie, "buat")},
                cookie=cookie)
    assert buat[0] == 409 and halaman_kode.TEKS_ANAK in buat[1] and KODE_TAMPIL.search(buat[1]) is None
    assert baris_tabel(dunia.berkas, "kode_anak") == 1


def test_kartu_gagal_baca_tidak_menjatuhkan_halaman_orang_tua(dunia, monkeypatch):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    _kirim(dunia, cookie, "buat")
    monkeypatch.setattr(kode, "kode_aktif", _meledak)

    kode_status, isi, _ = _req(dunia.server, RUTE, cookie=cookie)

    assert kode_status == 200
    assert halaman_kode.COPY_TAK_TERBACA in isi and FRAGMEN_KARTU in isi
    assert RUTE_KODE not in isi and "name=\"token\"" not in isi.split(FRAGMEN_KARTU)[1].split("</section>")[0]


def _meledak(*_args, **_kwargs):
    raise ValueError("kode tidak terbaca (sintetis)")


# --- kartu di halaman orang tua ---------------------------------------------------------------

def test_kartu_tersembunyi_tanpa_pin_tirai_tertutup_atau_sakelar_mati(dunia):
    cookie = _login(dunia.server, "raka-m", SANDI_A)
    tanpa_pin = _req(dunia.server, RUTE, cookie=cookie)[1]
    _pasang_pin(dunia, dunia.a, PIN_A)
    tirai_tertutup = _req(dunia.server, RUTE, cookie=cookie)[1]
    cookie_buka = _buka_tirai(dunia)
    dunia.monkeypatch.delenv("PAKET_BELAJAR")
    sakelar_mati = _req(dunia.server, RUTE, cookie=cookie_buka)[1]

    assert FRAGMEN_KARTU not in tanpa_pin
    assert FRAGMEN_KARTU not in tirai_tertutup and "Masukkan PIN" in tirai_tertutup
    assert FRAGMEN_KARTU not in sakelar_mati


def test_atur_pin_gagal_saat_tirai_terbuka_tetap_render_dengan_kartu(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)

    kode_status, isi, _ = _req(dunia.server, RUTE_PIN_ATUR,
                               data={"pin": "1234", "pin_ulang": "9999"}, cookie=cookie)

    assert kode_status == 400
    assert FRAGMEN_KARTU in isi and "Belum ada kode aktif" in isi


def test_kode_tidak_pernah_masuk_log(dunia, caplog):
    caplog.set_level(logging.DEBUG)
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)

    kode_status, isi, _ = _kirim(dunia, cookie, "buat")
    kode_tampil = KODE_TAMPIL.findall(isi)[0]

    assert kode_status == 200
    assert kode_tampil not in caplog.text and kode_tampil.replace("-", "") not in caplog.text


# --- peran non-murid, PIN gagal dibaca, domain token, dan pencatat -----------------------------

def _sesi_non_murid(d, peran: str) -> str:
    """Cookie sesi guru bawaan ServerUji, atau akun pengelola (peran admin) yang dibuat untuk tes ini."""
    if peran == "guru":
        return _login(d.server, NAMA_GURU, SANDI_GURU)
    auth.tambah_akun_dan_principal(NAMA_PENGELOLA, SANDI_PENGELOLA, "admin")
    return _login(d.server, NAMA_PENGELOLA, SANDI_PENGELOLA)


def _baris_terakhir(path, sql: str) -> tuple:
    """Satu baris dari DB tautan lewat mode ro; koneksi selalu ditutup (ResourceWarning dianggap galat)."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as kon:
        return kon.execute(sql).fetchone()


def _meledak_baca_pin(*_args, **_kwargs):
    raise sqlite3.OperationalError("database terkunci (sintetis)")


@pytest.mark.parametrize("peran", ["guru", "admin"])
@pytest.mark.parametrize("token_asal", ["palsu", "sah_untuk_sesi"])
def test_sesi_non_murid_post_ditolak_401_identik_anonim_tanpa_efek(dunia, peran, token_asal):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _sesi_non_murid(dunia, peran)
    token = "1.x" if token_asal == "palsu" else _token_langsung(cookie, "buat")
    anonim = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": "1.x"})

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)

    assert sessions.ambil_principal(cookie).peran == peran
    assert kode_status == 401 and "Perlu masuk" in isi
    assert (kode_status, isi) == anonim[:2]
    assert not dunia.berkas.exists()


def test_pin_tak_terbaca_fail_closed_403_belum_pin_tanpa_efek(dunia, monkeypatch):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    token = _token_langsung(cookie, "buat")
    monkeypatch.setattr(tautan_http, "pin_store", SimpleNamespace(ada_pin=_meledak_baca_pin))
    monkeypatch.setattr(tirai_aksi, "tertutup", lambda *_args, **_kwargs: False)

    kode_status, isi, _ = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token}, cookie=cookie)

    assert kode_status == 403 and "Pasang PIN" in isi
    assert tirai_aksi.COPY_TERTUTUP not in isi and KODE_TAMPIL.search(isi) is None
    assert not dunia.berkas.exists()


@pytest.mark.parametrize("domain", [b"pesanan-form-v1:", b"tautan-guru-form-v1:"])
def test_token_domain_lain_untuk_buat_ditolak_403_lalu_domain_kode_sah(dunia, domain):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    token_asing = _token_langsung(cookie, "buat", domain=domain)

    asing = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token_asing}, cookie=cookie)

    assert asing[0] == 403
    assert not dunia.berkas.exists()
    token_sah = _token_langsung(cookie, "buat", domain=tautan_http.DOMAIN_TOKEN_KODE)
    sah = _req(dunia.server, RUTE_KODE, data={"tindakan": "buat", "token": token_sah}, cookie=cookie)
    assert sah[0] == 200 and KODE_TAMPIL.search(sah[1])


def test_buat_dan_ganti_mencatat_oleh_dan_peran_dari_sesi(dunia):
    _pasang_pin(dunia, dunia.a, PIN_A)
    cookie = _buka_tirai(dunia)
    akun = dunia.akun_a.id_akun

    buat = _kirim(dunia, cookie, "buat")

    assert buat[0] == 200
    assert _baris_terakhir(dunia.berkas, SQL_KODE_TERAKHIR) == (akun, akun, "orang_tua")
    form = _form_kode(_req(dunia.server, RUTE, cookie=cookie)[1], "ganti")
    ganti = _req(dunia.server, RUTE_KODE,
                 data={"tindakan": "ganti", "konfirmasi": "1", "kode_id": form["kode_id"], "token": form["token"]}, cookie=cookie)

    assert ganti[0] == 200
    assert _baris_terakhir(dunia.berkas, SQL_KODE_TERAKHIR) == (akun, akun, "orang_tua")
    assert _baris_terakhir(dunia.berkas, SQL_CABUT_TERAKHIR) == (akun, "orang_tua")

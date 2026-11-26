"""Blok "Kode anak untuk guru" di detail order Paket Belajar admin dan `POST /admin/kelas/kode-anak` (Fase 3b-5).

Data sepenuhnya sintetis (akun, anak, dan order di tmp_path). Positive control dulu: buat yang sah harus berhasil,
supaya tiap tes penolakan membuktikan sesuatu. Efek (atau ketiadaannya) dibuktikan dari isi DB tautan dan respons.
"""
from __future__ import annotations

import html
import http.cookies
import json
import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

import admin_kode_anak_http as akh
import admin_kode_anak_pages as akp
import admin_store
import auth
import form_token
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_kode as kode
import kelas_kit
import kelas_store as store
import paket_belajar_katalog as katalog
import sessions
from cek_http_kit import (  # noqa: F401
    AKUN_ADMIN, AKUN_A, AKUN_MURID, ambil_token, id_akun, minta_mentah, server, tambah_anak,
)
from guru_tautan_kit import (
    JALUR_TAUTAN, KINI, KODE, LOGIN_ANAK, SANDI_ANAK, baris_tabel, hapus_keluarga_sintetis, keadaan_tautan,
    siapkan_db_tautan, siapkan_kelompok_dan_order, tambah_murid,
)
from harian_kit import jam  # noqa: F401

RUTE_DETAIL = "/admin/kelas/verifikasi"
RUTE_KODE = akp.RUTE_KODE
RUTE_TAK_ADA = "/admin/tidak-ada"
ORDER_TAK_ADA = "kor_" + "0" * 32  # id order Paket Belajar (kelas_dasar: kor_ + 32 hex)
DOMAIN_ORANG_TUA = b"kode-anak-form-v1:"
POLA_KODE_TAMPIL = re.compile(r"\b[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}\b")
POLA_FORM = re.compile(r'<form method="post" action="/admin/kelas/kode-anak"([^>]*)>(.*?)</form>', re.S)
POLA_ISIAN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)">')
POLA_FORM_TEMA = re.compile(r'<form class="admin-tema".*?</form>', re.S)
SQL_KODE_TERAKHIR = "SELECT akun_id, siswa_id, oleh, peran FROM kode_anak ORDER BY id DESC LIMIT 1"
SQL_CABUT_TERAKHIR = "SELECT oleh, peran FROM kode_cabut ORDER BY id DESC LIMIT 1"


@pytest.fixture
def dunia(server, tmp_path, monkeypatch):
    berkas = siapkan_db_tautan(tmp_path, monkeypatch)
    kondisi = siapkan_kelompok_dan_order(server)
    return SimpleNamespace(server=server, berkas=berkas, kondisi=kondisi, order=_order_anak(kondisi.siswa_id),
                           cookie=_login_admin(server), admin=id_akun(AKUN_ADMIN))


# --- pembantu ---------------------------------------------------------------------------------

def _login_admin(server) -> str:
    kode_status, _isi, tajuk = minta_mentah(server, "/masuk", None, {"nama": AKUN_ADMIN[0], "sandi": AKUN_ADMIN[1]})
    assert kode_status == 303
    return http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value


def _order_anak(siswa_id: int) -> str:
    with store.buka(admin_store.BAWAAN) as kon:
        return kon.execute("SELECT id FROM kelas_order WHERE siswa_id=?", (siswa_id,)).fetchone()[0]


def _sql(berkas: Path, perintah: str):
    with closing(sqlite3.connect(Path(berkas).resolve().as_uri() + "?mode=ro", uri=True)) as kon:
        return kon.execute(perintah).fetchone()


def _cookie(d) -> dict:
    return {"Cookie": "osn_sesi=" + d.cookie}


def _detail(d):
    return minta_mentah(d.server, RUTE_DETAIL + "?order=" + d.order, None, None, _cookie(d))


def _isi_detail(d) -> str:
    kode_status, isi, _tajuk = _detail(d)
    assert kode_status == 200
    return isi


def _form(isi: str, tindakan: str) -> dict:
    for _atribut, badan in POLA_FORM.findall(isi):
        isian = {nama: html.unescape(nilai) for nama, nilai in POLA_ISIAN.findall(badan)}
        if isian.get("tindakan") == tindakan:
            return isian
    raise AssertionError("form %s tidak ada" % tindakan)


def _form_dari_detail(d, tindakan: str) -> dict:
    return _form(_isi_detail(d), tindakan)


def _kirim(d, data: dict):
    return minta_mentah(d.server, RUTE_KODE, None, data, _cookie(d))


def _buat(d):
    return _kirim(d, _form_dari_detail(d, "buat"))


def _token_admin(d, tindakan: str, order_id: str, domain: bytes = akh.DOMAIN_TOKEN_ADMIN) -> str:
    principal = sessions.ambil_principal(d.cookie)
    return form_token.buat_token(principal, d.cookie, domain=domain, aksi="kode:%s:%s" % (tindakan, order_id))


def _keadaan(d) -> tuple:
    return tuple(keadaan_tautan(d.berkas).values())


def _respons(hasil) -> tuple:
    """Bagian respons yang harus identik untuk penolakan: status, Content-Type, Content-Length, badan."""
    kode_status, isi, tajuk = hasil
    return kode_status, tajuk.get("Content-Type"), tajuk.get("Content-Length"), isi


def _tanpa_tema(hasil) -> tuple:
    """Respons tanpa formulir tema admin: tinjauan tema ditandatangani per respons, jadi berbeda antar-permintaan."""
    kode_status, ctype, clen, isi = _respons(hasil)
    return kode_status, ctype, clen, POLA_FORM_TEMA.sub("", isi)


def _referensi_404(d, akun, data, headers=None):
    """Jawaban rute admin tak dikenal untuk identitas yang sama: acuan 404 identik."""
    return _respons(minta_mentah(d.server, RUTE_TAK_ADA, akun, data, headers))


def _kode_guru(d, kode_tampil: str) -> tuple:
    """Jawaban guru memasukkan `kode_tampil` ke kelompoknya; dipakai untuk membandingkan kegagalan."""
    token = ambil_token(d.server, AKUN_A, f"/guru/kelas/{d.kondisi.kelompok_id}")
    return _respons(minta_mentah(d.server, JALUR_TAUTAN.format(klp=d.kondisi.kelompok_id), AKUN_A,
                                 data={"kode": kode_tampil, "token": token}))


# --- positive control dan isi blok ------------------------------------------------------------

def test_positive_control_buat_menampilkan_kode_sekali_dan_mencatat_admin(dunia):
    kode_status, isi, tajuk = _buat(dunia)

    assert kode_status == 200
    assert tajuk.get("Cache-Control") == "no-store" and "Location" not in tajuk
    tampil = POLA_KODE_TAMPIL.findall(isi)
    assert len(tampil) == 1
    assert dasar.cari_kode_aktif(aturan.hash_kode(tampil[0].replace("-", ""))) is not None
    assert _sql(dunia.berkas, SQL_KODE_TERAKHIR) == (
        dunia.kondisi.murid_id, dunia.kondisi.siswa_id, dunia.admin, aturan.PERAN_ADMIN)


def test_blok_tanpa_kode_menampilkan_form_buat_dan_detail_tidak_membuat_berkas(dunia):
    isi = _isi_detail(dunia)

    assert "Belum ada kode aktif." in isi
    assert _form(isi, "buat")["order_id"] == dunia.order
    assert not dunia.berkas.exists()


def test_detail_setelah_buat_tidak_memuat_kode_maupun_id_mentah(dunia):
    kode_tampil = POLA_KODE_TAMPIL.findall(_buat(dunia)[1])[0]

    isi = _isi_detail(dunia)

    assert kode_tampil not in isi and kode_tampil.replace("-", "") not in isi
    assert dunia.kondisi.murid_id not in isi
    assert "Kode aktif sejak" in isi and "dibuat oleh admin" in isi
    assert "Ganti kode anak ini?" in isi and "Cabut semua kode anak ini?" in isi


def test_kode_tidak_pernah_masuk_log(dunia, caplog):
    caplog.set_level(logging.DEBUG)
    kode_tampil = POLA_KODE_TAMPIL.findall(_buat(dunia)[1])[0]

    _isi_detail(dunia)

    assert kode_tampil not in caplog.text and kode_tampil.replace("-", "") not in caplog.text


# --- akses dan tanpa efek ---------------------------------------------------------------------

@pytest.mark.parametrize("akun", [None, AKUN_A, AKUN_MURID], ids=["anonim", "guru", "murid"])
def test_non_admin_mendapat_404_identik_dengan_rute_admin_lain_tanpa_efek(dunia, akun):
    data = {"tindakan": "buat", "order_id": dunia.order, "token": "1.x"}
    sebelum = _keadaan(dunia)

    hasil = _respons(minta_mentah(dunia.server, RUTE_KODE, akun, data))

    assert hasil[0] == 404
    assert hasil == _referensi_404(dunia, akun, data)
    assert _keadaan(dunia) == sebelum and not dunia.berkas.exists()


def test_token_salah_domain_lain_aksi_lain_atau_order_lain_ditolak_403_tanpa_efek(dunia):
    form = _form_dari_detail(dunia, "buat")
    sebelum = _keadaan(dunia)
    tokens = {
        "salah": "1.deadbeef",
        "domain_orang_tua": _token_admin(dunia, "buat", dunia.order, domain=DOMAIN_ORANG_TUA),
        "aksi_lain": _token_admin(dunia, "ganti", dunia.order),
        "order_lain": _token_admin(dunia, "buat", ORDER_TAK_ADA),
    }

    for nama, token in tokens.items():
        kode_status, isi, _tajuk = _kirim(dunia, form | {"token": token})
        assert kode_status == 403, nama
        assert not POLA_KODE_TAMPIL.search(isi), nama
    assert _keadaan(dunia) == sebelum and not dunia.berkas.exists()


def test_admin_basic_tanpa_sesi_berkuki_melihat_baca_saja_dan_post_403(dunia):
    token = form_token.buat_token(sessions.principal_basic(*AKUN_ADMIN), None,
                                  domain=akh.DOMAIN_TOKEN_ADMIN, aksi="kode:buat:" + dunia.order)

    kode_status, isi, _tajuk = minta_mentah(dunia.server, RUTE_DETAIL + "?order=" + dunia.order, AKUN_ADMIN)
    post = minta_mentah(dunia.server, RUTE_KODE, AKUN_ADMIN,
                        {"tindakan": "buat", "order_id": dunia.order, "token": token})

    assert kode_status == 200 and akp.COPY_TANPA_SESI in isi and 'name="token"' not in isi
    assert post[0] == 403 and not dunia.berkas.exists()


# --- pemakaian ulang dan batas aturan ---------------------------------------------------------

def test_kirim_ulang_form_buat_yang_sama_ditolak_409_tanpa_kode_kedua(dunia):
    form = _form_dari_detail(dunia, "buat")
    assert _kirim(dunia, form)[0] == 200
    sebelum = _keadaan(dunia)

    kode_status, isi, tajuk = _kirim(dunia, form)

    assert kode_status == 409 and not POLA_KODE_TAMPIL.search(isi)
    assert "Location" not in tajuk and _keadaan(dunia) == sebelum


def test_buat_ditolak_bila_sudah_ada_kode_aktif_meski_token_baru(dunia):
    assert _buat(dunia)[0] == 200
    sebelum = _keadaan(dunia)

    kode_status, isi, _tajuk = _kirim(dunia, {"tindakan": "buat", "order_id": dunia.order,
                                              "token": _token_admin(dunia, "buat", dunia.order)})

    assert kode_status == 409 and not POLA_KODE_TAMPIL.search(isi)
    assert _keadaan(dunia) == sebelum


def test_ganti_dengan_kode_id_basi_ditolak_409_tanpa_efek(dunia):
    _buat(dunia)
    kode_lama = _form_dari_detail(dunia, "ganti")["kode_id"]
    assert _kirim(dunia, _form_dari_detail(dunia, "ganti"))[0] == 200
    sebelum = _keadaan(dunia)

    kode_status, isi, _tajuk = _kirim(dunia, _form_dari_detail(dunia, "ganti") | {"kode_id": kode_lama})

    assert kode_status == 409 and not POLA_KODE_TAMPIL.search(isi)
    assert _keadaan(dunia) == sebelum


def test_ganti_mematikan_kode_lama_dan_guru_hanya_menerima_kegagalan_identik(dunia, jam):
    kode_lama = POLA_KODE_TAMPIL.findall(_buat(dunia)[1])[0]

    kode_status, isi, tajuk = _kirim(dunia, _form_dari_detail(dunia, "ganti"))
    kode_baru = POLA_KODE_TAMPIL.findall(isi)

    assert kode_status == 200 and tajuk.get("Cache-Control") == "no-store" and len(kode_baru) == 1
    assert kode_baru[0] != kode_lama
    gagal_salah = _kode_guru(dunia, "ZZZZ-ZZZZ-ZZZZ-ZZZZ")
    assert _kode_guru(dunia, kode_lama) == gagal_salah
    assert _kode_guru(dunia, kode_baru[0]) != gagal_salah


# --- cabut, dan anak yang sudah dihapus -------------------------------------------------------

def test_cabut_tetap_bisa_untuk_anak_dihapus_tetapi_ganti_dan_buat_ditolak(dunia):
    _buat(dunia)
    form_ganti = _form_dari_detail(dunia, "ganti")
    form_cabut = _form_dari_detail(dunia, "cabut")
    hapus_keluarga_sintetis(AKUN_A[0])
    sebelum_ganti = _keadaan(dunia)

    kode_ganti, isi_ganti, _tajuk = _kirim(dunia, form_ganti)
    assert kode_ganti == 409 and not POLA_KODE_TAMPIL.search(isi_ganti)
    assert _keadaan(dunia) == sebelum_ganti

    kode_cabut, _isi, _tajuk = _kirim(dunia, form_cabut)
    assert kode_cabut == 200
    assert _sql(dunia.berkas, SQL_CABUT_TERAKHIR) == (dunia.admin, aturan.PERAN_ADMIN)

    assert _tindakan_tersedia(_isi_detail(dunia)) == set()  # anak tak aktif dan tanpa kode: tanpa formulir sama sekali
    data_buat = {"tindakan": "buat", "order_id": dunia.order, "token": _token_admin(dunia, "buat", dunia.order)}
    kode_buat, isi_buat, _tajuk = _kirim(dunia, data_buat)
    assert kode_buat == 409 and not POLA_KODE_TAMPIL.search(isi_buat)


def test_admin_mencabut_kode_buatan_orang_tua_dan_blok_menampilkan_pembuatnya(dunia):
    kode.buat_kode_baru(dunia.kondisi.murid_id, dunia.kondisi.siswa_id, oleh=dunia.kondisi.murid_id,
                        peran=aturan.PERAN_ORANG_TUA, pada=KINI)
    isi = _isi_detail(dunia)
    assert "dibuat oleh orang tua" in isi

    kode_status, _isi, _tajuk = _kirim(dunia, _form(isi, "cabut"))

    assert kode_status == 200
    assert kode.kode_aktif(dunia.kondisi.murid_id, dunia.kondisi.siswa_id) is None
    assert _sql(dunia.berkas, SQL_CABUT_TERAKHIR) == (dunia.admin, aturan.PERAN_ADMIN)


# --- isian dan galat ----------------------------------------------------------------------------

def test_isian_asing_atau_order_tak_sah_atau_ganti_tanpa_kode_id_ditolak_400(dunia):
    form = _form_dari_detail(dunia, "buat")
    sebelum = _keadaan(dunia)

    asing = _kirim(dunia, form | {"akun_id": dunia.kondisi.murid_id})
    order_rusak = _kirim(dunia, form | {"order_id": "ord_zz"})
    ganti_tanpa_id = _kirim(dunia, {"tindakan": "ganti", "order_id": dunia.order, "token": form["token"]})

    assert asing[0] == 400 and order_rusak[0] == 400 and ganti_tanpa_id[0] == 400
    assert _keadaan(dunia) == sebelum


def test_order_tidak_ada_dijawab_404_identik_rute_tak_dikenal(dunia):
    data = {"tindakan": "buat", "order_id": ORDER_TAK_ADA, "token": _token_admin(dunia, "buat", ORDER_TAK_ADA)}

    hasil = _respons(_kirim(dunia, data))

    assert hasil == _referensi_404(dunia, None, data, _cookie(dunia))
    assert not dunia.berkas.exists()


def test_galat_tulis_dijawab_503_tanpa_kode(dunia, monkeypatch):
    def gagal(*_args, **_kwargs):
        raise dasar.GalatTautan("tulis gagal (sintetis)")

    monkeypatch.setattr(akh.kode, "buat_kode_baru", gagal)

    kode_status, isi, _tajuk = _buat(dunia)

    assert kode_status == 503 and not POLA_KODE_TAMPIL.search(isi)
    assert not dunia.berkas.exists()


def _tambah_order_private(server):
    """Order Private lunas milik anak sintetis lain. Blok dan POST untuk order ini harus tak tersedia."""
    siswa = tambah_anak(server, "Anak Sintetis Privat", AKUN_A[0], None)
    murid = tambah_murid("anak-privat", SANDI_ANAK, siswa_id=siswa)
    with store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        # n=2: sha256 bukti harus unik antar order (kelas_kit.sha(n)); order Mini di dunia memakai n=1.
        kelas_kit.lunas(kon, siswa, katalog.KODE_PRIVATE, n=2, akun=murid["id_akun"], sekarang=KINI)
        kon.commit()
    return _order_anak(siswa)


# --- ganti: kode_id tidak sah ------------------------------------------------------------------

@pytest.mark.parametrize("kode_id", ["abc", "0", "00", "-1", " 1", "1" * 19, ""],
                         ids=["huruf", "nol", "nol-nol", "negatif", "spasi", "terlalu-panjang", "kosong"])
def test_ganti_dengan_kode_id_tidak_sah_ditolak_400_tanpa_efek(dunia, kode_id):
    _buat(dunia)
    aktif = kode.kode_aktif(dunia.kondisi.murid_id, dunia.kondisi.siswa_id)["id"]
    sebelum = _keadaan(dunia)

    kode_status, isi, _tajuk = _kirim(dunia, _form_dari_detail(dunia, "ganti") | {"kode_id": kode_id})

    assert kode_status == 400 and not POLA_KODE_TAMPIL.search(isi)
    assert _keadaan(dunia) == sebelum
    assert kode.kode_aktif(dunia.kondisi.murid_id, dunia.kondisi.siswa_id)["id"] == aktif


# --- cabut: idempoten, tanpa kode_id ---------------------------------------------------------------

def test_form_cabut_tidak_membawa_kode_id_dan_cabut_yang_membawanya_ditolak_400(dunia):
    _buat(dunia)
    form = _form_dari_detail(dunia, "cabut")
    aktif = kode.kode_aktif(dunia.kondisi.murid_id, dunia.kondisi.siswa_id)["id"]
    sebelum = _keadaan(dunia)

    kode_status, _isi, _tajuk = _kirim(dunia, form | {"kode_id": str(aktif)})

    assert "kode_id" not in form
    assert kode_status == 400
    assert _keadaan(dunia) == sebelum


def test_cabut_idempoten_dua_kali_dengan_jawaban_sama_dan_tanpa_kode_kedua(dunia):
    _buat(dunia)
    form = _form_dari_detail(dunia, "cabut")

    pertama = _kirim(dunia, form)
    kedua = _kirim(dunia, form)

    assert pertama[0] == 200 and _tanpa_tema(pertama) == _tanpa_tema(kedua)
    assert "Location" not in pertama[2]
    assert baris_tabel(dunia.berkas, "kode_cabut") == 1
    assert kode.kode_aktif(dunia.kondisi.murid_id, dunia.kondisi.siswa_id) is None


def test_cabut_tanpa_kode_aktif_dijawab_200_dan_tidak_membuat_berkas(dunia):
    data = {"tindakan": "cabut", "order_id": dunia.order, "token": _token_admin(dunia, "cabut", dunia.order)}

    kode_status, isi, _tajuk = _kirim(dunia, data)

    assert kode_status == 200 and not POLA_KODE_TAMPIL.search(isi)
    assert not dunia.berkas.exists()


# --- order Private: tanpa blok, POST 404 identik ----------------------------------------------------

def test_order_private_tidak_menampilkan_blok_kode_anak(dunia):
    order_private = _tambah_order_private(dunia.server)

    kode_status, isi, _tajuk = minta_mentah(dunia.server, RUTE_DETAIL + "?order=" + order_private, None, None,
                                            _cookie(dunia))

    assert kode_status == 200
    assert akp.JUDUL_KARTU not in isi and 'id="admin-kode-anak"' not in isi


@pytest.mark.parametrize("tindakan", ["buat", "cabut"])
def test_post_order_private_404_identik_dengan_order_tak_ada(dunia, tindakan):
    order_private = _tambah_order_private(dunia.server)
    sebelum = _keadaan(dunia)
    data_private = {"tindakan": tindakan, "order_id": order_private,
                    "token": _token_admin(dunia, tindakan, order_private)}
    data_tak_ada = {"tindakan": tindakan, "order_id": ORDER_TAK_ADA,
                    "token": _token_admin(dunia, tindakan, ORDER_TAK_ADA)}

    hasil = _respons(_kirim(dunia, data_private))

    assert hasil == _respons(_kirim(dunia, data_tak_ada))
    assert hasil == _referensi_404(dunia, None, data_private, _cookie(dunia))
    assert _keadaan(dunia) == sebelum and not dunia.berkas.exists()


# --- akun anak tidak aktif atau bukan akun murid (LOW-2) ---------------------------------------

def _tindakan_tersedia(isi: str) -> set:
    """Tindakan formulir kode anak yang tampil di halaman ini. Kosong bila blok hanya baca-saja."""
    return {dict(POLA_ISIAN.findall(badan)).get("tindakan") for _atribut, badan in POLA_FORM.findall(isi)}


def _ubah_akun_murid(login: str, **kunci) -> None:
    """Ubah satu akun murid di berkas auth secara mentah. Keadaan ini tidak bisa dibuat lewat API."""
    berkas = auth.BERKAS_SANDI
    data = json.loads(berkas.read_text(encoding="utf-8"))
    for akun in data["akun"]:
        if akun["pengguna"] == login:
            akun.update(kunci)
    berkas.write_text(json.dumps(data), encoding="utf-8")


def _akun_murid_hilang(_d) -> None:
    assert auth.hapus_akun(LOGIN_ANAK)


def _akun_murid_dinonaktifkan(_d) -> None:
    _ubah_akun_murid(LOGIN_ANAK, dinonaktifkan=True)


def _anak_dianonimkan(_d) -> None:
    hapus_keluarga_sintetis(AKUN_A[0])


PERUBAHAN_ANAK_TAK_AKTIF = [
    pytest.param(_akun_murid_hilang, id="akun-murid-hilang"),
    pytest.param(_akun_murid_dinonaktifkan, id="akun-murid-nonaktif"),
    pytest.param(_anak_dianonimkan, id="anak-dianonimkan"),
]


def _tambah_order_mini_akun_guru(server) -> tuple:
    """Order Mini lunas yang `akun_id`-nya akun guru, bukan akun murid (seperti akun guru lama).

    Mengembalikan (order, siswa).
    """
    siswa = tambah_anak(server, "Anak Sintetis Gamma", AKUN_A[0], None)
    with store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_kit.lunas(kon, siswa, katalog.KODE_MINI, n=2, akun=id_akun(AKUN_A), sekarang=KINI)
        kon.commit()
    return _order_anak(siswa), siswa


def _isi_order(d, order_id: str) -> str:
    kode_status, isi, _tajuk = minta_mentah(d.server, RUTE_DETAIL + "?order=" + order_id, None, None, _cookie(d))
    assert kode_status == 200
    return isi


def test_order_akun_bukan_murid_tanpa_kode_hanya_baca_saja(dunia):
    order_guru, _siswa = _tambah_order_mini_akun_guru(dunia.server)

    isi = _isi_order(dunia, order_guru)

    assert akp.COPY_ANAK_TAK_AKTIF in isi
    assert _tindakan_tersedia(isi) == set()


def test_order_akun_bukan_murid_dengan_kode_sisa_hanya_tombol_cabut(dunia):
    order_guru, siswa = _tambah_order_mini_akun_guru(dunia.server)
    guru = id_akun(AKUN_A)
    dasar.buat_kode(akun_id=guru, siswa_id=siswa, kode_hash=aturan.hash_kode(KODE), oleh=guru,
                    peran=aturan.PERAN_ORANG_TUA, pada=KINI)  # kode sisa dari akun lama; buat lewat domain ditolak

    isi = _isi_order(dunia, order_guru)
    kode_status, _isi_hasil, _tajuk = _kirim(dunia, _form(isi, "cabut"))

    assert akp.COPY_ANAK_TAK_AKTIF in isi and _tindakan_tersedia(isi) == {"cabut"}
    assert kode_status == 200
    assert kode.kode_aktif(guru, siswa) is None


def test_post_buat_order_akun_bukan_murid_tetap_ditolak_409_tanpa_kode(dunia):
    order_guru, siswa = _tambah_order_mini_akun_guru(dunia.server)
    data = {"tindakan": "buat", "order_id": order_guru, "token": _token_admin(dunia, "buat", order_guru)}

    kode_status, isi, _tajuk = _kirim(dunia, data)

    assert kode_status == 409 and not POLA_KODE_TAMPIL.search(isi)
    assert not dunia.berkas.exists()


@pytest.mark.parametrize("perubahan", PERUBAHAN_ANAK_TAK_AKTIF)
def test_anak_tak_aktif_tanpa_kode_hanya_baca_saja_dan_post_buat_tetap_409(dunia, perubahan):
    assert _tindakan_tersedia(_isi_detail(dunia)) == {"buat"}  # kontrol positif: sebelum berubah, Buat tampil
    perubahan(dunia)
    data = {"tindakan": "buat", "order_id": dunia.order, "token": _token_admin(dunia, "buat", dunia.order)}

    isi = _isi_detail(dunia)
    kode_status, isi_post, _tajuk = _kirim(dunia, data)

    assert akp.COPY_ANAK_TAK_AKTIF in isi and _tindakan_tersedia(isi) == set()
    assert kode_status == 409 and not POLA_KODE_TAMPIL.search(isi_post)
    assert not dunia.berkas.exists()


@pytest.mark.parametrize("perubahan", PERUBAHAN_ANAK_TAK_AKTIF)
def test_anak_tak_aktif_dengan_kode_hanya_tombol_cabut_dan_cabut_tetap_jalan(dunia, perubahan):
    assert _buat(dunia)[0] == 200
    assert _tindakan_tersedia(_isi_detail(dunia)) == {"ganti", "cabut"}  # kontrol positif
    perubahan(dunia)

    isi = _isi_detail(dunia)
    kode_status, _isi_hasil, _tajuk = _kirim(dunia, _form(isi, "cabut"))

    assert akp.COPY_ANAK_TAK_AKTIF in isi and _tindakan_tersedia(isi) == {"cabut"}
    assert kode_status == 200
    assert _sql(dunia.berkas, SQL_CABUT_TERAKHIR) == (dunia.admin, aturan.PERAN_ADMIN)
    assert kode.kode_aktif(dunia.kondisi.murid_id, dunia.kondisi.siswa_id) is None


def test_galat_baca_status_anak_tampil_tak_terbaca_bukan_tak_aktif(dunia, monkeypatch):
    assert _buat(dunia)[0] == 200
    assert _tindakan_tersedia(_isi_detail(dunia)) == {"ganti", "cabut"}  # kontrol positif

    def _rusak(_path):
        raise OSError("berkas tidak bisa dibuka")

    monkeypatch.setattr(akh.guru_tautan_anak, "_baca_akun", _rusak)
    isi = _isi_detail(dunia)

    assert akp.COPY_TAK_TERBACA in isi
    assert akp.COPY_ANAK_TAK_AKTIF not in isi and _tindakan_tersedia(isi) == set()

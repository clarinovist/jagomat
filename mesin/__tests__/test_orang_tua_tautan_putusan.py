"""Persetujuan dan penolakan permintaan guru di `POST /murid/orang-tua/tautan` lewat HTTP nyata (Fase 3b-3).

Gerbang ditegakkan server: PIN terpasang, tirai terbuka, token domain `tautan-ortu-form-v1:` dengan aksi
`tautan:<permintaan_id>:<hasil>`, dan id permintaan milik anak sesi. Tiap penolakan dibuktikan TANPA efek: hash kedua
DB tidak berubah dan tidak ada penempatan. Id milik anak lain dibandingkan dengan id yang tidak ada (oracle).
Positive control dulu: setuju yang sah harus menempatkan anak, supaya setiap penolakan berarti.
Data sepenuhnya sintetis di tmp_path (DB tautan lewat `siapkan_db_tautan`, admin lewat ServerUji).
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import admin_store
import form_token
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_laju as laju
import jadwal_store as js
import kelas_kit
import orang_tua_tautan_http as tautan_http
import pin_orang_tua_store as pin_store
import sessions
import tirai_orang_tua as tirai
from cek_http_kit import AKUN_A, AKUN_B, ambil_token, id_akun, minta_mentah, server, tambah_anak  # noqa: F401
from guru_tautan_kit import (ADMIN, JALUR_TAUTAN, KINI, LOGIN_ANAK, NAMA_KELOMPOK, SANDI_ANAK, KondisiTautan,
                             baris_tabel, siapkan_db_tautan, siapkan_kelompok_dan_order, tambah_murid)
from harian_kit import jam  # noqa: F401  (fixture jam: jam sintetis tetap)
from orang_tua_kode_kit import KODE_TAMPIL, RUTE, RUTE_KODE, form_kode, login, req

PIN = "4821"
PIN_BETA = "1357"
SANDI_BETA = "sandi-anak-beta-tautan-123"
LOGIN_BETA = "anak-beta"
SANDI_GAMMA = "sandi-anak-gamma-123"
MASA_PIN = 1_800_000_000
JALUR_PUTUSAN = RUTE + "/tautan"
POLA_PUTUSAN = re.compile(r'<form method="post" action="/murid/orang-tua/tautan">(.*?)</form>', re.S)
POLA_INPUT = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)">')
DOMAIN_KODE = tautan_http.DOMAIN_TOKEN_KODE
DOMAIN_PUTUSAN = tautan_http.DOMAIN_TOKEN_PUTUSAN
ID_TAK_ADA = 987654
COPY_KONFIRMASI = "Kode yang sudah diberikan ke guru akan mati; permintaan yang menunggu dibatalkan."
JUDUL_MENUNGGU = "Permintaan guru menunggu"
JUDUL_DISETUJUI = "Permintaan disetujui"
JUDUL_DITOLAK = "Permintaan ditolak"
PESAN_PENUH = "Kelompok ini sudah penuh"
PESAN_TAK_BISA = "Permintaan ini sudah diputuskan"
COPY_BELUM_ADA = "Belum ada permintaan guru yang menunggu."
SQL_PENEMPATAN = ("SELECT p.kelompok_id FROM jadwal_penempatan AS p JOIN kelas_order AS o ON o.id = p.order_id "
                  "WHERE o.siswa_id = ? ORDER BY p.kelompok_id")


@dataclass
class Dunia:
    server: object
    kondisi: KondisiTautan
    db: Path


# --- penyiapan --------------------------------------------------------------------------------

def _siapkan(server, tmp_path, monkeypatch, *, kuota: int = 5) -> Dunia:
    db = siapkan_db_tautan(tmp_path, monkeypatch)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada-sakelar.db"))
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("PAKET_BELAJAR", "1")
    tirai._reset()
    kondisi = siapkan_kelompok_dan_order(server, kuota=kuota)
    return Dunia(server=server, kondisi=kondisi, db=db)


@pytest.fixture
def d(server, jam, tmp_path, monkeypatch):
    dunia = _siapkan(server, tmp_path, monkeypatch)
    yield dunia
    tirai._reset()


# --- bantuan HTTP -----------------------------------------------------------------------------

def _pasang_pin(server, siswa_id: int, pin: str = PIN) -> None:
    with server.buka() as kon:
        pin_store.simpan(kon, siswa_id, pin, MASA_PIN)


def _hapus_pin(server, siswa_id: int) -> None:
    with server.buka() as kon:
        pin_store.hapus(kon, siswa_id)


def _buka_tirai(server, cookie: str, pin: str = PIN) -> None:
    status, _, _ = req(server, RUTE + "/pin", data={"pin": pin}, cookie=cookie)
    assert status == 303


def _halaman(server, cookie: str) -> str:
    return req(server, RUTE, cookie=cookie)[1]


def _buat_kode(server, cookie: str) -> str:
    """Kode anak dibuat lewat halaman orang tua; mengembalikan kode bentuk tampil (dengan tanda hubung)."""
    masukan = form_kode(_halaman(server, cookie), "buat")
    status, isi, _ = req(server, RUTE_KODE, data={"tindakan": "buat", "token": masukan["token"]}, cookie=cookie)
    assert status == 200
    return KODE_TAMPIL.findall(isi)[0]


def _ajukan_guru(server, kelompok_id: str, kode_tampil: str):
    tok = ambil_token(server, AKUN_A, f"/guru/kelas/{kelompok_id}")
    return minta_mentah(server, JALUR_TAUTAN.format(klp=kelompok_id), AKUN_A,
                        data={"kode": kode_tampil, "token": tok})


def _menunggu(d: Dunia) -> list:
    return [b for b in dasar.daftar_untuk_anak(d.kondisi.murid_id, d.kondisi.siswa_id, KINI)
            if b["status"] == aturan.STATUS_MENUNGGU]


def _siapkan_permintaan(d: Dunia) -> Tuple[str, int, str]:
    """PIN dan tirai terbuka, kode dibuat, guru A mengajukan. Mengembalikan (cookie anak, id permintaan, kode)."""
    _pasang_pin(d.server, d.kondisi.siswa_id)
    cookie = login(d.server, LOGIN_ANAK, SANDI_ANAK)
    _buka_tirai(d.server, cookie)
    kode_tampil = _buat_kode(d.server, cookie)
    diajukan = _ajukan_guru(d.server, d.kondisi.kelompok_id, kode_tampil)
    assert diajukan[0] == 200 and LOGIN_ANAK in diajukan[1]
    return cookie, _menunggu(d)[0]["id"], kode_tampil


def _siapkan_anak_lain(d: Dunia) -> str:
    """Anak kedua dengan PIN dan tirai terbuka; mengembalikan cookie sesinya."""
    siswa_beta = tambah_anak(d.server, "Anak Sintetis Beta", AKUN_A[0], None)
    tambah_murid(login=LOGIN_BETA, sandi=SANDI_BETA, siswa_id=siswa_beta)
    _pasang_pin(d.server, siswa_beta, PIN_BETA)
    cookie = login(d.server, LOGIN_BETA, SANDI_BETA)
    _buka_tirai(d.server, cookie, PIN_BETA)
    return cookie


def _isi_kursi(d: Dunia) -> None:
    """Anak ketiga ditempatkan ke kelompok ini; dengan kuota 1, kursi itu penuh."""
    siswa = tambah_anak(d.server, "Anak Sintetis Gamma", AKUN_A[0], None)
    murid = tambah_murid(login="anak-gamma", sandi=SANDI_GAMMA, siswa_id=siswa)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        tagihan = kelas_kit.lunas(kon, siswa, "mini", n=2, akun=murid["id_akun"], sekarang=kelas_kit.KINI)
        js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=d.kondisi.kelompok_id, sekarang=KINI)
        kon.commit()


def _token_langsung(cookie: str, permintaan_id: int, hasil: str, *, domain: bytes = DOMAIN_PUTUSAN,
                    aksi: str = "") -> str:
    """Token sah untuk sesi itu tanpa melalui halaman (untuk tes gerbang sebelum halaman bisa dirender)."""
    principal = sessions.ambil_principal(cookie)
    return form_token.buat_token(principal, cookie, domain=domain,
                                 aksi=aksi or f"tautan:{permintaan_id}:{hasil}")


def _form_putusan(isi: str, permintaan_id: int, hasil: str) -> dict:
    for blok in POLA_PUTUSAN.findall(isi):
        masukan = dict(POLA_INPUT.findall(blok))
        if masukan.get("permintaan_id") == str(permintaan_id) and masukan.get("hasil") == hasil:
            return masukan
    return {}


def _putuskan(d: Dunia, cookie: str, permintaan_id: int, hasil: str):
    """POST putusan dengan token dari halaman yang baru dirender, seperti tombol di browser."""
    token = _form_putusan(_halaman(d.server, cookie), permintaan_id, hasil)["token"]
    return _kirim_putusan(d, cookie, permintaan_id, hasil, token)


def _kirim_putusan(d: Dunia, cookie: str, permintaan_id, hasil: str, token: str):
    return req(d.server, JALUR_PUTUSAN,
               data={"permintaan_id": str(permintaan_id), "hasil": hasil, "token": token}, cookie=cookie)


def _bentuk(jawaban) -> tuple:
    status, isi, header = jawaban
    return status, isi, header.get("Content-Type"), header.get("Content-Length"), header.get("Cache-Control")


# --- keadaan dua DB ---------------------------------------------------------------------------

def _sidik(path) -> str | None:
    berkas = Path(path)
    return hashlib.sha256(berkas.read_bytes()).hexdigest() if berkas.exists() else None


def _keadaan(d: Dunia) -> tuple:
    return _sidik(d.db), _sidik(admin_store.BAWAAN)


def _sql(path, kueri: str, parameter: tuple = ()) -> list:
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as kon:
        return [tuple(baris) for baris in kon.execute(kueri, parameter).fetchall()]


def _penempatan(siswa_id: int) -> list:
    return [b[0] for b in _sql(admin_store.BAWAAN, SQL_PENEMPATAN, (siswa_id,))]


def _ledger(d: Dunia) -> list:
    return _sql(d.db, "SELECT permintaan_id, hasil, oleh FROM putusan ORDER BY id")


# --- kartu: tampil hanya bila gerbang terbuka -------------------------------------------------

def test_kartu_tanpa_pin_tidak_menampilkan_permintaan_dan_tanpa_form_putusan(d):
    cookie, _, _ = _siapkan_permintaan(d)
    _hapus_pin(d.server, d.kondisi.siswa_id)

    isi = _halaman(d.server, cookie)

    assert JUDUL_MENUNGGU not in isi
    assert JALUR_PUTUSAN not in isi


def test_kartu_dengan_tirai_tertutup_tidak_menampilkan_permintaan(d):
    _siapkan_permintaan(d)
    cookie_tertutup = login(d.server, LOGIN_ANAK, SANDI_ANAK)

    isi = _halaman(d.server, cookie_tertutup)

    assert JUDUL_MENUNGGU not in isi
    assert JALUR_PUTUSAN not in isi


def test_kartu_tampil_permintaan_menunggu_tanpa_id_akun_anak_kelompok_atau_kode(d):
    cookie, permintaan_id, kode_tampil = _siapkan_permintaan(d)

    isi = _halaman(d.server, cookie)

    assert JUDUL_MENUNGGU in isi
    assert _form_putusan(isi, permintaan_id, "setuju")
    assert _form_putusan(isi, permintaan_id, "tolak")
    assert "<strong>guru</strong>" in isi and NAMA_KELOMPOK in isi
    assert COPY_KONFIRMASI in isi and 'name="konfirmasi"' in isi
    for rahasia in (d.kondisi.murid_id, d.kondisi.guru_id, d.kondisi.kelompok_id,
                    kode_tampil.replace("-", ""), aturan.hash_kode(kode_tampil)):
        assert rahasia not in isi


def test_kartu_tanpa_permintaan_menampilkan_copy_belum_ada(d):
    _pasang_pin(d.server, d.kondisi.siswa_id)
    cookie = login(d.server, LOGIN_ANAK, SANDI_ANAK)
    _buka_tirai(d.server, cookie)

    isi = _halaman(d.server, cookie)

    assert COPY_BELUM_ADA in isi
    assert JALUR_PUTUSAN not in isi


# --- gerbang: ditolak tanpa efek --------------------------------------------------------------

def test_setuju_tanpa_pin_ditolak_403_tanpa_efek(d):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    token = _token_langsung(cookie, permintaan_id, "setuju")
    _hapus_pin(d.server, d.kondisi.siswa_id)
    sebelum = _keadaan(d)

    jawaban = _kirim_putusan(d, cookie, permintaan_id, "setuju", token)

    assert jawaban[0] == 403
    assert _keadaan(d) == sebelum
    assert _penempatan(d.kondisi.siswa_id) == []


def test_setuju_dengan_tirai_tertutup_ditolak_403_tanpa_efek(d):
    _, permintaan_id, _ = _siapkan_permintaan(d)
    cookie_tertutup = login(d.server, LOGIN_ANAK, SANDI_ANAK)
    token = _token_langsung(cookie_tertutup, permintaan_id, "setuju")
    sebelum = _keadaan(d)

    jawaban = _kirim_putusan(d, cookie_tertutup, permintaan_id, "setuju", token)

    assert jawaban[0] == 403
    assert _keadaan(d) == sebelum
    assert _penempatan(d.kondisi.siswa_id) == []


@pytest.mark.parametrize("jenis_token", ["domain_kode", "aksi_lain", "salah"])
def test_token_tidak_sah_ditolak_403_tanpa_efek(d, jenis_token):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    if jenis_token == "domain_kode":
        token = _token_langsung(cookie, permintaan_id, "setuju", domain=DOMAIN_KODE)
    elif jenis_token == "aksi_lain":
        token = _token_langsung(cookie, permintaan_id, "tolak")
    else:
        token = "1.salah"
    sebelum = _keadaan(d)

    jawaban = _kirim_putusan(d, cookie, permintaan_id, "setuju", token)

    assert jawaban[0] == 403
    assert _keadaan(d) == sebelum
    assert _penempatan(d.kondisi.siswa_id) == []


@pytest.mark.parametrize("isian", [
    {"hasil": "setuju", "token": "x"},
    {"permintaan_id": "1", "hasil": "hapus", "token": "x"},
    {"permintaan_id": "abc", "hasil": "setuju", "token": "x"},
    {"permintaan_id": "0", "hasil": "setuju", "token": "x"},
    {"permintaan_id": "01", "hasil": "setuju", "token": "x"},
    {"permintaan_id": "1", "hasil": "setuju", "token": "x", "siswa_id": "2"},
])
def test_bentuk_isian_tidak_sah_ditolak_400_tanpa_efek(d, isian):
    cookie, _, _ = _siapkan_permintaan(d)
    sebelum = _keadaan(d)

    jawaban = req(d.server, JALUR_PUTUSAN, data=isian, cookie=cookie)

    assert jawaban[0] == 400
    assert _keadaan(d) == sebelum


def test_permintaan_anak_lain_dan_id_tak_ada_dijawab_identik_tanpa_efek(d):
    _, permintaan_id, _ = _siapkan_permintaan(d)
    cookie_beta = _siapkan_anak_lain(d)
    sebelum = _keadaan(d)

    lain = _kirim_putusan(d, cookie_beta, permintaan_id, "setuju",
                          _token_langsung(cookie_beta, permintaan_id, "setuju"))
    tak_ada = _kirim_putusan(d, cookie_beta, ID_TAK_ADA, "setuju",
                             _token_langsung(cookie_beta, ID_TAK_ADA, "setuju"))

    assert lain[0] == tak_ada[0] == 409
    assert _bentuk(lain) == _bentuk(tak_ada)
    assert PESAN_TAK_BISA in lain[1]
    assert _keadaan(d) == sebelum
    assert _penempatan(d.kondisi.siswa_id) == []


# --- setuju dan tolak -------------------------------------------------------------------------

def test_setuju_menempatkan_anak_dan_mencatat_putusan_oleh_anak(d):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)

    jawaban = _putuskan(d, cookie, permintaan_id, "setuju")

    assert jawaban[0] == 200 and JUDUL_DISETUJUI in jawaban[1]
    assert "Location" not in jawaban[2]
    assert _penempatan(d.kondisi.siswa_id) == [d.kondisi.kelompok_id]
    assert _ledger(d) == [(permintaan_id, "setuju", d.kondisi.murid_id)]
    status = [b["status"] for b in dasar.daftar_untuk_guru(d.kondisi.guru_id, KINI)]
    assert status == [aturan.STATUS_SETUJU]


def test_kirim_ulang_setuju_hanya_satu_penempatan_dan_satu_putusan(d):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    token = _form_putusan(_halaman(d.server, cookie), permintaan_id, "setuju")["token"]
    assert _kirim_putusan(d, cookie, permintaan_id, "setuju", token)[0] == 200

    kedua = _kirim_putusan(d, cookie, permintaan_id, "setuju", token)

    assert kedua[0] == 409 and PESAN_TAK_BISA in kedua[1]
    assert _penempatan(d.kondisi.siswa_id) == [d.kondisi.kelompok_id]
    assert len(_ledger(d)) == 1


def test_setuju_lalu_tolak_dari_tab_kedua_gagal_dan_putusan_tidak_berubah(d):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    isi = _halaman(d.server, cookie)
    token_setuju = _form_putusan(isi, permintaan_id, "setuju")["token"]
    token_tolak = _form_putusan(isi, permintaan_id, "tolak")["token"]
    assert _kirim_putusan(d, cookie, permintaan_id, "setuju", token_setuju)[0] == 200
    sebelum = _ledger(d)

    tolak = _kirim_putusan(d, cookie, permintaan_id, "tolak", token_tolak)

    assert tolak[0] == 409 and PESAN_TAK_BISA in tolak[1]
    assert _ledger(d) == sebelum


def test_tolak_tanpa_penempatan_dan_guru_sama_tertahan_jeda_tetapi_guru_lain_bisa(d):
    cookie, permintaan_id, kode_tampil = _siapkan_permintaan(d)
    kode_id = dasar.kode_aktif(d.kondisi.murid_id, d.kondisi.siswa_id)["id"]

    jawaban = _putuskan(d, cookie, permintaan_id, "tolak")

    assert jawaban[0] == 200 and JUDUL_DITOLAK in jawaban[1]
    assert _penempatan(d.kondisi.siswa_id) == []
    assert _ledger(d) == [(permintaan_id, "tolak", d.kondisi.murid_id)]
    ulang_guru_sama = _ajukan_guru(d.server, d.kondisi.kelompok_id, kode_tampil)
    assert ulang_guru_sama[0] == 400 and LOGIN_ANAK not in ulang_guru_sama[1]
    guru_lain = dasar.ajukan(guru_id=id_akun(AKUN_B), kelompok_id=d.kondisi.kelompok_id, kode_id=kode_id,
                             pada=KINI)
    assert isinstance(guru_lain, int) and guru_lain > 0


def test_permintaan_kedaluwarsa_tidak_bisa_disetujui(d, jam):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    token = _token_langsung(cookie, permintaan_id, "setuju")
    jam.maju_jam(24 * 8)
    sebelum = _keadaan(d)

    jawaban = _kirim_putusan(d, cookie, permintaan_id, "setuju", token)

    assert jawaban[0] == 409 and PESAN_TAK_BISA in jawaban[1]
    assert _keadaan(d) == sebelum
    assert _penempatan(d.kondisi.siswa_id) == []


def test_kelompok_penuh_gagal_tanpa_putusan_dan_permintaan_tetap_menunggu(server, jam, tmp_path, monkeypatch):
    dunia = _siapkan(server, tmp_path, monkeypatch, kuota=1)
    cookie, permintaan_id, _ = _siapkan_permintaan(dunia)
    _isi_kursi(dunia)
    sebelum = _keadaan(dunia)

    jawaban = _putuskan(dunia, cookie, permintaan_id, "setuju")

    assert jawaban[0] == 409 and PESAN_PENUH in jawaban[1]
    assert _keadaan(dunia) == sebelum
    assert _ledger(dunia) == []
    assert _penempatan(dunia.kondisi.siswa_id) == []
    assert [b["id"] for b in _menunggu(dunia)] == [permintaan_id]


# --- ganti dan cabut: konfirmasi wajib, dan cabut membatalkan permintaan ------------------------

@pytest.mark.parametrize("tindakan", ["ganti", "cabut"])
def test_ganti_dan_cabut_tanpa_konfirmasi_ditolak_400_tanpa_efek(d, tindakan):
    cookie, _, _ = _siapkan_permintaan(d)
    masukan = form_kode(_halaman(d.server, cookie), tindakan)
    sebelum = _keadaan(d)

    jawaban = req(d.server, RUTE_KODE,
                  data={"tindakan": tindakan, "kode_id": masukan["kode_id"], "token": masukan["token"]},
                  cookie=cookie)

    assert jawaban[0] == 400
    assert _keadaan(d) == sebelum


@pytest.mark.parametrize("tindakan", ["ganti", "cabut"])
@pytest.mark.parametrize("nilai", ["", "0", "ya", "true"])
def test_ganti_dan_cabut_dengan_konfirmasi_bukan_satu_ditolak_400_tanpa_efek(d, tindakan, nilai):
    """Field `konfirmasi` ada tetapi nilainya bukan "1": ditolak, kode aktif tetap, tidak ada kode baru."""
    cookie, _, _ = _siapkan_permintaan(d)
    masukan = form_kode(_halaman(d.server, cookie), tindakan)
    kode_sebelum = dasar.kode_aktif(d.kondisi.murid_id, d.kondisi.siswa_id)["id"]
    baris_sebelum = baris_tabel(d.db, "kode_anak")
    sebelum = _keadaan(d)

    jawaban = req(d.server, RUTE_KODE,
                  data={"tindakan": tindakan, "kode_id": masukan["kode_id"], "token": masukan["token"],
                        "konfirmasi": nilai}, cookie=cookie)

    assert jawaban[0] == 400
    assert dasar.kode_aktif(d.kondisi.murid_id, d.kondisi.siswa_id)["id"] == kode_sebelum
    assert baris_tabel(d.db, "kode_anak") == baris_sebelum
    assert _keadaan(d) == sebelum


def test_cabut_dengan_konfirmasi_membatalkan_permintaan_menunggu(d):
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    isi = _halaman(d.server, cookie)
    masukan = form_kode(isi, "cabut")
    token_setuju = _form_putusan(isi, permintaan_id, "setuju")["token"]

    jawaban = req(d.server, RUTE_KODE,
                  data={"tindakan": "cabut", "kode_id": masukan["kode_id"], "token": masukan["token"],
                        "konfirmasi": "1"}, cookie=cookie)

    assert jawaban[0] == 200
    assert _menunggu(d) == []
    putusan = _kirim_putusan(d, cookie, permintaan_id, "setuju", token_setuju)
    assert putusan[0] == 409
    assert _penempatan(d.kondisi.siswa_id) == []


def test_anak_dihapus_antara_pengajuan_dan_persetujuan_gagal_tanpa_efek(d):
    """Dihapus dengan cara yang sama seperti tes HTTP kode: nama siswa dianonimkan, akun login tetap ada."""
    cookie, permintaan_id, _ = _siapkan_permintaan(d)
    token = _token_langsung(cookie, permintaan_id, "setuju")
    with d.server.buka() as kon:
        kon.execute("UPDATE siswa SET nama = ? WHERE id = ?", ("Dihapus-sintetis", d.kondisi.siswa_id))
        kon.commit()
    sebelum = _keadaan(d)

    jawaban = _kirim_putusan(d, cookie, permintaan_id, "setuju", token)

    assert jawaban[0] == 409 and "Akun anak ini sudah tidak aktif" in jawaban[1]
    assert _keadaan(d) == sebelum
    assert _penempatan(d.kondisi.siswa_id) == []


# --- batas aksi per akun (LOW-1) ----------------------------------------------------------------

@pytest.fixture(autouse=True)
def _laju_aksi_bersih():
    """Penghitung laju aksi di memori dikosongkan antar tes; tes tidak boleh mewarisi kuota tes lain."""
    laju._reset()
    yield
    laju._reset()


@pytest.fixture
def jam_laju(monkeypatch):
    """Jam yang diatur tes untuk penghitung laju saja. Sesi dan token tetap memakai jam asli."""
    waktu = {"kini": 1_800_000_000.0}
    monkeypatch.setattr(laju, "_waktu_kini", lambda sekarang: waktu["kini"] if sekarang is None else float(sekarang))
    return waktu


def _setuju_id_tak_ada(d, cookie) -> tuple:
    """Setuju ke id tak ada: galat domain (409) yang tetap memakai kuota. Mengembalikan jawaban HTTP."""
    token = _token_langsung(cookie, ID_TAK_ADA, "setuju")
    return _kirim_putusan(d, cookie, ID_TAK_ADA, "setuju", token)


def test_putusan_ikut_menghabiskan_kuota_akun_yang_sama(d, jam_laju):
    cookie, _permintaan_id, _kode = _siapkan_permintaan(d)  # pembuatan kode sudah memakai satu aksi
    for _ in range(aturan.AKSI_PER_AKUN - 1):
        assert _setuju_id_tak_ada(d, cookie)[0] == 409
    sebelum = _keadaan(d)

    kode_status, isi, _ = _setuju_id_tak_ada(d, cookie)

    assert kode_status == 429 and tautan_http.JUDUL_LAJU in isi
    assert _keadaan(d) == sebelum


def test_penolakan_token_putusan_tidak_menghabiskan_kuota(d, jam_laju):
    cookie, _permintaan_id, _kode = _siapkan_permintaan(d)  # pembuatan kode sudah memakai satu aksi
    for _ in range(aturan.AKSI_PER_AKUN + 5):
        assert _kirim_putusan(d, cookie, ID_TAK_ADA, "setuju", "1.0000")[0] == 403
    for _ in range(aturan.AKSI_PER_AKUN - 1):
        assert _setuju_id_tak_ada(d, cookie)[0] == 409

    assert _setuju_id_tak_ada(d, cookie)[0] == 429

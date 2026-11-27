"""Peringatan "di luar jam tetap guru" di halaman admin: render, HTTP, gerbang, dan penyimpanan yang tak berubah.

Data sintetis: guru `guru-b` dari kit, tanggal dan jam tetap. Gerbang dinyalakan lewat monkeypatch dan berkas guru
selalu di tmp_path (lewat env), tidak pernah berkas nyata.
"""
import hashlib
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

import admin_http
import admin_security
import admin_store
import auth
import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as dasar
import jadwal_admin_pages as ui
import jadwal_private_admin_pages as pv
import kelas_kit
import pesanan
import schema_jadwal
from admin_pesanan_kit import login_admin, minta_admin
from cek_http_kit import AKUN_ADMIN
from kelas_http_kit import jam, kidup, kmati, server  # noqa: F401

DAFTAR = "/admin/kelas"
KELOMPOK = "/admin/kelas/kelompok"
PENEMPATAN = "/admin/kelas/penempatan"
DETAIL = "/admin/kelas/verifikasi"
SLOT = pv.RUTE_SLOT
SLOT_BATAL = pv.RUTE_SLOT_BATAL
RUTE_PRIVATE = pv.RUTE
RUTE_TETAP = "/admin/jadwal/tetap"
TAUTAN = "https://zoom.us/j/123456789"
WAKTU_TETAP = "2026-11-23T03:00:00"
BLOK_SELASA = "2@480-600"                    # Selasa 08.00-10.00 WIB
BLOK_RABU_SABTU = "3@540-660;6@540-660"      # Rabu dan Sabtu 09.00-11.00 WIB
TANGGAL_MINI = "2026-11-24"                  # Selasa
TANGGAL_PRIVATE = "2026-11-25"               # Rabu
TOKEN = {"csrf": "c", "tinjauan": "t"}
TOKENS = {"ubah": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN, "tempatkan": TOKEN, "lepas": TOKEN}
GURU_RENDER = {"akun_" + "9" * 32: "guru-satu"}


# --- fixture dan helper HTTP ----------------------------------------------------------------

@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    return kidup


@pytest.fixture()
def admin(siap):
    return login_admin(siap)


@pytest.fixture()
def berkas_guru(tmp_path, monkeypatch):
    berkas = tmp_path / "guru-jadwal-tetap.db"
    monkeypatch.setenv(dasar.ENV_DB, str(berkas))
    return berkas


@pytest.fixture()
def gerbang_mati(monkeypatch):
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", False)


@pytest.fixture()
def gerbang_menyala(monkeypatch):
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", True)


@pytest.fixture()
def jadwal_selasa(siap, berkas_guru, gerbang_menyala):
    """Guru-b punya jadwal aktif Selasa 08.00-10.00 WIB; gerbang menyala."""
    _tetapkan(BLOK_SELASA)
    return berkas_guru


def _tetapkan(blok):
    dasar.tetapkan_admin(guru_akun=_guru(), blok=blok, admin_akun=_admin_id(), dibuat=WAKTU_TETAP)


def _admin_id() -> str:
    return auth.cari_akun(AKUN_ADMIN[0])["id_akun"]


def _guru() -> str:
    return auth.cari_akun("guru-b")["id_akun"]


def _token(cookie, aksi, isi):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie),
            "tinjauan": admin_security.buat_tinjauan(akun, cookie, aksi, isi)}


def _buat_kelompok(srv, cookie, *, tanggal=TANGGAL_MINI, jam="09:00", nama="Mini Peringatan") -> str:
    data = _token(cookie, "jadwal_kelompok_buat", {"section": "kelas_belajar"})
    data.update({"nama": nama, "lokasi": TAUTAN, "guru_id": _guru(), "kuota": "5",
                 "tanggal": tanggal, "jam": jam})
    kode, _, tajuk = minta_admin(srv, KELOMPOK, cookie, data)
    assert kode == 303, kode
    return tajuk["Location"].split("id=")[1]


def _order_private(siswa=3) -> str:
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return kelas_kit.lunas(kon, siswa, "private", n=siswa).order_id


def _tempatkan_private(srv, cookie, order_id, *, tanggal=TANGGAL_MINI, jam="09:00"):
    data = _token(cookie, "jadwal_tempatkan", {"order_id": order_id})
    data.update({"guru_id": _guru(), "tanggal": tanggal, "jam": jam})
    kode, _, _ = minta_admin(srv, PENEMPATAN, cookie, data)
    assert kode == 303, kode


def _slot_baru(srv, cookie, *, tanggal=TANGGAL_PRIVATE, jam="10:00") -> None:
    data = _token(cookie, "jadwal_private_slot_buat", {"section": "kelas_belajar"})
    data.update({"guru_id": _guru(), "tanggal": tanggal, "jam": jam})
    kode, _, _ = minta_admin(srv, SLOT, cookie, data)
    assert kode == 303, kode


def _id_slot_terakhir() -> int:
    berkas = Path(os.environ["JADWAL_PRIVATE_DB"])
    with closing(sqlite3.connect(str(berkas))) as kon:
        return kon.execute("SELECT id FROM private_slot ORDER BY id DESC LIMIT 1").fetchone()[0]


def _sha(berkas: Path) -> str:
    return hashlib.sha256(Path(berkas).read_bytes()).hexdigest()


def _halaman(srv, cookie, jalur):
    kode, isi, _ = minta_admin(srv, jalur, cookie)
    assert kode == 200, kode
    return isi


# --- render: byte identik bila tanpa tanda, dan teks peringatan ----------------------------------

def _sesi_render(id_, mulai, *, luar=None, bentrok=None, dibatalkan=0):
    kunci = {}
    if luar is not None:
        kunci["luar_jam"] = luar
    if bentrok is not None:
        kunci["bentrok"] = bentrok
    return {"id": id_, "ke": id_, "mulai": mulai, "menit": 60, "dibatalkan": dibatalkan, **kunci}


def _detail_render(sesi):
    kelompok = {"id": "klp_" + "a" * 32, "paket": "mini", "nama": "Mini A", "lokasi": TAUTAN,
                "guru_id": "akun_" + "9" * 32, "kuota": 5}
    return {"kelompok": kelompok, "anggota": [], "sesi": sesi, "terisi": 0}


def test_halaman_kelompok_tanpa_kunci_luar_jam_identik_dengan_luar_jam_nonaktif():
    # Arrange
    tanpa_kunci = [_sesi_render(1, "2026-11-24T02:00:00")]
    nonaktif = [_sesi_render(1, "2026-11-24T02:00:00", luar=False)]

    # Act
    biasa = ui.halaman_kelompok(_detail_render(tanpa_kunci), GURU_RENDER, TOKENS)
    dengan_kunci = ui.halaman_kelompok(_detail_render(nonaktif), GURU_RENDER, TOKENS)

    # Assert
    assert biasa == dengan_kunci
    assert ui.COPY_LUAR_JAM_SESI not in biasa and ui.COPY_LUAR_JAM_PERINGATAN not in biasa


def test_halaman_kelompok_menandai_baris_luar_jam_dan_satu_catatan():
    sesi = [_sesi_render(1, "2026-11-24T01:00:00", luar=False),
            _sesi_render(2, "2026-11-27T02:00:00", luar=True),
            _sesi_render(3, "2026-11-28T02:00:00", luar=True)]

    isi = ui.halaman_kelompok(_detail_render(sesi), GURU_RENDER, TOKENS)

    assert isi.count(ui.COPY_LUAR_JAM_SESI) == 2
    assert isi.count(ui.COPY_LUAR_JAM_PERINGATAN) == 1


def test_luar_jam_dan_bentrok_masing_masing_punya_catatan_sendiri_sekali():
    sesi = [_sesi_render(1, "2026-11-27T02:00:00", luar=True, bentrok=True)]

    isi = ui.halaman_kelompok(_detail_render(sesi), GURU_RENDER, TOKENS)

    assert isi.count(ui.COPY_LUAR_JAM_PERINGATAN) == 1
    assert isi.count(ui.COPY_BENTROK_PERINGATAN) == 1
    assert isi.count(ui.COPY_LUAR_JAM_SESI) == 1 and isi.count(ui.COPY_BENTROK_SESI) == 1


def test_blok_daftar_tautan_tetap_hanya_bila_diminta_dan_tanpa_id_di_tautan():
    kelompok = {"id": "klp_" + "a" * 32, "nama": "Mini A", "lokasi": TAUTAN, "guru_id": "akun_" + "9" * 32,
                "kuota": 5, "terisi": 0, "berikut": "2026-11-28T02:00:00"}
    biasa = ui.blok_daftar([kelompok], GURU_RENDER, TOKEN)

    assert biasa == ui.blok_daftar([kelompok], GURU_RENDER, TOKEN, tautan_tetap=False)
    assert ('href="%s"' % RUTE_TETAP) not in biasa
    dengan = ui.blok_daftar([kelompok], GURU_RENDER, TOKEN, tautan_tetap=True)
    assert ('href="%s"' % RUTE_TETAP) in dengan and ui.COPY_TAUTAN_TETAP in dengan
    tautan = dengan[dengan.index('href="%s"' % RUTE_TETAP):][:80]
    assert "akun_" not in tautan and "klp_" not in tautan and "kor_" not in tautan


def _slot_render(slot_id, status="terbuka", guru="akun_" + "9" * 32, mulai="2026-11-25T03:00:00"):
    return SimpleNamespace(slot_id=slot_id, guru_id=guru, mulai=mulai, status=status)


def _token_slot(slot_ids):
    return {"buat": TOKEN, "batal": {sid: TOKEN for sid in slot_ids}, "setujui": {}, "tolak": {}}


def test_halaman_private_tanpa_luar_jam_identik_dengan_frozenset_kosong():
    slot = [_slot_render(1), _slot_render(2, status="terisi")]
    token = _token_slot([1])

    biasa = pv.halaman(slot, (), GURU_RENDER, token)

    assert biasa == pv.halaman(slot, (), GURU_RENDER, token, luar_jam=frozenset())
    assert pv.COPY_LUAR_JAM_SLOT not in biasa and pv.COPY_LUAR_JAM_SLOT_PERINGATAN not in biasa


def test_halaman_private_menandai_slot_luar_jam_dan_satu_catatan():
    slot = [_slot_render(1), _slot_render(2)]

    isi = pv.halaman(slot, (), GURU_RENDER, _token_slot([1, 2]), luar_jam=frozenset({2}))

    assert isi.count(pv.COPY_LUAR_JAM_SLOT) == 1
    assert isi.count(pv.COPY_LUAR_JAM_SLOT_PERINGATAN) == 1


# --- HTTP: pertemuan dan slot ditandai saat gerbang menyala -------------------------------------

def test_detail_kelompok_menandai_pertemuan_di_luar_jam_saat_gerbang_menyala(siap, admin, jadwal_selasa):
    kid = _buat_kelompok(siap, admin)

    isi = _halaman(siap, admin, "%s?id=%s" % (KELOMPOK, kid))

    # Selasa 09.00 WIB dalam jam; Jumat (offset 3, 10, 17, 24 hari) di luar: empat pertemuan
    assert isi.count(ui.COPY_LUAR_JAM_SESI) == 4
    assert isi.count(ui.COPY_LUAR_JAM_PERINGATAN) == 1


def test_detail_order_private_menandai_pertemuan_di_luar_jam(siap, admin, jadwal_selasa):
    order = _order_private()
    _tempatkan_private(siap, admin, order, tanggal=TANGGAL_MINI, jam="09:00")

    isi = _halaman(siap, admin, "%s?order=%s" % (DETAIL, order))

    assert isi.count(ui.COPY_LUAR_JAM_SESI) == 4
    assert isi.count(ui.COPY_LUAR_JAM_PERINGATAN) == 1


def test_daftar_slot_private_menandai_slot_luar_jam_saat_gerbang_menyala(siap, admin, jadwal_selasa):
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="10:00")       # Rabu 10.00: Sabtu di luar blok Selasa

    isi = _halaman(siap, admin, RUTE_PRIVATE)

    assert isi.count(pv.COPY_LUAR_JAM_SLOT) == 1
    assert isi.count(pv.COPY_LUAR_JAM_SLOT_PERINGATAN) == 1


def test_slot_dibatalkan_tidak_ditandai_luar_jam(siap, admin, jadwal_selasa):
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="10:00")
    sid = _id_slot_terakhir()
    assert minta_admin(siap, SLOT_BATAL, admin, _form_slot_batal(admin, sid))[0] == 303

    isi = _halaman(siap, admin, RUTE_PRIVATE)

    assert "Dibatalkan" in isi
    assert pv.COPY_LUAR_JAM_SLOT not in isi and pv.COPY_LUAR_JAM_SLOT_PERINGATAN not in isi


def _form_slot_batal(cookie, sid):
    data = _token(cookie, "jadwal_private_slot_batal", {"target_id": sid})
    data["id"] = str(sid)
    return data


def test_slot_semua_pertemuan_di_dalam_jam_tidak_ditandai(siap, admin, berkas_guru, gerbang_menyala):
    _tetapkan(BLOK_RABU_SABTU)
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="10:00")

    isi = _halaman(siap, admin, RUTE_PRIVATE)

    assert pv.COPY_LUAR_JAM_SLOT not in isi and pv.COPY_LUAR_JAM_SLOT_PERINGATAN not in isi


# --- gerbang mati, guru tanpa jadwal, dan tautan statis -----------------------------------------

def test_gerbang_mati_tanpa_peringatan_dan_tanpa_membaca_berkas(siap, admin, berkas_guru, gerbang_mati,
                                                                monkeypatch):
    kid = _buat_kelompok(siap, admin)
    order = _order_private()
    _tempatkan_private(siap, admin, order, tanggal=TANGGAL_MINI, jam="09:00")
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="10:00")

    def _tidak_boleh_dibaca(*_args, **_kwargs):
        raise AssertionError("gerbang mati tidak boleh membaca jadwal tetap")

    monkeypatch.setattr(dasar, "aktif", _tidak_boleh_dibaca)
    halaman = [_halaman(siap, admin, "%s?id=%s" % (KELOMPOK, kid)),
               _halaman(siap, admin, "%s?order=%s" % (DETAIL, order)),
               _halaman(siap, admin, RUTE_PRIVATE),
               _halaman(siap, admin, DAFTAR)]

    for isi in halaman:
        assert ui.COPY_LUAR_JAM_SESI not in isi and pv.COPY_LUAR_JAM_SLOT not in isi
        assert ('href="%s"' % RUTE_TETAP) not in isi
    assert not berkas_guru.exists()


def test_gerbang_menyala_tanpa_jadwal_guru_tanpa_peringatan_dan_tanpa_berkas(siap, admin, berkas_guru,
                                                                              gerbang_menyala):
    kid = _buat_kelompok(siap, admin)

    isi = _halaman(siap, admin, "%s?id=%s" % (KELOMPOK, kid))

    assert ui.COPY_LUAR_JAM_SESI not in isi and ui.COPY_LUAR_JAM_PERINGATAN not in isi
    assert not berkas_guru.exists()


def test_tautan_statis_jadwal_tetap_hanya_saat_gerbang_menyala(siap, admin, berkas_guru, monkeypatch):
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", False)
    mati = _halaman(siap, admin, DAFTAR)
    monkeypatch.setattr(aturan, "GURU_JADWAL_TETAP_AKTIF", True)
    menyala = _halaman(siap, admin, DAFTAR)

    assert ('href="%s"' % RUTE_TETAP) not in mati
    assert ('href="%s"' % RUTE_TETAP) in menyala
    assert ui.COPY_TAUTAN_TETAP in menyala


# --- penyimpanan tidak berubah oleh GET, dan baca hanya sekali per guru ------------------------

def test_penyimpanan_admin_dan_guru_tidak_berubah_oleh_get(siap, admin, jadwal_selasa):
    kid = _buat_kelompok(siap, admin)
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="10:00")
    sebelum = (_sha(admin_store.BAWAAN), _sha(jadwal_selasa))

    _halaman(siap, admin, "%s?id=%s" % (KELOMPOK, kid))
    _halaman(siap, admin, RUTE_PRIVATE)
    _halaman(siap, admin, DAFTAR)

    assert (_sha(admin_store.BAWAAN), _sha(jadwal_selasa)) == sebelum


def test_blok_guru_dibaca_sekali_per_permintaan_walau_banyak_slot(siap, admin, jadwal_selasa, monkeypatch):
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="10:00")
    _slot_baru(siap, admin, tanggal=TANGGAL_PRIVATE, jam="13:00")
    dibaca = []
    asli = dasar.aktif

    def _catat(guru_akun, **kwargs):
        dibaca.append(guru_akun)
        return asli(guru_akun, **kwargs)

    monkeypatch.setattr(dasar, "aktif", _catat)

    _halaman(siap, admin, RUTE_PRIVATE)

    assert dibaca == [_guru()]

"""Admin jadwal Private lewat HTTP nyata: slot, pengajuan orang tua, setujui/tolak, batal, dan antrean.

Data sepenuhnya sintetis (akun, order, dan jam tetap dari `kelas_http_kit`). DB private dari conftest (JADWAL_PRIVATE_DB).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest

import admin_antrean as A
import admin_antrean_private as ap
import admin_http
import admin_security
import admin_store
import auth
import jadwal_admin_http as jah
import jadwal_private as jp
import jadwal_private_pola as jpp
import jadwal_store as js
import kelas_kit
import pesanan
import schema_jadwal
from admin_pesanan_kit import login_admin, minta_admin
from cek_http_kit import AKUN_A as AKUN_GURU_BASIC
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, minta_mentah
from kelas_http_kit import baca_admin, jam, kidup, kmati, server  # noqa: F401
from pesanan_kit import AKUN_A as AKUN_ORANG_TUA
import jadwal_private_admin_pages as ui

RUTE = ui.RUTE
SLOT = ui.RUTE_SLOT
BATAL = ui.RUTE_SLOT_BATAL
SETUJUI = ui.RUTE_SETUJUI
TOLAK = ui.RUTE_TOLAK
TAK_ADA = "/admin/tidak-ada"
KUNCI = "target_id"
TANGGAL, PUKUL = "2026-11-25", "10:00"        # 03.00 UTC; >= 24 jam sesudah AWAL (23 Nov 03.00 UTC)
MULAI = "2026-11-25T03:00:00"
SEKARANG = "2026-11-23T03:00:00"             # = jam fixture (AWAL)
SEKARANG_EPOCH = datetime(2026, 11, 23, 3, tzinfo=timezone.utc).timestamp()
SEKARANG_BASI_EPOCH = datetime(2026, 11, 25, 4, tzinfo=timezone.utc).timestamp()


@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    return kidup


@pytest.fixture()
def admin(siap):
    return login_admin(siap)


def _token(cookie, aksi, isi):
    akun = auth.cari_akun(AKUN_ADMIN[0])
    return {"csrf": admin_http._csrf(akun, cookie),
            "tinjauan": admin_security.buat_tinjauan(akun, cookie, aksi, isi)}


def _form_target(cookie, aksi, target):
    """Form aksi satu target: tinjauan mengikat `target_id`, field `id` harus sama."""
    data = _token(cookie, aksi, {KUNCI: target})
    data["id"] = str(target)
    return data


def _guru_id() -> str:
    return auth.cari_akun("guru-b")["id_akun"]


def _guru_sah() -> frozenset:
    return frozenset(jah.guru_map())


def _baris_privat(sql, args=()) -> list:
    berkas = Path(os.environ["JADWAL_PRIVATE_DB"])
    if not berkas.exists():
        return []
    with closing(sqlite3.connect(str(berkas))) as kon:
        kon.row_factory = sqlite3.Row
        return [dict(b) for b in kon.execute(sql, args).fetchall()]


def _slot_baru(srv, cookie, *, guru=None, tanggal=TANGGAL, pukul=PUKUL):
    data = _token(cookie, "jadwal_private_slot_buat", {"section": "kelas_belajar"})
    data.update({"guru_id": guru or _guru_id(), "tanggal": tanggal, "jam": pukul})
    return minta_admin(srv, SLOT, cookie, data)


def _buat_slot(srv, cookie, pukul=PUKUL) -> int:
    kode, _isi, _tajuk = _slot_baru(srv, cookie, pukul=pukul)
    assert kode == 303, kode
    return _baris_privat("SELECT id FROM private_slot ORDER BY id DESC LIMIT 1")[0]["id"]


def _aktif(siswa=1) -> str:
    with pesanan.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return kelas_kit.lunas(kon, siswa, "private", n=siswa).order_id


def _ajukan(siswa, slot_id) -> int:
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return jp.ajukan(kon, AKUN_ORANG_TUA, siswa, slot_id, SEKARANG, _guru_sah())


def _status(pid) -> str:
    return _baris_privat("SELECT status FROM private_pengajuan WHERE id=?", (pid,))[0]["status"]


def _slot_batal(sid) -> int:
    return _baris_privat("SELECT dibatalkan FROM private_slot WHERE id=?", (sid,))[0]["dibatalkan"]


def _jumlah_penempatan() -> int:
    return baca_admin("SELECT COUNT(*) AS n FROM jadwal_penempatan")[0]["n"]


def _penempatan(order_id) -> int:
    return baca_admin("SELECT COUNT(*) AS n FROM jadwal_penempatan WHERE order_id=?", (order_id,))[0]["n"]


# --- GET & akses ----------------------------------------------------------------------------

def test_admin_buat_slot_lalu_tampil_di_daftar(siap, admin):
    kode, _isi, tajuk = _slot_baru(siap, admin)
    assert kode == 303 and tajuk["Location"] == RUTE
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert "Terbuka" in isi and "guru-b" in isi and "pukul 10.00 WIB" in isi
    assert len(_baris_privat("SELECT * FROM private_slot")) == 1


def test_anonim_dan_guru_404_identik_untuk_semua_rute_private(siap):
    acuan_get = minta_mentah(siap, TAK_ADA, None, None)[:2]
    acuan_post = minta_mentah(siap, TAK_ADA, None, {})[:2]
    for akun in (None, AKUN_GURU_BASIC):
        assert minta_mentah(siap, RUTE, akun, None)[:2] == acuan_get
        for jalur in (SLOT, BATAL, SETUJUI, TOLAK):
            assert minta_mentah(siap, jalur, akun, {})[:2] == acuan_post


def test_query_tidak_dikenal_di_halaman_private_404(siap, admin):
    assert minta_admin(siap, RUTE + "?x=1", admin)[0] == 404


def test_halaman_private_tidak_memuat_sandi_atau_hash(siap, admin):
    sid = _buat_slot(siap, admin)
    _aktif(1)
    _ajukan(1, sid)
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200
    assert SANDI_ADMIN not in isi and "pbkdf2" not in isi.lower()


def test_halaman_private_tetap_terbuka_saat_sakelar_paket_belajar_mati(kmati):
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    admin = login_admin(kmati)
    kode, isi, _ = minta_admin(kmati, RUTE, admin)
    assert kode == 200 and "Slot Private" in isi


def test_halaman_kelas_menautkan_jadwal_private(siap, admin):
    kode, isi, _ = minta_admin(siap, "/admin/kelas", admin)
    assert kode == 200 and 'href="/admin/kelas/private"' in isi


# --- slot ------------------------------------------------------------------------------------

def test_slot_tidak_sah_ditolak_tanpa_efek(siap, admin):
    assert _slot_baru(siap, admin, guru="akun_" + "0" * 32)[0] == 400
    assert _slot_baru(siap, admin, tanggal="2026-11-20")[0] == 400
    assert _slot_baru(siap, admin)[0] == 303
    assert _slot_baru(siap, admin)[0] == 409  # duplikat: JadwalKonflik dari domain (409, bukan 400)
    assert len(_baris_privat("SELECT * FROM private_slot")) == 1


def test_csrf_salah_tinjauan_basi_dan_aksi_lain_ditolak_tanpa_efek(siap, admin):
    isi_form = {"guru_id": _guru_id(), "tanggal": TANGGAL, "jam": PUKUL}
    salah_csrf = dict(_token(admin, "jadwal_private_slot_buat", {"section": "kelas_belajar"}), **isi_form)
    salah_csrf["csrf"] = "salah"
    assert minta_admin(siap, SLOT, admin, salah_csrf)[0] == 403
    akun = auth.cari_akun(AKUN_ADMIN[0])
    basi = admin_security.buat_tinjauan(akun, admin, "jadwal_private_slot_buat",
                                        {"section": "kelas_belajar"}, sekarang=1)
    data_basi = dict(isi_form, csrf=admin_http._csrf(akun, admin), tinjauan=basi)
    assert minta_admin(siap, SLOT, admin, data_basi)[0] == 403
    aksi_lain = dict(_token(admin, "jadwal_private_tolak", {KUNCI: 1}), **isi_form)
    assert minta_admin(siap, SLOT, admin, aksi_lain)[0] == 403
    assert _baris_privat("SELECT * FROM private_slot") == []


def test_field_asing_ditolak_400_tanpa_efek(siap, admin):
    data = dict(_token(admin, "jadwal_private_slot_buat", {"section": "kelas_belajar"}),
                guru_id=_guru_id(), tanggal=TANGGAL, jam=PUKUL, order_id="ord_" + "0" * 32)
    assert minta_admin(siap, SLOT, admin, data)[0] == 400
    assert _baris_privat("SELECT * FROM private_slot") == []


def test_slot_batal_terbuka_berhasil_dan_slot_diajukan_ditolak(siap, admin):
    terbuka = _buat_slot(siap, admin, pukul="10:00")
    diajukan = _buat_slot(siap, admin, pukul="13:00")
    _aktif(1)
    _ajukan(1, diajukan)
    kode, _isi, _tajuk = minta_admin(siap, BATAL, admin, _form_target(admin, "jadwal_private_slot_batal", terbuka))
    assert kode == 303
    assert _slot_batal(terbuka) == 1
    assert minta_admin(siap, BATAL, admin, _form_target(admin, "jadwal_private_slot_batal", diajukan))[0] == 409
    assert _slot_batal(diajukan) == 0


# --- pengajuan: setujui, tolak, basi, id ---------------------------------------------------------

def test_setujui_pengajuan_hidup_menempatkan_delapan_pertemuan(siap, admin):
    sid = _buat_slot(siap, admin)
    oid = _aktif(1)
    pid = _ajukan(1, sid)
    kode, _isi, tajuk = minta_admin(siap, SETUJUI, admin, _form_target(admin, "jadwal_private_setujui", pid))
    assert kode == 303 and tajuk["Location"] == RUTE
    assert _status(pid) == "disetujui"
    assert _penempatan(oid) == 1
    assert baca_admin("SELECT COUNT(*) AS n FROM jadwal_pertemuan WHERE order_id=?", (oid,))[0]["n"] == 8


def test_setujui_pengajuan_basi_ditolak_dan_tombolnya_tidak_tampil(siap, admin, jam):  # noqa: F811
    sid = _buat_slot(siap, admin)
    oid = _aktif(1)
    pid = _ajukan(1, sid)
    jam.nilai = "2026-11-25T04:00:00"  # sesudah mulai slot (03.00 UTC): pengajuan basi
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200 and "kedaluwarsa: waktu mulai sudah lewat" in isi
    assert 'action="%s"' % SETUJUI not in isi and 'action="%s"' % TOLAK in isi
    assert minta_admin(siap, SETUJUI, admin, _form_target(admin, "jadwal_private_setujui", pid))[0] == 409
    assert _penempatan(oid) == 0
    assert _status(pid) == "diajukan"


def test_tolak_pengajuan_ubah_status_ditolak(siap, admin):
    sid = _buat_slot(siap, admin)
    _aktif(1)
    pid = _ajukan(1, sid)
    kode, _isi, tajuk = minta_admin(siap, TOLAK, admin, _form_target(admin, "jadwal_private_tolak", pid))
    assert kode == 303 and tajuk["Location"] == RUTE
    assert _status(pid) == "ditolak"
    assert _jumlah_penempatan() == 0


def test_id_form_berbeda_dari_tinjauan_ditolak_tanpa_efek(siap, admin):
    slot_a = _buat_slot(siap, admin, pukul="10:00")
    slot_b = _buat_slot(siap, admin, pukul="13:00")
    _aktif(1)
    _aktif(2)
    pa = _ajukan(1, slot_a)
    pb = _ajukan(2, slot_b)
    data = _token(admin, "jadwal_private_tolak", {KUNCI: pa})
    data["id"] = str(pb)
    assert minta_admin(siap, TOLAK, admin, data)[0] == 400
    assert _status(pa) == "diajukan" and _status(pb) == "diajukan"


# --- antrean & fail-safe -----------------------------------------------------------------------

def test_butir_antrean_private_menghitung_pengajuan_hidup_dan_hilang_saat_nol(siap, admin):
    sid = _buat_slot(siap, admin)
    _aktif(1)
    pid = _ajukan(1, sid)
    assert ap.jumlah(admin_store.BAWAAN, SEKARANG_EPOCH) == 1
    (butir,) = A._item_pengajuan_private(admin_store.BAWAAN, SEKARANG_EPOCH)
    assert butir.judul == "1 pengajuan jadwal Private menunggu"
    assert butir.jalur == RUTE and butir.tingkat == "tinjau"
    assert ap.jumlah(admin_store.BAWAAN, SEKARANG_EPOCH) == 1
    assert ap.jumlah(admin_store.BAWAAN, SEKARANG_BASI_EPOCH) == 0  # basi tidak dihitung
    assert A._item_pengajuan_private(admin_store.BAWAAN, SEKARANG_BASI_EPOCH) == ()
    assert minta_admin(siap, TOLAK, admin, _form_target(admin, "jadwal_private_tolak", pid))[0] == 303
    assert A._item_pengajuan_private(admin_store.BAWAAN, SEKARANG_EPOCH) == ()


def test_antrean_dan_halaman_fail_safe_saat_berkas_private_rusak(siap, admin):
    Path(os.environ["JADWAL_PRIVATE_DB"]).write_bytes(b"bukan sqlite " * 100)
    assert ap.jumlah(admin_store.BAWAAN, SEKARANG_EPOCH) == 0
    assert A._item_pengajuan_private(admin_store.BAWAAN, SEKARANG_EPOCH) == ()
    kode, _isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 503


# --- pola orang tua (2 hari + 1 jam) --------------------------------------------------------

def _ajukan_pola(siswa=1) -> int:
    """Pola Kamis & Jumat jam 15.00 WIB dari akun orang tua sintetis; tanggal usulan 26 Nov."""
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return jpp.ajukan(kon, AKUN_ORANG_TUA, siswa, {"hari_3": "1", "hari_4": "1", "jam": "15:00"}, SEKARANG)


def test_pola_tampil_dengan_tanggal_usulan_lalu_setujui_menempatkan_delapan_pertemuan(siap, admin):
    oid = _aktif(1)
    pid = _ajukan_pola(1)
    kode, isi, _ = minta_admin(siap, RUTE, admin)
    assert kode == 200 and "Pola orang tua" in isi and "Kamis &amp; Jumat pukul 15.00 WIB" in isi
    assert 'value="2026-11-26"' in isi and 'action="%s"' % ui.RUTE_POLA_SETUJUI in isi
    data = _form_target(admin, "jadwal_private_pola_setujui", pid)
    data.update({"guru_id": _guru_id(), "tanggal": "2026-11-26"})
    kode, _isi, tajuk = minta_admin(siap, ui.RUTE_POLA_SETUJUI, admin, data)
    assert kode == 303 and tajuk["Location"] == RUTE
    assert _baris_privat("SELECT status FROM private_pola_pengajuan WHERE id=?", (pid,))[0]["status"] == "disetujui"
    assert _penempatan(oid) == 1
    assert baca_admin("SELECT COUNT(*) AS n FROM jadwal_pertemuan WHERE order_id=?", (oid,))[0]["n"] == 8


def test_pola_tolak_lewat_http_ubah_status_ditolak_tanpa_penempatan(siap, admin):
    _aktif(1)
    pid = _ajukan_pola(1)
    kode, _isi, tajuk = minta_admin(siap, ui.RUTE_POLA_TOLAK, admin,
                                    _form_target(admin, "jadwal_private_pola_tolak", pid))
    assert kode == 303 and tajuk["Location"] == RUTE
    assert _baris_privat("SELECT status FROM private_pola_pengajuan WHERE id=?", (pid,))[0]["status"] == "ditolak"
    assert _jumlah_penempatan() == 0

"""Orang tua mengajukan jadwal Private lewat HTTP nyata (/murid/paket/jadwal-private/*; data sintetis).

Kartu dan tombol hanya untuk order Private aktif yang belum berjadwal. Setiap aksi yang ditolak dibuktikan tanpa efek
dengan membandingkan keadaan DB private dan penempatan sebelum dan sesudah, bukan hanya kode status.
"""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import time

import admin_store
import auth
import database
import jadwal_private as jp
import jadwal_store as js
import kelas_putusan
import kelas_store
import pin_orang_tua_store as pin_store
import schema_jadwal
import tirai_orang_tua as tirai
from bukti_kit import JPEG, PNG
from harian_kit import SANDI, Murid
from kelas_http_kit import (ADMIN, AWAL, M, baca_admin, bukti_terakhir, buat, buat_dan_unggah, buat_murid, halaman,
                            jam, kidup, kirim, kmati, minta_mentah, server, token)

AJUKAN = M + "/jadwal-private/ajukan"
BATAL = M + "/jadwal-private/batal"
AKSI_AJUKAN = "jadwal_private_ajukan:"
AKSI_BATAL = "jadwal_private_batal"
JUDUL = "Jadwal Private"
TANGGAL, PUKUL = "2026-11-25", "10:00"  # 03.00 UTC; lebih dari 24 jam sesudah AWAL
TEKS_SLOT = "25 November 2026 pukul 10.00 WIB"
GURU_NONAKTIF = "akun_" + "7" * 32
PIN = "4821"


@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    tirai._reset()
    yield kidup
    tirai._reset()


def _guru_id() -> str:
    return auth.cari_akun("guru-b")["id_akun"]


def _slot(tanggal=TANGGAL, pukul=PUKUL, guru=None, sah=None) -> int:
    g = guru or _guru_id()
    return jp.buat_slot(ADMIN, g, tanggal, pukul, AWAL, frozenset({g}) if sah is None else sah)


def _aktifkan(srv, murid, kode="private", isi=JPEG) -> str:
    order_id = buat_dan_unggah(srv, murid, kode, isi)
    with kelas_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, order_id, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(order_id))
    return order_id


def _murid_kedua_anak_sama(murid: Murid) -> Murid:
    """Akun kedua yang terhubung ke anak yang sama (pemilik anak diuji oleh guard ini)."""
    principal = auth.tambah_akun_dan_principal("murid-kedua", SANDI, "murid", siswa_id=murid.siswa_id)
    return Murid(("murid-kedua", SANDI), principal.id_akun, murid.siswa_id)


def _form_ajukan(murid, slot_id: int) -> dict:
    return {"token": token(murid.akun, AKSI_AJUKAN + str(slot_id)), "slot": str(slot_id)}


def _form_batal(murid) -> dict:
    return {"token": token(murid.akun, AKSI_BATAL)}


def _teks(isi: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


def _berkas_private() -> str:
    return os.environ["JADWAL_PRIVATE_DB"]


def _pengajuan() -> list:
    """Baris pengajuan dari DB private (kosong bila berkas belum ada)."""
    if not Path(_berkas_private()).exists():
        return []
    with closing(sqlite3.connect(_berkas_private())) as kon:
        kon.row_factory = sqlite3.Row
        return [dict(b) for b in kon.execute("SELECT id,order_id,slot_id,status FROM private_pengajuan ORDER BY id")]


def _keadaan() -> tuple:
    """Keadaan yang tidak boleh berubah saat aksi ditolak: pengajuan, penempatan, dan jumlah pertemuan."""
    return (_pengajuan(), baca_admin("SELECT * FROM jadwal_penempatan"),
            baca_admin("SELECT COUNT(*) AS n FROM jadwal_pertemuan")[0]["n"])


def test_kartu_hanya_untuk_private_aktif_tanpa_jadwal(siap, jam):  # noqa: F811
    assert JUDUL not in _teks(halaman(siap, siap.a))             # belum punya paket
    _aktifkan(siap, siap.a, "mini")
    _slot()
    assert JUDUL not in _teks(halaman(siap, siap.a))             # Mini tidak ditawari Private
    jam.maju_jam(1)                                              # urutan order sama waktu: beri jeda
    _aktifkan(siap, siap.b, "private", PNG)
    t = _teks(halaman(siap, siap.b))
    assert JUDUL in t and TEKS_SLOT in t and "Ajukan" in t and "2x seminggu" in t


def test_halaman_tidak_memuat_nama_guru_id_guru_atau_sandi(siap):
    _aktifkan(siap, siap.a)
    _slot()
    isi = halaman(siap, siap.a)
    assert JUDUL in _teks(isi)
    assert "guru-b" not in _teks(isi) and _guru_id() not in isi and SANDI not in isi


def test_ajukan_lalu_menunggu_dan_pilihan_kedua_menggantikan(siap):
    oid = _aktifkan(siap, siap.a)
    s1, s2 = _slot(), _slot(pukul="11:00")
    kode, _isi, tajuk = kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s1))
    assert (kode, tajuk["Location"]) == (303, M)
    assert [(p["order_id"], p["slot_id"], p["status"]) for p in _pengajuan()] == [(oid, s1, "diajukan")]
    t = _teks(halaman(siap, siap.a))
    assert "menunggu persetujuan tim" in t and "Batalkan pilihan" in t and "Ganti ke waktu ini" in t and TEKS_SLOT in t
    assert kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s2))[0] == 303
    assert [(p["slot_id"], p["status"]) for p in _pengajuan()] == [(s1, "dibatalkan"), (s2, "diajukan")]


def test_pengajuan_basi_tampil_sebagai_tidak_bisa_dipakai_bukan_menunggu(siap):
    import guru_status
    import kelas_private_pages as kp
    _aktifkan(siap, siap.a)
    s1 = _slot()
    kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s1))
    assert "menunggu persetujuan tim" in _teks(halaman(siap, siap.a))
    akun = auth.cari_akun("guru-b")
    guru_status.nonaktifkan(akun["id_akun"], auth.revisi_auth(akun), "admin-uji", int(time.time()))  # slot jadi basi
    t = _teks(halaman(siap, siap.a))
    assert "menunggu persetujuan" not in t and "Batalkan pilihan" not in t
    assert _teks(kp.COPY_DITOLAK) in t


def test_batal_mengembalikan_pilihan_ke_daftar(siap):
    _aktifkan(siap, siap.a)
    s1 = _slot()
    kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s1))
    assert kirim(siap, BATAL, siap.a, {"token": token(siap.a.akun, AKSI_AJUKAN + str(s1))})[0] == 403
    assert kirim(siap, BATAL, siap.a, _form_batal(siap.a))[0] == 303
    assert [p["status"] for p in _pengajuan()] == ["dibatalkan"]
    t = _teks(halaman(siap, siap.a))
    assert "menunggu persetujuan" not in t and "Ajukan" in t
    assert kirim(siap, BATAL, siap.a, _form_batal(siap.a))[0] == 409        # tidak ada yang bisa dibatalkan lagi


def test_form_atau_token_salah_ditolak_tanpa_efek(siap):
    _aktifkan(siap, siap.a)
    s1, s2 = _slot(), _slot(pukul="11:00")
    a = siap.a
    kasus = [
        ({**_form_ajukan(a, s1), "token": "salah"}, 403),
        ({**_form_ajukan(a, s1), "token": token(a.akun, AKSI_AJUKAN + str(s2))}, 403),   # token slot lain
        ({**_form_ajukan(a, s1), "token": token(a.akun, AKSI_BATAL)}, 403),              # token aksi lain
        ({**_form_ajukan(a, s1), "slot": "1_0"}, 400),
        ({**_form_ajukan(a, s1), "slot": " " + str(s1)}, 400),
        ({**_form_ajukan(a, s1), "slot": "0"}, 400),
        ({**_form_ajukan(a, s1), "slot": "bukan-id"}, 400),
        ({**_form_ajukan(a, s1), "order": "ord_" + "0" * 32}, 400),                      # order tidak boleh dari form
        ({**_form_ajukan(a, s1), "siswa": "1"}, 400),
        ({"token": token(a.akun, AKSI_AJUKAN + str(s1))}, 400),                          # slot hilang
    ]
    sebelum = _keadaan()
    for data, kode_harap in kasus:
        assert kirim(siap, AJUKAN, a, data)[0] == kode_harap, data
    assert _keadaan() == sebelum


def test_token_basi_ditolak_tanpa_efek(siap, monkeypatch):
    _aktifkan(siap, siap.a)
    s = _slot()
    waktu_asli = time.time
    monkeypatch.setattr(time, "time", lambda: 1000.0)                 # token dibuat jauh di masa lalu
    data = _form_ajukan(siap.a, s)
    monkeypatch.setattr(time, "time", waktu_asli)
    sebelum = _keadaan()
    assert kirim(siap, AJUKAN, siap.a, data)[0] == 403
    assert _keadaan() == sebelum


def test_anak_tanpa_order_private_dan_akun_terhubung_tidak_bisa_mengajukan(siap):
    oid = _aktifkan(siap, siap.a)
    s1 = _slot()
    kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s1))
    lain = _murid_kedua_anak_sama(siap.a)
    sebelum = _keadaan()
    assert kirim(siap, AJUKAN, siap.b, _form_ajukan(siap.b, _slot(pukul="11:00")))[0] == 409   # anak tanpa order
    assert kirim(siap, AJUKAN, lain, _form_ajukan(lain, _slot(pukul="12:00")))[0] == 409       # akun lain, anak sama
    assert kirim(siap, BATAL, lain, _form_batal(lain))[0] == 409                              # batal milik orang lain
    assert [(p["order_id"], p["status"]) for p in _pengajuan() if p["status"] == "diajukan"] == [(oid, "diajukan")]
    assert _keadaan() == sebelum


def test_slot_yang_melanggar_syarat_ditolak_tanpa_efek(siap):
    _aktifkan(siap, siap.a)
    dekat = _slot(tanggal="2026-11-23", pukul="11:00")       # kurang dari 24 jam sesudah AWAL
    asing = _slot(guru=GURU_NONAKTIF, sah=frozenset({GURU_NONAKTIF}))   # guru tidak aktif di akun
    jauh = _slot(tanggal="2026-12-20")                         # pertemuan terakhir melewati masa akses
    sebelum = _keadaan()
    for slot_id in (dekat, asing, jauh):
        assert kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, slot_id))[0] == 409, slot_id
    assert _keadaan() == sebelum


def test_slot_yang_sedang_diajukan_anak_lain_ditolak(siap, jam):  # noqa: F811
    _aktifkan(siap, siap.a)
    jam.maju_jam(1)
    _aktifkan(siap, siap.b, "private", PNG)
    s = _slot()
    assert kirim(siap, AJUKAN, siap.b, _form_ajukan(siap.b, s))[0] == 303
    sebelum = _keadaan()
    assert kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s))[0] == 409
    assert _keadaan() == sebelum


def test_sakelar_mati_jawab_seperti_rute_murid_tanpa_efek(siap, monkeypatch):
    _aktifkan(siap, siap.a)
    s = _slot()
    monkeypatch.setenv("PAKET_BELAJAR", "0")
    sebelum = _keadaan()
    acuan = buat(siap, siap.a, "private")[0]                  # rute Paket Belajar lain saat sakelar mati
    assert acuan == 401                                       # jalur murid asing: sama untuk semua rute sakelar
    assert kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s))[0] == acuan
    assert kirim(siap, BATAL, siap.a, _form_batal(siap.a))[0] == acuan
    assert _keadaan() == sebelum


def test_tanpa_sesi_anak_ditolak_tanpa_efek(siap):
    _aktifkan(siap, siap.a)
    s = _slot()
    sebelum = _keadaan()
    kode, _isi, _tajuk = minta_mentah(siap, AJUKAN, None, _form_ajukan(siap.a, s))
    assert kode == 401
    assert _keadaan() == sebelum


def test_pin_tirai_tertutup_menolak_ajukan_dan_menyembunyikan_kartu(siap):
    _aktifkan(siap, siap.a)
    s = _slot()
    with database.buka() as kon:
        pin_store.simpan(kon, siap.a.siswa_id, PIN, 1_800_000_000)
    sebelum = _keadaan()
    assert kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s))[0] == 403
    assert _keadaan() == sebelum
    t = _teks(halaman(siap, siap.a))
    assert "terkunci PIN" in t and JUDUL not in t and "Ajukan" not in t


def test_setujui_admin_menggantikan_kartu_dengan_jadwal_biasa(siap):
    oid = _aktifkan(siap, siap.a)
    kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, _slot()))
    pid = _pengajuan()[0]["id"]
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        jp.setujui(kon, ADMIN, pid, AWAL, frozenset({_guru_id()}))
    t = _teks(halaman(siap, siap.a))
    assert "Jadwal pertemuan" in t and "Pertemuan 1 · " + TEKS_SLOT in t
    assert JUDUL not in t and "menunggu" not in t and "Ajukan" not in t and "None" not in t
    assert [p["order_id"] for p in baca_admin("SELECT order_id FROM jadwal_penempatan")] == [oid]
    assert baca_admin("SELECT COUNT(*) AS n FROM jadwal_pertemuan")[0]["n"] == 8


def test_db_private_rusak_halaman_tetap_utuh_tanpa_kartu(siap):
    _aktifkan(siap, siap.a)
    s = _slot()
    Path(_berkas_private()).write_bytes(b"bukan berkas sqlite " * 64)
    t = _teks(halaman(siap, siap.a))
    assert "Pilih paket" in t and JUDUL not in t
    assert kirim(siap, AJUKAN, siap.a, _form_ajukan(siap.a, s))[0] == 503

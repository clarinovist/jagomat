"""Tautan "Jurnal dan kehadiran" di admin jadwal: hanya pertemuan sudah mulai dan tidak dibatalkan.

Data sintetis. Halaman admin tetap tanpa data baru selain tautan itu (tanpa form, tanpa kolom baru).
"""
import re

import jadwal_admin_pages as ui
from admin_pesanan_kit import minta_admin
from kelas_http_kit import jam, kidup, kmati, server  # noqa: F401
from test_jadwal_admin_http import (  # noqa: F401
    DETAIL,
    KELOMPOK,
    PENEMPATAN,
    _aktif,
    _baris,
    _buat_kelompok,
    _guru,
    _tempat_mini,
    _token,
    admin,
    siap,
)

RUTE_JURNAL = "/admin/jadwal/jurnal/"
TAUTAN_TEKS = "Jurnal dan kehadiran"
KINI = "2026-11-28T02:00:00"
LAMPAU = "2026-11-27T02:00:00"
BELUM = "2026-11-29T02:00:00"
SATU_DETIK_SEBELUM_MULAI = "2026-11-28T02:00:01"
GURU = {"akun_" + "9" * 32: "guru-satu"}
TOKEN = {"csrf": "c", "tinjauan": "t"}
TOKENS_KELOMPOK = {"ubah": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
TOKENS_BLOK = {"tempatkan": TOKEN, "lepas": TOKEN, "sesi_ubah": TOKEN, "sesi_batal": TOKEN}
POLA_HREF_JURNAL = re.compile(r'href="(/admin/jadwal/jurnal/[^"]*)"')


def _sesi(id_: int, mulai: str, dibatalkan: int = 0) -> dict:
    return {"id": id_, "ke": id_, "mulai": mulai, "menit": 60, "dibatalkan": dibatalkan}


def _detail(sesi: list) -> dict:
    return {"kelompok": {"id": "klp_" + "a" * 32, "paket": "mini", "nama": "Mini A",
                         "lokasi": "Ruang 1", "guru_id": "akun_" + "9" * 32, "kuota": 5},
            "anggota": [], "sesi": sesi, "terisi": 0}


def _ringkas_mini(sesi: list) -> dict:
    return {"kelompok_id": "klp_" + "a" * 32, "kelompok_nama": "Mini A", "kelompok_lokasi": "Ruang 1",
            "kelompok_guru": "akun_" + "9" * 32, "sesi": sesi}


def _ringkas_private(sesi: list) -> dict:
    return {"kelompok_id": None, "lokasi": "https://zoom.us/j/123456789",
            "guru_id": "akun_" + "9" * 32, "sesi": sesi}


def _anchor(sesi_id: int) -> str:
    return '<a class="admin-tautan" href="%s%d">%s</a>' % (RUTE_JURNAL, sesi_id, TAUTAN_TEKS)


def _halaman(sesi: list, kini=None) -> str:
    if kini is None:
        return ui.halaman_kelompok(_detail(sesi), GURU, TOKENS_KELOMPOK)
    return ui.halaman_kelompok(_detail(sesi), GURU, TOKENS_KELOMPOK, kini=kini)


def test_sesi_sudah_mulai_dan_aktif_mendapat_tautan_dengan_href_tepat():
    isi = _halaman([_sesi(7, LAMPAU)], kini=KINI)
    assert _anchor(7) in isi


def test_sesi_belum_mulai_tidak_mendapat_tautan():
    isi = _halaman([_sesi(7, BELUM)], kini=KINI)
    assert RUTE_JURNAL + "7" not in isi and TAUTAN_TEKS not in isi


def test_sesi_dibatalkan_tidak_mendapat_tautan_walau_sudah_lewat():
    isi = _halaman([_sesi(7, LAMPAU, dibatalkan=1)], kini=KINI)
    assert RUTE_JURNAL + "7" not in isi and TAUTAN_TEKS not in isi


def test_mulai_sama_dengan_kini_dianggap_sudah_mulai_dan_mendapat_tautan():
    isi = _halaman([_sesi(7, KINI)], kini=KINI)
    assert _anchor(7) in isi


def test_satu_detik_sebelum_mulai_belum_mendapat_tautan():
    isi = _halaman([_sesi(7, SATU_DETIK_SEBELUM_MULAI)], kini=KINI)
    assert RUTE_JURNAL + "7" not in isi


def test_tautan_hanya_untuk_pertemuan_yang_memenuhi_syarat_dan_tanpa_query():
    sesi = [_sesi(1, LAMPAU), _sesi(2, KINI), _sesi(3, BELUM), _sesi(4, LAMPAU, dibatalkan=1)]
    isi = _halaman(sesi, kini=KINI)
    assert POLA_HREF_JURNAL.findall(isi) == ["/admin/jadwal/jurnal/1", "/admin/jadwal/jurnal/2"]


def test_blok_private_memuat_tautan_hanya_untuk_pertemuan_sudah_mulai():
    ringkas = _ringkas_private([_sesi(5, LAMPAU), _sesi(6, BELUM)])
    isi = ui.blok_penempatan({"paket": "private"}, ringkas, [], GURU, True, TOKENS_BLOK, kini=KINI)
    assert _anchor(5) in isi and RUTE_JURNAL + "6" not in isi


def test_blok_kelompok_mini_di_detail_order_memuat_tautan_sudah_mulai():
    ringkas = _ringkas_mini([_sesi(8, LAMPAU), _sesi(9, BELUM)])
    isi = ui.blok_penempatan({"paket": "mini"}, ringkas, [], GURU, True, TOKENS_BLOK, kini=KINI)
    assert _anchor(8) in isi and RUTE_JURNAL + "9" not in isi


def test_tanpa_pertemuan_berlalu_keluaran_halaman_identik_dengan_tanpa_kini():
    sesi = [_sesi(i, BELUM) for i in range(1, 9)]
    tanpa = _halaman(sesi)
    dengan = _halaman(sesi, kini=KINI)
    assert dengan == tanpa and TAUTAN_TEKS not in tanpa


def test_tanpa_pertemuan_berlalu_keluaran_blok_private_identik_dengan_tanpa_kini():
    ringkas = _ringkas_private([_sesi(i, BELUM) for i in range(1, 9)])
    tanpa = ui.blok_penempatan({"paket": "private"}, ringkas, [], GURU, True, TOKENS_BLOK)
    dengan = ui.blok_penempatan({"paket": "private"}, ringkas, [], GURU, True, TOKENS_BLOK, kini=KINI)
    assert dengan == tanpa and TAUTAN_TEKS not in tanpa


def test_tautan_hanya_menambah_anchor_tanpa_form_atau_kolom_baru():
    sesi = [_sesi(1, LAMPAU), _sesi(2, BELUM)]
    tanpa = _halaman(sesi)
    dengan = _halaman(sesi, kini=KINI)
    assert dengan.replace(_anchor(1), "") == tanpa
    assert dengan.count("<form") == tanpa.count("<form")
    assert dengan.count("<th") == tanpa.count("<th")


def test_http_halaman_kelompok_memuat_tautan_tepat_saat_pertemuan_pertama_dimulai(siap, admin, jam):  # noqa: F811
    kid = _buat_kelompok(siap, admin)
    assert _tempat_mini(siap, admin, _aktif("mini"), kid)[0] == 303
    sesi = _baris("SELECT id,mulai FROM jadwal_pertemuan WHERE kelompok_id=? ORDER BY ke,id", (kid,))
    jam.nilai = sesi[0]["mulai"]
    kode, isi, _ = minta_admin(siap, "%s?id=%s" % (KELOMPOK, kid), admin)
    assert kode == 200
    assert _anchor(sesi[0]["id"]) in isi
    assert RUTE_JURNAL + str(sesi[1]["id"]) not in isi


def test_http_halaman_kelompok_tanpa_tautan_sebelum_pertemuan_pertama(siap, admin):  # noqa: F811
    kid = _buat_kelompok(siap, admin)
    kode, isi, _ = minta_admin(siap, "%s?id=%s" % (KELOMPOK, kid), admin)
    assert kode == 200
    assert RUTE_JURNAL not in isi and TAUTAN_TEKS not in isi


def test_http_detail_order_private_memuat_tautan_sesi_sudah_mulai(siap, admin, jam):  # noqa: F811
    order = _aktif("private")
    data = _token(admin, "jadwal_tempatkan", {"order_id": order})
    data.update({"guru_id": _guru(), "tanggal": "2026-11-25", "jam": "16:30"})
    assert minta_admin(siap, PENEMPATAN, admin, data)[0] == 303
    sesi = _baris("SELECT id,mulai FROM jadwal_pertemuan WHERE order_id=? ORDER BY ke,id", (order,))
    jam.nilai = sesi[0]["mulai"]
    kode, isi, _ = minta_admin(siap, "%s?order=%s" % (DETAIL, order), admin)
    assert kode == 200
    assert _anchor(sesi[0]["id"]) in isi
    assert RUTE_JURNAL + str(sesi[1]["id"]) not in isi


def test_http_detail_order_mini_memuat_tautan_sesi_sudah_mulai(siap, admin, jam):  # noqa: F811
    kid = _buat_kelompok(siap, admin)
    order = _aktif("mini")
    assert _tempat_mini(siap, admin, order, kid)[0] == 303
    sesi = _baris("SELECT id,mulai FROM jadwal_pertemuan WHERE kelompok_id=? ORDER BY ke,id", (kid,))
    jam.nilai = sesi[0]["mulai"]
    kode, isi, _ = minta_admin(siap, "%s?order=%s" % (DETAIL, order), admin)
    assert kode == 200
    assert _anchor(sesi[0]["id"]) in isi
    assert RUTE_JURNAL + str(sesi[1]["id"]) not in isi

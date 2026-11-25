"""Kartu jadwal pertemuan di /murid/paket lewat HTTP nyata: hanya milik anak sesi, gagal-diam, escape, tanpa id/guru.

Data sintetis. Jadwal ditempatkan lewat store (admin) di DB admin sintetis; halaman dibaca sebagai akun murid.
"""
from __future__ import annotations

import re
import sqlite3

import pytest

import admin_store
import jadwal_store as js
import kelas_putusan
import kelas_store
import schema_jadwal
from bukti_kit import JPEG, PNG
from kelas_http_kit import (AWAL, ADMIN, M, bukti_terakhir, buat_dan_unggah, buat_murid, halaman,  # noqa: F401
                            jam, kidup, kmati, minta_mentah, server)

GURU = "akun_" + "9" * 32
TANGGAL = "2026-11-24"
SEBELUM = "<h2>Jadwal pertemuan</h2>"


def teks(isi):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", isi.rsplit("</style>", 1)[-1]))


@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    return kidup


def _aktifkan(server, murid, kode, isi):
    order_id = buat_dan_unggah(server, murid, kode, isi)
    with kelas_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, order_id, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(order_id))
    return order_id


def _kelompok(lokasi, nama="Mini A"):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=lokasi, guru_id=GURU, kuota=5,
                                tanggal=TANGGAL, jam="09:00", sekarang=AWAL)


def _tempat_mini(order_id, kelompok_id):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.tempatkan(kon, ADMIN, order_id, kelompok_id=kelompok_id, sekarang=AWAL)


def _tempat_privat(order_id):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.tempatkan(kon, ADMIN, order_id, guru_id=GURU, tanggal=TANGGAL, jam="16:30", sekarang=AWAL)


def test_kartu_jadwal_mini_tampil_untuk_anak_pemilik(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok("Ruang Melati"))
    isi = halaman(siap, siap.a)
    t = teks(isi)
    assert SEBELUM in isi and "Lokasi: Ruang Melati" in t
    assert len(re.findall(r"Pertemuan [1-8] ·", t)) == 8
    assert "Pertemuan 1 · 24 November 2026 pukul 09.00 WIB" in t
    assert "Pertemuan 8 · 18 Desember 2026 pukul 09.00 WIB" in t
    assert "aktif sampai" in t                                  # halaman lama tetap utuh


def test_kartu_jadwal_private_lokasi_online_dan_label_dibatalkan(siap):
    order_id = _aktifkan(siap, siap.a, "private", JPEG)
    _tempat_privat(order_id)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        sesi = js.ringkas_order(kon, order_id)["sesi"][2]["id"]
        js.batalkan_pertemuan(kon, ADMIN, sesi, batal=True, sekarang=AWAL)
    t = teks(halaman(siap, siap.a))
    assert "Lokasi: Online" in t and "Pertemuan 1 · 24 November 2026 pukul 16.30 WIB" in t
    assert t.count("Dibatalkan") == 1 and re.search(r"Pertemuan 3 · [^·]+WIB · Dibatalkan", t)


def test_anak_lain_tidak_melihat_jadwal_anak_lain_dan_kueri_diabaikan(siap, jam):  # noqa: F811
    punya_a = _aktifkan(siap, siap.a, "mini", JPEG)
    jam.maju_jam(1)
    punya_b = _aktifkan(siap, siap.b, "mini", PNG)              # lebih baru dari milik A
    _tempat_mini(punya_a, _kelompok("Ruang Alfa", "Mini A"))
    _tempat_mini(punya_b, _kelompok("Ruang Beta", "Mini B"))
    a, b = teks(halaman(siap, siap.a)), teks(halaman(siap, siap.b))
    assert "Lokasi: Ruang Alfa" in a and "Ruang Beta" not in a
    assert "Lokasi: Ruang Beta" in b and "Ruang Alfa" not in b
    kode, isi, _ = minta_mentah(siap, M + "?siswa_id=%d&order=%s" % (siap.b.siswa_id, punya_b), siap.a.akun)
    assert kode == 200 and "Ruang Beta" not in isi and "Ruang Alfa" in isi


def test_kartu_jadwal_mini_tautan_sah_jadi_tautan_kelas_aman(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok("https://us02web.zoom.us/j/123?pwd=abc"))
    isi = halaman(siap, siap.a)
    assert 'href="https://us02web.zoom.us/j/123?pwd=abc"' in isi
    assert 'target="_blank" rel="noopener noreferrer nofollow"' in isi
    assert "Tautan kelas: https://us02web.zoom.us/j/123?pwd=abc" in teks(isi)


def test_kartu_jadwal_mini_lokasi_db_berbahaya_tidak_jadi_anchor(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok("javascript:alert(1)"))
    isi = halaman(siap, siap.a)
    assert SEBELUM in isi and 'target="_blank"' not in isi and 'href="javascript:' not in isi
    assert "Lokasi: javascript:alert(1)" in teks(isi)


def test_anak_tanpa_jadwal_tidak_melihat_kartu_walau_anak_lain_punya(siap):
    _tempat_mini(_aktifkan(siap, siap.b, "mini", PNG), _kelompok("Ruang Beta"))
    isi = halaman(siap, siap.a)
    assert SEBELUM not in isi and "Ruang Beta" not in isi


def test_paket_aktif_tanpa_penempatan_tetap_halaman_lama_tanpa_kartu(siap):
    _aktifkan(siap, siap.a, "mini", JPEG)
    isi = halaman(siap, siap.a)
    assert SEBELUM not in isi and "aktif sampai" in teks(isi) and "Daftar paket ini" in isi


def test_jadwal_belum_dipasang_halaman_tetap_200_tanpa_kartu(kidup):
    murid = buat_murid(kidup, "murid-a", "Anak Alfa")
    _aktifkan(kidup, murid, "mini", JPEG)
    isi = halaman(kidup, murid)
    assert SEBELUM not in isi and "aktif sampai" in teks(isi)


def test_jadwal_rusak_parsial_halaman_tetap_200_tanpa_kartu(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok("Ruang Melati"))
    kon = sqlite3.connect(admin_store.BAWAAN)
    kon.execute("DROP TABLE jadwal_pertemuan")
    kon.commit()
    kon.close()
    kode, isi, _ = minta_mentah(siap, M, siap.a.akun)
    assert kode == 200 and SEBELUM not in isi and "aktif sampai" in teks(isi) and "Traceback" not in isi


def test_galat_tagihan_tidak_ditelan_walau_jadwal_gagal_diam(siap):
    kon = sqlite3.connect(admin_store.BAWAAN)
    kon.execute("DROP TABLE kelas_akses")                       # kelas rusak: bukan urusan jadwal
    kon.commit()
    kon.close()
    assert minta_mentah(siap, M, siap.a.akun)[0] == 503


def test_sakelar_mati_rute_tetap_seperti_rute_tak_dikenal(siap, monkeypatch):
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok("Ruang Melati"))
    monkeypatch.delenv("PAKET_BELAJAR")
    asing = minta_mentah(siap, "/murid/tidak-ada-rute", siap.a.akun)[:2]
    assert minta_mentah(siap, M, siap.a.akun)[:2] == asing
    assert "Ruang Melati" not in asing[1]


def test_tidak_ada_id_guru_kelompok_atau_order_di_html(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    kid = _kelompok("Ruang Melati")
    _tempat_mini(order_id, kid)
    isi = halaman(siap, siap.a)
    for rahasia in ("akun_", "klp_", "kor_", GURU, kid, order_id, "Anak Alfa", str(siap.a.id_akun)):
        assert rahasia not in isi, rahasia


def test_lokasi_berbahaya_ter_escape(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok("<script>alert(1)</script>"))
    isi = halaman(siap, siap.a)
    assert "<script>alert(1)" not in isi and "&lt;script&gt;alert(1)&lt;/script&gt;" in isi

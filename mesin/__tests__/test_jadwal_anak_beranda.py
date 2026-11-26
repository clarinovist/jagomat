"""Kartu "Sesi berikutnya" di beranda anak (`/murid`) lewat HTTP nyata: waktu, durasi, nama login guru; tanpa tautan/id.

Data sintetis: akun murid dan guru di berkas sandi sementara, jadwal di DB admin sintetis, sakelar PAKET_BELAJAR
lewat fixture `kidup`. Tanpa jaringan ke luar, tanpa data asli.
"""
from __future__ import annotations

import contextlib
import html as pustaka_html
import re
import sqlite3
import types

import pytest

import admin_store
import auth
import guru_status
import jadwal_anak_kartu as kartu_modul
import jadwal_store as js
import kelas_putusan
import kelas_store
import schema_jadwal
import student_pages
from bukti_kit import JPEG, PNG
from kelas_http_kit import (ADMIN, AWAL, bukti_terakhir, buat_dan_unggah, buat_murid, jam, kidup,  # noqa: F401
                            kmati, minta_mentah, server)

BERANDA = "/murid"
GURU_A = "pengajar-alfa"
GURU_B = "pengajar-beta"
SANDI_GURU = "sandi-guru-jadwal-sintetis-123"
TANGGAL = "2026-11-24"                       # 09.00 WIB = 02.00 UTC
WAKTU_PERTAMA = "24 November 2026 pukul 09.00 WIB"
GURU_TIDAK_ADA = "akun_" + "7" * 32
WAKTU_NONAKTIF = 1_800_000_000
MAJU_KE_SESI_BERJALAN = 23.25                # 24 Nov 02.15 UTC: sesi pertama (02.00 UTC) sedang berlangsung


@pytest.fixture()
def siap(kidup):  # noqa: F811
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    kidup.a = buat_murid(kidup, "murid-a", "Anak Alfa")
    kidup.b = buat_murid(kidup, "murid-b", "Anak Beta")
    return kidup


def _guru(pengguna: str) -> str:
    auth.tambah_akun(pengguna, SANDI_GURU, "guru")
    return auth.cari_akun(pengguna)["id_akun"]


def _aktifkan(server_, murid, kode, isi):
    order_id = buat_dan_unggah(server_, murid, kode, isi)
    with kelas_store.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kelas_putusan.setujui(kon, order_id, ADMIN, AWAL, bukti_dilihat=bukti_terakhir(order_id))
    return order_id


def _kelompok(guru_id, nama="Mini A", lokasi="Ruang Melati"):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi=lokasi, guru_id=guru_id, kuota=5,
                                tanggal=TANGGAL, jam="09:00", sekarang=AWAL)


def _tempat_mini(order_id, kelompok_id):
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        js.tempatkan(kon, ADMIN, order_id, kelompok_id=kelompok_id, sekarang=AWAL)


def _ubah_admin(sql, parameter=()):
    with contextlib.closing(sqlite3.connect(admin_store.BAWAAN)) as kon:
        kon.execute(sql, parameter)
        kon.commit()


def _beranda(server_, murid) -> str:
    kode, isi, _ = minta_mentah(server_, BERANDA, murid.akun)
    assert kode == 200, kode
    return isi


def _kartu(isi: str) -> str:
    cocok = re.search(r"<section[^>]*judul-jadwal-anak.*?</section>", isi, re.S)
    return "" if cocok is None else cocok.group(0)


def _teks(fragmen: str) -> str:
    return re.sub(r"\s+", " ", pustaka_html.unescape(re.sub(r"<[^>]+>", " ", fragmen))).strip()


def _menit_pertama(order_id) -> int:
    with js.buka(admin_store.BAWAAN) as kon:
        return js.ringkas_order(kon, order_id)["sesi"][0]["menit"]


def _nonaktifkan(pengguna: str, id_guru: str) -> None:
    revisi = auth.revisi_auth(auth.cari_akun(pengguna))
    guru_status.nonaktifkan(id_guru, revisi, ADMIN, WAKTU_NONAKTIF)


# --- isi kartu ---------------------------------------------------------------------------------

def test_beranda_menampilkan_sesi_berikutnya_waktu_durasi_dan_nama_guru(siap):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok(_guru(GURU_A)))
    t = _teks(_kartu(_beranda(siap, siap.a)))
    assert "Sesi berikutnya" in t and WAKTU_PERTAMA in t
    assert "Durasi: %d menit" % _menit_pertama(order_id) in t
    assert "Guru: pengajar-alfa" in t
    assert "Sedang berlangsung" not in t


def test_sedang_berlangsung_ditandai_di_beranda(siap, jam):  # noqa: F811
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(_guru(GURU_A)))
    jam.maju_jam(MAJU_KE_SESI_BERJALAN)
    t = _teks(_kartu(_beranda(siap, siap.a)))
    assert "Sedang berlangsung" in t and WAKTU_PERTAMA in t


def test_kartu_tanpa_tautan_lokasi_atau_id(siap):
    guru = _guru(GURU_A)
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    kid = _kelompok(guru, lokasi="https://us02web.zoom.us/j/123?pwd=abc")
    _tempat_mini(order_id, kid)
    isi = _beranda(siap, siap.a)
    kartu = _kartu(isi)
    assert kartu
    for terlarang in ("<a ", "href", "http", "zoom", "<form", "<button", "klp_", "kor_", "akun_",
                      kid, order_id, guru, str(siap.a.id_akun)):
        assert terlarang not in kartu, terlarang
    assert "klp_" not in isi and "kor_" not in isi


def test_anak_lain_tidak_melihat_jadwal_anak_lain(siap, jam):  # noqa: F811
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(_guru(GURU_A), nama="Mini A"))
    jam.maju_jam(1)
    _tempat_mini(_aktifkan(siap, siap.b, "mini", PNG), _kelompok(_guru(GURU_B), nama="Mini B"))
    a = _teks(_kartu(_beranda(siap, siap.a)))
    b = _teks(_kartu(_beranda(siap, siap.b)))
    assert "Guru: pengajar-alfa" in a and "pengajar-beta" not in a
    assert "Guru: pengajar-beta" in b and "pengajar-alfa" not in b


# --- keadaan yang tanpa kartu ------------------------------------------------------------------

def test_anak_tanpa_penempatan_tanpa_kartu_walau_anak_lain_punya(siap, jam):  # noqa: F811
    _aktifkan(siap, siap.a, "mini", JPEG)
    jam.maju_jam(1)                  # order_terakhir() memilih yang terbaru: butuh waktu beda, bukan tie acak
    _tempat_mini(_aktifkan(siap, siap.b, "mini", PNG), _kelompok(_guru(GURU_A)))
    isi = _beranda(siap, siap.a)
    assert _kartu(isi) == "" and "Sesi berikutnya" not in isi


def test_sakelar_mati_tanpa_kartu_dan_halaman_sama_seperti_tanpa_penempatan(siap, monkeypatch):
    order_id = _aktifkan(siap, siap.a, "mini", JPEG)
    _tempat_mini(order_id, _kelompok(_guru(GURU_A)))
    monkeypatch.delenv("PAKET_BELAJAR")
    dengan_jadwal = _beranda(siap, siap.a)
    _ubah_admin("DELETE FROM jadwal_penempatan WHERE order_id=?", (order_id,))
    tanpa_penempatan = _beranda(siap, siap.a)
    assert "Sesi berikutnya" not in dengan_jadwal
    assert dengan_jadwal == tanpa_penempatan


def test_db_admin_belum_dipasang_halaman_200_tanpa_kartu(kidup):  # noqa: F811
    murid = buat_murid(kidup, "murid-a", "Anak Alfa")
    _aktifkan(kidup, murid, "mini", JPEG)
    kode, isi, _ = minta_mentah(kidup, BERANDA, murid.akun)
    assert kode == 200 and "Sesi berikutnya" not in isi


def test_galat_baca_jadwal_gagal_diam_halaman_tetap_200(siap):
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(_guru(GURU_A)))
    _ubah_admin("DROP TABLE jadwal_pertemuan")
    kode, isi, _ = minta_mentah(siap, BERANDA, siap.a.akun)
    assert kode == 200 and "Sesi berikutnya" not in isi and "Traceback" not in isi


# --- guru: nonaktif, tidak ada, dan nama yang di-escape ----------------------------------------

def test_guru_nonaktif_kartu_tanpa_baris_guru(siap):
    guru = _guru(GURU_A)
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(guru))
    _nonaktifkan(GURU_A, guru)
    isi = _beranda(siap, siap.a)
    t = _teks(_kartu(isi))
    assert "Sesi berikutnya" in t and "Guru:" not in t and GURU_A not in isi


def test_guru_tidak_ada_kartu_tanpa_baris_guru(siap):
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(GURU_TIDAK_ADA))
    isi = _beranda(siap, siap.a)
    t = _teks(_kartu(isi))
    assert "Sesi berikutnya" in t and "Guru:" not in t and GURU_TIDAK_ADA not in isi


def test_akun_bukan_guru_tidak_pernah_ditampilkan_namanya(siap, kidup):  # noqa: F811
    akun_anak_lain = buat_murid(kidup, "murid-c", "Anak Gamma").id_akun
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(akun_anak_lain))
    isi = _beranda(siap, siap.a)
    t = _teks(_kartu(isi))
    assert "Sesi berikutnya" in t and "Guru:" not in t
    assert "murid-c" not in isi and akun_anak_lain not in isi


def test_render_meng_escape_nama_guru_dan_tanpa_baris_guru_bila_kosong():
    sesi = {"mulai": "2026-11-24T02:00:00", "menit": 90, "berlangsung": False}
    dengan_nama = kartu_modul.kartu_html(sesi, "<b>x</b>")
    tanpa_nama = kartu_modul.kartu_html(sesi, None)
    assert "<b>x</b>" not in dengan_nama and "&lt;b&gt;x&lt;/b&gt;" in dengan_nama
    assert "Guru:" not in tanpa_nama and "Sesi berikutnya" in tanpa_nama


def test_render_menandai_sedang_berlangsung_dan_tanpa_tautan():
    sesi = {"mulai": "2026-11-24T02:00:00", "menit": 90, "berlangsung": True}
    fragmen = kartu_modul.kartu_html(sesi, "pengajar-alfa")
    assert "Sedang berlangsung" in fragmen
    assert all(terlarang not in fragmen for terlarang in ("<a ", "href", "<button", "<form", "<script"))


# --- halaman beranda: kartu kosong tidak mengubah bytes -------------------------------------------

def test_kartu_jadwal_kosong_tidak_mengubah_halaman(siap):
    with siap.buka() as kon:
        tanpa = student_pages.halaman_daftar_sesi_baru(kon, siap.a.siswa_id, siap.a.akun[0])
        dengan = student_pages.halaman_daftar_sesi_baru(kon, siap.a.siswa_id, siap.a.akun[0], kartu_jadwal="")
    assert tanpa == dengan


def test_kartu_jadwal_disisip_setelah_kartu_harian(siap):
    with siap.buka() as kon:
        isi = student_pages.halaman_daftar_sesi_baru(
            kon, siap.a.siswa_id, siap.a.akun[0],
            kartu_harian='<i id="uji-harian"></i>', kartu_jadwal='<i id="uji-jadwal"></i>').decode("utf-8")
    assert isi.index('id="uji-harian"') < isi.index('id="uji-jadwal"')


def test_kartu_jadwal_tampil_sebelum_kartu_utama_beranda(siap):
    """Kartu jadwal di atas isi utama beranda (di sini kartu keadaan kosong 'Siap untuk latihan pertama?')."""
    with siap.buka() as kon:
        isi = student_pages.halaman_daftar_sesi_baru(
            kon, siap.a.siswa_id, siap.a.akun[0], kartu_jadwal='<i id="uji-jadwal"></i>').decode("utf-8")
    assert "Siap untuk latihan pertama?" in isi
    assert isi.index('id="uji-jadwal"') < isi.index("Siap untuk latihan pertama?")


# --- berkas akun rusak: elemen bukan dict dilewati, beranda tetap 200 ----------------------------

def _pakai_daftar_akun(monkeypatch, daftar) -> None:
    """Ganti pembaca akun HANYA untuk modul kartu; `auth` global tetap dipakai login dan sesi."""
    monkeypatch.setattr(kartu_modul, "auth", types.SimpleNamespace(muat_akun=lambda *_a, **_k: daftar))


def test_guru_valid_tetap_ditemukan_walau_daftar_akun_berisi_elemen_bukan_dict(siap, monkeypatch):
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(_guru(GURU_A)))
    _pakai_daftar_akun(monkeypatch, ["rusak", None, 7] + auth.muat_akun())
    t = _teks(_kartu(_beranda(siap, siap.a)))
    assert "Sesi berikutnya" in t and "Guru: pengajar-alfa" in t


def test_daftar_akun_hanya_elemen_bukan_dict_beranda_200_dengan_kartu_tanpa_baris_guru(siap, monkeypatch):
    _tempat_mini(_aktifkan(siap, siap.a, "mini", JPEG), _kelompok(_guru(GURU_A)))
    _pakai_daftar_akun(monkeypatch, ["rusak", None, 7])
    t = _teks(_kartu(_beranda(siap, siap.a)))
    assert "Sesi berikutnya" in t and "Guru:" not in t

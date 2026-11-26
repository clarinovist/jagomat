"""Jadwal saya dan Kelas saya (guru, baca-saja) lewat HTTP: kepemilikan, 404 identik, tanpa bocor, tanpa efek samping.

Kasus H1-H8 dari plan Fase 1. Data sepenuhnya sintetis: akun guru dan admin dari cek_http_kit, murid feby, dan anak
buatan. Jam dipatok lewat fixture `jam` (AWAL 23 Nov 2026 pukul 10.00 WIB), jadi sesi Mini 21 Nov sudah lewat.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

import admin_store
import auth
import database
import jadwal_store as js
import kelas_kit
import schema_jadwal
import schema_tagihan_catatan
from cek_http_kit import AKUN_A, AKUN_ADMIN, AKUN_B, AKUN_MURID, id_akun, server, tambah_anak  # noqa: F401
from harian_kit import jam  # noqa: F401
from kelas_http_kit import pasang_skema

ADMIN = "admin_sintetis"
LOKASI_MEET = "https://meet.google.com/abc-defg-hij"
LOKASI_ZOOM = "https://zoom.us/j/123456789"
TIDAK_ADA = "/guru/tidak-ada"
KELAS_TIDAK_ADA = "/guru/kelas/klp_" + "0" * 32
KELAS_CACAT = "/guru/kelas/bukan-id"
PERLU_MASUK = "perlu masuk"


def _tempatkan_mini(kon, kelompok_id, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)


def _tempatkan_privat(kon, guru, siswa, n, tanggal, jam="16:30"):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=guru, tanggal=tanggal, jam=jam,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)


def _lunas_mini_akses_lewat(kon, siswa, n):
    """Order Mini lunas dengan masa akses sebulan yang berakhir 19 Nov (disetujui 19 Okt, sebelum jam uji 23 Nov)."""
    tagihan, bukti_id = kelas_kit.menunggu(kon, siswa, "mini", n, sekarang="2026-10-19T09:00:00",
                                           unggah_pada="2026-10-19T09:30:00")
    kelas_kit.setuju(kon, tagihan, bukti_id, sekarang="2026-10-19T10:00:00")
    return tagihan.order_id


def _tempatkan_mentah(kon, kelompok_id, order_id):
    """Penempatan langsung lewat SQL: tempatkan() memeriksa pertemuan terhadap masa akses, sedangkan order ini sengaja lewat."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                (order_id, kelompok_id, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))
    kon.commit()


def _isi_contoh(server):
    """Dua guru: A punya Mini Alfa (anak Alfa) dan Private (anak Beta); B punya Mini Beta dan Private (anak Delta)."""
    anak = {
        "alfa": tambah_anak(server, "Anak Sintetis Alfa", "guru", None),
        "beta": tambah_anak(server, "Anak Sintetis Beta", "guru", None),
        "gamma": tambah_anak(server, "Anak Sintetis Gamma", "guru-b", None),
        "delta": tambah_anak(server, "Anak Sintetis Delta", "guru-b", None),
    }
    guru_a, guru_b = id_akun(AKUN_A), id_akun(AKUN_B)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        kid_a = js.buat_kelompok(kon, ADMIN, nama="Mini Alfa", lokasi=LOKASI_MEET, guru_id=guru_a, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        kid_b = js.buat_kelompok(kon, ADMIN, nama="Mini Beta", lokasi=LOKASI_ZOOM, guru_id=guru_b, kuota=5,
                                 tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        _tempatkan_mini(kon, kid_a, anak["alfa"], n=1)
        _tempatkan_privat(kon, guru_a, anak["beta"], n=2, tanggal="2026-11-25")
        _tempatkan_mini(kon, kid_b, anak["gamma"], n=3)
        _tempatkan_privat(kon, guru_b, anak["delta"], n=4, tanggal="2026-11-26", jam="10:00")
        kon.commit()
    return {"kid_a": kid_a, "kid_b": kid_b}


@pytest.fixture()
def jadwal(server, jam):
    pasang_skema(admin_store.BAWAAN)
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    schema_tagihan_catatan.migrasikan(admin_store.BAWAAN)
    return _isi_contoh(server)


def _hash(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- H1: pemilik melihat data sendiri, tanpa id mentah ------------------------------------

def test_guru_pemilik_melihat_jadwal_dan_kelas_sendiri(server, jadwal):
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Mini Alfa" in isi and "Anak Sintetis Beta" in isi
    assert "24 November 2026 pukul 09.00 WIB" in isi
    assert "21 November 2026" not in isi
    assert "Mini Beta" not in isi and "Anak Sintetis Gamma" not in isi and "Anak Sintetis Delta" not in isi

    kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert kode == 200
    assert "Mini Alfa" in isi and "Mini Beta" not in isi

    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "Anak Sintetis Alfa" in isi and LOKASI_MEET in isi
    assert "Anak Sintetis Beta" not in isi


def test_halaman_guru_tidak_membocorkan_id_mentah(server, jadwal):
    for jalur in ("/guru/jadwal", "/guru/kelas", "/guru/kelas/" + jadwal["kid_a"]):
        kode, isi, _ = server.minta(jalur, auth=AKUN_A)
        assert kode == 200, jalur
        assert "kor_" not in isi and "akun_" not in isi, jalur
        assert "siswa_id" not in isi and "order_id" not in isi, jalur
        tautan = re.findall(r'href="/guru/kelas/klp_[0-9a-f]{32}"', isi)
        assert isi.count("klp_") == len(tautan), jalur


# --- H2: guru lain mendapat 404 identik ---------------------------------------------------

def test_detail_kelas_milik_guru_lain_404_identik(server, jadwal):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_B)
    assert acuan[0] == 404
    for jalur in ("/guru/kelas/" + jadwal["kid_a"], KELAS_TIDAK_ADA, KELAS_CACAT):
        kode, isi, _ = server.minta(jalur, auth=AKUN_B)
        assert (kode, isi) == (acuan[0], acuan[1]), jalur
        assert "Mini Alfa" not in isi


# --- H3: tanpa efek samping pada DB ---------------------------------------------------------

def test_permintaan_guru_tidak_mengubah_db(server, jadwal):
    admin_db = Path(admin_store.BAWAAN)
    sebelum = (_hash(admin_db), _hash(server.db))
    for jalur, akun in (
        ("/guru/kelas/" + jadwal["kid_a"], AKUN_B),
        ("/guru/kelas/" + jadwal["kid_a"], AKUN_A),
        ("/guru/jadwal", AKUN_A),
        ("/guru/kelas", AKUN_A),
        (KELAS_TIDAK_ADA, AKUN_A),
    ):
        server.minta(jalur, auth=akun)
    assert (_hash(admin_db), _hash(server.db)) == sebelum


# --- H4: parameter URL tidak mengganti pemilik -------------------------------------------

def test_guru_id_di_query_diabaikan(server, jadwal):
    for jalur in ("/guru/kelas", "/guru/jadwal"):
        acuan = server.minta(jalur, auth=AKUN_B)
        kode, isi, _ = server.minta(jalur + "?guru_id=" + id_akun(AKUN_A), auth=AKUN_B)
        assert (kode, isi) == (acuan[0], acuan[1]), jalur
        assert "Mini Alfa" not in isi and "Anak Sintetis Alfa" not in isi and "Anak Sintetis Beta" not in isi


# --- H5: selain guru pemilik -> 404 identik / 401 -----------------------------------------

@pytest.mark.parametrize("sufiks", ["/guru/jadwal", "/guru/kelas", "/guru/kelas/{kid_a}"])
def test_admin_mendapat_404_identik_rute_tak_dikenal(server, jadwal, sufiks):
    jalur = sufiks.format(kid_a=jadwal["kid_a"])
    acuan = server.minta(TIDAK_ADA, auth=AKUN_ADMIN)
    assert acuan[0] == 404
    kode, isi, _ = server.minta(jalur, auth=AKUN_ADMIN)
    assert (kode, isi) == (acuan[0], acuan[1]), jalur
    assert "Mini Alfa" not in isi


def test_murid_dan_anonim_ditolak_palang_sandi(server, jadwal):
    for akun in (AKUN_MURID, None):
        kode, isi, _ = server.minta("/guru/jadwal", auth=akun)
        assert kode == 401, akun
        assert PERLU_MASUK in isi.lower()
        assert "Mini Alfa" not in isi


def test_mode_lokal_tanpa_principal_404_identik_bukan_500(server, jadwal, monkeypatch):
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    monkeypatch.setattr(auth, "wajib_sandi", lambda: False)
    for jalur in ("/guru/jadwal", "/guru/kelas", "/guru/kelas/" + jadwal["kid_a"]):
        kode, isi, _ = server.minta(jalur)
        assert (kode, isi) == (acuan[0], acuan[1]), jalur


# --- H6: header respons privat ------------------------------------------------------------

def test_respons_guru_memakai_header_privat(server, jadwal):
    for jalur in ("/guru/jadwal", "/guru/kelas", "/guru/kelas/" + jadwal["kid_a"]):
        kode, _isi, tajuk = server.minta(jalur, auth=AKUN_A)
        assert kode == 200, jalur
        assert tajuk.get("Cache-Control") == "no-store", jalur
        assert tajuk.get("Referrer-Policy") == "no-referrer", jalur


# --- H9: anggota dengan masa akses lewat diberi tanda teks, nama tetap tampil ------------------

def test_anggota_akses_habis_diberi_tanda_teks_dan_nama_tetap_tampil(server, jadwal):
    siswa = tambah_anak(server, "Anak Sintetis Epsilon", "guru", None)
    with js.buka(admin_store.BAWAAN, tulis_data=True) as kon:
        order = _lunas_mini_akses_lewat(kon, siswa, n=9)
        _tempatkan_mentah(kon, jadwal["kid_a"], order)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "<li>Anak Sintetis Epsilon · Akses habis</li>" in isi
    assert "<li>Anak Sintetis Alfa</li>" in isi
    assert isi.count("Akses habis") == 1
    assert "Terisi 2 dari 5 anak." in isi
    assert "siswa_id" not in isi and "order_id" not in isi and "akun_" not in isi


# --- H7: DB admin belum dipasang atau rusak ------------------------------------------------

def test_db_admin_belum_dipasang_daftar_kosong_dan_detail_404(server):
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and "Belum ada jadwal." in isi
    kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert kode == 200 and "Belum ada kelas" in isi
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    assert server.minta(KELAS_TIDAK_ADA, auth=AKUN_A)[:2] == acuan[:2]


def test_db_admin_rusak_diperlakukan_belum_siap(server):
    Path(admin_store.BAWAAN).write_bytes(b"bukan basis data " * 64)
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200 and "Belum ada jadwal." in isi
    acuan = server.minta(TIDAK_ADA, auth=AKUN_A)
    assert server.minta(KELAS_TIDAK_ADA, auth=AKUN_A)[:2] == acuan[:2]


# --- H8: topbar guru ----------------------------------------------------------------------

def test_topbar_guru_memuat_dua_tautan_baru_dan_admin_tidak(server, jadwal):
    _kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert '<a href="/guru/jadwal" aria-current="page">Jadwal saya</a>' in isi
    assert '<a href="/guru/kelas">Kelas saya</a>' in isi

    _kode, isi, _ = server.minta("/guru/kelas", auth=AKUN_A)
    assert '<a href="/guru/kelas" aria-current="page">Kelas saya</a>' in isi

    _kode, isi, _ = server.minta("/guru", auth=AKUN_A)
    assert '<a href="/guru/jadwal">Jadwal saya</a>' in isi
    assert '<a href="/guru/kelas">Kelas saya</a>' in isi

    kode, isi, _ = server.minta("/admin", auth=AKUN_ADMIN)
    assert kode == 200
    assert "Jadwal saya" not in isi and "Kelas saya" not in isi


def test_latihan_tak_terbaca_nama_anak_memakai_placeholder(server, jadwal, monkeypatch, tmp_path):
    """latihan.db rusak (berkas ada, isinya bukan basis data): nama anak jadi placeholder, halaman tetap 200."""
    rusak = tmp_path / "latihan-rusak.db"
    rusak.write_bytes(b"bukan basis data " * 64)
    monkeypatch.setattr(database, "BAWAAN", rusak)
    kode, isi, _ = server.minta("/guru/kelas/" + jadwal["kid_a"], auth=AKUN_A)
    assert kode == 200
    assert "<li>Anak</li>" in isi
    assert "Anak Sintetis Alfa" not in isi
    kode, isi, _ = server.minta("/guru/jadwal", auth=AKUN_A)
    assert kode == 200
    assert "Private: Anak" in isi and "Anak Sintetis Beta" not in isi

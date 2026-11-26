"""Pembacaan jadwal guru (guru_jadwal_baca) pada DB admin sintetis: kepemilikan, order aktif, tanpa tulis.

Kasus B1-B5 dari plan Fase 1. Data sepenuhnya sintetis (akun_ buatan, anak nomor urut). Tidak membaca DB asli.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import admin_store_core
import guru_jadwal_baca as gb
import jadwal_store as js
import kelas_batal
import kelas_dasar
import kelas_kit
import kelas_status as ks
import schema_jadwal
import schema_tagihan_catatan

ADMIN = "admin_sintetis"
GURU_A = "akun_" + "a" * 32
GURU_B = "akun_" + "b" * 32
GURU_KOSONG = "akun_" + "c" * 32
KINI_LAMPAU = "2026-11-20T12:00:00"             # sebelum semua pertemuan contoh
KINI_SESI_PERTAMA_LEWAT = "2026-11-22T00:00:00"  # sesi Mini pertama (21 Nov 09.00 WIB) sudah lewat
KINI_AKSES_LEWAT = "2026-12-22T00:00:00"         # siswa 1 (akses berakhir 20 Des) sudah habis; siswa 9 (24 Des) belum
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
KELAS_TIDAK_SAH = ("klp_" + "f" * 32, "klp-bukan-id", None)
SQL_TULIS = ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER")


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    schema_tagihan_catatan.migrasikan(path)
    return path


def _mini(kon, nama, guru):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi="Ruang 1", guru_id=guru, kuota=5,
                            tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)


def _tempatkan_mini(kon, kelompok_id, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _tempatkan_privat(kon, guru, siswa, n, tanggal, jam="16:30"):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=guru, tanggal=tanggal, jam=jam,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _sisip_penempatan_mini_mentah(kon, order_id, kelompok_id):
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                (order_id, kelompok_id, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))
    kon.commit()


def _sisip_privat_mentah(kon, order_id, guru):
    """Penempatan + 8 sesi Private langsung lewat SQL (melewati domain) untuk order yang BELUM aktif."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                (order_id, guru, schema_jadwal.LOKASI_PRIVATE, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))
    for ke in range(1, 9):
        kon.execute("INSERT INTO jadwal_pertemuan(kelompok_id,order_id,ke,mulai,menit,dibatalkan,diubah,"
                    "diubah_oleh) VALUES(NULL,?,?,?,60,0,?,?)",
                    (order_id, ke, "2026-11-%02dT09:30:00" % (22 + ke), kelas_kit.KINI, ADMIN))
    kon.commit()


def _lunas_mini_pada(kon, siswa, n, dibuat, unggah, disetujui):
    """Order Mini lunas dengan masa akses satu bulan yang mulai pada `disetujui` (berakhir sebulan kemudian)."""
    tagihan, bukti_id = kelas_kit.menunggu(kon, siswa, "mini", n, sekarang=dibuat, unggah_pada=unggah)
    kelas_kit.setuju(kon, tagihan, bukti_id, sekarang=disetujui)
    return tagihan.order_id


def _akses_berakhir(kon, siswa_id):
    return kon.execute("SELECT berakhir FROM kelas_akses WHERE siswa_id=?", (siswa_id,)).fetchone()[0]


def _isi_contoh(kon):
    """Dua guru, masing-masing satu Mini dan satu Private (anak 1 dan 2 untuk A; 3 dan 4 untuk B)."""
    kid_a = _mini(kon, "Mini Alfa", GURU_A)
    kid_b = _mini(kon, "Mini Beta", GURU_B)
    _tempatkan_mini(kon, kid_a, siswa=1, n=1)
    _tempatkan_privat(kon, GURU_A, siswa=2, n=2, tanggal="2026-11-23")
    _tempatkan_mini(kon, kid_b, siswa=3, n=3)
    _tempatkan_privat(kon, GURU_B, siswa=4, n=4, tanggal="2026-11-24", jam="10:00")
    kon.commit()
    return {"kid_a": kid_a, "kid_b": kid_b}


@pytest.fixture()
def contoh(db):
    with js.buka(db, tulis_data=True) as kon:
        return _isi_contoh(kon)


def _ro(db):
    return js.buka(db)


# --- B1: kepemilikan ----------------------------------------------------------------------

def test_guru_hanya_melihat_pertemuan_miliknya(db, contoh):
    with _ro(db) as kon:
        a = gb.pertemuan_mendatang(kon, GURU_A, KINI_LAMPAU)
        b = gb.pertemuan_mendatang(kon, GURU_B, KINI_LAMPAU)
    assert {p["kelompok_id"] for p in a if p["jenis"] == "kelompok"} == {contoh["kid_a"]}
    assert {p["kelompok_id"] for p in b if p["jenis"] == "kelompok"} == {contoh["kid_b"]}
    assert {p["siswa_id"] for p in a if p["jenis"] == "privat"} == {2}
    assert {p["siswa_id"] for p in b if p["jenis"] == "privat"} == {4}
    assert len(a) == 16 and len(b) == 16


def test_daftar_kelas_hanya_kelompok_milik_guru(db, contoh):
    with _ro(db) as kon:
        a = gb.daftar_kelas(kon, GURU_A, KINI_LAMPAU)
        b = gb.daftar_kelas(kon, GURU_B, KINI_LAMPAU)
        kosong = gb.daftar_kelas(kon, GURU_KOSONG, KINI_LAMPAU)
    assert [k["id"] for k in a] == [contoh["kid_a"]]
    assert [k["id"] for k in b] == [contoh["kid_b"]]
    assert kosong == []


def test_guru_tanpa_jadwal_mendapat_daftar_kosong(db, contoh):
    with _ro(db) as kon:
        assert gb.pertemuan_mendatang(kon, GURU_KOSONG, KINI_LAMPAU) == []


# --- B2: mendatang dan dibatalkan ---------------------------------------------------------

def test_pertemuan_lampau_tidak_masuk_dan_pembatalan_ditandai(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        sesi = js.detail_kelompok(kon, contoh["kid_a"])["sesi"]
        kedua = next(s for s in sesi if s["ke"] == 2)
        js.batalkan_pertemuan(kon, ADMIN, kedua["id"], batal=True, sekarang=kelas_kit.KINI)
        kon.commit()
    with _ro(db) as kon:
        mendatang = gb.pertemuan_mendatang(kon, GURU_A, KINI_SESI_PERTAMA_LEWAT)
    mini = [p for p in mendatang if p["jenis"] == "kelompok"]
    assert len(mini) == 7
    assert min(p["mulai"] for p in mendatang) >= KINI_SESI_PERTAMA_LEWAT
    assert [p["mulai"] for p in mendatang] == sorted(p["mulai"] for p in mendatang)
    assert [p["ke"] for p in mini if p["dibatalkan"]] == [2]


# --- B3: order tidak aktif tidak tampil ---------------------------------------------------

def test_order_tidak_aktif_tidak_tampil_sebagai_anggota_atau_pertemuan(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        menunggu = kelas_kit.menunggu(kon, 5, "mini", n=5)[0].order_id
        _sisip_penempatan_mini_mentah(kon, menunggu, contoh["kid_a"])
        belum_bayar = kelas_kit.tagih(kon, 6, "private").order_id
        _sisip_privat_mentah(kon, belum_bayar, GURU_A)
        kedaluwarsa = kelas_kit.sisip_order(kon, 7, siswa=7, paket="private", dibuat="2026-11-18T09:00:00",
                                            kedaluwarsa="2026-11-19T00:00:00")
        _sisip_privat_mentah(kon, kedaluwarsa, GURU_A)
        dibatalkan = kelas_kit.tagih(kon, 8, "private").order_id
        kelas_batal.batalkan_tagihan(kon, kelas_kit.AKUN_A, 8, "private", kelas_kit.KINI)
        _sisip_privat_mentah(kon, dibatalkan, GURU_A)
        kon.commit()
    with _ro(db) as kon:
        # Pastikan setiap order uji memang TIDAK aktif, supaya tes ini bermakna.
        for oid in (menunggu, belum_bayar, kedaluwarsa, dibatalkan):
            order = ks.baris_order(kon, oid)
            assert ks.status_dari(order, ks.fakta_order(kon, oid), KINI_LAMPAU) != kelas_dasar.STATUS_AKTIF
        mendatang = gb.pertemuan_mendatang(kon, GURU_A, KINI_LAMPAU)
        detail = gb.detail_kelas(kon, GURU_A, contoh["kid_a"], KINI_LAMPAU)
        daftar = gb.daftar_kelas(kon, GURU_A, KINI_LAMPAU)
    assert {p["siswa_id"] for p in mendatang if p["jenis"] == "privat"} == {2}
    assert len(mendatang) == 16
    assert detail["anggota"] == [{"siswa_id": 1, "akses_habis": False}]
    assert daftar[0]["terisi"] == 1


# --- B4: detail milik lain, tak ada, dan cacat -> None ------------------------------------

def test_detail_kelas_milik_lain_tak_ada_dan_cacat_sama_hasilnya(db, contoh):
    with _ro(db) as kon:
        hasil = [gb.detail_kelas(kon, GURU_B, contoh["kid_a"], KINI_LAMPAU)]
        hasil += [gb.detail_kelas(kon, GURU_A, kelompok, KINI_LAMPAU) for kelompok in KELAS_TIDAK_SAH]
        milik = gb.detail_kelas(kon, GURU_A, contoh["kid_a"], KINI_LAMPAU)
    assert hasil == [None, None, None, None]
    assert milik["nama"] == "Mini Alfa"
    assert len(milik["sesi"]) == 8
    assert milik["anggota"] == [{"siswa_id": 1, "akses_habis": False}]


# --- akses habis: anggota Mini dengan masa akses lewat tetap tampil dan diberi tanda ------------

def _tambah_anggota_akses_24_des(kon, kid_a):
    """Siswa 9 disetujui 24 Nov (akses berakhir 24 Des 10.00 UTC), ditempatkan mentah ke kelas Alfa."""
    order = _lunas_mini_pada(kon, 9, 9, dibuat="2026-11-24T09:00:00", unggah="2026-11-24T09:30:00",
                             disetujui="2026-11-24T10:00:00")
    _sisip_penempatan_mini_mentah(kon, order, kid_a)
    return order


def test_anggota_mini_ditandai_akses_habis_sesuai_masa_berlaku(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        _tambah_anggota_akses_24_des(kon, contoh["kid_a"])
    with _ro(db) as kon:
        # Kondisi uji: siswa 1 berakhir 20 Des 09.30 UTC, siswa 9 berakhir 24 Des 10.00 UTC.
        assert _akses_berakhir(kon, 1) == "2026-12-20T09:30:00"
        assert _akses_berakhir(kon, 9) == "2026-12-24T10:00:00"
        detail = gb.detail_kelas(kon, GURU_A, contoh["kid_a"], KINI_AKSES_LEWAT)
        terisi = gb.daftar_kelas(kon, GURU_A, KINI_AKSES_LEWAT)[0]["terisi"]
    # Urutan anggota mengikuti id order acak (`id_order_baru`), jadi dibandingkan menurut siswa_id.
    assert sorted(detail["anggota"], key=lambda a: a["siswa_id"]) == [
        {"siswa_id": 1, "akses_habis": True}, {"siswa_id": 9, "akses_habis": False}]
    assert terisi == 2


def test_akses_habis_tepat_di_batas_berakhir(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        _tambah_anggota_akses_24_des(kon, contoh["kid_a"])
    with _ro(db) as kon:
        berakhir = _akses_berakhir(kon, 9)
        sedetik_sebelumnya = (datetime.strptime(berakhir, FORMAT_WAKTU) - timedelta(seconds=1)).strftime(FORMAT_WAKTU)
        tepat = gb.detail_kelas(kon, GURU_A, contoh["kid_a"], berakhir)["anggota"]
        sebelum = gb.detail_kelas(kon, GURU_A, contoh["kid_a"], sedetik_sebelumnya)["anggota"]
    assert {"siswa_id": 9, "akses_habis": True} in tepat
    assert {"siswa_id": 9, "akses_habis": False} in sebelum


def test_order_aktif_tanpa_baris_akses_tidak_ditandai_habis(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        oid = kelas_kit.sisip_order(kon, 11, siswa=11, paket="mini")
        kelas_kit.sisip_tagihan(kon, oid)
        bukti_id = kelas_kit.sisip_bukti(kon, oid, 11)
        kelas_kit.sisip_verifikasi(kon, oid, bukti_id)
        _sisip_penempatan_mini_mentah(kon, oid, contoh["kid_a"])
    with _ro(db) as kon:
        # Kondisi uji: order lunas (aktif) tetapi tanpa baris kelas_akses.
        akses = kon.execute("SELECT COUNT(*) FROM kelas_akses WHERE order_id=?", (oid,)).fetchone()[0]
        status = ks.status_dari(ks.baris_order(kon, oid), ks.fakta_order(kon, oid), KINI_AKSES_LEWAT)
        detail = gb.detail_kelas(kon, GURU_A, contoh["kid_a"], KINI_AKSES_LEWAT)
    assert akses == 0 and status == kelas_dasar.STATUS_AKTIF
    assert {"siswa_id": 11, "akses_habis": False} in detail["anggota"]


# --- B5: tanpa tulis, tanpa berkas baru ---------------------------------------------------

def test_pembacaan_tidak_mengubah_isi_berkas_dan_tidak_menulis_sql(db, contoh):
    sebelum = Path(db).read_bytes()
    sql = []
    with _ro(db) as kon:
        kon.set_trace_callback(sql.append)
        gb.pertemuan_mendatang(kon, GURU_A, KINI_LAMPAU)
        gb.daftar_kelas(kon, GURU_A, KINI_LAMPAU)
        gb.detail_kelas(kon, GURU_A, contoh["kid_a"], KINI_LAMPAU)
        kon.set_trace_callback(None)
    assert Path(db).read_bytes() == sebelum
    assert sql, "tidak ada kueri yang tercatat"
    assert not [s for s in sql if s.lstrip().upper().startswith(SQL_TULIS)]


def test_db_tidak_ada_jadi_belum_siap_tanpa_membuat_berkas(tmp_path):
    hilang = tmp_path / "tidak-ada.db"
    with pytest.raises(admin_store_core.StoreBelumSiap):
        with js.buka(hilang):
            pass
    assert not hilang.exists()


def test_db_tanpa_skema_jadwal_jadi_belum_siap(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    with pytest.raises(admin_store_core.StoreBelumSiap):
        with js.buka(path):
            pass


# --- nama anak: placeholder untuk id yang hilang ------------------------------------------

def test_nama_siswa_memakai_placeholder_untuk_id_yang_hilang(tmp_path):
    path = tmp_path / "latihan.db"
    tulis = sqlite3.connect(str(path))
    tulis.execute("CREATE TABLE siswa(id INTEGER PRIMARY KEY, nama TEXT NOT NULL)")
    tulis.execute("INSERT INTO siswa(id, nama) VALUES(1, 'Anak Sintetis Satu')")
    tulis.commit()
    tulis.close()
    kon = sqlite3.connect(str(path))
    try:
        assert gb.PLACEHOLDER_NAMA == "Anak"
        assert gb.nama_siswa(kon, [1, 99]) == {1: "Anak Sintetis Satu", 99: "Anak"}
        assert gb.nama_siswa(kon, []) == {}
    finally:
        kon.close()

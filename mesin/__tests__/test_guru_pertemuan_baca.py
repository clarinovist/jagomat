"""Kepemilikan pertemuan guru (`guru_jadwal_baca.pertemuan_milik`) pada DB admin sintetis: SELECT saja.

Kasus P1-P8 dari plan Fase 2a-2: Mini dan Private milik guru A, guru B tidak punya akses (None), id tak sah atau
tak ada (None), anggota aktif dan masuk form (R4), akses habis, dibatalkan, order tak aktif, dan tanpa tulis.
Data sepenuhnya sintetis (akun buatan, anak nomor urut). Tidak membaca DB asli.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import guru_jadwal_baca as gb
import jadwal_store as js
import kelas_kit
import schema_jadwal
import schema_tagihan_catatan

ADMIN = "admin_sintetis"
GURU_A = "akun_" + "a" * 32
GURU_B = "akun_" + "b" * 32
# Sama dengan AWAL uji jam: sesi Mini ke-1 (21 Nov) sudah lewat, ke-2 (24 Nov) belum.
KINI = "2026-11-23T03:00:00"
ID_TIDAK_ADA = 999_999
ID_MAKS = 2 ** 63 - 1
KUNCI_KEMBALI = {"id", "jenis", "id_awal", "ke", "mulai", "menit", "dibatalkan", "nama_kelompok", "anggota"}
KUNCI_ANGGOTA = {"order_id", "siswa_id", "akses_habis"}


def _mini(kon, nama, guru):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi="Ruang 1", guru_id=guru, kuota=5,
                            tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)


def _tempatkan_mini(kon, kelompok_id, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _tempatkan_privat(kon, guru, siswa, n, tanggal="2026-11-25", jam="16:30"):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=guru, tanggal=tanggal, jam=jam,
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _id_pertemuan_mini(kon, kelompok_id, ke):
    return kon.execute("SELECT id FROM jadwal_pertemuan WHERE kelompok_id=? AND ke=?", (kelompok_id, ke)).fetchone()[0]


def _id_pertemuan_privat(kon, order_id, ke):
    return kon.execute("SELECT id FROM jadwal_pertemuan WHERE order_id=? AND ke=?", (order_id, ke)).fetchone()[0]


def _sisip_penempatan_mini(kon, order_id, kelompok_id, dibuat):
    """Penempatan Mini lewat SQL: melewati domain agar `dibuat` bisa diatur (order tidak aktif atau masuk terlambat)."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)", (order_id, kelompok_id, dibuat, dibuat, ADMIN, ADMIN))
    kon.commit()  # tutup transaksi sisipan sebelum domain membuka transaksinya sendiri


@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    schema_tagihan_catatan.migrasikan(path)
    return path


@pytest.fixture()
def contoh(db):
    """Guru A: Mini Alfa (anak 1) dan Private (anak 2). Guru B: Mini Beta (anak 3) dan Private (anak 4)."""
    with js.buka(db, tulis_data=True) as kon:
        kid_a = _mini(kon, "Mini Alfa", GURU_A)
        kid_b = _mini(kon, "Mini Beta", GURU_B)
        ord_a1 = _tempatkan_mini(kon, kid_a, siswa=1, n=1)
        ord_a2 = _tempatkan_privat(kon, GURU_A, siswa=2, n=2)
        _tempatkan_mini(kon, kid_b, siswa=3, n=3)
        ord_b2 = _tempatkan_privat(kon, GURU_B, siswa=4, n=4, tanggal="2026-11-26", jam="10:00")
        kon.commit()
        return {
            "kid_a": kid_a, "kid_b": kid_b, "ord_a1": ord_a1, "ord_a2": ord_a2, "ord_b2": ord_b2,
            "mini_a1": _id_pertemuan_mini(kon, kid_a, 1), "mini_a2": _id_pertemuan_mini(kon, kid_a, 2),
            "mini_b1": _id_pertemuan_mini(kon, kid_b, 1),
            "privat_a1": _id_pertemuan_privat(kon, ord_a2, 1), "privat_b1": _id_pertemuan_privat(kon, ord_b2, 1),
        }


def _milik(db, guru, pertemuan_id, kini=KINI):
    with js.buka(db) as kon:
        return gb.pertemuan_milik(kon, guru, pertemuan_id, kini)


# --- P1: pemilik mendapat pertemuan Mini dan Private miliknya ----------------------------------

def test_guru_pemilik_mendapat_pertemuan_mini_dan_privat_miliknya(db, contoh):
    mini = _milik(db, GURU_A, contoh["mini_a1"])
    privat = _milik(db, GURU_A, contoh["privat_a1"])

    assert set(mini) == KUNCI_KEMBALI and set(privat) == KUNCI_KEMBALI
    assert mini["jenis"] == "kelompok" and mini["nama_kelompok"] == "Mini Alfa"
    assert mini["id_awal"] == contoh["kid_a"] and mini["ke"] == 1 and mini["dibatalkan"] is False
    assert [a["siswa_id"] for a in mini["anggota"]] == [1]
    assert set(mini["anggota"][0]) == KUNCI_ANGGOTA
    assert mini["anggota"][0]["order_id"] == contoh["ord_a1"]
    assert privat["jenis"] == "privat" and privat["nama_kelompok"] is None
    assert privat["id_awal"] == contoh["ord_a2"]
    assert [a["siswa_id"] for a in privat["anggota"]] == [2]


# --- P2: guru lain dan pertemuan guru lain -> None (satu jalur, tanpa pembeda) -----------------

def test_guru_lain_mendapat_none_untuk_kedua_jenis(db, contoh):
    assert _milik(db, GURU_B, contoh["mini_a1"]) is None
    assert _milik(db, GURU_B, contoh["privat_a1"]) is None
    assert _milik(db, GURU_A, contoh["mini_b1"]) is None
    assert _milik(db, GURU_A, contoh["privat_b1"]) is None


# --- P3: id tidak sah atau tidak ada -> None ----------------------------------------------------

@pytest.mark.parametrize("pertemuan_id", [0, -1, True, 1.0, "1", None, ID_TIDAK_ADA, ID_MAKS, ID_MAKS + 1])
def test_id_tak_sah_atau_tak_ada_menghasilkan_none(db, contoh, pertemuan_id):
    assert _milik(db, GURU_A, pertemuan_id) is None


# --- P4: anggota Mini hanya order aktif dan yang masuk sebelum pertemuan mulai (R4) --------------

def test_anggota_mini_hanya_order_aktif_dan_masuk_sebelum_mulai(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        menunggu = kelas_kit.menunggu(kon, 5, "mini", n=5)[0].order_id
        _sisip_penempatan_mini(kon, menunggu, contoh["kid_a"], "2026-11-19T00:00:00")
        terlambat = kelas_kit.lunas(kon, 6, "mini", n=6).order_id
        _sisip_penempatan_mini(kon, terlambat, contoh["kid_a"], "2026-11-22T00:00:00")
        kon.commit()

    ke1 = _milik(db, GURU_A, contoh["mini_a1"])
    ke2 = _milik(db, GURU_A, contoh["mini_a2"])

    assert [a["siswa_id"] for a in ke1["anggota"]] == [1]
    assert sorted(a["siswa_id"] for a in ke2["anggota"]) == [1, 6]
    assert menunggu not in {a["order_id"] for a in ke2["anggota"]}


# --- P5: akses habis ditandai, akses berlaku tidak ---------------------------------------------

def _lunas_mini_akses_lewat(kon, siswa, n):
    """Order Mini yang disetujui 19 Okt, masa aksesnya habis sebelum KINI. `kelas_akses` tidak bisa diubah (ledger)."""
    tagihan, bukti_id = kelas_kit.menunggu(kon, siswa, "mini", n, sekarang="2026-10-19T09:00:00",
                                           unggah_pada="2026-10-19T09:30:00")
    kelas_kit.setuju(kon, tagihan, bukti_id, sekarang="2026-10-19T10:00:00")
    return tagihan.order_id


def test_akses_habis_ditandai_dan_akses_berlaku_tidak(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        lewat = _lunas_mini_akses_lewat(kon, 7, n=7)
        _sisip_penempatan_mini(kon, lewat, contoh["kid_a"], "2026-11-20T09:30:00")
        kon.commit()

    mini = _milik(db, GURU_A, contoh["mini_a1"])

    assert {a["order_id"]: a["akses_habis"] for a in mini["anggota"]} == {contoh["ord_a1"]: False, lewat: True}


# --- P6: pertemuan dibatalkan tetap terbaca, dengan tanda ---------------------------------------

def test_pertemuan_dibatalkan_tetap_terbaca_dengan_tanda(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=1 WHERE id=?", (contoh["mini_a1"],))
        kon.commit()

    hasil = _milik(db, GURU_A, contoh["mini_a1"])

    assert hasil is not None and hasil["dibatalkan"] is True


# --- P7: order privat tidak aktif -> pertemuan tetap milik guru, anggota kosong ---------------

def test_order_privat_tak_aktif_anggota_kosong(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        belum_bayar = kelas_kit.menunggu(kon, 7, "private", n=7)[0].order_id
        kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                    "diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                    (belum_bayar, GURU_A, schema_jadwal.LOKASI_PRIVATE, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))
        kon.execute("INSERT INTO jadwal_pertemuan(kelompok_id,order_id,ke,mulai,menit,dibatalkan,diubah,diubah_oleh) "
                    "VALUES(NULL,?,1,?,60,0,?,?)", (belum_bayar, "2026-11-25T09:30:00", kelas_kit.KINI, ADMIN))
        pertemuan_id = kon.execute("SELECT id FROM jadwal_pertemuan WHERE order_id=?", (belum_bayar,)).fetchone()[0]
        kon.commit()

    hasil = _milik(db, GURU_A, pertemuan_id)

    assert hasil is not None and hasil["jenis"] == "privat"
    assert hasil["anggota"] == []


# --- P8: pembacaan tidak menulis dan tidak mengubah isi berkas ---------------------------------

def test_pembacaan_tidak_mengubah_isi_berkas(db, contoh):
    sebelum = hashlib.sha256(Path(db).read_bytes()).hexdigest()

    for pertemuan_id in (contoh["mini_a1"], contoh["privat_a1"], ID_TIDAK_ADA):
        _milik(db, GURU_A, pertemuan_id)
        _milik(db, GURU_B, pertemuan_id)

    assert hashlib.sha256(Path(db).read_bytes()).hexdigest() == sebelum

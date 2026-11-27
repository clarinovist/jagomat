"""Pembacaan koreksi admin (2b): pertemuan berdasar id tanpa filter guru, anggota, nama anak, dan riwayat.

Data sepenuhnya sintetis (akun buatan, anak nomor urut, latihan.db kecil di tmp). Tes ini SELECT saja.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import admin_jurnal_koreksi_baca as ajk
import guru_jadwal_baca as gb
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as dasar
import jadwal_store as js
import kelas_catatan
import kelas_kit
import kelas_status as ks
import schema_jadwal
import schema_tagihan_catatan

ADMIN = "admin_sintetis"
GURU_A = "akun_" + "a" * 32
GURU_B = "akun_" + "b" * 32
AKUN_ADMIN = "akun_" + "c" * 32
KINI = "2026-11-23T03:00:00"
ID_SAMPAH = [None, 0, -1, "1", True, 1.0, 2 ** 63, 2 ** 64]
ID_TIDAK_ADA = 999_999
KUNCI_PERTEMUAN = {"id", "jenis", "kelompok_id", "order_id", "nama_kelas", "ke", "mulai", "menit",
                   "kunci", "keterangan", "anggota"}
KUNCI_ANGGOTA = {"order_id", "siswa_id"}
PERINTAH_TULIS = re.compile(r"\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|VACUUM)\b", re.IGNORECASE)


def _geser(waktu: str, selisih: timedelta) -> str:
    return (datetime.strptime(waktu, aturan.FORMAT_WAKTU) + selisih).strftime(aturan.FORMAT_WAKTU)


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


def _sisip_penempatan_mini(kon, order_id, kelompok_id, dibuat):
    """Penempatan Mini lewat SQL agar `dibuat` bisa diatur (masuk terlambat atau order tak aktif)."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)", (order_id, kelompok_id, dibuat, dibuat, ADMIN, ADMIN))
    kon.commit()


def _id_pertemuan(kon, kolom, nilai, ke):
    return kon.execute("SELECT id FROM jadwal_pertemuan WHERE %s=? AND ke=?" % kolom, (nilai, ke)).fetchone()[0]


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
            "mini_a1": _id_pertemuan(kon, "kelompok_id", kid_a, 1),
            "mini_a2": _id_pertemuan(kon, "kelompok_id", kid_a, 2),
            "mini_b1": _id_pertemuan(kon, "kelompok_id", kid_b, 1),
            "privat_a1": _id_pertemuan(kon, "order_id", ord_a2, 1),
            "privat_b1": _id_pertemuan(kon, "order_id", ord_b2, 1),
        }


def _koreksi(db, pertemuan_id, kini=KINI):
    with js.buka(db) as kon:
        return ajk.pertemuan_untuk_koreksi(kon, pertemuan_id, kini)


def _isi_semua_tabel(path) -> dict:
    """Isi setiap tabel (termasuk sqlite_sequence) lewat SELECT; aman untuk DB WAL, tanpa membaca berkas mentah."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as kon:
        nama = [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {tabel: kon.execute("SELECT * FROM %s ORDER BY rowid" % tabel).fetchall() for tabel in nama}


# --- pertemuan_untuk_koreksi: id sampah dan tak ada ---------------------------------------------

@pytest.mark.parametrize("pertemuan_id", ID_SAMPAH)
def test_id_sampah_none_tanpa_sql(db, contoh, pertemuan_id):
    jejak = []
    with js.buka(db) as kon:
        kon.set_trace_callback(jejak.append)
        hasil = ajk.pertemuan_untuk_koreksi(kon, pertemuan_id, KINI)
        kon.set_trace_callback(None)
    assert hasil is None
    assert jejak == []


def test_id_tidak_ada_none(db, contoh):
    assert _koreksi(db, ID_TIDAK_ADA) is None


# --- pertemuan_untuk_koreksi: bentuk, kunci, dan jenis ---------------------------------------------

def test_mini_bentuk_kunci_dan_jenis(db, contoh):
    hasil = _koreksi(db, contoh["mini_a1"])

    assert set(hasil) == KUNCI_PERTEMUAN
    assert hasil["jenis"] == "mini"
    assert hasil["kelompok_id"] == contoh["kid_a"] and hasil["order_id"] is None
    assert hasil["nama_kelas"] == "Mini Alfa"
    assert hasil["ke"] == 1 and hasil["kunci"] == contoh["kid_a"] + ":1"


def test_privat_bentuk_kunci_dan_jenis(db, contoh):
    hasil = _koreksi(db, contoh["privat_a1"])

    assert set(hasil) == KUNCI_PERTEMUAN
    assert hasil["jenis"] == "private"
    assert hasil["kelompok_id"] is None and hasil["order_id"] == contoh["ord_a2"]
    assert hasil["nama_kelas"] is None
    assert hasil["kunci"] == contoh["ord_a2"] + ":1"


def test_guru_lain_tetap_terlihat_bagi_admin(db, contoh):
    assert _koreksi(db, contoh["mini_b1"]) is not None
    assert _koreksi(db, contoh["privat_b1"]) is not None


def test_kunci_mini_cocok_dengan_catatan_guru(db, contoh, tmp_path):
    """Kunci dari jalur admin dipakai `catat` guru, lalu `riwayat` menemukan baris itu (kunci tidak bergeser)."""
    hasil = _koreksi(db, contoh["mini_a1"])
    berkas = tmp_path / "catatan.db"
    dasar.catat(kunci=hasil["kunci"], pertemuan_id=contoh["mini_a1"], mulai=hasil["mulai"], topik="lainnya",
                hadir={hasil["anggota"][0]["order_id"]: "hadir"}, oleh=GURU_A, peran="guru",
                pada=hasil["mulai"], path=berkas)

    riwayat = dasar.riwayat(hasil["kunci"], hasil["mulai"], path=berkas)

    assert len(riwayat["jurnal"]) == 1 and len(riwayat["hadir"]) == 1


# --- pertemuan_untuk_koreksi: keterangan -----------------------------------------------------------

def test_keterangan_belum_mulai(db, contoh):
    mulai = _koreksi(db, contoh["mini_a1"])["mulai"]

    hasil = _koreksi(db, contoh["mini_a1"], kini=_geser(mulai, timedelta(days=-1)))

    assert hasil["keterangan"] == aturan.ALASAN_BELUM_MULAI


def test_keterangan_boleh_setelah_mulai(db, contoh):
    mulai = _koreksi(db, contoh["mini_a1"])["mulai"]

    hasil = _koreksi(db, contoh["mini_a1"], kini=_geser(mulai, timedelta(hours=1)))

    assert hasil["keterangan"] is None


def test_pertemuan_tiga_puluh_hari_lalu_tetap_boleh(db, contoh):
    """Tanpa pengunci 7 hari (keputusan d). Hanya keterangan yang diuji: order bisa sudah tak aktif pada kini ini."""
    mulai = _koreksi(db, contoh["mini_a1"])["mulai"]

    hasil = _koreksi(db, contoh["mini_a1"], kini=_geser(mulai, timedelta(days=30)))

    assert hasil["keterangan"] is None


def test_dibatalkan_sebelum_mulai_menang_dari_belum_mulai(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=1 WHERE id=?", (contoh["mini_a1"],))
        kon.commit()
    mulai = _koreksi(db, contoh["mini_a1"])["mulai"]

    hasil = _koreksi(db, contoh["mini_a1"], kini=_geser(mulai, timedelta(days=-1)))

    assert hasil["keterangan"] == aturan.ALASAN_DIBATALKAN


def test_dibatalkan_setelah_mulai(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=1 WHERE id=?", (contoh["mini_a1"],))
        kon.commit()
    mulai = _koreksi(db, contoh["mini_a1"])["mulai"]

    hasil = _koreksi(db, contoh["mini_a1"], kini=_geser(mulai, timedelta(hours=1)))

    assert hasil["keterangan"] == aturan.ALASAN_DIBATALKAN


# --- pertemuan_untuk_koreksi: anggota ------------------------------------------------------------

def test_anggota_mini_hanya_order_lunas_dan_masuk_sebelum_mulai(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        belum_lunas = kelas_kit.menunggu(kon, 5, "mini", n=5)[0].order_id
        _sisip_penempatan_mini(kon, belum_lunas, contoh["kid_a"], "2026-11-19T00:00:00")
        batal_tagihan = kelas_kit.tagih(kon, 8, "mini", sekarang=kelas_kit.KINI)
        kelas_catatan.catat(kon, batal_tagihan.order_id, kelas_catatan.AKSI_BATAL, kelas_kit.KINI)
        assert kelas_catatan.dibatalkan(kon, batal_tagihan.order_id)
        _sisip_penempatan_mini(kon, batal_tagihan.order_id, contoh["kid_a"], "2026-11-19T00:00:00")
        terlambat = kelas_kit.lunas(kon, 6, "mini", n=6).order_id
        _sisip_penempatan_mini(kon, terlambat, contoh["kid_a"], "2026-11-22T00:00:00")

    hasil = _koreksi(db, contoh["mini_a1"])

    assert [a["order_id"] for a in hasil["anggota"]] == [contoh["ord_a1"]]
    assert {a["order_id"] for a in hasil["anggota"]}.isdisjoint({belum_lunas, batal_tagihan.order_id, terlambat})


def test_anggota_mini_tidak_tercampur_kelompok_lain(db, contoh):
    hasil = _koreksi(db, contoh["mini_a1"])

    assert contoh["ord_b2"] not in {a["order_id"] for a in hasil["anggota"]}
    assert all(a["siswa_id"] != 3 for a in hasil["anggota"])


def test_anggota_privat_hanya_order_itu(db, contoh):
    hasil = _koreksi(db, contoh["privat_a1"])

    assert hasil["anggota"] == [{"order_id": contoh["ord_a2"], "siswa_id": 2}]


def test_anggota_diurut_order_id_dan_hanya_dua_kunci(db, contoh):
    hasil = _koreksi(db, contoh["mini_a1"])
    urut = [a["order_id"] for a in hasil["anggota"]]

    assert urut == sorted(urut)
    assert all(set(a) == KUNCI_ANGGOTA for a in hasil["anggota"])


# --- pertemuan_untuk_koreksi: tanpa tulis ----------------------------------------------------------

def test_pembacaan_tidak_menulis_dan_tidak_mengubah_isi(db, contoh):
    sebelum = _isi_semua_tabel(db)
    jejak = []

    with js.buka(db) as kon:
        kon.set_trace_callback(jejak.append)
        for pertemuan_id in (contoh["mini_a1"], contoh["privat_a1"], contoh["mini_b1"], ID_TIDAK_ADA):
            ajk.pertemuan_untuk_koreksi(kon, pertemuan_id, KINI)
        kon.set_trace_callback(None)

    assert jejak, "jejak kosong: tes tidak membuktikan apa pun"
    assert [s for s in jejak if PERINTAH_TULIS.match(s)] == []
    assert _isi_semua_tabel(db) == sebelum


# --- nama_anggota ----------------------------------------------------------------------------------

def _belajar(tmp_path):
    path = tmp_path / "latihan-sintetis.db"
    with closing(sqlite3.connect(str(path))) as kon:
        kon.execute("CREATE TABLE siswa(id INTEGER PRIMARY KEY, nama TEXT NOT NULL)")
        kon.execute("INSERT INTO siswa(id, nama) VALUES(1, 'Anak Sintetis Satu')")
        kon.execute("INSERT INTO siswa(id, nama) VALUES(2, 'Anak Sintetis Dua')")
        kon.commit()
    return path


ORDER_1 = "kor_" + "1" * 32
ORDER_2 = "kor_" + "2" * 32


def test_nama_anggota_memetakan_order_ke_nama_dan_placeholder(tmp_path):
    anggota = [{"order_id": ORDER_1, "siswa_id": 1}, {"order_id": ORDER_2, "siswa_id": 99}]
    with closing(sqlite3.connect(str(_belajar(tmp_path)))) as kon:
        hasil = ajk.nama_anggota(kon, anggota)

    assert hasil == {ORDER_1: "Anak Sintetis Satu", ORDER_2: gb.PLACEHOLDER_NAMA}


def test_nama_anggota_kosong(tmp_path):
    with closing(sqlite3.connect(str(_belajar(tmp_path)))) as kon:
        assert ajk.nama_anggota(kon, []) == {}


def test_nama_anggota_tabel_siswa_tak_ada_jadi_placeholder(tmp_path):
    path = tmp_path / "tanpa-siswa.db"
    with closing(sqlite3.connect(str(path))) as kon:
        kon.execute("CREATE TABLE lain(x INTEGER)")
        kon.commit()
    anggota = [{"order_id": ORDER_1, "siswa_id": 1}]
    with closing(sqlite3.connect(str(path))) as kon:
        hasil = ajk.nama_anggota(kon, anggota)

    assert hasil == {ORDER_1: gb.PLACEHOLDER_NAMA}


def test_nama_anggota_berkas_rusak_jadi_placeholder(tmp_path):
    path = tmp_path / "rusak.db"
    path.write_bytes(b"bukan sqlite sama sekali " * 200)
    anggota = [{"order_id": ORDER_1, "siswa_id": 1}]
    with closing(sqlite3.connect(str(path))) as kon:
        hasil = ajk.nama_anggota(kon, anggota)

    assert hasil == {ORDER_1: gb.PLACEHOLDER_NAMA}


# --- susun_riwayat (fungsi murni, masukan sintetis) ------------------------------------------------

ID_GURU = "akun_" + "a" * 32
ID_ADMIN = "akun_" + "b" * 32
ORDER_3 = "kor_" + "3" * 32
PADA_1 = "2026-11-21T10:00:00"
PADA_2 = "2026-11-21T12:00:00"


def _riwayat_sintetis():
    return {
        "jurnal": [
            {"id": 1, "topik": "lainnya", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 2, "topik": "lainnya", "oleh": ID_ADMIN, "peran": "admin", "pada": PADA_2},
        ],
        "hadir": [
            {"id": 1, "order_id": ORDER_1, "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 2, "order_id": ORDER_2, "status": "izin", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 3, "order_id": ORDER_3, "status": "tidak_hadir", "oleh": ID_ADMIN, "peran": "admin",
             "pada": PADA_2},
            {"id": 4, "order_id": ORDER_1, "status": "tidak_hadir", "oleh": ID_ADMIN, "peran": "admin",
             "pada": PADA_2},
        ],
    }


NAMA_ORDER = {ORDER_1: "budi", ORDER_2: "Ayu"}
NAMA_GURU = {ID_GURU: "Bu Sinta", ID_ADMIN: "Pak Admin"}
LABEL_LAINNYA = aturan.LABEL_TOPIK_LAINNYA


def test_susun_riwayat_satu_entri_per_catatan_urut_kronologis():
    hasil = ajk.susun_riwayat(_riwayat_sintetis(), NAMA_ORDER, NAMA_GURU)

    assert [e["pada"] for e in hasil] == [PADA_1, PADA_2]
    assert hasil[0] == {"pada": PADA_1, "peran": "guru", "pelaku": "Bu Sinta",
                        "perubahan": ["Topik: " + LABEL_LAINNYA, "Ayu: Izin", "budi: Hadir"]}
    assert hasil[1] == {"pada": PADA_2, "peran": "admin", "pelaku": "Admin",
                        "perubahan": ["Topik: " + LABEL_LAINNYA, "Anak lain: Tidak hadir", "budi: Tidak hadir"]}


def test_susun_riwayat_pelaku_admin_selalu_admin_walau_nama_ada():
    hasil = ajk.susun_riwayat(_riwayat_sintetis(), NAMA_ORDER, NAMA_GURU)

    assert [e["pelaku"] for e in hasil] == ["Bu Sinta", "Admin"]


def test_susun_riwayat_guru_tanpa_nama_jadi_guru():
    hasil = ajk.susun_riwayat(_riwayat_sintetis(), NAMA_ORDER, {})

    assert hasil[0]["pelaku"] == "Guru"


def test_susun_riwayat_urut_berdasar_pada_bukan_id():
    riwayat = {
        "jurnal": [{"id": 1, "topik": "lainnya", "oleh": ID_ADMIN, "peran": "admin", "pada": PADA_2}],
        "hadir": [{"id": 1, "order_id": ORDER_1, "status": "hadir", "oleh": ID_GURU, "peran": "guru",
                   "pada": PADA_1}],
    }

    hasil = ajk.susun_riwayat(riwayat, NAMA_ORDER, NAMA_GURU)

    assert [e["pada"] for e in hasil] == [PADA_1, PADA_2]


def test_susun_riwayat_pada_sama_beda_pelaku_jadi_dua_entri():
    riwayat = {
        "jurnal": [],
        "hadir": [
            {"id": 1, "order_id": ORDER_1, "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 2, "order_id": ORDER_1, "status": "izin", "oleh": ID_ADMIN, "peran": "admin", "pada": PADA_1},
        ],
    }

    hasil = ajk.susun_riwayat(riwayat, NAMA_ORDER, NAMA_GURU)

    assert len(hasil) == 2
    assert hasil == ajk.susun_riwayat(riwayat, NAMA_ORDER, NAMA_GURU)


def test_susun_riwayat_nama_anak_diurut_tanpa_membedakan_huruf():
    riwayat = {
        "jurnal": [],
        "hadir": [
            {"id": 1, "order_id": ORDER_1, "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 2, "order_id": ORDER_2, "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 3, "order_id": ORDER_3, "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
        ],
    }
    nama = {ORDER_1: "cici", ORDER_2: "Ayu", ORDER_3: "budi"}

    hasil = ajk.susun_riwayat(riwayat, nama, NAMA_GURU)

    assert hasil[0]["perubahan"] == ["Ayu: Hadir", "budi: Hadir", "cici: Hadir"]


def test_susun_riwayat_label_status_tiga_nilai():
    riwayat = {
        "jurnal": [],
        "hadir": [
            {"id": 1, "order_id": ORDER_1, "status": "hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 2, "order_id": ORDER_2, "status": "izin", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
            {"id": 3, "order_id": ORDER_3, "status": "tidak_hadir", "oleh": ID_GURU, "peran": "guru", "pada": PADA_1},
        ],
    }
    nama = {ORDER_1: "A", ORDER_2: "B", ORDER_3: "C"}

    hasil = ajk.susun_riwayat(riwayat, nama, NAMA_GURU)

    assert hasil[0]["perubahan"] == ["A: Hadir", "B: Izin", "C: Tidak hadir"]


def test_susun_riwayat_tanpa_id_dan_kunci_di_keluaran():
    keluaran = json.dumps(ajk.susun_riwayat(_riwayat_sintetis(), NAMA_ORDER, NAMA_GURU), ensure_ascii=False)

    for terlarang in ("kor_", "klp_", "akun_", ORDER_1, ORDER_2, ORDER_3, ID_GURU, ID_ADMIN,
                      "order_id", "oleh", "kunci"):
        assert terlarang not in keluaran


def test_susun_riwayat_tidak_memutasi_masukan():
    riwayat = _riwayat_sintetis()
    salinan = copy.deepcopy(riwayat)
    nama_order, nama_guru = dict(NAMA_ORDER), dict(NAMA_GURU)

    ajk.susun_riwayat(riwayat, nama_order, nama_guru)

    assert riwayat == salinan
    assert nama_order == NAMA_ORDER and nama_guru == NAMA_GURU


def test_susun_riwayat_masukan_kosong_menghasilkan_daftar_kosong():
    assert ajk.susun_riwayat({"jurnal": [], "hadir": []}, {}, {}) == []

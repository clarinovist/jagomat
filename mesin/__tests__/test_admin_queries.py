"""Unit test query pusat kendali admin dengan data sintetis temp."""

from dataclasses import asdict, fields
from datetime import datetime, timezone, timedelta
import sqlite3

import pytest

import admin_queries as q


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "admin-query-sintetis.db"
    kon = sqlite3.connect(str(path))
    kon.row_factory = sqlite3.Row
    kon.executescript(
        """
        CREATE TABLE siswa (
            id INTEGER PRIMARY KEY,
            nama TEXT NOT NULL,
            tingkat TEXT NOT NULL,
            pemilik TEXT NOT NULL,
            dibuat TEXT NOT NULL DEFAULT '2026-01-01 00:00:00'
        );
        CREATE TABLE sesi (
            id INTEGER PRIMARY KEY,
            siswa_id INTEGER NOT NULL,
            level TEXT NOT NULL,
            tanggal TEXT NOT NULL,
            mulai TEXT,
            selesai TEXT,
            dibatalkan TEXT,
            dibuat TEXT NOT NULL,
            FOREIGN KEY (siswa_id) REFERENCES siswa(id)
        );
        """
    )
    yield kon
    kon.close()


def _akun():
    return [
        {
            "id_akun": "akun_guru_a",
            "pengguna": "keluarga-a",
            "peran": "guru",
            "garam": "GARAM-SANGAT-RAHASIA",
            "kunci": "HASH-SANGAT-RAHASIA",
            "iterasi": 600000,
            "token": "TOKEN-SANGAT-RAHASIA",
        },
        {"id_akun": "akun_guru_b", "pengguna": "keluarga-b", "peran": "guru"},
        {"id_akun": "akun_admin", "pengguna": "pengelola", "peran": "admin"},
        {"id_akun": "akun_murid_1", "pengguna": "login-satu", "peran": "murid", "siswa_id": 1},
        {"id_akun": "akun_murid_2", "pengguna": "login-yatim", "peran": "murid", "siswa_id": 999},
        {"id_akun": "akun_murid_3", "pengguna": "Kembar", "peran": "murid"},
        {"id_akun": "akun_murid_4", "pengguna": "Tunggal", "peran": "murid"},
        {"id_akun": "akun_murid_5", "pengguna": "TakAda", "peran": "murid"},
    ]


def _isi_anomali(kon):
    kon.executemany(
        "INSERT INTO siswa(id,nama,tingkat,pemilik) VALUES(?,?,?,?)",
        [
            (1, "Eksplisit", "P3", "keluarga-a"),
            (2, "Belum Login", "P4", "keluarga-a"),
            (3, "Kembar", "P5", "keluarga-a"),
            (4, "Kembar", "P6", "keluarga-b"),
            (5, "Tunggal", "P3", "pemilik-hilang"),
            (6, "Tanpa Pemilik", "P4", ""),
            (7, "Punya Admin", "P5", "pengelola"),
        ],
    )
    kon.executemany(
        """INSERT INTO sesi(
               id,siswa_id,level,tanggal,mulai,selesai,dibatalkan,dibuat)
           VALUES(?,?,?,?,?,?,?,?)""",
        [
            (1, 1, "P3", "2026-09-12", "2026-09-12 09:00:00", "2026-09-12 09:20:00", None, "2026-09-12 08:59:00"),
            (2, 2, "P4", "2026-09-08", None, None, "2026-09-08 10:00:00", "2026-09-08 09:00:00"),
            (3, 5, "P3", "2026-08-20", None, None, None, "2026-08-20 07:00:00"),
        ],
    )
    kon.commit()


def test_snapshot_akun_allow_list_tidak_membawa_credential():
    snapshot = q.snapshot_akun(_akun())

    assert {field.name for field in fields(q.AkunPublik)} == {
        "id_akun", "pengguna", "peran", "siswa_id"
    }
    teks = repr(snapshot) + repr(tuple(asdict(item) for item in snapshot))
    for rahasia in (
        "GARAM-SANGAT-RAHASIA",
        "HASH-SANGAT-RAHASIA",
        "TOKEN-SANGAT-RAHASIA",
        "garam",
        "kunci",
        "iterasi",
        "token",
    ):
        assert rahasia not in teks


@pytest.mark.parametrize(
    "akun",
    [
        [{"pengguna": "sama", "peran": "guru"}, {"pengguna": "SAMA", "peran": "guru"}],
        [{"id_akun": "id-satu", "pengguna": "a", "peran": "guru"}, {"id_akun": "id-satu", "pengguna": "b", "peran": "guru"}],
        [{"id_akun": "id-satu", "pengguna": "a", "peran": "asing"}],
        [{"id_akun": "id-satu", "pengguna": "a", "peran": "guru", "siswa_id": 1}],
    ],
)
def test_snapshot_malformed_ditolak(akun):
    with pytest.raises(q.InputQueryTidakSah):
        q.snapshot_akun(akun)


def test_konteks_menandai_orphan_legacy_ambigu_tanpa_mengaitkan(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())
    masalah = {(item.pengguna, item.status, item.jumlah_kandidat) for item in konteks.login_bermasalah}

    assert ("login-yatim", "orphan_login", 0) in masalah
    assert ("Kembar", "legacy_same_name_ambiguous", 2) in masalah
    assert ("Tunggal", "legacy_login_unverified", 1) in masalah
    assert ("TakAda", "legacy_orphan_login", 0) in masalah

    siswa = q.daftar_siswa(db, konteks, per_halaman=100)
    by_id = {item.id: item for item in siswa.item}
    assert by_id[1].login_pengguna == "login-satu"
    assert by_id[2].login_pengguna is None
    assert "student_without_login" in by_id[2].status
    assert by_id[3].login_pengguna is None
    assert "legacy_same_name_ambiguous" in by_id[3].status
    assert by_id[4].login_pengguna is None
    assert "legacy_same_name_ambiguous" in by_id[4].status
    assert by_id[5].login_pengguna is None
    assert "legacy_login_unverified" in by_id[5].status
    assert "owner_without_account" in by_id[5].status
    assert "owner_empty" in by_id[6].status
    assert "owner_admin" in by_id[7].status

    # Query proyeksi readonly tidak melakukan repair apa pun.
    assert db.execute("SELECT pemilik FROM siswa WHERE id=6").fetchone()[0] == ""


def test_ringkasan_definisi_count_dan_aktivitas(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())
    sekarang = datetime(2026, 9, 13, 12, tzinfo=timezone(timedelta(hours=7)))

    hasil = q.ringkasan_admin(db, konteks, sekarang_wib=sekarang)

    assert hasil.jumlah_keluarga == 2  # admin bukan keluarga
    assert hasil.jumlah_siswa == 7
    assert hasil.jumlah_login_murid == 5
    assert hasil.jumlah_sesi == 3
    assert hasil.sesi_7_hari == 2
    assert hasil.sesi_30_hari == 3
    assert hasil.sesi_dibatalkan == 1
    assert [item.sesi_id for item in hasil.aktivitas_terbaru] == [1, 2, 3]
    assert hasil.aktivitas_terbaru[1].dibatalkan is True
    perhatian = {item.kode: item.jumlah for item in hasil.perhatian}
    assert perhatian["owner_without_account"] == 1
    assert perhatian["owner_empty"] == 1
    assert perhatian["orphan_login"] == 2
    assert perhatian["legacy_same_name_ambiguous"] == 1


def test_daftar_keluarga_memisahkan_admin_owner_hilang_dan_kosong(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())

    hasil = q.daftar_keluarga(db, konteks, per_halaman=100)
    by_name = {item.pengguna: item for item in hasil.item}

    assert hasil.total == 5
    assert by_name["keluarga-a"].kategori == "orang_tua"
    assert by_name["keluarga-a"].jumlah_siswa == 3
    assert by_name["keluarga-a"].jumlah_sesi == 2
    assert by_name["keluarga-b"].jumlah_siswa == 1
    assert by_name["pengelola"].kategori == "pengelola"
    assert "owner_admin" in by_name["pengelola"].status
    assert by_name["pemilik-hilang"].kategori == "pemilik_tanpa_akun"
    assert by_name[""].kategori == "pemilik_kosong"


def test_pencarian_siswa_literal_bukan_wildcard_dan_parameterized(db):
    db.executemany(
        "INSERT INTO siswa(id,nama,tingkat,pemilik) VALUES(?,?,?,?)",
        [
            (1, "Nama%Persen", "P3", "keluarga-a"),
            (2, "Nama_Pagar", "P4", "keluarga-a"),
            (3, "Nama\\Slash", "P5", "keluarga-b"),
            (4, "Nama Biasa", "P6", "keluarga-b"),
        ],
    )
    db.commit()
    konteks = q.buat_konteks(db, _akun())
    jejak = []
    db.set_trace_callback(jejak.append)

    assert [item.id for item in q.daftar_siswa(db, konteks, cari="%", per_halaman=100).item] == [1]
    assert [item.id for item in q.daftar_siswa(db, konteks, cari="_", per_halaman=100).item] == [2]
    assert [item.id for item in q.daftar_siswa(db, konteks, cari="\\", per_halaman=100).item] == [3]
    assert all(not sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")) for sql in jejak)


def test_pagination_default_max_stable_dan_filter_negatif(db):
    db.executemany(
        "INSERT INTO siswa(id,nama,tingkat,pemilik) VALUES(?,?,?,?)",
        [(i, "Nama Sama", "P3", "keluarga-a") for i in range(1, 131)],
    )
    db.commit()
    konteks = q.buat_konteks(db, _akun())

    awal = q.daftar_siswa(db, konteks)
    kedua = q.daftar_siswa(db, konteks, halaman=2)
    maksimal = q.daftar_siswa(db, konteks, per_halaman=100)
    assert len(awal.item) == 25
    assert [item.id for item in awal.item] == list(range(1, 26))
    assert [item.id for item in kedua.item] == list(range(26, 51))
    assert len(maksimal.item) == 100
    assert awal.total == 130
    assert awal.jumlah_halaman == 6

    for kwargs in (
        {"halaman": 0},
        {"per_halaman": 101},
        {"per_halaman": 0},
        {"tingkat": "P7"},
        {"status": "SQL bebas"},
        {"keluarga_id": "id-tak-ada"},
        {"cari": "x" * 81},
    ):
        with pytest.raises(q.InputQueryTidakSah):
            q.daftar_siswa(db, konteks, **kwargs)


def test_detail_hanya_id_dan_tidak_membaca_jawaban_diagnosis(db):
    _isi_anomali(db)
    konteks = q.buat_konteks(db, _akun())
    jejak = []
    db.set_trace_callback(jejak.append)

    keluarga = q.detail_keluarga(db, konteks, "akun_guru_a")
    siswa = q.detail_siswa(db, konteks, 1)

    assert keluarga is not None
    assert keluarga.keluarga.pengguna == "keluarga-a"
    assert keluarga.siswa.total == 3
    assert siswa is not None
    assert siswa.siswa.nama == "Eksplisit"
    assert siswa.sesi_terbaru[0].id == 1
    assert q.detail_keluarga(db, konteks, "akun_tidak_ada") is None
    assert q.detail_siswa(db, konteks, 9999) is None
    gabung = "\n".join(jejak).lower()
    assert "jawaban" not in gabung
    assert "diagnosis" not in gabung
    assert "malrule" not in gabung


def test_fixture_1000_keluarga_5000_siswa_query_count_konstan(db):
    akun = []
    siswa = []
    for keluarga in range(1000):
        pengguna = "keluarga-%04d" % keluarga
        akun.append({
            "id_akun": "akun_%04d" % keluarga,
            "pengguna": pengguna,
            "peran": "guru",
            "hash_tidak_boleh_lolos": "rahasia-%04d" % keluarga,
        })
        for nomor in range(5):
            siswa_id = keluarga * 5 + nomor + 1
            siswa.append((siswa_id, "Anak %04d-%d" % (keluarga, nomor), "P3", pengguna))
    db.executemany("INSERT INTO siswa(id,nama,tingkat,pemilik) VALUES(?,?,?,?)", siswa)
    db.commit()
    jejak = []
    db.set_trace_callback(jejak.append)

    konteks = q.buat_konteks(db, akun)
    mulai = len(jejak)
    keluarga = q.daftar_keluarga(db, konteks)
    query_keluarga = [sql for sql in jejak[mulai:] if sql.lstrip().upper().startswith("SELECT")]
    mulai = len(jejak)
    daftar = q.daftar_siswa(db, konteks)
    query_siswa = [sql for sql in jejak[mulai:] if sql.lstrip().upper().startswith("SELECT")]

    assert len(konteks.akun) == 1000
    assert len(konteks.siswa) == 5000
    assert keluarga.total == 1000
    assert len(keluarga.item) == 25
    assert daftar.total == 5000
    assert len(daftar.item) == 25
    assert len(query_keluarga) == 1
    assert len(query_siswa) == 1
    assert "rahasia-0000" not in repr(konteks)

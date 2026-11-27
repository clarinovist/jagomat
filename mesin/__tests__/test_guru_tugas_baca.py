"""Pembacaan tugas guru (guru_tugas_baca): anak tertaut ke guru, dan skor ringkas sesi. Hanya SELECT.

Data sepenuhnya sintetis (akun_ buatan, anak nomor urut). Tidak membaca DB asli.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

import database
import guru_tugas_baca as tb
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
ORDER_TIDAK_ADA = "kor_" + "f" * 32
KINI_LAMPAU = "2026-11-20T12:00:00"             # sebelum semua pertemuan dan akses contoh
KINI_AKSES_LEWAT = "2026-12-22T00:00:00"         # siswa 1 dan 2 (akses berakhir 20 Des) sudah habis
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
SQL_TULIS = ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER")
SQL_RAHASIA = ("kode_", "malrule", "alasan", "catatan", "restatement", "pembahasan", "nama", "cara", "j.jawaban")
BATAS_PARAMETER_SQLITE_LAMA = 999   # batas variabel SQLite versi lama; potongan harus tetap di bawahnya


# --- fixture jadwal (DB admin sintetis) -----------------------------------------------------

@pytest.fixture()
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    schema_tagihan_catatan.migrasikan(path)
    return path


def _ro(db):
    return js.buka(db)


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
    """Penempatan Mini lewat SQL (melewati domain) untuk order yang BELUM aktif."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)",
                (order_id, kelompok_id, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))


def _sisip_privat_mentah(kon, order_id, guru):
    """Penempatan Private + 8 pertemuan lewat SQL untuk order yang BELUM aktif."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,"
                "dibuat_oleh,diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                (order_id, guru, schema_jadwal.LOKASI_PRIVATE, kelas_kit.KINI, kelas_kit.KINI, ADMIN, ADMIN))
    for ke in range(1, 9):
        kon.execute("INSERT INTO jadwal_pertemuan(kelompok_id,order_id,ke,mulai,menit,dibatalkan,diubah,"
                    "diubah_oleh) VALUES(NULL,?,?,?,60,0,?,?)",
                    (order_id, ke, "2026-11-%02dT09:30:00" % (22 + ke), kelas_kit.KINI, ADMIN))


def _berakhir(kon, order_id):
    return kon.execute("SELECT berakhir FROM kelas_akses WHERE order_id=?", (order_id,)).fetchone()[0]


def _isi_contoh(kon):
    """Dua guru: A punya Mini (anak 1) dan Private (anak 2); B punya Mini (anak 3) dan Private (anak 4)."""
    kid_a = _mini(kon, "Mini Alfa", GURU_A)
    kid_b = _mini(kon, "Mini Beta", GURU_B)
    ord_mini_a = _tempatkan_mini(kon, kid_a, siswa=1, n=1)
    ord_priv_a = _tempatkan_privat(kon, GURU_A, siswa=2, n=2, tanggal="2026-11-23")
    ord_mini_b = _tempatkan_mini(kon, kid_b, siswa=3, n=3)
    ord_priv_b = _tempatkan_privat(kon, GURU_B, siswa=4, n=4, tanggal="2026-11-24", jam="10:00")
    kon.commit()
    return {"kid_a": kid_a, "kid_b": kid_b, "ord_mini_a": ord_mini_a, "ord_priv_a": ord_priv_a,
            "ord_mini_b": ord_mini_b, "ord_priv_b": ord_priv_b}


@pytest.fixture()
def contoh(db):
    with js.buka(db, tulis_data=True) as kon:
        return _isi_contoh(kon)


def _ringkas_tertaut(daftar):
    return {(d["order_id"], d["siswa_id"], d["kelompok_id"]) for d in daftar}


# --- kepemilikan: hanya order milik guru yang tertaut ----------------------------------------

def test_daftar_tertaut_hanya_memuat_order_guru_pemilik(db, contoh):
    with _ro(db) as kon:
        a = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
        b = tb.daftar_tertaut(kon, GURU_B, KINI_LAMPAU)
        kosong = tb.daftar_tertaut(kon, GURU_KOSONG, KINI_LAMPAU)
    assert _ringkas_tertaut(a) == {(contoh["ord_mini_a"], 1, contoh["kid_a"]),
                                   (contoh["ord_priv_a"], 2, None)}
    assert _ringkas_tertaut(b) == {(contoh["ord_mini_b"], 3, contoh["kid_b"]),
                                   (contoh["ord_priv_b"], 4, None)}
    assert kosong == []


def test_daftar_tertaut_memakai_kunci_yang_ditetapkan(db, contoh):
    with _ro(db) as kon:
        daftar = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
    assert daftar and all(set(d.keys()) == {"order_id", "siswa_id", "kelompok_id"} for d in daftar)


def test_anak_tertaut_hanya_untuk_guru_pemilik_order(db, contoh):
    with _ro(db) as kon:
        assert tb.anak_tertaut(kon, GURU_A, contoh["ord_mini_a"], KINI_LAMPAU) == 1
        assert tb.anak_tertaut(kon, GURU_A, contoh["ord_priv_a"], KINI_LAMPAU) == 2
        assert tb.anak_tertaut(kon, GURU_B, contoh["ord_mini_a"], KINI_LAMPAU) is None
        assert tb.anak_tertaut(kon, GURU_B, contoh["ord_priv_a"], KINI_LAMPAU) is None
        assert tb.anak_tertaut(kon, GURU_KOSONG, contoh["ord_mini_a"], KINI_LAMPAU) is None


@pytest.mark.parametrize("guru_buruk", [None, 7, ["akun_" + "a" * 32]])
def test_guru_bukan_teks_mendapat_hasil_kosong(db, contoh, guru_buruk):
    with _ro(db) as kon:
        assert tb.daftar_tertaut(kon, guru_buruk, KINI_LAMPAU) == []
        assert tb.anak_tertaut(kon, guru_buruk, contoh["ord_mini_a"], KINI_LAMPAU) is None


def test_order_tidak_ada_dan_order_guru_lain_sama_hasilnya_none(db, contoh):
    with _ro(db) as kon:
        tidak_ada = tb.anak_tertaut(kon, GURU_A, ORDER_TIDAK_ADA, KINI_LAMPAU)
        milik_lain = tb.anak_tertaut(kon, GURU_A, contoh["ord_mini_b"], KINI_LAMPAU)
    assert tidak_ada is None and milik_lain is None


# --- status order: hanya lunas, tidak dibatalkan, tidak kedaluwarsa ---------------------------

def test_order_belum_lunas_tidak_tertaut(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        menunggu = kelas_kit.menunggu(kon, 5, "mini", n=5)[0].order_id
        belum_bayar = kelas_kit.tagih(kon, 6, "private").order_id
        _sisip_penempatan_mini_mentah(kon, menunggu, contoh["kid_a"])
        _sisip_privat_mentah(kon, belum_bayar, GURU_A)
        kon.commit()
    with _ro(db) as kon:
        for oid in (menunggu, belum_bayar):
            status = ks.status_dari(ks.baris_order(kon, oid), ks.fakta_order(kon, oid), KINI_LAMPAU)
            assert status != kelas_dasar.STATUS_AKTIF
        daftar = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
        assert tb.anak_tertaut(kon, GURU_A, menunggu, KINI_LAMPAU) is None
        assert tb.anak_tertaut(kon, GURU_A, belum_bayar, KINI_LAMPAU) is None
    assert {d["order_id"] for d in daftar} == {contoh["ord_mini_a"], contoh["ord_priv_a"]}


def test_order_dibatalkan_tidak_tertaut(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        dibatalkan = kelas_kit.tagih(kon, 8, "private").order_id
        kelas_batal.batalkan_tagihan(kon, kelas_kit.AKUN_A, 8, "private", kelas_kit.KINI)
        _sisip_privat_mentah(kon, dibatalkan, GURU_A)
        kon.commit()
    with _ro(db) as kon:
        status = ks.status_dari(ks.baris_order(kon, dibatalkan), ks.fakta_order(kon, dibatalkan), KINI_LAMPAU)
        assert status != kelas_dasar.STATUS_AKTIF
        assert tb.anak_tertaut(kon, GURU_A, dibatalkan, KINI_LAMPAU) is None
        assert dibatalkan not in {d["order_id"] for d in tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)}


def test_order_kedaluwarsa_tidak_tertaut(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        kedaluwarsa = kelas_kit.sisip_order(kon, 7, siswa=7, paket="private", dibuat="2026-11-18T09:00:00",
                                            kedaluwarsa="2026-11-19T00:00:00")
        _sisip_privat_mentah(kon, kedaluwarsa, GURU_A)
        kon.commit()
    with _ro(db) as kon:
        status = ks.status_dari(ks.baris_order(kon, kedaluwarsa), ks.fakta_order(kon, kedaluwarsa), KINI_LAMPAU)
        assert status == kelas_dasar.STATUS_KEDALUWARSA
        assert tb.anak_tertaut(kon, GURU_A, kedaluwarsa, KINI_LAMPAU) is None
        assert kedaluwarsa not in {d["order_id"] for d in tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)}


def _lunas_tanpa_baris_akses(kon, kid_a, n=11):
    """Order Mini lunas (verifikasi setuju ada) yang TIDAK punya baris `kelas_akses`, lalu ditempatkan di kelompok guru A."""
    oid = kelas_kit.sisip_order(kon, n, siswa=n, paket="mini")
    kelas_kit.sisip_tagihan(kon, oid)
    bukti_id = kelas_kit.sisip_bukti(kon, oid, n)
    verifikasi_id = kelas_kit.sisip_verifikasi(kon, oid, bukti_id)
    _sisip_penempatan_mini_mentah(kon, oid, kid_a)
    kon.commit()
    return oid, verifikasi_id


def test_order_lunas_tanpa_baris_akses_ditolak_fail_closed(db, contoh):
    """Fail-closed (T3): order lunas tanpa `kelas_akses` tidak terbukti masih berlaku, jadi TIDAK tertaut."""
    with js.buka(db, tulis_data=True) as kon:
        oid, _ = _lunas_tanpa_baris_akses(kon, contoh["kid_a"])
    with _ro(db) as kon:
        akses = kon.execute("SELECT COUNT(*) FROM kelas_akses WHERE order_id=?", (oid,)).fetchone()[0]
        status = ks.status_dari(ks.baris_order(kon, oid), ks.fakta_order(kon, oid), KINI_LAMPAU)
        anak = tb.anak_tertaut(kon, GURU_A, oid, KINI_LAMPAU)
        daftar = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
    # Prasyarat uji: order lunas (AKTIF) tetapi tanpa baris akses.
    assert akses == 0 and status == kelas_dasar.STATUS_AKTIF
    assert anak is None
    assert oid not in {d["order_id"] for d in daftar}


def test_order_lunas_dengan_baris_akses_tertaut_sebagai_pembanding(db, contoh):
    """Pembanding untuk tes fail-closed: order yang sama TERTAUT begitu baris akses yang masih berlaku ditambahkan."""
    with js.buka(db, tulis_data=True) as kon:
        oid, verifikasi_id = _lunas_tanpa_baris_akses(kon, contoh["kid_a"], n=12)
        kon.execute("INSERT INTO kelas_akses(order_id, siswa_id, verifikasi_id, mulai, berakhir, dibuat) "
                    "VALUES(?, ?, ?, ?, ?, ?)",
                    (oid, 12, verifikasi_id, "2026-11-20T09:30:00", "2026-12-20T09:30:00", KINI_LAMPAU))
        kon.commit()
    with _ro(db) as kon:
        anak = tb.anak_tertaut(kon, GURU_A, oid, KINI_LAMPAU)
        daftar = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
    assert anak == 12
    assert oid in {d["order_id"] for d in daftar}


def test_penempatan_mini_yang_dilepas_tidak_tertaut(db, contoh):
    with js.buka(db, tulis_data=True) as kon:
        versi = kon.execute("SELECT dibuat FROM jadwal_penempatan WHERE order_id=?",
                            (contoh["ord_mini_a"],)).fetchone()[0]
        js.lepas_penempatan(kon, ADMIN, contoh["ord_mini_a"], versi=versi, sekarang=KINI_LAMPAU)
        kon.commit()
    with _ro(db) as kon:
        assert tb.anak_tertaut(kon, GURU_A, contoh["ord_mini_a"], KINI_LAMPAU) is None
        daftar = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
    assert {d["order_id"] for d in daftar} == {contoh["ord_priv_a"]}


# --- T3: akses paket sudah berakhir -> tidak tertaut ------------------------------------------

def test_akses_berakhir_tidak_tertaut_dan_tepat_di_batas(db, contoh):
    with _ro(db) as kon:
        berakhir = _berakhir(kon, contoh["ord_mini_a"])
        # Kondisi uji: akhir akses siswa 1 (order Mini guru A) berada sesudah KINI_LAMPAU.
        assert berakhir > KINI_LAMPAU
        sedetik_sebelumnya = (datetime.strptime(berakhir, FORMAT_WAKTU) - timedelta(seconds=1)).strftime(FORMAT_WAKTU)
        sebelum = tb.anak_tertaut(kon, GURU_A, contoh["ord_mini_a"], sedetik_sebelumnya)
        tepat = tb.anak_tertaut(kon, GURU_A, contoh["ord_mini_a"], berakhir)
    assert sebelum == 1
    assert tepat is None


def test_akses_berakhir_mengeluarkan_semua_order_guru_dari_daftar(db, contoh):
    with _ro(db) as kon:
        daftar = tb.daftar_tertaut(kon, GURU_A, KINI_AKSES_LEWAT)
        anak = tb.anak_tertaut(kon, GURU_A, contoh["ord_priv_a"], KINI_AKSES_LEWAT)
    assert daftar == []
    assert anak is None


# --- input sampah: tidak melempar galat SQL ---------------------------------------------------

@pytest.mark.parametrize("sampah", [None, 5, ["kor_x"], "", "x" * 5000, "kor_' OR 1=1 --", "\x00"])
def test_order_id_berformat_sampah_tidak_melempar_galat(db, contoh, sampah):
    with _ro(db) as kon:
        hasil = tb.anak_tertaut(kon, GURU_A, sampah, KINI_LAMPAU)
        daftar_sesudahnya = tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
    assert hasil is None
    assert {d["order_id"] for d in daftar_sesudahnya} == {contoh["ord_mini_a"], contoh["ord_priv_a"]}


# --- tanpa tulis: isi berkas sama, tidak ada SQL penulisan ------------------------------------

def _isi_semua_tabel(db) -> dict:
    """Isi setiap tabel pengguna, lewat SQL (bukan byte berkas): tidak bergantung pada mode journal (WAL atau tidak)."""
    with _ro(db) as kon:
        nama_tabel = [r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        return {nama: [tuple(r) for r in kon.execute('SELECT * FROM "%s"' % nama).fetchall()]
                for nama in nama_tabel}


def test_pembacaan_tugas_tidak_mengubah_isi_tabel_dan_tidak_menulis_sql(db, contoh):
    sebelum = _isi_semua_tabel(db)
    sql = []
    with _ro(db) as kon:
        kon.set_trace_callback(sql.append)
        tb.daftar_tertaut(kon, GURU_A, KINI_LAMPAU)
        tb.anak_tertaut(kon, GURU_B, contoh["ord_mini_a"], KINI_LAMPAU)
        kon.set_trace_callback(None)
    assert sebelum["jadwal_penempatan"], "kondisi uji: tabel penempatan tidak kosong"
    assert _isi_semua_tabel(db) == sebelum
    assert sql, "tidak ada kueri yang tercatat"
    assert not [s for s in sql if s.lstrip().upper().startswith(SQL_TULIS)]


# --- skor ringkas (DB belajar sintetis) -------------------------------------------------------

@pytest.fixture()
def belajar(tmp_path):
    path = tmp_path / "belajar-uji.db"
    database.siapkan(path)
    return path


def _sesi_dengan_pola(kon, siswa_id, seed, pola, *, selesai):
    """Sesi buatan `database.buat_sesi` dengan jawaban+diagnosis untuk urutan `pola` (1 benar, 0 salah).

    Mengembalikan (sesi_id, jumlah soal). Soal yang tak punya pola tetap tanpa jawaban.
    """
    sid = database.buat_sesi(kon, siswa_id, seed=seed)
    soal = [r["id"] for r in kon.execute("SELECT id FROM sesi_soal WHERE sesi_id=? ORDER BY nomor", (sid,))]
    for ss_id, benar in zip(soal, pola):
        jawaban_id = kon.execute("INSERT INTO jawaban(sesi_soal_id, jawaban) VALUES(?, ?)",
                                 (ss_id, "1")).lastrowid
        kon.execute("INSERT INTO diagnosis(jawaban_id, benar) VALUES(?, ?)", (jawaban_id, benar))
    if selesai:
        kon.execute("UPDATE sesi SET selesai=? WHERE id=?", ("2026-11-21 09:00:00", sid))
    return sid, len(soal)


def test_skor_benar_dan_total_tepat_untuk_sesi_selesai(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Satu")
        sid, jumlah = _sesi_dengan_pola(kon, anak, 11, [1, 1, 0, 1], selesai=True)
        skor = tb.skor_ringkas(kon, [(sid, anak)])
    assert jumlah >= 4
    assert skor == {sid: {"selesai": True, "benar": 3, "total": jumlah}}


def test_sesi_selesai_tanpa_jawaban_bernilai_nol(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Dua")
        sid, jumlah = _sesi_dengan_pola(kon, anak, 12, [], selesai=True)
        skor = tb.skor_ringkas(kon, [(sid, anak)])
    assert jumlah >= 1
    assert skor == {sid: {"selesai": True, "benar": 0, "total": jumlah}}


def test_benar_kosong_untuk_sesi_belum_selesai(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Tiga")
        sid, jumlah = _sesi_dengan_pola(kon, anak, 13, [1, 1, 1], selesai=False)
        skor = tb.skor_ringkas(kon, [(sid, anak)])
    assert skor == {sid: {"selesai": False, "benar": None, "total": jumlah}}


def test_pasangan_siswa_salah_tidak_muncul_di_hasil(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Empat")
        lain = database.tambah_siswa(kon, "Anak Uji Lima")
        sid, _jumlah = _sesi_dengan_pola(kon, anak, 14, [1], selesai=True)
        skor = tb.skor_ringkas(kon, [(sid, lain)])
        selesai = tb.selesai_himpunan(kon, [(sid, lain)])
    assert skor == {}
    assert selesai == set()


def test_sesi_dibatalkan_tidak_dihitung(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Enam")
        sid, _jumlah = _sesi_dengan_pola(kon, anak, 15, [1, 1], selesai=True)
        kon.execute("UPDATE sesi SET dibatalkan=? WHERE id=?", ("2026-11-21 10:00:00", sid))
        skor = tb.skor_ringkas(kon, [(sid, anak)])
    assert skor == {}


def test_hasil_skor_hanya_memuat_selesai_benar_dan_total(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Tujuh")
        selesai_id, _ = _sesi_dengan_pola(kon, anak, 16, [1, 0], selesai=True)
        belum_id, _ = _sesi_dengan_pola(kon, anak, 17, [1], selesai=False)
        skor = tb.skor_ringkas(kon, [(selesai_id, anak), (belum_id, anak)])
    assert set(skor) == {selesai_id, belum_id}
    for nilai in skor.values():
        assert set(nilai.keys()) == {"selesai", "benar", "total"}
        assert type(nilai["selesai"]) is bool


def test_sesi_tanpa_soal_bernilai_total_nol(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Delapan")
        sid = kon.execute("INSERT INTO sesi(siswa_id, seed, selesai) VALUES(?, ?, ?)",
                          (anak, 18, "2026-11-21 09:00:00")).lastrowid
        skor = tb.skor_ringkas(kon, [(sid, anak)])
    assert skor == {sid: {"selesai": True, "benar": 0, "total": 0}}


def test_pasangan_melebihi_satu_potongan_semua_terbaca(belajar):
    jumlah = tb.PANJANG_POTONGAN_PASANGAN + 50
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Sembilan")
        kon.executemany("INSERT INTO sesi(siswa_id, seed, selesai) VALUES(?, ?, ?)",
                        [(anak, 100 + i, "2026-11-21 09:00:00") for i in range(jumlah)])
        pasangan = [(r["id"], anak) for r in kon.execute("SELECT id FROM sesi WHERE siswa_id=?", (anak,))]
        skor = tb.skor_ringkas(kon, pasangan)
        selesai = tb.selesai_himpunan(kon, pasangan)
    assert len(pasangan) == jumlah
    assert set(skor) == {sid for sid, _ in pasangan}
    assert selesai == set(skor)


def test_potongan_pasangan_di_bawah_batas_variabel_sqlite_lama():
    assert tb.PANJANG_POTONGAN_PASANGAN * 2 <= BATAS_PARAMETER_SQLITE_LAMA


@pytest.mark.skipif(not hasattr(sqlite3.Connection, "setlimit"),
                    reason="sqlite3.Connection.setlimit hanya ada di Python 3.11+ (celah diterima di 3.9)")
def test_pasangan_dipotong_saat_batas_variabel_sqlite_diturunkan(belajar):
    """Membuktikan pemotongan aktif: dengan batas variabel di antara satu potongan dan seluruh pasangan, 1000 pasangan
    (2000 parameter) hanya bisa terbaca bila dipotong. Tanpa potongan, kueri gagal karena terlalu banyak variabel."""
    batas = 2 * tb.PANJANG_POTONGAN_PASANGAN + 100
    jumlah = 1000
    assert 2 * tb.PANJANG_POTONGAN_PASANGAN <= batas < 2 * jumlah
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Batas")
        kon.executemany("INSERT INTO sesi(siswa_id, seed, selesai) VALUES(?, ?, ?)",
                        [(anak, 500 + i, "2026-11-21 09:00:00") for i in range(jumlah)])
        pasangan = [(r["id"], anak) for r in kon.execute("SELECT id FROM sesi WHERE siswa_id=?", (anak,))]
        kon.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, batas)
        skor = tb.skor_ringkas(kon, pasangan)
    assert len(skor) == jumlah


def test_selesai_himpunan_konsisten_dengan_skor(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Sepuluh")
        selesai_id, _ = _sesi_dengan_pola(kon, anak, 19, [1], selesai=True)
        belum_id, _ = _sesi_dengan_pola(kon, anak, 20, [1], selesai=False)
        pasangan = [(selesai_id, anak), (belum_id, anak)]
        skor = tb.skor_ringkas(kon, pasangan)
        selesai = tb.selesai_himpunan(kon, pasangan)
    assert selesai == {sid for sid, nilai in skor.items() if nilai["selesai"]} == {selesai_id}


def test_pasangan_kosong_menghasilkan_kosong_tanpa_kueri(belajar):
    with database.buka(belajar) as kon:
        assert tb.skor_ringkas(kon, []) == {}
        assert tb.selesai_himpunan(kon, iter([])) == set()


@pytest.mark.parametrize("pasangan_buruk", [
    [("1", 1)],
    [(True, 1)],
    [(0, 1)],
    [(1, None)],
])
def test_pasangan_tidak_sah_ditolak_dengan_galat_eksplisit(belajar, pasangan_buruk):
    with database.buka(belajar) as kon:
        with pytest.raises(ValueError):
            tb.skor_ringkas(kon, pasangan_buruk)


def test_skor_dan_himpunan_tanpa_tulis_dan_tanpa_kolom_rahasia(belajar):
    with database.buka(belajar) as kon:
        anak = database.tambah_siswa(kon, "Anak Uji Sebelas")
        sid, _ = _sesi_dengan_pola(kon, anak, 21, [1, 0], selesai=True)
        kon.commit()
    sql = []
    with database.buka(belajar) as kon:
        kon.set_trace_callback(sql.append)
        tb.skor_ringkas(kon, [(sid, anak)])
        tb.selesai_himpunan(kon, [(sid, anak)])
        kon.set_trace_callback(None)
    assert sql, "tidak ada kueri yang tercatat"
    assert not [s for s in sql if s.lstrip().upper().startswith(SQL_TULIS)]
    for teks in sql:
        assert not [rahasia for rahasia in SQL_RAHASIA if rahasia in teks.lower()], teks

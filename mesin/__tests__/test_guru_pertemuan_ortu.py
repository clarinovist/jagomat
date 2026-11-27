"""Riwayat kehadiran dan jurnal untuk orang tua (`guru_pertemuan_ortu.riwayat_untuk_anak`): baca-saja, data sintetis.

Kasus: Mini dengan dua anak yang statusnya berbeda, Private, pertemuan masa depan dan dibatalkan, batas dan urutan,
pertemuan yang digeser, belum tercatat (bukan tidak hadir), berkas catatan hilang/rusak/versi asing, anak tanpa
penempatan, akun atau anak lain, galat DB jadwal yang tidak ditelan, dan pembacaan yang tidak mengubah DB jadwal.
"""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as catatan
import guru_pertemuan_ortu as ortu
import jadwal_store as js
import kelas_kit
import schema_jadwal
import schema_tagihan_catatan
from pesanan_kit import AKUN_A, AKUN_B

ADMIN = "admin_sintetis"
GURU = "akun_" + "a" * 32
PADA = "2026-11-22T10:00:00"
TOPIK = "pola-bilangan"
# Mini ke-1 (21 Nov) sudah lewat, ke-2 (24 Nov) belum. Mini dan Private ke-1 (25 Nov) belum mulai pada KINI.
KINI = "2026-11-23T03:00:00"
# Semua pertemuan Mini dan Private (delapan sesi, sampai pertengahan Des) sudah lewat.
KINI_LEWAT = "2026-12-31T00:00:00"
KUNCI_ITEM = {"mulai", "hadir", "topik"}
AWALAN_TERLARANG = ("kor_", "klp_", "akun_")


# --- fixture dan pembantu ----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def env_sintetis(tmp_path, monkeypatch):
    """Tidak ada tes yang boleh menyentuh catatan asli: env diarahkan ke berkas sementara."""
    monkeypatch.setenv(catatan.ENV_DB, str(tmp_path / "env-sintetis.db"))


@pytest.fixture
def db(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    schema_tagihan_catatan.migrasikan(path)
    return path


@pytest.fixture
def berkas(tmp_path):
    return tmp_path / "catatan-ortu.db"


def _mini(kon, nama):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi="Ruang 1", guru_id=GURU, kuota=5,
                            tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)


def _tempatkan_mini(kon, kelompok_id, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "mini", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _tempatkan_privat(kon, siswa, n):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=n)
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=GURU, tanggal="2026-11-25", jam="16:30",
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


@pytest.fixture
def kelas(db):
    """Mini Alfa: anak 1 dan anak 2 (dua status berbeda). Private: anak 3 (jadwal lain dari Mini)."""
    with js.buka(db, tulis_data=True) as kon:
        kelompok = _mini(kon, "Mini Alfa")
        o1 = _tempatkan_mini(kon, kelompok, siswa=1, n=1)
        o2 = _tempatkan_mini(kon, kelompok, siswa=2, n=2)
        privat = _tempatkan_privat(kon, siswa=3, n=3)
        kon.commit()
    return {"kelompok": kelompok, "o1": o1, "o2": o2, "privat": privat}


def _sesi(db, kolom, nilai, ke):
    with js.buka(db) as kon:
        baris = kon.execute("SELECT id, mulai FROM jadwal_pertemuan WHERE %s=? AND ke=?" % kolom,
                            (nilai, ke)).fetchone()
    return {"id": baris["id"], "mulai": baris["mulai"]}


def _sesi_mini(db, kelas, ke):
    return _sesi(db, "kelompok_id", kelas["kelompok"], ke)


def _sesi_privat(db, kelas, ke):
    return _sesi(db, "order_id", kelas["privat"], ke)


def _semua_mulai_mini(db, kelas):
    return [_sesi_mini(db, kelas, ke)["mulai"] for ke in range(1, 9)]


def _semua_mulai_privat(db, kelas):
    return [_sesi_privat(db, kelas, ke)["mulai"] for ke in range(1, 9)]


def _kunci_mini(kelas, ke):
    return aturan.kunci_pertemuan(kelas["kelompok"], ke)


def _catat(berkas, kunci, sesi, hadir, topik=TOPIK):
    catatan.catat(kunci=kunci, pertemuan_id=sesi["id"], mulai=sesi["mulai"], topik=topik, hadir=hadir,
                  oleh=GURU, peran="guru", pada=PADA, path=berkas)


def _riwayat(db, berkas, siswa, akun=AKUN_A, kini=KINI, **opsi):
    with js.buka(db) as kon:
        return ortu.riwayat_untuk_anak(kon, akun, siswa, kini, path_catatan=berkas, **opsi)


def _geser_mulai(db, kelompok_id, ke, mulai_baru):
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET mulai=? WHERE kelompok_id=? AND ke=?",
                    (mulai_baru, kelompok_id, ke))
        kon.commit()


def _batalkan(db, kelompok_id, ke):
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=1 WHERE kelompok_id=? AND ke=?", (kelompok_id, ke))
        kon.commit()


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tambah(waktu, **selisih):
    return (datetime.strptime(waktu, aturan.FORMAT_WAKTU) + timedelta(**selisih)).strftime(aturan.FORMAT_WAKTU)


def _sisip_penempatan_mini(kon, order_id, kelompok_id, dibuat):
    """Penempatan Mini lewat SQL agar `dibuat` bisa diatur. Domain menolak join setelah dua pertemuan mulai."""
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,?,NULL,NULL,?,?,?,?)", (order_id, kelompok_id, dibuat, dibuat, ADMIN, ADMIN))
    kon.commit()


def _masuk_mini(db, kelas, siswa, n, dibuat):
    """Anak yang masuk kelompok Mini kelas pada waktu `dibuat`; mengembalikan order_id."""
    with js.buka(db, tulis_data=True) as kon:
        order_id = kelas_kit.lunas(kon, siswa, "mini", n=n).order_id
        _sisip_penempatan_mini(kon, order_id, kelas["kelompok"], dibuat)
    return order_id


def _geser_penempatan_privat(kon, order_id, dibuat):
    """Penempatan Private dipasang ulang dengan `dibuat` lain lewat SQL (domain tidak menerima mulai di masa lampau)."""
    kon.execute("DELETE FROM jadwal_penempatan WHERE order_id=?", (order_id,))
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                (order_id, GURU, schema_jadwal.LOKASI_PRIVATE, dibuat, dibuat, ADMIN, ADMIN))
    kon.commit()


# --- anak melihat statusnya sendiri -------------------------------------------------------------

def test_mini_dua_anak_hanya_melihat_statusnya_sendiri(db, berkas, kelas):
    # Arrange: kedua anak satu kelompok; pertemuan ke-1 tercatat dengan status berbeda
    sesi = _sesi_mini(db, kelas, 1)
    _catat(berkas, _kunci_mini(kelas, 1), sesi, {kelas["o1"]: "hadir", kelas["o2"]: "tidak_hadir"})
    label = aturan.label_topik(TOPIK)

    # Act
    riwayat_1 = _riwayat(db, berkas, siswa=1)
    riwayat_2 = _riwayat(db, berkas, siswa=2)

    # Assert
    assert riwayat_1 == [{"mulai": sesi["mulai"], "hadir": "hadir", "topik": label}]
    assert riwayat_2 == [{"mulai": sesi["mulai"], "hadir": "tidak_hadir", "topik": label}]


def test_privat_bekerja_dengan_order_sebagai_id_awal(db, berkas, kelas):
    # Private ke-1 mulai 25 Nov; kini 26 Nov memastikan hanya ke-1 yang sudah berlangsung
    sesi = _sesi_privat(db, kelas, 1)
    _catat(berkas, aturan.kunci_pertemuan(kelas["privat"], 1), sesi, {kelas["privat"]: "izin"})

    hasil = _riwayat(db, berkas, siswa=3, kini="2026-11-26T00:00:00")

    assert hasil == [{"mulai": sesi["mulai"], "hadir": "izin", "topik": aturan.label_topik(TOPIK)}]


def test_hasil_hanya_tiga_kunci_tanpa_id_order_kunci_atau_akun(db, berkas, kelas):
    # Arrange: anak lain (order lain) juga tercatat; hasil untuk anak 1 tidak boleh memuat apa pun darinya
    sesi = _sesi_mini(db, kelas, 1)
    _catat(berkas, _kunci_mini(kelas, 1), sesi, {kelas["o1"]: "izin", kelas["o2"]: "hadir"})

    # Act
    hasil = _riwayat(db, berkas, siswa=1, kini=KINI_LEWAT)

    # Assert
    teks = repr(hasil)
    assert hasil and all(set(item) == KUNCI_ITEM for item in hasil)
    assert not any(awalan in teks for awalan in AWALAN_TERLARANG)
    assert kelas["o1"] not in teks and kelas["o2"] not in teks
    assert GURU not in teks


# --- jendela waktu, batas, dan urutan ----------------------------------------------------------

def test_pertemuan_masa_depan_dan_dibatalkan_tidak_muncul(db, berkas, kelas):
    mulai_ke1 = _sesi_mini(db, kelas, 1)["mulai"]

    hasil_kini = _riwayat(db, berkas, siswa=1)
    _batalkan(db, kelas["kelompok"], 1)
    hasil_batal = _riwayat(db, berkas, siswa=1)

    assert [item["mulai"] for item in hasil_kini] == [mulai_ke1]
    assert hasil_batal == []


def test_batas_dipatuhi_dan_urut_terbaru_dulu(db, berkas, kelas):
    semua_terurut = sorted(_semua_mulai_mini(db, kelas), reverse=True)

    hasil_bawaan = _riwayat(db, berkas, siswa=1, kini=KINI_LEWAT)
    hasil_tiga = _riwayat(db, berkas, siswa=1, kini=KINI_LEWAT, batas=3)

    assert ortu.BATAS_BAWAAN == 8
    assert [item["mulai"] for item in hasil_bawaan] == semua_terurut
    assert [item["mulai"] for item in hasil_tiga] == semua_terurut[:3]


@pytest.mark.parametrize("batas", [0, -1, True, "3", 2.0])
def test_batas_tidak_sah_ditolak(db, berkas, kelas, batas):
    with pytest.raises(ValueError):
        _riwayat(db, berkas, siswa=1, batas=batas)


@pytest.mark.parametrize("akun", [None, "", "akun_pendek", 7])
def test_akun_tidak_sah_ditolak(db, berkas, kelas, akun):
    with pytest.raises(ValueError):
        _riwayat(db, berkas, siswa=1, akun=akun)


@pytest.mark.parametrize("siswa", [0, -1, True, "1", None])
def test_siswa_tidak_sah_ditolak(db, berkas, kelas, siswa):
    with pytest.raises(ValueError):
        _riwayat(db, berkas, siswa=siswa)


# --- catatan belum ada, digeser, atau tidak terbaca --------------------------------------------

def test_pertemuan_digeser_tidak_mewarisi_catatan_lama(db, berkas, kelas):
    sesi = _sesi_mini(db, kelas, 1)
    _catat(berkas, _kunci_mini(kelas, 1), sesi, {kelas["o1"]: "hadir"})
    _geser_mulai(db, kelas["kelompok"], 1, "2026-11-22T10:00:00")

    hasil = _riwayat(db, berkas, siswa=1)

    assert hasil == [{"mulai": "2026-11-22T10:00:00", "hadir": None, "topik": None}]


def test_belum_tercatat_bukan_tidak_hadir(db, berkas, kelas):
    # Arrange: pertemuan ke-1 tercatat, tetapi hanya untuk anak 2
    sesi = _sesi_mini(db, kelas, 1)
    _catat(berkas, _kunci_mini(kelas, 1), sesi, {kelas["o2"]: "tidak_hadir"})

    # Act
    hasil = _riwayat(db, berkas, siswa=1)

    # Assert: anak 1 belum tercatat, jadi None; topik pertemuan tetap tampil
    assert hasil == [{"mulai": sesi["mulai"], "hadir": None, "topik": aturan.label_topik(TOPIK)}]


def test_berkas_catatan_tidak_ada_menampilkan_item_kosong_tanpa_membuat_berkas(db, berkas, kelas):
    hasil = _riwayat(db, berkas, siswa=1)

    assert [(item["hadir"], item["topik"]) for item in hasil] == [(None, None)]
    assert not berkas.exists()


def _berkas_rusak(berkas):
    berkas.write_bytes(b"bukan basis data sqlite sama sekali")


def _berkas_versi_asing(berkas):
    with closing(sqlite3.connect(str(berkas))) as kon:
        kon.execute("PRAGMA user_version = 7")
        kon.commit()


@pytest.mark.parametrize("siapkan", [_berkas_rusak, _berkas_versi_asing], ids=["rusak", "versi_asing"])
def test_berkas_rusak_atau_versi_asing_tetap_menampilkan_item_kosong(db, berkas, kelas, siapkan):
    siapkan(berkas)
    sebelum = _hash(berkas)
    mulai_ke1 = _sesi_mini(db, kelas, 1)["mulai"]

    hasil = _riwayat(db, berkas, siswa=1)

    assert hasil == [{"mulai": mulai_ke1, "hadir": None, "topik": None}]
    assert _hash(berkas) == sebelum


# --- penempatan, anak, dan akun lain -----------------------------------------------------------

def test_anak_tanpa_penempatan_mendapat_daftar_kosong(db, berkas, kelas):
    with js.buka(db, tulis_data=True) as kon:
        kelas_kit.lunas(kon, 9, "mini", n=9)
        kon.commit()

    assert _riwayat(db, berkas, siswa=9) == []
    assert _riwayat(db, berkas, siswa=99) == []


def test_anak_lain_dan_akun_lain_tidak_melihat_pertemuan_anak_ini(db, berkas, kelas):
    mulai_privat = set(_semua_mulai_privat(db, kelas))
    mulai_mini = set(_semua_mulai_mini(db, kelas))

    hasil_privat = {item["mulai"] for item in _riwayat(db, berkas, siswa=3, kini=KINI_LEWAT)}
    hasil_mini = {item["mulai"] for item in _riwayat(db, berkas, siswa=1, kini=KINI_LEWAT)}

    assert hasil_privat == mulai_privat
    assert hasil_mini == mulai_mini
    assert _riwayat(db, berkas, siswa=1, akun=AKUN_B) == []
    assert _riwayat(db, berkas, siswa=3, akun=AKUN_B, kini=KINI_LEWAT) == []


# --- galat dan larangan tulis ------------------------------------------------------------------

def test_galat_db_jadwal_tidak_ditelan(tmp_path, berkas):
    with closing(sqlite3.connect(str(tmp_path / "jadwal-kosong.db"))) as kon:
        kon.row_factory = sqlite3.Row
        with pytest.raises(sqlite3.OperationalError):
            ortu.riwayat_untuk_anak(kon, AKUN_A, 1, KINI, path_catatan=berkas)


def test_pembacaan_tidak_mengubah_db_jadwal_dan_tidak_membuat_berkas(db, berkas, kelas):
    sebelum = _hash(db)

    for siswa in (1, 2, 3, 9):
        _riwayat(db, berkas, siswa=siswa, kini=KINI_LEWAT, batas=2)

    assert _hash(db) == sebelum
    assert not berkas.exists()


# --- pertemuan sebelum anak masuk tidak ditampilkan (anggota_masuk_form: dibuat <= mulai) -----

@pytest.mark.parametrize("sebelum_masuk", [1, 2])
def test_anak_masuk_setelah_pertemuan_berlangsung_tidak_melihat_pertemuan_itu(db, berkas, kelas, sebelum_masuk):
    # Arrange: anak 4 masuk satu jam setelah pertemuan ke-`sebelum_masuk` mulai
    mulai = _semua_mulai_mini(db, kelas)
    _masuk_mini(db, kelas, siswa=4, n=4, dibuat=_tambah(mulai[sebelum_masuk - 1], hours=1))

    # Act
    hasil = _riwayat(db, berkas, siswa=4, kini=KINI_LEWAT)

    # Assert: pertemuan sebelum masuk hilang, yang sesudahnya tetap muncul (terbaru dulu)
    assert [item["mulai"] for item in hasil] == sorted(mulai[sebelum_masuk:], reverse=True)


def test_batas_tetap_penuh_walau_ada_pertemuan_sebelum_masuk(db, berkas, kelas):
    # Arrange: anak 4 masuk setelah pertemuan ke-2; enam pertemuan sah tersisa
    mulai = _semua_mulai_mini(db, kelas)
    _masuk_mini(db, kelas, siswa=4, n=4, dibuat=_tambah(mulai[1], hours=1))
    sah_terurut = sorted(mulai[2:], reverse=True)

    # Act
    hasil_enam = _riwayat(db, berkas, siswa=4, kini=KINI_LEWAT, batas=6)
    hasil_bawaan = _riwayat(db, berkas, siswa=4, kini=KINI_LEWAT)

    # Assert: batas 6 terisi penuh dengan enam pertemuan sah; batas bawaan hanya menemukan enam
    assert [item["mulai"] for item in hasil_enam] == sah_terurut
    assert [item["mulai"] for item in hasil_bawaan] == sah_terurut


@pytest.mark.parametrize("detik, indeks_pertama", [(0, 2), (1, 3)])
def test_pertemuan_tepat_pada_mulai_ikut_aturan_anggota_masuk(db, berkas, kelas, detik, indeks_pertama):
    # Arrange: dibuat == mulai ke-3 ikut (dibuat <= mulai); satu detik sesudahnya tidak ikut
    mulai = _semua_mulai_mini(db, kelas)
    _masuk_mini(db, kelas, siswa=5, n=5, dibuat=_tambah(mulai[2], seconds=detik))

    # Act
    hasil = _riwayat(db, berkas, siswa=5, kini=KINI_LEWAT)

    # Assert
    assert [item["mulai"] for item in hasil] == sorted(mulai[indeks_pertama:], reverse=True)


def test_privat_penempatan_setelah_mulai_tidak_melihat_pertemuan_itu(db, berkas, kelas):
    # Arrange: penempatan Private anak 3 dipasang satu jam setelah pertemuan ke-1 mulai
    mulai = _semua_mulai_privat(db, kelas)
    with js.buka(db, tulis_data=True) as kon:
        _geser_penempatan_privat(kon, kelas["privat"], _tambah(mulai[0], hours=1))

    # Act
    hasil = _riwayat(db, berkas, siswa=3, kini=KINI_LEWAT)

    # Assert
    assert [item["mulai"] for item in hasil] == sorted(mulai[1:], reverse=True)


# --- cabang kunci tidak valid dan galat catatan --------------------------------------------------

def test_kunci_tidak_valid_menghasilkan_item_kosong(db, berkas, kelas, monkeypatch):
    # Arrange: catatan ada untuk pertemuan ke-1, tetapi kunci-nya dibuat tidak sah
    sesi = _sesi_mini(db, kelas, 1)
    _catat(berkas, _kunci_mini(kelas, 1), sesi, {kelas["o1"]: "hadir"})

    def _kunci_rusak(id_awal, ke):
        raise ValueError("kunci pertemuan tidak sah")

    monkeypatch.setattr(aturan, "kunci_pertemuan", _kunci_rusak)

    # Act
    hasil = _riwayat(db, berkas, siswa=1)

    # Assert: item tetap muncul dengan None, tidak dibaca dan tidak menggagalkan daftar
    assert hasil == [{"mulai": sesi["mulai"], "hadir": None, "topik": None}]

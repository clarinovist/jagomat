"""Antrean admin "N pertemuan lewat tanpa jurnal" (admin_antrean_jurnal): read-only, data sintetis.

Hitungan mengikuti R6 (guru_pertemuan_aturan): pertemuan tidak dibatalkan, punya >= 1 anggota (R4), berada di jendela
24 jam s.d. 7 hari sesudah selesai, belum punya keadaan terkini jurnal, dan mulai >= PERTEMUAN_WAJIB_SEJAK. Catatan
dibaca dari GURU_PERTEMUAN_DB sementara. Tes ini tidak membaca DB asli.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import admin_antrean as A
import admin_antrean_jurnal as aj
import admin_queries as Q
import admin_store
import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as catatan
import jadwal_store as js
import kelas_kit
import schema_jadwal
import schema_tagihan_catatan

ADMIN = "admin_sintetis"
GURU_A = "akun_" + "a" * 32
GURU_B = "akun_" + "b" * 32
OLEH = "akun_" + "c" * 32
CUTOFF = "2026-11-20T00:00:00"
KINI = "2026-11-27T12:00:00"
SEKARANG = datetime.strptime(KINI, aturan.FORMAT_WAKTU).replace(tzinfo=timezone.utc).timestamp()
MENIT = 60
BELUM = "2026-11-26T11:00:01"  # selesai + 24 jam - 1 s terhadap KINI: belum masuk antrean
TEPAT_AKSI = "2026-11-26T11:00:00"  # selesai + 24 jam tepat: masuk "perlu diisi"
RIWAYAT_TEPAT = "2026-11-20T11:00:00"  # selesai + 7 hari tepat: "riwayat" (bukan perlu diisi)
AKSI_BATAS_7_HARI = "2026-11-20T11:00:01"  # selesai + 7 hari - 1 s: masih "perlu diisi"
MASA_DEPAN = "2026-11-28T09:00:00"
GESER = "2026-11-26T09:00:00"  # pertemuan yang digeser ke jendela aksi lain
JADWAL_PRIVAT = {  # ke: (mulai, dibatalkan)
    1: (BELUM, 0),
    2: (TEPAT_AKSI, 0),
    3: (RIWAYAT_TEPAT, 0),
    4: (AKSI_BATAS_7_HARI, 0),
    5: (TEPAT_AKSI, 1),
    6: (MASA_DEPAN, 0),
    7: (MASA_DEPAN, 0),
    8: (MASA_DEPAN, 0),
}
KE_PERLU_AWAL = [2, 4]
KE_RIWAYAT_AWAL = [3]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    schema_jadwal.migrasikan(path)
    schema_tagihan_catatan.migrasikan(path)
    monkeypatch.setenv("GURU_PERTEMUAN_DB", str(_berkas_catatan(tmp_path)))
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", CUTOFF)
    return path


def _berkas_catatan(tmp_path) -> Path:
    return tmp_path / "guru-pertemuan.db"


def _hash(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _privat(kon, guru, siswa):
    tagihan = kelas_kit.lunas(kon, siswa, "private", n=siswa)  # n = benih sha bukti: harus unik per order
    js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=guru, tanggal="2026-11-23", jam="16:30",
                 sekarang=kelas_kit.SESUDAH_UPLOAD)
    return tagihan.order_id


def _atur_privat(kon, order_id, jadwal=JADWAL_PRIVAT):
    for ke, (mulai, dibatalkan) in jadwal.items():
        kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=? WHERE order_id=? AND ke=?",
                    (mulai, MENIT, dibatalkan, order_id, ke))
    kon.commit()


def _mini(kon, nama, guru):
    return js.buat_kelompok(kon, ADMIN, nama=nama, lokasi="Ruang 1", guru_id=guru, kuota=5,
                            tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)


def _atur_mini(kon, kelompok_id, mulai_ke1=TEPAT_AKSI):
    kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=0 WHERE kelompok_id=? AND ke=1",
                (mulai_ke1, MENIT, kelompok_id))
    kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=0 WHERE kelompok_id=? AND ke>1",
                (MASA_DEPAN, MENIT, kelompok_id))
    kon.commit()


@pytest.fixture()
def skenario(db):
    with js.buka(db, tulis_data=True) as kon:
        order_a = _privat(kon, GURU_A, siswa=1)
        _atur_privat(kon, order_a)
    return {"order_a": order_a}


def _id_pertemuan(db, order_id, ke) -> int:
    with js.buka(db) as kon:
        return kon.execute("SELECT id FROM jadwal_pertemuan WHERE order_id=? AND ke=?", (order_id, ke)).fetchone()[0]


def _catat(order_id, ke, mulai, pertemuan_id):
    catatan.catat(kunci=aturan.kunci_pertemuan(order_id, ke), pertemuan_id=pertemuan_id, mulai=mulai,
                  topik="lainnya", hadir={order_id: "hadir"}, oleh=OLEH, peran="guru",
                  pada="2026-11-27T10:00:00")


def _kes(items) -> list:
    return [item["ke"] for item in items]


# --- cutoff dan hitungan dasar -----------------------------------------------------------------

def test_cutoff_kosong_tidak_membuka_db_admin(db, skenario, monkeypatch):
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", None)

    def jangan_buka(*_args, **_kwargs):
        raise AssertionError("DB admin tidak boleh dibuka saat butir mati")

    monkeypatch.setattr(js, "buka", jangan_buka)
    assert aj.jumlah(db, SEKARANG) == 0
    hasil = aj.daftar(db, SEKARANG)
    assert hasil["aktif"] is False and hasil["sejak"] is None
    assert hasil["perlu_diisi"] == [] and hasil["total_perlu_diisi"] == 0
    assert hasil["riwayat"] == [] and hasil["total_riwayat"] == 0
    assert hasil["riwayat_terpotong"] is False and hasil["catatan_terbaca"] is True


def test_hitungan_di_batas_24_jam_dan_7_hari(db, skenario):
    hasil = aj.daftar(db, SEKARANG)
    assert hasil["aktif"] is True and hasil["sejak"] == CUTOFF
    assert _kes(hasil["perlu_diisi"]) == KE_PERLU_AWAL
    assert hasil["total_perlu_diisi"] == 2
    assert _kes(hasil["riwayat"]) == KE_RIWAYAT_AWAL
    assert hasil["total_riwayat"] == 1
    assert hasil["riwayat_terpotong"] is False and hasil["catatan_terbaca"] is True
    assert aj.jumlah(db, SEKARANG) == 2


def test_pertemuan_dibatalkan_tidak_dihitung(db, skenario):
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET dibatalkan=1 WHERE order_id=? AND ke=2", (skenario["order_a"],))
        kon.commit()
    assert _kes(aj.daftar(db, SEKARANG)["perlu_diisi"]) == [4]


def test_tanpa_anggota_tidak_dihitung(db):
    with js.buka(db, tulis_data=True) as kon:
        kelompok_id = _mini(kon, "Mini Kosong", GURU_A)
        _atur_mini(kon, kelompok_id)
    assert aj.jumlah(db, SEKARANG) == 0


def _sisip_privat_belum_lunas(kon, siswa, guru):
    """Penempatan + 8 pertemuan langsung lewat SQL untuk order yang BELUM lunas (tidak aktif). Pola test_guru_jadwal_baca."""
    tagihan = kelas_kit.tagih(kon, siswa, "private")
    kon.execute("INSERT INTO jadwal_penempatan(order_id,kelompok_id,guru_id,lokasi,dibuat,diubah,dibuat_oleh,"
                "diubah_oleh) VALUES(?,NULL,?,?,?,?,?,?)",
                (tagihan.order_id, guru, schema_jadwal.LOKASI_PRIVATE, "2026-11-20T09:00:00",
                 "2026-11-20T09:00:00", ADMIN, ADMIN))
    for ke in range(1, 9):
        mulai = TEPAT_AKSI if ke == 1 else MASA_DEPAN
        kon.execute("INSERT INTO jadwal_pertemuan(kelompok_id,order_id,ke,mulai,menit,dibatalkan,diubah,"
                    "diubah_oleh) VALUES(NULL,?,?,?,?,0,?,?)",
                    (tagihan.order_id, ke, mulai, MENIT, "2026-11-20T09:00:00", ADMIN))
    kon.commit()


def test_order_belum_lunas_tidak_dihitung_walau_tertempel(db):
    with js.buka(db, tulis_data=True) as kon:
        _sisip_privat_belum_lunas(kon, 6, GURU_A)
    assert aj.jumlah(db, SEKARANG) == 0


def test_penempatan_masuk_sesudah_pertemuan_tidak_dihitung(db, skenario):
    # Penempatan dibuat 22 Nov, sesudah pertemuan ke-1 (21 Nov) yang sudah lewat: R4 mengecualikannya dari form
    # dan dari antrean. Tabel penempatan tidak bisa diubah (trigger), jadi keadaan ini dibuat lewat domain.
    jadwal = {1: ("2026-11-21T10:00:00", 0)}
    jadwal.update({ke: (MASA_DEPAN, 0) for ke in range(2, 9)})
    with js.buka(db, tulis_data=True) as kon:
        tagihan = kelas_kit.lunas(kon, 5, "private", n=5)
        js.tempatkan(kon, ADMIN, tagihan.order_id, guru_id=GURU_A, tanggal="2026-11-23", jam="16:30",
                     sekarang="2026-11-22T09:00:00")
        _atur_privat(kon, tagihan.order_id, jadwal)
    assert aj.jumlah(db, SEKARANG) == 2


def test_mulai_di_bawah_cutoff_tidak_dihitung(db, skenario, monkeypatch):
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", "2026-11-26T11:30:00")
    assert aj.jumlah(db, SEKARANG) == 0
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", TEPAT_AKSI)
    hasil = aj.daftar(db, SEKARANG)
    assert _kes(hasil["perlu_diisi"]) == [2] and hasil["riwayat"] == []


def test_mini_dan_privat_dihitung_dari_semua_guru(db, skenario):
    with js.buka(db, tulis_data=True) as kon:
        kelompok_id = _mini(kon, "Mini Beta", GURU_B)
        tagihan = kelas_kit.lunas(kon, 3, "mini", n=3)
        js.tempatkan(kon, ADMIN, tagihan.order_id, kelompok_id=kelompok_id, sekarang=kelas_kit.SESUDAH_UPLOAD)
        _atur_mini(kon, kelompok_id)
    perlu = aj.daftar(db, SEKARANG)["perlu_diisi"]
    assert sorted(item["jenis"] for item in perlu) == ["kelompok", "privat", "privat"]
    assert {item["guru_id"] for item in perlu} == {GURU_A, GURU_B}
    assert {item["nama"] for item in perlu if item["jenis"] == "kelompok"} == {"Mini Beta"}
    assert {item["nama"] for item in perlu if item["jenis"] == "privat"} == {"Private"}


# --- jurnal terkini dan snapshot ---------------------------------------------------------------

def test_jurnal_terkini_menghapus_butir(db, skenario):
    order_a = skenario["order_a"]
    _catat(order_a, ke=2, mulai=TEPAT_AKSI, pertemuan_id=_id_pertemuan(db, order_a, 2))
    assert _kes(aj.daftar(db, SEKARANG)["perlu_diisi"]) == [4]
    assert aj.jumlah(db, SEKARANG) == 1


def test_jurnal_pada_mulai_lama_tidak_berlaku_setelah_pertemuan_digeser(db, skenario):
    order_a = skenario["order_a"]
    _catat(order_a, ke=2, mulai=TEPAT_AKSI, pertemuan_id=_id_pertemuan(db, order_a, 2))
    with js.buka(db, tulis_data=True) as kon:
        kon.execute("UPDATE jadwal_pertemuan SET mulai=? WHERE order_id=? AND ke=2", (GESER, order_a))
        kon.commit()
    assert _kes(aj.daftar(db, SEKARANG)["perlu_diisi"]) == KE_PERLU_AWAL


# --- batas ukuran dan bentuk item --------------------------------------------------------------

def test_riwayat_terpotong_saat_kandidat_mencapai_batas(db, skenario, monkeypatch):
    monkeypatch.setattr(aj, "BATAS_KANDIDAT", 3)
    assert aj.daftar(db, SEKARANG)["riwayat_terpotong"] is True
    monkeypatch.setattr(aj, "BATAS_KANDIDAT", 500)
    assert aj.daftar(db, SEKARANG)["riwayat_terpotong"] is False


def test_item_hanya_memuat_kolom_aman(db, skenario):
    hasil = aj.daftar(db, SEKARANG)
    for item in hasil["perlu_diisi"] + hasil["riwayat"]:
        assert set(item) == {"jenis", "nama", "ke", "mulai", "guru_id"}
    teks = json.dumps(hasil, ensure_ascii=False)
    assert skenario["order_a"] not in teks
    assert "kor_" not in teks and "klp_" not in teks


def test_daftar_membatasi_lima_puluh_item_dan_menghitung_penuh(db):
    awal = datetime(2026, 11, 21, 10, 0, 0)
    with js.buka(db, tulis_data=True) as kon:
        orders = [_privat(kon, GURU_A, siswa) for siswa in range(10, 17)]
        urutan = 0
        for order_id in orders:
            for ke in range(1, 9):
                mulai = (awal + timedelta(hours=urutan)).strftime(aturan.FORMAT_WAKTU)
                kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=0 WHERE order_id=? AND ke=?",
                            (mulai, MENIT, order_id, ke))
                urutan += 1
        kon.commit()
    hasil = aj.daftar(db, SEKARANG)
    assert len(hasil["perlu_diisi"]) == 50
    assert hasil["total_perlu_diisi"] == 56


def test_jumlah_hanya_memeriksa_jendela_aksi_bukan_riwayat(db, skenario, monkeypatch):
    """`jumlah` dipanggil di setiap render sinyal admin: riwayat lama tidak boleh ikut dibaca/diperiksa anggotanya."""
    asli = aj.gb.anggota_order_pertemuan
    diperiksa = []

    def rekam(kon, order_id, mulai, waktu):
        diperiksa.append(mulai)
        return asli(kon, order_id, mulai, waktu)

    monkeypatch.setattr(aj.gb, "anggota_order_pertemuan", rekam)

    assert aj.jumlah(db, SEKARANG) == 2
    assert RIWAYAT_TEPAT not in diperiksa
    assert sorted(diperiksa) == sorted([TEPAT_AKSI, AKSI_BATAS_7_HARI])


def test_daftar_membatasi_lima_puluh_riwayat_dan_menghitung_penuh(db):
    awal = datetime(2026, 11, 20, 9, 30, 0)
    with js.buka(db, tulis_data=True) as kon:
        orders = [_privat(kon, GURU_A, siswa) for siswa in range(10, 17)]
        urutan = 0
        for order_id in orders:
            for ke in range(1, 9):
                mulai = (awal + timedelta(minutes=urutan)).strftime(aturan.FORMAT_WAKTU)
                kon.execute("UPDATE jadwal_pertemuan SET mulai=?, menit=?, dibatalkan=0 WHERE order_id=? AND ke=?",
                            (mulai, MENIT, order_id, ke))
                urutan += 1
        kon.commit()
    hasil = aj.daftar(db, SEKARANG)
    assert hasil["perlu_diisi"] == []
    assert len(hasil["riwayat"]) == 50
    assert hasil["total_riwayat"] == 56


def test_pembacaan_tidak_mengubah_db_admin(db, skenario):
    sebelum = _hash(db)
    aj.daftar(db, SEKARANG)
    aj.jumlah(db, SEKARANG)
    assert _hash(db) == sebelum


# --- catatan dan galat baca --------------------------------------------------------------------

def test_catatan_belum_ada_berarti_semua_dihitung_tanpa_membuat_berkas(db, skenario, tmp_path):
    berkas = _berkas_catatan(tmp_path)
    assert not berkas.exists()
    assert aj.jumlah(db, SEKARANG) == 2
    assert not berkas.exists()


def test_catatan_rusak_menghasilkan_nol_dan_tidak_terbaca(db, skenario, tmp_path):
    _berkas_catatan(tmp_path).write_bytes(b"bukan sqlite " * 100)
    hasil = aj.daftar(db, SEKARANG)
    assert hasil["catatan_terbaca"] is False
    assert hasil["perlu_diisi"] == [] and hasil["total_perlu_diisi"] == 0
    assert hasil["riwayat"] == [] and hasil["total_riwayat"] == 0
    assert aj.jumlah(db, SEKARANG) == 0


def test_catatan_versi_asing_ditolak_sebagai_tidak_terbaca(db, skenario, tmp_path):
    with closing(sqlite3.connect(str(_berkas_catatan(tmp_path)))) as kon:
        kon.execute("PRAGMA user_version = 2")
        kon.commit()
    hasil = aj.daftar(db, SEKARANG)
    assert hasil["catatan_terbaca"] is False and hasil["total_perlu_diisi"] == 0


def test_db_admin_belum_dipasang_menghasilkan_nol_tanpa_galat(tmp_path, monkeypatch):
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", CUTOFF)
    belum = tmp_path / "belum-ada.db"
    assert aj.jumlah(belum, SEKARANG) == 0
    assert not belum.exists()


def test_db_admin_rusak_menghasilkan_nol_dan_daftar_melempar_galat_baca(tmp_path, monkeypatch):
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", CUTOFF)
    rusak = tmp_path / "rusak.db"
    rusak.write_bytes(b"bukan sqlite " * 100)
    assert aj.jumlah(rusak, SEKARANG) == 0
    with pytest.raises(aj.GALAT_BACA):
        aj.daftar(rusak, SEKARANG)


# --- butir di kumpulkan ------------------------------------------------------------------------

def test_kumpulkan_menambah_butir_tinjau_tanpa_mengubah_perlu_keputusan(db, skenario, monkeypatch):
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", None)
    tanpa = A.kumpulkan(Q.KonteksAdmin((), (), ()), db, sekarang=SEKARANG)
    assert not [i for i in tanpa.item if i.jalur == A.JALUR_JURNAL]
    monkeypatch.setattr(aturan, "PERTEMUAN_WAJIB_SEJAK", CUTOFF)
    dengan = A.kumpulkan(Q.KonteksAdmin((), (), ()), db, sekarang=SEKARANG)
    assert dengan.total == tanpa.total + 1
    assert dengan.perlu_keputusan == tanpa.perlu_keputusan
    assert dengan.mendesak == tanpa.mendesak
    (butir,) = [i for i in dengan.item if i.jalur == A.JALUR_JURNAL]
    assert butir.tingkat == "tinjau"
    assert butir.judul == "2 pertemuan lewat tanpa jurnal"
    assert butir.deskripsi == A.KALIMAT_JURNAL
    assert butir.cta == "Lihat daftar"
    assert "akun_" not in butir.deskripsi and "kor_" not in butir.deskripsi

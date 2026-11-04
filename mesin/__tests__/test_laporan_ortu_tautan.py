"""Tahap 1 G3: schema, token bearer baca-saja, dan store laporan guru -> orang tua."""
import hashlib
import json
import sqlite3

import pytest

import database
import parent_report_links as tautan
import parent_report_store as toko

ISI = {"versi": 1, "topik": ["Pola Bilangan"], "tahap": {"nomor": 3, "label": "Latihan"},
       "langkah": "Coba sendiri beberapa soal pendek."}
SEKARANG = 1_800_000_000


@pytest.fixture
def kon(tmp_path):
    path = tmp_path / "g3.db"
    database.siapkan(path)
    with database.buka(path) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis", pemilik="guru")


def _draf(kon, siswa_id, mulai="2026-11-01", akhir="2026-11-30", isi=None):
    return toko.buat_draf(kon, siswa_id, mulai, akhir, isi or ISI)


def _terbit(kon, siswa_id, laporan_id, guru="Guru Uji", sekarang=SEKARANG):
    return toko.terbitkan(kon, siswa_id, laporan_id, guru, sekarang=sekarang)


def test_tabel_baru_ada_dan_siapkan_idempoten(tmp_path):
    path = tmp_path / "idem.db"
    database.siapkan(path)
    database.siapkan(path)
    with database.buka(path) as k:
        tabel = {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"laporan_ortu", "tautan_laporan"} <= tabel
        assert k.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert k.execute("PRAGMA foreign_key_check").fetchall() == []


def test_periode_terbalik_dan_catatan_terlalu_panjang_ditolak(kon, anak):
    with pytest.raises(sqlite3.IntegrityError):
        _draf(kon, anak, mulai="2026-12-01", akhir="2026-11-01")
    laporan_id = _draf(kon, anak)
    with pytest.raises(ValueError):
        toko.simpan_catatan(kon, anak, laporan_id, "x" * 2001)


def test_token_43_karakter_disimpan_sebagai_hash(kon, anak):
    laporan_id = _draf(kon, anak)
    token = _terbit(kon, anak, laporan_id)
    assert len(token) == 43
    baris = kon.execute("SELECT token_hash FROM tautan_laporan WHERE siswa_id = ?", (anak,)).fetchone()
    assert baris["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    semua = json.dumps([tuple(r) for r in kon.execute("SELECT * FROM tautan_laporan")])
    assert token not in semua


def test_ttl_tiga_puluh_hari_dan_kedaluwarsa(kon, anak):
    token = _terbit(kon, anak, _draf(kon, anak))
    assert tautan.TTL_DETIK == 30 * 24 * 60 * 60
    assert toko.ambil_dengan_token(kon, token, SEKARANG + tautan.TTL_DETIK - 1) is not None
    assert toko.ambil_dengan_token(kon, token, SEKARANG + tautan.TTL_DETIK) is None


def test_draf_belum_bisa_dibuka_dan_terbit_tidak_bisa_diulang(kon, anak):
    laporan_id = _draf(kon, anak)
    assert kon.execute("SELECT diterbitkan FROM laporan_ortu").fetchone()[0] is None
    _terbit(kon, anak, laporan_id)
    with pytest.raises(ValueError):
        _terbit(kon, anak, laporan_id)


def test_terbit_membaca_snapshot_dan_nama_live(kon, anak):
    laporan_id = _draf(kon, anak)
    toko.simpan_catatan(kon, anak, laporan_id, "Sudah lebih tenang.")
    token = _terbit(kon, anak, laporan_id, guru="Bu Feby")
    kon.execute("UPDATE siswa SET nama = 'Nama Baru' WHERE id = ?", (anak,))
    hasil = toko.ambil_dengan_token(kon, token, SEKARANG + 10)
    assert hasil["nama"] == "Nama Baru"
    assert hasil["isi"]["tahap"] == {"nomor": 3, "label": "Latihan"}
    assert hasil["catatan"] == "Sudah lebih tenang."
    assert hasil["guru"] == "Bu Feby"
    assert hasil["periode"] == ("2026-11-01", "2026-11-30")


def test_catatan_tidak_bisa_diubah_setelah_terbit(kon, anak):
    laporan_id = _draf(kon, anak)
    _terbit(kon, anak, laporan_id)
    with pytest.raises(ValueError):
        toko.simpan_catatan(kon, anak, laporan_id, "ubah")


def test_satu_tautan_aktif_per_anak_terbit_baru_mematikan_lama(kon, anak):
    lama = _terbit(kon, anak, _draf(kon, anak))
    baru = _terbit(kon, anak, _draf(kon, anak, "2026-12-01", "2026-12-31"), sekarang=SEKARANG + 5)
    assert toko.ambil_dengan_token(kon, lama, SEKARANG + 6) is None
    assert toko.ambil_dengan_token(kon, baru, SEKARANG + 6)["periode"][0] == "2026-12-01"
    assert kon.execute("SELECT COUNT(*) FROM tautan_laporan").fetchone()[0] == 1


def test_ganti_dan_cabut_tautan(kon, anak):
    laporan_id = _draf(kon, anak)
    awal = _terbit(kon, anak, laporan_id)
    ganti = toko.ganti_tautan(kon, anak, laporan_id, sekarang=SEKARANG + 1)
    assert ganti != awal
    assert toko.ambil_dengan_token(kon, awal, SEKARANG + 2) is None
    assert toko.ambil_dengan_token(kon, ganti, SEKARANG + 2) is not None
    assert toko.cabut_tautan(kon, anak, sekarang=SEKARANG + 3) is True
    assert toko.cabut_tautan(kon, anak, sekarang=SEKARANG + 4) is False
    assert toko.ambil_dengan_token(kon, ganti, SEKARANG + 5) is None
    # Tautan yang sudah dicabut tidak hidup lagi; hanya token baru yang sah.
    token_baru = toko.ganti_tautan(kon, anak, laporan_id, sekarang=SEKARANG + 6)
    assert toko.ambil_dengan_token(kon, ganti, SEKARANG + 7) is None
    assert toko.ambil_dengan_token(kon, token_baru, SEKARANG + 7) is not None


@pytest.mark.parametrize("token", ["", "x" * 43, "x" * 41, "é" * 43, None, 12345, b"x" * 43, "a" * 42 + "+"])
def test_token_tidak_sah_tidak_menyentuh_data(kon, anak, token):
    _terbit(kon, anak, _draf(kon, anak))
    assert toko.ambil_dengan_token(kon, token, SEKARANG + 1) is None


def test_hapus_draf_tapi_bukan_laporan_terbit(kon, anak):
    draf = _draf(kon, anak)
    assert toko.hapus_draf(kon, anak, draf) is True
    terbit = _draf(kon, anak)
    _terbit(kon, anak, terbit)
    with pytest.raises(ValueError):
        toko.hapus_draf(kon, anak, terbit)


def test_laporan_anak_lain_tidak_bisa_dikelola_lewat_id_anak_salah(kon, anak):
    lain = database.tambah_siswa(kon, "Anak Lain", pemilik="guru-lain")
    laporan_id = _draf(kon, anak)
    assert toko.ambil(kon, lain, laporan_id) is None
    with pytest.raises(ValueError):
        toko.simpan_catatan(kon, lain, laporan_id, "bukan milikmu")
    with pytest.raises(ValueError):
        _terbit(kon, lain, laporan_id)
    assert kon.execute("SELECT diterbitkan FROM laporan_ortu WHERE id = ?", (laporan_id,)).fetchone()[0] is None


def test_fk_komposit_menolak_tautan_ke_laporan_anak_lain(kon, anak):
    lain = database.tambah_siswa(kon, "Anak Lain", pemilik="guru-lain")
    laporan_id = _draf(kon, anak)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(
            "INSERT INTO tautan_laporan (siswa_id, laporan_id, token_hash, dibuat, kedaluarsa) VALUES (?, ?, ?, 1, 2)",
            (lain, laporan_id, "h" * 64),
        )


def test_hapus_anak_tanpa_bukti_menghapus_laporan_dan_tautan(kon, anak):
    _terbit(kon, anak, _draf(kon, anak))
    kon.execute("DELETE FROM siswa WHERE id = ?", (anak,))
    assert kon.execute("SELECT COUNT(*) FROM laporan_ortu").fetchone()[0] == 0
    assert kon.execute("SELECT COUNT(*) FROM tautan_laporan").fetchone()[0] == 0


def test_penanda_bukti_berubah(kon, anak):
    laporan_id = _draf(kon, anak)
    _terbit(kon, anak, laporan_id)
    assert toko.bukti_berubah(kon, anak, laporan_id) == 0
    kon.execute("INSERT INTO kejadian_belajar (siswa_id, jenis) VALUES (?, 'uji')", (anak,))
    assert toko.bukti_berubah(kon, anak, laporan_id) == 1


def test_migrasi_db_pra_fitur_menambah_tabel_tanpa_mengubah_histori(tmp_path):
    path = tmp_path / "lama.db"
    database.siapkan(path)
    with database.buka(path) as k:
        siswa = database.tambah_siswa(k, "Anak Lama", pemilik="guru")
        database.buat_sesi(k, siswa, 7, jumlah_soal=3)
        k.execute("DROP TABLE tautan_laporan")
        k.execute("DROP TABLE laporan_ortu")
        sebelum = {t: k.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in ("siswa", "sesi", "sesi_soal", "soal")}
    database.siapkan(path)
    with database.buka(path) as k:
        assert {t: k.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in sebelum} == sebelum
        assert {"laporan_ortu", "tautan_laporan"} <= {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert k.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert k.execute("PRAGMA foreign_key_check").fetchall() == []
        pertama = tuple(k.iterdump())
    database.siapkan(path)
    with database.buka(path) as k:
        assert tuple(k.iterdump()) == pertama

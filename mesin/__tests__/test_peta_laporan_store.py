"""Store dan skema laporan Peta untuk orang tua (D1-1): siklus draf-catatan-terbit, trigger, cascade.

Data sintetis di basis sementara. Penjagaan DB diuji dengan SQL langsung (melewati store) supaya trigger/UNIQUE/CHECK
terbukti berdiri sendiri; tes di sini menjadi sasaran mutation di `test_peta_laporan_mutation.py`.
"""
from __future__ import annotations

import calendar
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import peta_laporan_snapshot as snap  # noqa: E402
import peta_laporan_store as store  # noqa: E402

GURU, GURU_LAIN = "guru-a", "guru-b"
SEKARANG = calendar.timegm((2026, 11, 24, 8, 0, 0))  # 15:00 WIB
SEKARANG_WIB = "2026-11-24 15:00:00"
LEBIH_LAMBAT = SEKARANG + 3600
CATATAN = "Anak sudah mantap berhitung; latih pengukuran tiga kali seminggu."


def _isi(**ubah) -> dict:
    isi = {
        "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
        "jumlah_soal": 15,
        "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                       {"materi": "Pengukuran", "benar": 2, "total": 5}],
        "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran"], "ringkasan_perlu": [],
    }
    return {**isi, **ubah}


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "peta.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _anak(kon, nama="Anak Sintetis", pemilik=GURU) -> int:
    return database.tambah_siswa(kon, nama, "P4", pemilik=pemilik)


def _draf(kon, siswa_id=None, isi=None) -> int:
    siswa_id = _anak(kon) if siswa_id is None else siswa_id
    store.buat_draf(kon, siswa_id, GURU, _isi() if isi is None else isi, SEKARANG)
    return siswa_id


def _terbit(kon, siswa_id=None) -> int:
    siswa_id = _draf(kon, siswa_id)
    store.simpan_catatan(kon, siswa_id, CATATAN)
    store.terbitkan(kon, siswa_id, GURU_LAIN, LEBIH_LAMBAT)
    return siswa_id


def _baris(kon, siswa_id):
    return tuple(kon.execute("SELECT * FROM peta_laporan WHERE siswa_id = ?", (siswa_id,)).fetchone())


def _tolak_sql(kon, sql, args=()):
    awal = kon.total_changes
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute(sql, args)
    assert kon.total_changes == awal


# --- siklus lewat store ----------------------------------------------------------------

def test_buat_draf_menyimpan_snapshot_guru_dan_waktu_wib(kon):
    anak = _anak(kon)
    nomor = store.buat_draf(kon, anak, GURU, _isi(), SEKARANG)
    laporan = store.ambil(kon, anak)
    assert laporan["id"] == nomor and laporan["siswa_id"] == anak
    assert laporan["isi"] == _isi() and laporan["catatan"] == ""
    assert laporan["guru"] == GURU and laporan["dibuat"] == SEKARANG_WIB
    assert laporan["diterbitkan"] is None and laporan["diterbitkan_oleh"] is None


def test_siklus_draf_catatan_terbit_lengkap(kon):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, "Catatan awal")
    store.simpan_catatan(kon, anak, CATATAN)
    waktu = store.terbitkan(kon, anak, GURU_LAIN, LEBIH_LAMBAT)
    laporan = store.ambil(kon, anak)
    assert waktu == "2026-11-24 16:00:00" == laporan["diterbitkan"]
    assert laporan["diterbitkan_oleh"] == GURU_LAIN and laporan["guru"] == GURU
    assert laporan["catatan"] == CATATAN and laporan["isi"] == _isi()


def test_ambil_tanpa_laporan_none(kon):
    assert store.ambil(kon, _anak(kon)) is None


def test_draf_kedua_untuk_anak_yang_sama_ditolak(kon):
    anak = _draf(kon)
    with pytest.raises(ValueError):
        store.buat_draf(kon, anak, GURU_LAIN, _isi(skor=10), SEKARANG)
    assert store.ambil(kon, anak)["isi"]["skor"] == 47


def test_draf_kedua_setelah_terbit_juga_ditolak(kon):
    anak = _terbit(kon)
    with pytest.raises(ValueError):
        store.buat_draf(kon, anak, GURU, _isi(), SEKARANG)
    assert store.ambil(kon, anak)["diterbitkan"] is not None


def test_draf_untuk_dua_anak_berbeda_boleh(kon):
    a, b = _anak(kon, "A"), _anak(kon, "B")
    _draf(kon, a), _draf(kon, b)
    assert store.ambil(kon, a)["id"] != store.ambil(kon, b)["id"]


def test_buat_draf_menolak_isi_di_luar_allowlist(kon):
    anak = _anak(kon)
    with pytest.raises(ValueError):
        store.buat_draf(kon, anak, GURU, {**_isi(), "nama": "Anak Sintetis"}, SEKARANG)
    with pytest.raises(ValueError):
        store.buat_draf(kon, anak, GURU, _isi(skor=500), SEKARANG)
    assert store.ambil(kon, anak) is None


@pytest.mark.parametrize("guru", ["", "g" * 65, None, 7])
def test_buat_draf_menolak_akun_guru_tak_sah(kon, guru):
    anak = _anak(kon)
    with pytest.raises(ValueError):
        store.buat_draf(kon, anak, guru, _isi(), SEKARANG)
    assert store.ambil(kon, anak) is None


@pytest.mark.parametrize("waktu", [None, "2026-11-24", 1.5, True])
def test_waktu_harus_epoch_bulat(kon, waktu):
    anak = _anak(kon)
    with pytest.raises(ValueError):
        store.buat_draf(kon, anak, GURU, _isi(), waktu)
    _draf(kon, anak)
    store.simpan_catatan(kon, anak, CATATAN)
    with pytest.raises(ValueError):
        store.terbitkan(kon, anak, GURU, waktu)
    assert store.ambil(kon, anak)["diterbitkan"] is None


def test_simpan_catatan_batas_dua_ribu_karakter(kon):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, "c" * 2000)
    with pytest.raises(ValueError):
        store.simpan_catatan(kon, anak, "c" * 2001)
    with pytest.raises(ValueError):
        store.simpan_catatan(kon, anak, None)
    assert store.ambil(kon, anak)["catatan"] == "c" * 2000


def test_simpan_catatan_tanpa_laporan_ditolak(kon):
    with pytest.raises(ValueError):
        store.simpan_catatan(kon, _anak(kon), "x")


def test_simpan_catatan_pada_laporan_terbit_ditolak_dan_tidak_berubah(kon):
    anak = _terbit(kon)
    sebelum = _baris(kon, anak)
    with pytest.raises(ValueError):
        store.simpan_catatan(kon, anak, "diubah diam-diam")
    assert _baris(kon, anak) == sebelum


def test_catatan_anak_lain_tidak_tersentuh(kon):
    a, b = _draf(kon, _anak(kon, "A")), _draf(kon, _anak(kon, "B"))
    store.simpan_catatan(kon, a, "untuk A")
    assert store.ambil(kon, b)["catatan"] == ""


@pytest.mark.parametrize("catatan", ["", "   ", "\n\n", " \t\r\n "])
def test_terbit_butuh_catatan_tidak_kosong(kon, catatan):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, catatan)
    with pytest.raises(ValueError):
        store.terbitkan(kon, anak, GURU, SEKARANG)
    laporan = store.ambil(kon, anak)
    assert laporan["diterbitkan"] is None and laporan["diterbitkan_oleh"] is None


def test_terbit_kedua_kali_ditolak_dan_tidak_mengubah_penerbit_atau_waktu(kon):
    anak = _terbit(kon)
    sebelum = _baris(kon, anak)
    with pytest.raises(ValueError):
        store.terbitkan(kon, anak, GURU, LEBIH_LAMBAT + 99)
    assert _baris(kon, anak) == sebelum


def test_terbitkan_tanpa_laporan_ditolak(kon):
    with pytest.raises(ValueError):
        store.terbitkan(kon, _anak(kon), GURU, SEKARANG)


def test_hapus_draf_menghapus_draf_lalu_draf_baru_boleh(kon):
    anak = _draf(kon)
    assert store.hapus_draf(kon, anak) is True
    assert store.ambil(kon, anak) is None
    assert store.hapus_draf(kon, anak) is False
    _draf(kon, anak)
    assert store.ambil(kon, anak) is not None


def test_hapus_draf_tidak_menghapus_laporan_terbit(kon):
    anak = _terbit(kon)
    sebelum = _baris(kon, anak)
    with pytest.raises(ValueError):
        store.hapus_draf(kon, anak)
    assert _baris(kon, anak) == sebelum


def test_hapus_draf_anak_lain_tidak_tersentuh(kon):
    a, b = _draf(kon, _anak(kon, "A")), _draf(kon, _anak(kon, "B"))
    store.hapus_draf(kon, a)
    assert store.ambil(kon, b) is not None


def test_tulis_dalam_transaksi_pemanggil_tanpa_commit_sendiri(kon):
    anak = _anak(kon)
    kon.commit()
    store.buat_draf(kon, anak, GURU, _isi(), SEKARANG)
    kon.rollback()
    assert store.ambil(kon, anak) is None


# --- terbit_terakhir -----------------------------------------------------------------

def test_terbit_terakhir_menyembunyikan_draf(kon):
    anak = _draf(kon)
    store.simpan_catatan(kon, anak, CATATAN)
    assert store.terbit_terakhir(kon, anak) is None
    assert store.terbit_terakhir(kon, _anak(kon, "Tanpa laporan")) is None


def test_terbit_terakhir_hanya_isi_catatan_dan_waktu_tanpa_akun_guru(kon):
    anak = _terbit(kon)
    hasil = store.terbit_terakhir(kon, anak)
    assert set(hasil) == {"isi", "catatan", "diterbitkan"}
    assert hasil["isi"] == _isi() and hasil["catatan"] == CATATAN
    assert hasil["diterbitkan"] == "2026-11-24 16:00:00"
    teks = json.dumps(hasil)
    assert GURU not in teks and GURU_LAIN not in teks


# --- isi diperiksa ulang saat dibaca -----------------------------------------------------

def _sisip_mentah(kon, siswa_id, isi_teks, terbit=False):
    kon.execute(
        "INSERT INTO peta_laporan (siswa_id, isi, catatan, guru, dibuat) VALUES (?, ?, ?, ?, '2026-11-24 15:00:00')",
        (siswa_id, isi_teks, CATATAN, GURU))
    if terbit:
        kon.execute("UPDATE peta_laporan SET diterbitkan = '2026-11-24 16:00:00', diterbitkan_oleh = ? "
                    "WHERE siswa_id = ?", (GURU, siswa_id))


@pytest.mark.parametrize("isi_teks", [
    json.dumps({**_isi(), "nama": "Anak Sintetis"}),
    json.dumps({k: v for k, v in _isi().items() if k != "skor"}),
    json.dumps(_isi(skor="47")),
    json.dumps(_isi(per_materi=[{"materi": "A", "benar": 9, "total": 5}])),
    "[]",
    "bukan json",
])
def test_baris_dengan_isi_di_luar_allowlist_ditolak_saat_dibaca(kon, isi_teks):
    anak = _anak(kon)
    _sisip_mentah(kon, anak, isi_teks, terbit=True)
    with pytest.raises(ValueError):
        store.ambil(kon, anak)
    with pytest.raises(ValueError):
        store.terbit_terakhir(kon, anak)


def test_draf_dengan_isi_rusak_tidak_bisa_diterbitkan(kon):
    anak = _anak(kon)
    _sisip_mentah(kon, anak, json.dumps({**_isi(), "nama": "x"}))
    with pytest.raises(ValueError):
        store.terbitkan(kon, anak, GURU, SEKARANG)
    assert kon.execute("SELECT diterbitkan FROM peta_laporan").fetchone()[0] is None


# --- penjagaan DB lewat SQL langsung (melewati store) -----------------------------------------

@pytest.mark.parametrize("sql", [
    "UPDATE peta_laporan SET catatan = 'diubah'",
    "UPDATE peta_laporan SET diterbitkan = '2030-01-01 00:00:00'",
    "UPDATE peta_laporan SET diterbitkan = NULL, diterbitkan_oleh = NULL",
    "UPDATE peta_laporan SET diterbitkan_oleh = 'guru-x'",
    "UPDATE peta_laporan SET catatan = catatan",
])
def test_laporan_terbit_tidak_bisa_di_update_sama_sekali(kon, sql):
    anak = _terbit(kon)
    sebelum = _baris(kon, anak)
    _tolak_sql(kon, sql)
    assert _baris(kon, anak) == sebelum


@pytest.mark.parametrize("sql,args", [
    ("UPDATE peta_laporan SET isi = ?", (json.dumps(_isi(skor=1)),)),
    ("UPDATE peta_laporan SET siswa_id = ?", (999999,)),
    ("UPDATE peta_laporan SET guru = 'guru-x'", ()),
    ("UPDATE peta_laporan SET dibuat = '2030-01-01 00:00:00'", ()),
    ("UPDATE peta_laporan SET id = id + 100", ()),
])
def test_isi_siswa_guru_dibuat_id_draf_tidak_pernah_berubah(kon, sql, args):
    anak = _draf(kon)
    sebelum = _baris(kon, anak)
    _tolak_sql(kon, sql, args)
    assert _baris(kon, anak) == sebelum


def test_catatan_draf_boleh_berubah_lewat_sql_dan_kolom_lain_tetap(kon):
    anak = _draf(kon)
    sebelum = _baris(kon, anak)
    kon.execute("UPDATE peta_laporan SET catatan = 'baru' WHERE siswa_id = ?", (anak,))
    sesudah = _baris(kon, anak)
    assert sesudah[3] == "baru" and sesudah[:3] + sesudah[4:] == sebelum[:3] + sebelum[4:]


@pytest.mark.parametrize("catatan", ["", " ", "\n", "\t \r\n ", " \n\n "])
def test_trigger_terbit_tanpa_catatan_ditolak_walau_lewat_sql(kon, catatan):
    anak = _draf(kon)
    kon.execute("UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ?", (catatan, anak))
    sebelum = _baris(kon, anak)
    _tolak_sql(kon, "UPDATE peta_laporan SET diterbitkan = '2026-11-24 16:00:00', "
                    "diterbitkan_oleh = 'guru-x' WHERE siswa_id = ?", (anak,))
    assert _baris(kon, anak) == sebelum


def test_trigger_terbit_dengan_catatan_isi_lolos(kon):
    anak = _draf(kon)
    kon.execute("UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ?", (CATATAN, anak))
    kon.execute("UPDATE peta_laporan SET diterbitkan = '2026-11-24 16:00:00', diterbitkan_oleh = 'guru-x' "
                "WHERE siswa_id = ?", (anak,))
    assert _baris(kon, anak)[6] == "2026-11-24 16:00:00"


def test_baris_baru_tidak_boleh_langsung_terbit(kon):
    anak = _anak(kon)
    _tolak_sql(kon, "INSERT INTO peta_laporan (siswa_id, isi, catatan, guru, dibuat, diterbitkan, diterbitkan_oleh) "
                    "VALUES (?, ?, ?, 'g', 'w', '2026-11-24 16:00:00', 'g')", (anak, json.dumps(_isi()), CATATAN))


def test_unique_satu_laporan_per_anak_walau_lewat_sql(kon):
    anak = _draf(kon)
    _tolak_sql(kon, "INSERT INTO peta_laporan (siswa_id, isi, guru, dibuat) VALUES (?, ?, 'g', 'w')",
               (anak, json.dumps(_isi())))


def test_check_panjang_catatan_isi_dan_guru(kon):
    anak = _anak(kon)
    kolom = "INSERT INTO peta_laporan (siswa_id, isi, catatan, guru, dibuat) VALUES (?, ?, ?, ?, 'w')"
    _tolak_sql(kon, kolom, (anak, json.dumps(_isi()), "c" * 2001, "g"))
    _tolak_sql(kon, kolom, (anak, "x" * 8001, "", "g"))
    _tolak_sql(kon, kolom, (anak, json.dumps(_isi()), "", ""))
    _tolak_sql(kon, kolom, (anak, json.dumps(_isi()), "", "g" * 65))


def test_check_kolom_terbit_terisi_bersama(kon):
    anak = _draf(kon)
    kon.execute("UPDATE peta_laporan SET catatan = ? WHERE siswa_id = ?", (CATATAN, anak))
    _tolak_sql(kon, "UPDATE peta_laporan SET diterbitkan = '2026-11-24 16:00:00' WHERE siswa_id = ?", (anak,))
    _tolak_sql(kon, "UPDATE peta_laporan SET diterbitkan_oleh = 'g' WHERE siswa_id = ?", (anak,))


def test_siswa_wajib_ada(kon):
    _tolak_sql(kon, "INSERT INTO peta_laporan (siswa_id, isi, guru, dibuat) VALUES (999999, ?, 'g', 'w')",
               (json.dumps(_isi()),))


# --- skema idempoten dan penghapusan anak ----------------------------------------------------

def test_siapkan_berulang_idempoten_dan_laporan_utuh(tmp_path):
    jalur = tmp_path / "ulang.db"
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        anak = _terbit(k)
    database.siapkan(jalur)
    database.siapkan(jalur)
    with database.buka(jalur) as k:
        assert store.ambil(k, anak)["diterbitkan"] is not None
        nama = {r[0] for r in k.execute("SELECT name FROM sqlite_master WHERE tbl_name = 'peta_laporan'")}
    assert {"peta_laporan_insert_draf", "peta_laporan_terbit_tetap", "peta_laporan_isi_tetap",
            "peta_laporan_terbit_butuh_catatan"} <= nama


def test_tidak_ada_trigger_delete_yang_memblokir(kon):
    jenis = [r[0] for r in kon.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                                       "AND tbl_name = 'peta_laporan'")]
    assert jenis and not any("BEFORE DELETE" in s.upper() or "AFTER DELETE" in s.upper() for s in jenis)


@pytest.mark.parametrize("terbit", [False, True])
def test_hapus_siswa_menghapus_laporan_draf_dan_terbit(kon, terbit):
    anak = _terbit(kon) if terbit else _draf(kon)
    lain = _draf(kon, _anak(kon, "Anak Lain"))
    kon.execute("DELETE FROM siswa WHERE id = ?", (anak,))
    assert store.ambil(kon, anak) is None
    assert kon.execute("SELECT COUNT(*) FROM peta_laporan WHERE siswa_id = ?", (anak,)).fetchone()[0] == 0
    assert store.ambil(kon, lain) is not None
    assert kon.execute("PRAGMA foreign_key_check").fetchone() is None

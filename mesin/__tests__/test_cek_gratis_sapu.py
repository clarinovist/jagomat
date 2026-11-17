"""Sapuan retensi cek gratis (funnel Fase 2a): guard, kedaluwarsa, yatim, kedap sesi lain.

Semua data sintetis di basis sementara. Waktu disuntik; tidak ada jam nyata.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis  # noqa: E402
import cek_gratis_sapu  # noqa: E402
import database  # noqa: E402
import kontak_akun  # noqa: E402
from cek_gratis_kit import (  # noqa: E402
    ID_A, ID_B, ID_C, SEKARANG, hitung, jawab, mulai_cek, tambah_anak, tandai_selesai,
)

HIDUP = frozenset({ID_A, ID_B, ID_C})
DUA_BELAS_HARI = "2026-11-06 09:00:00"  # selesai 12 hari sebelum SEKARANG
TIGA_PULUH_SATU_HARI = "2026-10-17 09:00:00"
DUA_PULUH_SEMBILAN_HARI = "2026-10-20 09:00:00"
KEADAAN_NOL = {"bahan_dihapus": 0, "belum_selesai": 0, "tak_terhitung": 0, "yatim": 0, "terlindungi": 0}


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "sapu.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _selesai(kon, id_akun, pemilik, selesai_sesi, nama=None, benar=9):
    """Cek yang selesai pada `selesai_sesi` dan sudah dinilai (`benar`/15 benar)."""
    anak = tambah_anak(kon, nama or "Anak " + id_akun[-4:], pemilik, 4)
    sesi_id = mulai_cek(kon, id_akun, anak, pemilik)
    jawab(kon, sesi_id, semua_benar=benar)
    tandai_selesai(kon, sesi_id, selesai_sesi)
    assert cek_gratis.selesaikan_jika_siap(kon, id_akun, SEKARANG) is True
    return anak, sesi_id


def _belum_selesai(kon, id_akun, pemilik, dibuat):
    anak = tambah_anak(kon, "Anak " + id_akun[-4:], pemilik, 4)
    sesi_id = mulai_cek(kon, id_akun, anak, pemilik)
    kon.execute("UPDATE cek_gratis SET dibuat = ?, setuju_pada = ? WHERE siswa_id = ?", (dibuat, dibuat, anak))
    return anak, sesi_id


def _sapu(kon, sekarang=SEKARANG, hidup=HIDUP):
    return cek_gratis_sapu.sapu_cek_gratis(kon, sekarang, hidup)


def _bahan(kon, sesi_id):
    return tuple(
        kon.execute(sql, (sesi_id,)).fetchone()[0] for sql in (
            "SELECT COUNT(*) FROM sesi WHERE id = ?",
            "SELECT COUNT(*) FROM sesi_soal WHERE sesi_id = ?",
            "SELECT COUNT(*) FROM jawaban WHERE sesi_soal_id IN (SELECT id FROM sesi_soal WHERE sesi_id = ?)",
            "SELECT COUNT(*) FROM diagnosis WHERE jawaban_id IN (SELECT j.id FROM jawaban j "
            "JOIN sesi_soal ss ON ss.id = j.sesi_soal_id WHERE ss.sesi_id = ?)",
        ))


def _baris_cek(kon):
    return [tuple(r) for r in kon.execute("SELECT * FROM cek_gratis ORDER BY id")]


# --- guard daftar akun ------------------------------------------------------

@pytest.mark.parametrize("hidup", [set(), frozenset(), None, [ID_A], (ID_A,), {"x"}, {ID_A, "akun_zz"},
                                   {ID_A: 1}, "akun"])
def test_daftar_akun_kosong_atau_tidak_sah_ditolak_tanpa_menghapus(kon, hidup):
    _, sesi_id = _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI)
    _belum_selesai(kon, ID_B, "guru-b", "2026-11-01T00:00:00")
    awal = _baris_cek(kon)

    with pytest.raises(ValueError):
        _sapu(kon, hidup=hidup)

    assert _baris_cek(kon) == awal
    assert _bahan(kon, sesi_id)[0] == 1


def test_sapuan_menolak_koneksi_tanpa_foreign_key_aktif(tmp_path):
    jalur = tmp_path / "tanpa-fk.db"
    database.siapkan(jalur)
    kon = sqlite3.connect(str(jalur))
    kon.row_factory = sqlite3.Row
    try:
        with pytest.raises(ValueError, match="foreign key"):
            cek_gratis_sapu.sapu_cek_gratis(kon, SEKARANG, HIDUP)
    finally:
        kon.close()


@pytest.mark.parametrize("sekarang", [None, "bukan waktu", 5])
def test_sapuan_menolak_waktu_tidak_sah(kon, sekarang):
    with pytest.raises(ValueError):
        _sapu(kon, sekarang=sekarang)


# --- bahan selesai > 30 hari ------------------------------------------------

def test_selesai_lebih_30_hari_menghapus_bahan_tetapi_turunan_tetap(kon):
    anak, sesi_id = _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI)
    turunan = tuple(kon.execute("SELECT skor, kategori, ringkasan, selesai_pada FROM cek_gratis").fetchone())
    assert _bahan(kon, sesi_id) == (1, 15, 15, 15)

    hasil = _sapu(kon)

    assert hasil == {**KEADAAN_NOL, "bahan_dihapus": 1}
    assert _bahan(kon, sesi_id) == (0, 0, 0, 0)
    baris = kon.execute("SELECT * FROM cek_gratis").fetchone()
    assert (baris["skor"], baris["kategori"], baris["ringkasan"], baris["selesai_pada"]) == turunan
    assert baris["sesi_id"] is None and baris["bahan_dihapus_pada"] == SEKARANG
    assert baris["siswa_id"] == anak and baris["id_akun"] == ID_A
    hasil_baca = cek_gratis.baca_hasil(kon, ID_A)
    assert (hasil_baca["status"], hasil_baca["skor"]) == ("selesai", 60)


def test_selesai_30_hari_tepat_dan_kurang_belum_dihapus(kon):
    _, sesi_tepat = _selesai(kon, ID_A, "guru-a", "2026-10-19 10:00:00")
    _, sesi_baru = _selesai(kon, ID_B, "guru-b", DUA_PULUH_SEMBILAN_HARI)

    hasil = _sapu(kon)

    assert hasil == KEADAAN_NOL
    assert _bahan(kon, sesi_tepat)[0] == _bahan(kon, sesi_baru)[0] == 1


def test_sapuan_kedua_kali_tidak_mengubah_apa_pun(kon):
    _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI)
    _sapu(kon)
    awal = _baris_cek(kon)

    assert _sapu(kon) == KEADAAN_NOL
    assert _baris_cek(kon) == awal


# --- belum selesai > 7 hari -------------------------------------------------

def test_belum_selesai_lebih_7_hari_menghapus_sesi_dan_baris(kon):
    anak, sesi_id = _belum_selesai(kon, ID_A, "guru-a", "2026-11-10T09:00:00")

    hasil = _sapu(kon)

    assert hasil == {**KEADAAN_NOL, "belum_selesai": 1}
    assert hitung(kon, "cek_gratis") == 0
    assert _bahan(kon, sesi_id) == (0, 0, 0, 0)
    assert kon.execute("SELECT COUNT(*) FROM siswa WHERE id = ?", (anak,)).fetchone()[0] == 1


def test_belum_selesai_7_hari_tepat_dan_kurang_dibiarkan(kon):
    _, sesi_tepat = _belum_selesai(kon, ID_A, "guru-a", "2026-11-11T10:00:00")
    _, sesi_baru = _belum_selesai(kon, ID_B, "guru-b", "2026-11-14T10:00:00")

    assert _sapu(kon) == KEADAAN_NOL

    assert hitung(kon, "cek_gratis") == 2
    assert _bahan(kon, sesi_tepat)[0] == _bahan(kon, sesi_baru)[0] == 1


def test_anak_sudah_selesai_tetapi_skor_belum_dihitung_tidak_dianggap_belum_selesai(kon):
    anak = tambah_anak(kon, "Anak Selesai", "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)
    tandai_selesai(kon, sesi_id, DUA_BELAS_HARI)
    kon.execute("UPDATE cek_gratis SET dibuat = '2026-11-01T00:00:00'")

    assert _sapu(kon) == KEADAAN_NOL

    assert hitung(kon, "cek_gratis") == 1 and _bahan(kon, sesi_id)[0] == 1
    assert cek_gratis.selesaikan_jika_siap(kon, ID_A, SEKARANG) is True


def test_selesai_tak_pernah_dinilai_lebih_30_hari_dihapus_tanpa_membaca_jawaban(kon):
    anak = tambah_anak(kon, "Anak Lupa", "guru-a", 4)
    sesi_id = mulai_cek(kon, ID_A, anak, "guru-a")
    jawab(kon, sesi_id, semua_benar=15)
    tandai_selesai(kon, sesi_id, TIGA_PULUH_SATU_HARI)

    hasil = _sapu(kon)

    assert hasil == {**KEADAAN_NOL, "tak_terhitung": 1}
    assert hitung(kon, "cek_gratis") == 0 and _bahan(kon, sesi_id)[0] == 0


def test_sesi_cek_dibatalkan_dihitung_belum_selesai(kon):
    _, sesi_id = _belum_selesai(kon, ID_A, "guru-a", "2026-11-01T00:00:00")
    tandai_selesai(kon, sesi_id, DUA_BELAS_HARI)
    kon.execute("UPDATE sesi SET dibatalkan = '2026-11-06 10:00:00' WHERE id = ?", (sesi_id,))

    assert _sapu(kon) == {**KEADAAN_NOL, "belum_selesai": 1}


def test_cek_tanpa_sesi_dan_tanpa_skor_lebih_7_hari_dihapus(kon):
    _, sesi_id = _belum_selesai(kon, ID_A, "guru-a", "2026-11-01T00:00:00")
    kon.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))  # guru menghapus sesinya sendiri

    assert _sapu(kon) == {**KEADAAN_NOL, "belum_selesai": 1}
    assert hitung(kon, "cek_gratis") == 0


# --- yatim ------------------------------------------------------------------

def test_cek_akun_tidak_hidup_dihapus_beserta_sesinya_milik_akun_hidup_utuh(kon):
    _, sesi_yatim = _selesai(kon, ID_A, "guru-a", DUA_BELAS_HARI)
    _, sesi_hidup = _selesai(kon, ID_B, "guru-b", DUA_BELAS_HARI)

    hasil = _sapu(kon, hidup=frozenset({ID_B}))

    assert hasil == {**KEADAAN_NOL, "yatim": 1}
    assert [r[0] for r in kon.execute("SELECT id_akun FROM cek_gratis")] == [ID_B]
    assert _bahan(kon, sesi_yatim) == (0, 0, 0, 0)
    assert _bahan(kon, sesi_hidup)[0] == 1


def test_cek_yatim_yang_juga_kedaluwarsa_dihitung_yatim_dan_turunan_ikut_hilang(kon):
    _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI)

    assert _sapu(kon, hidup=frozenset({ID_B})) == {**KEADAAN_NOL, "yatim": 1}
    assert hitung(kon, "cek_gratis") == 0


def test_cek_yang_anaknya_tidak_ada_dihapus_walau_fk_tidak_menolong(kon):
    anak, _ = _selesai(kon, ID_A, "guru-a", DUA_BELAS_HARI)
    _selesai(kon, ID_B, "guru-b", DUA_BELAS_HARI)
    # Simulasi basis tanpa cascade: anak dicabut lewat koneksi lain tanpa FK.
    kon.commit()
    lain = sqlite3.connect(str(kon.execute("PRAGMA database_list").fetchone()[2]))
    lain.execute("DELETE FROM siswa WHERE id = ?", (anak,))
    lain.commit()
    lain.close()
    assert hitung(kon, "cek_gratis") == 2

    assert _sapu(kon)["yatim"] == 1
    assert [r[0] for r in kon.execute("SELECT id_akun FROM cek_gratis")] == [ID_B]


# --- hanya cek yang disentuh ------------------------------------------------

def test_sapuan_tidak_menyentuh_sesi_biasa_siswa_dan_kontak(kon):
    anak_a, _ = _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI)
    anak_b = tambah_anak(kon, "Anak Biasa", "guru-b", 4)
    biasa_a = database.buat_sesi(kon, anak_a, 31, jumlah_soal=2)
    biasa_b = database.buat_sesi(kon, anak_b, 32, jumlah_soal=2)
    for sesi_id in (biasa_a, biasa_b):
        for b in database.isi_sesi(kon, sesi_id):
            database.simpan_jawaban(kon, b["sesi_soal_id"], jawaban=b["kunci"], cara="cara sintetis")
        kon.execute("UPDATE sesi SET selesai = ? WHERE id = ?", (TIGA_PULUH_SATU_HARI, sesi_id))
    kontak_akun.simpan(kon, ID_A, "6281234567890", "2026-11-16T08:00:00")
    sebelum = {"siswa": hitung(kon, "siswa"), "kontak": hitung(kon, "kontak_akun"),
               "biasa": (_bahan(kon, biasa_a), _bahan(kon, biasa_b))}

    hasil = _sapu(kon, hidup=frozenset({ID_A, ID_B}))

    assert hasil["bahan_dihapus"] == 1
    assert {"siswa": hitung(kon, "siswa"), "kontak": hitung(kon, "kontak_akun"),
            "biasa": (_bahan(kon, biasa_a), _bahan(kon, biasa_b))} == sebelum
    assert sebelum["biasa"][0][2] == 2  # jawaban sesi biasa masih ada


def test_hasil_hanya_agregat_jumlah(kon):
    _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI, nama="Nama Rahasia")

    hasil = _sapu(kon)

    assert set(hasil) == set(KEADAAN_NOL) and all(type(v) is int for v in hasil.values())
    assert "Nama Rahasia" not in repr(hasil) and ID_A not in repr(hasil)


# --- bukti belajar & atomik -------------------------------------------------

def test_sesi_cek_yang_dikonfirmasi_guru_tidak_dihapus_dan_tidak_menggagalkan_sapuan(kon):
    _, sesi_bukti = _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI, benar=15)
    _, sesi_biasa = _selesai(kon, ID_B, "guru-b", TIGA_PULUH_SATU_HARI)
    # Pengesahan guru (bukti belajar) ditulis langsung: jalur PG penuh butuh arsip pilihan.
    kon.execute("INSERT INTO konfirmasi_hasil(sesi_id, nomor_urut, guru, fingerprint) VALUES (?, 1, 'guru-a', ?)",
                (sesi_bukti, "f" * 64))
    baris_bukti = [tuple(r) for r in kon.execute("SELECT * FROM cek_gratis WHERE id_akun = ?", (ID_A,))]

    hasil = _sapu(kon)

    assert hasil == {**KEADAAN_NOL, "bahan_dihapus": 1, "terlindungi": 1}
    assert _bahan(kon, sesi_bukti)[0] == 1 and _bahan(kon, sesi_biasa)[0] == 0
    assert [tuple(r) for r in kon.execute("SELECT * FROM cek_gratis WHERE id_akun = ?", (ID_A,))] == baris_bukti
    assert hitung(kon, "konfirmasi_hasil") == 1


def test_gagal_di_tengah_membatalkan_seluruh_sapuan(kon, monkeypatch):
    _selesai(kon, ID_A, "guru-a", DUA_BELAS_HARI)
    _belum_selesai(kon, ID_C, "guru-c", "2026-11-01T00:00:00")
    awal = (_baris_cek(kon), hitung(kon, "sesi"))

    def gagal(*args, **kwargs):
        raise RuntimeError("putus di tengah")

    monkeypatch.setattr(cek_gratis_sapu, "_hapus_bahan", gagal)

    with pytest.raises(RuntimeError):
        _sapu(kon, hidup=frozenset({ID_C}))  # yatim (ID_A) dihapus dulu, lalu gagal

    assert (_baris_cek(kon), hitung(kon, "sesi")) == awal


def test_sapuan_tidak_membaca_isi_jawaban_atau_kunci(kon):
    _selesai(kon, ID_A, "guru-a", TIGA_PULUH_SATU_HARI)
    _belum_selesai(kon, ID_B, "guru-b", "2026-11-01T00:00:00")
    dibaca = []

    def penjaga(aksi, tabel, kolom, _db, _pemicu):
        if aksi == sqlite3.SQLITE_READ and (
                (tabel == "jawaban" and kolom in {"jawaban", "cara", "restatement"})
                or (tabel == "soal" and kolom in {"kunci", "parameter"})
                or (tabel == "diagnosis" and kolom != "jawaban_id")):  # jawaban_id dibaca cascade
            dibaca.append((tabel, kolom))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    kon.set_authorizer(penjaga)
    try:
        hasil = _sapu(kon)
    finally:
        kon.set_authorizer(lambda *args: sqlite3.SQLITE_OK)

    assert dibaca == []
    assert hasil["bahan_dihapus"] == 1 and hasil["belum_selesai"] == 1

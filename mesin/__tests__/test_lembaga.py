"""Lembaga les (pemilik les): skema, store, aturan pindah anak, hapus keluarga.

Semua data sintetis. Setiap penolakan pindah dibuktikan tanpa tulis apa pun
lewat `total_changes` dan hitungan baris, bukan hanya status kembalian.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import family_deletion as hapus  # noqa: E402
import lembaga_store as L  # noqa: E402
from schema import SKEMA  # noqa: E402
from test_family_deletion import (  # noqa: E402,F401
    TARGET, _jalankan, _perintah, penyimpanan,
)

PEMILIK = "pemilik-les"
GURU_A = "guru-a"
GURU_B = "guru-b"
LUAR = "guru-luar"
ADMIN = "admin-sintetis"


@pytest.fixture()
def basis(tmp_path):
    jalur = tmp_path / "lembaga.db"
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        lembaga_id = L.buat_lembaga(kon, nama="Les Sintetis", pemilik=PEMILIK)
        L.tambah_anggota(kon, lembaga_id=lembaga_id, guru=GURU_A)
        L.tambah_anggota(kon, lembaga_id=lembaga_id, guru=GURU_B)
        anak = {
            "a": database.tambah_siswa(kon, "Anak A", "P3", pemilik=GURU_A),
            "b": database.tambah_siswa(kon, "Anak B", "P3", pemilik=GURU_B),
            "o": database.tambah_siswa(kon, "Anak O", "P3", pemilik=PEMILIK),
            "luar": database.tambah_siswa(kon, "Anak Luar", "P3", pemilik=LUAR),
        }
    return jalur, lembaga_id, anak


def _pindah(jalur, **kwargs):
    """Satu transaksi seperti handler; mengembalikan (hasil, perubahan_total)."""
    with database.buka(jalur) as kon:
        kon.execute("BEGIN IMMEDIATE")
        sebelum = kon.total_changes
        hasil = L.pindahkan(kon, **kwargs)
        return hasil, kon.total_changes - sebelum


def _pemilik(jalur, siswa_id):
    with database.buka(jalur) as kon:
        return kon.execute("SELECT pemilik FROM siswa WHERE id=?", (siswa_id,)).fetchone()[0]


def _jumlah_jejak(jalur):
    with database.buka(jalur) as kon:
        return kon.execute("SELECT COUNT(*) FROM pindah_siswa").fetchone()[0]


# --- skema ------------------------------------------------------------------

def test_skema_idempoten_dan_foreign_key_bersih(tmp_path):
    jalur = tmp_path / "s.db"
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        pertama = [tuple(r) for r in kon.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY type,name")]
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        kedua = [tuple(r) for r in kon.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY type,name")]
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 0
    assert pertama == kedua
    nama = {baris[1] for baris in pertama}
    assert {"lembaga", "anggota_lembaga", "pindah_siswa"} <= nama
    assert SKEMA.count("CREATE TABLE IF NOT EXISTS lembaga ") == 1


def test_jejak_pindah_tidak_bisa_dihapus_atau_diubah_intinya(basis):
    jalur, _lid, anak = basis
    hasil, _ = _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    assert hasil.status == "ok"
    with database.buka(jalur) as kon:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            kon.execute("DELETE FROM pindah_siswa")
        for kolom in ("siswa_id", "lembaga_id", "dibuat"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                kon.execute("UPDATE pindah_siswa SET %s=%s" % (kolom, kolom))
        # Nama guru boleh dipseudonimkan oleh penghapusan keluarga.
        kon.execute("UPDATE pindah_siswa SET dari='x', ke='y', oleh='z'")


def test_jejak_ikut_hilang_hanya_bila_anaknya_dihapus(basis):
    jalur, _lid, anak = basis
    _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    with database.buka(jalur) as kon:
        kon.execute("DELETE FROM siswa WHERE id=?", (anak["a"],))
        assert kon.execute("SELECT COUNT(*) FROM pindah_siswa").fetchone()[0] == 0
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


# --- store: keanggotaan ---------------------------------------------------------

def test_pemilik_tidak_boleh_jadi_anggota_dan_sebaliknya(basis):
    jalur, lid, _anak = basis
    with database.buka(jalur) as kon:
        with pytest.raises(L.PenolakanLembaga):
            L.tambah_anggota(kon, lembaga_id=lid, guru=PEMILIK)
        with pytest.raises(L.PenolakanLembaga):
            L.buat_lembaga(kon, nama="Dua", pemilik=GURU_A)  # sudah anggota
        with pytest.raises(L.PenolakanLembaga):
            L.buat_lembaga(kon, nama="Dua", pemilik=PEMILIK)  # sudah pemilik
        lain = L.buat_lembaga(kon, nama="Les Lain", pemilik="pemilik-dua")
        with pytest.raises(L.PenolakanLembaga):
            L.tambah_anggota(kon, lembaga_id=lain, guru=GURU_A)  # satu lembaga saja
        with pytest.raises(L.PenolakanLembaga):
            L.tambah_anggota(kon, lembaga_id=lain, guru=PEMILIK)
        with pytest.raises(L.PenolakanLembaga):
            L.buat_lembaga(kon, nama="  ", pemilik="pemilik-tiga")
        with pytest.raises(L.PenolakanLembaga):
            L.buat_lembaga(kon, nama="x" * 81, pemilik="pemilik-tiga")


def test_lembaga_milik_dan_anggota_terurut(basis):
    jalur, lid, _anak = basis
    with database.buka(jalur) as kon:
        assert L.lembaga_milik(kon, PEMILIK)["id"] == lid
        assert L.lembaga_milik(kon, GURU_A) is None
        assert L.lembaga_milik(kon, LUAR) is None
        assert L.anggota(kon, lid) == (GURU_A, GURU_B)
        assert L.lepas_anggota(kon, lembaga_id=lid, guru=GURU_A, oleh=ADMIN) == 1
        assert L.anggota(kon, lid) == (GURU_B,)
        with pytest.raises(L.PenolakanLembaga):
            L.lepas_anggota(kon, lembaga_id=lid, guru=GURU_A, oleh=ADMIN)


# --- store: ringkasan -------------------------------------------------------------

def test_ringkasan_hanya_agregat_pemilik_dulu_anggota_terurut(basis):
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        s1 = database.buat_sesi(kon, anak["b"], seed=1, jumlah_soal=1)
        s2 = database.buat_sesi(kon, anak["b"], seed=2, jumlah_soal=1)
        s3 = database.buat_sesi(kon, anak["b"], seed=3, jumlah_soal=1)
        kon.execute("UPDATE sesi SET dibatalkan='2026-01-01' WHERE id=?", (s3,))
        kon.execute("UPDATE sesi SET selesai='2026-11-01 08:00:00' WHERE id=?", (s1,))
        kon.execute("UPDATE sesi SET selesai='2026-11-02 08:00:00',"
                    "dikonfirmasi_guru=? WHERE id=?", (GURU_B, s2))
        database.buat_sesi(kon, anak["luar"], seed=4, jumlah_soal=1)
        ringkas = L.ringkasan(kon, L.lembaga_milik(kon, PEMILIK))
    assert [g.guru for g in ringkas] == [PEMILIK, GURU_A, GURU_B]
    assert [len(g.anak) for g in ringkas] == [1, 1, 1]
    b = ringkas[2].anak[0]
    assert (b.nama, b.jumlah_sesi, b.menunggu_konfirmasi) == ("Anak B", 2, 1)
    assert b.sesi_terakhir
    assert "Anak Luar" not in repr(ringkas)


# --- store: pindahkan -------------------------------------------------------------

def test_pindah_sukses_menulis_satu_ubahan_dan_satu_jejak(basis):
    jalur, lid, anak = basis
    hasil, perubahan = _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    assert hasil.status == "ok"
    assert perubahan == 2
    assert _pemilik(jalur, anak["a"]) == GURU_B
    with database.buka(jalur) as kon:
        jejak = kon.execute("SELECT * FROM pindah_siswa").fetchall()
    assert len(jejak) == 1
    assert (jejak[0]["siswa_id"], jejak[0]["lembaga_id"], jejak[0]["dari"],
            jejak[0]["ke"], jejak[0]["oleh"]) == (anak["a"], lid, GURU_A, GURU_B, PEMILIK)


def test_pindah_boleh_ke_dan_dari_pemilik(basis):
    jalur, _lid, anak = basis
    assert _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=PEMILIK)[0].status == "ok"
    assert _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)[0].status == "ok"
    assert _pemilik(jalur, anak["a"]) == GURU_B


def _tanpa_tulis(jalur, anak, status, **kwargs):
    jejak = _jumlah_jejak(jalur)
    pemilik = _pemilik(jalur, anak)
    hasil, perubahan = _pindah(jalur, **kwargs)
    assert hasil.status == status
    assert perubahan == 0
    assert _jumlah_jejak(jalur) == jejak
    assert _pemilik(jalur, anak) == pemilik


@pytest.mark.parametrize("aktor", [GURU_A, LUAR, "admin", ""])
def test_pindah_ditolak_bila_aktor_bukan_pemilik_lembaga(basis, aktor):
    jalur, _lid, anak = basis
    _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                 oleh=aktor, siswa_id=anak["a"], ke=GURU_B)


def test_pindah_ditolak_bila_anak_di_luar_lembaga_atau_tak_ada(basis):
    jalur, _lid, anak = basis
    _tanpa_tulis(jalur, anak["luar"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=anak["luar"], ke=GURU_B)
    _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=99999, ke=GURU_B)


def test_pindah_ditolak_bila_tujuan_di_luar_lembaga(basis):
    jalur, _lid, anak = basis
    for tujuan in (LUAR, "", "admin", "pemilik-dua"):
        _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                     oleh=PEMILIK, siswa_id=anak["a"], ke=tujuan)


def test_pindah_ke_guru_lembaga_lain_ditolak(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        lain = L.buat_lembaga(kon, nama="Les Lain", pemilik="pemilik-dua")
        L.tambah_anggota(kon, lembaga_id=lain, guru="anggota-dua")
    _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=anak["a"], ke="anggota-dua")
    _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                 oleh="pemilik-dua", siswa_id=anak["a"], ke="anggota-dua")


def test_pindah_ke_guru_yang_sama_ditolak_tanpa_tulis(basis):
    jalur, _lid, anak = basis
    _tanpa_tulis(jalur, anak["a"], "sama",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_A)


def _habiskan_pembeda(jalur, nama, pemilik):
    """Isi `nama`, `nama (2)` ... `nama (99)` milik `pemilik` (pembeda habis)."""
    with database.buka(jalur) as kon:
        database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)
        for urut in range(2, L.BATAS_PEMBEDA + 1):
            database.tambah_siswa(kon, "%s (%d)" % (nama, urut), "P3", pemilik=pemilik)


def test_pindah_ditolak_bila_pembeda_nama_habis_di_tujuan(basis):
    jalur, _lid, anak = basis
    _habiskan_pembeda(jalur, "Anak A", GURU_B)
    _tanpa_tulis(jalur, anak["a"], "bentrok_nama",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)


def test_pindah_dengan_nama_bentrok_berhasil_dan_nama_diberi_pembeda(basis):
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        database.tambah_siswa(kon, "Anak A", "P3", pemilik=GURU_B)
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
    hasil, perubahan = _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    assert hasil.status == "ok" and hasil.nama_baru == "Anak A (2)"
    assert perubahan == 2
    with database.buka(jalur) as kon:
        baris = kon.execute("SELECT id, nama, pemilik FROM siswa WHERE id=?", (anak["a"],)).fetchone()
        assert (baris["nama"], baris["pemilik"]) == ("Anak A (2)", GURU_B)
        # Anak lama milik tujuan tidak tersentuh dan tidak digabung.
        lama = kon.execute(
            "SELECT id FROM siswa WHERE nama='Anak A' AND pemilik=?", (GURU_B,)).fetchone()
        assert lama is not None and lama["id"] != anak["a"]
        assert kon.execute("SELECT siswa_id FROM sesi WHERE id=?", (sesi,)).fetchone()[0] == anak["a"]
        jejak = kon.execute("SELECT * FROM pindah_siswa").fetchall()
    assert [(j["siswa_id"], j["lembaga_id"], j["dari"], j["ke"], j["oleh"]) for j in jejak] == [
        (anak["a"], lid, GURU_A, GURU_B, PEMILIK)]


def test_pindah_nama_kembar_ketiga_mendapat_nomor_terkecil_yang_bebas(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        database.tambah_siswa(kon, "Anak A", "P3", pemilik=GURU_B)
        database.tambah_siswa(kon, "Anak A (2)", "P3", pemilik=GURU_B)
    hasil, _ = _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    assert hasil.nama_baru == "Anak A (3)"


def test_pindah_tanpa_bentrok_mempertahankan_nama(basis):
    jalur, _lid, anak = basis
    hasil, _ = _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    assert hasil.nama_baru == "Anak A"
    with database.buka(jalur) as kon:
        assert kon.execute("SELECT nama FROM siswa WHERE id=?", (anak["a"],)).fetchone()[0] == "Anak A"


# --- store: nama_bebas -------------------------------------------------------------

def test_nama_bebas_mengembalikan_nama_apa_adanya_bila_belum_dipakai(basis):
    jalur, _lid, _anak = basis
    with database.buka(jalur) as kon:
        sebelum = kon.total_changes
        assert L.nama_bebas(kon, "Anak Baru", GURU_A) == "Anak Baru"
        assert L.nama_bebas(kon, "Anak B", GURU_A) == "Anak B"  # dipakai pemilik lain, bukan GURU_A
        assert kon.total_changes == sebelum


def test_nama_bebas_bentrok_diberi_nomor_terkecil_yang_bebas(basis):
    jalur, _lid, _anak = basis
    with database.buka(jalur) as kon:
        assert L.nama_bebas(kon, "Anak A", GURU_A) == "Anak A (2)"
        database.tambah_siswa(kon, "Anak A (2)", "P3", pemilik=GURU_A)
        assert L.nama_bebas(kon, "Anak A", GURU_A) == "Anak A (3)"
        database.tambah_siswa(kon, "Anak A (4)", "P3", pemilik=GURU_A)
        assert L.nama_bebas(kon, "Anak A", GURU_A) == "Anak A (3)"
        database.tambah_siswa(kon, "Anak A (3)", "P3", pemilik=GURU_A)
        assert L.nama_bebas(kon, "Anak A", GURU_A) == "Anak A (5)"


def test_nama_bebas_tidak_peduli_huruf_besar_kecil(basis):
    jalur, _lid, _anak = basis
    with database.buka(jalur) as kon:
        assert L.nama_bebas(kon, "anak a", GURU_A) == "anak a (2)"
        assert L.nama_bebas(kon, "ANAK A", GURU_A) == "ANAK A (2)"
        database.tambah_siswa(kon, "ANAK A (2)", "P3", pemilik=GURU_A)
        assert L.nama_bebas(kon, "anak a", GURU_A) == "anak a (3)"


def test_nama_bebas_menghormati_nama_yang_dipesan_dalam_satu_operasi(basis):
    jalur, _lid, _anak = basis
    with database.buka(jalur) as kon:
        assert L.nama_bebas(kon, "Baru", GURU_A, ["BARU"]) == "Baru (2)"
        assert L.nama_bebas(kon, "Baru", GURU_A, ["Baru", "baru (2)"]) == "Baru (3)"


def test_nama_bebas_none_bila_sampai_batas_masih_bentrok(basis):
    jalur, _lid, _anak = basis
    _habiskan_pembeda(jalur, "Penuh", GURU_A)
    with database.buka(jalur) as kon:
        assert L.nama_bebas(kon, "Penuh", GURU_A) is None
        kon.execute("DELETE FROM siswa WHERE nama='Penuh (99)' AND pemilik=?", (GURU_A,))
        assert L.nama_bebas(kon, "Penuh", GURU_A) == "Penuh (99)"


# --- store: lepas_anggota -----------------------------------------------------------

def _lepas(jalur, lid, guru, oleh=ADMIN):
    """Satu transaksi seperti handler admin; mengembalikan (jumlah, perubahan_total)."""
    with database.buka(jalur) as kon:
        kon.execute("BEGIN IMMEDIATE")
        sebelum = kon.total_changes
        jumlah = L.lepas_anggota(kon, lembaga_id=lid, guru=guru, oleh=oleh)
        return jumlah, kon.total_changes - sebelum


def _keadaan_lembaga(jalur):
    with database.buka(jalur) as kon:
        return tuple(
            tuple(tuple(r) for r in kon.execute(sql))
            for sql in ("SELECT * FROM siswa ORDER BY id", "SELECT * FROM anggota_lembaga ORDER BY guru",
                        "SELECT * FROM pindah_siswa ORDER BY id", "SELECT * FROM lembaga ORDER BY id"))


def _tambah(jalur, nama, pemilik):
    with database.buka(jalur) as kon:
        return database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)


def test_jumlah_anak_guru_menghitung_anak_milik_guru_itu_saja(basis):
    jalur, _lid, _anak = basis
    _tambah(jalur, "Anak A2", GURU_A)
    with database.buka(jalur) as kon:
        assert L.jumlah_anak_guru(kon, GURU_A) == 2
        assert L.jumlah_anak_guru(kon, GURU_B) == 1
        assert L.jumlah_anak_guru(kon, "tidak-ada") == 0


def test_lepas_memindah_semua_anak_ke_pemilik_dengan_jejak_per_anak(basis):
    jalur, lid, anak = basis
    a2 = _tambah(jalur, "Anak O", GURU_A)      # bentrok dengan Anak O milik pemilik lembaga
    a3 = _tambah(jalur, "anak o", GURU_A)      # bentrok huruf kecil dan dengan kiriman sebelumnya
    sebelum_b = _pemilik(jalur, anak["b"])
    jumlah, _ = _lepas(jalur, lid, GURU_A)
    assert jumlah == 3
    with database.buka(jalur) as kon:
        assert L.anggota(kon, lid) == (GURU_B,)
        assert L.jumlah_anak_guru(kon, GURU_A) == 0
        nama = {r["id"]: (r["nama"], r["pemilik"]) for r in kon.execute("SELECT id,nama,pemilik FROM siswa")}
        jejak = [tuple(r) for r in kon.execute(
            "SELECT siswa_id,lembaga_id,dari,ke,oleh FROM pindah_siswa ORDER BY id")]
    assert nama[anak["a"]] == ("Anak A", PEMILIK)
    assert nama[a2] == ("Anak O (2)", PEMILIK)
    assert nama[a3] == ("anak o (3)", PEMILIK)
    assert nama[anak["o"]] == ("Anak O", PEMILIK)          # anak lama pemilik tidak tersentuh
    assert _pemilik(jalur, anak["b"]) == sebelum_b == GURU_B
    assert jejak == [(s, lid, GURU_A, PEMILIK, ADMIN) for s in (anak["a"], a2, a3)]


def test_lepas_tanpa_anak_hanya_menghapus_keanggotaan(basis):
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        kon.execute("UPDATE siswa SET pemilik=? WHERE id=?", (PEMILIK, anak["a"]))
    jumlah, perubahan = _lepas(jalur, lid, GURU_A)
    assert (jumlah, perubahan) == (0, 1)
    assert _jumlah_jejak(jalur) == 0


def test_lepas_mempertahankan_id_anak_dan_data_belajar(basis):
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        sebelum = tuple(kon.execute("SELECT * FROM sesi WHERE id=?", (sesi,)).fetchone())
    _lepas(jalur, lid, GURU_A)
    with database.buka(jalur) as kon:
        assert tuple(kon.execute("SELECT * FROM sesi WHERE id=?", (sesi,)).fetchone()) == sebelum
        assert kon.execute("SELECT pemilik FROM siswa WHERE id=?", (anak["a"],)).fetchone()[0] == PEMILIK


def _tanpa_efek_lepas(jalur, lid, guru, galat=L.PenolakanLembaga):
    sebelum = _keadaan_lembaga(jalur)
    with database.buka(jalur) as kon:
        kon.execute("BEGIN IMMEDIATE")
        awal = kon.total_changes
        with pytest.raises(galat):
            L.lepas_anggota(kon, lembaga_id=lid, guru=guru, oleh=ADMIN)
        assert kon.total_changes == awal
    assert _keadaan_lembaga(jalur) == sebelum


@pytest.mark.parametrize("kolom", ["mulai", "selesai"])
def test_lepas_ditolak_selagi_ada_anak_dengan_sesi_berjalan_tanpa_efek(basis, kolom):
    jalur, lid, anak = basis
    a2 = _tambah(jalur, "Anak A2", GURU_A)   # id lebih besar; anak pertama bersih, anak kedua berjalan
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, a2, seed=1, jumlah_soal=1)
        kon.execute("UPDATE sesi SET %s='2026-11-01 08:00:00' WHERE id=?" % kolom, (sesi,))
    _tanpa_efek_lepas(jalur, lid, GURU_A, L.PenolakanSesiBerjalan)
    # Setelah dikonfirmasi guru, lepas boleh.
    with database.buka(jalur) as kon:
        kon.execute("UPDATE sesi SET dikonfirmasi_guru=? WHERE id=?", (GURU_A, sesi))
    assert _lepas(jalur, lid, GURU_A)[0] == 2


def test_lepas_ditolak_selagi_operasi_foto_belum_selesai(basis):
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        _pasang_operasi_foto(kon, sesi, "reserved")
    _tanpa_efek_lepas(jalur, lid, GURU_A, L.PenolakanSesiBerjalan)


def test_sesi_berjalan_anak_guru_lain_tidak_menahan_lepas(basis):
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["b"], seed=1, jumlah_soal=1)
        kon.execute("UPDATE sesi SET mulai='2026-11-01 08:00:00' WHERE id=?", (sesi,))
    assert _lepas(jalur, lid, GURU_A)[0] == 1


@pytest.mark.parametrize("guru", [LUAR, PEMILIK, "admin", "", "tidak-ada"])
def test_lepas_non_anggota_ditolak_tanpa_efek(basis, guru):
    jalur, lid, _anak = basis
    _tanpa_efek_lepas(jalur, lid, guru)


def test_lepas_dari_lembaga_yang_salah_atau_tak_ada_ditolak_tanpa_efek(basis):
    jalur, lid, _anak = basis
    with database.buka(jalur) as kon:
        lain = L.buat_lembaga(kon, nama="Les Lain", pemilik="pemilik-dua")
    _tanpa_efek_lepas(jalur, lain, GURU_A)       # anggota lembaga lain
    _tanpa_efek_lepas(jalur, 99999, GURU_A)      # lembaga tak ada


def test_lepas_ditolak_tanpa_efek_bila_pembeda_nama_habis_di_pemilik(basis):
    jalur, lid, anak = basis
    _tambah(jalur, "Anak A2", GURU_A)            # anak bersih yang urut sesudahnya
    _habiskan_pembeda(jalur, "Anak A", PEMILIK)  # Anak A tidak bisa diberi nama bebas
    _tanpa_efek_lepas(jalur, lid, GURU_A, L.PenolakanNamaAnak)


@pytest.mark.parametrize("kolom", ["mulai", "selesai"])
def test_pindah_ditolak_selagi_sesi_berjalan(basis, kolom):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        kon.execute("UPDATE sesi SET %s='2026-11-01 08:00:00' WHERE id=?" % kolom, (sesi,))
    _tanpa_tulis(jalur, anak["a"], "sesi_berjalan",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    # Setelah dikonfirmasi guru, anak boleh pindah.
    with database.buka(jalur) as kon:
        kon.execute("UPDATE sesi SET dikonfirmasi_guru=? WHERE id=?", (GURU_A, sesi))
    assert _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)[0].status == "ok"


def test_sesi_dibatalkan_atau_belum_dimulai_tidak_menahan_pindah(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        s1 = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        s2 = database.buat_sesi(kon, anak["a"], seed=2, jumlah_soal=1)
        kon.execute("UPDATE sesi SET mulai='2026-11-01 08:00:00',"
                    "dibatalkan='2026-11-01 09:00:00' WHERE id=?", (s1,))
        del s2  # sesi baru dibuat belum dimulai
    assert _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)[0].status == "ok"


def _pasang_operasi_foto(kon, sesi_id, status):
    from schema import SKEMA_OPERASI_FOTO
    if not kon.execute("SELECT 1 FROM sqlite_master WHERE name='operasi_foto_baca'").fetchone():
        kon.executescript(SKEMA_OPERASI_FOTO)
    h = "a" * 64
    kon.execute(
        "INSERT INTO operasi_foto_baca(operasi_id,akun_id,actor_id,sesi_id,target_id,"
        "jenis,isi_sidik,konteks_sidik,permintaan_sidik,fence,status,dibuat,diperbarui)"
        " VALUES (?,?,?,?,0,'upload',?,?,?,?,?,1,1)",
        ("o" * 37, "akun", "akun", sesi_id, h, h, h, h, status),
    )


@pytest.mark.parametrize("status", ["reserved", "sent", "unknown"])
def test_pindah_ditolak_selagi_operasi_foto_belum_selesai(basis, status):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        _pasang_operasi_foto(kon, sesi, status)
    _tanpa_tulis(jalur, anak["a"], "sesi_berjalan",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)


def test_pindah_boleh_bila_operasi_foto_sudah_tuntas(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        _pasang_operasi_foto(kon, sesi, "no_output")
    assert _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)[0].status == "ok"


def test_pindah_memeriksa_ulang_dalam_transaksi_yang_sama(basis):
    """Anggota dilepas sebelum pindah: predikat dibaca ulang, bukan di-cache."""
    jalur, lid, anak = basis
    with database.buka(jalur) as kon:
        L.lepas_anggota(kon, lembaga_id=lid, guru=GURU_B, oleh=ADMIN)
    _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    # Anak guru yang dilepas kini milik pemilik lembaga; guru yang dilepas bukan tujuan sah lagi.
    assert _pemilik(jalur, anak["b"]) == PEMILIK
    _tanpa_tulis(jalur, anak["b"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=anak["b"], ke=GURU_B)


def test_pindah_hanya_mengubah_pemilik_bukan_data_belajar(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["a"], seed=1, jumlah_soal=1)
        sebelum = tuple(kon.execute("SELECT * FROM sesi WHERE id=?", (sesi,)).fetchone())
    _pindah(jalur, oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    with database.buka(jalur) as kon:
        assert tuple(kon.execute("SELECT * FROM sesi WHERE id=?", (sesi,)).fetchone()) == sebelum
        assert kon.execute("SELECT siswa_id FROM sesi WHERE id=?", (sesi,)).fetchone()[0] == anak["a"]


# --- hapus keluarga ---------------------------------------------------------------

def _siapkan_lembaga_di_live(paths, pemilik_lembaga, anggota_guru):
    with database.buka(paths["belajar"]) as kon:
        lid = L.buat_lembaga(kon, nama="Les Hapus", pemilik=pemilik_lembaga)
        for guru in anggota_guru:
            L.tambah_anggota(kon, lembaga_id=lid, guru=guru)
        return lid


def _preview(paths):
    return hapus.preview(paths["belajar"], paths["auth"], paths["admin"],
                         paths["ai"], paths["pendamping"], target_id=TARGET)


def test_hapus_keluarga_anggota_melepas_keanggotaan_dan_memseudonimkan_jejak(penyimpanan):
    paths, _bundle, hasil, target_sid, lain_sid, *_ = penyimpanan
    lid = _siapkan_lembaga_di_live(paths, "pemilik-les", ["keluarga-target", "keluarga-lain"])
    with database.buka(paths["belajar"]) as kon:
        kon.execute("INSERT INTO pindah_siswa(siswa_id,lembaga_id,dari,ke,oleh)"
                    " VALUES (?,?,?,?,?)",
                    (lain_sid, lid, "keluarga-target", "keluarga-lain", "pemilik-les"))
    inv = _preview(paths)
    selesai = _jalankan(penyimpanan, _perintah(inv))
    with database.buka(hasil / "bundle" / "latihan.db") as kon:
        assert [r[0] for r in kon.execute("SELECT guru FROM anggota_lembaga")] == ["keluarga-lain"]
        assert kon.execute("SELECT COUNT(*) FROM lembaga").fetchone()[0] == 1
        jejak = kon.execute("SELECT dari,ke,oleh FROM pindah_siswa").fetchone()
        assert jejak["dari"] == selesai.pseudonim
        assert (jejak["ke"], jejak["oleh"]) == ("keluarga-lain", "pemilik-les")
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []
        assert "keluarga-target" not in json.dumps([tuple(r) for r in kon.execute(
            "SELECT * FROM pindah_siswa")])
    # Sumber live tidak disentuh.
    with database.buka(paths["belajar"]) as kon:
        assert kon.execute("SELECT COUNT(*) FROM anggota_lembaga").fetchone()[0] == 2


def test_hapus_keluarga_pemilik_membubarkan_lembaga_anggota_tetap_punya_anak(penyimpanan):
    paths, _bundle, hasil, target_sid, lain_sid, *_ = penyimpanan
    lid = _siapkan_lembaga_di_live(paths, "keluarga-target", ["keluarga-lain"])
    with database.buka(paths["belajar"]) as kon:
        kon.execute("INSERT INTO pindah_siswa(siswa_id,lembaga_id,dari,ke,oleh)"
                    " VALUES (?,?,?,?,?)",
                    (lain_sid, lid, "keluarga-lain", "keluarga-lain", "keluarga-target"))
    inv = _preview(paths)
    selesai = _jalankan(penyimpanan, _perintah(inv))
    with database.buka(hasil / "bundle" / "latihan.db") as kon:
        assert kon.execute("SELECT COUNT(*) FROM lembaga").fetchone()[0] == 0
        assert kon.execute("SELECT COUNT(*) FROM anggota_lembaga").fetchone()[0] == 0
        assert kon.execute("SELECT pemilik FROM siswa WHERE id=?", (lain_sid,)).fetchone()[0] == "keluarga-lain"
        assert kon.execute("SELECT oleh FROM pindah_siswa").fetchone()[0] == selesai.pseudonim
        assert kon.execute("PRAGMA foreign_key_check").fetchall() == []


def test_hapus_keluarga_tanpa_lembaga_tidak_berubah(penyimpanan):
    paths, _bundle, hasil, *_ = penyimpanan
    inv = _preview(paths)
    assert _jalankan(penyimpanan, _perintah(inv)).status == "succeeded"
    with database.buka(hasil / "bundle" / "latihan.db") as kon:
        assert kon.execute("SELECT COUNT(*) FROM pindah_siswa").fetchone()[0] == 0

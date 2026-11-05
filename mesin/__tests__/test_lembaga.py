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
        L.lepas_anggota(kon, lembaga_id=lid, guru=GURU_A)
        assert L.anggota(kon, lid) == (GURU_B,)
        with pytest.raises(L.PenolakanLembaga):
            L.lepas_anggota(kon, lembaga_id=lid, guru=GURU_A)


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


def test_pindah_ditolak_bila_nama_bentrok_di_tujuan(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        database.tambah_siswa(kon, "Anak A", "P3", pemilik=GURU_B)
    _tanpa_tulis(jalur, anak["a"], "bentrok_nama",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)


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
        L.lepas_anggota(kon, lembaga_id=lid, guru=GURU_B)
    _tanpa_tulis(jalur, anak["a"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=anak["a"], ke=GURU_B)
    _tanpa_tulis(jalur, anak["b"], "tidak_berwenang",
                 oleh=PEMILIK, siswa_id=anak["b"], ke=GURU_A)


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

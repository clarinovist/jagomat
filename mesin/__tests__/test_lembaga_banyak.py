"""Pindah banyak anak sekaligus (F6) di store: semua-atau-tidak, kewenangan per anak,
sesi berjalan, nama kembar antar anak dalam satu batch, dan batas jumlah.

Data sepenuhnya sintetis. Penolakan dibuktikan tanpa tulis lewat selisih `total_changes`
pada koneksi yang sama (tanpa rollback pemanggil), jadi store sendiri yang harus atomik.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import lembaga_store as L  # noqa: E402
from test_lembaga import (  # noqa: E402,F401
    ADMIN, GURU_A, GURU_B, LUAR, PEMILIK, _habiskan_pembeda, _jumlah_jejak, _pasang_operasi_foto,
    _pemilik, basis,
)


def _banyak(jalur, **kwargs):
    """Satu transaksi seperti handler; mengembalikan (hasil, perubahan_total)."""
    with database.buka(jalur) as kon:
        kon.execute("BEGIN IMMEDIATE")
        sebelum = kon.total_changes
        hasil = L.pindahkan_banyak(kon, **kwargs)
        return hasil, kon.total_changes - sebelum


def _tanpa_tulis_banyak(jalur, anak_ids, status, jumlah=None, **kwargs):
    pemilik = {i: _pemilik(jalur, i) for i in anak_ids}
    jejak = _jumlah_jejak(jalur)
    hasil, perubahan = _banyak(jalur, **kwargs)
    assert hasil.status == status
    if jumlah is not None:
        assert hasil.jumlah == jumlah
    assert perubahan == 0
    assert _jumlah_jejak(jalur) == jejak
    assert {i: _pemilik(jalur, i) for i in anak_ids} == pemilik


def _tambah(jalur, nama, pemilik):
    with database.buka(jalur) as kon:
        return database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)


def _sesi_berjalan(jalur, siswa_id, kolom="mulai"):
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, siswa_id, seed=1, jumlah_soal=1)
        kon.execute("UPDATE sesi SET %s='2026-11-01 08:00:00' WHERE id=?" % kolom, (sesi,))
        return sesi


# --- berhasil ----------------------------------------------------------------

def test_banyak_sukses_satu_ubahan_dan_satu_jejak_per_anak(basis):
    jalur, lid, anak = basis
    hasil, perubahan = _banyak(
        jalur, oleh=PEMILIK, siswa_ids=[anak["a"], anak["o"]], ke=GURU_B)
    assert (hasil.status, hasil.jumlah, hasil.ke) == ("ok", 2, GURU_B)
    assert hasil.berhasil
    assert perubahan == 4
    assert _pemilik(jalur, anak["a"]) == _pemilik(jalur, anak["o"]) == GURU_B
    with database.buka(jalur) as kon:
        jejak = kon.execute(
            "SELECT siswa_id,lembaga_id,dari,ke,oleh FROM pindah_siswa ORDER BY siswa_id").fetchall()
    assert [tuple(r) for r in jejak] == [
        (anak["a"], lid, GURU_A, GURU_B, PEMILIK), (anak["o"], lid, PEMILIK, GURU_B, PEMILIK)]


def test_banyak_boleh_ke_pemilik_dan_satu_anak_saja(basis):
    jalur, _lid, anak = basis
    assert _banyak(jalur, oleh=PEMILIK, siswa_ids=[anak["a"], anak["b"]], ke=PEMILIK)[0].jumlah == 2
    assert _pemilik(jalur, anak["b"]) == PEMILIK
    assert _banyak(jalur, oleh=PEMILIK, siswa_ids=(anak["a"],), ke=GURU_A)[0].status == "ok"


def test_banyak_nama_kembar_antar_anak_dalam_batch_dan_dengan_tujuan_diberi_pembeda(basis):
    jalur, _lid, anak = basis
    k1 = _tambah(jalur, "Kembar", GURU_A)
    k2 = _tambah(jalur, "kembar", PEMILIK)  # beda huruf besar/kecil tetap kembar
    _tambah(jalur, "Kembar", GURU_B)         # sudah ada di tujuan
    hasil, _ = _banyak(jalur, oleh=PEMILIK, siswa_ids=[k2, k1], ke=GURU_B)
    assert hasil.status == "ok"
    with database.buka(jalur) as kon:
        nama = {r["id"]: r["nama"] for r in kon.execute(
            "SELECT id, nama FROM siswa WHERE id IN (?,?)", (k1, k2))}
    # urut id: k1 lebih dulu, lalu k2; keduanya tidak bentrok dengan "Kembar" milik tujuan
    assert nama == {k1: "Kembar (2)", k2: "kembar (3)"}


def test_banyak_nama_kembar_hanya_di_dalam_batch(basis):
    jalur, _lid, anak = basis
    k1 = _tambah(jalur, "Sama", GURU_A)
    k2 = _tambah(jalur, "Sama", PEMILIK)
    assert _banyak(jalur, oleh=PEMILIK, siswa_ids=[k1, k2], ke=GURU_B)[0].status == "ok"
    with database.buka(jalur) as kon:
        nama = sorted(r[0] for r in kon.execute(
            "SELECT nama FROM siswa WHERE pemilik=? AND nama LIKE 'Sama%'", (GURU_B,)))
    assert nama == ["Sama", "Sama (2)"]


def test_banyak_hanya_mengubah_pemilik_bukan_data_belajar(basis):
    jalur, _lid, anak = basis
    sesi = _sesi_berjalan(jalur, anak["a"], "selesai")
    with database.buka(jalur) as kon:
        kon.execute("UPDATE sesi SET dikonfirmasi_guru=? WHERE id=?", (GURU_A, sesi))
    assert _banyak(jalur, oleh=PEMILIK, siswa_ids=[anak["a"], anak["o"]], ke=GURU_B)[0].berhasil
    with database.buka(jalur) as kon:
        assert kon.execute("SELECT siswa_id FROM sesi WHERE id=?", (sesi,)).fetchone()[0] == anak["a"]


# --- kewenangan: tolak semua tanpa efek -------------------------------------------

@pytest.mark.parametrize("kunci", ["luar", 99999])
def test_banyak_ditolak_bila_anak_terakhir_di_luar_lembaga_atau_tak_ada(basis, kunci):
    jalur, _lid, anak = basis
    buruk = anak.get(kunci, kunci)
    ids = [anak["a"], anak["o"], buruk]  # anak sah lebih dulu; yang buruk diperiksa terakhir
    assert buruk > anak["o"]
    _tanpa_tulis_banyak(jalur, [anak["a"], anak["o"]], "tidak_berwenang",
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


@pytest.mark.parametrize("tujuan", [LUAR, "", "admin", "tidak-ada"])
def test_banyak_ditolak_bila_tujuan_di_luar_lembaga(basis, tujuan):
    jalur, _lid, anak = basis
    _tanpa_tulis_banyak(jalur, [anak["a"], anak["o"]], "tidak_berwenang",
                        oleh=PEMILIK, siswa_ids=[anak["a"], anak["o"]], ke=tujuan)


@pytest.mark.parametrize("aktor", [GURU_A, LUAR, "admin", ""])
def test_banyak_ditolak_bila_aktor_bukan_pemilik_lembaga(basis, aktor):
    jalur, _lid, anak = basis
    _tanpa_tulis_banyak(jalur, [anak["a"], anak["b"]], "tidak_berwenang",
                        oleh=aktor, siswa_ids=[anak["a"], anak["b"]], ke=GURU_B)


def test_banyak_ke_guru_lembaga_lain_ditolak(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        lain = L.buat_lembaga(kon, nama="Les Lain", pemilik="pemilik-dua")
        L.tambah_anggota(kon, lembaga_id=lain, guru="anggota-dua")
    _tanpa_tulis_banyak(jalur, [anak["a"]], "tidak_berwenang",
                        oleh=PEMILIK, siswa_ids=[anak["a"]], ke="anggota-dua")
    _tanpa_tulis_banyak(jalur, [anak["a"]], "tidak_berwenang",
                        oleh="pemilik-dua", siswa_ids=[anak["a"]], ke="anggota-dua")


@pytest.mark.parametrize("ids", [[], (), [True], ["1"], [1.0], None, "12", [1, 1]])
def test_banyak_bentuk_tidak_sah_ditolak_tanpa_tulis(basis, ids):
    jalur, _lid, anak = basis
    _tanpa_tulis_banyak(jalur, [anak["a"]], "tidak_berwenang",
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


def test_banyak_duplikat_id_ditolak_walau_anak_sah(basis):
    jalur, _lid, anak = basis
    _tanpa_tulis_banyak(jalur, [anak["a"]], "tidak_berwenang",
                        oleh=PEMILIK, siswa_ids=[anak["a"], anak["a"]], ke=GURU_B)


def test_banyak_kewenangan_mendahului_penolakan_bisnis(basis):
    """Anak luar + anak bersesi berjalan: jawabannya tetap tidak_berwenang (404), bukan pesan sesi."""
    jalur, _lid, anak = basis
    _sesi_berjalan(jalur, anak["a"])
    _tanpa_tulis_banyak(jalur, [anak["a"], anak["luar"]], "tidak_berwenang",
                        oleh=PEMILIK, siswa_ids=[anak["a"], anak["luar"]], ke=GURU_B)


# --- penolakan bisnis: tolak semua tanpa efek, sebut jumlah bermasalah ------------

def test_banyak_ditolak_bila_ada_anak_yang_sudah_di_tujuan(basis):
    jalur, _lid, anak = basis
    ids = [anak["a"], anak["o"], anak["b"]]
    _tanpa_tulis_banyak(jalur, ids, "sama", jumlah=1,
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


@pytest.mark.parametrize("kolom", ["mulai", "selesai"])
def test_banyak_ditolak_selagi_anak_terakhir_punya_sesi_berjalan(basis, kolom):
    jalur, _lid, anak = basis
    _sesi_berjalan(jalur, anak["o"], kolom)  # anak ke-2 (id lebih besar) bersesi berjalan
    ids = [anak["a"], anak["o"]]
    _tanpa_tulis_banyak(jalur, ids, "sesi_berjalan", jumlah=1,
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)
    # Setelah dikonfirmasi, seluruh batch boleh pindah.
    with database.buka(jalur) as kon:
        kon.execute("UPDATE sesi SET dikonfirmasi_guru=?", (PEMILIK,))
    assert _banyak(jalur, oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)[0].jumlah == 2


def test_banyak_menyebut_jumlah_semua_anak_bersesi_berjalan(basis):
    jalur, _lid, anak = basis
    _sesi_berjalan(jalur, anak["a"])
    _sesi_berjalan(jalur, anak["o"])
    ids = [anak["a"], anak["o"]]
    _tanpa_tulis_banyak(jalur, ids, "sesi_berjalan", jumlah=2,
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


def test_banyak_ditolak_selagi_operasi_foto_belum_selesai(basis):
    jalur, _lid, anak = basis
    with database.buka(jalur) as kon:
        sesi = database.buat_sesi(kon, anak["o"], seed=1, jumlah_soal=1)
        _pasang_operasi_foto(kon, sesi, "sent")
    ids = [anak["a"], anak["o"]]
    _tanpa_tulis_banyak(jalur, ids, "sesi_berjalan", jumlah=1,
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


def test_banyak_ditolak_bila_pembeda_nama_habis_tanpa_menulis_anak_lain(basis):
    jalur, _lid, anak = basis
    _habiskan_pembeda(jalur, "Anak O", GURU_B)  # "Anak O" tidak bisa diberi nama bebas di GURU_B
    ids = [anak["a"], anak["o"]]
    _tanpa_tulis_banyak(jalur, ids, "bentrok_nama",
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


# --- batas jumlah ------------------------------------------------------------

def _anak_massal(jalur, jumlah, pemilik):
    return [_tambah(jalur, "Murid %03d" % i, pemilik) for i in range(jumlah)]


def test_banyak_tepat_di_batas_diterima(basis):
    jalur, _lid, _anak = basis
    ids = _anak_massal(jalur, L.BATAS_PINDAH_BANYAK, GURU_A)
    hasil, perubahan = _banyak(jalur, oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)
    assert (hasil.status, hasil.jumlah) == ("ok", L.BATAS_PINDAH_BANYAK)
    assert perubahan == 2 * L.BATAS_PINDAH_BANYAK
    assert {_pemilik(jalur, i) for i in ids} == {GURU_B}


def test_banyak_di_atas_batas_ditolak_tanpa_tulis(basis):
    jalur, _lid, _anak = basis
    ids = _anak_massal(jalur, L.BATAS_PINDAH_BANYAK + 1, GURU_A)
    _tanpa_tulis_banyak(jalur, ids, "terlalu_banyak", jumlah=len(ids),
                        oleh=PEMILIK, siswa_ids=ids, ke=GURU_B)


def test_batas_pindah_banyak_adalah_konstanta_wajar():
    assert L.BATAS_PINDAH_BANYAK == 50

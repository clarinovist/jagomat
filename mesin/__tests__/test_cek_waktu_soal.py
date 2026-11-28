"""Waktu mengerjakan per soal pada alur anak cek gratis (F1): t0, jendela, batas, dan jalur simpan.

Data sintetis; jam server disuntik lewat monkeypatch supaya hasilnya deterministik.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_waktu_soal  # noqa: E402
from cek_anak_kit import Cek, lokasi, server  # noqa: E402,F401  (fixture server)

JAM_SINTETIS = 1_800_000_000
POLA_T0 = re.compile(r'name="t0" value="([0-9]+)"')


@pytest.fixture()
def cek(server):
    return Cek(server)


@pytest.fixture()
def jam(monkeypatch):
    penunjuk = {"detik": JAM_SINTETIS}
    monkeypatch.setattr(cek_waktu_soal, "sekarang", lambda: penunjuk["detik"])
    return penunjuk


def _detik(cek, nomor):
    with cek.server.buka() as kon:
        baris = kon.execute(
            """SELECT j.detik FROM jawaban j JOIN sesi_soal ss ON ss.id = j.sesi_soal_id
               WHERE ss.sesi_id = ? AND ss.nomor = ?""",
            (cek.sesi_id, nomor),
        ).fetchone()
    return baris[0] if baris else None


# --- fungsi murni ---------------------------------------------------------------

@pytest.mark.parametrize("t0, harapan", [
    (str(JAM_SINTETIS - 30), 30),
    (str(JAM_SINTETIS), 0),
    (str(JAM_SINTETIS - 600), 600),
    (str(JAM_SINTETIS - 601), 600),
    (str(JAM_SINTETIS - 3600), 600),
])
def test_detik_dihitung_lalu_dibatasi_di_batas_atas(t0, harapan):
    assert cek_waktu_soal.hitung_detik(t0, JAM_SINTETIS) == harapan


@pytest.mark.parametrize("t0", [
    None, "", "abc", "-5", "1.5", " 1000", "1000 ", "1e9", "1" * 13,
    str(JAM_SINTETIS + 1), str(JAM_SINTETIS - 3601),
])
def test_t0_tidak_sah_menghasilkan_detik_kosong(t0):
    assert cek_waktu_soal.hitung_detik(t0, JAM_SINTETIS) is None


def test_t0_bukan_teks_menghasilkan_detik_kosong():
    assert cek_waktu_soal.hitung_detik(JAM_SINTETIS - 30, JAM_SINTETIS) is None


# --- halaman soal memuat t0 dari jam server ----------------------------------------

def test_halaman_soal_memuat_t0_sama_dengan_jam_server(cek, jam):
    kode, isi, _t = cek.get(soal=1)
    assert kode == 200
    assert POLA_T0.search(isi).group(1) == str(JAM_SINTETIS)


def test_halaman_soal_tanpa_pilihan_dirender_ulang_dengan_t0_baru(cek, jam):
    jam["detik"] = JAM_SINTETIS + 90
    kode, isi, _t = cek.simpan(1, opsi=None)
    assert kode == 200
    assert POLA_T0.search(isi).group(1) == str(JAM_SINTETIS + 90)


# --- jalur simpan ------------------------------------------------------------------

def test_simpan_dengan_t0_sah_mengisi_detik(cek, jam):
    cek.get(soal=1)
    jam["detik"] = JAM_SINTETIS + 45
    kode, _i, tajuk = cek.simpan(1, t0=str(JAM_SINTETIS))
    assert kode == 303 and "soal=2" in lokasi(tajuk)
    assert _detik(cek, 1) == 45


def test_simpan_dengan_jeda_lama_dibatasi_600_detik(cek, jam):
    jam["detik"] = JAM_SINTETIS
    cek.simpan(1, t0=str(JAM_SINTETIS - 2000))
    assert _detik(cek, 1) == 600


def test_simpan_tanpa_t0_tetap_tersimpan_dengan_detik_kosong(cek, jam):
    kode, _i, _t = cek.simpan(1)
    assert kode == 303
    assert _detik(cek, 1) is None and cek.terjawab() == 1


@pytest.mark.parametrize("t0", ["abc", str(JAM_SINTETIS + 5), str(JAM_SINTETIS - 3601), ""])
def test_simpan_dengan_t0_rusak_tetap_tersimpan_dengan_detik_kosong(cek, jam, t0):
    kode, _i, _t = cek.simpan(1, t0=t0)
    assert kode == 303
    assert _detik(cek, 1) is None and cek.terjawab() == 1


def test_simpan_ulang_dengan_t0_sah_menimpa_detik_lama(cek, jam):
    cek.simpan(1, t0=str(JAM_SINTETIS - 30))
    assert _detik(cek, 1) == 30
    cek.simpan(1, opsi="opsi_2", t0=str(JAM_SINTETIS - 10))
    assert _detik(cek, 1) == 10


def test_simpan_ulang_dengan_t0_rusak_mempertahankan_detik_lama(cek, jam):
    cek.simpan(1, t0=str(JAM_SINTETIS - 30))
    jawaban_awal = cek.jawaban()[0][1]
    cek.simpan(1, opsi="opsi_2", t0="abc")
    assert _detik(cek, 1) == 30
    assert cek.jawaban()[0][1] != jawaban_awal  # jawaban tetap diperbarui walau detik dipertahankan


def test_keluar_dengan_t0_sah_juga_mengisi_detik(cek, jam):
    data = {
        "aksi": "keluar", "soal": "1", "revisi_pekerjaan": str(cek.revisi()),
        f"opsi_{cek.id_butir(1)}": "opsi_1", "t0": str(JAM_SINTETIS - 20),
    }
    jam["detik"] = JAM_SINTETIS
    kode, _i, tajuk = cek.post(data)
    assert kode == 303 and "keluar=1" in lokasi(tajuk)
    assert _detik(cek, 1) == 20


@pytest.mark.parametrize("data_tambahan", [
    {"aksi": "mulai", "t0": str(JAM_SINTETIS)},
    {"aksi": "kumpul", "t0": str(JAM_SINTETIS)},
])
def test_t0_di_aksi_selain_simpan_dan_keluar_ditolak_tanpa_efek(cek, jam, data_tambahan):
    data = dict(data_tambahan)
    if data["aksi"] == "kumpul":
        data["revisi_pekerjaan"] = str(cek.revisi())
    sebelum = (cek.jawaban(), cek.status_sesi())
    kode, _i, _t = cek.post(data)
    assert kode == 400
    assert (cek.jawaban(), cek.status_sesi()) == sebelum

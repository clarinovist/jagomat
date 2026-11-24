"""Data halaman orang tua (D1-3): `peta` hanya bila laporan TERBIT dan status pesanan sudah_dibayar; galat baca = None.

Data sintetis di basis sementara. Tes ini menjadi sasaran mutation di `test_peta_laporan_ortu_mutation.py`.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import orang_tua_data as data  # noqa: E402
import pesanan_dasar  # noqa: E402
import peta_laporan_store as store  # noqa: E402

GURU = "guru-sintetis"
EPOCH = 1_795_000_000
CATATAN = "Catatan sintetis: anak makin lancar berhitung."
LUNAS = pesanan_dasar.STATUS_SUDAH_DIBAYAR
BUKAN_LUNAS = [s for s in pesanan_dasar.STATUS_TURUNAN if s != LUNAS] + [None]
ISI = {
    "versi": 1, "kelas": 4, "tanggal_cek": "2026-11-18", "skor": 47, "kategori": "Perlu penguatan",
    "jumlah_soal": 15, "per_materi": [{"materi": "Berhitung", "benar": 5, "total": 5},
                                      {"materi": "Pengukuran", "benar": 2, "total": 5}],
    "kuat": ["Berhitung"], "perlu_dilatih": ["Pengukuran"], "ringkasan_perlu": [],
}


@pytest.fixture()
def kon(tmp_path):
    jalur = tmp_path / "peta-data.db"
    database.siapkan(jalur)
    with database.buka(jalur) as koneksi:
        yield koneksi


def _anak(kon, nama="Anak Sintetis") -> int:
    return database.tambah_siswa(kon, nama, "P4", pemilik=GURU)


def _laporan(kon, siswa, *, terbit=True, catatan=CATATAN) -> None:
    store.buat_draf(kon, siswa, GURU, ISI, EPOCH)
    store.simpan_catatan(kon, siswa, catatan)
    if terbit:
        store.terbitkan(kon, siswa, GURU, EPOCH + 60)


def test_terbit_dan_sudah_dibayar_mengisi_peta_tanpa_akun_guru(kon):
    siswa = _anak(kon)
    _laporan(kon, siswa)
    peta = data.peta_terbit(kon, siswa, LUNAS)
    assert peta["catatan"] == CATATAN and peta["isi"]["skor"] == 47 and peta["diterbitkan"]
    assert GURU not in repr(peta)


def test_draf_tidak_mengisi_peta_walau_sudah_dibayar(kon):
    siswa = _anak(kon)
    _laporan(kon, siswa, terbit=False)
    assert data.peta_terbit(kon, siswa, LUNAS) is None


def test_tanpa_laporan_peta_none(kon):
    assert data.peta_terbit(kon, _anak(kon), LUNAS) is None


@pytest.mark.parametrize("status", BUKAN_LUNAS)
def test_status_selain_sudah_dibayar_tidak_mengisi_peta(kon, status):
    siswa = _anak(kon)
    _laporan(kon, siswa)
    assert data.peta_terbit(kon, siswa, status) is None


def test_status_selain_sudah_dibayar_tidak_membaca_laporan_sama_sekali(kon, monkeypatch):
    def terlarang(*a, **k):
        raise AssertionError("laporan dibaca padahal belum lunas")
    monkeypatch.setattr(store, "terbit_terakhir", terlarang)
    assert data.peta_terbit(kon, _anak(kon), pesanan_dasar.STATUS_BELUM_BAYAR) is None


def test_laporan_anak_lain_tidak_pernah_terbaca(kon):
    a, b = _anak(kon, "Anak A"), _anak(kon, "Anak B")
    _laporan(kon, b)
    assert data.peta_terbit(kon, a, LUNAS) is None
    assert data.peta_terbit(kon, b, LUNAS)["catatan"] == CATATAN


def _rusakkan_isi(kon, siswa):
    kon.execute("DROP TRIGGER peta_laporan_terbit_tetap")
    kon.execute("DROP TRIGGER peta_laporan_isi_tetap")
    kon.execute("UPDATE peta_laporan SET isi = ? WHERE siswa_id = ?", ("{bukan json", siswa))


def test_isi_rusak_menjadi_none_dan_log_tanpa_data(kon, caplog):
    siswa = _anak(kon)
    _laporan(kon, siswa)
    _rusakkan_isi(kon, siswa)
    with caplog.at_level(logging.WARNING):
        assert data.peta_terbit(kon, siswa, LUNAS) is None
    assert caplog.records and CATATAN not in caplog.text and "bukan json" not in caplog.text


def test_isi_di_luar_allowlist_menjadi_none(kon):
    siswa = _anak(kon)
    _laporan(kon, siswa)
    kon.execute("DROP TRIGGER peta_laporan_terbit_tetap")
    kon.execute("DROP TRIGGER peta_laporan_isi_tetap")
    kon.execute("UPDATE peta_laporan SET isi = ? WHERE siswa_id = ?", ('{"versi": 1}', siswa))
    assert data.peta_terbit(kon, siswa, LUNAS) is None


def test_tabel_hilang_menjadi_none_bukan_galat(kon):
    siswa = _anak(kon)
    kon.execute("DROP TABLE peta_laporan")
    assert data.peta_terbit(kon, siswa, LUNAS) is None


def test_galat_sqlite_apa_pun_menjadi_none(kon, monkeypatch):
    def gagal(*a, **k):
        raise sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(store, "terbit_terakhir", gagal)
    assert data.peta_terbit(kon, _anak(kon), LUNAS) is None


def test_kumpulkan_mengisi_field_peta_hanya_saat_lunas(kon, monkeypatch):
    siswa = _anak(kon)
    _laporan(kon, siswa)
    monkeypatch.setattr(data, "status_pesanan", lambda *a, **k: LUNAS)
    assert data.kumpulkan(kon, "akun_" + "a1" * 16, siswa).peta["catatan"] == CATATAN
    monkeypatch.setattr(data, "status_pesanan", lambda *a, **k: pesanan_dasar.STATUS_BELUM_BAYAR)
    assert data.kumpulkan(kon, "akun_" + "a1" * 16, siswa).peta is None

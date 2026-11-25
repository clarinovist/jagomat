"""Butir antrean admin "Peta dibayar, laporan belum terbit" (butir QA #2, 25 Nov 2026; data sintetis, read-only).

Janji publik: laporan terbit dalam 48 jam setelah pembayaran. Order Peta lunas tanpa laporan terbit ditampilkan; yang sudah lewat janji
naik jadi "penting". Sumber = domain `purna` (lunas, ditahan, direfund, terbit, terlambat), bukan salinan logikanya.
"""
from datetime import datetime, timezone

import pytest

import admin_antrean as A
import admin_antrean_bayar as B
import admin_operations
import admin_queries as Q
import kelas_kit as kk
import purna
import pesanan_kit
from kelas_kit import db_kelas, kon_kelas  # noqa: F401

LUNAS = pesanan_kit.SEKARANG                       # 2026-11-18T10:00:00
DALAM_JANJI = "2026-11-18T22:00:00"                # +12 jam
LEWAT_JANJI = "2026-11-20T11:00:00"                # +49 jam
KONTEKS_KOSONG = Q.KonteksAdmin((), (), ())


def _epoch(iso):
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def tanpa_operasi(monkeypatch):
    monkeypatch.setattr(admin_operations, "antrean", lambda path, **k: ((), 0))
    monkeypatch.setattr(admin_operations, "bukti_backup", lambda sekarang: ("Bundle valid", 1.0))


def _kumpulkan(path, kini):
    return A.kumpulkan(KONTEKS_KOSONG, path, sekarang=_epoch(kini))


def _butir(antrean):
    return [i for i in antrean.item if "laporan belum terbit" in i.judul]


def test_tanpa_order_peta_lunas_nol(db_kelas):
    assert B.peta_belum_terbit(db_kelas, DALAM_JANJI) == (0, 0)


def test_lunas_dalam_janji_menunggu_belum_terlambat(db_kelas, kon_kelas):
    kk.peta_lunas(kon_kelas, 1)
    assert B.peta_belum_terbit(db_kelas, DALAM_JANJI) == (1, 0)


def test_lunas_lewat_janji_terlambat(db_kelas, kon_kelas):
    kk.peta_lunas(kon_kelas, 1)
    assert B.peta_belum_terbit(db_kelas, LEWAT_JANJI) == (1, 1)


def test_laporan_terbit_tidak_dihitung(db_kelas, kon_kelas):
    order = kk.peta_lunas(kon_kelas, 1)
    purna.catat_terbit(kon_kelas, order, "guru_sintetis", DALAM_JANJI)
    assert B.peta_belum_terbit(db_kelas, LEWAT_JANJI) == (0, 0)


def test_belum_lunas_tidak_dihitung(db_kelas, kon_kelas):
    pesanan_kit.buat(kon_kelas, 1, akun=kk.AKUN_A, siswa=1)           # dibuat, belum dibayar
    assert B.peta_belum_terbit(db_kelas, LEWAT_JANJI) == (0, 0)


def test_order_yang_direfund_tidak_dihitung(db_kelas, kon_kelas):
    import pesanan
    from purna_kit import operasi
    from transfer_kit import ADMIN
    order = kk.peta_lunas(kon_kelas, 1)
    pesanan.catat_refund(kon_kelas, order, operasi(1), ADMIN, "kebijakan", DALAM_JANJI)
    assert B.peta_belum_terbit(db_kelas, LEWAT_JANJI) == (0, 0)


def test_beberapa_order_dihitung_terpisah(db_kelas, kon_kelas):
    a = kk.peta_lunas(kon_kelas, 1)
    kk.peta_lunas(kon_kelas, 2, akun=kk.AKUN_B)
    purna.catat_terbit(kon_kelas, a, "guru_sintetis", DALAM_JANJI)
    assert B.peta_belum_terbit(db_kelas, LEWAT_JANJI) == (1, 1)


def test_ledger_tak_terbaca_atau_purna_belum_dipasang_berarti_nol(tmp_path):
    (tmp_path / "bukan-db.db").write_bytes(b"bukan sqlite")
    assert B.peta_belum_terbit(tmp_path / "bukan-db.db", LEWAT_JANJI) == (0, 0)
    assert B.peta_belum_terbit(tmp_path / "tidak-ada.db", LEWAT_JANJI) == (0, 0)


def test_antrean_dalam_janji_butir_tinjau_tanpa_menambah_perlu_keputusan(db_kelas, kon_kelas):
    kk.peta_lunas(kon_kelas, 1)
    antrean = _kumpulkan(db_kelas, DALAM_JANJI)
    (item,) = _butir(antrean)
    assert (item.tingkat, item.judul) == ("tinjau", "1 Peta dibayar, laporan belum terbit")
    assert antrean.perlu_keputusan == 0 and antrean.total == 1
    assert item.jalur == "/admin/pembayaran?status=dibayar"


def test_antrean_lewat_janji_butir_penting_dan_menambah_perlu_keputusan(db_kelas, kon_kelas):
    kk.peta_lunas(kon_kelas, 1)
    kk.peta_lunas(kon_kelas, 2, akun=kk.AKUN_B)
    antrean = _kumpulkan(db_kelas, LEWAT_JANJI)
    (item,) = _butir(antrean)
    assert item.tingkat == "penting" and item.judul == "2 Peta dibayar, laporan belum terbit"
    assert "2 di antaranya sudah lewat" in item.deskripsi and "48 jam" in item.deskripsi
    assert antrean.perlu_keputusan == 1 and antrean.mendesak == 0


def test_antrean_tanpa_nama_anak_atau_akun(db_kelas, kon_kelas):
    kk.peta_lunas(kon_kelas, 1)
    (item,) = _butir(_kumpulkan(db_kelas, LEWAT_JANJI))
    assert kk.AKUN_A not in repr(item) and "siswa" not in repr(item).lower().replace("siswa_id", "")


def test_antrean_kosong_bila_semua_terbit(db_kelas, kon_kelas):
    order = kk.peta_lunas(kon_kelas, 1)
    purna.catat_terbit(kon_kelas, order, "guru_sintetis", DALAM_JANJI)
    antrean = _kumpulkan(db_kelas, LEWAT_JANJI)
    assert _butir(antrean) == [] and antrean.total == 0

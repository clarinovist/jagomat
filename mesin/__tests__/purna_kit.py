"""Pembantu bersama tes domain purna: DB admin sintetis (pesanan + transfer + purna) dan order lunas."""
from __future__ import annotations

import pytest

import pesanan
import pesanan_transfer as tf
import schema_purna
from pesanan_kit import SEKARANG, buat, hitung, operasi, siapkan_db, terapkan  # noqa: F401
from transfer_kit import ADMIN, menunggu, siapkan_db_transfer

WAKTU_SETUJU = "2026-11-18T12:00:00"
# Order QRIS lunas pada SEKARANG; order transfer lunas pada WAKTU_SETUJU (SLA 48 jam, toleransi 0 jam, voucher 90 hari).
QRIS_JANJI, QRIS_BATAS, QRIS_HINGGA = "2026-11-20T10:00:00", "2026-11-20T10:00:00", "2027-02-16T10:00:00"
TRANSFER_JANJI, TRANSFER_BATAS, TRANSFER_HINGGA = ("2026-11-20T12:00:00", "2026-11-20T12:00:00",
                                                   "2027-02-16T12:00:00")
PELAKU = ADMIN


def siapkan_db_purna(tmp_path):
    """DB admin sintetis: pesanan + transfer + purna (migrasi eksplisit)."""
    path = siapkan_db_transfer(tmp_path)
    schema_purna.migrasikan(path)
    return path


@pytest.fixture
def db(tmp_path):
    return siapkan_db_purna(tmp_path)


@pytest.fixture
def kon(db):
    with pesanan.buka(db, tulis_data=True) as koneksi:
        yield koneksi


@pytest.fixture
def kon_tanpa_purna(tmp_path):
    """Koneksi ke DB pesanan + transfer yang BELUM dimigrasikan purna."""
    with pesanan.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as koneksi:
        yield koneksi


@pytest.fixture
def kon_pesanan_saja(tmp_path):
    """Koneksi ke DB pesanan v1 saja (tanpa transfer_*, tanpa purna_*)."""
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as koneksi:
        yield koneksi


def order_qris_lunas(kon, n=1):
    order = buat(kon, n)
    terapkan(kon, order, n, transaction_id="trx-sintetis-%04d" % n)
    return order["order_id"]


def order_transfer_lunas(kon, n=1):
    order, _ = menunggu(kon, n)
    tf.setujui(kon, order["order_id"], ADMIN, WAKTU_SETUJU)
    return order["order_id"]


def order_belum_lunas(kon, n=1):
    return buat(kon, n)["order_id"]


def refund_mentah(kon, order_id, n=1, tabel="pesanan_refund"):
    """Sisipkan catatan refund tanpa lewat domain (melewati guard) untuk menyiapkan keadaan langka."""
    kon.execute("INSERT INTO %s(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) VALUES(?,?,?,?,?)"
                % tabel, (operasi(n), order_id, ADMIN, "kebijakan", SEKARANG))
    kon.commit()


def baris(kon, tabel):
    return [tuple(r) for r in kon.execute("SELECT * FROM %s ORDER BY rowid" % tabel)]

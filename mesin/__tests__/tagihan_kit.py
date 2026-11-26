"""Pembantu tes batal/pulih tagihan (`tagihan_*`): DB admin sintetis dengan kelas dan catatan tagihan.

Semua data sintetis (akun, anak, dan waktu buatan dari `kelas_kit`). Koneksi memakai transaksi implisit sqlite3,
jadi tes yang menyisipkan baris mentah memanggil `commit()` sebelum memanggil domain yang memakai `d.tulis`.
"""
from __future__ import annotations

import pytest

import pesanan
import schema_tagihan_catatan as stc
from kelas_kit import KINI, siapkan_db_kelas


def siapkan_db_tagihan(tmp_path):
    """DB admin sintetis: kelas sudah dipasang dan catatan tagihan sudah dimigrasikan."""
    path = siapkan_db_kelas(tmp_path)
    stc.migrasikan(path)
    return path


@pytest.fixture
def db_tagihan(tmp_path):
    return siapkan_db_tagihan(tmp_path)


@pytest.fixture
def kon_tagihan(db_tagihan):
    with pesanan.buka(db_tagihan, tulis_data=True) as koneksi:
        yield koneksi


def sisip_catatan(kon, order_id, aksi, dibuat=KINI, *, id_catatan=None, ganti=False):
    """Sisip satu baris `tagihan_catatan` MENTAH (melewati domain) untuk menguji trigger; mengembalikan id."""
    perintah = "INSERT OR REPLACE" if ganti else "INSERT"
    if id_catatan is None:
        kursor = kon.execute(perintah + " INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)",
                             (order_id, aksi, dibuat))
    else:
        kursor = kon.execute(perintah + " INTO tagihan_catatan(id,order_id,aksi,dibuat) VALUES(?,?,?,?)",
                             (id_catatan, order_id, aksi, dibuat))
    kon.commit()
    return kursor.lastrowid


def semua_catatan(kon):
    return [tuple(r) for r in kon.execute("SELECT id,order_id,aksi,dibuat FROM tagihan_catatan ORDER BY id")]


def jumlah_catatan(kon):
    return kon.execute("SELECT COUNT(*) FROM tagihan_catatan").fetchone()[0]



"""Pembantu bersama tes domain kelas: DB admin sintetis (pesanan + transfer + purna + kelas) dan data sintetis.

Semua data sintetis. Akun/anak/admin hanya id buatan; tanpa DB asli.
"""
from __future__ import annotations

import pytest

import kelas_putusan
import kelas_store
import pesanan
import schema_kelas
from pesanan_kit import AKUN_A, AKUN_B, SEKARANG, buat, operasi, terapkan  # noqa: F401
from purna_kit import siapkan_db_purna

ADMIN = "admin_sintetis_a"
ADMIN_B = "admin_sintetis_b"
MIME = "image/jpeg"
UKURAN = 120_000
# Peta QRIS lunas pada SEKARANG; deposit berlaku 90 hari (sampai 2027-02-16T10:00:00).
KINI = "2026-11-20T09:00:00"
SESUDAH_UPLOAD = "2026-11-20T09:30:00"
SESUDAH_JENDELA = "2026-11-21T09:00:00"           # tepat 24 jam sesudah KINI
SESUDAH_DEPOSIT = "2027-02-17T00:00:00"


def siapkan_db_kelas(tmp_path):
    """DB admin sintetis: pesanan + transfer + purna + kelas (migrasi eksplisit)."""
    path = siapkan_db_purna(tmp_path)
    schema_kelas.migrasikan(path)
    return path


@pytest.fixture
def db_kelas(tmp_path):
    return siapkan_db_kelas(tmp_path)


@pytest.fixture
def kon_kelas(db_kelas):
    with pesanan.buka(db_kelas, tulis_data=True) as koneksi:
        yield koneksi


def sha(n):
    return "%064x" % (n + 0xA0)


def berkas(n):
    return "%032x" % (n + 0xB0)


def kor(n):
    return "kor_%032x" % n


def kel(n):
    return "kel_%032x" % n


def peta_lunas(kon, siswa, akun=AKUN_A):
    """Order Peta (QRIS) lunas pada SEKARANG untuk `siswa`; mengembalikan order_id. Deposit aktif sampai 90 hari."""
    order = buat(kon, siswa, akun=akun, siswa=siswa)
    terapkan(kon, order, siswa, transaction_id="trx-sintetis-%04d" % siswa)
    return order["order_id"]


# --- jalur domain (kelas_store/kelas_putusan) ------------------------------------------------------

def pilih_pertama(bebas):
    """Pemilih kode unik deterministik untuk tes: kode terkecil yang masih bebas."""
    return bebas[0]


def tagih(kon, siswa=1, paket="mini", *, akun=AKUN_A, sekarang=KINI):
    return kelas_store.buat_tagihan(kon, akun, siswa, paket, sekarang, acak=pilih_pertama)


def unggah(kon, siswa=1, paket="mini", n=1, *, akun=AKUN_A, sekarang=SESUDAH_UPLOAD):
    return kelas_store.catat_bukti(kon, akun, siswa, paket, MIME, UKURAN, sha(n), berkas(n), sekarang)


def menunggu(kon, siswa=1, paket="mini", n=1, *, akun=AKUN_A, sekarang=KINI, unggah_pada=SESUDAH_UPLOAD):
    """Tagihan + satu bukti: status `menunggu`. Mengembalikan (TagihanKelas, id bukti)."""
    tagihan = tagih(kon, siswa, paket, akun=akun, sekarang=sekarang)
    return tagihan, unggah(kon, siswa, paket, n, akun=akun, sekarang=unggah_pada)["bukti_id"]


def setuju(kon, tagihan, bukti_id, *, sekarang=SESUDAH_UPLOAD, admin=ADMIN):
    return kelas_putusan.setujui(kon, tagihan.order_id, admin, sekarang, bukti_dilihat=bukti_id)


def lunas(kon, siswa=1, paket="mini", n=1, *, akun=AKUN_A, sekarang=KINI, putus=SESUDAH_UPLOAD):
    """Tagihan sampai disetujui admin (akses tertulis). Mengembalikan TagihanKelas awal."""
    tagihan, bukti_id = menunggu(kon, siswa, paket, n, akun=akun, sekarang=sekarang)
    setuju(kon, tagihan, bukti_id, sekarang=putus)
    return tagihan


# --- sisipan mentah (melewati domain) untuk tes skema dan keadaan langka -----------------------

def sisip_order(kon, n=1, *, akun=AKUN_A, siswa=1, paket="mini", dibuat=KINI, kedaluwarsa="2026-11-21T09:00:00"):
    kon.execute("INSERT INTO kelas_order(id,akun_id,siswa_id,paket,dibuat,kedaluwarsa) VALUES(?,?,?,?,?,?)",
                (kor(n), akun, siswa, paket, dibuat, kedaluwarsa))
    return kor(n)


def sisip_tagihan(kon, oid, *, harga=250_000, deposit=0, diskon=0, deposit_order=None, kode=7, nominal=None,
                  total=None, dibuat=KINI):
    nominal = harga - deposit - diskon if nominal is None else nominal
    total = nominal + kode if total is None else total
    kon.execute("INSERT INTO kelas_tagihan(order_id,harga_dasar,potongan_deposit,potongan_diskon,"
                "deposit_order_id,nominal,kode_unik,total_transfer,dibuat) VALUES(?,?,?,?,?,?,?,?,?)",
                (oid, harga, deposit, diskon, deposit_order, nominal, kode, total, dibuat))


def sisip_bukti(kon, oid, n=1, *, diunggah=SESUDAH_UPLOAD, **ganti):
    nilai = dict(berkas=berkas(n), mime=MIME, ukuran=UKURAN, sha256=sha(n))
    nilai.update(ganti)
    return kon.execute("INSERT INTO kelas_bukti(order_id,berkas,mime,ukuran,sha256,diunggah) VALUES(?,?,?,?,?,?)",
                       (oid, nilai["berkas"], nilai["mime"], nilai["ukuran"], nilai["sha256"], diunggah)).lastrowid


def sisip_verifikasi(kon, oid, bukti_id, *, keputusan="setuju", alasan=None, admin=ADMIN, dibuat=SESUDAH_UPLOAD):
    return kon.execute("INSERT INTO kelas_verifikasi(order_id,keputusan,admin_id,alasan,bukti_hingga_id,dibuat) "
                       "VALUES(?,?,?,?,?,?)", (oid, keputusan, admin, alasan, bukti_id, dibuat)).lastrowid


def baris(kon, tabel):
    return [tuple(r) for r in kon.execute("SELECT * FROM %s ORDER BY rowid" % tabel)]

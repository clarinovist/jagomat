"""Pembantu bersama tes transfer rekening: DB admin sementara + data sintetis."""
from __future__ import annotations

from pesanan_kit import (AKUN_A, AKUN_B, SEKARANG, SESUDAH_KEDALUWARSA, buat,  # noqa: F401
                         hitung, operasi, ord_id, siapkan_db)
import pesanan_transfer as tf
import schema_transfer

ADMIN = "admin_sintetis_a"
ADMIN_B = "admin_sintetis_b"
MIME = "image/jpeg"
UKURAN = 120_000
SESUDAH_UPLOAD = "2026-11-18T12:00:00"


def siapkan_db_transfer(tmp_path):
    """DB admin sintetis: pesanan v1 + namespace transfer_*."""
    path = siapkan_db(tmp_path)
    schema_transfer.migrasikan(path)
    return path


def akun_ke(n):
    """Akun sintetis ke-n: satu akun hanya boleh punya satu order menunggu verifikasi."""
    return "akun_" + ("%02x" % (n + 0xC0)) * 16


def sha(n):
    return "%064x" % (n + 0xA0)


def berkas(n):
    return "%032x" % (n + 0xB0)


def tagihan(kon, n=1, *, akun=AKUN_A, sekarang=SEKARANG, **ganti):
    """Order sintetis ke-n beserta tagihan transfer jendela terbarunya."""
    order = buat(kon, n, akun=akun, sekarang=sekarang)
    return order, tf.buat_tagihan_transfer(kon, order["order_id"], akun, sekarang, **ganti)


def unggah(kon, order, n=1, *, akun=AKUN_A, sekarang=SESUDAH_UPLOAD, **ganti):
    """Catat satu bukti sintetis unik (n menentukan sha256/nama berkas)."""
    argumen = dict(mime=MIME, ukuran=UKURAN, sha256=sha(n), nama_tersimpan=berkas(n))
    argumen.update(ganti)
    return tf.catat_bukti(kon, order["order_id"], akun, sekarang=sekarang, **argumen)


def menunggu(kon, n=1, *, akun=AKUN_A):
    """Order + tagihan + satu bukti: status `menunggu_verifikasi`."""
    order, tag = tagihan(kon, n, akun=akun)
    unggah(kon, order, n, akun=akun)
    return order, tag

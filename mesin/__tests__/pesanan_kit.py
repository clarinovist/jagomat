"""Pembantu bersama tes pesanan: DB admin sementara dan data sintetis (tanpa jaringan)."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import pesanan  # noqa: E402
import schema_pesanan  # noqa: E402

AKUN_A = "akun_" + "a1" * 16
AKUN_B = "akun_" + "b2" * 16
MERCHANT = "M_SINTETIS"
SEKARANG = "2026-11-18T10:00:00"
SESUDAH_KEDALUWARSA = "2026-11-19T10:00:01"
TRANSAKSI = "trx-sintetis-0001"


def ord_id(n):
    return "ord_%032x" % n


def operasi(n):
    return "op-sintetis-%04d" % n


def siapkan_db(tmp_path):
    """DB admin sintetis: bootstrap standar + migrasi pesanan eksplisit."""
    path = Path(tmp_path) / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    schema_pesanan.migrasikan(path)
    return path


def buat(kon, n=1, *, akun=AKUN_A, siswa=None, sekarang=SEKARANG, **ganti):
    """Order sintetis ke-n (siswa_id default = n), prasyarat terpenuhi."""
    argumen = dict(akun_id=akun, siswa_id=n if siswa is None else siswa, cek_id=n,
                   cek_selesai=True, punya_kontak=True, sekarang=sekarang,
                   merchant=MERCHANT, order_id=ord_id(n))
    argumen.update(ganti)
    return pesanan.buat_order(kon, **argumen)


def hasil_status(order, **ganti):
    """Hasil status provider sintetis yang sah (settlement QRIS Rp49.000)."""
    data = {"order_id": order["order_id"], "transaction_status": "settlement",
            "status_code": "200", "transaction_id": TRANSAKSI,
            "gross_amount": "49000.00", "merchant_id": MERCHANT, "currency": "IDR",
            "payment_type": "qris", "fraud_status": "accept"}
    data.update(ganti)
    return {k: v for k, v in data.items() if v is not None}


def terapkan(kon, order, n=1, *, sekarang=SEKARANG, **ganti):
    return pesanan.terapkan_hasil_provider(
        kon, order["order_id"], hasil_status(order, **ganti), sekarang, operasi(n))


def hitung(kon, tabel):
    return kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0]


def jumlah_semua_pesanan(kon):
    return {t: hitung(kon, t) for t in schema_pesanan.TABEL}


def snapshot_langganan(kon):
    """Seluruh isi tabel langganan_*/paket_* sebagai tuple (untuk dibandingkan)."""
    nama = [r[0] for r in kon.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND "
        "(name GLOB 'langganan_*' OR name GLOB 'paket_*') ORDER BY name")]
    return {n: tuple(tuple(r) for r in kon.execute('SELECT * FROM "%s"' % n)) for n in nama}

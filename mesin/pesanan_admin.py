"""Catatan yatim, refund manual, dan daftar admin pesanan.

Refund hanya CATATAN manual admin (tanpa panggilan provider). Yatim menyimpan
callback `ord_` yang lolos signature tetapi tanpa order: hanya potongan id,
petunjuk status, dan hash payload (tanpa payload mentah/PII).
"""
from __future__ import annotations

import re

import pesanan_dasar as d
import pesanan_status as st
from schema_pesanan import CATATAN_REFUND

BATAS_ID_YATIM = 40
BATAS_PER_HALAMAN = 100
_ASING_ID = re.compile(r"[^A-Za-z0-9_-]")
_PANJANG_AKUN_SINGKAT = 13  # 'akun_' + 8 hex


def _id_yatim(teks):
    if type(teks) is not str or not teks:
        raise d.PesananDataTidakSah("order_id_teks tidak sah")
    return _ASING_ID.sub("?", teks[:BATAS_ID_YATIM])


def catat_yatim(kon, order_id_teks, status_hint, hash_payload, sekarang, operasi_id):
    """Catat callback `ord_` tanpa order, durable dan idempoten per `operasi_id`.

    Mengembalikan True bila baris baru, False bila replay identik;
    PesananKonflik bila `operasi_id` sama dengan isi berbeda.
    """
    d.periksa_koneksi(kon)
    d.periksa_operasi_id(operasi_id)
    isi = (_id_yatim(order_id_teks), d.status_aman(status_hint), d.periksa_hash(hash_payload))
    kini = d.waktu_baku(sekarang)
    with d.tulis(kon):
        lama = kon.execute(
            "SELECT order_id_teks,status_hint,hash_payload FROM pesanan_yatim WHERE operasi_id=?",
            (operasi_id,)).fetchone()
        if lama is not None:
            if tuple(lama) != isi:
                raise d.PesananKonflik("operasi yatim sama dengan isi berbeda")
            return False
        kon.execute("INSERT INTO pesanan_yatim(operasi_id,order_id_teks,status_hint,hash_payload,dibuat) "
                    "VALUES(?,?,?,?,?)", (operasi_id,) + isi + (kini,))
        return True


def catat_refund(kon, order_id, operasi_id, dicatat_oleh, catatan_kode, sekarang):
    """Catat refund manual untuk order ber-receipt; idempoten per `operasi_id`.

    Satu catatan refund per order. Order tanpa receipt ditolak (PesananKonflik).
    Status turunan menjadi `direfund`. Mengembalikan {status, baru}.
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    d.periksa_operasi_id(operasi_id)
    d.periksa_pelaku(dicatat_oleh)
    if catatan_kode not in CATATAN_REFUND:
        raise d.PesananDataTidakSah("catatan_kode tidak sah")
    kini = d.waktu_baku(sekarang)
    isi = (order_id, dicatat_oleh, catatan_kode)
    with d.tulis(kon):
        baru = _tulis_refund(kon, operasi_id, isi, kini)
        order = st.dict_order(st.baris_order(kon, order_id))
        return {"status": st.status_dari_db(kon, order, kini), "baru": baru}


def _tulis_refund(kon, operasi_id, isi, kini):
    lama = kon.execute("SELECT order_id,dicatat_oleh,catatan_kode FROM pesanan_refund "
                       "WHERE operasi_id=?", (operasi_id,)).fetchone()
    if lama is not None:
        if tuple(lama) != isi:
            raise d.PesananKonflik("operasi refund sama dengan isi berbeda")
        return False
    order_id = isi[0]
    if st.baris_order(kon, order_id) is None:
        raise d.PesananTidakDitemukan()
    if st.receipt_order(kon, order_id) is None:
        raise d.PesananKonflik("order belum punya receipt")
    if kon.execute("SELECT 1 FROM pesanan_refund WHERE order_id=?", (order_id,)).fetchone():
        raise d.PesananKonflik("order sudah punya catatan refund")
    kon.execute("INSERT INTO pesanan_refund(operasi_id,order_id,dicatat_oleh,catatan_kode,dibuat) "
                "VALUES(?,?,?,?,?)", (operasi_id,) + isi + (kini,))
    return True


_SQL_DAFTAR = """
SELECT o.order_id, o.akun_id, o.dibuat, o.kedaluwarsa, r.hasil AS receipt_hasil,
       r.alasan_kode,
       EXISTS(SELECT 1 FROM pesanan_refund f WHERE f.order_id=o.order_id) AS direfund,
       EXISTS(SELECT 1 FROM pesanan_pengamatan p WHERE p.order_id=o.order_id
              AND p.sumber='status' AND p.transaction_status IN (%s)) AS refund_teramati
FROM pesanan_order o LEFT JOIN pesanan_receipt r ON r.order_id=o.order_id
ORDER BY o.dibuat DESC, o.order_id DESC LIMIT ? OFFSET ?
""" % ",".join("'%s'" % s for s in d.STATUS_REFUND_PROVIDER)


def _item_admin(baris, kini):
    return {
        "order_id": baris["order_id"],
        "akun": baris["akun_id"][:_PANJANG_AKUN_SINGKAT],
        "dibuat": baris["dibuat"],
        "kedaluwarsa": baris["kedaluwarsa"],
        "alasan_kode": baris["alasan_kode"],
        "status": st.turunkan_status(
            kedaluwarsa=baris["kedaluwarsa"], sekarang=kini,
            receipt_hasil=baris["receipt_hasil"], direfund=bool(baris["direfund"]),
            refund_teramati=bool(baris["refund_teramati"])),
    }


def daftar_admin(kon, *, halaman, per_halaman, sekarang):
    """Daftar order terbaru (SELECT saja) berdata minimal untuk admin.

    Tanpa kontak, nama anak, siswa_id, cek_id, merchant, atau payload; akun
    hanya awalan id. `sekarang` dibutuhkan untuk status `kedaluwarsa`.
    """
    d.periksa_koneksi(kon)
    d.periksa_bilangan(halaman, "halaman")
    if type(per_halaman) is not int or not 1 <= per_halaman <= BATAS_PER_HALAMAN:
        raise d.PesananDataTidakSah("per_halaman tidak sah")
    kini = d.waktu_baku(sekarang)
    total = kon.execute("SELECT COUNT(*) FROM pesanan_order").fetchone()[0]
    baris = kon.execute(_SQL_DAFTAR, (per_halaman, (halaman - 1) * per_halaman)).fetchall()
    return {"items": tuple(_item_admin(b, kini) for b in baris), "total": total,
            "halaman": halaman, "per_halaman": per_halaman}

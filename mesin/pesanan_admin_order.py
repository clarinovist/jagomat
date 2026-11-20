"""Pembaca detail satu order untuk halaman admin `/admin/pesanan/order` (SELECT saja, tanpa HTTP).

Data minimal: awalan akun, status turunan, nominal tagihan, waktu, dan urutan perjalanan order. Tidak pernah
mengembalikan transaksi_id, merchant, payload, kontak, nama anak, siswa_id, nama berkas, atau sha256.
Aman pada DB tanpa namespace `transfer_*` (order QRIS tetap terbaca; nominal None).
"""
from __future__ import annotations

from typing import Optional

import pesanan_admin_transfer as pat
import pesanan_dasar as d
import pesanan_status as st
import pesanan_transfer_baca as tb

_PANJANG_AKUN_SINGKAT = 13  # 'akun_' + 8 hex
CARA_TRANSFER = "transfer"
CARA_QRIS = "qris"
LANGKAH_DIBUAT = "dibuat"
LANGKAH_BUKTI = "bukti"
LANGKAH_SETUJU = "setuju"
LANGKAH_TOLAK = "tolak"
LANGKAH_LUNAS = "lunas"
LANGKAH_PERLU_DIPERIKSA = "perlu_diperiksa"
LANGKAH_REFUND = "refund"
LANGKAH_KEDALUWARSA = "kedaluwarsa"


def _langkah(kode: str, waktu: str, jumlah: int = 0) -> dict:
    return {"kode": kode, "waktu": waktu, "jumlah": jumlah}


def _langkah_transfer(kon, order_id: str, ringkas: dict) -> list:
    """Bukti terakhir, keputusan admin, dan catatan refund transfer (kosong bila transfer belum dipasang)."""
    if not tb.terpasang(kon):
        return []
    langkah = []
    if ringkas.get("jumlah_bukti"):
        langkah.append(_langkah(LANGKAH_BUKTI, ringkas["diunggah"], ringkas["jumlah_bukti"]))
    for b in kon.execute("SELECT keputusan,dibuat FROM transfer_verifikasi WHERE order_id=? ORDER BY id",
                         (order_id,)):
        langkah.append(_langkah(LANGKAH_SETUJU if b["keputusan"] == "setuju" else LANGKAH_TOLAK, b["dibuat"]))
    refund = kon.execute("SELECT dibuat FROM transfer_refund WHERE order_id=?", (order_id,)).fetchone()
    return langkah + ([] if refund is None else [_langkah(LANGKAH_REFUND, refund["dibuat"])])


def _langkah_provider(kon, order_id: str) -> list:
    """Hasil receipt penyedia (tanpa transaksi_id) dan catatan refund jalur penyedia."""
    langkah = []
    receipt = kon.execute("SELECT hasil,dibuat FROM pesanan_receipt WHERE order_id=?", (order_id,)).fetchone()
    if receipt is not None:
        kode = LANGKAH_LUNAS if receipt["hasil"] == "lunas" else LANGKAH_PERLU_DIPERIKSA
        langkah.append(_langkah(kode, receipt["dibuat"]))
    refund = kon.execute("SELECT dibuat FROM pesanan_refund WHERE order_id=?", (order_id,)).fetchone()
    return langkah + ([] if refund is None else [_langkah(LANGKAH_REFUND, refund["dibuat"])])


def _cara_bayar(kon, order_id: str) -> str:
    if tb.terpasang(kon) and kon.execute(
            "SELECT 1 FROM transfer_tagihan WHERE order_id=?", (order_id,)).fetchone():
        return CARA_TRANSFER
    return CARA_QRIS


def detail_order(kon, order_id, sekarang) -> Optional[dict]:
    """Detail satu order (dict baru) atau None bila order tak dikenal.

    Kunci: order_id, akun (awalan), status, dibuat, kedaluwarsa (jendela bayar terbaru), cara, nominal
    (tagihan transfer atau None), jumlah_bukti, langkah (tuple dict {kode, waktu, jumlah} terurut waktu;
    hanya langkah yang datanya ada). `order_id` tak sah = PesananDataTidakSah.
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    kini = d.waktu_baku(sekarang)
    baris = st.baris_order(kon, order_id)
    if baris is None:
        return None
    status = st.status_dari_db(kon, st.dict_order(baris), kini)
    kedaluwarsa = st.jendela_terbaru(kon, order_id)["kedaluwarsa"]
    ringkas = pat.ringkasan(kon, (order_id,)).get(order_id, {})
    langkah = [_langkah(LANGKAH_DIBUAT, baris["dibuat"])]
    langkah += _langkah_transfer(kon, order_id, ringkas) + _langkah_provider(kon, order_id)
    if status == d.STATUS_KEDALUWARSA:
        langkah.append(_langkah(LANGKAH_KEDALUWARSA, kedaluwarsa))
    return {"order_id": order_id, "akun": baris["akun_id"][:_PANJANG_AKUN_SINGKAT], "status": status,
            "dibuat": baris["dibuat"], "kedaluwarsa": kedaluwarsa, "cara": _cara_bayar(kon, order_id),
            "nominal": ringkas.get("nominal"), "jumlah_bukti": ringkas.get("jumlah_bukti", 0),
            "langkah": tuple(sorted(langkah, key=lambda x: x["waktu"]))}

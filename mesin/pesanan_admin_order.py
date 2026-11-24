"""Pembaca detail satu order untuk halaman admin `/admin/pesanan/order` (SELECT saja, tanpa HTTP).

Data minimal: awalan akun, status turunan, nominal tagihan, waktu, urutan perjalanan order, penanda dua jalur
bayar, dan JUMLAH order lain dengan bukti sama (hitungan saja). Tidak pernah
mengembalikan transaksi_id, merchant, payload, kontak, nama anak, siswa_id, nama berkas, atau sha256.
Aman pada DB tanpa namespace `transfer_*` (order QRIS tetap terbaca; nominal None).
"""
from __future__ import annotations

from typing import Optional

import pesanan_admin_transfer as pat
import pesanan_dasar as d
import purna
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


def _dua_jalur(kon, order_id: str) -> bool:
    receipt = st.receipt_order(kon, order_id)
    fakta = tb.fakta(kon, order_id)
    return st.dua_jalur(None if receipt is None else receipt["hasil"], fakta["lunas"], fakta["bukti"])


def purna_ringkas(kon, order_id, sekarang) -> dict:
    """Whitelist keadaan purna satu order untuk admin (dict baru): hanya status, kode, dan waktu turunan.

    Kunci: terpasang, lunas, voucher, kode, berlaku_hingga, janji_terbit, batas_pilihan (batas terlambat), terbit,
    terlambat, dipakai, direfund, ditahan (12 kunci). Tanpa nama, kontak, akun, pelaku pencatat, atau operasi_id. Bila skema `purna_*`
    belum dimigrasikan, hasilnya netral (`terpasang` False, selebihnya kosong) supaya pemanggil tidak bisa
    bertindak atas status turunan ledger yang belum punya tabel pencatatnya.
    """
    if not purna.terpasang(kon):
        return {"terpasang": False, "lunas": False, "voucher": None, "kode": None, "berlaku_hingga": None,
                "janji_terbit": None, "batas_pilihan": None, "terbit": None, "terlambat": False,
                "dipakai": False, "direfund": False, "ditahan": False}
    k = purna.keadaan(kon, order_id, sekarang)
    return {"terpasang": True, "lunas": k.lunas, "voucher": k.voucher, "kode": k.kode,
            "berlaku_hingga": k.berlaku_hingga, "janji_terbit": k.janji_terbit, "batas_pilihan": k.batas_pilihan,
            "terbit": k.terbit, "terlambat": k.terlambat, "dipakai": k.dipakai,
            "direfund": k.direfund, "ditahan": k.ditahan}


def kartu_cek_berlaku(status) -> bool:
    """Gerbang kartu "Data cek untuk laporan" di Detail order: hanya order LUNAS (status turunan `sudah_dibayar`).

    `perlu_diperiksa`, `direfund`, dan status belum lunas tidak mendapat kartu: laporan tidak ditulis untuk
    pembayaran yang belum pasti atau sudah dikembalikan.
    """
    return status == d.STATUS_SUDAH_DIBAYAR


def kunci_cek(kon, order_id) -> Optional[tuple]:
    """(siswa_id, cek_id, akun_id) dari baris pesanan_order di ledger admin, atau None bila order tak ada.

    Dipakai SERVER untuk mencocokkan baris cek di DB belajar; tidak pernah masuk `detail_order` maupun HTML.
    """
    baris = st.baris_order(kon, order_id)
    return None if baris is None else (baris["siswa_id"], baris["cek_id"], baris["akun_id"])


def detail_order(kon, order_id, sekarang) -> Optional[dict]:
    """Detail satu order (dict baru) atau None bila order tak dikenal.

    Kunci: order_id, akun (awalan), status, dibuat, kedaluwarsa (jendela bayar terbaru), cara, nominal
    (tagihan transfer atau None), jumlah_bukti, dua_jalur (receipt penyedia lunas + jejak transfer aktif),
    bukti_dipakai_ulang (jumlah order lain dengan sha256 bukti sama), purna (lihat :func:`purna_ringkas`),
    langkah (tuple dict {kode, waktu, jumlah} terurut waktu; hanya langkah yang datanya ada). `order_id` tak sah = PesananDataTidakSah.
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
            "dua_jalur": _dua_jalur(kon, order_id), "purna": purna_ringkas(kon, order_id, kini),
            "bukti_dipakai_ulang": pat.order_lain_bukti_sama(kon, order_id),
            "langkah": tuple(sorted(langkah, key=lambda x: x["waktu"]))}

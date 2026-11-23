"""Pembaca sisi admin untuk transfer rekening (SELECT saja, tanpa HTTP, berkas, atau jaringan).

Dipakai halaman admin: ringkasan per baris daftar pesanan, detail verifikasi satu order, dan
metadata satu bukti untuk pratinjau. Tidak pernah mengembalikan nama berkas tersimpan lewat
`detail`/`ringkasan` (hanya `ambil_bukti` untuk rute pratinjau), sha256, atau id akun penuh.
Aman pada DB tanpa namespace `transfer_*` (hasil kosong / None).
"""
from __future__ import annotations

from typing import Optional

import pesanan_dasar as d
import pesanan_status as st
import pesanan_transfer_baca as tb

_PANJANG_AKUN_SINGKAT = 13  # 'akun_' + 8 hex
KEADAAN_MENUNGGU = "menunggu"
KEADAAN_DIPUTUSKAN = "diputuskan"
KEADAAN_DIHAPUS = "dihapus"

_SQL_NOMINAL = (
    "SELECT t.order_id, t.nominal_transfer FROM transfer_tagihan t WHERE t.order_id IN (%s) "
    "AND t.urutan=(SELECT MAX(j.urutan) FROM pesanan_jendela j WHERE j.order_id=t.order_id)")
_SQL_BUKTI = ("SELECT order_id, COUNT(*) AS jumlah, MAX(diunggah) AS terakhir FROM transfer_bukti "
              "WHERE order_id IN (%s) GROUP BY order_id")


def ringkasan(kon, order_ids) -> dict:
    """{order_id: {nominal, jumlah_bukti, diunggah}} untuk id yang diminta; {} bila transfer belum dipasang.

    `nominal` = tagihan jendela bayar terbaru (49.000 + kode unik) atau None; `diunggah` = waktu
    bukti terakhir atau None.
    """
    d.periksa_koneksi(kon)
    ids = tuple(order_ids)
    if not ids or not tb.terpasang(kon):
        return {}
    marka = ",".join("?" * len(ids))
    nominal = {b[0]: b[1] for b in kon.execute(_SQL_NOMINAL % marka, ids)}
    bukti = {b["order_id"]: (b["jumlah"], b["terakhir"]) for b in kon.execute(_SQL_BUKTI % marka, ids)}
    return {i: {"nominal": nominal.get(i), "jumlah_bukti": bukti.get(i, (0, None))[0],
                "diunggah": bukti.get(i, (0, None))[1]} for i in ids}


def order_lain_bukti_sama(kon, order_id) -> int:
    """Jumlah order LAIN yang punya bukti dengan sha256 sama dengan salah satu bukti order ini.

    Hanya hitungan (tanpa id order/akun lain atau sha256). 0 bila transfer belum dipasang.
    """
    d.periksa_koneksi(kon)
    if not tb.terpasang(kon):
        return 0
    return kon.execute(
        "SELECT COUNT(DISTINCT b2.order_id) FROM transfer_bukti b1 JOIN transfer_bukti b2 "
        "ON b2.sha256=b1.sha256 AND b2.order_id<>b1.order_id WHERE b1.order_id=?", (order_id,)).fetchone()[0]


def _keadaan_bukti(bukti_id, diputuskan_hingga, dihapus) -> str:
    if bukti_id in dihapus:
        return KEADAAN_DIHAPUS
    return KEADAAN_DIPUTUSKAN if bukti_id <= diputuskan_hingga else KEADAAN_MENUNGGU


def _bukti_order(kon, order_id) -> tuple:
    hingga = kon.execute("SELECT COALESCE(MAX(bukti_hingga_id),0) FROM transfer_verifikasi "
                         "WHERE order_id=?", (order_id,)).fetchone()[0]
    dihapus = {b[0] for b in kon.execute(
        "SELECT h.bukti_id FROM transfer_bukti_hapus h JOIN transfer_bukti b ON b.id=h.bukti_id "
        "WHERE b.order_id=?", (order_id,))}
    baris = kon.execute("SELECT id,urutan,mime,ukuran,diunggah FROM transfer_bukti WHERE order_id=? "
                        "ORDER BY id", (order_id,)).fetchall()
    return tuple({"id": b["id"], "urutan": b["urutan"], "mime": b["mime"], "ukuran": b["ukuran"],
                  "diunggah": b["diunggah"],
                  "keadaan": _keadaan_bukti(b["id"], hingga, dihapus)} for b in baris)


def _riwayat(kon, order_id) -> tuple:
    baris = kon.execute("SELECT keputusan,alasan,dibuat FROM transfer_verifikasi WHERE order_id=? "
                        "ORDER BY id", (order_id,))
    return tuple({"keputusan": b["keputusan"], "alasan": b["alasan"], "dibuat": b["dibuat"]} for b in baris)


def detail(kon, order_id, sekarang) -> Optional[dict]:
    """Detail verifikasi satu order (dict baru) atau None bila order tak dikenal / transfer belum dipasang.

    Kunci: order_id, akun (awalan), status, dibuat, nominal, bukti (tuple dict tanpa berkas/sha256),
    keputusan (riwayat), bukti_terakhir_id (None bila belum ada bukti).
    """
    d.periksa_koneksi(kon)
    d.periksa_order_id(order_id)
    kini = d.waktu_baku(sekarang)
    baris = st.baris_order(kon, order_id)
    if baris is None or not tb.terpasang(kon):
        return None
    bukti = _bukti_order(kon, order_id)
    return {"order_id": order_id, "akun": baris["akun_id"][:_PANJANG_AKUN_SINGKAT],
            "status": st.status_dari_db(kon, st.dict_order(baris), kini), "dibuat": baris["dibuat"],
            "nominal": ringkasan(kon, (order_id,))[order_id]["nominal"],
            "bukti": bukti, "keputusan": _riwayat(kon, order_id),
            "bukti_terakhir_id": bukti[-1]["id"] if bukti else None}


def ambil_bukti(kon, bukti_id) -> Optional[dict]:
    """Metadata satu bukti untuk pratinjau {id, order_id, berkas, mime, dihapus}; None bila tak sah/tak ada."""
    d.periksa_koneksi(kon)
    if type(bukti_id) is not int or bukti_id < 1 or not tb.terpasang(kon):
        return None
    baris = kon.execute(
        "SELECT b.id,b.order_id,b.berkas,b.mime,"
        "EXISTS(SELECT 1 FROM transfer_bukti_hapus h WHERE h.bukti_id=b.id) AS dihapus "
        "FROM transfer_bukti b WHERE b.id=?", (bukti_id,)).fetchone()
    if baris is None:
        return None
    return {"id": baris["id"], "order_id": baris["order_id"], "berkas": baris["berkas"],
            "mime": baris["mime"], "dihapus": bool(baris["dihapus"])}

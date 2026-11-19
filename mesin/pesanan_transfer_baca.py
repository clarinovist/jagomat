"""Fakta transfer rekening untuk status turunan (SELECT saja).

Dipakai `pesanan_status`/`pesanan_jendela`/`pesanan_admin`, jadi harus aman pada DB
yang belum punya namespace `transfer_*` (v1 pesanan): fragmen SQL mundur ke konstanta
(`0`/`NULL`) dan `fakta` mengembalikan nilai netral. Tidak ada tulis, tidak ada
impor selain `pesanan_dasar`.

Fakta (semuanya diturunkan, tidak disimpan):

* `lunas`    ada baris `transfer_lunas` (admin menyetujui);
* `direfund` ada `transfer_refund`;
* `bukti`    `'menunggu'` bila ada bukti yang belum diputuskan (id di atas
  `bukti_hingga_id` terbesar), `'ditolak'` bila keputusan tolak berada di jendela
  bayar terbaru, selain itu None.
"""
from __future__ import annotations

BUKTI_MENUNGGU = "menunggu"
BUKTI_DITOLAK = "ditolak"

# Fragmen untuk order beralias `o` (pesanan_order).
_SQL_ADA = {
    "lunas": "EXISTS(SELECT 1 FROM transfer_lunas tl WHERE tl.order_id=o.order_id)",
    "direfund": "EXISTS(SELECT 1 FROM transfer_refund tr WHERE tr.order_id=o.order_id)",
    "menunggu": (
        "EXISTS(SELECT 1 FROM transfer_bukti tb WHERE tb.order_id=o.order_id AND tb.id>"
        "COALESCE((SELECT MAX(tv.bukti_hingga_id) FROM transfer_verifikasi tv "
        "WHERE tv.order_id=o.order_id),0))"),
    "ditolak": (
        "EXISTS(SELECT 1 FROM transfer_verifikasi tv WHERE tv.order_id=o.order_id "
        "AND tv.keputusan='tolak' AND tv.urutan="
        "(SELECT MAX(tj.urutan) FROM pesanan_jendela tj WHERE tj.order_id=o.order_id))"),
}
_SQL_NETRAL = {"lunas": "0", "direfund": "0", "menunggu": "0", "bukti": "NULL"}


def terpasang(kon):
    """True bila namespace `transfer_*` sudah dimigrasikan (cek ringan, bukan validasi)."""
    return kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='transfer_tagihan'"
                       ).fetchone() is not None


def sql_fakta(kon):
    """Fragmen SQL boolean/teks untuk order beralias `o`: lunas, direfund, menunggu, bukti."""
    if not terpasang(kon):
        return dict(_SQL_NETRAL)
    bukti = "CASE WHEN %s THEN '%s' WHEN %s THEN '%s' END" % (
        _SQL_ADA["menunggu"], BUKTI_MENUNGGU, _SQL_ADA["ditolak"], BUKTI_DITOLAK)
    return {"lunas": _SQL_ADA["lunas"], "direfund": _SQL_ADA["direfund"],
            "menunggu": _SQL_ADA["menunggu"], "bukti": bukti}


def fakta(kon, order_id):
    """Fakta transfer satu order: {lunas: bool, direfund: bool, bukti: None|'menunggu'|'ditolak'}."""
    netral = {"lunas": False, "direfund": False, "bukti": None}
    if not terpasang(kon):
        return netral
    sql = sql_fakta(kon)
    baris = kon.execute(
        "SELECT %s AS lunas, %s AS direfund, %s AS bukti FROM pesanan_order o WHERE o.order_id=?"
        % (sql["lunas"], sql["direfund"], sql["bukti"]), (order_id,)).fetchone()
    if baris is None:
        return netral
    return {"lunas": bool(baris["lunas"]), "direfund": bool(baris["direfund"]),
            "bukti": baris["bukti"]}

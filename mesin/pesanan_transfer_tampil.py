"""Pembaca tampilan transfer rekening sisi guru (SELECT saja, tanpa HTTP/berkas/jaringan).

Satu potret ledger untuk halaman `/pesanan`: status turunan, nominal tagihan (49.000 + kode
unik) yang dipegang, jendela bayar terbaru, alasan penolakan admin, jumlah bukti, dan
aksi yang boleh (buat tagihan / unggah). Aturan ini mencerminkan `pesanan_transfer`
(domain yang tetap penegak akhir); halaman hanya menyembunyikan tombol yang pasti ditolak.
Kepemilikan lewat `akun_id`: order bukan milik akun -> PesananTidakDitemukan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pesanan_dasar as d
import pesanan_jendela as jd
import pesanan_status as st
import pesanan_transfer as tf
from schema_transfer import MAKS_BUKTI

_STATUS_BOLEH_UNGGAH = (d.STATUS_BELUM_BAYAR, d.STATUS_DITOLAK)
_STATUS_TERIMA_BUKTI = (d.STATUS_BELUM_BAYAR, d.STATUS_DITOLAK, d.STATUS_MENUNGGU_VERIFIKASI)
HAMBATAN_TAGIHAN = "tagihan"      # tagihan transfer belum dibuat
HAMBATAN_STATUS = "status"        # status pesanan tidak menerima bukti (lunas, kedaluwarsa, ...)
HAMBATAN_JENDELA = "jendela"      # jendela bayar sudah lewat
HAMBATAN_BATAS = "batas"          # sudah MAKS_BUKTI bukti


@dataclass(frozen=True)
class TampilanTransfer:
    status: str
    nominal: Optional[int]
    kedaluwarsa: str
    alasan_tolak: Optional[str]
    jumlah_bukti: int
    boleh_tagihan: bool
    boleh_unggah: bool
    boleh_ulang: bool = False


def _jumlah_bukti(kon, order_id) -> int:
    return kon.execute("SELECT COUNT(*) FROM transfer_bukti WHERE order_id=?", (order_id,)).fetchone()[0]


def _alasan_tolak(kon, order_id, urutan) -> Optional[str]:
    baris = kon.execute(
        "SELECT alasan FROM transfer_verifikasi WHERE order_id=? AND urutan=? AND keputusan='tolak' "
        "ORDER BY id DESC LIMIT 1", (order_id, urutan)).fetchone()
    return None if baris is None else baris["alasan"]


def _boleh_ulang(kon, order_id, status, jendela, kini) -> bool:
    """Jendela habis tanpa bukti menunggu/lunas, belum di batas jendela, dan kuota masih ada."""
    return (status == d.STATUS_KEDALUWARSA and jendela["urutan"] < jd.MAKS_JENDELA
            and jd.jumlah_aktif(kon, kini, kecuali=order_id) < d.KUOTA_ORDER)


def baca(kon, order_id, akun_id, sekarang) -> TampilanTransfer:
    """Tampilan transfer satu order milik `akun_id` pada waktu `sekarang`."""
    d.periksa_koneksi(kon)
    kini = d.waktu_baku(sekarang)
    order = st.ambil_order(kon, order_id, akun_id)
    jendela = st.jendela_terbaru(kon, order_id)
    status = st.status_dari_db(kon, order, kini)
    tagihan = tf.ambil_tagihan(kon, order_id, akun_id)
    jumlah = _jumlah_bukti(kon, order_id)
    jendela_terbuka = kini < jendela["kedaluwarsa"]
    return TampilanTransfer(
        status=status,
        nominal=None if tagihan is None else tagihan["nominal_transfer"],
        kedaluwarsa=jendela["kedaluwarsa"],
        alasan_tolak=_alasan_tolak(kon, order_id, jendela["urutan"]) if status == d.STATUS_DITOLAK else None,
        jumlah_bukti=jumlah,
        boleh_tagihan=tagihan is None and status == d.STATUS_BELUM_BAYAR,
        boleh_unggah=(tagihan is not None and status in _STATUS_BOLEH_UNGGAH
                      and jendela_terbuka and jumlah < MAKS_BUKTI),
        boleh_ulang=_boleh_ulang(kon, order_id, status, jendela, kini))


def hambatan_unggah(tampilan: TampilanTransfer, sekarang) -> Optional[str]:
    """Alasan pasti-ditolak untuk unggah bukti baru (pesan ramah); None bila boleh dicoba.

    Mengikuti syarat `pesanan_transfer.catat_bukti`; domain tetap penegak akhir (balapan
    antara pembacaan ini dan penulisan tetap ditolak di sana).
    """
    if tampilan.nominal is None:
        return HAMBATAN_TAGIHAN
    if tampilan.status not in _STATUS_TERIMA_BUKTI:
        return HAMBATAN_STATUS
    if d.waktu_baku(sekarang) >= tampilan.kedaluwarsa:
        return HAMBATAN_JENDELA
    if tampilan.jumlah_bukti >= MAKS_BUKTI:
        return HAMBATAN_BATAS
    return None

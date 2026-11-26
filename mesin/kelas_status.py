"""Pembacaan keadaan order kelas (SELECT saja): fakta, status turunan, order terbuka, dan baris tagihan.

Status TIDAK disimpan; selalu diturunkan dari fakta dan waktu:

* `aktif`        ada keputusan setuju (akses ada di `kelas_akses`);
* `menunggu`     ada bukti belum diputuskan; TIDAK kedaluwarsa, admin tetap dapat memutuskan;
* `kedaluwarsa`  jendela bayar (24 jam) lewat tanpa bukti menunggu; pembeli boleh membuat tagihan baru;
* `dibatalkan`   pembeli membatalkan tagihan yang belum ada bukti selama jendela masih terbuka (lihat `kelas_catatan`);
* `ditolak`      keputusan terakhir menolak dan jendela masih terbuka (boleh unggah ulang);
* `belum_bayar`  jendela terbuka, belum ada bukti.

Urutan pengecekan persis seperti daftar itu. Order "terbuka" = belum_bayar, menunggu, atau ditolak: tagihan yang
masih memegang nominal (kode unik) dan, bila memotong deposit, memegang deposit itu. Tagihan dibatalkan TIDAK terbuka
(`STATUS_DIBATALKAN` di luar `STATUS_TERBUKA`), tetapi kode unik dan total-nya tetap dipegang sampai jendela lewat
(`nominal_dipegang` tidak diubah), agar pemulihan tidak berbenturan dengan tagihan lain yang memakai total yang sama.
Semua kueri di sini memfilter `akun_id` bila diberi akun, sehingga order milik akun lain tidak pernah terbaca
(sama seperti tidak ada).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

import kelas_catatan as cat
import kelas_dasar as k
import paket_belajar_katalog as katalog
import schema_kelas as sk

KOLOM_ORDER = "id,akun_id,siswa_id,paket,dibuat,kedaluwarsa"
KOLOM_TAGIHAN = ("harga_dasar,potongan_deposit,potongan_diskon,deposit_order_id,nominal,kode_unik,"
                 "total_transfer,dibuat")


@dataclass(frozen=True)
class Fakta:
    lunas: bool
    putusan_terakhir: Optional[str]
    alasan: Optional[str]
    bukti_terakhir_id: Optional[int]
    jumlah_bukti: int
    menunggu: bool
    dibatalkan: bool = False


def fakta_order(kon, order_id: str) -> Fakta:
    lunas = kon.execute("SELECT 1 FROM kelas_verifikasi WHERE order_id=? AND keputusan='setuju'",
                        (order_id,)).fetchone() is not None
    putusan = kon.execute("SELECT keputusan,alasan,bukti_hingga_id FROM kelas_verifikasi WHERE order_id=? "
                          "ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    bukti = kon.execute("SELECT MAX(id),COUNT(*) FROM kelas_bukti WHERE order_id=?", (order_id,)).fetchone()
    terakhir, jumlah = bukti[0], bukti[1]
    menunggu = terakhir is not None and (putusan is None or terakhir > putusan["bukti_hingga_id"])
    return Fakta(lunas, None if putusan is None else putusan["keputusan"],
                 None if putusan is None else putusan["alasan"], terakhir, jumlah, menunggu,
                 cat.dibatalkan(kon, order_id))


def status_dari(order, fakta: Fakta, kini: str) -> str:
    if fakta.lunas:
        return k.STATUS_AKTIF
    if fakta.menunggu:
        return k.STATUS_MENUNGGU
    if kini >= order["kedaluwarsa"]:
        return k.STATUS_KEDALUWARSA
    if fakta.dibatalkan:
        return k.STATUS_DIBATALKAN
    return k.STATUS_DITOLAK if fakta.putusan_terakhir == k.KEPUTUSAN_TOLAK else k.STATUS_BELUM_BAYAR


def baris_order(kon, order_id: str):
    return kon.execute("SELECT %s FROM kelas_order WHERE id=?" % KOLOM_ORDER, (order_id,)).fetchone()


def baris_order_akun(kon, akun_id: str, order_id: str):
    """Order milik `akun_id`, atau None (id tak ada dan order milik akun lain tak terbedakan)."""
    return kon.execute("SELECT %s FROM kelas_order WHERE id=? AND akun_id=?" % KOLOM_ORDER,
                       (order_id, akun_id)).fetchone()


def baris_tagihan(kon, order_id: str):
    return kon.execute("SELECT %s FROM kelas_tagihan WHERE order_id=?" % KOLOM_TAGIHAN, (order_id,)).fetchone()


def rincian_dari_baris(kode_paket: str, tagihan) -> katalog.Rincian:
    return katalog.Rincian(kode_paket, tagihan["harga_dasar"], tagihan["potongan_deposit"],
                           tagihan["potongan_diskon"], tagihan["nominal"])


def order_terbuka_siswa(kon, akun_id: str, siswa_id: int, kini: str) -> Iterator[Tuple[object, Fakta, str]]:
    """(baris order, fakta, status) semua order milik akun untuk anak ini yang masih terbuka, terbaru dulu.

    "Terbaru" = urutan sisip (rowid, ledger tidak pernah dihapus), bukan `dibuat`: jam server yang melompat mundur tidak boleh membuat
    tagihan hasil ganti paket kalah dari tagihan lama.
    """
    for order in kon.execute("SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? "
                             "ORDER BY rowid DESC" % KOLOM_ORDER, (akun_id, siswa_id)).fetchall():
        fakta = fakta_order(kon, order["id"])
        status = status_dari(order, fakta, kini)
        if status in k.STATUS_TERBUKA:
            yield order, fakta, status


def order_terbuka(kon, akun_id: str, siswa_id: int, kode_paket: str, kini: str):
    """(baris order, fakta, status) terbuka milik akun untuk (anak, paket), atau None."""
    for ada in order_terbuka_siswa(kon, akun_id, siswa_id, kini):
        if ada[0]["paket"] == kode_paket:
            return ada
    return None


def order_dibatalkan(kon, akun_id: str, siswa_id: int, kode_paket: str, kini: str):
    """(baris order, fakta, status) tagihan DIBATALKAN milik akun untuk (anak, paket) yang jendelanya belum lewat, atau None.

    Terbaru dulu (urutan sisip). Jendela yang sudah lewat tampak `kedaluwarsa`, jadi tidak ikut di sini.
    """
    kandidat = kon.execute("SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? AND paket=? "
                           "ORDER BY rowid DESC" % KOLOM_ORDER, (akun_id, siswa_id, kode_paket)).fetchall()
    for order in kandidat:
        fakta = fakta_order(kon, order["id"])
        status = status_dari(order, fakta, kini)
        if status == k.STATUS_DIBATALKAN:
            return order, fakta, status
    return None


def akun_lain_punya_order(kon, akun_id: str, siswa_id: int) -> bool:
    """True bila anak ini sudah punya order kelas atas nama akun LAIN (dipakai untuk menolak sebagai 'tidak ada')."""
    return kon.execute("SELECT 1 FROM kelas_order WHERE siswa_id=? AND akun_id<>? LIMIT 1",
                       (siswa_id, akun_id)).fetchone() is not None


def nominal_dipegang(kon, kini: str) -> set:
    """Total transfer yang masih dipegang: tagihan terbuka, atau lunas dalam `HARI_TAHAN_KODE_LUNAS` hari."""
    baris = kon.execute(
        "SELECT t.total_transfer FROM kelas_tagihan t JOIN kelas_order o ON o.id=t.order_id "
        "WHERE (NOT %s AND (o.kedaluwarsa>? OR %s)) OR EXISTS(SELECT 1 FROM kelas_verifikasi v "
        "WHERE v.order_id=o.id AND v.keputusan='setuju' AND v.dibuat>?)"
        % (sk.SQL_SUDAH_LUNAS, sk.SQL_BELUM_DIPUTUSKAN),
        (kini, k.batas_hari_lalu(kini, k.HARI_TAHAN_KODE_LUNAS)))
    return {b[0] for b in baris}

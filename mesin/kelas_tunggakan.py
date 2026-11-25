"""Tunggakan Paket Belajar: anak yang paket bulanannya sudah habis dan belum diperpanjang (baca-saja, tanpa tulis).

Notifikasi untuk ADMIN lewat antrean "Perlu ditangani", bukan untuk orang tua. Satu item per (anak, paket). Hari
dihitung dari akses TERAKHIR paket itu (MAX `berakhir`), dibulatkan ke bawah. Order terbuka (belum bayar, menunggu,
atau ditolak) dari akun mana pun menahan tunggakan; statusnya diturunkan lewat `kelas_status` supaya aturan
kedaluwarsa tidak diduplikasi. Paket yang berakhir lebih awal daripada paket lain milik anak yang sama tidak ikut
dihitung (anak yang pindah paket bukan tunggakan). Akun pembeli tidak dibaca, hanya `siswa_id`. Lewat `HARI_TUNGGAKAN_MAKS` dianggap
berhenti dan tidak muncul lagi, supaya antrean tidak menumpuk selamanya.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

import kelas_dasar as k
import kelas_status as ks
import paket_belajar_katalog as katalog

HARI_TUNGGAKAN_MIN = 30
HARI_TUNGGAKAN_PENTING = 60
HARI_TUNGGAKAN_MAKS = 120
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
SQL_AKSES_TERAKHIR = ("SELECT a.siswa_id AS siswa_id, o.paket AS paket, MAX(a.berakhir) AS berakhir "
                      "FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
                      "GROUP BY a.siswa_id, o.paket")


@dataclass(frozen=True)
class Tunggakan:
    siswa_id: int
    kode_paket: str
    nama_paket: str
    berakhir: str
    hari_lewat: int


def _waktu(baku: str) -> datetime:
    return datetime.strptime(baku, FORMAT_WAKTU)


def _hari_lewat(berakhir: str, kini: str) -> int:
    """Hari penuh sejak `berakhir`; selisih negatif (belum berakhir) dibulatkan ke bawah oleh `timedelta.days`."""
    return (_waktu(kini) - _waktu(berakhir)).days


def _ada_order_terbuka(kon, siswa_id: int, kode_paket: str, kini: str) -> bool:
    """True bila ada order terbuka untuk (anak, paket) dari akun mana pun. Akun tidak diperlukan untuk ini."""
    for order in kon.execute("SELECT %s FROM kelas_order WHERE siswa_id=? AND paket=?" % ks.KOLOM_ORDER,
                             (siswa_id, kode_paket)).fetchall():
        fakta = ks.fakta_order(kon, order["id"])
        if ks.status_dari(order, fakta, kini) in k.STATUS_TERBUKA:
            return True
    return False


def _tunggakan_dari_baris(kon, baris, kini: str):
    """Tunggakan untuk satu (anak, paket) bila dalam jendela hari dan tidak ada order terbuka; selain itu None."""
    hari = _hari_lewat(baris["berakhir"], kini)
    if not HARI_TUNGGAKAN_MIN <= hari <= HARI_TUNGGAKAN_MAKS:
        return None
    if _ada_order_terbuka(kon, baris["siswa_id"], baris["paket"], kini):
        return None
    return Tunggakan(baris["siswa_id"], baris["paket"], katalog.ambil(baris["paket"]).nama,
                     baris["berakhir"], hari)


def daftar_tunggakan(kon, sekarang: str) -> Tuple[Tunggakan, ...]:
    """Tunggakan paket kelas per (anak, paket), hari lalu terbesar dulu, lalu anak, lalu kode paket.

    `sekarang` adalah waktu baku UTC naif (atau str ISO yang dinormalkan `kelas_dasar.ke_baku`).
    """
    kini = k.ke_baku(sekarang)
    semua = kon.execute(SQL_AKSES_TERAKHIR).fetchall()
    akhir_anak = {}
    for baris in semua:
        akhir_anak[baris["siswa_id"]] = max(akhir_anak.get(baris["siswa_id"], ""), baris["berakhir"])
    hasil = []
    for baris in semua:
        if baris["berakhir"] < akhir_anak[baris["siswa_id"]]:
            continue  # anak sudah punya akses paket lain yang lebih akhir (mis. pindah Mini/Private): bukan tunggakan
        tunggakan = _tunggakan_dari_baris(kon, baris, kini)
        if tunggakan is not None:
            hasil.append(tunggakan)
    return tuple(sorted(hasil, key=lambda t: (-t.hari_lewat, t.siswa_id, t.kode_paket)))

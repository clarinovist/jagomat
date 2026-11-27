"""Riwayat kehadiran dan jurnal pertemuan untuk halaman orang tua: pembaca BACA-SAJA, per anak.

Penempatan dicari seperti kartu "Sesi berikutnya" anak (`jadwal_anak_baca`): order AKTIF terbaru milik (akun, anak)
yang punya penempatan. Pertemuan yang diambil: kelompok Mini untuk penempatan kelompok, atau pertemuan order untuk
Private. Hanya yang tidak dibatalkan, sudah mulai (`mulai <= kini`), dimulai pada atau sesudah penempatan anak
(`mulai >= dibuat`), dan paling baru sebanyak `batas`.

Keadaan catatan dibaca lewat `guru_pertemuan_dasar.terkini`, lalu HANYA status order anak sendiri yang keluar: status
anggota Mini lain tidak pernah masuk hasil. Hasil hanya berisi `mulai`, `hadir`, dan `topik` (label). Tidak ada id,
kunci, atau pencatat. Modul ini hanya SELECT pada koneksi jadwal dan tidak membuat berkas catatan.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import guru_pertemuan_aturan as aturan
import guru_pertemuan_dasar as catatan
import kelas_dasar as kd
import kelas_status as ks
import pesanan_dasar as d

_log = logging.getLogger(__name__)

BATAS_BAWAAN = 8
_SQL_ORDER_ANAK = ("SELECT %s FROM kelas_order WHERE akun_id=? AND siswa_id=? ORDER BY dibuat DESC,id DESC"
                   % ks.KOLOM_ORDER)
_SQL_PENEMPATAN_ORDER = "SELECT kelompok_id, dibuat FROM jadwal_penempatan WHERE order_id=?"
# `mulai >= dibuat` = `anggota_masuk_form` (penempatan sudah ada pada saat pertemuan mulai). Saringan di SQL, sebelum
# LIMIT, supaya `batas` terisi pertemuan yang sah.
_SQL_BERLANGSUNG_KELOMPOK = ("SELECT ke, mulai FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0 "
                             "AND mulai<=? AND mulai>=? ORDER BY mulai DESC,id DESC LIMIT ?")
_SQL_BERLANGSUNG_ORDER = ("SELECT ke, mulai FROM jadwal_pertemuan WHERE order_id=? AND dibatalkan=0 "
                          "AND mulai<=? AND mulai>=? ORDER BY mulai DESC,id DESC LIMIT ?")


def _periksa_batas(batas) -> None:
    if type(batas) is not int or batas < 1:
        raise ValueError("Batas riwayat harus bilangan bulat positif.")


def _penempatan_dari_baris(order_id: str, baris) -> dict:
    """Penempatan satu order: `id_awal` = kelompok (Mini) atau order (Private), dipakai untuk membentuk kunci."""
    kelompok_id = baris["kelompok_id"]
    return {"order_id": order_id, "kelompok_id": kelompok_id, "dibuat": baris["dibuat"],
            "id_awal": order_id if kelompok_id is None else kelompok_id}


def _penempatan_order(kon, order_id: str) -> Optional[dict]:
    baris = kon.execute(_SQL_PENEMPATAN_ORDER, (order_id,)).fetchone()
    return None if baris is None else _penempatan_dari_baris(order_id, baris)


def _penempatan_aktif(kon, akun_id: str, siswa_id: int, kini: str) -> Optional[dict]:
    """Penempatan order AKTIF terbaru milik (akun, anak). Order aktif tanpa penempatan dilewati."""
    for order in kon.execute(_SQL_ORDER_ANAK, (akun_id, siswa_id)).fetchall():
        if ks.status_dari(order, ks.fakta_order(kon, order["id"]), kini) != kd.STATUS_AKTIF:
            continue
        penempatan = _penempatan_order(kon, order["id"])
        if penempatan is not None:
            return penempatan
    return None


def _pertemuan_berlangsung(kon, penempatan: dict, kini: str, batas: int) -> list:
    """Pertemuan yang sudah mulai sejak anak masuk, tidak dibatalkan, terbaru dulu, paling banyak `batas`."""
    dibuat = penempatan["dibuat"]
    if penempatan["kelompok_id"] is not None:
        return kon.execute(_SQL_BERLANGSUNG_KELOMPOK,
                           (penempatan["kelompok_id"], kini, dibuat, batas)).fetchall()
    return kon.execute(_SQL_BERLANGSUNG_ORDER, (penempatan["order_id"], kini, dibuat, batas)).fetchall()


def _keadaan_anak(id_awal: str, ke: int, mulai: str, order_id: str,
                  path_catatan) -> Tuple[Optional[str], Optional[str]]:
    """(status anak, topik berlabel) untuk satu pertemuan. (None, None) bila catatan tak bisa dibaca.

    Hanya `order_id` anak yang diambil dari keadaan; anggota lain tidak pernah keluar dari fungsi ini.
    """
    try:
        keadaan = catatan.terkini(aturan.kunci_pertemuan(id_awal, ke), mulai, path=path_catatan)
        topik = keadaan["topik"]
        label = None if topik is None else aturan.label_topik(topik)
        return keadaan["hadir"].get(order_id), label
    except (catatan.GalatCatatan, ValueError):
        _log.warning("catatan pertemuan tidak terbaca untuk riwayat orang tua; item ditampilkan kosong")
        return None, None


def _item_riwayat(baris, penempatan: dict, path_catatan) -> dict:
    hadir, topik = _keadaan_anak(penempatan["id_awal"], baris["ke"], baris["mulai"], penempatan["order_id"],
                                 path_catatan)
    return {"mulai": baris["mulai"], "hadir": hadir, "topik": topik}


def riwayat_untuk_anak(kon_jadwal, akun_id: str, siswa_id: int, kini, *, batas: int = BATAS_BAWAAN,
                       path_catatan=None) -> List[dict]:
    """Riwayat `batas` pertemuan terakhir yang sudah mulai untuk satu anak, terbaru dulu.

    Tiap item: `mulai` (waktu baku dari DB), `hadir` (status order anak sendiri, atau None bila belum tercatat),
    dan `topik` (label, atau None bila tidak ada jurnal). Pertemuan yang mulai sebelum penempatan anak tidak masuk
    (aturan `anggota_masuk_form`). Tanpa penempatan aktif hasilnya []. `akun_id` dan `siswa_id` harus dari sesi
    orang tua; `kini` disuntik pemanggil. Galat DB jadwal dibiarkan naik.
    """
    d.periksa_koneksi(kon_jadwal)
    d.periksa_akun_id(akun_id)
    kd.periksa_siswa_id(siswa_id)
    _periksa_batas(batas)
    waktu = kd.ke_baku(kini)
    penempatan = _penempatan_aktif(kon_jadwal, akun_id, siswa_id, waktu)
    if penempatan is None:
        return []
    baris = _pertemuan_berlangsung(kon_jadwal, penempatan, waktu, batas)
    return [_item_riwayat(b, penempatan, path_catatan) for b in baris]

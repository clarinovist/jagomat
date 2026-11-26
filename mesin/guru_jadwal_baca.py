"""Pembacaan jadwal untuk guru (SELECT saja): pertemuan mendatang, kelas Mini milik guru, dan detailnya.

Kepemilikan DI SQL: Mini lewat `jadwal_kelompok.guru_id`, Private lewat `jadwal_penempatan.guru_id`. Guru yang
dipakai selalu disuntik pemanggil dari sesi, tidak pernah dari URL atau form. Hanya order berstatus aktif (lewat
`kelas_status`, sama dengan kartu orang tua) yang tampil sebagai anggota atau pertemuan Private. Modul ini tidak
menulis dan tidak membuat berkas; koneksi dibuka pemanggil (`jadwal_store.buka`, mode ro).
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

import jadwal_dasar as jd
import kelas_dasar as dasar
import kelas_status as ks

PLACEHOLDER_NAMA = "Anak"


def _id_kelompok_sah(kelompok_id) -> bool:
    try:
        jd.periksa_kelompok_id(kelompok_id)
    except jd.JadwalTidakSah:
        return False
    return True


def _order_aktif_ids(kon, order_ids: Iterable[str], kini: str) -> Set[str]:
    """Himpunan id order yang statusnya aktif pada `kini` (diturunkan dari fakta, tidak disimpan)."""
    aktif = set()
    for order_id in set(order_ids):
        order = ks.baris_order(kon, order_id)
        if order is not None and ks.status_dari(order, ks.fakta_order(kon, order_id), kini) == dasar.STATUS_AKTIF:
            aktif.add(order_id)
    return aktif


def _anggota_aktif(kon, kelompok_id: str, kini: str) -> List[int]:
    """siswa_id anggota kelompok yang ordernya aktif, urut id order."""
    baris = kon.execute(
        "SELECT p.order_id, o.siswa_id FROM jadwal_penempatan p JOIN kelas_order o ON o.id=p.order_id "
        "WHERE p.kelompok_id=? ORDER BY p.order_id", (kelompok_id,)).fetchall()
    aktif = _order_aktif_ids(kon, (b["order_id"] for b in baris), kini)
    return [b["siswa_id"] for b in baris if b["order_id"] in aktif]


def _pertemuan_berikut(kon, kelompok_id: str, kini: str) -> Optional[str]:
    return kon.execute(
        "SELECT MIN(mulai) FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0 AND mulai>=?",
        (kelompok_id, kini)).fetchone()[0]


def _pertemuan_dict(jenis: str, baris, **identitas) -> dict:
    return {"jenis": jenis, **identitas, "ke": int(baris["ke"]), "mulai": baris["mulai"],
            "menit": int(baris["menit"]), "dibatalkan": bool(baris["dibatalkan"])}


def _pertemuan_mini(kon, guru_id: str, kini: str) -> List[dict]:
    baris = kon.execute(
        "SELECT k.id AS kelompok_id, k.nama AS nama_kelompok, s.ke, s.mulai, s.menit, s.dibatalkan "
        "FROM jadwal_pertemuan s JOIN jadwal_kelompok k ON k.id=s.kelompok_id "
        "WHERE k.guru_id=? AND s.mulai>=?", (guru_id, kini)).fetchall()
    return [_pertemuan_dict("kelompok", b, kelompok_id=b["kelompok_id"], nama_kelompok=b["nama_kelompok"],
                            siswa_id=None) for b in baris]


def _pertemuan_privat(kon, guru_id: str, kini: str) -> List[dict]:
    baris = kon.execute(
        "SELECT s.order_id, o.siswa_id, s.ke, s.mulai, s.menit, s.dibatalkan "
        "FROM jadwal_pertemuan s JOIN jadwal_penempatan p ON p.order_id=s.order_id "
        "JOIN kelas_order o ON o.id=s.order_id "
        "WHERE p.guru_id=? AND p.kelompok_id IS NULL AND s.kelompok_id IS NULL AND s.mulai>=?",
        (guru_id, kini)).fetchall()
    aktif = _order_aktif_ids(kon, (b["order_id"] for b in baris), kini)
    return [_pertemuan_dict("privat", b, kelompok_id=None, nama_kelompok=None, siswa_id=b["siswa_id"])
            for b in baris if b["order_id"] in aktif]


def pertemuan_mendatang(kon, guru_id: str, kini) -> List[dict]:
    """Pertemuan Mini dan Private milik guru dengan `mulai >= kini`, urut waktu.

    Tiap item: `jenis` ("kelompok"|"privat"), `kelompok_id`, `nama_kelompok`, `siswa_id` (hanya privat),
    `ke`, `mulai` (UTC baku), `menit`, `dibatalkan`.
    """
    waktu = dasar.ke_baku(kini)
    hasil = _pertemuan_mini(kon, guru_id, waktu) + _pertemuan_privat(kon, guru_id, waktu)
    return sorted(hasil, key=lambda p: (p["mulai"], p["jenis"], p["ke"]))


def _ringkas_kelas(kon, baris, kini: str) -> dict:
    return {"id": baris["id"], "nama": baris["nama"], "kuota": int(baris["kuota"]),
            "terisi": len(_anggota_aktif(kon, baris["id"], kini)),
            "berikut": _pertemuan_berikut(kon, baris["id"], kini)}


def daftar_kelas(kon, guru_id: str, kini) -> List[dict]:
    """Kelompok Mini milik guru: `id`, `nama`, `kuota`, `terisi` (anggota aktif), `berikut` (mulai atau None)."""
    waktu = dasar.ke_baku(kini)
    baris = kon.execute("SELECT id, nama, kuota FROM jadwal_kelompok WHERE guru_id=? ORDER BY nama, id",
                        (guru_id,)).fetchall()
    return [_ringkas_kelas(kon, b, waktu) for b in baris]


def detail_kelas(kon, guru_id: str, kelompok_id, kini) -> Optional[dict]:
    """Detail satu kelompok milik guru, atau None. Id cacat, tak ada, dan milik guru lain sama-sama None."""
    if not _id_kelompok_sah(kelompok_id):
        return None
    waktu = dasar.ke_baku(kini)
    kelompok = kon.execute("SELECT id, nama, lokasi, kuota FROM jadwal_kelompok WHERE id=? AND guru_id=?",
                           (kelompok_id, guru_id)).fetchone()
    if kelompok is None:
        return None
    sesi = kon.execute("SELECT ke, mulai, menit, dibatalkan FROM jadwal_pertemuan "
                       "WHERE kelompok_id=? ORDER BY ke, id", (kelompok_id,)).fetchall()
    return {
        "nama": kelompok["nama"],
        "lokasi": kelompok["lokasi"],
        "kuota": int(kelompok["kuota"]),
        "sesi": [{"ke": int(s["ke"]), "mulai": s["mulai"], "menit": int(s["menit"]),
                  "dibatalkan": bool(s["dibatalkan"])} for s in sesi],
        "anggota": _anggota_aktif(kon, kelompok_id, waktu),
    }


def nama_siswa(kon, ids) -> Dict[int, str]:
    """Nama anak dari latihan.db untuk id hasil kueri milik guru; id yang tidak ditemukan memakai placeholder."""
    unik = sorted(set(ids))
    if not unik:
        return {}
    tanda = ",".join("?" * len(unik))
    ditemukan = {int(siswa_id): nama for siswa_id, nama in
                 kon.execute("SELECT id, nama FROM siswa WHERE id IN (%s)" % tanda, unik).fetchall()}
    return {siswa_id: ditemukan.get(siswa_id, PLACEHOLDER_NAMA) for siswa_id in unik}
